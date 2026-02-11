"""
ASGI config for OmniCloud dns service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.dns.settings')
application = get_asgi_application()
