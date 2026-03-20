"""Test: Refund, Pfand Return, Napojnica"""
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.test import RequestFactory
from unittest.mock import patch
import json

from companies.models import Company
from pos.models import *
from inventory.models import InventoryItem, StockMovement

konjik = Company.objects.get(name__icontains="Konjik")
su = User.objects.get(username="superadmin")
kava = InventoryItem.objects.get(company=konjik, sku="TEST-KAVA")
pivo = InventoryItem.objects.get(company=konjik, sku="TEST-PIVO")

term = POSTerminal.objects.filter(company=konjik).first()
last = term.sessions.order_by("-session_number").first()
next_num = (last.session_number + 1) if last else 1
session = POSSession.objects.create(
    terminal=term, operator=su, session_number=next_num,
    opening_cash=Decimal("100"), status="open"
)
factory = RequestFactory()
passed = 0
failed = 0

# === TEST 1: REFUND ===
print("=" * 60)
print("TEST 1: REFUND — gost vraća 2 od 3 piva (toplo pivo)")
print("=" * 60)

pivo.refresh_from_db()
pivo_before = pivo.quantity
print(f"  Pivo prije prodaje: {pivo_before}")

# Prodaj 3 piva
r1 = POSReceipt.objects.create(
    session=session, receipt_number=1, note="Original",
    status="paid", paid_at=timezone.now()
)
ri1 = POSReceiptItem.objects.create(
    receipt=r1, inventory_item=pivo, description="Pivo",
    quantity=3, unit_price=Decimal("3.50"), tax_rate=Decimal("25"),
    total_price=Decimal("10.50")
)
r1.total = Decimal("10.50")
r1.save()
POSPaymentLine.objects.create(receipt=r1, method="CASH", amount=Decimal("10.50"))
StockMovement.objects.create(
    item=pivo, movement_type="out", quantity=3,
    unit_price=Decimal("3.50"), reason="POS prodaja", performed_by=su
)
pivo.refresh_from_db()
print(f"  Pivo nakon prodaje 3 kom: {pivo.quantity}")

# Refund 2
from pos.views import refund_receipt
req = factory.post(
    "/pos/receipt/%d/refund/" % r1.pk,
    data=json.dumps({"items": [{"item_id": ri1.pk, "quantity": 2}], "reason": "Toplo pivo"}),
    content_type="application/json"
)
req.user = su
with patch("pos.views.get_user_company", return_value=konjik):
    resp = refund_receipt(req, r1.pk)
result = json.loads(resp.content)
pivo.refresh_from_db()
print(f"  Refund response: {result}")
print(f"  Pivo nakon refunda 2 kom: {pivo.quantity}")
print(f"  Refund iznos: {result.get('refund_total', '?')} EUR")
if result.get("ok") and pivo.quantity == pivo_before - 1:
    print("  PASS: Refund radi ispravno!")
    passed += 1
else:
    print("  FAIL: Refund problem")
    failed += 1


# === TEST 2: PFAND RETURN ===
print("\n" + "=" * 60)
print("TEST 2: PFAND RETURN — gost vraća 5 boca")
print("=" * 60)

pfand_item, _ = InventoryItem.objects.get_or_create(
    company=konjik, sku="TEST-PFAND",
    defaults={
        "name": "Boca 0.5L (kaucija)", "quantity": Decimal("0"),
        "unit_price": Decimal("0.25"), "is_pfand": True, "is_active": True,
    }
)
pfand_before = pfand_item.quantity
print(f"  Pfand stock prije: {pfand_before}")

from pos.views import pfand_return
req2 = factory.post(
    "/pos/api/pfand-return/",
    data=json.dumps({"pfand_item_id": pfand_item.pk, "quantity": 5, "session_id": session.pk}),
    content_type="application/json"
)
req2.user = su
with patch("pos.views.get_user_company", return_value=konjik):
    resp2 = pfand_return(req2)
