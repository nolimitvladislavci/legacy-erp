"""
Invoicing Signals — auto-knjiženje faktura u Konto modul.

Trigger: Invoice status promjena na CONFIRMED/FISCALIZED/SENT/PAID
"""

import logging

from django.db import DatabaseError, IntegrityError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Status lista koji triggeraju knjiženje
BOOKABLE_STATUSES = ("CONFIRMED", "FISCALIZED", "SENT", "PAID")
# Doctype lista za knjiženje (ne knjižimo ponude/predračune)
BOOKABLE_DOCTYPES = ("R", "A", "S", "GS", "FA", "URA", "RN")


@receiver(pre_save, sender="invoicing.Invoice")
def track_status_change(sender, instance, **kwargs):
    """Track status changes to detect transition into bookable status."""
    instance._old_status = None
    if instance.pk:
        try:
            old = sender.objects.only("status").get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender="invoicing.Invoice")
def auto_book_invoice(sender, instance, created, **kwargs):
    """Auto-book invoice when status changes to CONFIRMED/FISCALIZED/SENT/PAID."""
    old_status = getattr(instance, "_old_status", None)
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
    from decimal import Decimal

    try:
        _total = Decimal(str(instance.total))
    except Exception:
        _total = Decimal(0)
    if not _total or _total <= 0:
        return

    # Skip invoices without company (no accounting context)
    if instance.company is None:
        return

    try:
        from konto.services_file import book_invoice

        je = book_invoice(instance)
        if je:
            logger.info(
                "Auto-knjiženje: faktura %s → temeljnica %s",
                instance.number,
                je.entry_number,
            )
    except ImportError:
        logger.warning(
            "Auto-knjiženje neuspješno za fakturu %s",
            instance.number,
            exc_info=True,
        )


# ── SupplierRiskAlert auto-trigger za ulazne fakture ─────────────────────


@receiver(post_save, sender="invoicing.Invoice")
def trigger_supplier_risk_check(sender, instance, created, **kwargs):
    """
    Kad se kreira ulazna faktura (URA) — provjeri bonitet dobavljača.
    Pokreće async Celery task. Preskače ako firma nema T&C consent (GDPR).
    """
    if not created:
        return
    # Samo ulazne fakture
    if instance.doctype not in ("URA", "UR"):
        return
    # Treba imati OIB dobavljača
    supplier_oib = getattr(instance, "client_oib", "") or ""
    if not supplier_oib or len(supplier_oib) < 8:
        return
    # Company mora postojati
    company = getattr(instance, "company", None)
    if not company:
        return
    # GDPR: preskoci ako nema T&C consent
    if not getattr(company, "has_signed_tc_consent", False):
        return

    try:
        from fiskalizacija.tasks import check_supplier_risk_async

        check_supplier_risk_async.delay(supplier_oib, str(company.id))
    except ImportError:
        logger.debug("SupplierRisk async trigger failed for OIB=%s", supplier_oib, exc_info=True)


# ── Sprint 1C: Invoice → Otpremnica auto-wire ─────────────────────────────


