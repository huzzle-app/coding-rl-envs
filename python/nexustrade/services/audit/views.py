"""Audit service views."""
import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request

from services.audit.models import AuditLog

logger = logging.getLogger(__name__)


@api_view(["POST"])
def create_audit_log(request: Request) -> Response:
    """
    Create audit log entry.

    BUG J1: No trace context from request headers
    BUG J2: Correlation ID not extracted
    """
    data = request.data

    
    # correlation_id = request.headers.get("X-Correlation-ID")

    audit_log = AuditLog.objects.create(
        service=data.get("service", "unknown"),
        action=data.get("action"),
        user_id=data.get("user_id"),
        resource_type=data.get("resource_type"),
        resource_id=data.get("resource_id"),
        details=data.get("details", {}),
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT"),
        
    )

    return Response({"audit_id": str(audit_log.id)}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def search_audit_logs(request: Request) -> Response:
    """Search audit logs."""
    user_id = request.query_params.get("user_id")
    service = request.query_params.get("service")
    action = request.query_params.get("action")
    limit = int(request.query_params.get("limit", 100))

    queryset = AuditLog.objects.all().order_by("-timestamp")

    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if service:
        queryset = queryset.filter(service=service)
    if action:
        queryset = queryset.filter(action=action)

    logs = queryset[:limit]

    return Response({
        "logs": [
            {
                "id": str(log.id),
                "timestamp": log.timestamp.isoformat(),
                "service": log.service,
                "action": log.action,
                "user_id": str(log.user_id) if log.user_id else None,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
            }
            for log in logs
        ]
    })


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "healthy", "service": "audit"})
