# CC_TASK_CONCURRENCY_LOCKOVI — Race Condition Fix
# Agent: CC Code
# Prioritet: KRITIČAN — produkcijski crash pri 150+ istovremenih transakcija
# Datum: 2026-03-25

---

## Problem

`pos/services.py` nema transakcijske brave na 3 kritična mjesta.
Bez `select_for_update()`, 2 istovremena zahtjeva mogu:
- Dvaput fiskalizirati isti račun → dupli JIR → kaznena odgovornost
- Dvaput smanjiti zalihe → negativna stanja
- Dvaput otvoriti sesiju → sesija duplikat

---

## FIX 1 — `process_payment` (redak ~168)

**Problem:** status check bez locka
```python
# TRENUTNO (OPASNO):
if receipt.status != POSReceipt.Status.OPEN:
    raise PaymentError("Račun je već zatvoren.")
```

**Fix:**
```python
@transaction.atomic
def process_payment(receipt: "POSReceipt", method: str, amount_paid: Decimal,
                    user: "User | None" = None) -> dict:
    from .models import POSPaymentLine, POSReceipt

    # LOCK — samo jedan thread može ući za ovaj račun
    receipt = POSReceipt.objects.select_for_update().get(pk=receipt.pk)

    if receipt.status != POSReceipt.Status.OPEN:
        raise PaymentError("Račun je već zatvoren.")
    if not receipt.items.exists():
        raise PaymentError("Nije moguće platiti prazan račun.")
    # ... ostatak nepromijenjen
```

---

## FIX 2 — `_deduct_inventory` (redak ~248)

**Problem:** čita inventory_item bez locka, može doći do negativnih zaliha

**Fix:**
```python
def _deduct_inventory(receipt: "POSReceipt", user: "User | None" = None) -> int:
    from inventory.models import StockMovement, InventoryItem

    count = 0
    # Dohvati sve inventory_item_id-ove s lockom
    item_ids = [
        item.inventory_item_id
        for item in receipt.items.all()
        if item.inventory_item_id
    ]
    # Zaključaj sve relevantne artikle odjednom
    locked_items = {
        item.pk: item
        for item in InventoryItem.objects.select_for_update().filter(pk__in=item_ids)
    }

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
        count += _deduct_bom(item, receipt, user)

    return count
```

---

## FIX 3 — `open_session` (redak ~52)

**Problem:** check-then-create bez locka → dupla sesija moguća

**Fix:**
```python
def open_session(terminal: "POSTerminal", user: "User", opening_cash: Decimal = Decimal("0")) -> "POSSession":
    from .models import POSSession

    with transaction.atomic():
        # Zaključaj terminal row
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
```

---

## FIX 4 — `fiscalize_pos_receipt` idempotency (fiscal/service.py ~55)

**Problem:** nema provjere je li račun već fiskaliziran → dupli JIR

**Fix — dodaj na početak `fiscalize_pos_receipt`:**
```python
def fiscalize_pos_receipt(receipt):
    from .models import FiscalLog

    # IDEMPOTENCY GUARD — ne šalji dvaput
    if FiscalLog.objects.filter(receipt_type='pos_receipt', receipt_id=receipt.pk, status='success').exists():
        logger.warning("Receipt %d already fiscalized — skipping", receipt.pk)
        existing = FiscalLog.objects.filter(receipt_type='pos_receipt', receipt_id=receipt.pk, status='success').first()
        return existing.jir if existing else None

    # ... ostatak nepromijenjen
```

---

## Testovi koje treba napisati

```python
# tests/test_concurrency.py
from django.test import TransactionTestCase
from concurrent.futures import ThreadPoolExecutor

class ConcurrencyTest(TransactionTestCase):
    def test_double_payment_prevented(self):
        """Isti račun ne može biti plaćen dvaput."""
        # ... setup receipt
        results = []
        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(process_payment, receipt, "CASH", Decimal("10"))
            f2 = ex.submit(process_payment, receipt, "CASH", Decimal("10"))
        # Točno jedan mora uspjeti, drugi mora baciti PaymentError
        
    def test_inventory_no_negative_stock(self):
        """Zalihe ne mogu ići u minus pri istovremenim prodajama."""
        # ... setup 1 komad na stanju, 2 istovremene prodaje
        # Jedna mora uspjeti, druga mora baciti grešku ili se odbiti
```

---

## Napomena
- Svi `@transaction.atomic` dekoratori su već na `process_payment` i `quick_pay` — OK.
- `select_for_update()` radi SAMO unutar `transaction.atomic()` bloka — ovo je ispunjeno.
- Nakon deploya: provjeri EXPLAIN ANALYZE na PostgreSQL-u za hotspot querije.
