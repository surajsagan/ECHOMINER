"""FastAPI application factory."""
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api.routes_auth import router as auth_router
from .api.routes_admin import router as admin_router
from .api.routes_content import router as content_router
from .api.routes_jobs import router as jobs_router
from .config import get_settings
from .db import engine
from .logging_setup import configure_logging, request_id_var

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="EchoMiner API",
    version="0.3.0",
    description="EchoMiner research platform API. JSS AHER / DBT-BUILDER.",
    docs_url=None if settings.env == "prod" else "/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["content-type", "x-csrf-token"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.env == "prod":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/healthz", tags=["ops"])
def healthz():
    return {"status": "ok", "version": app.version}


@app.get("/readyz", tags=["ops"])
def readyz():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse({"status": "degraded", "database": str(exc)[:200]}, status_code=503)
    return {"status": "ready", "database": "ok"}


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(content_router)
app.include_router(admin_router)
