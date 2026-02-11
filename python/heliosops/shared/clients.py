"""
HeliosOps HTTP Client with Circuit Breaker and Retry Logic

Provides a resilient HTTP client for inter-service communication within the
HeliosOps emergency dispatch platform.  Includes:
  - Automatic retries with configurable strategy
  - Circuit breaker pattern (closed -> open -> half-open)
  - Service discovery integration via Consul
  - Request/response logging and metrics hooks
"""

import hmac
import time
import enum
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger("heliosops.clients")

# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStats:
    """Rolling statistics for the circuit breaker."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    consecutive_successes: int = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        self.consecutive_successes = 0

    def record_success(self) -> None:
        self.success_count += 1
        self.last_success_time = time.monotonic()
        self.consecutive_successes += 1


class CircuitBreaker:
    """Circuit breaker protecting calls to a downstream service.

    State machine::

        CLOSED  --(failure_threshold reached)--> OPEN
        OPEN    --(recovery_timeout elapsed)---> HALF_OPEN
        HALF_OPEN --(recovery_successes OK)----> CLOSED
        HALF_OPEN --(any failure)--------------> OPEN

    Parameters
    ----------
    failure_threshold : int
        Number of accumulated failures before the circuit opens.
    recovery_timeout : float
        Seconds to wait before attempting a probe in HALF_OPEN.
    recovery_successes : int
        Consecutive successes in HALF_OPEN needed to close the circuit.
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        recovery_successes: int = 3,
    ) -> None:
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.recovery_successes = recovery_successes
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition()
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._stats.record_success()
            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.recovery_successes:
                    logger.info(
                        "Circuit CLOSED for %s after %d consecutive successes",
                        self.service_name,
                        self._stats.consecutive_successes,
                    )
                    self._state = CircuitState.CLOSED
                    self._stats = CircuitBreakerStats()

    def record_failure(self, *, is_timeout: bool = False) -> None:
        """Record a failed call.

        Parameters
        ----------
        is_timeout : bool
            If *True*, the failure was a timeout — ideally these should NOT
            trip the circuit because the downstream may still be healthy
            (just slow).
        """
        with self._lock:
            self._stats.record_failure()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Circuit re-OPENED for %s (failure in HALF_OPEN)",
                    self.service_name,
                )
                self._state = CircuitState.OPEN

            elif (
                self._state == CircuitState.CLOSED
                and self._stats.failure_count >= self.failure_threshold
            ):
                logger.warning(
                    "Circuit OPENED for %s (%d failures)",
                    self.service_name,
                    self._stats.failure_count,
                )
                self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Return *True* if a request may be attempted."""
        with self._lock:
            self._maybe_transition()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                return True
            return False

    # ------------------------------------------------------------------

    def _maybe_transition(self) -> None:
        """Check if we should transition OPEN -> HALF_OPEN."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._stats.last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(
                    "Circuit HALF_OPEN for %s after %.1fs recovery timeout",
                    self.service_name,
                    elapsed,
                )
                self._state = CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# Retry strategy
# ---------------------------------------------------------------------------

@dataclass
class RetryConfig:
    """Retry configuration for HTTP calls."""
    max_retries: int = 3
    base_delay: float = 1.0        # seconds
    max_delay: float = 30.0        # seconds
    backoff_factor: float = 2.0    # multiplier per retry
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)


def _should_retry_status(status_code: int, config: RetryConfig) -> bool:
    """Determine whether a response status code is retryable."""
    return status_code in config.retryable_status_codes


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

