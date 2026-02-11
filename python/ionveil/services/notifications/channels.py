"""
IonVeil Multi-Channel Notification Service
=============================================
Send notifications via email, SMS, push, and radio channels.
Includes template rendering and intelligent channel routing.
"""

import asyncio
import json
import logging
import os
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("ionveil.notifications")

TEMPLATE_DIR = Path(os.getenv("TEMPLATE_DIR", "/opt/ionveil/templates"))

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    RADIO = "radio"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class Recipient:
    id: str
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    push_token: Optional[str] = None
    radio_channel: Optional[str] = None
    preferred_channels: list[Channel] = field(default_factory=lambda: [Channel.EMAIL])


@dataclass
class IncidentContext:
    id: str
    title: str
    description: str
    priority: int
    latitude: float
    longitude: float
    status: str = "open"
    victim_ssn: Optional[str] = None  # sensitive PII
    victim_name: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationResult:
    notification_id: str
    channel: Channel
    recipient_id: str
    success: bool
    error: Optional[str] = None
    sent_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Template engine (simple)
# ---------------------------------------------------------------------------

class TemplateEngine:
    """Load and render notification templates."""

    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self._dir = template_dir
        self._cache: dict[str, str] = {}

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context variables."""
        raw = self._load(template_name)
        # Simple placeholder substitution: {{key}}
        result = raw
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    def _load(self, name: str) -> str:
        """Load template from disk (with in-memory cache)."""
        if name in self._cache:
            return self._cache[name]
        path = self._dir / f"{name}.txt"
        if not path.exists():
            # Fall back to a generic template
            return (
                "IonVeil Alert: {{title}}\n"
                "Priority: P{{priority}}\n"
                "Status: {{status}}\n"
                "Description: {{description}}\n"
                "Location: {{latitude}}, {{longitude}}"
            )
        content = path.read_text(encoding="utf-8")
        self._cache[name] = content
        return content


# ---------------------------------------------------------------------------
# Channel senders
# ---------------------------------------------------------------------------

async def _send_email(
    recipient: Recipient,
    subject: str,
    body: str,
    smtp_host: str = "localhost",
    smtp_port: int = 587,
) -> NotificationResult:
    """Send an email notification."""
    nid = str(uuid.uuid4())
    if not recipient.email:
        return NotificationResult(nid, Channel.EMAIL, recipient.id, False, "No email address")

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = "alerts@ionveil.example.com"
        msg["To"] = recipient.email
        msg.attach(MIMEText(body, "plain"))

        # Use executor-backed sync SMTP send to keep harness behavior deterministic.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: _smtp_send(smtp_host, smtp_port, msg))

        logger.info("Email sent to %s for notification %s", recipient.email, nid)
        return NotificationResult(nid, Channel.EMAIL, recipient.id, True, sent_at=datetime.now(timezone.utc))
    except Exception as exc:
        logger.error("Email send failed for %s: %s", recipient.id, exc)
        return NotificationResult(nid, Channel.EMAIL, recipient.id, False, str(exc))


def _smtp_send(host: str, port: int, msg: MIMEMultipart) -> None:
    """Blocking SMTP send (called via executor)."""
    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        server.send_message(msg)


async def _send_sms(
    recipient: Recipient,
    message: str,
    incident: IncidentContext,
) -> NotificationResult:
    """Send an SMS notification.

    """
    nid = str(uuid.uuid4())
    if not recipient.phone_number:
        return NotificationResult(nid, Channel.SMS, recipient.id, False, "No phone number")

    try:
        template_path = TEMPLATE_DIR / "sms_template.txt"
        if template_path.exists():
            with open(template_path, "r") as f:
                template = f.read()
            message = template.replace("{{message}}", message)

        logger.info(
            "Sending SMS to %s (phone: %s) for incident %s (victim SSN: %s)",
            recipient.name,
            recipient.phone_number,
            incident.id,
            incident.victim_ssn,
        )

        # Simulate SMS API call
        await asyncio.sleep(0.1)

        return NotificationResult(nid, Channel.SMS, recipient.id, True, sent_at=datetime.now(timezone.utc))
    except Exception as exc:
        logger.error("SMS send failed for %s: %s", recipient.id, exc)
        return NotificationResult(nid, Channel.SMS, recipient.id, False, str(exc))


async def _send_push(
    recipient: Recipient,
    title: str,
    body: str,
) -> NotificationResult:
    """Send a push notification via FCM/APNs."""
    nid = str(uuid.uuid4())
    if not recipient.push_token:
        return NotificationResult(nid, Channel.PUSH, recipient.id, False, "No push token")

    try:
        payload = {
            "to": recipient.push_token,
            "notification": {"title": title, "body": body[:256]},
            "priority": "high",
        }
        # Simulate push API call
        await asyncio.sleep(0.05)
        logger.info("Push notification sent to %s", recipient.id)
        return NotificationResult(nid, Channel.PUSH, recipient.id, True, sent_at=datetime.now(timezone.utc))
    except Exception as exc:
        logger.error("Push send failed for %s: %s", recipient.id, exc)
        return NotificationResult(nid, Channel.PUSH, recipient.id, False, str(exc))


async def _send_radio(
    recipient: Recipient,
    message: str,
) -> NotificationResult:
    """Dispatch a radio notification to the unit's assigned channel."""
    nid = str(uuid.uuid4())
    if not recipient.radio_channel:
        return NotificationResult(nid, Channel.RADIO, recipient.id, False, "No radio channel")

    try:
        # Simulate radio dispatch
        await asyncio.sleep(0.02)
        logger.info("Radio dispatch on channel %s for %s", recipient.radio_channel, recipient.id)
        return NotificationResult(nid, Channel.RADIO, recipient.id, True, sent_at=datetime.now(timezone.utc))
    except Exception as exc:
        return NotificationResult(nid, Channel.RADIO, recipient.id, False, str(exc))


