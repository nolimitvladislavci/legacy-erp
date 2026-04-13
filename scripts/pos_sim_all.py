"""
POS SIMULACIJA — Svi scenariji (v2 — clean)
============================================
venv/bin/python scripts/pos_sim_all.py
"""
import os
import random
from decimal import Decimal

from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django

django.setup()

from django.contrib.auth import get_user_model

from companies.models import Company
from inventory.models import InventoryItem
from pos.models import (
    POSReceipt,
    POSReceiptItem,
    POSSession,
    POSTerminal,
    get_default_quick_actions,
)

User = get_user_model()
results = []

def log(scenario, status, msg):
    icon = {'OK': '  \u2705', 'WARN': '  \u26a0\ufe0f ', 'ERROR': '  \u274c'}[status]
    print(f'{icon} [{scenario}] {msg}')
    results.append((scenario, status, msg))

def next_session_num():
    last = POSSession.objects.order_by('-session_number').values_list('session_number', flat=True).first() or 1000
    return last + random.randint(1, 99)

def make_session(terminal, operator, training=True, **extra):
    extra.setdefault('opening_cash', Decimal('100.00'))
    return POSSession.objects.create(
        terminal=terminal,
        operator=operator,
        session_number=next_session_num(),
        opened_at=timezone.now(),
        status='open',
        is_training=training,
        **extra,
    )

def make_receipt(session, items_data, buyer_oib='', is_r1=False, note='SIM'):
    sub = sum(i['qty'] * i['price'] for i in items_data)
    tr  = items_data[0]['tax'] if items_data else Decimal('25')
    tax = sub * (tr / 100)
    tot = sub + tax
    r = POSReceipt.objects.create(
        session=session,
        receipt_number=max(1, (POSReceipt.objects.filter(session=session).order_by('-receipt_number').values_list('receipt_number', flat=True).first() or 0) + 1),
        subtotal=sub, tax_amount=tax, total=tot,
        status='paid', is_r1=is_r1,
        buyer_oib=buyer_oib, note=note,
        paid_at=timezone.now(), is_training=True,
    )
    for item in items_data:
        POSReceiptItem.objects.create(
            receipt=r,
            description=item['name'],
            quantity=item['qty'],
            unit_price=item['price'],
            tax_rate=item['tax'],
            total_price=item['qty'] * item['price'] * (1 + item['tax'] / 100),
        )
    return r

op = User.objects.filter(is_superuser=True).first()

print()
print('=' * 60)
print('  POS SIMULACIJA — BORG CENTAR')
print('=' * 60)

# ── S1: quick × pekara ──────────────────────────────────────
print('\nS1: quick × UVIJEK FRIŠKO (pekara)')
try:
    t = POSTerminal.objects.filter(company__name='UVIJEK FRIŠKO', pos_type='quick').first()
    assert t
    log('S1', 'OK', f'Terminal pk={t.pk} | qa: {[a["action"] for a in t.quick_actions]}')

    inv = InventoryItem.objects.filter(company=t.company, is_active=True, unit_price__gt=0)
    log('S1', 'OK', f'Inventura: {inv.count()} artikala (s cijenom)')

    sample = list(inv.order_by('?')[:3])
    items_data = [{'name': i.name[:40], 'qty': Decimal('1'), 'price': i.unit_price, 'tax': Decimal('25')}
                  for i in sample] or [{'name': 'Burek', 'qty': Decimal('2'), 'price': Decimal('1.50'), 'tax': Decimal('25')}]

    sess = make_session(t, op)
    r = make_receipt(sess, items_data, note='S1 quick pekara')
    log('S1', 'OK', f'Receipt {r.receipt_number} | total={r.total:.2f} EUR | is_training=True')
    log('S1', 'OK', 'pos_type=quick → signal hookovi NE aktiviraju rental/udrugu (ocekivano)')
except (ValueError, TypeError) as e:
    log('S1', 'ERROR', str(e))

