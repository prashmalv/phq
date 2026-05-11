"""
Chat API v2 — Matrix-integrated version.
Handles sessions, history, JWT auth from Matrix.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
import jwt

from backend.config import settings
from backend.chat import history as hist
from backend.chat.agent import MatrixQueryAgent

router = APIRouter(prefix="/v2/chat")

# Shared agent instance (initialized on first use)
_agent: MatrixQueryAgent | None = None

def get_agent() -> MatrixQueryAgent:
    global _agent
    if _agent is None:
        _agent = MatrixQueryAgent()
        hist.init_db()
    return _agent


# ─── Auth ────────────────────────────────────────────────────────────────────

def decode_matrix_jwt(token: str) -> dict:
    """
    Decode JWT from Matrix dashboard.
    In dev mode (no secret configured) returns a dummy officer.
    UPDATE: Replace 'YOUR_MATRIX_JWT_SECRET' with the actual secret from Matrix team.
    """
    if not settings.MATRIX_JWT_SECRET:
        return {"officer_id": "dev_officer", "name": "Dev Officer"}
    try:
        payload = jwt.decode(
            token,
            settings.MATRIX_JWT_SECRET,
            algorithms=["HS256"],
        )
        return {
            "officer_id": payload.get("sub") or payload.get("id") or payload.get("officer_id"),
            "name": payload.get("name") or payload.get("username"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_officer(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return decode_matrix_jwt(authorization[7:])


# ─── Models ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    session_id: Optional[str] = None   # None → create new session


class QueryResponse(BaseModel):
    session_id: str
    answer: str
    confidence: float
    evidence_count: int
    sources: list[str]
    district_detected: Optional[str]
    latency_ms: int


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    officer: dict = Depends(get_officer),
    agent: MatrixQueryAgent = Depends(get_agent),
):
    officer_id = officer["officer_id"]

    # Session management
    session_id = req.session_id
    if not session_id:
        session_id = hist.create_session(officer_id, req.query)
    else:
        # Verify session belongs to this officer (security check)
        sessions = hist.list_sessions(officer_id)
        if not any(s["session_id"] == session_id for s in sessions):
            raise HTTPException(status_code=403, detail="Session not found")

    # Get conversation context for follow-up questions
    session_history = hist.get_recent_context(session_id)

    # Save user message
    hist.add_message(session_id, "user", req.query)

    # Run agent
    result = await agent.run(
        query=req.query,
        officer_id=officer_id,
        session_history=session_history,
    )

    # Save assistant message with metadata
    hist.add_message(session_id, "assistant", result["answer"], meta={
        "confidence": result["confidence"],
        "evidence_count": result["evidence_count"],
        "sources": result["sources"],
        "latency_ms": result["latency_ms"],
    })

    return QueryResponse(
        session_id=session_id,
        answer=result["answer"],
        confidence=result["confidence"],
        evidence_count=result["evidence_count"],
        sources=result["sources"],
        district_detected=result.get("district_detected"),
        latency_ms=result["latency_ms"],
    )


@router.get("/sessions")
def list_sessions(officer: dict = Depends(get_officer)):
    """List all chat sessions for the logged-in officer."""
    return hist.list_sessions(officer["officer_id"])


@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    officer: dict = Depends(get_officer),
):
    """Get full message history for a session."""
    sessions = hist.list_sessions(officer["officer_id"])
    if not any(s["session_id"] == session_id for s in sessions):
        raise HTTPException(status_code=403, detail="Session not found")
    return hist.get_messages(session_id)
