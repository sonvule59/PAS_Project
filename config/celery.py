from __future__ import absolute_import, unicode_literals
import os
import ssl
from celery import Celery
from celery.schedules import crontab
# Configure Celery Beat schedule
from django.conf import settings as django_settings

# Set the default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testpas.settings')

# Create Celery app instance
app = Celery('config')

# Using 'rpc://' (RPC backend) avoids Redis SSL conflicts
app.conf.result_backend = 'rpc://'
app.conf.task_ignore_result = True
app.conf.task_store_eager_result = False

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Load configuration from Django settings (e.g., CELERY_BROKER_URL)
# This will set broker_url and result_backend if they're in settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Force result backend to rpc:// after loading settings
# This prevents Celery from trying to use Redis as result backend
# rpc:// doesn't require Redis connection, avoiding SSL conflicts
# Must override settings.CELERY_RESULT_BACKEND = None to avoid SSL errors
app.conf.result_backend = 'rpc://'

# Get Redis URL from environment (Render uses REDIS_URL, fallback to CELERY_BROKER_URL)
# Priority: REDIS_URL env var > CELERY_BROKER_URL env var > settings.CELERY_BROKER_URL
redis_url = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL') or app.conf.broker_url

# Override with environment variable if it exists (Render uses REDIS_URL)
if redis_url:
    # Ensure Redis URL uses rediss:// if it's supposed to be SSL
    if not redis_url.startswith(('redis://', 'rediss://')):
        if '://' not in redis_url:
            redis_url = f'rediss://{redis_url}'
    
    # Set broker URL first
    app.conf.broker_url = redis_url
    
    # Configure SSL for Upstash - use proper SSL with certificate verification
    if redis_url.startswith('rediss://'):
        # Upstash requires SSL - use default Python SSL context (secure)
        # Remove the custom broker_transport_options that set CERT_NONE
        app.conf.broker_use_ssl = {
            'ssl_cert_reqs': ssl.CERT_REQUIRED,  # Changed from CERT_NONE
        }
    elif redis_url.startswith('redis://'):
        # For non-SSL Redis, explicitly clear any SSL settings
        app.conf.broker_use_ssl = None
        app.conf.broker_transport_options = {}
    
    # Keep result backend as rpc://
    app.conf.result_backend = 'rpc://'
    
    # Connection settings for better reliability with Upstash
    app.conf.broker_connection_retry = True
    app.conf.broker_connection_max_retries = 10
    app.conf.broker_connection_retry_on_startup = True
    app.conf.broker_heartbeat = 30  # Send keepalive every 30 seconds
    app.conf.broker_connection_timeout = 30
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1
    app.conf.worker_max_tasks_per_child = 100  # Restart worker after 100 tasks

# Auto-discover tasks in installed apps (e.g., testpas.tasks)
app.autodiscover_tasks()

# Close database connections after each task to prevent SSL connection issues
# This ensures each task gets a fresh database connection
@app.task(bind=True)
def close_db_connections(self):
    """Signal handler to close database connections after each task"""
    from django.db import connections
    for conn in connections.all():
        conn.close()

# Register signal to close DB connections after each task
from celery.signals import task_postrun

@task_postrun.connect
def close_db_connections_handler(sender=None, **kwargs):
    """Close database connections after each Celery task completes"""
    from django.db import connections
    for conn in connections.all():
        try:
            conn.close()
        except Exception:
            pass  # Ignore errors when closing connections

# Check if TIME_COMPRESSION is enabled (for testing)
# Set TIME_COMPRESSION = True in testpas/settings.py for testing
# Set TIME_COMPRESSION = False in testpas/settings.py for production
TIME_COMPRESSION = getattr(django_settings, 'TIME_COMPRESSION', True)
if TIME_COMPRESSION:
    schedule_seconds = 30.0
    app.conf.beat_schedule = {
        'run-daily-timeline-checks': {
            'task': 'testpas.tasks.run_daily_timeline_checks',
            'schedule': schedule_seconds,
        },
    }
else:
    # For deployment: run daily at 7:00 AM Central Time
    app.conf.update(
        timezone='US/Central',
        enable_utc=True,
    )
    app.conf.beat_schedule = {
        'run-daily-timeline-checks': {
            'task': 'testpas.tasks.run_daily_timeline_checks',
            'schedule': crontab(hour=7, minute=0)
        },
    }