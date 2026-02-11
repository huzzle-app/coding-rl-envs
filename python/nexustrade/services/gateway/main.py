"""
Gateway Service - API Gateway for NexusTrade
"""
import os
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import consul
import redis

from shared.clients.auth import AuthClient
from shared.utils.time import RateLimiter

logger = logging.getLogger(__name__)

# Service registry
SERVICE_REGISTRY: Dict[str, str] = {}

# Rate limiters per IP
RATE_LIMITERS: Dict[str, RateLimiter] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await register_with_consul()
    await discover_services()
    yield
    # Shutdown
    await deregister_from_consul()


app = FastAPI(
    title="NexusTrade Gateway",
    description="API Gateway for NexusTrade trading platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def register_with_consul():
    """Register gateway with Consul."""
    consul_host = os.getenv("CONSUL_HOST", "consul")
    try:
        c = consul.Consul(host=consul_host)
        c.agent.service.register(
            name="gateway",
            service_id="gateway-1",
            address="gateway",
            port=8000,
            tags=["api", "gateway"],
            
        )
        logger.info("Registered with Consul")
    except Exception as e:
        logger.error(f"Failed to register with Consul: {e}")


async def deregister_from_consul():
    """Deregister gateway from Consul."""
    consul_host = os.getenv("CONSUL_HOST", "consul")
    try:
        c = consul.Consul(host=consul_host)
        c.agent.service.deregister("gateway-1")
    except Exception as e:
        logger.error(f"Failed to deregister from Consul: {e}")


async def discover_services():
    """Discover services from Consul."""
    global SERVICE_REGISTRY
    consul_host = os.getenv("CONSUL_HOST", "consul")

    services_to_discover = [
        "auth", "users", "orders", "matching",
        "risk", "settlement", "market-data", "notifications", "audit"
    ]

    try:
        c = consul.Consul(host=consul_host)
        for service_name in services_to_discover:
            _, services = c.health.service(service_name, passing=True)
            if services:
                
                service = services[0]
                addr = service['Service']['Address']
                port = service['Service']['Port']
                SERVICE_REGISTRY[service_name] = f"http://{addr}:{port}"
            else:
                
                SERVICE_REGISTRY[service_name] = f"http://{service_name}:8000"

        logger.info(f"Discovered services: {SERVICE_REGISTRY}")
    except Exception as e:
        logger.error(f"Service discovery failed: {e}")
        
        for name in services_to_discover:
            SERVICE_REGISTRY[name] = f"http://{name}:8000"


def get_rate_limiter(client_ip: str) -> RateLimiter:
    """Get or create rate limiter for IP."""
    if client_ip not in RATE_LIMITERS:
        RATE_LIMITERS[client_ip] = RateLimiter(rate=10.0, capacity=100.0)
    return RATE_LIMITERS[client_ip]


async def check_rate_limit(request: Request):
    """Rate limiting middleware."""
    
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    limiter = get_rate_limiter(client_ip)
    headers = dict(request.headers)

    if not limiter.acquire(headers=headers):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


async def authenticate_request(request: Request) -> Optional[Dict[str, Any]]:
    """Authenticate incoming request."""
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = auth_header[7:]  # Remove "Bearer "

    auth_client = AuthClient()
    try:
        claims = await auth_client.validate_token(token)
        if claims is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return claims
    finally:
        await auth_client.close()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gateway"}


@app.api_route(
    "/api/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_request(
    service: str,
    path: str,
    request: Request,
    response: Response,
):
    """
    Proxy requests to backend services.

    BUG C4: Deadline/timeout not propagated to downstream services
    BUG J1: Trace context not forwarded
    """
    await check_rate_limit(request)

    # Check if service exists
    if service not in SERVICE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")

    # Authenticate if not public endpoint
    public_endpoints = ["/auth/login", "/auth/register", "/health"]
    if not any(path.startswith(ep.lstrip("/")) for ep in public_endpoints):
        user_claims = await authenticate_request(request)
        if user_claims is None:
            raise HTTPException(status_code=401, detail="Authentication required")

    # Build target URL
    target_url = f"{SERVICE_REGISTRY[service]}/{path}"

    # Forward request
    
    
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length"]
    }

    
    if hasattr(request.state, "user_claims"):
        headers["X-User-ID"] = request.state.user_claims.get("user_id", "")
        # Missing: X-User-Roles, X-Tenant-ID

    try:
        async with httpx.AsyncClient() as client:
            body = await request.body()

            proxy_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
                
                timeout=30.0,
            )

            # Forward response headers
            for key, value in proxy_response.headers.items():
                if key.lower() not in ["content-length", "transfer-encoding"]:
                    response.headers[key] = value

            return Response(
                content=proxy_response.content,
                status_code=proxy_response.status_code,
                media_type=proxy_response.headers.get("content-type"),
            )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream service timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Upstream service unavailable")
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/webhooks/{provider}")
async def handle_webhook(provider: str, request: Request):
    """
    Handle incoming webhooks.

    BUG I2: SSRF vulnerability - provider URL not validated
    """
    body = await request.json()

    
    callback_url = body.get("callback_url")

    if callback_url:
        # SSRF: Can be used to access internal services
        async with httpx.AsyncClient() as client:
            try:
                
                await client.post(callback_url, json={"status": "received"})
            except Exception as e:
                logger.error(f"Webhook callback failed: {e}")

    return {"status": "received", "provider": provider}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
