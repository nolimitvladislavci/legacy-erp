"""
DeepSeek Code Patrol — Celery task.
Pokreće se noćno putem Celery Beat (02:00 svaki dan).
Skenira sve appove asinkrono, ne blokira main worker.
"""

import logging

from celery import shared_task

logger = logging.getLogger("deepseek_patrol")


@shared_task(
    bind=True,
    soft_time_limit=3600,  # 1h max
    max_retries=0,  # ne ponavljaj — svaka noć je nova
    name="core.tasks_patrol.run_code_patrol",
)
def run_code_patrol(self, app_label: str = None, min_priority: int = 3, force: bool = False):
    """
    Noćni DeepSeek Code Patrol.

    Args:
        app_label: Skenira samo ovaj app (None = svi)
        min_priority: Max broj prioriteta koji se zapisuje (1=samo kritično, 3=srednje+)
        force: Pokreni čak i ako je danas već pokrenuto
    """
    from io import StringIO
    from django.core.management import call_command

    logger.info("Code Patrol task pokrenut (app=%s, min_priority=%s)", app_label, min_priority)

    buf = StringIO()
    kwargs = {
        "min_priority": min_priority,
        "force": force,
        "stdout": buf,
        "stderr": buf,
    }
    if app_label:
        kwargs["app"] = app_label

    try:
        call_command("deepseek_patrol", **kwargs)
        output = buf.getvalue()
        logger.info("Code Patrol završen:\n%s", output[-1000:])
        return {"status": "ok", "output": output[-500:]}
    except Exception as exc:
        logger.error("Code Patrol greška: %s", exc)
        return {"status": "error", "error": str(exc)[:300]}


@shared_task(name="core.tasks_patrol.patrol_single_app")
def patrol_single_app(app_label: str, min_priority: int = 2):
    """Skenira jedan app — za ad-hoc ili po deployment hooku."""
    return run_code_patrol.apply(
        args=[], kwargs={"app_label": app_label, "min_priority": min_priority, "force": True}
    ).get()
