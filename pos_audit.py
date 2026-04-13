import os, sys
sys.path.insert(0, '/var/www/fina-connect')
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'

import django
django.setup()

from pos.models import *
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

SEP = "=" * 55

print(SEP)
print("POS MODUL — KOMPLETNA ANALIZA")
print(f"Datum: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
print(SEP)

# Terminali
print("\n[ TERMINALI ]")
for t in POSTerminal.objects.select_related('company').all():
    print(f"  #{t.id} | {t.name} | {t.company} | aktivan:{t.is_active}")

# Sesije
print("\n[ SESIJE ]")
for s in POSSession.objects.select_related('terminal').order_by('-opened_at'):
    closed = s.closed_at.strftime('%d.%m %H:%M') if s.closed_at else 'OTVORENA'
    cashiers = s.active_cashiers.count() if hasattr(s, 'active_cashiers') else '?'
    print(f"  #{s.id} | {s.terminal.name} | {s.status} | otvoren:{s.opened_at.strftime('%d.%m %H:%M')} | zatvoren:{closed} | blagajnici:{cashiers}")

# Blagajnici
print("\n[ BLAGAJNICI ]")
for c in POSCashier.objects.all():
    pin = 'DA' if c.pin else 'NEMA PINA'
    print(f"  #{c.id} | {c.name} | aktivan:{c.is_active} | PIN:{pin}")

# Bonovi/Računi
print("\n[ BONOVI — STATISTIKA ]")
total = POSReceipt.objects.count()
print(f"  Ukupno bonova: {total}")
for status in ['OPEN', 'ISSUED', 'STORNO', 'PAID']:
    cnt = POSReceipt.objects.filter(status=status).count()
    if cnt:
        print(f"  {status}: {cnt}")

# Iznosi
issued = POSReceipt.objects.filter(status='ISSUED')
if issued.exists():
    total_amount = issued.aggregate(s=Sum('total_amount'))['s'] or 0
    avg_amount = issued.aggregate(a=Avg('total_amount'))['a'] or 0
    print(f"  Ukupno naplaćeno: {total_amount:.2f} EUR")
    print(f"  Prosječni bon: {avg_amount:.2f} EUR")

# Plaćanja
print("\n[ METODE PLAĆANJA ]")
payments = POSPaymentLine.objects.values('payment_method').annotate(
    cnt=Count('id'), total=Sum('amount')
).order_by('-total')
for p in payments:
    print(f"  {p['payment_method']} | {p['cnt']}x | {p['total']:.2f} EUR")

# Stavke
print("\n[ STAVKE BONOVA ]")
items_count = POSReceiptItem.objects.count()
top_items = POSReceiptItem.objects.values('description').annotate(
    cnt=Count('id'), total=Sum('subtotal')
).order_by('-cnt')[:10]
print(f"  Ukupno stavki: {items_count}")
print(f"  Top 10 artikala:")
for i in top_items:
    print(f"    - {i['description'][:40]} | {i['cnt']}x | {i['total']:.2f} EUR")

# Stolovi
print("\n[ STOLOVI ]")
table_count = Table.objects.count()
print(f"  Ukupno stolova: {table_count}")
if table_count:
    for t in Table.objects.all().order_by('section', 'name'):
        print(f"  {t.name} | sekcija:{t.section} | kapacitet:{t.capacity} | status:{t.status}")

# Gastro narudžbe
print("\n[ GASTRO NARUDZBE ]")
orders = GastroOrder.objects.count()
print(f"  Ukupno narudžbi: {orders}")
if orders:
    for status in ['pending', 'confirmed', 'preparing', 'ready', 'delivered', 'paid', 'cancelled']:
        cnt = GastroOrder.objects.filter(status=status).count()
        if cnt:
            print(f"  {status}: {cnt}")

# Waiter shifts
print("\n[ KONOBAR SMJENE ]")
try:
    shifts = WaiterShift.objects.select_related('user').all().order_by('-started_at')[:10]
    for s in shifts:
        end = s.ended_at.strftime('%d.%m %H:%M') if s.ended_at else 'AKTIVNA'
        print(f"  {s.user} | start:{s.started_at.strftime('%d.%m %H:%M')} | kraj:{end} | orders:{s.total_orders_claimed}")
except DatabaseError as e:
    print(f"  Greška: {e}")

# Daily reports
print("\n[ DNEVNI IZVJESTAJI ]")
try:
    reports = POSDailyReport.objects.count()
    print(f"  Ukupno: {reports}")
except DatabaseError as e:
    print(f"  Greška: {e}")

# Loyalty
print("\n[ LOYALTY PROGRAM ]")
try:
    lp = LoyaltyProgram.objects.count()
    gl = GuestLoyalty.objects.count()
    print(f"  Loyalty programi: {lp}")
    print(f"  Gosti u programu: {gl}")
except DatabaseError as e:
    print(f"  Greška: {e}")

# Vouchers
print("\n[ VAUCERI ]")
try:
    v = Voucher.objects.count()
    print(f"  Ukupno vaučera: {v}")
except DatabaseError as e:
    print(f"  Greška: {e}")

# Cash deposits
print("\n[ BLAGAJNICKI POLOG ]")
try:
    cd = CashDeposit.objects.all().order_by('-created_at')[:5]
    print(f"  Zadnjih 5 pologa:")
    for d in cd:
        print(f"  {d.created_at.strftime('%d.%m')} | {d.amount} EUR | {d.deposit_type}")
except DatabaseError as e:
    print(f"  Greška: {e}")

# POS Settings
print("\n[ POS SETTINGS ]")
try:
    for s in POSSettings.objects.select_related('company').all():
        print(f"  Firma: {s.company}")
        print(f"  Fiskalizacija: {getattr(s, 'fiscalization_enabled', 'N/A')}")
        print(f"  Štampač: {getattr(s, 'printer_type', 'N/A')}")
        print(f"  Quick items: {getattr(s, 'quick_item_ids', 'N/A')}")
except (ValueError, TypeError) as e:
    print(f"  Greška: {e}")

print("\n" + SEP)
print("KRAJ ANALIZE")
print(SEP)
