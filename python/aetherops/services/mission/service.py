from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

SERVICE_NAME = "mission"
SERVICE_ROLE = "mission state registry"

VALID_PHASES = ["planning", "fueling", "launch", "orbit", "deorbit", "complete", "aborted"]

PHASE_TRANSITIONS: Dict[str, List[str]] = {
    "planning": ["fueling", "aborted"],
    "fueling": ["launch", "aborted"],
    "launch": ["orbit", "aborted"],
    
    "orbit": ["deorbit"],
    "deorbit": ["complete", "aborted"],
    "complete": [],
    "aborted": [],
}


@dataclass
class MissionState:
    mission_id: str
    phase: str = "planning"
    fuel_loaded_kg: float = 0.0
    satellites: List[str] = field(default_factory=list)


class MissionRegistry:
    def __init__(self) -> None:
        self._missions: Dict[str, MissionState] = {}

    def register(self, mission_id: str) -> MissionState:
        state = MissionState(mission_id=mission_id)
        self._missions[mission_id] = state
        return state

    def get(self, mission_id: str) -> Optional[MissionState]:
        return self._missions.get(mission_id)

    def all_ids(self) -> List[str]:
        return sorted(self._missions.keys())

    def count(self) -> int:
        return len(self._missions)


def validate_phase_transition(current: str, target: str) -> bool:
    allowed = PHASE_TRANSITIONS.get(current, [])
    return target in allowed


def compute_mission_health(state: MissionState) -> float:
    score = 100.0
    if state.phase == "aborted":
        return 0.0
    if state.fuel_loaded_kg < 50:
        score -= 30
    
    if len(state.satellites) < 2:
        score -= 20
    
    return round(score, 2)


def phase_index(phase: str) -> int:
    if phase in VALID_PHASES:
        return VALID_PHASES.index(phase)
    return -1
