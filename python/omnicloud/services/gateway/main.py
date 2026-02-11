"""
OmniCloud API Gateway
Terminal Bench v2 - FastAPI gateway with rate limiting and multi-tenant routing.

Contains bugs:
- L5: No health check endpoint defined initially
- L11: CORS middleware misconfigured - blocks inter-service calls
- I4: Rate limit bypass via X-Forwarded-For header spoofing
- J4: Health check reports healthy even when dependencies are down
"""
import os
import time
import uuid
import logging
from typing import Dict, Any, Optional
from collections import defaultdict

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniCloud Gateway", version="1.0.0")


# Should include service hostnames, not just localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  
    allow_credentials=True,
    allow_methods=["GET"],  
    allow_headers=["*"],
)

# Rate limiting state
_rate_limits: Dict[str, list] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 100  # requests per window


def get_client_ip(request: Request) -> str:
    """Get client IP for rate limiting.

    BUG I4: Trusts X-Forwarded-For header without validation.
    Attacker can spoof this header to bypass rate limits.
    """
    
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting per client IP."""
    client_ip = get_client_ip(request)
    now = time.time()

    # Clean old entries
    _rate_limits[client_ip] = [
        t for t in _rate_limits[client_ip]
        if now - t < RATE_LIMIT_WINDOW
    ]

    if len(_rate_limits[client_ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _rate_limits[client_ip].append(now)
    response = await call_next(request)
    return response


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to requests."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint.

    BUG J4: Returns healthy without checking downstream dependencies.
    Gateway should verify Redis, Kafka, and at least one backend service.
    """
    
    return {"status": "healthy", "service": "gateway"}


@app.get("/")
async def root():
    return {"service": "omnicloud-gateway", "version": "1.0.0"}


@app.get("/api/v1/services")
async def list_services():
    """List all available services."""
    return {
        "services": [
            {"name": "auth", "port": 8001, "status": "unknown"},
            {"name": "tenants", "port": 8002, "status": "unknown"},
            {"name": "compute", "port": 8003, "status": "unknown"},
            {"name": "network", "port": 8004, "status": "unknown"},
            {"name": "storage", "port": 8005, "status": "unknown"},
            {"name": "dns", "port": 8006, "status": "unknown"},
            {"name": "loadbalancer", "port": 8007, "status": "unknown"},
            {"name": "secrets", "port": 8008, "status": "unknown"},
            {"name": "config", "port": 8009, "status": "unknown"},
            {"name": "deploy", "port": 8010, "status": "unknown"},
            {"name": "monitor", "port": 8011, "status": "unknown"},
            {"name": "billing", "port": 8012, "status": "unknown"},
            {"name": "audit", "port": 8013, "status": "unknown"},
            {"name": "compliance", "port": 8014, "status": "unknown"},
        ]
    }
