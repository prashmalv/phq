"""
Query Agent for Matrix integration.
Searches two Qdrant collections (phq_events + phq_topics) and
synthesises an answer via the local LLM.
"""
import time
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
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
- Mention date and district for every cited incident.
- Official police reports (marked ★) are the most credible source — cite them first."""


class MatrixQueryAgent:
    def __init__(self):
        self.qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.llm = LLMClient()
        self.col_events = settings.QDRANT_COLLECTION
        self.col_topics = settings.QDRANT_TOPICS_COLLECTION

    def _embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def _parse_time_range(self, query_lower: str) -> tuple[Optional[str], Optional[str]]:
        now = datetime.utcnow()
        if any(x in query_lower for x in ["last 5 year", "pichle 5 saal", "5 years"]):
            return (now - timedelta(days=1825)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["last year", "pichle saal", "1 year"]):
            return (now - timedelta(days=365)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["last month", "pichle mahine", "30 day", "pichle 30"]):
            return (now - timedelta(days=30)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["last week", "pichle hafte", "7 day"]):
            return (now - timedelta(days=7)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["today", "aaj", "24 hour"]):
            return (now - timedelta(days=1)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        if any(x in query_lower for x in ["recently", "recent", "abhi", "haal hi me"]):
            return (now - timedelta(days=30)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        return None, None

    def _detect_district(self, query: str) -> Optional[str]:
        q = query.lower()
        for d in UP_DISTRICTS:
            if d.lower() in q:
                return d
        return None

    def _search_collection(
        self,
        collection: str,
        vector: list[float],
        district: Optional[str],
        limit: int,
    ) -> list[dict]:
        must = []
        if district:
            must.append(FieldCondition(key="district", match=MatchValue(value=district)))
        qfilter = Filter(must=must) if must else None
        hits = self.qdrant.search(
            collection_name=collection,
            query_vector=vector,
            limit=limit,
            query_filter=qfilter,
            with_payload=True,
            score_threshold=0.30,
        )
        return [{"score": h.score, **h.payload} for h in hits]

    def _search(self, query: str, district: Optional[str]) -> list[dict]:
        """Search both collections, merge and sort by score."""
        vector = self._embed(query)
        events = self._search_collection(self.col_events, vector, district, limit=10)
        topics = self._search_collection(self.col_topics, vector, district, limit=6)
        combined = events + topics
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined

    def _format_evidence_line(self, idx: int, r: dict) -> str:
        is_official = r.get("is_official_report") or r.get("source_table") == "district_internal_report"
        is_topic = r.get("source_table") == "topic"

        label = "★ Official Report" if is_official else ("Topic" if is_topic else r.get("platform") or "social")
        district = r.get("district") or "Unknown"
        date = str(r.get("occurred_at") or r.get("created_at") or "")[:10]
        event = r.get("event_type") or ""
        sentiment = r.get("sentiment") or ""
        topic_title = r.get("topic_title") or ""
        persons = r.get("person_names") or ""
        content = str(r.get("content") or "")[:350]

        meta_parts = [p for p in [label, district, date, event] if p]
        meta = " | ".join(meta_parts)

        extras = []
        if topic_title:
            extras.append(f"Topic: {topic_title}")
        if sentiment:
            extras.append(f"Sentiment: {sentiment}")
        if persons:
            extras.append(f"Persons: {persons}")

        line = f"[{idx}] ({meta}) {content}"
        if extras:
            line += f"\n     {' · '.join(extras)}"
        return line

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

        results = self._search(query, district)

        # Date-filter in Python (Qdrant payload dates are strings)
        if from_date:
            results = [
                r for r in results
                if (r.get("occurred_at") or r.get("created_at") or "") >= from_date
            ]

        latency_ms = int((time.monotonic() - t0) * 1000)

        if not results:
            is_hindi = any(c > "ऀ" for c in query)
            return {
                "answer": (
                    "इस query के लिए database में कोई relevant जानकारी नहीं मिली।"
                    if is_hindi else
                    "No relevant information found for this query. "
                    "Try expanding the time range or rephrasing."
                ),
                "confidence": 0.1,
                "evidence_count": 0,
                "sources": [],
                "latency_ms": latency_ms,
            }

        # Build evidence block (top 12 results)
        evidence_lines = [
            self._format_evidence_line(i, r)
            for i, r in enumerate(results[:12], 1)
        ]
        evidence_block = "\n".join(evidence_lines)

        # Recent conversation context
        context_block = ""
        if session_history:
            ctx = []
            for msg in session_history[-4:]:
                role = "Officer" if msg["role"] == "user" else "Assistant"
                ctx.append(f"{role}: {msg['content'][:200]}")
            context_block = "\n\nPrevious conversation:\n" + "\n".join(ctx)

        user_prompt = (
            f"Query: {query}{context_block}\n\n"
            f"Evidence from database (★ = official police report):\n{evidence_block}\n\n"
            "Answer the query based on the evidence above. Cite evidence numbers. Be concise."
        )

        try:
            answer = await self.llm.complete(
                prompt=user_prompt,
                system=SYSTEM_PROMPT,
                max_tokens=600,
            )
            confidence = min(0.95, 0.5 + len(results) * 0.04)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            answer = f"Found {len(results)} relevant records:\n\n{evidence_block}"
            confidence = 0.4

        # Surface unique sources (platform names + "Official Report" if present)
        sources = set()
        for r in results:
            if r.get("is_official_report") or r.get("source_table") == "district_internal_report":
                sources.add("Official Report")
            elif r.get("platform"):
                sources.add(r["platform"])
            elif r.get("source_table") == "topic":
                sources.add("Grouped Topic")

        return {
            "answer": answer,
            "confidence": round(confidence, 2),
            "evidence_count": len(results),
            "sources": sorted(sources),
            "district_detected": district,
            "time_range": {"from": from_date, "to": to_date} if from_date else None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
