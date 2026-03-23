"""
Invoicing Signals — auto-knjiženje faktura u Konto modul.

Trigger: Invoice status promjena na CONFIRMED/FISCALIZED/SENT/PAID
"""
import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Status lista koji triggeraju knjiženje
BOOKABLE_STATUSES = ('CONFIRMED', 'FISCALIZED', 'SENT', 'PAID')
# Doctype lista za knjiženje (ne knjižimo ponude/predračune)
BOOKABLE_DOCTYPES = ('R', 'A', 'S', 'GS', 'FA', 'URA', 'RN')


@receiver(pre_save, sender='invoicing.Invoice')
def track_status_change(sender, instance, **kwargs):
    """Track status changes to detect transition into bookable status."""
    instance._old_status = None
    if instance.pk:
        try:
            old = sender.objects.only('status').get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='invoicing.Invoice')
def auto_book_invoice(sender, instance, created, **kwargs):
    """Auto-book invoice when status changes to CONFIRMED/FISCALIZED/SENT/PAID."""
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    # Skip if status didn't change to a bookable status
    if new_status not in BOOKABLE_STATUSES:
        return
    # Skip if already in bookable status (no transition)
    if old_status in BOOKABLE_STATUSES:
        return
    # Skip non-bookable doctypes (ponude, predracuni)
    if instance.doctype not in BOOKABLE_DOCTYPES:
        return
    # Skip zero-amount invoices
    if not instance.total or instance.total <= 0:
        return

    try:
        from konto.services_file import book_invoice
        je = book_invoice(instance)
        if je:
            logger.info(
                'Auto-knjiženje: faktura %s → temeljnica %s',
                instance.number, je.entry_number,
            )
    except Exception:
        logger.warning(
            'Auto-knjiženje neuspješno za fakturu %s',
            instance.number, exc_info=True,
        )
