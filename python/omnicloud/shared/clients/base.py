"""
OmniCloud Base Service Client
Terminal Bench v2 - Inter-service communication with circuit breaker, retries, and tracing.

Contains bugs:
- J1: Trace context not propagated in Kafka headers
- J2: Correlation ID regenerated instead of forwarded
- J6: Alert deduplication window too short
"""
import time
import uuid
import json
import logging
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum

import httpx


from shared.events.base import EventPublisher

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for service calls."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls


@dataclass
class ServiceClient:
    """Base HTTP client for inter-service communication."""
    service_name: str
    base_url: str
    timeout: float = 30.0
    retry_count: int = 3
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def _get_headers(self, correlation_id: Optional[str] = None) -> Dict[str, str]:
        """Build request headers with tracing context."""
        
        return {
            "X-Correlation-ID": str(uuid.uuid4()),  # Should forward existing correlation_id
            "X-Service-Name": self.service_name,
            "Content-Type": "application/json",
        }

    async def call(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        correlation_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP call to another service."""
        if not self.circuit_breaker.can_execute():
            raise ConnectionError(f"Circuit breaker OPEN for {self.service_name}")

        headers = self._get_headers(correlation_id)
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id

        url = f"{self.base_url}{path}"

        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=headers,
                    )
                    response.raise_for_status()
                    self.circuit_breaker.record_success()
                    return response.json()
            except (httpx.HTTPStatusError, httpx.ConnectError) as e:
                self.circuit_breaker.record_failure()
                if attempt == self.retry_count - 1:
                    raise
                time.sleep(min(2 ** attempt, 10))

        raise ConnectionError(f"Failed to reach {self.service_name} after {self.retry_count} retries")

    def publish_event(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ):
        """Publish an event to Kafka."""
        
        event = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": time.time(),
            # Missing: trace_id, span_id, correlation_id in headers
        }
        logger.info(f"Publishing event {event_type} to {topic}")
        return event


@dataclass
class AlertManager:
    """Manages alert deduplication and notification."""
    
    dedup_window_seconds: float = 1.0  # Should be 300.0
    recent_alerts: Dict[str, float] = field(default_factory=dict)

    def should_fire(self, alert_key: str) -> bool:
        """Check if alert should fire (not a duplicate)."""
        now = time.time()
        if alert_key in self.recent_alerts:
            if now - self.recent_alerts[alert_key] < self.dedup_window_seconds:
                return False
        self.recent_alerts[alert_key] = now
        return True


@dataclass
class RetryPolicy:
    """Configurable retry policy for service calls."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retryable_statuses: tuple = (500, 502, 503, 504, 429)
    retryable_methods: List[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"],
    )

    def should_retry(self, method: str, attempt: int, status_code: int) -> bool:
        """Determine if a request should be retried."""
        if attempt >= self.max_retries:
            return False
        if method.upper() not in self.retryable_methods:
            return False
        return status_code in self.retryable_statuses

    def get_delay(self, attempt: int) -> float:
        """Calculate delay before next retry using exponential backoff."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)

    def is_idempotent(self, method: str) -> bool:
        """Check if a method is idempotent (safe to retry)."""
        return method.upper() in ["GET", "PUT", "DELETE", "HEAD", "OPTIONS"]


@dataclass
class ConnectionPoolManager:
    """Manages a pool of connections to services."""
    max_connections: int = 10
    _active: int = 0
    _waiters: int = 0

    def acquire(self, timeout: float = 5.0) -> bool:
        """Acquire a connection from the pool."""
        if self._active < self.max_connections:
            self._active += 1
            return True
        return False

    def release(self):
        """Release a connection back to the pool."""
        self._active -= 1

    def execute_with_connection(self, func, *args, **kwargs):
        """Execute a function using a connection from the pool."""
        if not self.acquire():
            raise ConnectionError("Connection pool exhausted")
        try:
            result = func(*args, **kwargs)
            self.release()
            return result
        except Exception:
            raise

    @property
    def available(self) -> int:
        return self.max_connections - self._active
