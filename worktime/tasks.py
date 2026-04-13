import logging
from celery import shared_task
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('worktime')


@shared_task(bind=True, soft_time_limit=300)
def worktime_anomaly_patrol(self):
    """
    Nocni AI patrol -- analizira TimeLog-ove bez aktivnosti.
    Pokrece se svake noci u 02:30.
    """
    import os
    from worktime.models import TimeLog, ActivityEvent, AnomalyReport
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    yesterday = now - timedelta(days=1)
    alerts = []

    # 1. Ghost shift -- smjena otvorena >12h bez POS akcije
    ghost_shifts = TimeLog.objects.filter(
        status='OPEN',
        start_time__lte=now - timedelta(hours=12),
    ).select_related('user', 'company')

    for ts in ghost_shifts:
        activity_count = ActivityEvent.objects.filter(
            user=ts.user,
            timestamp__gte=ts.start_time,
            action__startswith='POS_',
        ).count()
        if activity_count == 0:
            alerts.append({
                'type': 'GHOST_SHIFT',
                'severity': 'high',
                'user': ts.user.username,
                'company': str(ts.company) if ts.company else '',
                'detail': 'Smjena otvorena %s bez POS aktivnosti' % ts.start_time.strftime('%H:%M'),
                'time_log_id': ts.pk,
                'user_id': ts.user_id,
                'company_id': ts.company_id,
            })

    # 2. Nedostajuca pauza -- >6h rada bez evidentirane pauze
    long_shifts = TimeLog.objects.filter(
        status='CLOSED',
        date=yesterday.date(),
        gross_hours__gte=6,
        break_minutes=0,
    ).select_related('user', 'company')

    for ts in long_shifts:
        alerts.append({
            'type': 'MISSING_BREAK',
            'severity': 'medium',
            'user': ts.user.username,
            'company': str(ts.company) if ts.company else '',
            'detail': '%.1fh rada bez evidentirane pauze (ArbZG/ZOR)' % float(ts.gross_hours),
            'time_log_id': ts.pk,
            'user_id': ts.user_id,
            'company_id': ts.company_id,
        })

    if not alerts:
        return {'alerts': 0}

    # 3. AI analiza
    ai_summary = 'AI analiza nedostupna'
    try:
        import anthropic
        import json
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=400,
                messages=[{
                    'role': 'user',
                    'content': (
                        'Analiziraj ove anomalije u evidenciji radnog vremena. '
                        'Odgovori na hrvatskom, 2-3 recenice, navedi sto je hitno:\n\n'
                        + json.dumps(alerts, ensure_ascii=False, default=str)
                    ),
                }]
            )
            ai_summary = response.content[0].text
    except (TypeError, ValueError) as ai_err:
        logger.warning('AI patrol failed: %s', ai_err)

    # 4. Spremi AnomalyReport zapise
    created = 0
    for alert in alerts:
        try:
            AnomalyReport.objects.create(
                time_log_id=alert.get('time_log_id'),
                user_id=alert['user_id'],
                company_id=alert.get('company_id'),
                anomaly_type=alert['type'],
                severity=alert['severity'],
                description=alert['detail'] + '\n\nAI: ' + ai_summary,
                ai_confidence=75,
            )
            created += 1
        except (IntegrityError, DatabaseError) as db_err:
            logger.warning('AnomalyReport create failed: %s', db_err)

    # 5. Notifikacija superadminima
    try:
        from notifications.services import notify
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for admin in User.objects.filter(is_superuser=True, is_active=True):
            notify(
                recipient=admin,
                notification_type='system',
                title='Worktime Patrol -- %d anomalija' % len(alerts),
                message=ai_summary,
                url='/worktime/',
            )
    except DatabaseError as notif_err:
        logger.warning('Patrol notify failed: %s', notif_err)

    return {'alerts': len(alerts), 'created': created}


# ═══════════════════════════════════════════════════════════════
# Data Vault — GDPR + ZOR kompromis
# Svake noći: ako radnik terminiran > 30 dana, skrij IBAN iz UI-a
# IBAN ostaje u bazi (bank_account) — ZOR zahtijeva čuvanje 6 god
# ═══════════════════════════════════════════════════════════════

@shared_task(name='worktime.tasks.iban_vault_check')
def iban_vault_check():
    """Nightly: archive IBAN for terminated employees after 30 days."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import EmployeeProfile

    cutoff = timezone.now().date() - timedelta(days=30)
    to_vault = EmployeeProfile.objects.filter(
        is_terminated=True,
        iban_archived=False,
        terminated_at__lte=cutoff,
        bank_account__gt='',
    )
    count = to_vault.update(iban_archived=True, iban_archived_at=timezone.now())
    logger.info('Data Vault: %d IBAN(s) archived', count)
    return {'archived': count}
