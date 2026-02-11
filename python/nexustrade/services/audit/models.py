"""Audit service models."""
from uuid import uuid4
from django.db import models


class AuditLog(models.Model):
    """Audit log entry."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    service = models.CharField(max_length=50)
    action = models.CharField(max_length=100)
    user_id = models.UUIDField(null=True, blank=True)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100)
    
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "audit"
        db_table = "audit_logs"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["user_id"]),
            models.Index(fields=["service", "action"]),
        ]
