"""
core/qr_registry_tasks.py — Async taskovi za QR Registry

- send_tamper_alert_task: WhatsApp + email kad se detektira tamper
- cleanup_scan_logs_task: Briše QRScanLog starije od 90 dana (Celery Beat)
"""

import logging

from celery import shared_task

logger = logging.getLogger("fenix.qr_registry")

OWNER_WHATSAPP = "+38598767677"  # Ivan — vlasnik


@shared_task(name="qr_registry.send_tamper_alert", max_retries=3, default_retry_delay=60)
def send_tamper_alert_task(qr_token_id: str) -> dict:
    """
    Šalje WhatsApp + email alert kad QR token ima > 5 geo-lokacija u 24h.
    Honeypot: netko skenira dokument s više lokacija → moguća kopija/zlouporabu.
    """
    from core.qr_registry_models import QRToken

    try:
        qr = QRToken.objects.get(id=qr_token_id)
    except QRToken.DoesNotExist:
        logger.error("send_tamper_alert: QRToken %s not found", qr_token_id)
        return {"error": "not_found"}

    unique_ips = list({e.get("ip", "") for e in (qr.geo_log or []) if e.get("ip")})
    msg = (
        f"⚠️ TAMPER ALERT — QR kod skeniran s {len(unique_ips)} lokacija u 24h!\n"
        f"Objekt: {qr.object_type} / {qr.label or qr.object_ref[:30]}\n"
        f"Token: {qr.short}\n"
        f"Provjeri: https://fina-connect.online/qr/{qr.token}/\n"
        f"Ukupno skenova: {qr.scan_count}"
    )

    # WhatsApp
    try:
        from core.whatsapp import send_whatsapp_message

        send_whatsapp_message(OWNER_WHATSAPP, msg)
        logger.info("Tamper alert WhatsApp sent for QR %s", qr.short)
    except Exception as e:
        logger.warning("WhatsApp tamper alert failed: %s", e)

    # Email (fallback)
    try:
        from django.conf import settings
        from django.core.mail import send_mail

        send_mail(
            subject=f"[FENIX] Tamper Alert — QR {qr.short}",
            message=msg,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@limit-connect.com"),
            recipient_list=["ivan@limit-connect.com"],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning("Email tamper alert failed: %s", e)

    QRToken.objects.filter(id=qr_token_id).update(tamper_alert_sent=True)
    return {"sent": True, "qr_short": qr.short, "ips": len(unique_ips)}


@shared_task(name="qr_registry.cleanup_scan_logs")
def cleanup_scan_logs_task() -> dict:
    """
    Celery Beat: briše QRScanLog starije od 90 dana.
    Konfiguracija u settings.py CELERY_BEAT_SCHEDULE.
    """
    from datetime import timedelta

    from django.utils import timezone

    from core.qr_registry_models import QRScanLog

    cutoff = timezone.now() - timedelta(days=90)
    deleted, _ = QRScanLog.objects.filter(scanned_at__lt=cutoff).delete()
    logger.info("QR cleanup: deleted %d scan logs older than 90 days", deleted)
    return {"deleted": deleted}
