"""
Fenix v3 — Celery konfiguracija | PLAN_009
3 queue: default, heavy (OCR/AI), scheduled (Beat)
"""
from __future__ import annotations
import logging
from celery import Celery
from celery.signals import task_failure

logger = logging.getLogger("fenix")

app = Celery("fenix_v3")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscovery — OBAVEZNO (stari bug: zaboravljeni autodiscovery)
app.autodiscover_tasks()

# 3 queue-a
app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "heavy":   {"exchange": "heavy",   "routing_key": "heavy"},
    "scheduled": {"exchange": "scheduled", "routing_key": "scheduled"},
}
app.conf.task_default_queue = "default"
app.conf.task_routes = {
    "arhiva.tasks.*":    {"queue": "heavy"},
    "invoicing.tasks.*": {"queue": "heavy"},
    "core.tasks.deepseek_code_patrol": {"queue": "scheduled"},
}
app.conf.worker_prefetch_multiplier = 1  # fair dispatch za heavy taskove


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    logger.error("Task %s [%s] failed: %s", sender.name, task_id, exception, exc_info=True)
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exception)
    except Exception:
        pass


# Beat Schedule
from celery.schedules import crontab

app.conf.beat_schedule = {
    'pos-anomaly-6h': {
        'task': 'pos.tasks.run_anomaly_detection',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'scheduled'},
    },
    'pos-benchmark-nightly': {
        'task': 'pos.tasks.run_pos_benchmark',
        'schedule': crontab(minute=30, hour=2),
        'options': {'queue': 'scheduled'},
    },
    'deepseek-code-patrol-nightly': {
        'task': 'core.tasks.deepseek_code_patrol',
        'schedule': crontab(minute=0, hour=2),   # 02:00 svake noci
        'options': {'queue': 'scheduled'},
    },
}
