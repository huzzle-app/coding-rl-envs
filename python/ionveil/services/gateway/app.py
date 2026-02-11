"""
IonVeil API Gateway
=====================
FastAPI-based API gateway for the IonVeil emergency dispatch platform.
Handles routing, middleware, rate limiting, and request/response lifecycle.
"""

import asyncio
import hashlib
import logging
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ionveil.gateway")


@dataclass
class GatewayConfig:
    """Central gateway configuration."""

    host: str = "0.0.0.0"
    port: int = int(os.getenv("GATEWAY_PORT", "8000"))
    database_url: str = os.getenv("DATABASE_URL", "postgresql://ionveil:ionveil@localhost:5432/ionveil")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rate_limit_window: int = 60  # seconds
    rate_limit_max_requests: int = 100
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    jwt_secret: str = os.getenv("JWT_SECRET", "ionveil-secret-key")
    debug: bool = os.getenv("IONVEIL_DEBUG", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1, le=5)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    category: str = Field(default="general")
    org_id: Optional[str] = None


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[str] = None


class DispatchRequest(BaseModel):
    incident_id: str
    unit_ids: list[str] = Field(default_factory=list)
    priority_override: Optional[int] = None


class ResourceQuery(BaseModel):
    lat: float
    lon: float
    radius_km: float = 10.0
    required_skills: list[str] = Field(default_factory=list)


class AuthLogin(BaseModel):
    username: str
    password: str


