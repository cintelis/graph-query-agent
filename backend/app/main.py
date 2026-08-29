"""FastAPI entrypoint for the orchestration agent (infrastructure scaffold).

This is the API-gateway shell (spec §5.1). It currently exposes only health
and readiness probes that prove the backing infrastructure is wired up:

* ``GET /health`` — liveness: the process is running (no dependency checks).
* ``GET /ready``  — readiness: pings Neo4j and Postgres; 200 when both are
  reachable, 503 (``degraded``) otherwise.

It also mounts the Auditor Console (``app.auditor``): a governed,
deterministic, strictly read-only query surface over an external
DesignGraph Neo4j, under ``/api/*``. The full planner/tool-registry stack
(spec §5) remains a later deliverable.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auditor.router import router as auditor_router
from app.config import settings
from app.db import neo4j, postgres


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Release pooled connections on shutdown.
    await neo4j.close()
    await postgres.close()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# The Auditor Console UI is a static file (opened from file:// or any local
# static server), so CORS must be permissive for the local demo. Every route
# is read-only and unauthenticated demo surface — nothing sensitive to CSRF.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Auditor Console: governed, deterministic, read-only DesignGraph queries.
# Requires only Neo4j; Postgres stays untouched/optional for these routes.
app.include_router(auditor_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready")
async def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    healthy = True
    for name, probe in (("neo4j", neo4j.ping), ("postgres", postgres.ping)):
        try:
            await probe()
            checks[name] = "up"
        except Exception as exc:  # noqa: BLE001 — surface the reason in the probe body
            checks[name] = f"down: {exc}"
            healthy = False

    body = {"status": "ready" if healthy else "degraded", "checks": checks}
    return JSONResponse(body, status_code=200 if healthy else 503)
