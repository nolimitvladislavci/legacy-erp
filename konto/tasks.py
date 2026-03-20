"""
konto/tasks.py
Celery tasks for async bookkeeping operations.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def ai_bookkeeper_process(self, archive_entry_id, auto_commit=False):
    """
    Async AI bookkeeper: analyse ArhivaEntry and propose/execute booking.

    Called from post_save signal on ArhivaEntry (auto_commit=False by default,
    so everything goes to human review initially).
    """
    try:
        from konto.ai_bookkeeper import process_archive_entry
        return process_archive_entry(archive_entry_id, auto_commit=auto_commit)
    except Exception as exc:
        logger.error(
            "ai_bookkeeper_process failed for ArhivaEntry {}: {}".format(
                archive_entry_id, exc
            )
        )
        raise self.retry(exc=exc)


# Re-export monthly_vat_calculation so Celery beat can find it via konto.tasks
from konto.tasks_vat import monthly_vat_calculation  # noqa: F401
