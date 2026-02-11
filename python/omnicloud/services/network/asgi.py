"""
ASGI config for OmniCloud network service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.network.settings')
application = get_asgi_application()
