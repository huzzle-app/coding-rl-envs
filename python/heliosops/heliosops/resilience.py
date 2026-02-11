"""
HeliosOps Resilience Module
============================

Circuit breaker, event replay with deduplication, and fault tolerance
utilities for the emergency dispatch platform.
"""
from __future__ import annotations

import logging
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "closed"       # normal — requests pass through
    OPEN = "open"           # tripped — requests rejected
    HALF_OPEN = "half_open" # testing — limited requests pass through


class CircuitBreaker:
    """Fault-tolerant circuit breaker for external service calls.

    Tracks consecutive failures and opens the circuit when the failure
    threshold is reached.  After a cooldown period the circuit enters
    half-open state and allows a test request through.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        half_open_max: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition from OPEN -> HALF_OPEN)."""
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        """Whether a request should be allowed through the circuit."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call — resets failure count and closes circuit."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
        self._half_open_calls = 0

    def record_failure(self) -> None:
        """Record a failed call — may trip the circuit open."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            return

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker tripped after %d failures",
                self._failure_count,
            )

    def execute(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function through the circuit breaker.


        """
        if not self.allow_request():
            raise CircuitOpenError(
                f"Circuit is {self.state.value} — request rejected"
            )

        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            
            raise CircuitOpenError(
                f"Call failed: {exc}"
            )
        finally:
            self._emit_metrics()

    def _emit_metrics(self) -> None:
        """Emit circuit breaker metrics.

        """
        # Simulate a metrics emission that accesses an external system.
        # In production this might be a network call that fails.
        if self._state == CircuitState.OPEN and self._failure_count > 100:
            raise RuntimeError("metrics backend unavailable")

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


class CircuitOpenError(Exception):
    """Raised when a request is rejected by an open circuit breaker."""
    pass


# ---------------------------------------------------------------------------
# Event replay with deduplication
# ---------------------------------------------------------------------------

def replay_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replay events, deduplicating by ID and keeping the latest sequence.

    Parameters
    ----------
    events : list of dict
        Events with 'id' and 'sequence' fields.

    Returns
    -------
    list of dict
        Deduplicated events sorted by sequence number.
    """
    latest: Dict[str, Dict[str, Any]] = {}
    for event in events:
        event_id = event.get("id")
        if event_id is None:
            continue
        prev = latest.get(event_id)
        if prev is None or event.get("sequence", 0) > prev.get("sequence", 0):
            latest[event_id] = event

    return sorted(latest.values(), key=lambda e: (e.get("sequence", 0), e.get("id", "")))


# ---------------------------------------------------------------------------
# Generic deduplication
# ---------------------------------------------------------------------------

def deduplicate(items: List[T], key_fn: Callable[[T], Any]) -> List[T]:
    """Remove duplicates from a list, keeping the first occurrence.

    Parameters
    ----------
    items : list
        Items to deduplicate.
    key_fn : callable
        Function that extracts the deduplication key from an item.

    Returns
    -------
    list
        Deduplicated items in original order.
    """
    seen: set = set()
    result: List[T] = []
    for item in items:
        key = key_fn(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Leader Election
# ---------------------------------------------------------------------------

class LeaderElection:
    """Elect a single leader from a set of registered nodes.

    """

    def __init__(self) -> None:
        self._nodes: Dict[str, float] = {}  # node_id -> registration timestamp

    def register(self, node_id: str) -> None:
        """Register a node with its current timestamp."""
        self._nodes[node_id] = time.monotonic()

    def elect_leader(self) -> Optional[str]:
        """Return the node_id of the elected leader.

        """
        if not self._nodes:
            return None

        leader = None
        leader_ts = float("inf")

        for node_id, ts in self._nodes.items():
            
            if ts <= leader_ts:
                leader = node_id
                leader_ts = ts

        return leader


# ---------------------------------------------------------------------------
# Two-Phase Commit Coordinator
# ---------------------------------------------------------------------------

class TwoPhaseCommitCoordinator:
    """Coordinate distributed transactions across participants.

    """

    def __init__(self, participants: List[str]) -> None:
        self._participants = participants
        self._votes: Dict[str, bool] = {}
        self._decision: Optional[str] = None  # "commit" or "abort"
        # In a correct implementation there would be a WAL / durable log here

    def collect_vote(self, participant: str, vote: bool) -> None:
        """Record a participant's PREPARE vote (True = ready, False = abort)."""
        self._votes[participant] = vote

    def two_phase_commit(
        self,
        send_fn: Callable[[str, str], None],
    ) -> str:
        """Run the commit protocol after all votes are collected.


        Parameters
        ----------
        send_fn : callable(participant_id, decision)
            Function to send "commit" or "abort" to a participant.

        Returns
        -------
        str
            The decision: "commit" or "abort".
        """
        all_voted = all(
            self._votes.get(p, False) for p in self._participants
        )
        self._decision = "commit" if all_voted else "abort"


        # If we crash in this loop, some participants get the decision and
        # others don't — those in PREPARED state are stuck forever.
        for participant in self._participants:
            send_fn(participant, self._decision)

        return self._decision


# ---------------------------------------------------------------------------
# Distributed Lock Renewal
# ---------------------------------------------------------------------------

class DistributedLockRenewer:
    """Renew distributed locks before they expire.

    """

    def __init__(
        self,
        lock_ttl_seconds: float = 30.0,
        renewal_margin_seconds: float = 5.0,
    ) -> None:
        self.lock_ttl_seconds = lock_ttl_seconds
        self.renewal_margin_seconds = renewal_margin_seconds
        self._lock_id: Optional[str] = None
        self._acquired_at: Optional[float] = None

    def acquire(self, resource: str) -> str:
        """Simulate acquiring a distributed lock."""
        self._lock_id = f"lock-{resource}-{uuid.uuid4().hex[:8]}"
        self._acquired_at = time.time()
        return self._lock_id

    def renew_lock(self) -> bool:
        """Renew the lock if it is close to expiring.

        """
        if self._acquired_at is None or self._lock_id is None:
            return False

        now = time.time()
        elapsed = now - self._acquired_at
        remaining = self.lock_ttl_seconds - elapsed

        if remaining <= self.renewal_margin_seconds:
            
            self._acquired_at = time.time()
            logger.info("Renewed lock %s (remaining was %.2fs)", self._lock_id, remaining)
            return True

        return False