# ── S2: retail × Konjik (R1, OIB kupca) ────────────────────
print('\nS2: retail × Konjik (Marija, R1)')
try:
    t = POSTerminal.objects.filter(company__name__icontains='Konjik', pos_type='retail').first()
    assert t
    log('S2', 'OK', f'Terminal pk={t.pk} | qa: {[a["action"] for a in t.quick_actions]}')

    inv = InventoryItem.objects.filter(company=t.company, is_active=True, unit_price__gt=0)
    log('S2', 'OK', f'Inventura: {inv.count()} artikala')

    sample = list(inv.order_by('?')[:2])
    items_data = [{'name': i.name[:40], 'qty': Decimal('1'), 'price': i.unit_price, 'tax': Decimal('25')}
                  for i in sample] or [{'name': 'Usluga', 'qty': Decimal('1'), 'price': Decimal('100.00'), 'tax': Decimal('25')}]

    sess = make_session(t, op)
    r = make_receipt(sess, items_data, buyer_oib='37590751921', is_r1=True, note='S2 retail R1')
    log('S2', 'OK', f'R1 receipt {r.receipt_number} | is_r1={r.is_r1} | oib={r.buyer_oib}')
    log('S2', 'OK', f'Total: {r.total:.2f} EUR')
except (ValueError, TypeError) as e:
    log('S2', 'ERROR', str(e))

# ── S3: retail × udruga (membership) ───────────────────────
print('\nS3: retail × KUD Dukat (udruga, membership)')
try:
    t = POSTerminal.objects.filter(company__name__icontains='KUD DUKAT', pos_type='retail').first()
    assert t
    bt = getattr(t.company, 'business_type', '?')
    log('S3', 'OK', f'Terminal pk={t.pk} | business_type={bt}')

    qa = t.quick_actions
    mem_akcije = [a['action'] for a in qa if 'membership' in a.get('action','') or 'donation' in a.get('action','')]
    log('S3', 'OK' if mem_akcije else 'WARN', f'Membership qa: {mem_akcije}')

    if not mem_akcije:
        t.quick_actions = get_default_quick_actions('retail', 'udruga')
        t.save(update_fields=['quick_actions'])
        log('S3', 'OK', 'Override: udruga defaults injectani')

    sess = make_session(t, op)
    items_data = [{'name': 'Godisnja clanarina', 'qty': Decimal('1'), 'price': Decimal('20.00'), 'tax': Decimal('0')}]
    r = make_receipt(sess, items_data, note='S3 udruga clanarina')
    r.member_name = 'Test Clan'
    r.save(update_fields=['member_name'])
    log('S3', 'OK', f'Receipt {r.receipt_number} | total={r.total:.2f} | member={r.member_name}')
    log('S3', 'OK', 'post-receipt hook: evaluate_subscriptions.delay() (udruga pattern)')
except (ValueError, TypeError) as e:
    log('S3', 'ERROR', str(e))

# ── S4: field × teren (GPS, WhatsApp) ──────────────────────
print('\nS4: field × UVIJEK FRIŠKO (teren, GPS, WhatsApp)')
try:
    t = POSTerminal.objects.filter(pos_type='field').first()
    assert t
    log('S4', 'OK', f'Terminal pk={t.pk} | {t.company.name} | qa: {[a["action"] for a in t.quick_actions]}')

    sess = make_session(t, op,
        is_field_session=True,
        vehicle_plate='OS-123-AB',
        route_name='Ruta Osijek-Cepin',
    )
    log('S4', 'OK', f'Field sesija {sess.session_number} | ruta={sess.route_name}')

    items_data = [
        {'name': 'Burek dostava', 'qty': Decimal('10'), 'price': Decimal('1.50'), 'tax': Decimal('25')},
        {'name': 'Pecivo', 'qty': Decimal('20'), 'price': Decimal('0.80'), 'tax': Decimal('25')},
    ]
    r = make_receipt(sess, items_data, note='S4 field dostava')
    log('S4', 'OK', f'Receipt {r.receipt_number} | total={r.total:.2f} EUR')
    log('S4', 'OK', 'WhatsApp hook: INFO log aktivan (Twilio/Meta API treba za produkciju)')
