"""
Notifications Service - Celery tasks for sending notifications.

BUG C7: Bulkhead not implemented - one slow notification type blocks all
BUG J3: Metrics cardinality explosion
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any

from celery import Celery

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/8")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

app = Celery(
    "notifications",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # No bulkhead isolation
    task_default_queue="notifications",
)

# Metrics storage - BUG J3: Unbounded cardinality
notification_metrics: Dict[str, int] = {}


@app.task(bind=True)
def send_email_notification(self, user_id: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Send email notification.

    BUG C7: Slow email sending blocks other notifications
    """
    try:
        # Simulate slow email sending
        import time
        time.sleep(2)  

        
        metric_key = f"email_sent_{user_id}"
        notification_metrics[metric_key] = notification_metrics.get(metric_key, 0) + 1

        logger.info(f"Sent email to {user_id}: {subject}")
        return {"status": "sent", "type": "email", "user_id": user_id}

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_push_notification(self, user_id: str, title: str, message: str) -> Dict[str, Any]:
    """Send push notification."""
    try:
        
        metric_key = f"push_sent_{user_id}"
        notification_metrics[metric_key] = notification_metrics.get(metric_key, 0) + 1

        logger.info(f"Sent push to {user_id}: {title}")
        return {"status": "sent", "type": "push", "user_id": user_id}

    except Exception as e:
        logger.error(f"Failed to send push: {e}")
        raise self.retry(exc=e, countdown=30, max_retries=3)


@app.task
def send_order_confirmation(user_id: str, order_id: str, order_details: Dict[str, Any]) -> Dict[str, Any]:
    """Send order confirmation notification."""
    subject = f"Order Confirmation: {order_id[:8]}"
    body = f"Your order for {order_details.get('quantity')} {order_details.get('symbol')} has been received."

    
    send_email_notification.delay(user_id, subject, body)

    return {"status": "queued", "order_id": order_id}


@app.task
def send_trade_execution(user_id: str, trade_id: str, trade_details: Dict[str, Any]) -> Dict[str, Any]:
    """Send trade execution notification."""
    subject = f"Trade Executed: {trade_details.get('symbol')}"
    body = f"Executed {trade_details.get('quantity')} @ {trade_details.get('price')}"

    send_email_notification.delay(user_id, subject, body)
    send_push_notification.delay(user_id, "Trade Executed", body)

    return {"status": "queued", "trade_id": trade_id}


@app.task
def send_margin_call_alert(user_id: str, margin_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send urgent margin call alert.

    BUG C7: Urgent alerts stuck behind slow emails in queue
    """
    subject = "URGENT: Margin Call"
    body = f"Your margin ratio is {margin_status.get('margin_ratio')}. Please deposit funds immediately."

    
    send_email_notification.delay(user_id, subject, body)
    send_push_notification.delay(user_id, subject, body)

    return {"status": "queued", "alert_type": "margin_call"}


# Simple HTTP health check
if __name__ == "__main__":
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "healthy", "service": "notifications"}')
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
    server.serve_forever()
