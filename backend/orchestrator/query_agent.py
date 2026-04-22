"""
LangGraph-based Query Orchestration Agent.
Decomposes a natural language query (Hindi/English), routes sub-queries to
the appropriate DB(s), merges results, and generates a cited answer.

Flow:
  parse_query → route_to_dbs (parallel) → merge_results → generate_answer
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from loguru import logger

from backend.config import settings
from backend.orchestrator.llm_client import LLMClient
from backend.storage.graph_store import GraphStore
from backend.storage.search_store import SearchStore
from backend.storage.timeseries_store import TimeSeriesStore
from backend.storage.vector_store import VectorStore


# ─── Agent State ────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    query: str
    query_lang: str
    parsed: dict               # extracted intents: time_range, district, event_type, entities, analysis_type
    vector_results: list[dict]
    graph_results: list[dict]
    ts_results: list[dict]
    search_results: list[dict]
    merged_results: list[dict]
    answer: str
    sources: list[str]
    confidence: float
    latency_ms: int
    error: Optional[str]


# ─── Node functions ─────────────────────────────────────────────────────────

class QueryAgent:
    def __init__(
        self,
        vector: VectorStore,
        graph: GraphStore,
        ts: TimeSeriesStore,
        search: SearchStore,
        llm: LLMClient,
    ):
        self.vector = vector
        self.graph = graph
        self.ts = ts
        self.search = search
        self.llm = llm
        self.graph_workflow = self._build_graph()

    def _build_graph(self) -> Any:
        g = StateGraph(AgentState)
        g.add_node("parse_query", self._parse_query)
        g.add_node("route_to_dbs", self._route_to_dbs)
        g.add_node("merge_results", self._merge_results)
        g.add_node("generate_answer", self._generate_answer)

        g.set_entry_point("parse_query")
        g.add_edge("parse_query", "route_to_dbs")
        g.add_edge("route_to_dbs", "merge_results")
        g.add_edge("merge_results", "generate_answer")
        g.add_edge("generate_answer", END)
        return g.compile()

    # ─── Node: parse_query ──────────────────────────────────────────────────

    async def _parse_query(self, state: AgentState) -> AgentState:
        query = state["query"]
        prompt = f"""You are a query parser for a government intelligence system.
Extract structured intent from this query: "{query}"

