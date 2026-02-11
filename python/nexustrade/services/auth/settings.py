"""
Django settings for Auth Service.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-secret-key-change-in-production")


# Should check DEBUG env var, but defaults override it
DEBUG = True  
if os.getenv("ENVIRONMENT") == "production":
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"  

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "services.auth",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "services.auth.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "users_db"),
        "USER": os.getenv("POSTGRES_USER", "nexustrade"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "nexustrade_secret"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres-users"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        
        "CONN_MAX_AGE": 0,  # No connection reuse
    }
}

# JWT Settings
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_key_that_should_be_rotated")
JWT_ALGORITHM = "HS256"

JWT_ACCESS_TOKEN_LIFETIME = 60  # 1 minute - way too short
JWT_REFRESH_TOKEN_LIFETIME = 3600 * 24 * 7  # 7 days

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
