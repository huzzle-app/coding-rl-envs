"""
ASGI config for OmniCloud compliance service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.compliance.settings')
application = get_asgi_application()
