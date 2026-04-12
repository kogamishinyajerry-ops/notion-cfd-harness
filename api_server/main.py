"""
FastAPI Application Factory

Creates and configures the FastAPI application for AI-CFD Knowledge Harness.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_server.config import (
    API_PREFIX,
    CORS_ORIGINS,
    DEBUG,
    DOCS_URL,
    HOST,
    OPENAPI_URL,
    PORT,
    REDOC_URL,
)
from api_server.routers import cases, jobs, knowledge, status, auth, websocket, visualization, pipelines, sweeps

logger = logging.getLogger(__name__)

# Application start time for uptime calculation
APP_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    from api_server.services.trame_session_manager import get_trame_session_manager

    logger.info(f"Starting AI-CFD Knowledge Harness API v1.6.0")
    logger.info(f"Server: {HOST}:{PORT}, Debug: {DEBUG}")

    # Start Trame idle monitor
    trame_manager = get_trame_session_manager()
    trame_manager.start_idle_monitor()

    # Initialize pipeline database (schema v3 — pipelines + steps + sweeps + sweep_cases tables)
    from api_server.services.pipeline_db import init_pipeline_db
    init_pipeline_db()  # idempotent; schema v3 applied automatically
    logger.info("Sweep database initialized (shared with pipelines.db)")

    yield

    # Pipeline cleanup on shutdown (PIPE-06)
    from api_server.services.cleanup_handler import get_cleanup_handler
    cleanup_handler = get_cleanup_handler()
    await cleanup_handler.cleanup_on_server_shutdown()
    logger.info("Pipeline cleanup completed on shutdown")

    # Stop Trame idle monitor
    await trame_manager.stop_idle_monitor()
    logger.info("Shutting down AI-CFD Knowledge Harness API")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="AI-CFD Knowledge Harness API",
        description=(
            "REST API for AI-CFD Knowledge Harness system providing:\n"
            "- Case management (CRUD operations)\n"
            "- Job submission and status monitoring\n"
            "- Knowledge registry queries\n"
            "- Report generation and verification"
        ),
        version="1.2.0",
        docs_url=DOCS_URL,
        redoc_url=REDOC_URL,
        openapi_url=OPENAPI_URL,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(status.router, prefix=API_PREFIX, tags=["status"])
    app.include_router(auth.router, prefix=API_PREFIX, tags=["auth"])
    app.include_router(cases.router, prefix=API_PREFIX, tags=["cases"])
    app.include_router(jobs.router, prefix=API_PREFIX, tags=["jobs"])
    app.include_router(knowledge.router, prefix=API_PREFIX, tags=["knowledge"])
    app.include_router(websocket.router, tags=["websocket"])
    app.include_router(visualization.router, prefix=API_PREFIX, tags=["visualization"])
    app.include_router(pipelines.router, prefix=API_PREFIX, tags=["pipelines"])
    app.include_router(sweeps.router, prefix=API_PREFIX, tags=["sweeps"])

    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint returning API information."""
        return {
            "name": "AI-CFD Knowledge Harness API",
            "version": "1.2.0",
            "docs": DOCS_URL,
            "openapi": OPENAPI_URL,
        }

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
    )