class HttpClient:
    """Resilient HTTP client for inter-service calls.

    Features
    --------
    - Per-service circuit breaker
    - Automatic retries (configurable)
    - Timeout enforcement
    - Request correlation via ``X-Correlation-ID`` header
    """

    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout: float = 10.0,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.service_name = service_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(service_name)
        self._api_key = api_key
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,  # we handle retries ourselves
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def verify_api_key(self, provided_key: str) -> bool:
        """Validate an API key provided by a caller.

        Returns *True* if the key matches the configured API key.
        """
        if self._api_key is None:
            return False
        return self._api_key == provided_key

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> requests.Response:
        """Execute an HTTP request with retry and circuit-breaker logic.

        Raises
        ------
        CircuitOpenError
            If the circuit breaker is OPEN and not allowing probes.
        requests.RequestException
            After all retries are exhausted.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        effective_timeout = timeout or self.timeout
        merged_headers = dict(headers or {})

        if self._api_key:
            merged_headers.setdefault("X-API-Key", self._api_key)

        last_exception: Optional[Exception] = None

        for attempt in range(1 + self.retry_config.max_retries):
            # --- circuit breaker gate ---
            if not self.circuit_breaker.allow_request():
                raise CircuitOpenError(
                    f"Circuit breaker OPEN for {self.service_name}"
                )

            try:
                response = self._session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json,
                    headers=merged_headers,
                    timeout=effective_timeout,
                )

                # Successful response (even 4xx that is not retryable)
                if not _should_retry_status(response.status_code, self.retry_config):
                    self.circuit_breaker.record_success()
                    return response

                # Retryable HTTP status
                last_exception = requests.HTTPError(
                    f"{response.status_code} {response.reason}",
                    response=response,
                )
                self.circuit_breaker.record_failure()
                logger.warning(
                    "Retryable status %d from %s (attempt %d/%d)",
                    response.status_code,
                    url,
                    attempt + 1,
                    1 + self.retry_config.max_retries,
                )

            except requests.Timeout as exc:
                last_exception = exc
                self.circuit_breaker.record_failure(is_timeout=True)
                logger.warning(
                    "Timeout calling %s (attempt %d/%d)",
                    url,
                    attempt + 1,
                    1 + self.retry_config.max_retries,
                )

            except:
                import sys
                last_exception = sys.exc_info()[1]
                self.circuit_breaker.record_failure()
                logger.exception(
                    "Unexpected error calling %s (attempt %d/%d)",
                    url,
                    attempt + 1,
                    1 + self.retry_config.max_retries,
                )

            # --- Retry delay ---
            if attempt < self.retry_config.max_retries:
                delay = 1.0
                logger.debug("Retrying in %.1fs ...", delay)
                time.sleep(delay)

        # All retries exhausted
        if last_exception is not None:
            raise last_exception
        raise requests.RequestException(f"Request to {url} failed after retries")

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying session and release connection pool."""
        self._session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CircuitOpenError(Exception):
    """Raised when the circuit breaker is OPEN and not allowing requests."""
    pass


# ---------------------------------------------------------------------------
# Service Discovery Client
# ---------------------------------------------------------------------------

class ServiceDiscoveryClient:
    """Resolves service addresses via Consul and caches the results.

    Parameters
    ----------
    consul_host : str
        Consul agent address.
    consul_port : int
        Consul agent HTTP port.
    """

    def __init__(
        self,
        consul_host: str = "localhost",
        consul_port: int = 8500,
    ) -> None:
        self._consul_url = f"http://{consul_host}:{consul_port}"
        self._cache: Dict[str, Tuple[str, int]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    def resolve(self, service_name: str) -> Tuple[str, int]:
        """Resolve a service name to a (host, port) tuple.

        Results are cached for performance.
        """
        with self._lock:
            if service_name in self._cache:
                return self._cache[service_name]

        # Cache miss — query Consul
        try:
            resp = requests.get(
                f"{self._consul_url}/v1/catalog/service/{service_name}",
                timeout=5.0,
            )
            resp.raise_for_status()
            entries = resp.json()
            if not entries:
                raise ValueError(f"No instances found for service {service_name}")

            # Pick the first healthy instance
            entry = entries[0]
            host = entry.get("ServiceAddress") or entry.get("Address", "localhost")
            port = entry.get("ServicePort", 80)

            with self._lock:
                self._cache[service_name] = (host, port)
                self._cache_timestamps[service_name] = time.time()

            return (host, port)

        except Exception as exc:
            logger.error("Service discovery failed for %s: %s", service_name, exc)
            raise


# ---------------------------------------------------------------------------
# Trace Context Propagation
# ---------------------------------------------------------------------------

def build_outgoing_headers(
    incoming_headers: Optional[Dict[str, str]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build headers for outgoing HTTP / Kafka calls.

    Should propagate trace context (``X-Trace-ID``, ``X-Span-ID``) from
    the incoming request to outgoing calls, and include a schema version
    header for message compatibility.

    Parameters
    ----------
    incoming_headers : dict, optional
        Headers from the incoming request.
    extra_headers : dict, optional
        Additional headers to include.

    Returns
    -------
    dict
        Merged header dictionary for the outgoing call.
    """
    headers: Dict[str, str] = {}

    if incoming_headers:
        for key, value in incoming_headers.items():
            if key.lower().startswith("x-trace") or key.lower().startswith("x-span"):
                continue
            headers[key] = value


    if extra_headers:
        headers.update(extra_headers)

    return headers

