from __future__ import annotations

import logging

import psycopg.errors

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from commerce_connector.api.config import APISettings
from commerce_connector.api.routers import ai, analytics, auth, connections, conversations, dashboards, data, database, datasets, files, health, library, me, models, ops, platforms, prompts, subscription, sync, tasks, tenants, usage


def create_app() -> FastAPI:
    settings = APISettings.from_env()
    app = FastAPI(
        title="Universal Commerce Platform API",
        version="0.6.0",
        description=(
            "Frontend API for the complete Universal Commerce platform: multi-store connections, ingestion, all finalized Supabase application tables, Bronze/Silver/Gold data, RAG/AI analytics and dashboard specifications. Backend credentials are supplied through environment variables."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    logger = logging.getLogger("commerce_connector.api")

    # Added BEFORE CORS so it sits inside it: an unexpected error becomes a JSON
    # 500 that still carries CORS headers. Without this the browser shows a
    # confusing "CORS error" instead of the real 500.
    @app.middleware("http")
    async def catch_unhandled_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except psycopg.errors.UniqueViolation:
            logger.warning("Duplicate record on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=409, content={"detail": "Yeh record pehle se maujood hai."})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": f"Internal server error ({type(exc).__name__})"})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api = "/api/v1"
    app.include_router(health.router, prefix=api)
    app.include_router(auth.router, prefix=api)
    app.include_router(me.router, prefix=api)
    app.include_router(tasks.router, prefix=api)
    app.include_router(conversations.router, prefix=api)
    app.include_router(prompts.router, prefix=api)
    app.include_router(usage.router, prefix=api)
    app.include_router(library.router, prefix=api)
    app.include_router(files.router, prefix=api)
    app.include_router(datasets.router, prefix=api)
    app.include_router(models.router, prefix=api)
    app.include_router(subscription.router, prefix=api)
    app.include_router(tenants.router, prefix=api)
    app.include_router(platforms.router, prefix=api)
    app.include_router(connections.router, prefix=api)
    app.include_router(sync.router, prefix=api)
    app.include_router(data.router, prefix=api)
    app.include_router(database.router, prefix=api)
    app.include_router(ai.router, prefix=api)
    app.include_router(analytics.router, prefix=api)
    app.include_router(ops.router, prefix=api)
    app.include_router(dashboards.router, prefix=api)

    @app.get("/", tags=["Root"])
    def root():
        return {
            "name": "Universal Commerce Platform API",
            "version": "0.6.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app


app = create_app()