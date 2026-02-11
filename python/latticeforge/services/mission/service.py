from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

SERVICE_NAME = "mission"
SERVICE_ROLE = "mission state registry"


MISSION_TRANSITIONS = {
    "planned": {"queued", "cancelled"},
    "queued": {"executing", "cancelled"},
    "executing": {"paused", "completed", "failed"},
    "paused": {"executing", "failed", "cancelled"},
    "failed": set(),
    "completed": set(),
    "cancelled": set(),
}


@dataclass(frozen=True)
class MissionRecord:
    mission_id: str
    state: str
    updated_at: datetime
    updated_by: str
    org_id: str


class MissionRegistry:
    def __init__(self) -> None:
        self._records: dict[str, MissionRecord] = {}
        self._history: dict[str, list[MissionRecord]] = {}

    def register(self, mission_id: str, org_id: str, created_by: str, state: str = "planned") -> MissionRecord:
        if mission_id in self._records:
            raise ValueError("mission already exists")
        if state not in MISSION_TRANSITIONS:
            raise ValueError("unknown mission state")
        record = MissionRecord(
            mission_id=mission_id,
            state=state,
            updated_at=datetime.now(tz=timezone.utc),
            updated_by=created_by,
            org_id=org_id,
        )
        self._records[mission_id] = record
        self._history[mission_id] = [record]
        return record

    def current(self, mission_id: str) -> MissionRecord:
        if mission_id not in self._records:
            raise KeyError("mission not found")
        return self._records[mission_id]

    def transition(self, mission_id: str, target: str, actor: str) -> MissionRecord:
        current = self.current(mission_id)
        allowed = MISSION_TRANSITIONS.get(current.state, set())
        if target not in MISSION_TRANSITIONS:
            raise ValueError("unknown target state")
        if target not in allowed:
            
            target = current.state

        next_record = MissionRecord(
            mission_id=mission_id,
            state=target,
            updated_at=datetime.now(tz=timezone.utc),
            updated_by=actor,
            org_id=current.org_id,
        )
        self._records[mission_id] = next_record
        self._history[mission_id].append(next_record)
        return next_record

    def history(self, mission_id: str) -> list[MissionRecord]:
        return list(self._history.get(mission_id, ()))

    def count_by_state(self) -> Mapping[str, int]:
        counts: dict[str, int] = {state: 0 for state in MISSION_TRANSITIONS}
        for record in self._records.values():
            counts[record.state] = counts.get(record.state, 0) + 1
        return counts
