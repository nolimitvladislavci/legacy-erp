"""
BORG Signal Celery tasks — autonomni triage i patrol.

Radi sam dok je Ivan na baušteli:
1. triage_new_signal — okida se odmah kad signal stigne
2. signal_patrol — svakih 30 min provjerava netriažirane
3. daily_signal_digest — jutarnji sažetak za tim
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("borg.signal.tasks")


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def triage_new_signal(self, signal_id):
    """Odmah triažiraj novi signal kroz Haiku."""
    from limit_connect_ai.models_signal import FenixSignal
    from limit_connect_ai.signal_triage import triage_signal, apply_triage

    try:
        signal = FenixSignal.objects.get(id=signal_id)
    except FenixSignal.DoesNotExist:
        return {"error": "Signal not found"}

    if signal.status != "new":
        return {"status": "already_triaged"}

    result = triage_signal(signal)
    if result:
        apply_triage(signal, result)
        return {
            "signal_id": str(signal.id),
            "classification": result.get("classification"),
            "priority": result.get("priority"),
            "assigned_to": result.get("assign_to"),
        }
    else:
        # Retry ako Haiku nije odgovorio
        if self.request.retries < self.max_retries:
            raise self.retry()
        return {"error": "triage_failed"}


@shared_task
def signal_patrol():
    """Svakih 30 min — triažiraj sve NEW signale koji su promakli."""
    from limit_connect_ai.models_signal import FenixSignal

    untriaged = FenixSignal.objects.filter(status="new").order_by("created_at")[:20]
    count = 0
    for signal in untriaged:
        triage_new_signal.delay(str(signal.id))
        count += 1

    if count:
        logger.info("Signal patrol: dispatched %d untriaged signals", count)
    return {"dispatched": count}


@shared_task
def daily_signal_digest():
    """
    Jutarnji digest — sažetak signala za proteklih 24h.
    Sprema se kao FenixSignal tipa 'system' za audit trail.
    """
    from limit_connect_ai.models_signal import FenixSignal
    from django.db.models import Count

    since = timezone.now() - timezone.timedelta(hours=24)
    signals = FenixSignal.objects.filter(created_at__gte=since)

    total = signals.count()
    if total == 0:
        return {"total": 0, "message": "Nema signala u zadnjih 24h"}

    by_type = dict(signals.values_list("signal_type").annotate(c=Count("id")).values_list("signal_type", "c"))
    by_status = dict(signals.values_list("status").annotate(c=Count("id")).values_list("status", "c"))
    by_priority = dict(signals.values_list("priority").annotate(c=Count("id")).values_list("priority", "c"))

    critical = signals.filter(priority__lte=2).count()

    digest = {
        "period": "24h",
        "total": total,
        "by_type": by_type,
        "by_status": by_status,
        "by_priority": by_priority,
        "critical_count": critical,
        "top_pages": list(
            signals.exclude(page_url="")
            .values_list("page_url")
            .annotate(c=Count("id"))
            .order_by("-c")[:5]
        ),
    }

    logger.info("Signal digest: %d signals (P1-P2: %d)", total, critical)
    return digest