# ---------------------------------------------------------------------------
# High-level send function
# ---------------------------------------------------------------------------

async def send_notification(
    incident: IncidentContext,
    channel: Channel,
    recipients: list[Recipient],
) -> list[NotificationResult]:
    """Send a notification to all recipients on the specified channel."""
    engine = TemplateEngine()
    ctx = {
        "title": incident.title,
        "description": incident.description,
        "priority": incident.priority,
        "status": incident.status,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "incident_id": incident.id,
    }
    body = engine.render(f"incident_{channel.value}", ctx)
    subject = f"[P{incident.priority}] {incident.title}"

    tasks = []
    for recipient in recipients:
        if channel == Channel.EMAIL:
            tasks.append(_send_email(recipient, subject, body))
        elif channel == Channel.SMS:
            tasks.append(_send_sms(recipient, body, incident))
        elif channel == Channel.PUSH:
            tasks.append(_send_push(recipient, subject, body))
        elif channel == Channel.RADIO:
            tasks.append(_send_radio(recipient, body))

    results = await asyncio.gather(*tasks)
    return list(results)


# ---------------------------------------------------------------------------
# Notification Router
# ---------------------------------------------------------------------------

class NotificationRouter:
    """Route notifications to the appropriate channel(s) based on
    priority and recipient preferences.
    """

    # Priority -> required channels
    CHANNEL_POLICY: dict[int, list[Channel]] = {
        1: [Channel.SMS, Channel.PUSH, Channel.RADIO, Channel.EMAIL],
        2: [Channel.SMS, Channel.PUSH, Channel.EMAIL],
        3: [Channel.PUSH, Channel.EMAIL],
        4: [Channel.EMAIL],
        5: [Channel.EMAIL],
    }

    async def route(
        self,
        incident: IncidentContext,
        recipients: list[Recipient],
    ) -> list[NotificationResult]:
        """Deliver notifications on all channels dictated by policy."""
        channels = self.CHANNEL_POLICY.get(incident.priority, [Channel.EMAIL])

        all_results: list[NotificationResult] = []
        for channel in channels:
            eligible = [r for r in recipients if self._has_channel(r, channel)]
            if not eligible:
                continue
            results = await send_notification(incident, channel, eligible)
            all_results.extend(results)

        return all_results

    async def send_all_channels(
        self,
        incident: IncidentContext,
        recipients: list[Recipient],
    ) -> list[NotificationResult]:
        """Blast on ALL channels simultaneously.

        """
        tasks = []
        for channel in Channel:
            eligible = [r for r in recipients if self._has_channel(r, channel)]
            if eligible:
                tasks.append(send_notification(incident, channel, eligible))

        results = await asyncio.gather(*tasks)
        flat: list[NotificationResult] = []
        for batch in results:
            flat.extend(batch)
        return flat

    @staticmethod
    def _has_channel(recipient: Recipient, channel: Channel) -> bool:
        if channel == Channel.EMAIL:
            return recipient.email is not None
        if channel == Channel.SMS:
            return recipient.phone_number is not None
        if channel == Channel.PUSH:
            return recipient.push_token is not None
        if channel == Channel.RADIO:
            return recipient.radio_channel is not None
        return False


