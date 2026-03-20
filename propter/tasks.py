"""Propter Celery taskovi."""
from celery import shared_task
import logging

logger = logging.getLogger("propter.tasks")


@shared_task(bind=True, max_retries=3, default_retry_delay=300,
             name="propter.tasks.auto_close_billing_periods")
def auto_close_billing_periods(self):
    """Zatvori OPEN periode prethodnog mj. i kreiraj zbirne racune.
    Celery beat: 1. u mj. u 06:00.
    """
    try:
        from propter.services.aggregate import auto_close_previous
        results = auto_close_previous()
        ok  = [r for r in results if r.get("status") == "OK"]
        err = [r for r in results if r.get("status") == "ERROR"]
        logger.info("auto_close: %d OK, %d ERROR", len(ok), len(err))
        return {"ok": len(ok), "errors": len(err), "results": results}
    except Exception as exc:
        logger.error("auto_close_billing_periods: %s", exc)
        raise self.retry(exc=exc)


@shared_task(name="propter.tasks.send_zbirni_eracun")
def send_zbirni_eracun(billing_period_id, user_pk=None):
    """Posalji zbirni e-Racun na FINA CIS async."""
    try:
        from propter.models import BillingPeriod
        from eracun.models import ERacun
        from eracun.services.engine import process_eracun

        period = BillingPeriod.objects.get(pk=billing_period_id)
        if not period.zbirni_eracun_id:
            return {"success": False, "message": "Period nema zbirni e-Racun"}

        eracun = ERacun.objects.get(pk=period.zbirni_eracun_id)
        user = None
        if user_pk:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.filter(pk=user_pk).first()

        success, message = process_eracun(eracun, user=user)
        return {"success": success, "message": message,
                "eracun": eracun.invoice_number}
    except Exception as exc:
        logger.error("send_zbirni_eracun: %s", exc)
        return {"success": False, "message": str(exc)}


@shared_task(name="propter.tasks.recalculate_eko_stats")
def recalculate_eko_stats(billing_period_id):
    """Recalculate EkoStats za period (npr. nakon korekcije otpremnica)."""
    try:
        from propter.models import BillingPeriod, EkoStats
        period = BillingPeriod.objects.get(pk=billing_period_id)
        eko = EkoStats.calculate(period)
        return {"badge": eko.badge_level, "co2_saved": float(eko.co2_saved_grams)}
    except Exception as exc:
        logger.error("recalculate_eko_stats: %s", exc)
        return {"error": str(exc)}
