from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
TRANSITIONS = {
    "queued": {"allocated", "cancelled"},
    "allocated": {"departed", "cancelled"},
    "departed": {"arrived", "cancelled"},
    "arrived": set(),
    "cancelled": set(),
}

TERMINAL_STATES: Set[str] = {"arrived", "cancelled"}


# ---------------------------------------------------------------------------
# Core transition check (preserved signature)
# ---------------------------------------------------------------------------

def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in TRANSITIONS.get(from_state, set())


# ---------------------------------------------------------------------------
# State introspection
# ---------------------------------------------------------------------------

def is_terminal_state(state: str) -> bool:
    return state in TERMINAL_STATES


def is_valid_state(state: str) -> bool:
    return state in TRANSITIONS


def allowed_transitions(state: str) -> Set[str]:
    return set(TRANSITIONS.get(state, set()))


# ---------------------------------------------------------------------------
# Shortest path via BFS
# ---------------------------------------------------------------------------

def validate_state_path(states: List[str]) -> List[str]:
    errors: List[str] = []
    if not states:
        return ["empty path"]
    for s in states:
        if s not in TRANSITIONS:
            errors.append(f"unknown state: {s}")
            return errors
    for i in range(len(states) - 1):
        if not can_transition(states[i], states[i + 1]):
            errors.append(f"invalid transition: {states[i]} -> {states[i+1]}")
    return errors


def shortest_path(from_state: str, to_state: str) -> List[str]:
    if from_state == to_state:
        return [from_state]
    if from_state not in TRANSITIONS or to_state not in TRANSITIONS:
        return []
    visited: Set[str] = {from_state}
    queue: deque = deque([(from_state, [from_state])])
    while queue:
        current, path = queue.popleft()
        for neighbour in TRANSITIONS.get(current, set()):
            if neighbour in visited:
                continue
            new_path = path + [neighbour]
            if neighbour == to_state:
                return new_path
            visited.add(neighbour)
            queue.append((neighbour, new_path))
    return []


# ---------------------------------------------------------------------------
# Transition records
# ---------------------------------------------------------------------------

@dataclass
class TransitionRecord:
    entity_id: str
    from_state: str
    to_state: str
    timestamp: float = 0.0
    reason: str = ""


@dataclass
class TransitionResult:
    success: bool
    entity_id: str
    from_state: str
    to_state: str
    error: str = ""


# ---------------------------------------------------------------------------
# WorkflowEngine — thread-safe entity lifecycle manager
# ---------------------------------------------------------------------------

class WorkflowEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entities: Dict[str, str] = {}
        self._history: List[TransitionRecord] = []

    def register(self, entity_id: str, initial_state: str = "queued") -> bool:
        with self._lock:
            if entity_id in self._entities:
                return False
            if initial_state not in TRANSITIONS:
                return False
            self._entities[entity_id] = initial_state
            return True

    def get_state(self, entity_id: str) -> Optional[str]:
        with self._lock:
            return self._entities.get(entity_id)

    def transition(self, entity_id: str, to_state: str, reason: str = "") -> TransitionResult:
        with self._lock:
            current = self._entities.get(entity_id)
            if current is None:
                return TransitionResult(False, entity_id, "", to_state, "entity not found")
            if not can_transition(current, to_state):
                return TransitionResult(False, entity_id, current, to_state, f"invalid transition {current} -> {to_state}")
            self._entities[entity_id] = to_state
            self._history.append(TransitionRecord(entity_id, current, to_state, time.monotonic(), reason))
            return TransitionResult(True, entity_id, current, to_state)

    def is_terminal(self, entity_id: str) -> bool:
        with self._lock:
            state = self._entities.get(entity_id)
            return state is not None and state in TERMINAL_STATES

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._entities.values() if s not in TERMINAL_STATES)

    def history(self, entity_id: Optional[str] = None) -> List[TransitionRecord]:
        with self._lock:
            if entity_id:
                return [r for r in self._history if r.entity_id == entity_id]
            return list(self._history)

    def rollback(self, entity_id: str) -> TransitionResult:
        with self._lock:
            current = self._entities.get(entity_id)
            if current is None:
                return TransitionResult(False, entity_id, "", "", "entity not found")
            entity_history = [r for r in self._history if r.entity_id == entity_id]
            if not entity_history:
                return TransitionResult(False, entity_id, current, current, "no history")
            prev_state = entity_history[-1].from_state
            self._entities[entity_id] = prev_state
            self._history.append(TransitionRecord(entity_id, current, prev_state, time.monotonic(), "rollback"))
            return TransitionResult(True, entity_id, current, prev_state)

    def clone_entity(self, src_id: str, new_id: str) -> bool:
        with self._lock:
            src_state = self._entities.get(src_id)
            if new_id in self._entities:
                return False
            self._entities[new_id] = src_state
            return True

    def audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "entity": r.entity_id,
                    "from": r.from_state,
                    "to": r.to_state,
                    "reason": r.reason,
                    "ts": r.timestamp,
                }
                for r in self._history
            ]
