"""
Events API — browse and search ingested events.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_current_officer, get_ts, get_vector
from backend.storage.timeseries_store import TimeSeriesStore
from backend.storage.vector_store import VectorStore

router = APIRouter(prefix="/events")


@router.get("/recent")
async def recent_events(
    district: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    ts: TimeSeriesStore = Depends(get_ts),
    officer: dict = Depends(get_current_officer),
):
    from_date = datetime.utcnow() - timedelta(days=days)
    return await ts.events_in_range(
        from_date=from_date,
        to_date=datetime.utcnow(),
        district=district,
        event_type=event_type,
        limit=limit,
    )


@router.get("/search")
async def search_events(
    q: str = Query(..., min_length=2),
    district: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    vector: VectorStore = Depends(get_vector),
    officer: dict = Depends(get_current_officer),
):
    return vector.search(
        query=q,
        district=district,
        event_type=event_type,
        limit=limit,
    )


@router.get("/district-summary")
async def district_summary(
    days: int = Query(30, ge=1, le=365),
    event_type: Optional[str] = Query(None),
    ts: TimeSeriesStore = Depends(get_ts),
    officer: dict = Depends(get_current_officer),
):
    from_date = datetime.utcnow() - timedelta(days=days)
    return await ts.event_count_by_district(
        from_date=from_date,
        to_date=datetime.utcnow(),
        event_type=event_type,
    )
