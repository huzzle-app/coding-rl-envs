from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from .dependency import topological_sort
from .models import BurnWindow, IncidentTicket


def schedule_operations(
    windows: Iterable[BurnWindow],
    incidents: Iterable[IncidentTicket],
    now: datetime,
) -> List[Dict[str, object]]:
    incident_weight = sum(ticket.severity for ticket in incidents)
    slots: List[Dict[str, object]] = []

    for window in sorted(windows, key=lambda item: (item.start, -item.priority)):
        if window.end <= now:
            continue
        slots.append(
            {
                "window_id": window.window_id,
                "eta": window.start,
                "priority": window.priority + incident_weight,
                "duration": window.duration_seconds(),
            }
        )
    return slots


def sequence_from_dependencies(stages: List[str], edges: List[Tuple[str, str]]) -> List[str]:
    return topological_sort(stages, edges)


def has_window_overlap(windows: Iterable[BurnWindow]) -> bool:
    ordered = sorted(windows, key=lambda item: item.start)
    for current, following in zip(ordered, ordered[1:]):
        if current.end > following.start:
            return True
    return False


def batch_schedule_with_cooldown(
    operations: List[Dict[str, object]],
    batch_size: int,
    cooldown_s: int,
) -> List[Dict[str, object]]:
    if not operations or batch_size <= 0:
        return []

    scheduled: List[Dict[str, object]] = []
    offset = cooldown_s

    for i in range(0, len(operations), batch_size):
        batch = operations[i : i + batch_size]
        for op in batch:
            scheduled.append({**op, "scheduled_offset_s": offset})
        offset += cooldown_s
    return scheduled


def estimate_completion_time(
    scheduled: List[Dict[str, object]],
    per_op_duration_s: int,
    cooldown_s: int,
) -> int:
    if not scheduled:
        return 0
    max_offset = max(int(op["scheduled_offset_s"]) for op in scheduled)
    total = max_offset + per_op_duration_s - cooldown_s
    return max(total, 0)
