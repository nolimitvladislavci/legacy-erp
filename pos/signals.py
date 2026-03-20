"""
POS Signals — auto-generiranje dnevnog izvještaja na zatvaranju sesije.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from pos.models import POSSession, POSDailyReport


@receiver(post_save, sender=POSSession)
def generate_daily_report_on_close(sender, instance, **kwargs):
    """Kad se sesija zatvori, generiraj POSDailyReport."""
    if instance.status in ('closed', 'z_done') and instance.closed_at:
        try:
            POSDailyReport.generate_from_session(instance)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'POSDailyReport generiranje neuspješno za sesiju #%s',
                instance.pk, exc_info=True,
            )
