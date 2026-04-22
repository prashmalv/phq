"""
Chat API — primary officer interface.
POST /api/v1/chat/query
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.dependencies import get_agent, get_current_officer, get_ts
from backend.orchestrator.query_agent import QueryAgent
from backend.storage.timeseries_store import TimeSeriesStore

router = APIRouter(prefix="/chat")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000, description="Natural language query in Hindi or English")
    session_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[str]
    evidence_count: int
    latency_ms: int
    parsed_intent: dict
    cached: bool = False


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    agent: QueryAgent = Depends(get_agent),
    ts: TimeSeriesStore = Depends(get_ts),
    officer: dict = Depends(get_current_officer),
):
    """
    Primary chat endpoint. Accepts Hindi or English queries.
    Returns sourced, structured answers from the hybrid knowledge base.
    """
    # Check CAG cache first
    cached = await ts.get_cached_answer(req.query)
    if cached:
        return QueryResponse(**cached, cached=True)

    result = await agent.run(query=req.query, officer_id=officer["officer_id"])

    # Cache high-confidence answers
    if result["confidence"] >= 0.7:
        await ts.set_cached_answer(req.query, result)

    return QueryResponse(**result)