@receiver(post_save, sender="invoicing.Invoice")
def auto_create_otpremnica(sender, instance, created, **kwargs):
    """
    Invoice R/FA → kreira Otpremnica ako ima inventarnih stavki.
    Samo pri kreiranju, ne pri svakom save.
    Non-blocking — ne smije blokirati fakturiranje.
    """
    if not created:
        return
    if instance.doctype not in ("R", "FA", "RN"):
        return

    try:
        from invoicing.models import InvoiceItem

        items_with_inv = InvoiceItem.objects.filter(
            invoice=instance,
            inventory_item__isnull=False,
        ).select_related("inventory_item")

        if not items_with_inv.exists():
            return

        from propter.models import BillingPeriod, Otpremnica, OtpremnicaItem

        # Duplikat check
        if Otpremnica.objects.filter(invoice_id=str(instance.pk)).exists():
            return

        bp = BillingPeriod.get_or_create_current(instance.company)

        # Datum
        issue_date = instance.date_issued
        if hasattr(issue_date, "date"):
            issue_date = issue_date.date()

        otp = Otpremnica.objects.create(
            company=instance.company,
            billing_period=bp,
            invoice_id=str(instance.pk),
            issue_date=issue_date,
            delivery_date=getattr(instance, "date_delivery", None) or issue_date,
            recipient_name=instance.client_name or "",
            recipient_oib=instance.client_oib or "",
            recipient_address=instance.client_address or "",
            subtotal=instance.subtotal or 0,
            tax_amount=instance.tax_amount or 0,
            total=instance.total or 0,
            source=Otpremnica.Source.INVOICE,
            status=Otpremnica.Status.ISSUED,
        )

        for i, item in enumerate(items_with_inv, 1):
            OtpremnicaItem.objects.create(
                otpremnica=otp,
                line_number=i,
                description=item.description or "",
                quantity=item.quantity or 1,
                unit="EA",
                unit_price=item.unit_price or 0,
                tax_rate=getattr(item, "tax_percent", 25) or 25,
                line_total=getattr(item, "total", 0) or (item.unit_price or 0) * (item.quantity or 1),
            )

        # Bilježi na Invoice
        from django.db import models as db_models

        BillingPeriod.objects.filter(pk=bp.pk).update(otpremnica_count=db_models.F("otpremnica_count") + 1)
        sender.objects.filter(pk=instance.pk).update(
            internal_note=db_models.Value((instance.internal_note or "") + "\n[OTP: %s]" % otp.number)
        )

        logger.info("Auto OTP-%s iz fakture %s (%s stavki)", otp.number, instance.number, items_with_inv.count())

    except (IntegrityError, DatabaseError) as e:
        logger.warning("auto_create_otpremnica failed for %s: %s", instance.number, e)


# ─────────────────────────────────────────────────────────────────────────────
# GLOBALNI PEČAT — Proof of Existence + DocumentSeal pri finalizaciji fakture
# ─────────────────────────────────────────────────────────────────────name────
# Svaka faktura koja prelazi u SENT/CONFIRMED/FISCALIZED automatski dobiva:
#   1. QRToken (W3C VC 1.1) — već radi via core/qr_registry.py signals
#   2. DocumentSeal (eIDAS/GoBD/ZED) — novo, kreira se ovdje
# ─────────────────────────────────────────────────────────────────────────────

_ISSUE_TRIGGER_STATUSES = {"SENT", "CONFIRMED", "FISCALIZED"}


@receiver(post_save, sender="invoicing.Invoice")
def auto_seal_invoice(sender, instance, created, **kwargs):
    """
    Pri prvoj finalizaciji fakture (SENT/CONFIRMED/FISCALIZED):
    kreira DocumentSeal + bilježi u log.
    Idempotentno — ne duplicira seal za isti račun.
    """
    if created:
        return

    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    # Samo pri prijelazu u issued statuse
    if new_status not in _ISSUE_TRIGGER_STATUSES:
        return
    if old_status in _ISSUE_TRIGGER_STATUSES:
        return

    try:
        from evalidator.models import DocumentSeal

        # Idempotentnost — provjeri postoji li već seal za ovaj invoice
        # SHA-256 iz ključnih metapodataka
        import hashlib
        meta = f"invoice:{instance.pk}:{instance.number}:{instance.total}:{instance.company_id}"
        sha256 = hashlib.sha256(meta.encode()).hexdigest()

        # Idempotentnost — provjeri postoji li već seal za ovaj invoice
        existing = DocumentSeal.objects.filter(sha256_hash=sha256).first()
        if existing:
            return  # već zapečaćeno

        from datetime import timedelta
        from django.utils import timezone

        company = instance.company
        expires = timezone.now() + timedelta(days=3652)  # GoBD: 10 godina

        seal = DocumentSeal.objects.create(
            sha256_hash=sha256,
            arhiva_company_id=company.pk if company else None,
            doc_number=instance.number or "",
            doc_date=getattr(instance, "issue_date", None) or getattr(instance, "date_issue", None),
            partner_name=getattr(instance, "client_name", "") or "",
            amount=instance.total or 0,
            currency=getattr(instance, "currency", "EUR") or "EUR",
            issuer_name=company.name if company else "",
            issuer_country=getattr(company, "country", "HR") or "HR",
            expires_at=expires,
            send_channel="auto",
        )
        logger.info(
            "DocumentSeal %s kreiran za Invoice %s (status=%s)",
            seal.seal_token, instance.number, new_status,
        )

    except Exception as e:
        logger.warning("auto_seal_invoice failed for %s: %s", getattr(instance, "number", instance.pk), e)
