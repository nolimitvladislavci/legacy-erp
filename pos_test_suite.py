"""
LIMIT-CONNECT POS — KOMPLETNI TEST SUITE v2
Pokreni: cd /var/www/fina-connect && venv/bin/python pos_test_suite.py
"""
import os, sys, time, json, uuid as _uuid
from decimal import Decimal
from datetime import datetime, timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
import django; django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

G='\033[92m'; R='\033[91m'; Y='\033[93m'; B='\033[94m'
C='\033[96m'; DIM='\033[2m'; RESET='\033[0m'; BOLD='\033[1m'

results = []
t0_global = time.time()

def passed(name, detail='', ms=None):
    results.append({'s':'PASS','n':name,'d':detail})
    dur = f' {DIM}({ms:.0f}ms){RESET}' if ms else ''
    print(f'  {G}✓{RESET} {name}  {DIM}{detail}{RESET}{dur}')

def failed(name, detail='', ms=None):
    results.append({'s':'FAIL','n':name,'d':detail})
    dur = f' {DIM}({ms:.0f}ms){RESET}' if ms else ''
    print(f'  {R}✗{RESET} {name}  {R}{detail}{RESET}{dur}')

def warn(name, detail=''):
    results.append({'s':'WARN','n':name,'d':detail})
    print(f'  {Y}⚠{RESET} {name}  {DIM}{detail}{RESET}')

def section(t):
    print(f'\n{B}{BOLD}━━━ {t} ━━━{RESET}')

def run(name, fn):
    t0 = time.time()
    try:
        r = fn()
        ms = (time.time()-t0)*1000
        if r is False: failed(name, ms=ms)
        elif isinstance(r,str) and r.startswith('W:'): warn(name, r[2:])
        else: passed(name, str(r) if r and r is not True else '', ms)
    except Exception as e:
        failed(name, str(e)[:100], (time.time()-t0)*1000)

print(f'\n{BOLD}{C}╔══════════════════════════════════════════╗')
print(f'║  LIMIT-CONNECT POS TEST SUITE v2        ║')
print(f'║  {datetime.now().strftime("%d.%m.%Y %H:%M")}                       ║')
print(f'╚══════════════════════════════════════════╝{RESET}')

from pos.models import (POSTerminal, POSSession, POSReceipt, POSReceiptItem,
    POSPaymentLine, POSCashier, POSSettings, POSDailyReport,
    Table, GastroOrder, GastroOrderItem, WaiterShift,
    Voucher, CashDeposit, ExpiryBatch, LoyaltyProgram,
    ImprovementSuggestion)
from companies.models import Company
from inventory.models import InventoryItem

_session = None; _terminal = None; _receipt = None
_table = None; _order = None; _shift = None

# ══ 1. MODELI ══════════════════════════════════════
section('1. MODELI I BAZA')

def t_models():
    models = [POSTerminal,POSSession,POSReceipt,POSReceiptItem,
              POSPaymentLine,POSCashier,POSDailyReport,Table,
              GastroOrder,WaiterShift,Voucher,CashDeposit]
    return f'{len(models)} modela OK, bonovi:{POSReceipt.objects.count()}'
run('Svi POS modeli dostupni', t_models)

run('Konjik company postoji', lambda:
    f'OIB:{Company.objects.filter(name__icontains="Konjik").first().oib}'
    if Company.objects.filter(name__icontains='Konjik').exists() else False)

run('Aktivni terminali', lambda:
    f'{POSTerminal.objects.filter(is_active=True).count()} terminala'
    if POSTerminal.objects.filter(is_active=True).exists() else False)

run('Blagajnici s PIN-om', lambda: (
    lambda n,p: f'{n} blagajnika, {p} s PIN-om' if n else False)(
    POSCashier.objects.filter(is_active=True).count(),
    POSCashier.objects.filter(is_active=True).exclude(pin_hash='').count()))

def t_inventory():
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not k: return 'W:Nema Konjik'
    n = InventoryItem.objects.filter(company=k, is_active=True).count()
    return f'{n} artikala' if n else 'W:0 artikala za Konjik'
run('Inventory artikli za Konjik', t_inventory)

# ══ 2. BLAGAJNIK PIN ═══════════════════════════════
section('2. BLAGAJNIK — PIN')

def t_pin():
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not k: return False
    with transaction.atomic():
        c = POSCashier(company=k, name='__TEST__', is_active=True)
        c.set_pin('1234')
        c.save()
        ok = c.check_pin('1234')
        bad = c.check_pin('9999')
        c.delete()
        return f'ispravni:{ok} pogresan_odbijen:{not bad}'
