"""Django settings for Settlement Service."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure")
DEBUG = True
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["django.contrib.contenttypes", "rest_framework", "services.settlement"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "services.settlement.urls"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "orders_db"),
        "USER": os.getenv("POSTGRES_USER", "nexustrade"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "nexustrade_secret"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres-orders"),
        "PORT": "5432",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
