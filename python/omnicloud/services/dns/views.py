"""
OmniCloud DNS Service Views
"""
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "dns"})


def api_root(request):
    return JsonResponse({"service": "dns", "version": "1.0.0"})
