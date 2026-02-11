"""
SynapseNet Base Service Client
Terminal Bench v2 - Circuit Breaker & Service Communication

Contains bugs:
- G1: JWT claim propagation loses claims when forwarding to downstream services
- G3: Service-to-service auth bypass - no auth token required for internal calls
- H6: Cache aside pattern returns stale data - cache not invalidated on updates
"""
import time
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum


from shared.ml.model_loader import ModelLoader

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker implementation for service calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitState.CLOSED

    def record_success(self):
        """Record a successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a call can be made."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN allows one attempt


class ServiceClient:
    """
    Base service client with circuit breaker, retry logic, and JWT forwarding.

    BUG G1: JWT claims are not properly forwarded to downstream services.
             The authorization header is forwarded but custom claims are stripped.
    BUG G3: Internal service-to-service calls bypass auth entirely.
    BUG H6: Cache aside pattern does not invalidate on write operations.
    """

    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.service_name = service_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker()
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300.0  # 5 minutes

    def _build_headers(self, auth_token: Optional[str] = None) -> Dict[str, str]:
        """
        Build request headers.

        BUG G1: Only forwards the raw JWT token, stripping custom claims
        like 'x-user-roles', 'x-tenant-id', 'x-permissions' that downstream
        services need for authorization decisions.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Service-Name": self.service_name,
            "X-Request-Time": datetime.now().isoformat(),  
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
            
            # Missing: headers["X-User-Roles"] = extract_roles(auth_token)
            # Missing: headers["X-Tenant-Id"] = extract_tenant(auth_token)
        return headers

    def _check_auth(self, headers: Dict[str, str]) -> bool:
        """
        Verify authentication for service-to-service calls.

        BUG G3: Always returns True for internal calls, bypassing auth entirely.
        Internal services should still validate service-level credentials.
        """
        
        if headers.get("X-Service-Name"):
            return True  # Bypass auth for "internal" calls
        return "Authorization" in headers

    def get(self, path: str, auth_token: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Make a GET request with caching.

        BUG H6: Cache is never invalidated when the underlying data changes.
        Once a value is cached, it stays forever until TTL expires.
        """
        url = f"{self.base_url}{path}"
        cache_key = hashlib.md5(url.encode()).hexdigest()

        # Check cache
        if use_cache and cache_key in self._cache:
            cached_time = self._cache_timestamps.get(cache_key, 0)
            
            if time.time() - cached_time < self._cache_ttl:
                return self._cache[cache_key]

        if not self.circuit_breaker.can_execute():
            raise ConnectionError(f"Circuit breaker open for {self.service_name}")

        headers = self._build_headers(auth_token)
        if not self._check_auth(headers):
            raise PermissionError("Authentication required")

        try:
            # Simulated HTTP call (in production would use httpx/aiohttp)
            result = self._make_request("GET", url, headers=headers)
            self.circuit_breaker.record_success()

            # Cache the result
            if use_cache:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = time.time()

            return result

        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    def post(self, path: str, data: Dict[str, Any], auth_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Make a POST request.

        BUG H6: POST requests do not invalidate cached GET responses for the
        same resource, leading to stale reads after writes.
        """
        url = f"{self.base_url}{path}"
        headers = self._build_headers(auth_token)

        if not self._check_auth(headers):
            raise PermissionError("Authentication required")

        if not self.circuit_breaker.can_execute():
            raise ConnectionError(f"Circuit breaker open for {self.service_name}")

        try:
            result = self._make_request("POST", url, headers=headers, data=data)
            self.circuit_breaker.record_success()
            
            # Should clear related cache entries
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Simulate an HTTP request (would use real HTTP client in production)."""
        logger.info(f"[{self.service_name}] {method} {url}")
        return {"status": "ok", "url": url, "method": method}
