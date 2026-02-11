"""
ASGI config for OmniCloud billing service.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.billing.settings')
application = get_asgi_application()
