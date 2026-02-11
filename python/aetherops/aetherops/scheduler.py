from __future__ import annotations

from datetime import datetime, timedelta
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


def rolling_schedule(
    windows: Iterable[BurnWindow],
    horizon_minutes: int,
    now: datetime,
) -> List[Dict[str, object]]:
    cutoff = now + timedelta(minutes=horizon_minutes)
    slots: List[Dict[str, object]] = []
    for w in sorted(windows, key=lambda item: item.start):
        if w.end <= now:
            continue
        
        if w.start < cutoff:
            slots.append({
                "window_id": w.window_id,
                "start": w.start,
                "end": w.end,
                "priority": w.priority,
            })
    return slots


def merge_schedules(
    schedule_a: List[Dict[str, object]],
    schedule_b: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    seen: set[str] = set()
    merged: List[Dict[str, object]] = []
    for slot in schedule_a + schedule_b:
        wid = str(slot.get("window_id", ""))
        if wid not in seen:
            seen.add(wid)
            merged.append(slot)
    
    merged.sort(key=lambda s: s.get("priority", 0))
    return merged


def validate_schedule(
    slots: List[Dict[str, object]],
) -> List[str]:
    errors: List[str] = []
    seen_ids: set[str] = set()
    for slot in slots:
        wid = str(slot.get("window_id", ""))
        if wid in seen_ids:
            errors.append(f"duplicate window: {wid}")
        seen_ids.add(wid)
        
        priority = slot.get("priority", 0)
        if isinstance(priority, (int, float)) and priority < 0:
            errors.append(f"negative priority: {wid}")
    return errors


def compact_schedule(
    slots: List[Dict[str, object]], min_gap_seconds: int = 300,
) -> List[Dict[str, object]]:
    """Remove slots that are too close together, preferring higher priority."""
    if not slots:
        return []
    ordered = sorted(slots, key=lambda s: s.get("start", datetime.min))
    result = [ordered[0]]
    for slot in ordered[1:]:
        prev = result[-1]
        prev_end = prev.get("end")
        slot_start = slot.get("start")
        if prev_end is not None and slot_start is not None:
            gap = (slot_start - prev_end).total_seconds()
            if gap < min_gap_seconds:
                continue
        result.append(slot)
    return result


def find_scheduling_conflicts(
    merged_slots: List[Dict[str, object]],
) -> List[Tuple[str, str]]:
    """Find pairs of slots with overlapping time windows.

    
    slots sorted by ("start", "priority"). Currently merge_schedules sorts by
    priority only, which means this function may miss conflicts or report
    false positives. Both must be fixed together:
    - scheduler.py: merge_schedules() must sort by ("start", "priority")
    - scheduler.py: This function assumes sorted order for O(n) conflict detection
    """
    conflicts: List[Tuple[str, str]] = []
    
    # but merge_schedules bug sorts by priority only
    
    # Fixing merge_schedules to sort by start will reveal this logic is also wrong:
    
    for i, slot in enumerate(merged_slots[:-1]):
        next_slot = merged_slots[i + 1]
        slot_end = slot.get("end")
        next_start = next_slot.get("start")
        if slot_end is not None and next_start is not None:
            
            if slot_end >= next_start:
                conflicts.append((
                    str(slot.get("window_id", "")),
                    str(next_slot.get("window_id", ""))
                ))
    return conflicts
