"""
SynapseNet Webhooks Service Views
Terminal Bench v2 - Event Webhooks & Notifications

Contains bugs:
- I2: SSRF via webhook URL - no validation of target URL
- J3: Metrics cardinality explosion from dynamic labels
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class WebhookManager:
    """
    Manage webhook subscriptions and delivery.

    BUG I2: Does not validate webhook URLs. An attacker can register
    internal URLs (http://169.254.169.254, http://localhost:8001)
    to perform SSRF attacks.
    """

    def __init__(self):
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._delivery_log: List[Dict[str, Any]] = []

    def register_webhook(self, url: str, events: List[str], secret: Optional[str] = None) -> str:
        """
        Register a webhook.

        BUG I2: No URL validation - allows internal/private network URLs.
        """
        subscription_id = str(uuid.uuid4())
        
        # Should block: localhost, 127.0.0.1, 169.254.x.x, 10.x.x.x, 172.16-31.x.x, 192.168.x.x
        self._subscriptions[subscription_id] = {
            "url": url,  # Could be http://169.254.169.254/latest/meta-data/
            "events": events,
            "secret": secret,
            "created_at": time.time(),
            "is_active": True,
        }
        return subscription_id

    def deliver_event(self, event_type: str, payload: Dict[str, Any]) -> int:
        """Deliver event to matching webhooks."""
        delivered = 0
        for sub_id, sub in self._subscriptions.items():
            if sub["is_active"] and event_type in sub["events"]:
                self._delivery_log.append({
                    "subscription_id": sub_id,
                    "url": sub["url"],
                    "event_type": event_type,
                    "timestamp": time.time(),
                })
                delivered += 1
        return delivered


class MetricsCollector:
    """
    Collect metrics for monitoring.

    BUG J3: Creates unique metric labels for every request, causing
    cardinality explosion that crashes the monitoring system.
    """

    def __init__(self):
        self._metrics: Dict[str, int] = {}

    def record_delivery(self, subscription_id: str, event_type: str, url: str, status: str):
        """
        Record a webhook delivery metric.

        BUG J3: Uses subscription_id and URL in metric labels.
        With many subscriptions, this creates unbounded cardinality.
        """
        
        label = f"webhook_delivery_{{sub={subscription_id},type={event_type},url={url},status={status}}}"
        self._metrics[label] = self._metrics.get(label, 0) + 1

    def get_metric_count(self) -> int:
        """Get total number of unique metric labels."""
        return len(self._metrics)
