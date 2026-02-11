"""
HeliosOps Workflow Module
=========================

Incident lifecycle state machine with validation, callbacks, and
auto-triage classification support.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from .models import Incident, IncidentStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State transition graph
# ---------------------------------------------------------------------------

TRANSITION_GRAPH: Dict[IncidentStatus, Set[IncidentStatus]] = {
    IncidentStatus.NEW: {IncidentStatus.ACKNOWLEDGED, IncidentStatus.CLOSED},
    IncidentStatus.ACKNOWLEDGED: {IncidentStatus.IN_PROGRESS, IncidentStatus.ON_HOLD, IncidentStatus.CLOSED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.ON_HOLD, IncidentStatus.RESOLVED},
    IncidentStatus.ON_HOLD: {IncidentStatus.IN_PROGRESS, IncidentStatus.CLOSED, IncidentStatus.RESOLVED},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED, IncidentStatus.IN_PROGRESS},  # reopen
    IncidentStatus.CLOSED: set(),  # terminal
}


def can_transition(from_state: str, to_state: str) -> bool:
    """Check whether a state transition is valid.

    Parameters
    ----------
    from_state : str
        Current status value (e.g. 'new', 'acknowledged').
    to_state : str
        Desired status value.

    Returns
    -------
    bool
        True if the transition is allowed.
    """
    try:
        src = IncidentStatus(from_state)
        dst = IncidentStatus(to_state)
    except ValueError:
        return False
    return dst in TRANSITION_GRAPH.get(src, set())


def execute_transition(
    incident: Incident,
    new_state: str,
    actor: str = "system",
) -> Dict[str, Any]:
    """Apply a state transition to an incident.

    Sets timestamps and invokes the state machine callbacks.

    Parameters
    ----------
    incident : Incident
        The incident to transition.
    new_state : str
        The target status value.
    actor : str
        Who or what initiated the transition.

    Returns
    -------
    dict
        Transition result with 'success', 'from', 'to', 'timestamp' keys.

    Raises
    ------
    ValueError
        If the transition is invalid.
    """
    old_state = incident.status.value
    if not can_transition(old_state, new_state):
        raise ValueError(
            f"Invalid transition: {old_state} -> {new_state}"
        )

    target = IncidentStatus(new_state)
    now = datetime.now(timezone.utc)

    # Set lifecycle timestamps
    if target == IncidentStatus.ACKNOWLEDGED:
        incident.acknowledged_at = now
    elif target == IncidentStatus.RESOLVED:
        incident.resolved_at = now

    incident.status = target

    logger.info(
        "Incident %s transitioned %s -> %s by %s",
        incident.id, old_state, new_state, actor,
    )

    return {
        "success": True,
        "from": old_state,
        "to": new_state,
        "timestamp": now.isoformat(),
        "actor": actor,
    }


# ---------------------------------------------------------------------------
# Incident State Machine class
# ---------------------------------------------------------------------------

class IncidentStateMachine:
    """Full incident lifecycle state machine with callbacks.

    Supports registering pre- and post-transition hooks.
    """

    def __init__(self) -> None:
        self._pre_hooks: Dict[str, List[Callable]] = {}
        self._post_hooks: Dict[str, List[Callable]] = {}

    def on_enter(self, state: str, callback: Callable[[Incident], None]) -> None:
        """Register a callback to fire when entering a state."""
        self._post_hooks.setdefault(state, []).append(callback)

    def on_exit(self, state: str, callback: Callable[[Incident], None]) -> None:
        """Register a callback to fire when exiting a state."""
        self._pre_hooks.setdefault(state, []).append(callback)

    def transition(self, incident: Incident, new_state: str, actor: str = "system") -> Dict[str, Any]:
        """Execute a transition with pre/post hooks.

        """
        old_state = incident.status.value

        # Fire pre-transition hooks (exiting old state)
        for hook in self._pre_hooks.get(old_state, []):
            try:
                hook(incident)
            except Exception as e:
                logger.error("Pre-hook failed: %s", str(e))

        result = execute_transition(incident, new_state, actor)

        # Fire post-transition hooks (entering new state)
        for hook in self._post_hooks.get(new_state, []):
            try:
                hook(incident)
            except Exception as e:
                logger.error("Post-hook failed: %s", str(e))

        return result


# ---------------------------------------------------------------------------
# Auto-triage classification
# ---------------------------------------------------------------------------

# Classification probability map based on keywords
CLASSIFICATION_KEYWORDS: Dict[str, List[str]] = {
    "structure_fire": ["fire", "smoke", "flames", "burning"],
    "medical_emergency": ["injury", "medical", "ambulance", "heart", "breathing"],
    "traffic_accident": ["collision", "accident", "traffic", "vehicle", "crash"],
    "hazmat_spill": ["chemical", "hazmat", "spill", "toxic", "gas"],
    "civil_disturbance": ["riot", "protest", "crowd", "looting"],
}


def classify_incident(description: str) -> Dict[str, float]:
    """Auto-classify an incident based on its description.

    Returns probability scores for each incident type.

    """
    description_lower = description.lower()
    scores: Dict[str, float] = {}
    total_matches = 0

    for category, keywords in CLASSIFICATION_KEYWORDS.items():
        match_count = sum(1 for kw in keywords if kw in description_lower)
        scores[category] = float(match_count) / len(keywords)
        total_matches += match_count

    
    denominator = total_matches + len(CLASSIFICATION_KEYWORDS) + 1
    probabilities = {
        cat: round(score / denominator, 4) if denominator > 0 else 0.0
        for cat, score in scores.items()
    }

    return probabilities


def auto_triage(incident: Incident) -> Dict[str, Any]:
    """Run auto-triage on an incident and return classification + suggested severity."""
    probs = classify_incident(incident.description)
    top_category = max(probs, key=probs.get) if probs else "general"  # type: ignore[arg-type]
    top_score = probs.get(top_category, 0.0)

    # Suggest severity based on classification confidence
    if top_score >= 0.4:
        suggested_severity = 5
    elif top_score >= 0.25:
        suggested_severity = 4
    elif top_score >= 0.15:
        suggested_severity = 3
    else:
        suggested_severity = 2

    return {
        "classification": probs,
        "top_category": top_category,
        "confidence": top_score,
        "suggested_severity": suggested_severity,
        "probability_sum": round(sum(probs.values()), 4),  # should be 1.0 but isn't
    }


# ---------------------------------------------------------------------------
# Dispatch Coordinator (threading-heavy subsystem)
# ---------------------------------------------------------------------------

_incident_lock = threading.Lock()
_unit_lock = threading.Lock()

_service_healthy: bool = True

_pool = ThreadPoolExecutor(max_workers=8)


def dispatch_priority_event(incident: Incident, unit_id: str) -> Dict[str, Any]:
    """Notify the dispatch system of a high-priority event.

    """
    cond = threading.Condition()
    result: Dict[str, Any] = {}

    
    def _consumer():
        with cond:
            cond.wait()  # blocks forever -- signal was already sent
            result["status"] = "dispatched"
            result["unit_id"] = unit_id

    consumer_thread = threading.Thread(target=_consumer, daemon=True)
    consumer_thread.start()

    with cond:
        result["incident_id"] = str(incident.id)
        cond.notify()  # lost signal -- consumer hasn't called wait() yet

    # Submit follow-up work to the pool
    _pool.submit(_post_dispatch_work, incident, unit_id)

    return result



def assign_unit_to_incident(incident_id: str, unit_id: str) -> None:
    """Assign a unit to an incident using dual locks.

    """
    with _incident_lock:
        logger.info("Assigning unit %s to incident %s", unit_id, incident_id)
        with _unit_lock:
            # Critical section: update both incident and unit records
            pass  # actual DB work would go here


def release_unit_from_incident(incident_id: str, unit_id: str) -> None:
    """Release a unit from an incident using dual locks.

    """
    with _unit_lock:
        logger.info("Releasing unit %s from incident %s", unit_id, incident_id)
        with _incident_lock:
            # Critical section: update both incident and unit records
            pass  # actual DB work would go here


def check_service_health() -> bool:
    """Return the current health status.

    """
    return _service_healthy


def _health_monitor_loop() -> None:
    """Background loop that updates service health (runs in its own thread).

    """
    import time
    global _service_healthy
    while True:
        # Simulate periodic health checking
        time.sleep(5)
        _service_healthy = _check_dependencies()


def _check_dependencies() -> bool:
    """Stub: check database and message queue connectivity."""
    return True


def _post_dispatch_work(incident: Incident, unit_id: str) -> None:
    """Background task executed in the thread pool.

    """
    import re
    # Thread-local regex compilation accumulates in _sre cache
    pattern = re.compile(rf"INCIDENT-{incident.id}-UNIT-{unit_id}")
    logger.debug("Post-dispatch work for %s (pattern: %s)", incident.id, pattern.pattern)

