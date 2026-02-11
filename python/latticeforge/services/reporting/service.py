from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from latticeforge.models import IncidentTicket
from services.policy.service import PolicyDecision

SERVICE_NAME = "reporting"
SERVICE_ROLE = "regulatory and mission reporting"


@dataclass(frozen=True)
class ReportSection:
    key: str
    title: str
    body: Mapping[str, Any]


def rank_incidents(incidents: Sequence[IncidentTicket]) -> list[dict[str, Any]]:
    
    ordered = sorted(incidents, key=lambda incident: (incident.severity, incident.ticket_id))
    return [
        {
            "ticket_id": incident.ticket_id,
            "severity": incident.severity,
            "subsystem": incident.subsystem,
            "description": incident.description,
        }
        for incident in ordered
    ]


def decision_breakdown(decisions: Sequence[PolicyDecision]) -> dict[str, int]:
    counts = {"approved": 0, "hold": 0, "rejected": 0}
    for decision in decisions:
        if decision.hold:
            counts["hold"] += 1
        elif decision.approved:
            counts["approved"] += 1
        else:
            counts["rejected"] += 1
    return counts


def compile_daily_report(
    mission_id: str,
    incidents: Sequence[IncidentTicket],
    decisions: Sequence[PolicyDecision],
    slo_view: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    sections = [
        ReportSection(
            key="incidents",
            title="Incident Rank",
            body={"items": rank_incidents(incidents)},
        ),
        ReportSection(
            key="policy",
            title="Policy Gate Decisions",
            body=decision_breakdown(decisions),
        ),
        ReportSection(
            key="slo",
            title="Service SLO",
            body={"services": dict(slo_view)},
        ),
    ]
    return {
        "mission_id": mission_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "section_count": len(sections),
        "sections": [{"key": s.key, "title": s.title, "body": dict(s.body)} for s in sections],
    }


def serialize_report(report: Mapping[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"))
