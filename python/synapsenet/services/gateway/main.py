"""
SynapseNet API Gateway
Terminal Bench v2 - FastAPI Gateway Service

Contains bugs:
- L11: CORS misconfiguration blocks cross-service calls
- I4: Rate limit bypass via X-Forwarded-For header spoofing
- J1: Trace context not propagated to downstream services
- K1: Environment variable precedence wrong - config file overrides env
"""
import os
import time
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "rate_limit_per_minute": 100,
    "cors_allowed_origins": ["http://localhost:3000"],
    "request_timeout": 30,
}


def get_config(key: str) -> Any:
    """
    Get configuration value.

    BUG K1: Returns config file value even when environment variable is set.
    Should check env vars first, then fall back to config file.
    """
    
    if key in DEFAULT_CONFIG:
        return DEFAULT_CONFIG[key]
    # Environment variable is checked second (should be first)
    env_value = os.environ.get(key.upper())
    if env_value is not None:
        return env_value
    return None


class RateLimiter:
    """
    Request rate limiter.

    BUG I4: Uses X-Forwarded-For header to identify clients, which can be spoofed.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._request_counts: Dict[str, list] = {}

    def check_rate_limit(self, request_headers: Dict[str, str]) -> bool:
        """
        Check if a request is within rate limits.

        BUG I4: Uses X-Forwarded-For header to identify clients.
        An attacker can spoof this header to bypass rate limiting.
        """
        
        client_ip = request_headers.get("X-Forwarded-For", request_headers.get("remote_addr", "unknown"))

        now = time.time()
        if client_ip not in self._request_counts:
            self._request_counts[client_ip] = []

        # Clean old entries
        self._request_counts[client_ip] = [
            t for t in self._request_counts[client_ip]
            if now - t < self.window_seconds
        ]

        if len(self._request_counts[client_ip]) >= self.max_requests:
            return False

        self._request_counts[client_ip].append(now)
        return True


class TraceContext:
    """
    Distributed tracing context.

    BUG J1: Trace context is created but not propagated to Kafka messages
    or downstream HTTP calls.
    """

    def __init__(self):
        self.trace_id = str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())
        self.parent_span_id: Optional[str] = None

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "TraceContext":
        """Extract trace context from request headers."""
        ctx = cls()
        ctx.trace_id = headers.get("X-Trace-Id", ctx.trace_id)
        ctx.parent_span_id = headers.get("X-Span-Id")
        return ctx

    def to_headers(self) -> Dict[str, str]:
        """
        Convert trace context to headers for propagation.

        BUG J1: This method exists but is never called when making
        downstream requests or publishing Kafka messages.
        """
        headers = {
            "X-Trace-Id": self.trace_id,
            "X-Span-Id": self.span_id,
        }
        if self.parent_span_id:
            headers["X-Parent-Span-Id"] = self.parent_span_id
        return headers



CORS_CONFIG = {
    "allow_origins": get_config("cors_allowed_origins"),  # Only localhost:3000
    "allow_methods": ["GET"],  
    "allow_headers": ["Content-Type"],  
    "allow_credentials": False,  
}


def create_app():
    """Create the FastAPI application."""
    rate_limiter = RateLimiter(
        max_requests=get_config("rate_limit_per_minute"),
    )

    return {
        "service": "gateway",
        "port": 8000,
        "rate_limiter": rate_limiter,
        "cors_config": CORS_CONFIG,
    }


class RequestDeduplicator:
    """Deduplicate incoming requests using idempotency keys."""

    def __init__(self, ttl_seconds: float = 300.0):
        self.ttl_seconds = ttl_seconds
        self._seen: Dict[str, Dict[str, Any]] = {}

    def _hash_key(self, idempotency_key: str) -> str:
        """Hash the idempotency key for storage."""
        return str(hash(idempotency_key))

    def is_duplicate(self, idempotency_key: str) -> bool:
        """Check if a request with this key was already processed."""
        hashed = self._hash_key(idempotency_key)
        if hashed in self._seen:
            entry = self._seen[hashed]
            age = time.time() - entry["timestamp"]
            if age < self.ttl_seconds:
                return True
            del self._seen[hashed]
        return False

    def record(self, idempotency_key: str, response: Dict[str, Any]):
        """Record a processed request."""
        hashed = self._hash_key(idempotency_key)
        self._seen[hashed] = {
            "response": response,
            "timestamp": time.time(),
        }

    def get_cached_response(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get the cached response for a duplicate request."""
        hashed = self._hash_key(idempotency_key)
        entry = self._seen.get(hashed)
        if entry and time.time() - entry["timestamp"] < self.ttl_seconds:
            return entry["response"]
        return None

    def cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, v in self._seen.items()
                   if now - v["timestamp"] >= self.ttl_seconds]
        for k in expired:
            del self._seen[k]


class CircuitBreakerRegistry:
    """Manage circuit breakers for multiple downstream services."""

    def __init__(self, default_threshold: int = 5, default_timeout: float = 30.0):
        self.default_threshold = default_threshold
        self.default_timeout = default_timeout
        self._breakers: Dict[str, Dict[str, Any]] = {}

    def get_or_create(self, service_name: str) -> Dict[str, Any]:
        """Get or create a circuit breaker for a service."""
        if service_name not in self._breakers:
            self._breakers[service_name] = {
                "state": "closed",
                "failure_count": 0,
                "last_failure_time": 0.0,
                "threshold": self.default_threshold,
                "timeout": self.default_timeout,
                "success_count": 0,
            }
        return self._breakers[service_name]

    def record_success(self, service_name: str):
        """Record a successful call to a service."""
        breaker = self.get_or_create(service_name)
        breaker["success_count"] += 1
        if breaker["state"] == "half_open":
            breaker["failure_count"] = 0
            breaker["state"] = "closed"

    def record_failure(self, service_name: str):
        """Record a failed call to a service."""
        breaker = self.get_or_create(service_name)
        breaker["failure_count"] += 1
        breaker["last_failure_time"] = time.time()
        if breaker["failure_count"] >= breaker["threshold"]:
            breaker["state"] = "open"

    def can_call(self, service_name: str) -> bool:
        """Check if a call to the service is allowed."""
        breaker = self.get_or_create(service_name)
        if breaker["state"] == "closed":
            return True
        if breaker["state"] == "open":
            elapsed = time.time() - breaker["last_failure_time"]
            if elapsed >= breaker["timeout"]:
                breaker["state"] = "half_open"
                return True
            return False
        return True

    def get_all_states(self) -> Dict[str, str]:
        """Get the state of all circuit breakers."""
        return {name: info["state"] for name, info in self._breakers.items()}


# Module-level app creation for uvicorn
app = create_app()
