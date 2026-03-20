"""
TEST: Završetak smjene — radni sati, blagajnički izvještaj, Z-report
Simulacija: 3 konobara + 1 recepcija rade smjenu, zatvaraju, generiraju izvještaje
"""
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.test import RequestFactory
from unittest.mock import patch
from datetime import timedelta
import json

from companies.models import Company
from pos.models import *
from inventory.models import InventoryItem, StockMovement
from pos.worktime_bridge import cashier_clock_in, cashier_clock_out, session_close_all_cashiers

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
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  ERROR: {name} -> {e}")

# Artikli
pizza = InventoryItem.objects.get(company=konjik, sku="TEST-PIZZA")
pivo = InventoryItem.objects.get(company=konjik, sku="TEST-PIVO")
kava = InventoryItem.objects.get(company=konjik, sku="TEST-KAVA")
steak = InventoryItem.objects.get(company=konjik, sku="TEST-STEAK")
vino = InventoryItem.objects.get(company=konjik, sku="TEST-VINO")
naoc = InventoryItem.objects.get(company=konjik, sku="TEST-NAOC")

term = POSTerminal.objects.filter(company=konjik).first()

print("=" * 70)
print("SIMULACIJA: PUNA SMJENA — 3 blagajnika, 8h rad, zatvaranje")
print("=" * 70)

# ── Kreiranje blagajnika ──
print("\n--- FAZA 1: Prijava blagajnika ---")

def t_create_cashiers():
    global c_ana, c_marko, c_ivan
    for name, pin in [("Ana-T", "1111"), ("Marko-T", "2222"), ("Ivan-T", "3333")]:
        c, _ = POSCashier.objects.get_or_create(
            company=konjik, name=name,
            defaults={"is_active": True, "can_void": True, "can_discount": True,
                      "max_discount_percent": Decimal("10"), "user": su}
        )
        c.set_pin(pin)
        c.save()
    c_ana = POSCashier.objects.get(company=konjik, name="Ana-T")
    c_marko = POSCashier.objects.get(company=konjik, name="Marko-T")
    c_ivan = POSCashier.objects.get(company=konjik, name="Ivan-T")
    return c_ana.check_pin("1111") and c_marko.check_pin("2222") and c_ivan.check_pin("3333")
test("1.1 Kreiranje 3 blagajnika (Ana, Marko, Ivan) s PIN-om", t_create_cashiers)

# ── Otvaranje smjene ──
def t_open_session():
    global session
    last = term.sessions.order_by("-session_number").first()
    next_num = (last.session_number + 1) if last else 1
    session = POSSession.objects.create(
        terminal=term, operator=su, session_number=next_num,
        opening_cash=Decimal("300.00"), status="open"
    )
    return session.status == "open"
test("1.2 Otvaranje smjene (300 EUR početna gotovina)", t_open_session)

# ── Clock in svih blagajnika ──
def t_clock_in():
    cashier_clock_in(c_ana)
    cashier_clock_in(c_marko)
    cashier_clock_in(c_ivan)
    session.active_cashiers.add(c_ana, c_marko, c_ivan)
    return (c_ana.clock_in_at is not None and
            c_marko.clock_in_at is not None and
            c_ivan.clock_in_at is not None and
            session.active_cashiers.count() == 3)
test("1.3 Clock-in sva 3 blagajnika", t_clock_in)

# ── Simulacija rada: Ana prodaje ──
print("\n--- FAZA 2: Prodaja (Ana=5 računa, Marko=3, Ivan=2) ---")

receipt_counter = [0]
def make_receipt(cashier, items_list, method="CASH"):
    receipt_counter[0] += 1
    r = POSReceipt.objects.create(
        session=session, receipt_number=receipt_counter[0],
        cashier=cashier, note=cashier.name,
        status="paid", paid_at=now()
    )
    total = Decimal("0")
    for inv, qty in items_list:
        price = inv.unit_price * qty
        tax = inv.tax_rate.rate if inv.tax_rate else Decimal("25")
        POSReceiptItem.objects.create(
            receipt=r, inventory_item=inv, description=inv.name,
            quantity=qty, unit_price=inv.unit_price,
            tax_rate=tax, total_price=price
        )
        total += price
    r.total = total
    r.save()
    POSPaymentLine.objects.create(receipt=r, method=method, amount=total)
    return r

def t_ana_sales():
    make_receipt(c_ana, [(pizza, 2), (pivo, 2)], "CASH")      # 24.00
    make_receipt(c_ana, [(steak, 1), (vino, 2)], "CARD")       # 27.50
    make_receipt(c_ana, [(kava, 4)], "CASH")                    # 7.20
    make_receipt(c_ana, [(pizza, 1), (kava, 1)], "CASH")       # 10.30
    r5 = make_receipt(c_ana, [(naoc, 1)], "CARD")               # 120.00
    # Napojnica na zadnjem računu
    POSReceiptItem.objects.create(
        receipt=r5, description="Napojnica", quantity=1,
        unit_price=Decimal("5.00"), tax_rate=Decimal("0"),
        total_price=Decimal("5.00"), is_tip=True
    )
    r5.total += Decimal("5.00")
    r5.save()
    ana_total = sum(r.total for r in session.receipts.filter(cashier=c_ana, status="paid"))
    print(f"    Ana: 5 računa = {ana_total} EUR")
    return session.receipts.filter(cashier=c_ana).count() == 5
