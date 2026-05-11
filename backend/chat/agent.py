"""
Simplified Query Agent for Matrix integration.
Only uses Qdrant (already on their server) + LLM.
No Neo4j / TimescaleDB required for Phase 1.
"""
import time
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.orchestrator.llm_client import LLMClient


UP_DISTRICTS = settings.UP_DISTRICTS

SYSTEM_PROMPT = """You are an intelligence analyst assistant for Police HQ, Uttar Pradesh.
You help senior officers quickly find information about incidents, events, public sentiment,
and social media trends across UP districts.

Rules:
- Answer ONLY based on the evidence provided. Do not hallucinate.
- Always cite evidence using [1], [2] notation.
- Be concise and factual. Officers need quick answers.
- If evidence is insufficient, say so clearly.
- Respond in the same language as the query (Hindi or English).
- For Hindi queries, respond in Hindi.
- Mention date and district for every cited incident."""


class MatrixQueryAgent:
    def __init__(self):
        self.qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.llm = LLMClient()
        self.collection = settings.QDRANT_COLLECTION

    def _embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def _parse_time_range(self, query_lower: str) -> tuple[Optional[str], Optional[str]]:
        """Extract time range from query string."""
        now = datetime.utcnow()
        if any(x in query_lower for x in ["last 5 year", "pichle 5 saal", "5 years"]):
            return (now - timedelta(days=1825)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["last year", "pichle saal", "1 year"]):
            return (now - timedelta(days=365)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["last month", "pichle mahine", "30 day"]):
            return (now - timedelta(days=30)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["last week", "pichle hafte", "7 day"]):
            return (now - timedelta(days=7)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["today", "aaj", "24 hour"]):
            return (now - timedelta(days=1)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["recently", "recent", "abhi", "haal hi me"]):
            return (now - timedelta(days=30)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        return None, None

    def _detect_district(self, query: str) -> Optional[str]:
        query_lower = query.lower()
        for district in UP_DISTRICTS:
            if district.lower() in query_lower:
                return district
        return None

    def _build_filter(self, district: Optional[str]) -> Optional[Filter]:
        if district:
            return Filter(must=[FieldCondition(key="district", match=MatchValue(value=district))])
        return None

    def search(
        self,
        query: str,
        limit: int = 12,
        district: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> list[dict]:
        vector = self._embed(query)
        must_conditions = []
        if district:
            must_conditions.append(FieldCondition(key="district", match=MatchValue(value=district)))
        if platform:
            must_conditions.append(FieldCondition(key="platform", match=MatchValue(value=platform)))

        query_filter = Filter(must=must_conditions) if must_conditions else None
        results = self.qdrant.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            score_threshold=0.35,
        )
        return [{"score": r.score, **r.payload} for r in results]

    async def run(
        self,
        query: str,
        officer_id: str,
        session_history: list[dict] | None = None,
    ) -> dict:
        t0 = time.monotonic()

        query_lower = query.lower()
        district = self._detect_district(query)
        from_date, to_date = self._parse_time_range(query_lower)

        # Search Qdrant
        results = self.search(query=query, limit=12, district=district)

        # Filter by date if extracted from query
        if from_date and results:
            results = [
                r for r in results
                if r.get("created_at", "") >= from_date
            ]

        latency_ms = int((time.monotonic() - t0) * 1000)

        if not results:
            no_result_answer = (
                "इस query के लिए database में कोई relevant जानकारी नहीं मिली।"
                if any(c > 'ऀ' for c in query)
                else "No relevant information found in the database for this query. "
                     "Try expanding the time range or rephrasing."
            )
            return {
                "answer": no_result_answer,
                "confidence": 0.1,
                "evidence_count": 0,
                "sources": [],
                "latency_ms": latency_ms,
            }

        # Build evidence block
        evidence_lines = []
        for i, r in enumerate(results[:10], 1):
            content = str(r.get("content", ""))[:400]
            platform = r.get("platform", "unknown")
            district_str = r.get("district", "Unknown")
            date_str = str(r.get("created_at", ""))[:10]
            author = r.get("author", "")
            evidence_lines.append(
                f"[{i}] ({date_str} | {district_str} | {platform}{' | @'+author if author else ''}) {content}"
            )
        evidence_block = "\n".join(evidence_lines)

        # Include recent conversation context for follow-up questions
        context_block = ""
        if session_history:
            context_lines = []
            for msg in session_history[-4:]:
                role = "Officer" if msg["role"] == "user" else "Assistant"
                context_lines.append(f"{role}: {msg['content'][:200]}")
            context_block = "\n\nPrevious conversation:\n" + "\n".join(context_lines)

        user_prompt = f"""Query: {query}{context_block}

Evidence from database:
{evidence_block}

Answer the query based on the evidence above. Cite evidence numbers. Be concise."""

        try:
            answer = await self.llm.complete(
                prompt=user_prompt,
                system=SYSTEM_PROMPT,
                max_tokens=600,
            )
            confidence = min(0.95, 0.5 + len(results) * 0.04)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            answer = f"Found {len(results)} relevant records:\n\n" + evidence_block
            confidence = 0.4

        return {
            "answer": answer,
            "confidence": round(confidence, 2),
            "evidence_count": len(results),
            "sources": list({r.get("platform", "unknown") for r in results}),
            "district_detected": district,
            "time_range": {"from": from_date, "to": to_date} if from_date else None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
