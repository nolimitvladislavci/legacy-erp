"""
BORG SLA Engine — Celery tasks za detekciju SLA kršenja.

check_sla: svakih 10 min provjerava kartice koje predugo stoje u statusu.
archive_old_activity: mjesečno broji stare zapise (arhiva u v2).
"""
import logging
from celery import shared_task
from borg_ops.business_hours import sla_breached, is_business_hour
from django.utils import timezone

logger = logging.getLogger('borg.sla')

SLA_RULES = {
    'work_orders.WorkOrder': {
        'in_progress': 480,     # 8h
    },
    'burza.ProjectLead': {
        'NOVI_UPIT':        1440,   # 24h
        'INTERNA_PROCJENA': 4320,   # 72h
        'NA_BURZI':         10080,  # 7 dana
    },
    'interventions.HitnaIntervencija': {
        'NOVO':        15,    # 15 min
        'DODIJELJENO': 30,    # 30 min
        'NA_PUTU':     60,    # 1h
    },
}


@shared_task(name='borg_ops.check_sla')
def check_sla():
    """Celery beat: svakih 10 min — SLA breach detekcija."""
    from borg_ops.models import StatusTimestamp
    from django.contrib.contenttypes.models import ContentType
    from django.apps import apps

    now = timezone.now()
    breaches = []

    for model_path, rules in SLA_RULES.items():
        app_label, model_name = model_path.split('.')
        try:
            Model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        ct = ContentType.objects.get_for_model(Model)

        for status, max_minutes in rules.items():
            # Dron #2 fix: ne alarmiramo van radnog vremena (vikend/praznik)
            if not is_business_hour():
                continue

            cutoff = now - timezone.timedelta(minutes=max_minutes)
            candidates = StatusTimestamp.objects.filter(
                content_type=ct,
                status=status,
                exited_at__isnull=True,
                entered_at__lt=cutoff,
            ).select_related('user')

            for ts in candidates:
                # Računaj RADNE minute — ne ukupno proteklo vrijeme
                breached, elapsed = sla_breached(ts.entered_at, max_minutes)
                if not breached:
                    continue   # Ukupno radno vrijeme još nije premašeno

                logger.warning(
                    'SLA BREACH: %s #%s u statusu %s — %d radnih min (max %d)',
                    model_name, ts.object_id, status, elapsed, max_minutes
                )
                breaches.append({
                    'model': model_name,
                    'pk': ts.object_id,
                    'status': status,
                    'minutes': elapsed,
                    'max': max_minutes,
                })

    if breaches:
        logger.warning('SLA check: %d breach(es) detected', len(breaches))

    return {
        'checked_at': now.isoformat(),
        'breaches': len(breaches),
        'details': breaches[:20],
    }


@shared_task(name='borg_ops.archive_old_activity')
def archive_old_activity():
    """Mjesecno: broji aktivnosti starije od 90 dana (arhiva u v2)."""
    from borg_ops.models import CardActivity
    cutoff = timezone.now() - timezone.timedelta(days=90)
    count = CardActivity.objects.filter(created_at__lt=cutoff).count()
    logger.info('CardActivity: %d zapisa starijih od 90 dana', count)
    return {'old_records': count}