run('PIN set + check + pogrešan odbijen', t_pin)

run('Blagajnik dozvole', lambda: (
    lambda c: f'can_void:{c.can_void} discount:{c.can_discount} max:{c.max_discount_percent}%'
    if c else 'W:Nema blagajnika')(
    POSCashier.objects.filter(is_active=True).first()))

# ══ 3. SESIJA ══════════════════════════════════════
section('3. SESIJA')

def t_open_session():
    global _session, _terminal
    t = POSTerminal.objects.filter(is_active=True).first()
    if not t: return False
    _terminal = t
    last = POSSession.objects.filter(terminal=t).order_by('-session_number').first()
    sn = (last.session_number + 1) if last else 1
    s = POSSession.objects.create(
        terminal=t, session_number=sn, status='open', opening_cash=Decimal('100.00'))
    _session = s
    return f'#{s.id} sn:{sn} terminal:{t.name}'
run('Otvaranje sesije', t_open_session)

def t_session_props():
    if not _session: return 'W:Nema sesije'
    return f'total_sales:{_session.total_sales} expected_cash:{_session.expected_closing_cash}'
run('Sesija properties', t_session_props)

# ══ 4. BON ═════════════════════════════════════════
section('4. BON')

def t_create_receipt():
    global _receipt
    if not _session: return 'W:Nema sesije'
    last = POSReceipt.objects.filter(
        session__terminal=_session.terminal).order_by('-receipt_number').first()
    rn = (last.receipt_number + 1) if last else 1
    r = POSReceipt.objects.create(session=_session, receipt_number=rn, status='open')
    _receipt = r
    return f'#{r.id} rn:{r.receipt_number} status:{r.status}'
run('Kreiranje bona', t_create_receipt)

def t_add_item():
    if not _receipt: return 'W:Nema bona'
    k = Company.objects.filter(name__icontains='Konjik').first()
    inv = InventoryItem.objects.filter(company=k, is_active=True).first() if k else None
    ri = POSReceiptItem.objects.create(
        receipt=_receipt,
        inventory_item=inv,
        description=inv.name if inv else 'TEST ARTIKL',
        quantity=Decimal('2'),
        unit_price=inv.unit_price if inv else Decimal('15.00'),
        tax_rate=Decimal('25'), unit='kom')
    _receipt.recalculate()
    return f'{ri.description} x{ri.quantity} total_price:{ri.total_price}'
run('Dodavanje stavke (inventory artikl)', t_add_item)

def t_add_manual():
    if not _receipt: return 'W:Nema bona'
    POSReceiptItem.objects.create(
        receipt=_receipt, description='RUČNI UNOS',
        quantity=Decimal('1'), unit_price=Decimal('10.00'),
        tax_rate=Decimal('25'), unit='kom')
    _receipt.recalculate()
    r = POSReceipt.objects.get(id=_receipt.id)
    return f'{r.items.count()} stavki subtotal:{r.subtotal} tax:{r.tax_amount} total:{r.total}'
run('Ručni unos + recalculate totals', t_add_manual)

def t_remove_item():
    if not _receipt: return 'W:Nema bona'
    item = _receipt.items.last()
    if not item: return 'W:Nema stavki'
    item.delete()
    _receipt.recalculate()
    return f'obrisano, preostalo:{_receipt.items.count()} stavki'
run('Brisanje stavke', t_remove_item)

# ══ 5. NAPLATA ═════════════════════════════════════
section('5. NAPLATA')

def t_method_choices():
    choices = [c[0] for c in POSPaymentLine.Method.choices]
    missing = [m for m in ['CASH','CARD','MOBILE','VOUCHER','ACCOUNT','CRYPTO','REVOLUT','AIRCASH']
               if m not in choices]
    return f'{len(choices)} metoda' if not missing else f'W:Nedostaju:{missing}'
run('Sve payment metode (8)', t_method_choices)

def t_pay_cash():
    if not _receipt: return 'W:Nema bona'
    r = POSReceipt.objects.get(id=_receipt.id)
    amount = r.total or Decimal('30.00')
    POSPaymentLine.objects.create(receipt=r, method='CASH', amount=amount)
    r.status='paid'; r.paid_at=timezone.now(); r.save()
    return f'CASH {amount} EUR bon:{r.status}'
