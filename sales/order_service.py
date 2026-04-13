"""
sales/order_service.py — SalesOrder lifecycle management

P1 flow: Narudžba → Potvrda → Isporuka → Faktura
P7 flow: Narudžba → Potvrda → Otpremnica → Faktura

auto_apply_prices()      — primijeni posebni cjenik na stavke narudžbe
confirm_order()          — potvrdi narudžbu, rezerviraj stock
create_otpremnica()      — kreiraj otpremnicu iz narudžbe (P7)
create_invoice()         — kreiraj fakturu iz narudžbe
next_order_number()      — generiraj sljedeći broj narudžbe
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .ai_services import resolve_price
from .models import SalesOrder

logger = logging.getLogger(__name__)


def next_order_number(company):
    """Generiraj sljedeći broj narudžbe: NAR-YYYYMM-NNN."""
    prefix = f"NAR-{timezone.now().strftime('%Y%m')}-"
    last = (
        SalesOrder.objects.filter(
            company=company,
            order_number__startswith=prefix,
        )
        .order_by("-order_number")
        .first()
    )

    if last:
        try:
            last_num = int(last.order_number.split("-")[-1])
            return f"{prefix}{last_num + 1:03d}"
        except (ValueError, IndexError):
            pass
    return f"{prefix}001"


def auto_apply_prices(order):
    """
    Primijeni posebni cjenik na sve stavke narudžbe.
    Automatski pronalazi najbolju cijenu za kupca.
    """
    if not order.partner or not order.price_list:
        return 0

    applied = 0
    for line in order.lines.select_related("item").all():
        result = resolve_price(order.company, order.partner, line.item, line.quantity)
        if result["has_special_price"]:
            discount = result["discount_applied"]
            line.unit_price = result["price"]
            line.discount_percent = discount.get("savings_percent", 0)
            line.save(update_fields=["unit_price", "discount_percent"])
            applied += 1

    if applied:
        order.recalculate()

    return applied


@transaction.atomic
def confirm_order(order, user=None):
    """Potvrdi narudžbu — provjeri dostupnost, promijeni status."""
    if order.status != "draft":
        raise ValueError(f"Narudžba {order.order_number} nije u nacrtu")

    # Check stock availability
    warnings = []
    for line in order.lines.select_related("item").all():
        available = getattr(line.item, "quantity", 0)
        if available < line.quantity:
            warnings.append(f"{line.item.name}: potrebno {line.quantity}, dostupno {available}")

    order.status = "confirmed"
    order.save(update_fields=["status", "updated_at"])
    order.recalculate()

    logger.info(f"SalesOrder confirmed: {order.order_number}")
    return {"warnings": warnings}


@transaction.atomic
def create_otpremnica(order, user=None):
    """
    Kreiraj otpremnicu iz narudžbe (P7 flow).
    Koristi propter.Otpremnica model.
    """
    if order.status not in ("confirmed", "processing"):
        raise ValueError("Narudžba mora biti potvrđena za otpremnicu")

    from propter.models import Otpremnica, OtpremnicaItem

    otp = Otpremnica.objects.create(
        company=order.company,
        partner=order.partner,
        date=timezone.now().date(),
        source=Otpremnica.Source.ORDER if hasattr(Otpremnica, "Source") else "order",
        status=Otpremnica.Status.ISSUED if hasattr(Otpremnica, "Status") else "issued",
        notes=f"Iz narudžbe {order.order_number}",
    )

    for line in order.lines.select_related("item").all():
        remaining = line.quantity - line.delivered_quantity
        if remaining <= 0:
            continue
        OtpremnicaItem.objects.create(
            otpremnica=otp,
            item_name=line.item.name,
            quantity=remaining,
            unit=line.unit,
            unit_price=line.unit_price,
        )
        line.delivered_quantity = line.quantity
        line.save(update_fields=["delivered_quantity"])

    order.otpremnica = otp
    order.status = "shipped"
    order.save(update_fields=["otpremnica", "status", "updated_at"])

    logger.info(f"Otpremnica created from {order.order_number}: {otp.pk}")
    return otp


@transaction.atomic
def create_invoice(order, user=None):
    """
    Kreiraj fakturu iz narudžbe — završni korak P1/P7 flowa.
    """
    if order.status not in ("shipped", "confirmed", "processing"):
        raise ValueError("Narudžba mora biti isporučena ili potvrđena za fakturiranje")

    from invoicing.models import Invoice, InvoiceItem

    inv = Invoice.objects.create(
        company=order.company,
        partner=order.partner,
        direction="outgoing",
        invoice_type="racun",
        issue_date=timezone.now().date(),
        due_date=order.delivery_date or (timezone.now().date() + timezone.timedelta(days=15)),
        currency=order.currency,
        status="draft",
        client_name=order.partner.name,
        buyer_name=order.partner.name,
        buyer_oib=getattr(order.partner, "oib", ""),
        notes=f"Iz narudžbe {order.order_number}",
    )

    # Auto-number
    from invoicing.services.invoice_service import generate_invoice_number

    try:
        inv.number = generate_invoice_number(order.company)
    except AttributeError:
        inv.number = f"RAC-{timezone.now().strftime('%Y%m%d')}-{inv.pk}"
    inv.save(update_fields=["number"])

    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for line in order.lines.select_related("item").all():
        net = line.net_total
        tax = line.tax_amount
        InvoiceItem.objects.create(
            invoice=inv,
            description=line.item.name,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount_percent=line.discount_percent,
            tax_rate=line.tax_rate,
            total=line.gross_total,
        )
        subtotal += net
        tax_total += tax

    inv.subtotal = subtotal
    inv.tax_amount = tax_total
    inv.total = subtotal + tax_total
    inv.save(update_fields=["subtotal", "tax_amount", "total"])

    order.invoice = inv
    order.status = "invoiced"
    order.save(update_fields=["invoice", "status", "updated_at"])

    # Create open item for saldakonti
    from sales.models import OpenItem

    OpenItem.objects.create(
        company=order.company,
        partner=order.partner,
        direction="receivable",
        document_type="racun",
        document_number=inv.number,
        document_date=inv.issue_date,
        due_date=inv.due_date or inv.issue_date,
        original_amount=inv.total,
        currency=inv.currency,
        invoice=inv,
    )

    logger.info(f"Invoice {inv.number} created from {order.order_number}")
    return inv
