"""
FastAPI application — main entry point.
All routes are prefixed with /api/v1
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.routes import chat, events, analytics, health
from backend.api.dependencies import get_container, AppContainer


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting PHQ Government Intelligence Bot API...")
    container = AppContainer()
    await container.init()
    app.state.container = container
    logger.info("All services initialized")
    yield
    # Shutdown
    await container.close()
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
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(events.router, prefix="/api/v1", tags=["events"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
