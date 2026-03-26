"""
pos/services/_otpremnica_bridge.py
POS Receipt → Otpremnica auto-wire.

Trigger: POSReceipt paid s artiklima koji imaju inventory_item.
Skip: training, nulti iznos, bez inventarnih artikala, duplikati.
NIKAD ne blokira POS — sve u try/except na pozivnoj strani.
"""
import logging
from django.db import models

logger = logging.getLogger('pos.otpremnica')


def pos_receipt_to_otpremnica(receipt):
    """
    Kreira Otpremnica iz POS bona.
    Automatski — korisnik ništa ne radi.
    """
    # Skip: training receipts
    if getattr(receipt, 'is_training', False):
        return None

    # Skip: nulti iznos
    if not receipt.total or float(receipt.total) == 0:
        return None

    # Provjeri ima li inventarnih artikala
    from pos.models import POSReceiptItem
    items_with_inv = list(POSReceiptItem.objects.filter(
        receipt=receipt,
        inventory_item__isnull=False,
    ).select_related('inventory_item'))

    if not items_with_inv:
        return None  # Usluge/radovi ne trebaju otpremnicu

    from propter.models import Otpremnica, OtpremnicaItem, BillingPeriod

    # Provjeri duplikat
    if Otpremnica.objects.filter(pos_receipt_id=str(receipt.pk)).exists():
        return None

    company = receipt.session.terminal.company
    bp = BillingPeriod.get_or_create_current(company)

    # Kupac info
    recipient_name = getattr(receipt, 'buyer_name', '') or 'Gotovinski kupac'
    recipient_oib = getattr(receipt, 'buyer_oib', '') or ''

    otp = Otpremnica.objects.create(
        company=company,
        billing_period=bp,
        pos_receipt_id=str(receipt.pk),
        issue_date=receipt.created_at.date(),
        delivery_date=receipt.created_at.date(),
        recipient_name=recipient_name,
        recipient_oib=recipient_oib,
        subtotal=receipt.subtotal or 0,
        tax_amount=receipt.tax_amount or 0,
        total=receipt.total,
        source=Otpremnica.Source.POS,
        status=Otpremnica.Status.ISSUED,
    )

    # Stavke
    for i, item in enumerate(items_with_inv, 1):
        OtpremnicaItem.objects.create(
            otpremnica=otp,
            line_number=i,
            description=item.description or (item.inventory_item.name if item.inventory_item else ''),
            quantity=item.quantity,
            unit='EA',
            unit_price=item.unit_price,
            tax_rate=item.tax_rate or 25,
            line_total=item.total_price or (item.unit_price * item.quantity),
        )

    # Ažuriraj BillingPeriod counter
    BillingPeriod.objects.filter(pk=bp.pk).update(
        otpremnica_count=models.F('otpremnica_count') + 1
    )

    logger.info('OTP-%s kreirana iz POS bona #%s (%s EUR, %d stavki)',
                otp.number, receipt.receipt_number, receipt.total, len(items_with_inv))

    return otp
