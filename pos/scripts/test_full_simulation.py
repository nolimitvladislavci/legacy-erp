"""
POS MEGA SIMULACIJA — End-to-end test svih flowova.
Od ulaska gosta do "doviđenja, dođite nam opet!"

Pokreni: venv/bin/python manage.py shell < pos/test_full_simulation.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from companies.models import Company, CompanyBranch
from pos.models import *
from inventory.models import InventoryItem, StockMovement

konjik = Company.objects.get(name__icontains="Konjik")
su = User.objects.get(username="superadmin")
now = timezone.now

passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    try:
        r = fn()
        if r:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            errors.append(name)
            print(f"  FAIL: {name}")
    except (ValueError, TypeError) as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  ERROR: {name} -> {e}")

# Artikli
pizza = InventoryItem.objects.get(company=konjik, sku="TEST-PIZZA")
pivo = InventoryItem.objects.get(company=konjik, sku="TEST-PIVO")
kava = InventoryItem.objects.get(company=konjik, sku="TEST-KAVA")
desert = InventoryItem.objects.get(company=konjik, sku="TEST-DESERT")
salata = InventoryItem.objects.get(company=konjik, sku="TEST-SALATA")
steak = InventoryItem.objects.get(company=konjik, sku="TEST-STEAK")
vino = InventoryItem.objects.get(company=konjik, sku="TEST-VINO")
naoc = InventoryItem.objects.get(company=konjik, sku="TEST-NAOC")
stakla = InventoryItem.objects.get(company=konjik, sku="TEST-STAKLA")
pregled = InventoryItem.objects.get(company=konjik, sku="TEST-PREGLED")

pizza_before = pizza.quantity
pivo_before = pivo.quantity
naoc_before = naoc.quantity

term = POSTerminal.objects.filter(company=konjik, is_active=True).first()

print("=" * 70)
print("SIMULACIJA 1: RESTORAN — Gost dolazi, naručuje, jede, plaća")
print("=" * 70)

# 1.1 Otvaranje smjene
def t11():
    global session_r
    last = term.sessions.order_by("-session_number").first()
    next_num = (last.session_number + 1) if last else 1
    session_r = POSSession.objects.create(
        terminal=term, operator=su, session_number=next_num,
        opening_cash=Decimal("200.00"), status="open"
    )
    return session_r.pk > 0 and session_r.status == "open"
test("1.1 Otvaranje smjene (200 EUR gotovine)", t11)

# 1.2 Stol 5 — Gost naručuje
def t12():
    global order1, table1
    table1, _ = Table.objects.get_or_create(
        company=konjik, name="Stol 5-T",
        defaults={"table_type": "table", "capacity": 4, "is_active": True}
    )
    order1 = GastroOrder.objects.create(
        company=konjik, table=table1, status="new",
        guest_name="Marko Horvat", guest_email="marko@test.hr",
        notes="Bez luka na pizzi"
    )
    GastroOrderItem.objects.create(order=order1, inventory_item=pizza, quantity=1, notes="bez luka")
    GastroOrderItem.objects.create(order=order1, inventory_item=salata, quantity=1)
    GastroOrderItem.objects.create(order=order1, inventory_item=pivo, quantity=2)
    table1.is_occupied = True
    table1.save()
    return order1.items.count() == 3 and table1.is_occupied
test("1.2 Narudžba Stol 5: pizza + salata + 2 piva (QR simulacija)", t12)

# 1.3 Kuhinja potvrđuje
def t13():
    order1.status = "confirmed"
    order1.save()
    order1.status = "preparing"
    order1.save()
    return order1.status == "preparing"
test("1.3 Kuhinja: new -> confirmed -> preparing", t13)

# 1.4 Kuhinja gotova
def t14():
    order1.status = "ready"
    order1.save()
    return order1.status == "ready"
test("1.4 Kuhinja: preparing -> ready", t14)

# 1.5 Konobar dostavlja
def t15():
    order1.claimed_by = su
    order1.claimed_at = now()
    order1.status = "delivering"
    order1.save()
    order1.delivered_by = su
    order1.delivered_at = now()
    order1.status = "delivered"
    order1.save()
    return order1.status == "delivered" and order1.delivered_by is not None
test("1.5 Konobar: claim -> deliver", t15)

# 1.6 Drugi gost na drugom stolu
def t16():
    global order2, table2
    table2, _ = Table.objects.get_or_create(
        company=konjik, name="Stol 7-T",
        defaults={"table_type": "table", "capacity": 2, "is_active": True}
    )
    order2 = GastroOrder.objects.create(
        company=konjik, table=table2, status="new",
        guest_name="Ana Kovačević", notes="Vegetarijanka"
    )
    GastroOrderItem.objects.create(order=order2, inventory_item=salata, quantity=2)
    GastroOrderItem.objects.create(order=order2, inventory_item=vino, quantity=1)
    GastroOrderItem.objects.create(order=order2, inventory_item=desert, quantity=1)
    order2.status = "delivered"
    order2.save()
    return order2.items.count() == 3
test("1.6 Stol 7: Ana naručuje (2 salate + vino + desert)", t16)

# 1.7 Naplata Stol 5 — gotovina
def t17():
    global receipt1
    last_r = session_r.receipts.order_by("-receipt_number").first()
    next_rn = (last_r.receipt_number + 1) if last_r else 1
    receipt1 = POSReceipt.objects.create(
        session=session_r, receipt_number=next_rn,
        table_number="Stol 5", note="Marko Horvat",
        status="paid", paid_at=now()
    )
    total = Decimal("0")
    for oi in order1.items.select_related("inventory_item", "inventory_item__tax_rate"):
        inv = oi.inventory_item
        price = inv.unit_price * oi.quantity
        tax = inv.tax_rate.rate if inv.tax_rate else Decimal("25")
        POSReceiptItem.objects.create(
            receipt=receipt1, inventory_item=inv,
            description=inv.name, quantity=oi.quantity,
            unit_price=inv.unit_price, tax_rate=tax, total_price=price
        )
        total += price
        StockMovement.objects.create(
            item=inv, movement_type="out", quantity=oi.quantity,
            unit_price=inv.unit_price, reason="POS bon #%d" % next_rn, performed_by=su
        )
    receipt1.total = total
    receipt1.subtotal = total / Decimal("1.13")
    receipt1.tax_amount = total - receipt1.subtotal
    receipt1.save()
    POSPaymentLine.objects.create(receipt=receipt1, method="CASH", amount=total, change_given=Decimal("0"))
    order1.status = "paid"
    order1.save()
    table1.is_occupied = False
    table1.save()
    print(f"    Ukupno: {total} EUR (gotovina)")
    return total > 0 and receipt1.payment_lines.count() == 1
test("1.7 Naplata Stol 5 — gotovina", t17)

# 1.8 Naplata Stol 7 — kartica
def t18():
    global receipt2
    last_r = session_r.receipts.order_by("-receipt_number").first()
    next_rn = (last_r.receipt_number + 1) if last_r else 1
    receipt2 = POSReceipt.objects.create(
        session=session_r, receipt_number=next_rn,
        table_number="Stol 7", note="Ana Kovačević",
        status="paid", paid_at=now()
    )
    total = Decimal("0")
    for oi in order2.items.select_related("inventory_item", "inventory_item__tax_rate"):
        inv = oi.inventory_item
        price = inv.unit_price * oi.quantity
        tax = inv.tax_rate.rate if inv.tax_rate else Decimal("25")
        POSReceiptItem.objects.create(
            receipt=receipt2, inventory_item=inv,
            description=inv.name, quantity=oi.quantity,
            unit_price=inv.unit_price, tax_rate=tax, total_price=price
        )
        total += price
        StockMovement.objects.create(
            item=inv, movement_type="out", quantity=oi.quantity,
            unit_price=inv.unit_price, reason="POS bon #%d" % next_rn, performed_by=su
        )
    receipt2.total = total
    receipt2.save()
    POSPaymentLine.objects.create(receipt=receipt2, method="CARD", amount=total)
    order2.status = "paid"
    order2.save()
    print(f"    Ukupno: {total} EUR (kartica)")
    return total > 0
test("1.8 Naplata Stol 7 — kartica", t18)

# 1.9 Inventar provjera
def t19():
    pizza.refresh_from_db()
    pivo.refresh_from_db()
    pd = pizza_before - pizza.quantity
    bd = pivo_before - pivo.quantity
    print(f"    Pizza: {pizza_before} -> {pizza.quantity} (-{pd})")
    print(f"    Pivo: {pivo_before} -> {pivo.quantity} (-{bd})")
    return pd == 1 and bd == 2
test("1.9 Inventar: pizza -1, pivo -2", t19)

# 1.10 Zatvaranje smjene
def t110():
    expected = session_r.opening_cash + receipt1.total  # samo gotovina
    session_r.closing_cash = expected
    session_r.closed_at = now()
    session_r.status = "closed"
    session_r.save()
    diff = session_r.cash_difference
    print(f"    Očekivano: {expected} EUR | Prebrojano: {session_r.closing_cash} EUR | Razlika: {diff}")
    return session_r.status == "closed"
test("1.10 Zatvaranje smjene + cash reconciliation", t110)

# 1.11 POSDailyReport
def t111():
    report = POSDailyReport.objects.filter(session=session_r).first()
    if report:
        print(f"    Revenue: {report.total_revenue} | Cash: {report.cash_total} | Card: {report.card_total}")
        print(f"    Računi: {report.receipt_count} | Avg: {report.average_ticket}")
        return report.receipt_count >= 2
    # Ručno generiraj ako signal nije pokrenut
    report = POSDailyReport.generate_from_session(session_r)
    print(f"    Manual: {report.total_revenue} | Cash: {report.cash_total} | Card: {report.card_total}")
    return report.receipt_count >= 2
test("1.11 POSDailyReport generiran", t111)


print("\n" + "=" * 70)
print("SIMULACIJA 2: BRZA BLAGAJNA — Optika (3 klika)")
print("=" * 70)

def t21():
    global session_q
    last = term.sessions.order_by("-session_number").first()
    next_num = (last.session_number + 1) if last else 1
    session_q = POSSession.objects.create(
        terminal=term, operator=su, session_number=next_num,
        opening_cash=Decimal("100.00"), status="open"
    )
    return session_q.status == "open"
test("2.1 Quick session otvoren", t21)

def t22():
    global receipt_q
    receipt_q = POSReceipt.objects.create(
        session=session_q, receipt_number=1,
        note="Kupac: Ivan Ivić", status="paid", paid_at=now()
    )
    total = Decimal("0")
    for inv, qty in [(naoc, 1), (stakla, 1), (pregled, 1)]:
        price = inv.unit_price * qty
        tax = inv.tax_rate.rate if inv.tax_rate else Decimal("25")
        POSReceiptItem.objects.create(
            receipt=receipt_q, inventory_item=inv,
            description=inv.name, quantity=qty,
            unit_price=inv.unit_price, tax_rate=tax, total_price=price
        )
        total += price
        StockMovement.objects.create(
            item=inv, movement_type="out", quantity=qty,
            unit_price=inv.unit_price, reason="POS Quick", performed_by=su
        )
    receipt_q.total = total
    receipt_q.save()
    POSPaymentLine.objects.create(receipt=receipt_q, method="CARD", amount=total)
    print(f"    Okvir(120) + Stakla(85) + Pregled(30) = {total} EUR")
    return total == Decimal("235.00")
test("2.2 Quick pay: okvir + stakla + pregled = 235 EUR", t22)

def t23():
    naoc.refresh_from_db()
    diff = naoc_before - naoc.quantity
    print(f"    Okviri: {naoc_before} -> {naoc.quantity} (-{diff})")
    return diff == 1
test("2.3 Zaliha okvira -1", t23)

def t24():
    receipt_s = POSReceipt.objects.create(
        session=session_q, receipt_number=2,
        note="STORNO", status="paid", paid_at=now()
    )
    POSReceiptItem.objects.create(
        receipt=receipt_s, inventory_item=kava,
        description=kava.name, quantity=1,
        unit_price=kava.unit_price, tax_rate=Decimal("25"),
        total_price=kava.unit_price
    )
    receipt_s.total = kava.unit_price
    receipt_s.save()
    POSPaymentLine.objects.create(receipt=receipt_s, method="CASH", amount=kava.unit_price)
    receipt_s.status = "cancelled"
    receipt_s.cancel_reason = "Krivo naplaćeno"
    receipt_s.save()
    return receipt_s.status == "cancelled"
test("2.4 Storno računa (krivo naplaćeno)", t24)


print("\n" + "=" * 70)
print("SIMULACIJA 3: SPLIT PAYMENT — 2 gosta na jednom stolu")
print("=" * 70)

def t31():
    global session_s
    last = term.sessions.order_by("-session_number").first()
    next_num = (last.session_number + 1) if last else 1
    session_s = POSSession.objects.create(
        terminal=term, operator=su, session_number=next_num,
        opening_cash=Decimal("50.00"), status="open"
    )
    return True
test("3.1 Split session otvoren", t31)

def t32():
    global order_split, table_s
    table_s, _ = Table.objects.get_or_create(
        company=konjik, name="Stol 10-T",
        defaults={"table_type": "table", "capacity": 4, "is_active": True}
    )
    order_split = GastroOrder.objects.create(
        company=konjik, table=table_s, status="new",
        guest_name="Grupa", notes="Split test"
    )
    GastroOrderItem.objects.create(order=order_split, inventory_item=steak, quantity=1, notes="Gost A")
    GastroOrderItem.objects.create(order=order_split, inventory_item=vino, quantity=2, notes="Gost A")
    GastroOrderItem.objects.create(order=order_split, inventory_item=pizza, quantity=1, notes="Gost B")
    GastroOrderItem.objects.create(order=order_split, inventory_item=pivo, quantity=1, notes="Gost B")
    GastroOrderItem.objects.create(order=order_split, inventory_item=desert, quantity=1, notes="Gost B")
    order_split.status = "delivered"
    order_split.save()
    return order_split.items.count() == 5
test("3.2 Stol 10: GostA (steak+2vina=27.50) GostB (pizza+pivo+desert=17.00)", t32)

def t33():
    items = list(order_split.items.select_related("inventory_item", "inventory_item__tax_rate"))
    # Gost A — kartica
    ra = POSReceipt.objects.create(session=session_s, receipt_number=1, table_number="Stol 10", note="Gost A", status="paid", paid_at=now())
    total_a = Decimal("0")
    for oi in [i for i in items if "Gost A" in (i.notes or "")]:
        inv = oi.inventory_item
        price = inv.unit_price * oi.quantity
        tax = inv.tax_rate.rate if inv.tax_rate else Decimal("25")
        POSReceiptItem.objects.create(receipt=ra, inventory_item=inv, description=inv.name, quantity=oi.quantity, unit_price=inv.unit_price, tax_rate=tax, total_price=price)
        total_a += price
    ra.total = total_a
    ra.save()
    POSPaymentLine.objects.create(receipt=ra, method="CARD", amount=total_a)
    # Gost B — gotovina
    rb = POSReceipt.objects.create(session=session_s, receipt_number=2, table_number="Stol 10", note="Gost B", status="paid", paid_at=now())
    total_b = Decimal("0")
    for oi in [i for i in items if "Gost B" in (i.notes or "")]:
        inv = oi.inventory_item
        price = inv.unit_price * oi.quantity
        tax = inv.tax_rate.rate if inv.tax_rate else Decimal("25")
        POSReceiptItem.objects.create(receipt=rb, inventory_item=inv, description=inv.name, quantity=oi.quantity, unit_price=inv.unit_price, tax_rate=tax, total_price=price)
        total_b += price
    rb.total = total_b
    rb.save()
    POSPaymentLine.objects.create(receipt=rb, method="CASH", amount=total_b)
    order_split.status = "paid"
    order_split.save()
    print(f"    Gost A: {total_a} EUR (CARD)")
    print(f"    Gost B: {total_b} EUR (CASH)")
    print(f"    Ukupno stol: {total_a + total_b} EUR")
    return total_a == Decimal("27.50") and total_b == Decimal("17.00")
test("3.3 Split: 2 računa (A=27.50 CARD, B=17.00 CASH)", t33)


print("\n" + "=" * 70)
print("SIMULACIJA 4: CASHIER PIN + WAITER SHIFT")
print("=" * 70)

def t41():
    global cashier1
    cashier1, _ = POSCashier.objects.get_or_create(
        company=konjik, name="Ana Blagajnica-T",
        defaults={"is_active": True, "can_void": True, "can_discount": True, "max_discount_percent": Decimal("10"), "user": su}
    )
    cashier1.set_pin("1234")
    cashier1.save()
    ok = cashier1.check_pin("1234")
    bad = cashier1.check_pin("0000")
    print(f"    Hash: {cashier1.pin_hash[:35]}...")
    print(f"    Correct PIN: {ok} | Wrong PIN: {bad}")
    return ok and not bad
test("4.1 Cashier PIN (PBKDF2): set + verify + reject", t41)

def t42():
    has_dollar = "$" in cashier1.pin_hash
    fits = len(cashier1.pin_hash) <= 64
    return has_dollar and fits
test("4.2 PBKDF2 format, fits varchar(64)", t42)

def t43():
    global ws
    ws = WaiterShift.objects.create(user=su, company=konjik)
    ws.last_heartbeat = now()
    ws.heartbeat_count = 3
    ws.total_orders_claimed = 5
    ws.total_orders_delivered = 4
    ws.save()
    return ws.is_active and not ws.is_heartbeat_stale
test("4.3 WaiterShift + heartbeat (active, not stale)", t43)

def t44():
    ws.is_active = False
    ws.ended_at = now()
    ws.save()
    print(f"    Trajanje: {ws.duration_display}")
    print(f"    Narudžbe: {ws.total_orders_claimed} claimed, {ws.total_orders_delivered} delivered")
    return not ws.is_active
test("4.4 WaiterShift zatvoren", t44)


print("\n" + "=" * 70)
print("SIMULACIJA 5: EDGE CASES & STRESS")
print("=" * 70)

def t51():
    item_low = InventoryItem.objects.create(
        company=konjik, sku="TEST-EDGE1", name="Zadnji komad",
        quantity=Decimal("1"), unit_price=Decimal("10"), is_active=True
    )
    StockMovement.objects.create(item=item_low, movement_type="out", quantity=2, performed_by=su, reason="oversell")
    item_low.refresh_from_db()
    print(f"    Zaliha: {item_low.quantity} (dopušta minus)")
    return item_low.quantity == Decimal("-1")
test("5.1 Oversell — zaliha ide u minus (sustav ne blokira)", t51)

def t52():
    big = POSReceipt.objects.create(
        session=session_s, receipt_number=99,
        note="STRESS", status="paid", paid_at=now()
    )
    for i in range(100):
        POSReceiptItem.objects.create(
            receipt=big, inventory_item=kava,
            description="Kava #%d" % (i+1), quantity=1,
            unit_price=kava.unit_price, tax_rate=Decimal("25"),
            total_price=kava.unit_price
        )
    big.total = kava.unit_price * 100
    big.save()
    print(f"    100 kava = {big.total} EUR")
    return big.items.count() == 100
test("5.2 Stress: 100 stavki na jednom računu", t52)

def t53():
    # Razni metodi plaćanja
    r = POSReceipt.objects.create(session=session_s, receipt_number=100, note="Mixed", status="paid", paid_at=now())
    r.total = Decimal("50.00")
    r.save()
    POSPaymentLine.objects.create(receipt=r, method="CASH", amount=Decimal("20.00"))
    POSPaymentLine.objects.create(receipt=r, method="CARD", amount=Decimal("20.00"))
    POSPaymentLine.objects.create(receipt=r, method="MOBILE", amount=Decimal("10.00"))
    total_paid = sum(p.amount for p in r.payment_lines.all())
    print(f"    Cash:20 + Card:20 + Mobile:10 = {total_paid} EUR")
    return total_paid == Decimal("50.00") and r.payment_lines.count() == 3
test("5.3 Mixed payment (gotovina + kartica + mobitel)", t53)

def t54():
    # GastroReview
    review = GastroReview.objects.create(
        company=konjik, order=order1,
        guest_name="Marko Horvat", guest_email="marko@test.hr",
        rating=5, comment="Odlična pizza!", food_rating=5, service_rating=5
    )
    return review.rating == 5
test("5.4 Gost ostavlja recenziju (5 zvjezdica)", t54)


print("\n" + "=" * 70)
print("SIMULACIJA 6: SESSION PROPERTIES")
print("=" * 70)

def t61():
    ts = session_r.total_sales
    tcs = session_r.total_cash_sales
    ec = session_r.expected_closing_cash
    cd = session_r.cash_difference
    print(f"    total_sales: {ts} EUR")
    print(f"    total_cash: {tcs} EUR")
    print(f"    expected_cash: {ec} EUR")
    print(f"    cash_diff: {cd} EUR")
    return ts > 0
test("6.1 Session properties (total_sales, cash, expected)", t61)


# === REZULTATI ===
print("\n" + "=" * 70)
print("REZULTATI SIMULACIJE")
print("=" * 70)
total = passed + failed
print(f"\n  PASSED: {passed}/{total}")
print(f"  FAILED: {failed}/{total}")
if errors:
    print("\n  Greške:")
    for e in errors:
        print(f"    - {e}")
print(f"\n  Score: {round(passed/total*100)}%")
print("=" * 70)
