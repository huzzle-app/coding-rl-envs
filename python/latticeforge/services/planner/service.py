from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from latticeforge.dependency import longest_chain, topological_sort
from latticeforge.models import BurnWindow, IncidentTicket
from latticeforge.scheduler import has_window_overlap, schedule_operations

SERVICE_NAME = "planner"
SERVICE_ROLE = "burn planning and timeline"


@dataclass(frozen=True)
class PlanStage:
    stage: str
    owner: str
    depends_on: tuple[str, ...]
    critical: bool = False


@dataclass(frozen=True)
class MissionPlan:
    ordered_stages: tuple[str, ...]
    stage_depth: int
    overlap_detected: bool
    schedule: tuple[dict[str, object], ...]
    critical_stages: tuple[str, ...]


def stage_graph_for_incidents(incidents: Iterable[IncidentTicket]) -> tuple[list[str], list[tuple[str, str]]]:
    base_stages = ["intake", "analysis", "policy", "dispatch", "audit"]
    edges = [
        ("intake", "analysis"),
        ("analysis", "policy"),
        ("policy", "dispatch"),
        ("dispatch", "audit"),
    ]
    if any(ticket.severity >= 4 for ticket in incidents):
        base_stages.insert(3, "resilience")
        edges.extend([("analysis", "resilience"), ("resilience", "dispatch")])
    return base_stages, edges


def build_mission_plan(
    windows: Iterable[BurnWindow],
    incidents: Iterable[IncidentTicket],
    now: datetime,
) -> MissionPlan:
    incident_list = list(incidents)
    stages, edges = stage_graph_for_incidents(incident_list)
    ordered = tuple(topological_sort(stages, edges))
    depth = longest_chain(stages, edges)
    schedule = tuple(schedule_operations(windows, incident_list, now))
    overlap = has_window_overlap(windows)
    critical = tuple(stage for stage in ordered if stage in {"policy", "dispatch", "resilience"})
    return MissionPlan(ordered, depth, overlap, schedule, critical)


def critical_path_depth(plan: MissionPlan) -> int:
    return max(plan.stage_depth, len(plan.critical_stages))
