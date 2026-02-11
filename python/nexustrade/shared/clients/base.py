"""
Base service client with circuit breaker pattern.
"""
import asyncio
import time
import logging
from typing import Optional, Any, Dict, Callable
from enum import Enum
from dataclasses import dataclass, field
import httpx

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation for service calls.

    BUG C1: Circuit breaker never opens - threshold check is wrong
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = CircuitState.CLOSED
                self._half_open_calls = 0
                logger.info("Circuit breaker closed after successful half-open calls")

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        
        if self._failure_count > self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def can_execute(self) -> bool:
        """Check if a call can be executed."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                return True
            return False

        # Half-open state
        return self._half_open_calls < self.half_open_max_calls

    @property
    def state(self) -> CircuitState:
        return self._state


class ServiceClient:
    """
    Base HTTP client for service-to-service communication.
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker()

        
        self._client: Optional[httpx.AsyncClient] = None
        self._request_coalescing: Dict[str, asyncio.Future] = {}

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _execute_with_retry(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        """Execute request with retry logic."""
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            if not self.circuit_breaker.can_execute():
                raise Exception(f"Circuit breaker is open for {self.service_name}")

            try:
                client = await self.get_client()
                response = await client.request(method, path, **kwargs)

                if response.status_code >= 500:
                    
                    self.circuit_breaker.record_failure()
                    last_error = Exception(f"Server error: {response.status_code}")
                    # No backoff - immediate retry
                    continue

                self.circuit_breaker.record_success()
                return response

            except httpx.TimeoutException as e:
                self.circuit_breaker.record_failure()
                last_error = e
                
                continue
            except Exception as e:
                self.circuit_breaker.record_failure()
                last_error = e
                continue

        raise last_error or Exception("Max retries exceeded")

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        coalesce: bool = False,
    ) -> httpx.Response:
        """
        Make a GET request.

        BUG C3: Request coalescing can leak data between users if coalesce=True
        """
        if coalesce:
            cache_key = f"{path}:{params}"
            if cache_key in self._request_coalescing:
                # Wait for existing request - BUG: returns same response to different users
                return await self._request_coalescing[cache_key]

            future = asyncio.get_event_loop().create_future()
            self._request_coalescing[cache_key] = future

            try:
                response = await self._execute_with_retry("GET", path, params=params, headers=headers)
                future.set_result(response)
                return response
            finally:
                del self._request_coalescing[cache_key]

        return await self._execute_with_retry("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make a POST request."""
        return await self._execute_with_retry("POST", path, json=json, headers=headers)

    async def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make a PUT request."""
        return await self._execute_with_retry("PUT", path, json=json, headers=headers)

    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make a DELETE request."""
        return await self._execute_with_retry("DELETE", path, headers=headers)