# ---------------------------------------------------------------------------
# Event Listener Registry
# ---------------------------------------------------------------------------

_listeners: list[Any] = []


class NotificationChannel:
    """Base class for notification channel integrations.

    """

    def __init__(self, channel_name: str, handler: Any = None):
        self.channel_name = channel_name
        self._handler = handler or self._default_handler

        _listeners.append({
            "channel": channel_name,
            "handler": self._handler,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(
            "Registered listener for channel %s (total listeners: %d)",
            channel_name, len(_listeners),
        )

    def teardown(self) -> None:
        """Tear down the notification channel.

        """
        logger.info("Channel %s torn down (listeners NOT cleaned up)", self.channel_name)

    @staticmethod
    def _default_handler(event: dict) -> None:
        logger.debug("Default handler processing event: %s", event.get("type", "unknown"))

    @staticmethod
    def notify_all(event: dict) -> None:
        """Fan out an event to all registered listeners."""
        for listener in _listeners:
            try:
                listener["handler"](event)
            except Exception as exc:
                logger.error("Listener %s failed: %s", listener["channel"], exc)


# ---------------------------------------------------------------------------
# Redis Cache Layer (used by notification dedup)
# ---------------------------------------------------------------------------

class NotificationCache:
    """Redis-backed cache for notification deduplication and rate limiting.


    """

    def __init__(self, redis_clients: list[Any]):
        """
        Parameters
        ----------
        redis_clients : list
            List of Redis client instances, one per shard.
        """
        self._shards = redis_clients
        self._num_shards = len(redis_clients) if redis_clients else 1

    def _get_shard(self, key: str) -> Any:
        """Select the correct shard for a given key via consistent hashing."""
        shard_idx = hash(key) % self._num_shards
        return self._shards[shard_idx]

    def get(self, key: str) -> Optional[str]:
        """Read from the correct shard based on key hash."""
        shard = self._get_shard(key)  # correct shard selection
        return shard.get(key)

    def set(self, key: str, value: str, ttl: int = 300) -> None:
        """Write a cache entry.

        """
        shard = self._shards[0]
        shard.set(key, value, ex=ttl)

    def delete(self, key: str) -> None:
        """Delete a key from the correct shard."""
        shard = self._get_shard(key)
        shard.delete(key)

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern across all shards.


        Parameters
        ----------
        pattern : str
            Redis glob pattern (e.g. ``"notif:incident:*"``).

        Returns
        -------
        int
            Number of keys deleted.
        """
        deleted = 0
        for shard in self._shards:
            cursor, keys = shard.scan(cursor=0, match=pattern, count=100)
            # Missing: while cursor != 0: cursor, more_keys = shard.scan(...)
            if keys:
                shard.delete(*keys)
                deleted += len(keys)
        return deleted
