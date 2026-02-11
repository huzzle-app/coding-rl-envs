"""Admin service ASGI configuration."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.admin.settings')
from django.core.asgi import get_asgi_application
application = get_asgi_application()
