"""
konto/signals.py
Automatic booking when BankTransaction gets matched to an invoice.
"""
import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='konto.BankTransaction')
def auto_book_on_match(sender, instance, **kwargs):
    """
    Detects status transition to 'matched' and triggers auto-booking.

    Uses pre_save to compare old vs new status:
    - Old status != 'matched' AND new status == 'matched' → book
    - Already booked (is_booked=True) → skip
    - No matched_invoice → skip
    """
    if instance.is_booked:
        return

    if instance.status != 'matched':
        return

    if not instance.matched_invoice_id:
        return

    # Check if this is a status CHANGE (not just a save of already-matched)
    if instance.pk:
        try:
            old = sender.objects.only('status', 'is_booked').get(pk=instance.pk)
            if old.status == 'matched' and old.is_booked:
                return  # Already matched and booked
            if old.status == 'matched':
                return  # Status didn't change
        except sender.DoesNotExist:
            pass  # New object — proceed

    # Defer booking to post_save to ensure the transaction is committed
    # We set a flag that post_save will pick up
    instance._needs_booking = True


@receiver(pre_save, sender='konto.BankTransaction')
def _clear_booking_flag(sender, instance, **kwargs):
    """Ensure _needs_booking is initialized."""
    if not hasattr(instance, '_needs_booking'):
        instance._needs_booking = False


from django.db.models.signals import post_save

@receiver(post_save, sender='konto.BankTransaction')
def _execute_booking(sender, instance, **kwargs):
    """Execute booking after save if flagged by pre_save."""
    if getattr(instance, '_needs_booking', False):
        instance._needs_booking = False
        from konto.booking_engine import book_bank_transaction
        book_bank_transaction(instance)


# -----------------------------------------------
# AI Bookkeeper: auto-propose booking for new ArhivaEntry
# -----------------------------------------------

@receiver(post_save, sender='documents.ArhivaEntry')
def trigger_ai_bookkeeper(sender, instance, created, **kwargs):
    """
    When a new ArhivaEntry is created, queue AI bookkeeper analysis.
    auto_commit=False so everything goes to human review first.
    """
    if not created:
        return

    # Skip zero-amount entries
    if not instance.amount or instance.amount <= 0:
        return

    # Only process bookable source types
    bookable_types = ('invoice_in', 'invoice_out', 'eracun', 'primka', 'otpremnica')
    if instance.source_type not in bookable_types:
        return

    try:
        from konto.tasks import ai_bookkeeper_process
        ai_bookkeeper_process.delay(instance.pk, auto_commit=False)
    except ImportError:
        logger.warning(
            "Failed to queue ai_bookkeeper for ArhivaEntry {}".format(instance.pk),
            exc_info=True,
        )