Respond ONLY with valid JSON (no markdown):
{{
  "district": "district name or null",
  "time_range_days": number (e.g. 1825 for 5 years, 30 for last month, null if not specified),
  "from_date": "ISO date or null",
  "to_date": "ISO date or null",
  "event_type": "violence|stampede|protest|accident|natural_disaster|misinformation|fire|crime|general or null",
  "persons": ["list of person names mentioned"],
  "analysis_type": "incident|sentiment|comparison|person_trace|count",
  "keywords": ["important search keywords from the query"],
  "language": "hi|en"
}}"""
        try:
            parsed_str = await self.llm.complete(prompt, max_tokens=300)
            parsed = json.loads(parsed_str)
        except Exception as e:
            logger.warning(f"Query parsing failed, using defaults: {e}")
            parsed = {
                "district": None, "time_range_days": 365,
                "event_type": None, "persons": [],
                "analysis_type": "incident", "keywords": [query],
                "language": "en",
            }

        # Resolve time range
        if parsed.get("time_range_days") and not parsed.get("from_date"):
            parsed["from_date"] = (
                datetime.utcnow() - timedelta(days=parsed["time_range_days"])
            ).isoformat()
            parsed["to_date"] = datetime.utcnow().isoformat()

        return {**state, "parsed": parsed, "query_lang": parsed.get("language", "en")}

    # ─── Node: route_to_dbs ─────────────────────────────────────────────────

    async def _route_to_dbs(self, state: AgentState) -> AgentState:
        p = state["parsed"]
        query = state["query"]

        district = p.get("district")
        event_type = p.get("event_type")
        from_date = datetime.fromisoformat(p["from_date"]) if p.get("from_date") else None
        to_date = datetime.fromisoformat(p["to_date"]) if p.get("to_date") else None
        keywords = " ".join(p.get("keywords", [query]))
        persons = p.get("persons", [])

        # Run all DB queries in parallel
        tasks = {
            "vector": self.vector.search(
                query=keywords,
                district=district,
                event_type=event_type,
                limit=15,
            ),
            "search": self.search.keyword_search(
                query=keywords,
                district=district,
                event_type=event_type,
                from_date=from_date,
                to_date=to_date,
                limit=15,
            ),
        }

        # Time-series only if time range is specified
        if from_date:
            tasks["ts"] = self.ts.events_in_range(
                from_date=from_date,
                to_date=to_date or datetime.utcnow(),
                district=district,
                event_type=event_type,
                limit=50,
            )

        # Graph only for relational queries
        graph_results = []
        if persons:
            for person in persons[:3]:
                graph_results.extend(self.graph.events_by_person(person, limit=10))
        elif district and p.get("analysis_type") != "sentiment":
            graph_results = self.graph.events_in_location(
                district=district,
                event_type=event_type,
                from_date=from_date,
                to_date=to_date,
                limit=30,
            )

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        result_map = dict(zip(tasks.keys(), results))

        return {
            **state,
            "vector_results": result_map.get("vector", []) if not isinstance(result_map.get("vector"), Exception) else [],
            "search_results": result_map.get("search", []) if not isinstance(result_map.get("search"), Exception) else [],
            "ts_results": result_map.get("ts", []) if not isinstance(result_map.get("ts"), Exception) else [],
            "graph_results": graph_results,
        }

    # ─── Node: merge_results ────────────────────────────────────────────────

    async def _merge_results(self, state: AgentState) -> AgentState:
        seen_ids: set = set()
        merged = []
        sources_used = []

        all_results = [
            ("vector", state.get("vector_results", [])),
            ("search", state.get("search_results", [])),
            ("ts", state.get("ts_results", [])),
            ("graph", state.get("graph_results", [])),
        ]

        for db_name, results in all_results:
            if results:
                sources_used.append(db_name)
            for r in results:
                eid = str(r.get("event_id", ""))
                if eid and eid in seen_ids:
                    continue
                seen_ids.add(eid)
                merged.append({**r, "_db": db_name})

        # Sort by occurred_at descending (where available)
        merged.sort(
            key=lambda x: str(x.get("occurred_at", "")),
            reverse=True,
        )

        # Cross-source credibility boost: events confirmed by 2+ sources score higher
        # (simple heuristic: events with same content hash from multiple DBs)
        top_results = merged[:30]

        return {**state, "merged_results": top_results, "sources": sources_used}

    # ─── Node: generate_answer ──────────────────────────────────────────────

    async def _generate_answer(self, state: AgentState) -> AgentState:
        query = state["query"]
        results = state["merged_results"]
        p = state["parsed"]

        if not results:
            return {
                **state,
                "answer": "No relevant incidents found in the database for this query. Consider expanding the time range or checking a different district.",
                "confidence": 0.1,
            }

        # Build evidence block (top 10 results)
        evidence_lines = []
        for i, r in enumerate(results[:10], 1):
            content = str(r.get("content", ""))[:300]
            district = r.get("district", "Unknown")
            date = str(r.get("occurred_at", ""))[:10]
            source = r.get("source", "unknown")
            ev_type = r.get("event_type", "")
            evidence_lines.append(
                f"[{i}] ({date}, {district}, {source}) [{ev_type}] {content}"
            )
        evidence_block = "\n".join(evidence_lines)

        system_prompt = """You are a government intelligence analyst for Police HQ, Uttar Pradesh.
Answer the officer's query based ONLY on the evidence provided.
Be factual, concise, and cite evidence numbers like [1], [2].
Provide a confidence level (High/Medium/Low) based on evidence quality and volume.
Respond in the same language as the query (Hindi or English).
Do NOT speculate beyond the evidence."""

        user_prompt = f"""Query: {query}

Evidence:
{evidence_block}

Provide:
1. Direct answer to the query
2. Key incidents summary (date, location, type)
3. Confidence level and reasoning
4. Any conflicting information detected"""

        try:
            answer = await self.llm.complete(
                user_prompt, system=system_prompt, max_tokens=800
            )
            confidence = 0.8 if len(results) >= 5 else 0.5
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            answer = f"Found {len(results)} relevant records. Evidence: {evidence_block[:500]}"
            confidence = 0.4

        return {**state, "answer": answer, "confidence": confidence}

    # ─── Public interface ────────────────────────────────────────────────────

    async def run(self, query: str, officer_id: str = "anonymous") -> dict:
        start = time.monotonic()
        initial_state: AgentState = {
            "query": query,
            "query_lang": "en",
            "parsed": {},
            "vector_results": [],
            "graph_results": [],
            "ts_results": [],
            "search_results": [],
            "merged_results": [],
            "answer": "",
            "sources": [],
            "confidence": 0.0,
            "latency_ms": 0,
            "error": None,
        }

        final_state = await self.graph_workflow.ainvoke(initial_state)
        latency_ms = int((time.monotonic() - start) * 1000)

        # Log audit trail
        await self.ts.log_query({
            "officer_id": officer_id,
            "query_text": query,
            "query_lang": final_state.get("query_lang"),
            "answer_text": final_state.get("answer"),
            "db_sources": final_state.get("sources"),
            "latency_ms": latency_ms,
        })

        return {
            "answer": final_state["answer"],
            "confidence": final_state["confidence"],
            "sources": final_state["sources"],
            "evidence_count": len(final_state["merged_results"]),
            "latency_ms": latency_ms,
            "parsed_intent": final_state["parsed"],
        }