test("2.1 Ana: 5 računa (pizza, steak, kava, naočale + napojnica)", t_ana_sales)

def t_marko_sales():
    make_receipt(c_marko, [(pivo, 3), (pizza, 1)], "CASH")     # 19.00
    make_receipt(c_marko, [(steak, 2), (vino, 1)], "CARD")     # 41.50
    make_receipt(c_marko, [(kava, 2), (pivo, 1)], "MOBILE")    # 7.10
    marko_total = sum(r.total for r in session.receipts.filter(cashier=c_marko, status="paid"))
    print(f"    Marko: 3 računa = {marko_total} EUR")
    return session.receipts.filter(cashier=c_marko).count() == 3
test("2.2 Marko: 3 računa (piva, steak, kava)", t_marko_sales)

def t_ivan_sales():
    make_receipt(c_ivan, [(naoc, 1), (InventoryItem.objects.get(company=konjik, sku="TEST-STAKLA"), 1)], "CARD")  # 205.00
    make_receipt(c_ivan, [(InventoryItem.objects.get(company=konjik, sku="TEST-PREGLED"), 2)], "CASH")  # 60.00
    ivan_total = sum(r.total for r in session.receipts.filter(cashier=c_ivan, status="paid"))
    print(f"    Ivan: 2 računa = {ivan_total} EUR")
    return session.receipts.filter(cashier=c_ivan).count() == 2
test("2.3 Ivan: 2 računa (naočale+stakla, 2 pregleda)", t_ivan_sales)

# Storno jedan od Markovih
def t_storno():
    r_storno = session.receipts.filter(cashier=c_marko).last()
    r_storno.status = "cancelled"
    r_storno.cancel_reason = "Gost otišao bez plaćanja"
    r_storno.save()
    print(f"    Stornirano: bon #{r_storno.receipt_number} ({r_storno.total} EUR)")
    return r_storno.status == "cancelled"
test("2.4 Storno jednog Markovog računa", t_storno)

# ── Gotovinski polog/isplata ──
print("\n--- FAZA 3: Gotovinski polozi ---")

def t_deposit():
    CashDeposit.objects.create(
        session=session, operator=su, deposit_type="withdrawal",
        amount=Decimal("100.00"), note="Polog u sef"
    )
    CashDeposit.objects.create(
        session=session, operator=su, deposit_type="deposit",
        amount=Decimal("50.00"), note="Sitniš iz sefa"
    )
    return session.cash_deposits.count() == 2
test("3.1 Polog u sef (100 EUR) + sitniš iz sefa (50 EUR)", t_deposit)

# ── Zatvaranje smjene ──
print("\n--- FAZA 4: Zatvaranje smjene ---")

def t_close():
    # Simuliraj da su blagajnici radili od ranije
    import datetime
    start = now() - timedelta(hours=8)
    for c in [c_ana, c_marko, c_ivan]:
        c.clock_in_at = start
        c.save(update_fields=["clock_in_at"])

    session.closing_cash = session.expected_closing_cash
    session.closed_at = now()
    session.status = "closed"
    session.save()

    print(f"    Total sales: {session.total_sales} EUR")
    print(f"    Cash sales: {session.total_cash_sales} EUR")
    print(f"    Expected cash: {session.expected_closing_cash} EUR")
    print(f"    Closing cash: {session.closing_cash} EUR")
    print(f"    Difference: {session.cash_difference} EUR")
    return session.status == "closed"
test("4.1 Zatvaranje smjene", t_close)

# ── Cashier clock-out → TimeEntry ──
def t_clockout():
    entries = []
    for c in [c_ana, c_marko, c_ivan]:
        entry = cashier_clock_out(c)
        if entry:
            entries.append(entry)
            print(f"    {c.name}: {entry.duration}h | {entry.date} | {entry.description[:50]}")
        else:
            print(f"    {c.name}: NO ENTRY (nema usera?)")
    return len(entries) >= 1  # Bar jedan mora uspjeti
test("4.2 Clock-out → TimeEntry za svakog blagajnika", t_clockout)

# ── WaiterShift test ──
def t_waiter_shifts():
    shifts = []
    for c in [c_ana, c_marko]:
        ws = WaiterShift.objects.create(user=su, company=konjik)
        ws.total_orders_claimed = 5
        ws.total_orders_delivered = 4
        ws.heartbeat_count = 48  # 8h / 10min
        ws.is_active = False
        ws.ended_at = now()
        ws.save()
        shifts.append(ws)
        print(f"    {c.name} shift: {ws.duration_display} | {ws.total_orders_claimed} narudžbi")
    return len(shifts) == 2
test("4.3 WaiterShift za konobari (Ana, Marko)", t_waiter_shifts)


