"""
Analytics API — trends, sentiment, district comparisons.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_current_officer, get_ts
from backend.storage.timeseries_store import TimeSeriesStore

router = APIRouter(prefix="/analytics")


@router.get("/trend")
async def district_trend(
    district: str = Query(...),
    days: int = Query(30, ge=7, le=365),
    event_type: Optional[str] = Query(None),
    ts: TimeSeriesStore = Depends(get_ts),
    officer: dict = Depends(get_current_officer),
):
    """Daily event count and sentiment trend for a district."""
    return await ts.daily_trend(district=district, days=days, event_type=event_type)
