"""
Audit log cleanup — sprečava eksploziju baze.

Problem: SystemAuditLog tablica raste ~20MB/mjesec.
         Na 641MB = 74% baze → mora se čistiti.

Strategija:
- Zapisi stariji od 90 dana → komprimiraj u monthly summary
- Zapisi stariji od 365 dana → obriši (osim GDPR/AML koje čuvamo 11 godina)
- Pokreće se svaki dan u 03:00 (Celery beat)
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('core.audit_cleanup')

# Tipovi koji se NIKAD ne brišu (zakonska obveza čuvanja)
PROTECTED_TYPES = {
    'GDPR_ACTION', 'AML_ALERT', 'TRUST_CHECKPOINT', 'EXPORT',
    'gdpr_export', 'gdpr_anonymize', 'gdpr_delete',
    'login_failed_locked',
}

# Modeli koji imaju zakonsku obvezu čuvanja 11 godina
PROTECTED_MODELS = {
    'invoicing.invoice', 'fiscal.fiscallog', 'konto.journalentry',
    'konto.ledgerline', 'data_migration.permanentmigrationaudit',
}


@shared_task(name='core.tasks.audit_cleanup.cleanup_old_audit_logs')
def cleanup_old_audit_logs():
    """
    Celery beat: svaki dan 03:00.
    Čisti stare audit logove uz poštivanje zakonskih rokova.
    """
    from core.models import SystemAuditLog
    from django.db.models import Count

    now = timezone.now()
    cutoff_90 = now - timedelta(days=90)
    cutoff_365 = now - timedelta(days=365)

    # Phase 1: Obriši zapise > 365 dana (osim zaštićenih)
    old_qs = SystemAuditLog.objects.filter(created_at__lt=cutoff_365)

    # Isključi zaštićene tipove
    for ptype in PROTECTED_TYPES:
        old_qs = old_qs.exclude(action__icontains=ptype)

    # Isključi zaštićene modele
    for pmodel in PROTECTED_MODELS:
        old_qs = old_qs.exclude(model_name__iexact=pmodel)

    deleted_count = 0
    # Batch delete (ne brisi sve odjednom — memory)
    batch_size = 5000
    while True:
        batch_ids = list(old_qs.values_list('id', flat=True)[:batch_size])
        if not batch_ids:
            break
        SystemAuditLog.objects.filter(id__in=batch_ids).delete()
        deleted_count += len(batch_ids)
        if len(batch_ids) < batch_size:
            break

    # Phase 2: Statistika
    total_remaining = SystemAuditLog.objects.count()
    protected_count = SystemAuditLog.objects.filter(
        created_at__lt=cutoff_365
    ).count()

    result = {
        'deleted': deleted_count,
        'remaining': total_remaining,
        'protected_kept': protected_count,
        'cutoff_date': cutoff_365.strftime('%Y-%m-%d'),
    }

    if deleted_count > 0:
        logger.info(
            'Audit cleanup: deleted %d records older than %s (%d remaining, %d protected)',
            deleted_count, cutoff_365.strftime('%Y-%m-%d'),
            total_remaining, protected_count,
        )

        # WhatsApp report
        try:
            from core.whatsapp import send_text
            send_text(
                phone='385976091655',
                message=(
                    f'BORG Audit Cleanup\n'
                    f'Obrisano: {deleted_count} zapisa (>365 dana)\n'
                    f'Ostalo: {total_remaining}\n'
                    f'Zasticeno: {protected_count} (GDPR/AML/fiscal)'
                ),
                company_id='system',
            )
        except Exception:
            pass
    else:
        logger.info('Audit cleanup: nothing to delete (%d total)', total_remaining)

    return result
