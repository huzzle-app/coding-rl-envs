"""
Django settings for Orders Service.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-secret-key-change-in-production")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "services.orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "services.orders.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "orders_db"),
        "USER": os.getenv("POSTGRES_USER", "nexustrade"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "nexustrade_secret"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres-orders"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        
        "CONN_MAX_AGE": 600,  # Keep connections alive
        "OPTIONS": {
            
        },
    }
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/3")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
