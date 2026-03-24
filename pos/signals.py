"""
POS Signals — auto-generiranje dnevnog izvještaja i auto-knjiženje na zatvaranju sesije.
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


@receiver(post_save, sender=POSSession)
def auto_book_pos_session(sender, instance, **kwargs):
    """Kad se sesija zatvori, automatski proknjiži u Konto modul."""
    if instance.status in ('closed', 'z_done') and instance.closed_at:
        try:
            from konto.services_file import book_pos_session
            je = book_pos_session(instance)
            if je:
                import logging
                logging.getLogger(__name__).info(
                    'POS auto-knjiženje: sesija #%s → temeljnica %s',
                    instance.pk, je.entry_number,
                )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'POS auto-knjiženje neuspješno za sesiju #%s',
                instance.pk, exc_info=True,
            )


# ═══════════════════════════════════════════════════════════════
#  Context-Aware Post-Receipt Hooks (POS kao Centar Svijeta)
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='pos.POSReceipt')
def context_post_receipt_hooks(sender, instance, created, **kwargs):
    """
    Nakon svake transakcije — kontekstualni hookovi ovisno o pos_type i business_type.

    reception → auto-eVisitor prijava
    udruga → auto-produlji članstvo
    field → WhatsApp PDF račun
    """
    if not created:
        return

    import logging
    logger = logging.getLogger('pos.signals.context_hooks')

    try:
        terminal = instance.session.terminal
        company = terminal.company
    except Exception:
        return

    pos_type = terminal.pos_type
    business_type = getattr(company, 'business_type', 'doo')

    # ── Rental Hook: auto-eVisitor ──
    if pos_type == 'reception':
        try:
            from rental.tasks import check_evisitor_pending
            check_evisitor_pending.delay()
            logger.info('Rental hook: eVisitor check triggered after receipt %s', instance.pk)
        except Exception as e:
            logger.warning('Rental hook failed: %s', e)

    # ── Udruga Hook: auto-produlji članstvo ──
    if business_type in ('udruga', 'zadruga', 'ustanova'):
        try:
            # Provjeri ima li stavka "CLANARINA" ili "MEMBERSHIP" u receiptu
            membership_items = instance.items.filter(
                item_name__iregex=r'(članarin|membership|clanarin)'
            )
            if membership_items.exists():
                from udruge.tasks import auto_extend_membership_from_receipt
                auto_extend_membership_from_receipt.delay(instance.pk)
                logger.info('Udruga hook: membership extension triggered for receipt %s', instance.pk)
        except Exception as e:
            logger.warning('Udruga hook failed: %s', e)

    # ── Field Hook: WhatsApp PDF ──
    if pos_type == 'field':
        try:
            customer_phone = getattr(instance, 'customer_phone', '') or ''
            if not customer_phone:
                # Pokušaj izvući iz partnera
                partner = getattr(instance, 'partner', None)
                if partner:
                    customer_phone = getattr(partner, 'phone', '') or ''

            if customer_phone:
                from notifications.tasks import send_receipt_whatsapp
                send_receipt_whatsapp.delay(instance.pk, customer_phone)
                logger.info('Field hook: WhatsApp receipt triggered for %s', instance.pk)
        except Exception as e:
            logger.warning('Field hook failed: %s', e)
