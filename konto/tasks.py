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



# ══════════════════════════════════════════════════════════════════════════════
# SAF-T HR Export — OECD Standard Audit File for Tax
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, soft_time_limit=300)
def generate_saft_export(self, company_id, period_from_str, period_to_str):
    """
    Async generacija SAF-T XML za firmu i period.
    period_from_str/period_to_str: 'YYYY-MM-DD'
    """
    import os
    from datetime import date
    from companies.models import Company
    from konto.saft_generator import SAFTGenerator

    logger = logging.getLogger('konto.saft')

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}

    period_from = date.fromisoformat(period_from_str)
    period_to = date.fromisoformat(period_to_str)

    logger.info('SAF-T export starting for %s (%s to %s)', company.name, period_from, period_to)

    try:
        gen = SAFTGenerator(company, period_from, period_to)
        xml = gen.generate()

        # Save to file
        export_dir = '/var/www/fina-connect/exports/saft'
        os.makedirs(export_dir, exist_ok=True)
        filename = f'SAFT_{company.oib}_{period_from}_{period_to}.xml'
        filepath = os.path.join(export_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml)

        file_size = os.path.getsize(filepath) / 1024

        # BorgAuditEntry
        try:
            from borg_ops.audit_helpers import log_borg_audit
            log_borg_audit(
                company=company,
                entry_type='EXPORT',
                summary=f'SAF-T HR export: {period_from} do {period_to} ({file_size:.0f} KB)',
                metadata={'file': filename, 'size_kb': file_size},
            )
        except Exception:
            pass

        logger.info('SAF-T export completed: %s (%.0f KB)', filename, file_size)
        return {'status': 'completed', 'file': filepath, 'size_kb': file_size}

    except Exception as e:
        logger.error('SAF-T export failed for %s: %s', company.name, e)
        return {'status': 'failed', 'error': str(e)}
