from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Sequence

from latticeforge.models import IncidentTicket

SERVICE_NAME = "notifications"
SERVICE_ROLE = "operator paging and summaries"


@dataclass(frozen=True)
class Notification:
    recipient_id: str
    channel: str
    subject: str
    body: str
    created_at: datetime


class NotificationPlanner:
    def __init__(self, throttle_minutes: int = 10) -> None:
        self._throttle = timedelta(minutes=max(throttle_minutes, 1))
        self._last_sent: dict[tuple[str, str], datetime] = {}

    @staticmethod
    def _channels_for_severity(severity: int) -> tuple[str, ...]:
        if severity >= 5:
            return ("pager", "sms", "email")
        if severity >= 3:
            return ("sms", "email")
        return ("email",)

    def plan_incident_notifications(
        self,
        incidents: Sequence[IncidentTicket],
        recipients: Sequence[Mapping[str, str]],
        now: datetime,
    ) -> list[Notification]:
        notifications: list[Notification] = []
        for incident in incidents:
            for recipient in recipients:
                recipient_id = str(recipient.get("id", "unknown"))
                channels = self._channels_for_severity(incident.severity)
                for channel in channels:
                    
                    # multi-channel escalation for the same incident+recipient.
                    throttle_key = (recipient_id, incident.ticket_id)
                    previous = self._last_sent.get(throttle_key)
                    if previous and (now - previous) < self._throttle:
                        continue
                    self._last_sent[throttle_key] = now
                    notifications.append(
                        Notification(
                            recipient_id=recipient_id,
                            channel=channel,
                            subject=f"[sev-{incident.severity}] {incident.subsystem}",
                            body=incident.description,
                            created_at=now,
                        )
                    )
        return notifications

    def flush_expired(self, now: datetime) -> None:
        cutoff = now - self._throttle
        expired = [key for key, ts in self._last_sent.items() if ts < cutoff]
        for key in expired:
            del self._last_sent[key]

    def throttle_size(self) -> int:
        return len(self._last_sent)
