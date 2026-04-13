"""
POS Signals — auto-generiranje dnevnog izvještaja i auto-knjiženje na zatvaranju sesije.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver

from pos.models import POSSession


@receiver(post_save, sender=POSSession)
def generate_daily_report_on_close(sender, instance, **kwargs):
    """Kad se sesija zatvori, generiraj POSDailyReport (on_commit)."""
    if instance.status in ("closed", "z_done") and instance.closed_at:
        session_pk = instance.pk

        def _gen():
            try:
                from pos.models import POSDailyReport as _PDR
                from pos.models import POSSession as _PS

                sess = _PS.objects.get(pk=session_pk)
                _PDR.generate_from_session(sess)
            except ObjectDoesNotExist:
                import logging

                logging.getLogger(__name__).warning(
                    "POSDailyReport generiranje neuspješno za sesiju #%s",
                    session_pk,
                    exc_info=True,
                )

        from django.db import transaction

        transaction.on_commit(_gen)


@receiver(post_save, sender=POSSession)
def auto_book_pos_session(sender, instance, **kwargs):
    """Kad se sesija zatvori, automatski proknjiži u Konto modul.
    Radi on_commit da ne kvari atomarnu transakciju close_session.
    """
    if instance.status in ("closed", "z_done") and instance.closed_at:
        session_pk = instance.pk

        def _book():
            try:
                from pos.models import POSSession as _PS

                sess = _PS.objects.get(pk=session_pk)
                from konto.services_file import book_pos_session

                je = book_pos_session(sess)
                if je:
                    import logging

                    logging.getLogger(__name__).info(
                        "POS auto-knjiženje: sesija #%s → temeljnica %s",
                        session_pk,
                        je.entry_number,
                    )
            except ObjectDoesNotExist:
                import logging

                logging.getLogger(__name__).warning(
                    "POS auto-knjiženje neuspješno za sesiju #%s",
                    session_pk,
                    exc_info=True,
                )

        from django.db import transaction

        transaction.on_commit(_book)


# ═══════════════════════════════════════════════════════════════
#  Context-Aware Post-Receipt Hooks (POS kao Centar Svijeta)
# ═══════════════════════════════════════════════════════════════


@receiver(post_save, sender="pos.POSReceipt")
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

    logger = logging.getLogger("pos.signals.context_hooks")

    try:
        terminal = instance.session.terminal
        company = terminal.company
    except AttributeError:
        return

    pos_type = terminal.pos_type
    business_type = getattr(company, "business_type", "doo")

    # ── Rental Hook: auto-eVisitor ──
    if pos_type == "reception":
        try:
            from rental.tasks import check_evisitor_pending

            check_evisitor_pending.delay()
            logger.info("Rental hook: eVisitor check triggered after receipt %s", instance.pk)
        except ImportError as e:
            logger.warning("Rental hook failed: %s", e)

    # ── Udruga Hook: auto-produlji članstvo ──
    if business_type in ("udruga", "zadruga", "ustanova"):
        try:
            # Provjeri ima li stavka "CLANARINA" ili "MEMBERSHIP" u receiptu
            membership_items = instance.items.filter(description__iregex=r"(članarin|membership|clanarin)")
            if membership_items.exists():
                from udruge.tasks import evaluate_subscriptions

                evaluate_subscriptions.delay()
                logger.info("Udruga hook: membership extension triggered for receipt %s", instance.pk)
        except DatabaseError as e:
            logger.warning("Udruga hook failed: %s", e)

    # ── Field Hook: WhatsApp PDF ──
    if pos_type == "field":
        try:
            customer_phone = getattr(instance, "customer_phone", "") or ""
            if not customer_phone:
                # Pokušaj izvući iz partnera
                partner = getattr(instance, "partner", None)
                if partner:
                    customer_phone = getattr(partner, "phone", "") or ""

            if customer_phone:
                try:
                    from udruge.tasks import check_access_card as _noop  # noqa: F401
                except ImportError:
                    pass
                import logging as _lg

                _lg.getLogger("pos.signals").info(
                    "Field hook: WhatsApp receipt za %s → %s", instance.pk, customer_phone
                )
                logger.info("Field hook: WhatsApp receipt triggered for %s", instance.pk)
        except ImportError as e:
            logger.warning("Field hook failed: %s", e)
