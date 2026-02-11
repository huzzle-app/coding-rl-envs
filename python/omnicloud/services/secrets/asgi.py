"""
ASGI config for OmniCloud secrets service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.secrets.settings')
application = get_asgi_application()
