"""
Report API endpoints.

GET  /api/v2/reports/           — list all reports
POST /api/v2/reports/generate   — manually trigger a report
GET  /api/v2/reports/{id}       — report metadata (JSON)
GET  /api/v2/reports/{id}/html  — full HTML report (browser/email)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional

from backend.api.routes.chat_v2 import get_officer
from backend.reports import store as rstore
from backend.reports.generator import ReportGenerator

router = APIRouter(prefix="/v2/reports")

_generator: Optional[ReportGenerator] = None


def get_generator() -> ReportGenerator:
    global _generator
    if _generator is None:
        _generator = ReportGenerator()
        rstore.init_db()
    return _generator


class GenerateRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    from_date: str = Field(..., description="YYYY-MM-DD")
    to_date: str = Field(..., description="YYYY-MM-DD")


@router.get("/")
def list_reports(officer: dict = Depends(get_officer)):
    return rstore.list_reports(limit=30)


@router.post("/generate")
async def generate_report(
    req: GenerateRequest,
    officer: dict = Depends(get_officer),
    gen: ReportGenerator = Depends(get_generator),
):
    report_id = await gen.generate(
        title=req.title,
        from_date=req.from_date,
        to_date=req.to_date,
        trigger="manual",
    )
    return {"report_id": report_id, "status": "generating"}


@router.get("/{report_id}")
def get_report_meta(report_id: str, officer: dict = Depends(get_officer)):
    report = rstore.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "report_id": report["report_id"],
        "title": report["title"],
        "from_date": report["from_date"],
        "to_date": report["to_date"],
        "status": report["status"],
        "trigger": report["trigger"],
        "created_at": report["created_at"],
    }


@router.get("/{report_id}/html", response_class=HTMLResponse)
def get_report_html(report_id: str, officer: dict = Depends(get_officer)):
    report = rstore.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.get("html"):
        return HTMLResponse("<p>Report generation in progress...</p>", status_code=202)
    return HTMLResponse(report["html"])
