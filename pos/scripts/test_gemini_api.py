"""Test: Gemini JSON Ugovori A/B/C"""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory

from companies.models import Company
from pos.models import POSSession, POSTerminal

su = User.objects.get(username="superadmin")
konjik = Company.objects.get(name__icontains="Konjik")
factory = RequestFactory()

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        if fn():
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")
    except (ValueError, TypeError) as e:
        failed += 1
        print(f"  ERROR: {name} -> {e}")


print("=" * 70)
print("UGOVOR A: GET /api/pos/items/ — Paginacija artikala")
print("=" * 70)

from pos.views import api_pos_items


def test_a1():
    req = factory.get("/pos/api/pos/items/?page=1&per_page=10")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_items(req)
    data = json.loads(resp.content)
    print(f"    Status: {data['status']}")
    print(f"    Items: {len(data['data']['items'])}")
    print(f"    Page: {data['data']['pagination']['current_page']}/{data['data']['pagination']['total_pages']}")
    print(f"    Total: {data['data']['pagination']['total_items']}")
    print(f"    Has next: {data['data']['pagination']['has_next']}")
    return (data['status'] == 'success' and
            len(data['data']['items']) == 10 and
            data['data']['pagination']['total_items'] > 10)
test("A1: Paginacija (page=1, per_page=10)", test_a1)

def test_a2():
    req = factory.get("/pos/api/pos/items/?search=pizza")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_items(req)
    data = json.loads(resp.content)
    items = data['data']['items']
    print(f"    Search 'pizza': {len(items)} rezultata")
    for it in items:
        print(f"      {it['id']}: {it['name']} | {it['price']} EUR | tax={it['tax_rate']}%")
    return data['status'] == 'success' and any('pizza' in i['name'].lower() for i in items)
test("A2: Pretraga 'pizza'", test_a2)

def test_a3():
    req = factory.get("/pos/api/pos/items/?category=drink&per_page=5")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_items(req)
    data = json.loads(resp.content)
    items = data['data']['items']
    print(f"    Kategorija 'drink': {len(items)} artikala")
    return data['status'] == 'success' and len(items) <= 5
test("A3: Filter po kategoriji 'drink'", test_a3)

# Format check
def test_a4():
    req = factory.get("/pos/api/pos/items/?page=1&per_page=1")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_items(req)
    data = json.loads(resp.content)
    item = data['data']['items'][0]
    required_fields = ['id', 'name', 'price', 'tax_rate', 'is_weighable', 'stock_qty', 'category', 'barcode']
    missing = [f for f in required_fields if f not in item]
    if missing:
        print(f"    MISSING fields: {missing}")
    else:
        print(f"    All required fields present: {required_fields}")
    return len(missing) == 0
test("A4: JSON format ima sva obavezna polja", test_a4)


print("\n" + "=" * 70)
print("UGOVOR B: POST /api/pos/checkout/ — Naplata")
print("=" * 70)

from inventory.models import InventoryItem
from pos.views import api_pos_checkout

pizza = InventoryItem.objects.get(company=konjik, sku="TEST-PIZZA")
kava = InventoryItem.objects.get(company=konjik, sku="TEST-KAVA")

# Nađi ili kreiraj otvorenu sesiju
term = POSTerminal.objects.filter(company=konjik).first()
session = POSSession.objects.filter(terminal=term, status='open').first()
if not session:
    from decimal import Decimal
    last = term.sessions.order_by("-session_number").first()
    next_num = (last.session_number + 1) if last else 1
    session = POSSession.objects.create(
        terminal=term, operator=su, session_number=next_num,
        opening_cash=Decimal("100"), status="open"
    )

pizza_before = pizza.quantity

def test_b1():
    req = factory.post("/pos/api/pos/checkout/", data=json.dumps({
        "session_id": session.pk,
        "payment_method": "CASH",
        "amount_paid": 20,
        "items": [
            {"item_id": pizza.pk, "quantity": 1},
            {"item_id": kava.pk, "quantity": 2}
        ]
    }), content_type="application/json")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_checkout(req)
    data = json.loads(resp.content)
    print(f"    Status: {data['status']}")
    if data['status'] == 'success':
        d = data['data']
        print(f"    Invoice: {d['invoice_number']}")
        print(f"    Total: {d['total']} EUR")
        print(f"    Change: {d['change']} EUR")
        print(f"    ZKI: {d.get('zki', '—')}")
        print(f"    JIR: {d.get('jir', '—')}")
        print(f"    PDF: {d['pdf_url']}")
        return True
    else:
        print(f"    Error: {data.get('error', {})}")
        return False
test("B1: Checkout (pizza + 2 kave = 12.10 EUR, gotovina)", test_b1)

# Provjera zaliha
def test_b2():
    pizza.refresh_from_db()
    diff = float(pizza_before) - float(pizza.quantity)
    print(f"    Pizza stock: {pizza_before} -> {pizza.quantity} (diff={diff})")
    return diff == 1.0
test("B2: Zaliha pizze smanjena za 1", test_b2)

# Checkout s karticom
def test_b3():
    naoc = InventoryItem.objects.get(company=konjik, sku="TEST-NAOC")
    req = factory.post("/pos/api/pos/checkout/", data=json.dumps({
        "session_id": session.pk,
        "payment_method": "CARD",
        "items": [{"item_id": naoc.pk, "quantity": 1, "unit_price": 120.00}],
        "tip_amount": 3.00,
    }), content_type="application/json")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_checkout(req)
    data = json.loads(resp.content)
    print(f"    Total (s napojnicom): {data['data']['total']} EUR")
    return data['status'] == 'success' and float(data['data']['total']) == 123.00
test("B3: Checkout kartica (naočale 120 + napojnica 3 = 123 EUR)", test_b3)


print("\n" + "=" * 70)
print("UGOVOR C: Error handling")
print("=" * 70)

def test_c1():
    req = factory.post("/pos/api/pos/checkout/", data=json.dumps({
        "session_id": 99999,
        "payment_method": "CASH",
        "items": [{"item_id": 1, "quantity": 1}]
    }), content_type="application/json")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_checkout(req)
    data = json.loads(resp.content)
    print(f"    Response: {data}")
    return data['status'] == 'error' and 'code' in data.get('error', {})
test("C1: Error — nepostojeća sesija", test_c1)

def test_c2():
    req = factory.post("/pos/api/pos/checkout/", data=json.dumps({
        "session_id": session.pk,
        "payment_method": "CASH",
        "items": []
    }), content_type="application/json")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_checkout(req)
    data = json.loads(resp.content)
    print(f"    Response: {data}")
    return data['status'] == 'error' and data['error']['code'] == 'EMPTY_CART'
test("C2: Error — prazna košarica", test_c2)

def test_c3():
    req = factory.post("/pos/api/pos/checkout/", data=b"not json", content_type="application/json")
    req.user = su
    with patch("pos.views.get_user_company", return_value=konjik):
        resp = api_pos_checkout(req)
    data = json.loads(resp.content)
    return data['status'] == 'error' and data['error']['code'] == 'INVALID_JSON'
test("C3: Error — invalid JSON", test_c3)


print("\n" + "=" * 70)
total = passed + failed
print(f"REZULTATI: {passed}/{total} PASSED")
if passed == total:
    print("GEMINI JSON UGOVORI: SVE PROLAZI!")
print("=" * 70)
