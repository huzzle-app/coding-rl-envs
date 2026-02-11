"""
ASGI config for OmniCloud auth service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.auth.settings')
application = get_asgi_application()
