"""
TalentFlow Celery Configuration

Celery setup for async task processing.
"""
import os

from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talentflow.settings.development')

app = Celery('talentflow')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Override timezone settings
app.conf.update(
    timezone='UTC',
    enable_utc=True,
)

# Load task modules from all registered Django apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    'cleanup-expired-tokens': {
        'task': 'apps.accounts.tasks.cleanup_expired_tokens',
        'schedule': 3600.0,  # Every hour
    },
    'update-candidate-scores': {
        'task': 'apps.candidates.tasks.update_candidate_scores',
        'schedule': 300.0,  # Every 5 minutes
    },
    'process-scheduled-interviews': {
        'task': 'apps.interviews.tasks.process_scheduled_interviews',
        'schedule': 60.0,  # Every minute
    },
    'generate-analytics-reports': {
        'task': 'apps.analytics.tasks.generate_daily_report',
        'schedule': 86400.0,  # Daily
    },
}

# Task routing
app.conf.task_routes = {
    'apps.accounts.*': {'queue': 'auth'},
    'apps.candidates.*': {'queue': 'candidates'},
    'apps.jobs.*': {'queue': 'jobs'},
    'apps.interviews.*': {'queue': 'interviews'},
    'apps.analytics.*': {'queue': 'analytics'},
}

# Task result settings
app.conf.task_track_started = True
app.conf.task_time_limit = 300  # 5 minutes
app.conf.task_soft_time_limit = 240  # 4 minutes

# Worker settings
app.conf.worker_prefetch_multiplier = 4
app.conf.worker_concurrency = 4


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f'Request: {self.request!r}')
