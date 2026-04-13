"""
POS business logic — pure functions, no request/response.

Extracted from views.py to enable:
- Unit testing without HTTP
- Reuse across views, API, Celery tasks
- Clear separation of concerns
"""
import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils.timezone import now

from core.exceptions import PaymentError, SessionError
from django.db import IntegrityError, DatabaseError

if False:  # TYPE_CHECKING
    from pos.models import POSTerminal, POSSession, POSReceipt, POSReceiptItem
    from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


# ── Receipt Calculation ─────────────────────────────────────

def recalculate_receipt(receipt: "POSReceipt") -> None:
    """Recalculate receipt totals from items. Saves to DB."""
    items = list(receipt.items.all())
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in items:
        net = item.quantity * item.unit_price * (1 - item.discount_percent / 100)
        tax = net * item.tax_rate / 100
        subtotal += net
        tax_total += tax
    receipt.subtotal = round(subtotal, 2)
    receipt.tax_amount = round(tax_total, 2)
    receipt.total = round(subtotal + tax_total - receipt.discount, 2)
    receipt.save(update_fields=["subtotal", "tax_amount", "total"])


# ── Session Management ──────────────────────────────────────

def open_session(terminal: "POSTerminal", user: "User", opening_cash: Decimal = Decimal("0")) -> "POSSession":
    """Open a new POS session on terminal. Returns session or raises."""
    from .models import POSSession

    # LOCK — sprečava duplu sesiju pri istovremenom otvaranju
    terminal = type(terminal).objects.select_for_update().get(pk=terminal.pk)

    if terminal.sessions.filter(status=POSSession.Status.OPEN).exists():
        raise SessionError("Terminal već ima otvorenu sesiju.")

    last = terminal.sessions.order_by("-session_number").first()
    next_num = (last.session_number + 1) if last else 1

    session = POSSession.objects.create(
        terminal=terminal,
        operator=user,
        session_number=next_num,
        opening_cash=opening_cash,
        status=POSSession.Status.OPEN,
    )
    logger.info("Session #%d opened on terminal %s by %s", next_num, terminal.pk, user.pk)
    return session


def close_session(session: "POSSession", closing_cash: Decimal = Decimal("0")) -> bool:
    """Close a POS session. Returns True if successful."""
    from .models import POSReceipt, POSSession

    if session.status != POSSession.Status.OPEN:
        raise SessionError("Sesija je već zatvorena.")

    open_count = session.receipts.filter(status=POSReceipt.Status.OPEN).count()
    if open_count:
        raise SessionError(f"Nije moguće zatvoriti: {open_count} otvorenih računa.")

    session.closing_cash = closing_cash
    session.closed_at = now()
    session.status = POSSession.Status.CLOSED
    session.save()
    logger.info("Session #%d closed, cash=%.2f", session.session_number, closing_cash)
    return True


# ── Receipt Creation ────────────────────────────────────────

def create_receipt(session: "POSSession", table_number: str = "", note: str = "") -> "POSReceipt":
    """Create a new receipt in session. Returns receipt."""
    from .models import POSReceipt

    last = session.receipts.order_by("-receipt_number").first()
    next_num = (last.receipt_number + 1) if last else 1

    receipt = POSReceipt.objects.create(
        session=session,
        receipt_number=next_num,
        table_number=table_number,
        note=note,
    )
    logger.info("Receipt #%d created in session %d", next_num, session.pk)
    return receipt


def add_receipt_item(receipt: "POSReceipt", inventory_item_id: Optional[int], description: str,
                     quantity: Decimal, unit_price: Decimal,
                     unit: str = "kom", tax_rate: Decimal = Decimal("25"),
                     discount_percent: Decimal = Decimal("0")) -> "POSReceiptItem":
    """Add item to receipt. Returns created item."""
    from .models import POSReceiptItem

    item = POSReceiptItem.objects.create(
        receipt=receipt,
        inventory_item_id=inventory_item_id,
        description=description[:200],
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        tax_rate=tax_rate,
        discount_percent=discount_percent,
    )
    recalculate_receipt(receipt)
    return item


def remove_receipt_item(receipt: "POSReceipt", item_id: int) -> bool:
    """Remove item from receipt. Returns True if found and deleted."""
    from .models import POSReceiptItem

    deleted, _ = POSReceiptItem.objects.filter(pk=item_id, receipt=receipt).delete()
    if deleted:
        recalculate_receipt(receipt)
    return deleted > 0


# ── Payment Processing ──────────────────────────────────────

@transaction.atomic
def process_payment(receipt: "POSReceipt", method: str, amount_paid: Decimal,
                    user: "User | None" = None) -> dict:
    """
    Process payment for receipt.
    Creates payment line, updates inventory, attempts fiscalization.
    Returns dict with payment details.
    """
    from .models import POSPaymentLine, POSReceipt

    # LOCK — sprečava duplu naplatu pri istovremenim zahtjevima
    receipt = POSReceipt.objects.select_for_update().get(pk=receipt.pk)

    if receipt.status != POSReceipt.Status.OPEN:
        raise PaymentError("Račun je već zatvoren.")
    if not receipt.items.exists():
        raise PaymentError("Nije moguće platiti prazan račun.")

    change = max(Decimal("0"), amount_paid - receipt.total)

    # Payment line
    POSPaymentLine.objects.create(
        receipt=receipt,
        method=method,
        amount=receipt.total,
        change_given=change,
    )

    # Close receipt
    receipt.status = POSReceipt.Status.PAID
    receipt.paid_at = now()
    receipt.save(update_fields=["status", "paid_at"])

    # Inventory deduction
    _deduct_inventory(receipt, user)

    # Fiscalization (non-blocking)
    jir = _attempt_fiscalization(receipt)

    logger.info(
        "Payment processed: receipt=%d method=%s total=%.2f jir=%s",
        receipt.receipt_number, method, receipt.total, jir or "none"
    )

    return {
        "receipt_id": receipt.pk,
        "receipt_number": receipt.receipt_number,
        "total": receipt.total,
        "change": change,
        "jir": jir,
    }


