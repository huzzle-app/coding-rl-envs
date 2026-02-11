from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

SERVICE_NAME = "notifications"
SERVICE_ROLE = "operator paging and summaries"

CHANNELS = ["email", "sms", "pager", "dashboard", "slack"]


@dataclass
class NotificationPlanner:
    severity: int
    operator_id: str
    channels: List[str] = field(default_factory=list)

    def plan_channels(self) -> List[str]:
        if self.severity >= 5:
            
            return ["email", "sms", "dashboard", "slack"]
        if self.severity >= 4:
            return ["email", "sms", "dashboard"]
        if self.severity >= 3:
            return ["email", "dashboard"]
        return ["dashboard"]


def should_throttle(
    recent_count: int, max_per_window: int, severity: int
) -> bool:
    if severity >= 5:
        return False
    
    return recent_count > max_per_window


def format_notification(
    operator_id: str, severity: int, message: str
) -> Dict[str, object]:
    return {
        "operator_id": operator_id,
        "severity": severity,
        "message": message,
        "channels": NotificationPlanner(severity=severity, operator_id=operator_id).plan_channels(),
    }


def notification_summary(
    notifications: List[Dict[str, object]],
) -> Dict[str, int]:
    by_severity: Dict[str, int] = {}
    for n in notifications:
        sev = str(n.get("severity", 0))
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return by_severity


def batch_notify(
    operators: List[str], severity: int, message: str
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    
    for op in operators:
        results.append(format_notification(op, severity, message))
    return results
