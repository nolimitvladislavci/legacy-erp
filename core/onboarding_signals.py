"""
Onboarding auto-completion signals.

Connected in core/apps.py ready() to automatically mark onboarding steps
when users create their first partner, item, invoice, or POS terminal.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="inventory.InventoryItem")
def on_item_saved(sender, instance, created, **kwargs):
    """Mark first_item_added when any InventoryItem is created."""
    if not created:
        return
    company = getattr(instance, "company", None)
    if not company:
        return
    try:
        from companies.models import OnboardingProgress

        ob, _ = OnboardingProgress.objects.get_or_create(company=company)
        if not ob.first_item_added:
            ob.first_item_added = True
            ob.save(update_fields=["first_item_added", "updated_at"])
    except DatabaseError:
        logger.warning("onboarding signal item error", exc_info=True)


@receiver(post_save, sender="pos.POSTerminal")
def on_pos_terminal_saved(sender, instance, created, **kwargs):
    """Mark pos_configured when a POSTerminal is created."""
    if not created:
        return
    company = getattr(instance, "company", None)
    if not company:
        return
    try:
        from companies.models import OnboardingProgress

        ob, _ = OnboardingProgress.objects.get_or_create(company=company)
        if not ob.pos_configured:
            ob.pos_configured = True
            ob.save(update_fields=["pos_configured", "updated_at"])
    except DatabaseError:
        logger.warning("onboarding signal pos error", exc_info=True)
