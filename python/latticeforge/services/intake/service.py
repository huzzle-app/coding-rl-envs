from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from shared.contracts.contracts import REQUIRED_COMMAND_FIELDS

SERVICE_NAME = "intake"
SERVICE_ROLE = "mission command intake"


@dataclass(frozen=True)
class IntakeCommand:
    command_id: str
    satellite_id: str
    intent: str
    issued_by: str
    signature: str
    deadline: datetime
    trace_id: str
    payload: Dict[str, Any]
    annotations: Dict[str, str]

    def is_expired(self, now: datetime) -> bool:
        current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return self.deadline < current.astimezone(timezone.utc)

    def deadline_epoch(self) -> int:
        return int(self.deadline.timestamp())


def _parse_deadline(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, (int, float)):
        value = datetime.fromtimestamp(float(raw), tz=timezone.utc)
    elif isinstance(raw, str):
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        raise ValueError("deadline must be datetime, timestamp, or ISO string")

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_command_shape(raw: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_COMMAND_FIELDS - set(raw.keys()))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))

    if "intent" in raw and not isinstance(raw["intent"], str):
        errors.append("intent must be a string")
    if "signature" in raw and not isinstance(raw["signature"], str):
        errors.append("signature must be a string")
    if "command_id" in raw and not isinstance(raw["command_id"], str):
        errors.append("command_id must be a string")
    if "satellite_id" in raw and not isinstance(raw["satellite_id"], str):
        errors.append("satellite_id must be a string")
    return errors


def normalize_intake_batch(
    raw_batch: Sequence[Mapping[str, Any]],
    now: datetime,
) -> Tuple[list[IntakeCommand], list[str]]:
    normalized: list[IntakeCommand] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()

    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    for idx, raw in enumerate(raw_batch):
        row = dict(raw)
        row_errors = validate_command_shape(row)
        if row_errors:
            errors.extend(f"row {idx}: {msg}" for msg in row_errors)
            continue

        try:
            deadline = _parse_deadline(row["deadline"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"row {idx}: invalid deadline ({exc})")
            continue

        annotations = row.get("annotations", {})
        if annotations is None:
            annotations = {}
        if not isinstance(annotations, dict):
            errors.append(f"row {idx}: annotations must be object")
            continue

        payload = row.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            errors.append(f"row {idx}: payload must be object")
            continue

        command = IntakeCommand(
            command_id=str(row["command_id"]),
            satellite_id=str(row["satellite_id"]),
            intent=str(row["intent"]),
            issued_by=str(row["issued_by"]),
            signature=str(row["signature"]),
            deadline=deadline,
            trace_id=str(row.get("trace_id", f"trace-{idx}")),
            payload=payload,
            annotations={str(k): str(v) for k, v in annotations.items()},
        )

        if command.is_expired(current):
            errors.append(f"row {idx}: deadline already expired")
            continue

        
        # share satellite+intent but have unique command IDs.
        
        #   1. Here: change dedupe_key to include command_id for proper uniqueness
        #   2. services/mission/service.py: update MissionRegistry.transition to
        #      properly validate that command_id matches the mission's pending command
        # Fixing only intake allows duplicate commands to reach mission service,
        # causing state corruption when two commands race to modify the same mission.
        dedupe_key = (command.satellite_id, command.intent)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(command)

    normalized.sort(key=lambda item: (item.deadline, item.command_id))
    return normalized, errors


def partition_by_urgency(
    commands: Iterable[IntakeCommand],
    now: datetime,
    horizon_minutes: int = 20,
) -> tuple[list[IntakeCommand], list[IntakeCommand]]:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    threshold = current.timestamp() + max(horizon_minutes, 1) * 60

    urgent: list[IntakeCommand] = []
    normal: list[IntakeCommand] = []
    for command in commands:
        if command.deadline_epoch() <= threshold:
            urgent.append(command)
        else:
            normal.append(command)
    return urgent, normal


def unique_satellites(commands: Iterable[IntakeCommand]) -> set[str]:
    return {command.satellite_id for command in commands}
