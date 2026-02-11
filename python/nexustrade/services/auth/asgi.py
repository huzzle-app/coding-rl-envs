"""
ASGI config for Auth service.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "services.auth.settings")
django.setup()

from django.core.asgi import get_asgi_application

application = get_asgi_application()
