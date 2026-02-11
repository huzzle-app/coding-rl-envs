"""Django settings for Registry service."""
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'insecure-default-key')
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.auth']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'models_db'),
        'USER': os.environ.get('DB_USER', 'synapsenet'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'synapsenet_secret'),
        'HOST': os.environ.get('DB_HOST', 'postgres-models'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
ROOT_URLCONF = 'services.registry.urls'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
