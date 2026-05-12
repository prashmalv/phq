"""
FastAPI application — main entry point.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from backend.api.routes import health
from backend.api.routes.chat_v2 import router as chat_v2_router
from backend.api.routes.reports import router as reports_router
from backend.sync.embedding_sync import EmbeddingSync
from backend.reports.generator import ReportGenerator
from backend.reports.scheduler import ReportScheduler
from backend.reports.store import init_db as init_reports_db


FRONTEND_DEDICATED = Path(__file__).parent.parent.parent / "frontend" / "dedicated"
FRONTEND_WIDGET = Path(__file__).parent.parent.parent / "frontend" / "widget"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PHQ Intelligence Bot API...")

    # Init databases
    init_reports_db()

    # Start embedding sync in background
    syncer = EmbeddingSync()
    sync_task = asyncio.create_task(syncer.run_forever(interval_seconds=60))
    logger.info("Embedding sync loop started")

    # Start report scheduler in background
    generator = ReportGenerator()
    scheduler = ReportScheduler(generator)
    sched_task = asyncio.create_task(scheduler.run_forever())
    logger.info("Report scheduler started")

    yield

    sync_task.cancel()
    sched_task.cancel()
    logger.info("API shutdown complete")


app = FastAPI(
    title="PHQ Government Intelligence Bot",
    version="1.0.0",
    description="AI-powered decision support for Police HQ, Uttar Pradesh",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://matrixupp.com",
        "https://aibot.matrixupp.com",
        # wildcard subdomain support via regex is not native in FastAPI CORS —
        # list known Matrix subdomains here, or use allow_origins=["*"] internally
        "http://localhost:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API routes ──────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat_v2_router, prefix="/api", tags=["chat"])
app.include_router(reports_router, prefix="/api", tags=["reports"])

# ─── Static files (widget JS + CSS) ──────────────────────────────────────────
if FRONTEND_WIDGET.exists():
    app.mount("/static/widget", StaticFiles(directory=str(FRONTEND_WIDGET)), name="widget")

if FRONTEND_DEDICATED.exists():
    app.mount("/static/app", StaticFiles(directory=str(FRONTEND_DEDICATED)), name="dedicated")


# ─── Dedicated chat page (served at root) ────────────────────────────────────
@app.get("/", include_in_schema=False)
@app.get("/ai-bot/", include_in_schema=False)
async def serve_chat_page():
    index = FRONTEND_DEDICATED / "index.html"
    if index.exists():
        from fastapi.responses import HTMLResponse
        content = index.read_text()
        # Fix relative asset paths to absolute (assets served at /static/app/)
        content = content.replace('href="app.css"', 'href="/static/app/app.css"')
        content = content.replace('src="app.js"',   'src="/static/app/app.js"')
        return HTMLResponse(content)
    return {"message": "PHQ Intelligence Bot API", "docs": "/api/docs"}