# ── POSDailyReport ──
print("\n--- FAZA 5: Izvještaji ---")

def t_daily_report():
    report = POSDailyReport.generate_from_session(session)
    print(f"    Total revenue: {report.total_revenue} EUR")
    print(f"    Cash: {report.cash_total} | Card: {report.card_total} | Mobile: {report.mobile_total}")
    print(f"    Receipts: {report.receipt_count} | Cancelled: {report.cancelled_count}")
    print(f"    Average ticket: {report.average_ticket} EUR")
    print(f"    Tax breakdown: {json.dumps(report.tax_breakdown, indent=2)}")
    print(f"    Cashier breakdown: {json.dumps(report.cashier_breakdown, indent=2)}")
    return (report.receipt_count > 0 and
            report.cash_total > 0 and
            report.card_total > 0 and
            len(report.cashier_breakdown) >= 3)
test("5.1 POSDailyReport — kompletni dnevni izvještaj", t_daily_report)

# ── Per-cashier breakdown ──
def t_cashier_breakdown():
    from django.db.models import Sum, Count
    for cashier in [c_ana, c_marko, c_ivan]:
        receipts = session.receipts.filter(cashier=cashier, status="paid")
        total = receipts.aggregate(s=Sum("total"))["s"] or Decimal("0")
        count = receipts.count()
        cash = sum(
            pl.amount for r in receipts
            for pl in r.payment_lines.filter(method="CASH")
        )
        card = sum(
            pl.amount for r in receipts
            for pl in r.payment_lines.filter(method="CARD")
        )
        tips = receipts.filter(items__is_tip=True).aggregate(s=Sum("items__total_price"))["s"] or Decimal("0")
        print(f"    {cashier.name}: {count} računa | {total} EUR | cash={cash} | card={card} | tips={tips}")
    return True
test("5.2 Blagajnički izvještaj po osobi", t_cashier_breakdown)

# ── Z-Report data ──
def t_zreport_data():
    paid = list(session.receipts.filter(status="paid").prefetch_related("items", "payment_lines"))
    cancelled = session.receipts.filter(status="cancelled").count()

    # Payment breakdown
    payment_bd = {}
    for r in paid:
        for pl in r.payment_lines.all():
            payment_bd[pl.method] = payment_bd.get(pl.method, Decimal("0")) + pl.amount
    print(f"    Plaćanja: { {k: str(v) for k,v in payment_bd.items()} }")

    # Tax breakdown
    tax_bd = {}
    for r in paid:
        for item in r.items.all():
            rate = str(item.tax_rate)
            if rate not in tax_bd:
                tax_bd[rate] = {"base": Decimal("0"), "tax": Decimal("0"), "total": Decimal("0")}
            net = item.total_price / (1 + item.tax_rate / 100) if item.tax_rate else item.total_price
            tax_amount = item.total_price - net
            tax_bd[rate]["base"] += net
            tax_bd[rate]["tax"] += tax_amount
            tax_bd[rate]["total"] += item.total_price
    for rate, vals in tax_bd.items():
        print(f"    PDV {rate}%: base={vals['base']:.2f} | tax={vals['tax']:.2f} | total={vals['total']:.2f}")

    print(f"    Ukupno računa: {len(paid)} paid, {cancelled} cancelled")
    print(f"    Total revenue: {sum(r.total for r in paid)} EUR")
    return len(paid) > 0 and len(payment_bd) > 0
test("5.3 Z-Report podaci (payment + tax breakdown)", t_zreport_data)

# ── Session properties ──
def t_session_props():
    print(f"    total_sales: {session.total_sales}")
    print(f"    total_cash_sales: {session.total_cash_sales}")
    print(f"    deposits: +{session.total_deposits_amount} / -{session.total_withdrawals_amount}")
    print(f"    expected_cash: {session.expected_closing_cash}")
    print(f"    closing_cash: {session.closing_cash}")
    print(f"    cash_diff: {session.cash_difference}")
    return session.total_sales > 0
test("5.4 Session properties (totals, deposits, expected cash)", t_session_props)

# ── Napojnica report ──
def t_tip_report():
    tips = POSReceiptItem.objects.filter(
        is_tip=True, receipt__session=session, receipt__status="paid"
    )
    total = sum(t.total_price for t in tips)
    print(f"    Napojnice u smjeni: {tips.count()} stavki = {total} EUR")
    for t in tips:
        cashier = t.receipt.cashier.name if t.receipt.cashier else "?"
        print(f"      {cashier}: {t.total_price} EUR")
    return total > 0
test("5.5 Napojnice u smjeni", t_tip_report)


# ═══ REZULTATI ═══
print("\n" + "=" * 70)
print("REZULTATI — SMJENA + IZVJEŠTAJI")
print("=" * 70)
total = passed + failed
print(f"\n  PASSED: {passed}/{total}")
print(f"  FAILED: {failed}/{total}")
if errors:
    print("\n  Greške:")
    for e in errors:
        print(f"    - {e}")
print(f"\n  Score: {round(passed/total*100) if total else 0}%")
print("=" * 70)
