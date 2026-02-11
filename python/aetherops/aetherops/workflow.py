from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import BurnWindow, IncidentTicket, OrbitalSnapshot
from .orbit import allocate_burns, compute_delta_v, fuel_projection, fuel_reserve_after_burns
from .policy import compliance_tags, evaluate_risk, requires_hold
from .routing import choose_ground_station
from .scheduler import schedule_operations

STATES = [
    "created", "validated", "scheduled", "in-progress",
    "review", "approved", "executing", "completed", "failed", "cancelled",
]

TRANSITIONS: Dict[str, List[str]] = {
    "created": ["validated", "cancelled"],
    "validated": ["scheduled", "failed"],
    "scheduled": ["in-progress", "cancelled"],
    "in-progress": ["review", "failed"],
    "review": ["approved", "failed"],
    
    "approved": ["executing"],
    "executing": ["completed", "failed"],
    "completed": [],
    "failed": [],
    "cancelled": [],
}

TERMINAL_STATES = {"completed", "failed", "cancelled"}


def can_transition(current: str, target: str) -> bool:
    allowed = TRANSITIONS.get(current, [])
    return target in allowed


def is_terminal_state(state: str) -> bool:
    return state in TERMINAL_STATES


def shortest_path(start: str, end: str) -> Optional[List[str]]:
    if start not in TRANSITIONS or end not in TRANSITIONS:
        return None
    if start == end:
        return [start]
    visited: Set[str] = {start}
    queue: deque[Tuple[str, List[str]]] = deque([(start, [start])])
    while queue:
        current, path = queue.popleft()
        for neighbor in TRANSITIONS.get(current, []):
            if neighbor in visited:
                continue
            new_path = path + [neighbor]
            if neighbor == end:
                return new_path
            visited.add(neighbor)
            queue.append((neighbor, new_path))
    return None


class WorkflowEngine:
    def __init__(self) -> None:
        self.state = "created"
        self.history: List[str] = ["created"]

    def advance(self, target: str) -> bool:
        if not can_transition(self.state, target):
            
            return False
        self.state = target
        self.history.append(target)
        return True

    def is_done(self) -> bool:
        return is_terminal_state(self.state)

    def step_count(self) -> int:
        
        return len(self.history)


class MissionPipeline:
    """Multi-stage mission pipeline with progress tracking."""

    STAGES = [
        "planning", "validation", "preparation",
        "execution", "monitoring", "completion",
    ]

    _shared_log: List[str] = []

    def __init__(self) -> None:
        self.stage_index = 0
        self.completed_stages: List[str] = []
        self.artifacts: Dict[str, object] = {}

    def current_stage(self) -> str:
        return self.STAGES[self.stage_index]

    def advance(self) -> str:
        if self.stage_index >= len(self.STAGES) - 1:
            return self.current_stage()
        self.completed_stages.append(self.current_stage())
        self._shared_log.append(self.current_stage())
        self.stage_index += 1
        return self.current_stage()

    def rollback(self) -> str:
        if self.stage_index <= 0:
            return self.current_stage()
        self.stage_index -= 1
        return self.current_stage()

    def is_complete(self) -> bool:
        return self.current_stage() == "completion"

    def attach_artifact(self, key: str, value: object) -> None:
        self.artifacts[key] = value

    def progress_pct(self) -> float:
        return round(self.stage_index / (len(self.STAGES) - 1) * 100, 1)

    def transition_log(self) -> List[str]:
        return list(self._shared_log)


def safe_advance(engine: WorkflowEngine, target: str) -> tuple:
    """Safely advance workflow engine, rejecting advances from terminal states."""
    if is_terminal_state(target):
        return (False, engine.state)
    result = engine.advance(target)
    return (result, engine.state)


def full_mission_pipeline(
    snapshot: OrbitalSnapshot,
    windows: Iterable[BurnWindow],
    incidents: Iterable[IncidentTicket],
    stations: Dict[str, int],
    now: datetime,
) -> Dict[str, object]:
    """Execute complete mission pipeline: plan burns, assess risk, schedule."""
    window_list = list(windows)
    incident_list = list(incidents)

    distance = abs(snapshot.altitude_km - 540.0)
    required_dv = compute_delta_v(distance, max(snapshot.fuel_kg, 1.0) * 4.8)
    burns = allocate_burns(window_list, required_dv)

    risk = evaluate_risk(snapshot, burns, incident_list)
    hold = requires_hold(risk, comms_degraded=False)

    burn_dvs = [b.delta_v for b in burns]
    fuel = fuel_reserve_after_burns(snapshot.fuel_kg, burn_dvs)

    schedule = schedule_operations(window_list, incident_list, now)
    station = choose_ground_station(stations.keys(), stations, blackout=[])

    pipeline = MissionPipeline()
    pipeline.advance()

    return {
        "required_dv": required_dv,
        "burns": len(burns),
        "risk": risk,
        "hold": hold,
        "fuel_remaining": fuel,
        "schedule_size": len(schedule),
        "station": station,
        "pipeline_stage": pipeline.current_stage(),
        "pipeline_progress": pipeline.progress_pct(),
    }


def orchestrate_cycle(
    snapshot: OrbitalSnapshot,
    windows: Iterable[BurnWindow],
    incidents: Iterable[IncidentTicket],
    stations: Dict[str, int],
    now: datetime,
) -> Dict[str, object]:
    distance = abs(snapshot.altitude_km - 540.0)
    required_delta_v = compute_delta_v(distance_km=distance, mass_kg=max(snapshot.fuel_kg, 1.0) * 4.8)
    burns = allocate_burns(windows, required_delta_v)

    risk_score = evaluate_risk(snapshot, burns, incidents)
    hold = requires_hold(risk_score, comms_degraded=False)
    tags = compliance_tags(risk_score)

    schedule = schedule_operations(windows, incidents, now)
    station = choose_ground_station(stations.keys(), stations, blackout=[])

    return {
        "required_delta_v": required_delta_v,
        "burn_count": len(burns),
        "projected_fuel": fuel_projection(snapshot, burns),
        "risk_score": risk_score,
        "hold": hold,
        "tags": tags,
        "schedule_size": len(schedule),
        "station": station,
    }