@transaction.atomic
def quick_pay(session: "POSSession", items_data: list[dict], method: str = "CASH",
              amount_paid: Decimal = Decimal("0"),
              cashier_name: str = "", user: "User | None" = None) -> dict:
    """
    One-shot: create receipt + add items + pay.
    Used by quick POS and restaurant POS.
    Returns payment result dict.
    """
    if not items_data:
        raise PaymentError("Nema stavki za naplatu.")

    receipt = create_receipt(session, note=cashier_name[:50])

    for item_data in items_data:
        try:
            add_receipt_item(
                receipt=receipt,
                inventory_item_id=item_data.get("id") or None,
                description=str(item_data.get("name", ""))[:200],
                quantity=Decimal(str(item_data.get("qty", 1))),
                unit_price=Decimal(str(item_data.get("price", 0))),
                tax_rate=Decimal(str(item_data.get("tax", 25))),
            )
        except (ValueError, TypeError) as e:
            logger.warning("Failed to add item %s: %s", item_data, e)

    receipt.refresh_from_db()

    if method == "CARD":
        amount_paid = receipt.total
    elif not amount_paid:
        amount_paid = receipt.total

    return process_payment(receipt, method, amount_paid, user)


# ── Internal Helpers ────────────────────────────────────────

def _deduct_inventory(receipt: "POSReceipt", user: "User | None" = None) -> int:
    """Deduct inventory for all items in receipt. Returns count of movements."""
    from inventory.models import StockMovement
    count = 0

    # LOCK — zaključaj sve inventory artikle odjednom prije dedukcije
    item_ids = [
        item.inventory_item_id
        for item in receipt.items.all()
        if item.inventory_item_id
    ]
    if item_ids:
        from inventory.models import InventoryItem
        list(InventoryItem.objects.select_for_update().filter(pk__in=item_ids))

    for item in receipt.items.select_related("inventory_item").all():
        if not item.inventory_item_id:
            continue

        StockMovement.objects.create(
            item_id=item.inventory_item_id,
            movement_type="out",
            quantity=item.quantity,
            unit_price=item.unit_price,
            reason=f"POS bon #{receipt.receipt_number}",
            performed_by=user,
        )
        count += 1

        # BOM auto-deduction
        count += _deduct_bom(item, receipt, user)

    return count


def _deduct_bom(receipt_item: "POSReceiptItem", receipt: "POSReceipt", user: "User | None" = None) -> int:
    """Deduct BOM components for a receipt item. Returns movement count."""
    try:
        from calculator.models import BOM
        from inventory.models import StockMovement

        boms = BOM.objects.filter(
            article_id=receipt_item.inventory_item_id,
            is_active=True,
        ).prefetch_related("items__material")

        count = 0
        for bom in boms:
            sold_qty = receipt_item.quantity / (bom.yield_quantity or 1)
            for bi in bom.items.select_related("material").all():
                deduct = bi.net_quantity * sold_qty
                StockMovement.objects.create(
                    item=bi.material,
                    movement_type="out",
                    quantity=deduct,
                    unit_price=bi.material.purchase_price,
                    reason=f"BOM — POS bon #{receipt.receipt_number}",
                    performed_by=user,
                )
                count += 1
        return count
    except (IntegrityError, DatabaseError) as e:
        logger.warning("BOM deduction failed for item %s: %s", receipt_item.pk, e)
        return 0


def _attempt_fiscalization(receipt: "POSReceipt") -> str | None:
    """Attempt fiscal registration. Returns JIR or None."""
    try:
        from fiscal.service import fiscalize_pos_receipt
        jir = fiscalize_pos_receipt(receipt)
        return jir
    except Exception as e:
        logger.warning("Fiscalization failed for receipt %d: %s", receipt.pk, e)
        return None


# ── Z-Report ────────────────────────────────────────────────

def generate_zreport(session: "POSSession") -> dict:
    """Generate Z-report data for a session."""
    from django.db.models import Sum

    from .models import POSPaymentLine, POSReceipt

    receipts = session.receipts.filter(status=POSReceipt.Status.PAID)
    payments = POSPaymentLine.objects.filter(receipt__session=session, receipt__status="paid")

    total_sales = receipts.aggregate(s=Sum("total"))["s"] or Decimal("0")
    receipt_count = receipts.count()

    by_method = {}
    for method_code, method_name in POSPaymentLine.Method.choices:
        amount = payments.filter(method=method_code).aggregate(s=Sum("amount"))["s"]
        if amount:
            by_method[method_code] = {"name": method_name, "amount": amount}

    return {
        "session": session,
        "total_sales": total_sales,
        "receipt_count": receipt_count,
        "by_method": by_method,
        "opening_cash": session.opening_cash,
        "closing_cash": session.closing_cash,
        "expected_cash": session.expected_closing_cash,
        "difference": session.cash_difference,
    }
