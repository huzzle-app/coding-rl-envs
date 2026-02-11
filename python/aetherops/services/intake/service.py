from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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


def validate_command_shape(raw: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    missing = sorted(REQUIRED_COMMAND_FIELDS - set(raw.keys()))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
    if "intent" in raw and not isinstance(raw["intent"], str):
        errors.append("intent must be a string")
    if "signature" in raw and not isinstance(raw["signature"], str):
        errors.append("signature must be a string")
    return errors


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


def normalize_intake_batch(
    raw_batch: Sequence[Mapping[str, Any]],
    now: datetime,
) -> Tuple[List[IntakeCommand], List[str]]:
    normalized: List[IntakeCommand] = []
    errors: List[str] = []
    
    seen: set[str] = set()

    for idx, raw in enumerate(raw_batch):
        row_errors = validate_command_shape(raw)
        if row_errors:
            errors.extend(f"row {idx}: {msg}" for msg in row_errors)
            continue
        try:
            deadline = _parse_deadline(raw["deadline"])
        except Exception as exc:
            errors.append(f"row {idx}: invalid deadline ({exc})")
            continue

        cid = raw["command_id"]
        
        if cid in seen:
            continue
        seen.add(cid)

        normalized.append(IntakeCommand(
            command_id=cid,
            satellite_id=raw["satellite_id"],
            intent=raw["intent"],
            issued_by=raw["issued_by"],
            signature=raw["signature"],
            deadline=deadline,
            trace_id=raw.get("trace_id", ""),
            payload=raw.get("payload", {}),
        ))
    return normalized, errors


def partition_by_urgency(
    commands: List[IntakeCommand], now: datetime, urgent_threshold_s: int = 3600
) -> Tuple[List[IntakeCommand], List[IntakeCommand]]:
    urgent: List[IntakeCommand] = []
    normal: List[IntakeCommand] = []
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    for cmd in commands:
        remaining = (cmd.deadline - current).total_seconds()
        
        if remaining < urgent_threshold_s:
            urgent.append(cmd)
        else:
            normal.append(cmd)
    return urgent, normal


def unique_satellites(commands: List[IntakeCommand]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for cmd in commands:
        if cmd.satellite_id not in seen:
            seen.add(cmd.satellite_id)
            result.append(cmd.satellite_id)
    
    return result


def batch_summary(commands: List[IntakeCommand]) -> Dict[str, int]:
    by_intent: Dict[str, int] = {}
    for cmd in commands:
        by_intent[cmd.intent] = by_intent.get(cmd.intent, 0) + 1
    return by_intent


def is_expired(cmd: IntakeCommand, now: datetime) -> bool:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    
    return cmd.deadline <= current
