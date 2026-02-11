"""
ASGI config for OmniCloud config service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.config.settings')
application = get_asgi_application()