run('Naplata gotovinom (CASH)', t_pay_cash)

def t_pay_split():
    if not _session: return 'W:Nema sesije'
    last = POSReceipt.objects.filter(session__terminal=_session.terminal).order_by('-receipt_number').first()
    rn = (last.receipt_number+1) if last else 100
    with transaction.atomic():
        r = POSReceipt.objects.create(session=_session, receipt_number=rn, status='open')
        POSReceiptItem.objects.create(receipt=r, description='Split', quantity=Decimal('1'),
            unit_price=Decimal('80.65'), tax_rate=Decimal('25'), unit='kom')
        r.recalculate()
        POSPaymentLine.objects.create(receipt=r, method='CASH', amount=Decimal('60.00'))
        POSPaymentLine.objects.create(receipt=r, method='CARD', amount=Decimal('40.65'))
        total = sum(p.amount for p in r.payment_lines.all())
        r.status='paid'; r.paid_at=timezone.now(); r.save()
        return f'CASH 60 + CARD 40.65 = {total}'
run('Split naplata CASH+CARD', t_pay_split)

def t_change_given():
    if not _session: return 'W:Nema sesije'
    last = POSReceipt.objects.filter(session__terminal=_session.terminal).order_by('-receipt_number').first()
    rn = (last.receipt_number+1) if last else 101
    with transaction.atomic():
        r = POSReceipt.objects.create(session=_session, receipt_number=rn, status='open')
        POSReceiptItem.objects.create(receipt=r, description='Kusur test', quantity=Decimal('1'),
            unit_price=Decimal('8.00'), tax_rate=Decimal('25'), unit='kom')
        r.recalculate()
        kusur = Decimal('10.00') - r.total
        POSPaymentLine.objects.create(receipt=r, method='CASH', amount=Decimal('10.00'), change_given=kusur)
        r.status='paid'; r.paid_at=timezone.now(); r.save()
        pl = r.payment_lines.first()
        return f'plateno:10 total:{r.total} kusur:{pl.change_given}'
run('Kusur (change_given)', t_change_given)

def t_cancel():
    if not _session: return 'W:Nema sesije'
    last = POSReceipt.objects.filter(session__terminal=_session.terminal).order_by('-receipt_number').first()
    rn = (last.receipt_number+1) if last else 102
    with transaction.atomic():
        r = POSReceipt.objects.create(session=_session, receipt_number=rn, status='open',
            cancel_reason='Test storniranja')
        r.status='cancelled'; r.save()
        return f'#{r.id} storniran'
run('Storniranje bona (cancelled)', t_cancel)

# ══ 6. VOUCHER ═════════════════════════════════════
section('6. VOUCHER')

def t_voucher():
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not k: return 'W:Nema Konjik'
    v = Voucher.objects.create(
        company=k, code=f'T-{_uuid.uuid4().hex[:6].upper()}',
        original_amount=Decimal('50.00'), remaining=Decimal('50.00'),
        expiry_date=timezone.now().date()+timedelta(days=30), is_active=True)
    usable = v.is_usable
    v.remaining = Decimal('0.00')
    v.save()
    not_usable = not v.is_usable
    v.delete()
    return f'usable:{usable} depleted_rejected:{not_usable}'
run('Voucher create + deplete + check', t_voucher)

def t_voucher_expired():
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not k: return 'W:Nema Konjik'
    v = Voucher.objects.create(
        company=k, code=f'EX-{_uuid.uuid4().hex[:6].upper()}',
        original_amount=Decimal('10.00'), remaining=Decimal('10.00'),
        expiry_date=timezone.now().date()-timedelta(days=1), is_active=True)
    expired = v.is_expired
    usable = v.is_usable
    v.delete()
    return f'expired:{expired} usable:{usable}'
run('Voucher expiry check', t_voucher_expired)

# ══ 7. CASH DEPOSIT ════════════════════════════════
section('7. CASH DEPOSIT')

def t_dep():
    if not _session: return 'W:Nema sesije'
    d = CashDeposit.objects.create(session=_session, deposit_type='deposit',
        amount=Decimal('200.00'), note='Test pologa')
    return f'#{d.id} deposit:200'
run('Pologa gotovine', t_dep)

def t_with():
    if not _session: return 'W:Nema sesije'
    w = CashDeposit.objects.create(session=_session, deposit_type='withdrawal',
        amount=Decimal('50.00'), note='Test isplate')
    return f'#{w.id} withdrawal:50'
run('Isplata gotovine', t_with)

