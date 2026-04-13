"""
Delivery Celery Tasks — Cold Chain patrol + HACCP notifications.

Registriraj u celery-beat:
  scan_active_boxes      — every 5 min
  cleanup_old_readings   — daily 03:00
"""
import logging
from celery import shared_task
from datetime import timedelta
from django.utils import timezone as tz

logger = logging.getLogger('cold_chain_patrol')


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def scan_active_boxes(self):
    """
    Svakih 5 min: traži SmartBoxeve u tranzitu čiji senzori šute > 15 min.
    Podiže HACCPIncident za signal_lost i blokira box.
    """
    from delivery.models import SmartBox, HACCPIncident

    timeout = tz.now() - timedelta(minutes=15)

    # Boxevi koji su aktivni (in_use), imaju senzor, i zadnje očitanje starije od 15 min
    silent_boxes = SmartBox.objects.filter(
        status='in_use',
        has_sensor=True,
        last_reading_at__lt=timeout,
        haccp_status__in=['ok', 'warning'],  # ne diraj već blokirane
    ).select_related('current_delivery', 'owner_company')

    created_count = 0
    for box in silent_boxes:
        # Provjeri da ne dupliciramo incident za isti box
        existing = HACCPIncident.objects.filter(
            smart_box=box,
            incident_type='offline_retroactive',
            is_resolved=False,
        ).exists()

        if existing:
            continue

        incident = HACCPIncident.objects.create(
            incident_type='offline_retroactive',
            severity='critical',
            smart_box=box,
            consolidated_delivery=box.current_delivery,
            breach_start=box.last_reading_at or tz.now(),
            max_temperature=box.last_temp or 0,
            duration_minutes=int((tz.now() - (box.last_reading_at or tz.now())).total_seconds() / 60),
            description=(
                'SIGNAL LOST: Senzor %s offline > 15 min. '
                'Zadnje očitanje: %s (%s°C). Stanje robe nepoznato.'
            ) % (
                box.sensor_device_id or box.box_id,
                box.last_reading_at.strftime('%H:%M') if box.last_reading_at else '?',
                box.last_temp or '?',
            ),
            reading_ids=[],
        )

        # Blokiraj box
        box.haccp_status = 'blocked'
        box.haccp_blocked_at = tz.now()
        box.save(update_fields=['haccp_status', 'haccp_blocked_at'])

        created_count += 1
        logger.error(
            '[HACCP PATROL] Signal lost: SmartBox %s offline %d min — incident #%d',
            box.box_id,
            int((tz.now() - (box.last_reading_at or tz.now())).total_seconds() / 60),
            incident.pk,
        )

        # Push notifikacija vozaču/dispatcheru
        notify_haccp_incident.delay(incident.pk)

    if created_count:
        logger.info('[HACCP PATROL] Scan complete: %d new incidents', created_count)

    return {'scanned': silent_boxes.count(), 'incidents_created': created_count}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def notify_haccp_incident(self, incident_id):
    """
    Šalje Web Push notifikaciju vozaču i hub adminu za HACCP incident.
    Koristi postojeći push_notifications.push.send_push_to_user().
    """
    from delivery.models import HACCPIncident
    from push_notifications.push import send_push_to_user

    try:
        incident = HACCPIncident.objects.select_related(
            'smart_box__owner_company',
            'consolidated_delivery__driver',
        ).get(pk=incident_id)
    except HACCPIncident.DoesNotExist:
        return

    title = 'HACCP UZBUNA!'
    body = incident.description[:200]
    url = '/delivery/incidents/'

    notified = []

    # 1. Notificiraj vozača (driver na ConsolidatedDelivery)
    delivery = incident.consolidated_delivery
    if delivery and hasattr(delivery, 'driver') and delivery.driver:
        ok = send_push_to_user(delivery.driver, title, body, url=url)
        if ok:
            notified.append('driver:%s' % delivery.driver.pk)

    # 2. Notificiraj admina hub kompanije
    if delivery and hasattr(delivery, 'hub_company') and delivery.hub_company:
        from accounts.models import UserProfile
        admins = UserProfile.objects.filter(
            company=delivery.hub_company,
            role__in=['company_admin', 'manager'],
            push_subscription__gt='',
        ).select_related('user')[:3]

        for profile in admins:
            ok = send_push_to_user(profile.user, title, body, url=url)
            if ok:
                notified.append('admin:%s' % profile.user.pk)

    # 3. Fallback: in-app notifikacija
    try:
        from notifications.services import notify
        if delivery and delivery.driver:
            notify(
                recipient=delivery.driver,
                notification_type='haccp',
                title=title,
                message=body,
                url=url,
            )
    except ImportError:
        pass  # Ne blokira ako notifikacije ne rade

    logger.info('[HACCP] Incident #%d notified: %s', incident_id, ', '.join(notified) or 'nobody')
    return {'incident_id': incident_id, 'notified': notified}


@shared_task
def cleanup_old_readings():
    """
    Dnevno: briši SensorReading starije od 90 dana.
    Zadržava samo reading_ids referenciran u HACCPIncident.
    """
    from delivery.models import SensorReading, HACCPIncident
    from django.db.models import Q

    cutoff = tz.now() - timedelta(days=90)

    # Sakupi ID-eve koji su referencirani u incidentima
    protected_ids = set()
    for inc in HACCPIncident.objects.filter(reading_ids__len__gt=0).values_list('reading_ids', flat=True):
        if isinstance(inc, list):
            protected_ids.update(inc)

    deleted, _ = (
        SensorReading.objects
        .filter(timestamp__lt=cutoff)
        .exclude(pk__in=protected_ids)
        .delete()
    )

    logger.info('[COLD CHAIN] Cleanup: deleted %d readings older than 90 days', deleted)
    return {'deleted': deleted}