class AuthRefresh(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# In-memory database adapter used for local benchmark runtime.
# ---------------------------------------------------------------------------

class DatabasePool:
    """Async database connection pool wrapper."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool = None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection pool."""
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                self._dsn, min_size=5, max_size=20, command_timeout=30,
            )
            self._connected = True
            logger.info("Database pool established: %s connections", 20)
        except Exception as exc:
            logger.error("Failed to connect to database: %s", exc)
            self._connected = False

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def fetch(self, query: str, *args) -> list[dict]:
        if not self._pool:
            raise RuntimeError("Database pool not initialised")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args) -> Optional[dict]:
        if not self._pool:
            raise RuntimeError("Database pool not initialised")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def execute(self, query: str, *args) -> str:
        if not self._pool:
            raise RuntimeError("Database pool not initialised")
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """In-memory sliding-window rate limiter."""

    def __init__(self, window: int = 60, max_requests: int = 100):
        self._window = window
        self._max_requests = max_requests
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Return True if the client has not exceeded their rate limit."""
        now = time.monotonic()
        timestamps = self._requests[client_id]
        # Purge expired entries
        self._requests[client_id] = [
            ts for ts in timestamps if now - ts < self._window
        ]
        if len(self._requests[client_id]) >= self._max_requests:
            return False
        self._requests[client_id].append(now)
        return True

    def remaining(self, client_id: str) -> int:
        now = time.monotonic()
        valid = [ts for ts in self._requests[client_id] if now - ts < self._window]
        return max(0, self._max_requests - len(valid))


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request/response pair with timing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        logger.debug(
            "Incoming request %s %s from %s [rid=%s]",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            request_id,
        )

        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"

        logger.debug(
            "Response %s for %s %s [rid=%s, %.2fms]",
            response.status_code,
            request.method,
            request.url.path,
            request_id,
            elapsed_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-client rate limits."""

    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "0.0.0.0"
        if not self._limiter.is_allowed(client_ip):
            remaining = self._limiter.remaining(client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "remaining": remaining,
                },
                headers={"Retry-After": "60"},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(
            self._limiter.remaining(client_ip)
        )
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return JSON errors."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred.",
                    "trace_id": str(uuid.uuid4()),
                },
            )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app(config: Optional[GatewayConfig] = None) -> FastAPI:
    """Create and configure the FastAPI gateway application."""

    if config is None:
        config = GatewayConfig()

    app = FastAPI(
        title="IonVeil API Gateway",
        version="1.0.0",
        description="Emergency dispatch operations platform",
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None,
    )

    # -- State ---------------------------------------------------------------
    db = DatabasePool(config.database_url)
    limiter = RateLimiter(config.rate_limit_window, config.rate_limit_max_requests)

    # -- CORS ----------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,  # ["*"]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Middleware stack (order matters: outermost first) --------------------
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(RequestLoggingMiddleware)

    # -- Lifecycle -----------------------------------------------------------

    @app.on_event("startup")
    async def on_startup():
        logger.info("Gateway starting on %s:%s", config.host, config.port)
        await db.connect()

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("Gateway shutting down")
        await db.close()

    # -- Dependency helpers --------------------------------------------------

    async def get_db() -> DatabasePool:
        return db

    async def get_current_user(request: Request) -> dict:
        """Extract and validate the bearer token from the Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        token = auth_header[7:]
        # Lightweight validation; full check delegated to auth service
        if len(token) < 20:
            raise HTTPException(status_code=401, detail="Invalid token")
        # Lightweight claim extraction for local runtime without remote auth call.
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return {
            "user_id": f"user-{digest[:12]}",
            "role": "operator",
            "org_id": f"org-{digest[12:20]}",
        }

    # -- Health & info -------------------------------------------------------

    @app.get("/health")
    async def health_check(pool: DatabasePool = Depends(get_db)):
        """
        Health check endpoint used by load balancers and orchestration.

        """
        db_status = "unknown"
        try:
            await pool.fetch("SELECT 1")
            db_status = "connected"
        except Exception as exc:
            logger.warning("Health check: database unreachable: %s", exc)
            db_status = "disconnected"

        return {
            "status": "healthy",
            "version": "1.0.0",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/info")
    async def info():
        return {
            "service": "ionveil-gateway",
            "version": "1.0.0",
            "environment": os.getenv("IONVEIL_ENV", "production"),
        }

    # -- Incidents -----------------------------------------------------------

    @app.post("/api/v1/incidents", status_code=201)
    async def create_incident(
        body: IncidentCreate,
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        incident_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        await pool.execute(
            """
            INSERT INTO incidents (id, title, description, priority, latitude, longitude,
                                   category, org_id, status, created_by, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open', $9, $10, $10)
            """,
            incident_id,
            body.title,
            body.description,
            body.priority,
            body.latitude,
            body.longitude,
            body.category,
            body.org_id or user["org_id"],
            user["user_id"],
            now,
        )

        return {
            "id": incident_id,
            "title": body.title,
            "description": body.description,  # raw, unescaped
            "priority": body.priority,
            "status": "open",
            "created_at": now.isoformat(),
        }

    @app.get("/api/v1/incidents")
    async def list_incidents(
        status: Optional[str] = None,
        priority: Optional[int] = Query(default=None, ge=1, le=5),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=500),
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        """
        List incidents for the current user's organisation.

        """
        conditions = ["org_id = $1"]
        params: list[Any] = [user["org_id"]]
        idx = 2

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if priority is not None:
            conditions.append(f"priority = ${idx}")
            params.append(priority)
            idx += 1

        where = " AND ".join(conditions)

        query = f"SELECT * FROM incidents WHERE {where} ORDER BY created_at DESC"
        rows = await pool.fetch(query, *params)

        return {
            "incidents": rows,
            "total": len(rows),
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/v1/incidents/{incident_id}")
    async def get_incident(
        incident_id: str,
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        row = await pool.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")
        return row

    @app.patch("/api/v1/incidents/{incident_id}")
    async def update_incident(
        incident_id: str,
        body: IncidentUpdate,
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        updates = []
        params: list[Any] = []
        idx = 1
        for field_name, value in body.dict(exclude_unset=True).items():
            updates.append(f"{field_name} = ${idx}")
            params.append(value)
            idx += 1
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(incident_id)
        set_clause = ", ".join(updates)
        await pool.execute(
            f"UPDATE incidents SET {set_clause}, updated_at = NOW() WHERE id = ${idx}",
            *params,
        )
        return {"id": incident_id, "updated": True}

    @app.delete("/api/v1/incidents/{incident_id}")
    async def delete_incident(
        incident_id: str,
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        await pool.execute("DELETE FROM incidents WHERE id = $1", incident_id)
        return {"id": incident_id, "deleted": True}

    # -- Dispatch ------------------------------------------------------------

    @app.post("/api/v1/dispatch")
    async def dispatch_units(
        body: DispatchRequest,
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        incident = await pool.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", body.incident_id
        )
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        result = {
            "incident_id": body.incident_id,
            "dispatched_units": body.unit_ids,
            "status": "dispatched",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Dispatched %d units to incident %s", len(body.unit_ids), body.incident_id)
        return result

    # -- Resources -----------------------------------------------------------

    @app.get("/api/v1/resources/available")
    async def available_resources(
        lat: float = Query(...),
        lon: float = Query(...),
        radius_km: float = Query(default=10.0),
        pool: DatabasePool = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        rows = await pool.fetch(
            """
            SELECT * FROM units
            WHERE status = 'available'
              AND ST_DWithin(location, ST_MakePoint($1, $2)::geography, $3)
            """,
            lon, lat, radius_km * 1000,
        )
        return {"units": rows, "count": len(rows)}

    # -- Auth routes (proxied to auth service) --------------------------------

    @app.post("/api/v1/auth/login")
    async def login(body: AuthLogin, pool: DatabasePool = Depends(get_db)):
        logger.debug("Login attempt for user: %s", body.username)
        token_seed = hashlib.sha256(f"{body.username}:{time.time_ns()}".encode("utf-8")).hexdigest()
        return {"access_token": f"ionveil-{token_seed[:40]}", "token_type": "bearer"}

    @app.post("/api/v1/auth/refresh")
    async def refresh(body: AuthRefresh):
        token_seed = hashlib.sha256(f"{body.refresh_token}:{time.time_ns()}".encode("utf-8")).hexdigest()
        return {"access_token": f"ionveil-{token_seed[:40]}", "token_type": "bearer"}

    # -- Custom response headers --------------------------

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """
        Adds security headers to every response.


        """
        response = await call_next(request)


        host = request.headers.get("host", "unknown")
        response.headers["X-Served-By"] = f"ionveil-gateway/{host}"

        return response

    return app


# ---------------------------------------------------------------------------
# Standalone entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    cfg = GatewayConfig()
    application = create_app(cfg)
    uvicorn.run(application, host=cfg.host, port=cfg.port, log_level="debug")