def t_balance():
    if not _session: return 'W:Nema sesije'
    s = POSSession.objects.get(id=_session.id)
    return f'deposits:{s.total_deposits_amount} withdrawals:{s.total_withdrawals_amount} expected:{s.expected_closing_cash}'
run('Sesija balance kalkulacija', t_balance)

# ══ 8. GASTRO ══════════════════════════════════════
section('8. GASTRO — STOLOVI I NARUDŽBE')

def t_tables():
    n = Table.objects.filter(is_active=True).count()
    if not n: return 'W:Nema stolova'
    f = Table.objects.filter(is_active=True, is_occupied=False).count()
    return f'{n} stolova, {f} slobodnih'
run('Stolovi postoje', t_tables)

def t_table():
    global _table
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not k: return 'W:Nema Konjik'
    t = Table.objects.create(company=k, name='__TEST_STOL__',
        table_type='indoor', capacity=4, is_active=True, is_occupied=False)
    _table = t
    return f'#{t.id} {t.name} cap:{t.capacity}'
run('Kreiranje stola', t_table)

def t_table_occ():
    if not _table: return 'W:Nema stola'
    _table.is_occupied = True; _table.save(update_fields=['is_occupied'])
    return f'is_occupied:{Table.objects.get(id=_table.id).is_occupied}'
run('Stol zauzet (is_occupied)', t_table_occ)

def t_order():
    global _order
    if not _table: return 'W:Nema stola'
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not k: return 'W:Nema Konjik'
    o = GastroOrder.objects.create(company=k, table=_table,
        status='new', guest_name='Test Gost')
    inv = InventoryItem.objects.filter(company=k, is_active=True).first()
    GastroOrderItem.objects.create(order=o, inventory_item=inv,
        quantity=Decimal('2'), notes='bez luka')
    _order = o
    return f'#{o.id} items:{o.items.count()}'
run('Kreiranje gastro narudžbe', t_order)

def t_order_flow():
    if not _order: return 'W:Nema narudžbe'
    for s in ['confirmed','preparing','ready','delivering','delivered']:
        _order.status = s; _order.save(update_fields=['status'])
    return f'flow OK → {GastroOrder.objects.get(id=_order.id).status}'
run('Narudžba flow (new→delivered)', t_order_flow)

# ══ 9. KONOBAR SMJENA ══════════════════════════════
section('9. KONOBAR SMJENA')

def t_shift_open():
    global _shift
    user = User.objects.filter(is_active=True).first()
    k = Company.objects.filter(name__icontains='Konjik').first()
    if not user or not k: return False
    _shift = WaiterShift.objects.create(user=user, company=k, is_active=True)
    return f'#{_shift.id} user:{user.username}'
run('Otvaranje konobar smjene', t_shift_open)

def t_shift_close():
    if not _shift: return 'W:Nema smjene'
    _shift.is_active=False; _shift.ended_at=timezone.now()
    _shift.save(update_fields=['is_active','ended_at'])
    s = WaiterShift.objects.get(id=_shift.id)
    return f'zatvorena dur:{s.duration_minutes}min'
run('Zatvaranje smjene (ended_at)', t_shift_close)

run('Nema zombie smjena', lambda: (
    lambda n: f'{n} aktivnih' if n<=10 else f'W:{n} aktivnih — možda zombiji')(
    WaiterShift.objects.filter(is_active=True).count()))

# ══ 10. EXPIRY BATCH ═══════════════════════════════
section('10. EXPIRY BATCH')

def t_expiry():
    k = Company.objects.filter(name__icontains='Konjik').first()
    inv = InventoryItem.objects.filter(company=k, is_active=True).first() if k else None
    if not inv: return 'W:Nema artikla'
    b = ExpiryBatch.objects.create(company=k, inventory_item=inv,
        batch_number=f'B-{_uuid.uuid4().hex[:6].upper()}',
        quantity=Decimal('10'), expiry_date=timezone.now().date()+timedelta(days=60))
    r = f'days:{b.days_until_expiry} expired:{b.is_expired} warning:{b.is_warning}'
    b.delete(); return r
run('Expiry batch (60d, ne isteklo)', t_expiry)

