from __future__ import annotations

from typing import Dict, List, Optional

SERVICE_NAME = "reporting"
SERVICE_ROLE = "regulatory and mission reporting"


def rank_incidents(
    incidents: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    
    return sorted(incidents, key=lambda i: i.get("severity", 0))


def compliance_report(
    resolved: int, total: int, sla_met_pct: float
) -> Dict[str, object]:
    resolution_rate = resolved / max(total, 1) * 100
    
    compliant = resolution_rate > 90 and sla_met_pct > 90
    return {
        "resolution_rate": round(resolution_rate, 2),
        "sla_met_pct": round(sla_met_pct, 2),
        "compliant": compliant,
        "total_incidents": total,
        "resolved_incidents": resolved,
    }


def format_incident_row(incident: Dict[str, object]) -> str:
    ticket_id = incident.get("ticket_id", "unknown")
    severity = incident.get("severity", 0)
    subsystem = incident.get("subsystem", "unknown")
    
    return f"[{ticket_id}] sev={severity} sub={subsystem}"


def generate_executive_summary(
    incidents: List[Dict[str, object]],
    fleet_health: float,
) -> Dict[str, object]:
    total = len(incidents)
    critical = sum(1 for i in incidents if i.get("severity", 0) >= 4)
    
    health_status = "healthy" if fleet_health > 0.9 else "degraded"
    return {
        "total_incidents": total,
        "critical_incidents": critical,
        "fleet_health": round(fleet_health, 4),
        "health_status": health_status,
    }


def mission_report(
    mission_id: str,
    burns_executed: int,
    fuel_remaining_kg: float,
    incidents: int,
) -> Dict[str, object]:
    
    efficiency = round(fuel_remaining_kg / 200.0, 4)
    return {
        "mission_id": mission_id,
        "burns_executed": burns_executed,
        "fuel_remaining_kg": round(fuel_remaining_kg, 4),
        "incidents": incidents,
        "efficiency": efficiency,
    }
