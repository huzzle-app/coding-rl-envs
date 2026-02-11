"""
OmniCloud Tenants Service Views
"""
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "tenants"})


def api_root(request):
    return JsonResponse({"service": "tenants", "version": "1.0.0"})