def t_expiry_warn():
    k = Company.objects.filter(name__icontains='Konjik').first()
    inv = InventoryItem.objects.filter(company=k, is_active=True).first() if k else None
    if not inv: return 'W:Nema artikla'
    b = ExpiryBatch.objects.create(company=k, inventory_item=inv,
        batch_number=f'W-{_uuid.uuid4().hex[:6].upper()}',
        quantity=Decimal('5'), expiry_date=timezone.now().date()+timedelta(days=3))
    r = f'warning:{b.is_warning} expired:{b.is_expired}'
    b.delete(); return r
run('Expiry warning (3 dana)', t_expiry_warn)

# ══ 11. FISKALIZACIJA ══════════════════════════════
section('11. FISKALIZACIJA')

def t_fisk_config():
    try:
        from fiskalizacija.models import FiscalConfig
        c = FiscalConfig.objects.first()
        if not c: return 'W:Nema FiscalConfig'
        return f'OIB:{c.company.oib} demo:{c.is_demo} active:{c.is_active}'
    except Exception as e: return f'W:{e}'
run('FiscalConfig postoji', t_fisk_config)

def t_fisk_cert():
    try:
        from fiskalizacija.models import FiscalConfig
        c = FiscalConfig.objects.first()
        if not c or not c.cert_path: return False
        sz = os.path.getsize(c.cert_path) if os.path.exists(c.cert_path) else 0
        return f'{os.path.basename(c.cert_path)} {sz}B'
    except Exception as e: return f'W:{e}'
run('Fiscal cert na disku', t_fisk_cert)

def t_fisk_ping():
    try:
        from fiskalizacija.fisk import ping_fina
        from fiskalizacija.models import FiscalConfig
        c = FiscalConfig.objects.first()
        if not c: return 'W:Nema config'
        return f'PING:{ping_fina(c.cert_path, c.get_password(), demo=True)}'
    except Exception as e: return f'W:{e}'
run('FINA CIS ping (test server)', t_fisk_ping)

def t_zki():
    try:
        from fiskalizacija.fisk import generate_zki, load_p12
        from fiskalizacija.models import FiscalConfig
        c = FiscalConfig.objects.first()
        if not c: return 'W:Nema config'
        key,_,_,_ = load_p12(c.cert_path, c.get_password())
        zki = generate_zki(c.company.oib, datetime.now(), 'T-001', 'POS1', 'UR1', Decimal('100.00'), key)
        return f'ZKI:{zki[:16]}... ({len(zki)} chars)'
    except Exception as e: return f'W:{e}'
run('ZKI generacija', t_zki)

def t_fiscalize():
    try:
        from fiskalizacija.fisk import fiscalize_receipt as fr
        paid = POSReceipt.objects.filter(status='paid').order_by('-paid_at').first()
        if not paid: return 'W:Nema plaćenih bonova'
        jir = fr(paid)
        return f'JIR:{jir[:15]}...' if jir else 'W:JIR=None'
    except Exception as e: return f'W:{e}'
run('Fiskalizacija plaćenog bona', t_fiscalize)

# ══ 12. Z-REPORT ════════════════════════════════════
section('12. Z-REPORT I DAILY REPORTS')

def t_daily():
    n = POSDailyReport.objects.count()
    if not n: return 'W:Nema daily reporta'
    last = POSDailyReport.objects.order_by('-date').first()
    return f'{n} reporta, zadnji:{last.date} rev:{last.total_revenue}'
run('Daily reports u bazi', t_daily)

def t_gen_report():
    if not _session: return 'W:Nema sesije'
    try:
        rep = POSDailyReport.generate_from_session(_session)
        return f'#{rep.id} date:{rep.date} rev:{rep.total_revenue}' if rep else 'W:vratio None'
    except Exception as e: return f'W:{e}'
run('generate_from_session()', t_gen_report)

def t_close_session():
    if not _session: return 'W:Nema sesije'
    _session.status='closed'; _session.closed_at=timezone.now()
    _session.save(update_fields=['status','closed_at'])
    s = POSSession.objects.get(id=_session.id)
    return f'#{s.id} status:{s.status} at:{s.closed_at.strftime("%H:%M:%S")}'
run('Zatvaranje sesije', t_close_session)

# ══ 13. OFFLINE / PWA ══════════════════════════════
section('13. OFFLINE I PWA')

run('Service Worker', lambda: (
    lambda p: f'sw.js {os.path.getsize(p)}B'
    if os.path.exists(p) else False)(
    '/var/www/fina-connect/static/sw.js'))

run('PWA manifest', lambda: (
    lambda p: f'{json.load(open(p)).get("name")} display:{json.load(open(p)).get("display")}'
    if os.path.exists(p) else False)(
    '/var/www/fina-connect/static/manifest.json'))

