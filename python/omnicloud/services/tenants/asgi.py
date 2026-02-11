"""
ASGI config for OmniCloud tenants service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.tenants.settings')
application = get_asgi_application()
