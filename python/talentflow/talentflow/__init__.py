# TalentFlow - Talent Management SaaS Platform
# This module initializes the Celery app for Django

from .celery import app as celery_app

__all__ = ('celery_app',)
__version__ = '1.0.0'