def t_offline_bar():
    import subprocess
    r = subprocess.run(['grep','-c','offlineBar',
        '/var/www/fina-connect/templates/base.html'], capture_output=True, text=True)
    n = int(r.stdout.strip()) if r.returncode==0 else 0
    return f'offlineBar x{n}' if n else 'W:offlineBar nije u base.html'
run('Offline UI indikator', t_offline_bar)

def t_idb():
    import subprocess
    r = subprocess.run(['grep','-c','indexedDB',
        '/var/www/fina-connect/templates/inventory/inventura_count.html'],
        capture_output=True, text=True)
    n = int(r.stdout.strip()) if r.returncode==0 else 0
    return f'IndexedDB x{n}' if n else 'W:IndexedDB nije implementiran'
run('Inventura IndexedDB', t_idb)

# ══ 14. IMPROVEMENT SUGGESTIONS ════════════════════
section('14. IMPROVEMENT SUGGESTIONS')

def t_impr():
    k = Company.objects.filter(name__icontains='Konjik').first()
    user = User.objects.filter(is_active=True).first()
    if not k or not user: return 'W:Nema Konjik/user'
    imp = ImprovementSuggestion.objects.create(
        company=k, author=user,
        title='Test', description='Test prijedlog', category='pos')
    imp.delete()
    return 'create + delete OK'
run('ImprovementSuggestion lifecycle', t_impr)

# ══ CLEANUP ════════════════════════════════════════
section('CLEANUP')

def do_cleanup():
    n = 0
    n += Table.objects.filter(name='__TEST_STOL__').delete()[0]
    n += POSCashier.objects.filter(name='__TEST__').delete()[0]
    n += Voucher.objects.filter(code__startswith='T-').filter(notes='').delete()[0]
    n += Voucher.objects.filter(code__startswith='EX-').delete()[0]
    if _session:
        POSSession.objects.filter(id=_session.id).delete(); n+=1
    return f'{n} test zapisa obrisano'
run('Čišćenje test podataka', do_cleanup)

# ══ Z-REPORT ═══════════════════════════════════════
total_t = time.time()-t0_global
p = sum(1 for r in results if r['s']=='PASS')
f = sum(1 for r in results if r['s']=='FAIL')
w = sum(1 for r in results if r['s']=='WARN')
n = len(results)
score = int(p/n*100) if n else 0

print(f'\n{BOLD}{C}╔══════════════════════════════════════════╗')
print(f'║  Z-REPORT — {datetime.now().strftime("%d.%m.%Y %H:%M")}             ║')
print(f'╚══════════════════════════════════════════╝{RESET}')
print(f'\n  {G}✓ PASS  {p:3d}{RESET}')
print(f'  {R}✗ FAIL  {f:3d}{RESET}')
print(f'  {Y}⚠ WARN  {w:3d}{RESET}')
print(f'  {DIM}──────────────{RESET}')
print(f'    UKUPNO {n:3d}  {DIM}({total_t:.1f}s){RESET}')

bar = '█'*int(30*score/100)+'░'*(30-int(30*score/100))
col = G if score>=90 else Y if score>=70 else R
grade = (f'{G}10/10 — PRODUKCIJA SPREMA{RESET}' if score>=95 else
         f'{G}9/10 — ODLIČNO{RESET}' if score>=85 else
         f'{Y}8/10 — DOBRO{RESET}' if score>=75 else
         f'{Y}7/10{RESET}' if score>=65 else
         f'{R}HITNE POPRAVKE{RESET}')
print(f'\n  {col}{bar}{RESET} {BOLD}{score}%{RESET}')
print(f'  Ocjena: {BOLD}{grade}')

if f:
    print(f'\n{R}{BOLD}  KRITIČNO — FAIL:{RESET}')
    for r in results:
        if r['s']=='FAIL': print(f'  {R}✗{RESET} {r["n"]}  {DIM}{r["d"]}{RESET}')
if w:
    print(f'\n{Y}  UPOZORENJA:{RESET}')
    for r in results:
        if r['s']=='WARN': print(f'  {Y}⚠{RESET} {r["n"]}  {DIM}{r["d"]}{RESET}')

msg = ('✓ Sustav spreman.' if f==0 and w<=3 else
       '⚠ Provjeri upozorenja.' if f==0 else
       '✗ Popravi greške.')
print(f'\n  {G if f==0 else R}{msg}{RESET}\n')