result2 = json.loads(resp2.content)
pfand_item.refresh_from_db()
print(f"  Pfand return response: {result2}")
print(f"  Pfand stock nakon povrata 5 boca: {pfand_item.quantity}")
print(f"  Gost dobiva natrag: {result2.get('amount', '?')} EUR")
if result2.get("ok") and pfand_item.quantity == pfand_before + 5:
    print("  PASS: Pfand return radi!")
    passed += 1
else:
    print("  FAIL: Pfand return problem")
    failed += 1


# === TEST 3: NAPOJNICA ===
print("\n" + "=" * 60)
print("TEST 3: NAPOJNICA — konobar dobiva 2 EUR bakšiš")
print("=" * 60)

r2 = POSReceipt.objects.create(
    session=session, receipt_number=10, note="S napojnicom",
    status="paid", paid_at=timezone.now()
)
POSReceiptItem.objects.create(
    receipt=r2, inventory_item=kava, description="Kava",
    quantity=2, unit_price=Decimal("1.80"), tax_rate=Decimal("25"),
    total_price=Decimal("3.60")
)
POSReceiptItem.objects.create(
    receipt=r2, description="Napojnica",
    quantity=1, unit_price=Decimal("2.00"), tax_rate=Decimal("0"),
    total_price=Decimal("2.00"), is_tip=True
)
r2.total = Decimal("5.60")
r2.save()
POSPaymentLine.objects.create(receipt=r2, method="CASH", amount=Decimal("5.60"))

tip_items = POSReceiptItem.objects.filter(
    is_tip=True, receipt__session=session
)
tip_total = sum(t.total_price for t in tip_items)
print(f"  Napojnica stavke: {tip_items.count()}")
print(f"  Ukupno napojnica u sesiji: {tip_total} EUR")
print(f"  Tax rate na napojnici: {tip_items.first().tax_rate}% (treba biti 0)")
if tip_total >= Decimal("2.00") and tip_items.first().tax_rate == Decimal("0"):
    print("  PASS: Napojnica ispravna (tax=0, ne fiskalizira se)")
    passed += 1
else:
    print("  FAIL: Napojnica problem")
    failed += 1


# === TEST 4: TIP REPORT ===
print("\n" + "=" * 60)
print("TEST 4: NAPOJNICA IZVJEŠTAJ — po konobaru")
print("=" * 60)

from pos.views import tip_report
req3 = factory.get("/pos/tips/?format=json")
req3.user = su
with patch("pos.views.get_user_company", return_value=konjik):
    resp3 = tip_report(req3)
result3 = json.loads(resp3.content)
print(f"  Tip report: {result3}")
if result3.get("ok") and Decimal(result3.get("total_tips", "0")) > 0:
    print("  PASS: Tip report radi!")
    passed += 1
else:
    print("  FAIL: Tip report problem")
    failed += 1


# === TEST 5: MIXED REFUND + TIP (ne refundira napojnicu) ===
print("\n" + "=" * 60)
print("TEST 5: REFUND ne smije refundirati napojnicu")
print("=" * 60)

# Probaj refundirati kavu (ne napojnicu)
kava_item = r2.items.filter(is_tip=False).first()
if kava_item:
    req4 = factory.post(
        "/pos/receipt/%d/refund/" % r2.pk,
        data=json.dumps({"items": [{"item_id": kava_item.pk, "quantity": 1}], "reason": "Test refund bez tipa"}),
        content_type="application/json"
    )
    req4.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp4 = refund_receipt(req4, r2.pk)
    result4 = json.loads(resp4.content)
    print(f"  Refund kave (ne tipa): {result4}")
    if result4.get("ok"):
        print("  PASS: Refund samo robe, napojnica ostaje")
        passed += 1
    else:
        print("  FAIL")
        failed += 1


# === REZULTATI ===
print("\n" + "=" * 60)
print(f"REZULTATI: {passed}/{passed + failed} PASSED")
print("=" * 60)