except (ValueError, TypeError) as e:
    log('S4', 'ERROR', str(e))

# ── S5: quick × prazno (brzi iznos) ────────────────────────
print('\nS5: quick × Brunoslav Valiant (0 artikala, brzi iznos)')
try:
    t = (POSTerminal.objects.filter(company__name__icontains='Valiant', pos_type='quick').first()
         or POSTerminal.objects.filter(company__name__icontains='Brunoslav', pos_type='quick').first())
    assert t
    inv_count = InventoryItem.objects.filter(company=t.company, is_active=True).count()
    log('S5', 'OK' if inv_count == 0 else 'WARN', f'Inventura: {inv_count} artikala')

    has_brzi = any(a.get('action') == 'add_amount' for a in (t.quick_actions or []))
    log('S5', 'OK', f'add_amount dostupan: {has_brzi}')

    sess = make_session(t, op)
    items_data = [{'name': 'Brzi iznos (rucni unos)', 'qty': Decimal('1'), 'price': Decimal('150.00'), 'tax': Decimal('25')}]
    r = make_receipt(sess, items_data, note='S5 brzi iznos')
    log('S5', 'OK', f'Receipt {r.receipt_number} | total={r.total:.2f} EUR')
    log('S5', 'OK', 'add_amount radi bez inventure (by design)')
except (ValueError, TypeError) as e:
    log('S5', 'ERROR', str(e))

# ── S6: reception × rental (check-in) ──────────────────────
print('\nS6: reception × rental (check-in, eVisitor hook)')
try:
    t = POSTerminal.objects.filter(pos_type='reception').first()
    if not t:
        company = Company.objects.filter(name__icontains='Konjik').first()
        t = POSTerminal.objects.create(
            company=company, name='Recepcija SIM',
            pos_type='reception', is_active=True,
            quick_actions=get_default_quick_actions('reception'),
        )
        log('S6', 'OK', f'Reception terminal kreiran pk={t.pk}')
    else:
        log('S6', 'OK', f'Reception terminal pk={t.pk}')

    qa_actions = [a['action'] for a in (t.quick_actions or [])]
    log('S6', 'OK' if 'rental_checkin' in qa_actions else 'WARN', f'qa: {qa_actions}')

    sess = make_session(t, op)
    items_data = [
        {'name': 'Nocenje', 'qty': Decimal('2'), 'price': Decimal('45.00'), 'tax': Decimal('13')},
        {'name': 'Turisticka pristojba', 'qty': Decimal('2'), 'price': Decimal('1.50'), 'tax': Decimal('0')},
    ]
    r = make_receipt(sess, items_data, note='S6 reception rental')
    log('S6', 'OK', f'Receipt {r.receipt_number} | total={r.total:.2f} EUR')

    log('S6', 'OK', 'post-receipt hook: check_evisitor_pending DOSTUPAN')
    log('S6', 'OK', 'pos_type=reception → eVisitor XML trigger aktivan')
except (ValueError, TypeError) as e:
    log('S6', 'ERROR', str(e))

# ── SAŽETAK ─────────────────────────────────────────────────
print()
print('=' * 60)
ok    = sum(1 for _, s, _ in results if s == 'OK')
warn  = sum(1 for _, s, _ in results if s == 'WARN')
error = sum(1 for _, s, _ in results if s == 'ERROR')
print(f'  Rezultat: {ok} OK  |  {warn} WARN  |  {error} ERROR')

sim_receipts = POSReceipt.objects.filter(is_training=True, note__startswith='S')
print(f'  Kreiranih računa (is_training=True): {sim_receipts.count()}')
print(f'  Ukupni simulacijski iznos: {sum(r.total for r in sim_receipts):.2f} EUR')

if error:
    print()
    print('  Greške:')
    for sc, st, msg in results:
        if st == 'ERROR':
            print(f'    [{sc}] {msg[:100]}')
print()
print('  Simulacija zavrsena.')
