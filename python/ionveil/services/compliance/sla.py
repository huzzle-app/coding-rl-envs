"""
IonVeil SLA Monitoring & Compliance Service
===============================================
Monitors SLA compliance for incident response, maintains an immutable
audit log, and generates regulatory compliance reports.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

import aiohttp

logger = logging.getLogger("ionveil.compliance")


# ---------------------------------------------------------------------------
# SLA Configuration
# ---------------------------------------------------------------------------

# Maximum response time (minutes) by priority level
SLA_RESPONSE_TIMES: dict[int, int] = {
    1: 5,    # Critical: 5 min
    2: 10,   # High: 10 min
    3: 20,   # Medium: 20 min
    4: 45,   # Low: 45 min
    5: 120,  # Informational: 2 hours
}

# Escalation thresholds (percentage of SLA time elapsed)
ESCALATION_THRESHOLDS = [0.50, 0.75, 0.90, 1.00]


class SLAStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACHED = "breached"
    UNKNOWN = "unknown"


@dataclass
class SLACheckResult:
    incident_id: str
    priority: int
    sla_target_minutes: int
    elapsed_minutes: float
    status: SLAStatus
    remaining_minutes: float
    escalation_level: int  # 0 = none, 1-4 = escalation stages
    breach_time: Optional[datetime] = None


@dataclass
class AuditEntry:
    id: str
    org_id: str
    incident_id: Optional[str]
    action: str
    actor: str
    details: dict[str, Any]
    timestamp: datetime
    checksum: str  # SHA-256 of entry content for tamper detection


# ---------------------------------------------------------------------------
# In-memory persistence adapters for benchmark runtime.
# ---------------------------------------------------------------------------

class _AuditDB:
    """In-memory audit log store simulating an append-only table."""

    def __init__(self):
        self._entries: list[AuditEntry] = []

    async def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    async def query(
        self,
        org_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        action: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> list[AuditEntry]:
        """Query audit entries.

        """
        results = []
        for e in self._entries:
            if e.org_id != org_id:
                continue
            if start and e.timestamp < start:
                continue
            if end and e.timestamp > end:
                continue
            if action and e.action != action:
                continue
            if incident_id and e.incident_id != incident_id:
                continue
            results.append(e)
        return results

    async def count(self, org_id: str) -> int:
        return sum(1 for e in self._entries if e.org_id == org_id)


class _IncidentDB:
    """Stub incident database for SLA checks."""

    def __init__(self):
        self._incidents: dict[str, dict[str, Any]] = {}

    async def get(self, incident_id: str) -> Optional[dict[str, Any]]:
        return self._incidents.get(incident_id)

    async def update_sla_status(self, incident_id: str, status: str) -> None:
        inc = self._incidents.get(incident_id)
        if inc:
            inc["sla_status"] = status


# ---------------------------------------------------------------------------
# SLA Monitor
# ---------------------------------------------------------------------------

class SLAMonitor:
    """Check and enforce SLA compliance for incident response."""

    def __init__(
        self,
        incident_db: Optional[_IncidentDB] = None,
        audit_db: Optional[_AuditDB] = None,
    ):
        self._incidents = incident_db or _IncidentDB()
        self._audit = audit_db or _AuditDB()

    async def check_sla_compliance(
        self,
        incident_id: str,
        dispatch_time: datetime,
        arrival_time: Optional[datetime] = None,
        priority: int = 3,
    ) -> SLACheckResult:
        """Evaluate SLA compliance for a single incident."""
        sla_target = SLA_RESPONSE_TIMES.get(priority, 120)
        now = datetime.now(timezone.utc)

        if arrival_time:
            elapsed = (arrival_time - dispatch_time).total_seconds() / 60.0
        else:
            elapsed = (now - dispatch_time).total_seconds() / 60.0

        remaining = sla_target - elapsed
        ratio = elapsed / sla_target if sla_target > 0 else 1.0

        # Determine escalation level
        escalation = 0
        for i, threshold in enumerate(ESCALATION_THRESHOLDS):
            if ratio >= threshold:
                escalation = i + 1

        # Determine status
        if arrival_time and elapsed <= sla_target:
            status = SLAStatus.COMPLIANT
        elif ratio >= 1.0:
            status = SLAStatus.BREACHED
        elif ratio >= 0.75:
            status = SLAStatus.WARNING
        else:
            status = SLAStatus.COMPLIANT

        breach_time = None
        if status == SLAStatus.BREACHED:
            breach_time = dispatch_time + timedelta(minutes=sla_target)

        result = SLACheckResult(
            incident_id=incident_id,
            priority=priority,
            sla_target_minutes=sla_target,
            elapsed_minutes=round(elapsed, 2),
            status=status,
            remaining_minutes=round(max(0, remaining), 2),
            escalation_level=escalation,
            breach_time=breach_time,
        )

        # Update incident record
        await self._incidents.update_sla_status(incident_id, status.value)

        return result

    async def check_all_active(
        self,
        org_id: str,
        active_incidents: list[dict[str, Any]],
    ) -> list[SLACheckResult]:
        """Batch-check SLA compliance for all active incidents."""
        results = []
        for inc in active_incidents:
            dispatch_time = inc.get("dispatch_time")
            if not dispatch_time:
                continue
            if isinstance(dispatch_time, str):
                dispatch_time = datetime.fromisoformat(dispatch_time)

            result = await self.check_sla_compliance(
                incident_id=inc["id"],
                dispatch_time=dispatch_time,
                arrival_time=inc.get("arrival_time"),
                priority=inc.get("priority", 3),
            )
            results.append(result)
        return results


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Append-only audit log for compliance and forensics."""

    def __init__(self, db: Optional[_AuditDB] = None):
        self._db = db or _AuditDB()

    async def log_audit_event(
        self,
        org_id: str,
        action: str,
        actor: str,
        details: dict[str, Any],
        incident_id: Optional[str] = None,
    ) -> str:
        """Record an immutable audit event."""
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Compute checksum for tamper detection
        content = json.dumps({
            "id": entry_id,
            "org_id": org_id,
            "action": action,
            "actor": actor,
            "details": details,
            "incident_id": incident_id,
            "timestamp": now.isoformat(),
        }, sort_keys=True)
        checksum = hashlib.sha256(content.encode()).hexdigest()

        entry = AuditEntry(
            id=entry_id,
            org_id=org_id,
            incident_id=incident_id,
            action=action,
            actor=actor,
            details=details,
            timestamp=now,
            checksum=checksum,
        )
        await self._db.append(entry)
        logger.info("Audit event: %s by %s [%s]", action, actor, entry_id[:8])
        return entry_id

    async def get_audit_trail(
        self,
        org_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        incident_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve the audit trail for an organisation or incident."""
        entries = await self._db.query(org_id, start, end, incident_id=incident_id)
        return [
            {
                "id": e.id,
                "action": e.action,
                "actor": e.actor,
                "details": e.details,
                "incident_id": e.incident_id,
                "timestamp": e.timestamp.isoformat(),
                "checksum": e.checksum,
            }
            for e in sorted(entries, key=lambda x: x.timestamp)
        ]


# ---------------------------------------------------------------------------
# Compliance Report Generator
# ---------------------------------------------------------------------------

class ComplianceReportGenerator:
    """Generate regulatory compliance reports."""

    def __init__(
        self,
        sla_monitor: Optional[SLAMonitor] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self._sla = sla_monitor or SLAMonitor()
        self._audit = audit_logger or AuditLogger()

    async def generate_compliance_report(
        self,
        org_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Generate a compliance report for the given period.


        """
        query = f"SELECT * FROM audits WHERE org_id = '{org_id}' AND timestamp >= '{start.isoformat()}' AND timestamp <= '{end.isoformat()}'"
        logger.debug("Compliance query: %s", query)

        # Local runtime fallback uses the in-memory query path.
        audit_entries = await self._audit._db.query(org_id, start, end)

        # Build report
        total_events = len(audit_entries)
        actions_summary: dict[str, int] = {}
        for entry in audit_entries:
            actions_summary[entry.action] = actions_summary.get(entry.action, 0) + 1

        report = {
            "org_id": org_id,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_audit_events": total_events,
            "actions_summary": actions_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self._enrich_report_with_external_data(report, audit_entries)

        return report

    async def _enrich_report_with_external_data(
        self,
        report: dict[str, Any],
        entries: list[AuditEntry],
    ) -> None:
        """Fetch supplementary data from external URLs in metadata.

        """
        external_data = []
        for entry in entries:
            url = entry.details.get("report_url")
            if url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            data = await resp.json()
                            external_data.append({
                                "source": url,
                                "status": resp.status,
                                "data": data,
                            })
                except Exception as exc:
                    logger.warning("Failed to fetch external data from %s: %s", url, exc)

        if external_data:
            report["external_references"] = external_data
