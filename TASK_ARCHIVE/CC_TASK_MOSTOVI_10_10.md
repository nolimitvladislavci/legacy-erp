# CC_TASK: MOSTOVI DO 10/10 — IRA/URA/POS kompletni tijek
# Datum: 04.04.2026. | Rok: 07.04.2026. (ponedjeljak) | Prioritet: P0
# Cilj: Sustav koji ZNADE što je pošlo i što je došlo — svaki euro.
#
# Zakonska osnova:
#   Zakon o računovodstvu NN 78/2015 — dvojno knjiženje obavezno
#   Pravilnik o porezu na dodanu vrijednost NN 79/2013
#   Zakon o lokalnim porezima NN 115/2016 čl. 35 — porez na potrošnju
#   Zakon o trgovini NN 87/2008 — evidencija primitka robe

PRAVILO: READ models.py/services PRIJE svakog WRITE.
PRAVILO: select_for_update() za sve stock i konto operacije.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.
PRAVILO: Svaki most = zasebna atomarna transakcija. Jedan ne smije blokirati drugi.

---

## MOST 1 — po_receive → gr.confirm() [KRITIČAN BUG]

### Problem:
procurement/views.py:po_receive() kreira GoodsReceipt ali NIKAD ne poziva gr.confirm()
→ zaliha se ne uvećava
→ StockMovement 'in' se ne kreira
→ Konto ne zna da je roba stigla

### Provjeri:
```bash
grep -n "\.confirm\(\)\|gr\.confirm\|GoodsReceipt" procurement/views.py | head -15
sed -n '161,220p' procurement/views.py
```

### Fix — procurement/views.py:po_receive():

Pronađi blok gdje se kreira GoodsReceipt:
```python
gr = GoodsReceipt.objects.create(
    company=company,
    supplier=po.supplier,
    reference=po.po_number,
    created_by=request.user,
)
for item in po.items.all():
    if item.quantity_received > 0 and item.inventory_item:
        GoodsReceiptItem.objects.create(...)
messages.success(request, f'Primka {gr.pk} automatski kreirana.')
```

ZAMIJENI: nakon `for item...` petlje, DODAJ:
```python
# Potvrdi primku — uvećaj zalihu, kreiraj StockMovement, Konto JE
try:
    gr._confirmed_by = request.user
    gr.confirm()
    messages.success(request,
        f'Primka {gr.receipt_number} potvrđena. '
        f'Zaliha uvećana za {len(po.items.filter(quantity_received__gt=0))} artikala.')
except Exception as _ce:
    import logging
    logging.getLogger(__name__).error(f'gr.confirm() fail: {_ce}', exc_info=True)
    messages.warning(request,
        f'Primka kreirana ali potvrda nije uspjela: {_ce}. '
        f'Ručno potvrdite primku {gr.pk}.')
```

---

## MOST 2 — GoodsReceipt.confirm() → JournalEntry (URA knjiženje)

### Problem:
GoodsReceipt.confirm() docstring kaže "All confirmed receipts get an automatic journal entry"
ali na kraju confirm() metode — nema JournalEntry koda. Obećano, nije napravljeno.

### Provjeri:
```bash
sed -n '500,620p' inventory/models.py
grep -n "JournalEntry\|konto\|book\|journal" inventory/models.py | head -15
```

### Fix — Na kraju GoodsReceipt.confirm() metode, UNUTAR `with _tx.atomic():` bloka:

```python
# URA auto-knjiženje (Zakon o računovodstvu — svaka primka robe knjizi se)
# Primka robe 1000€ + PDV 250€:
#   D 3000 Zalihe robe          1000,00€
#   D 1400 Pretporez             250,00€
#   P 2200 Obveze prema dobavljaču 1250,00€
if not is_consignment and total_purchase > 0:
    try:
        from konto.services_file import book_goods_receipt
        book_goods_receipt(self)
    except Exception as _ke:
        import logging
        logging.getLogger(__name__).warning(
            f'GoodsReceipt.confirm(): konto knjiženje nije uspjelo: {_ke}')
        # Ne bacamo exception — zaliha je uvećana, konto se može ručno popraviti
```

### Kreiraj: konto/services_file.py — dodaj funkciju `book_goods_receipt`:

READ: konto/services_file.py (book_pos_session, book_invoice — vidi pattern)
READ: konto/models.py (KontoAccount, JournalEntry, LedgerLine)

```python
def book_goods_receipt(goods_receipt, user=None):
    """
    Knjiži primku robe u double-entry ledger (URA automatski).

    Primka robe 1000€ neto + 250€ PDV = 1250€:
      D: 3000 Zalihe robe                1000,00€
      D: 1400 Pretporez                   250,00€
      P: 2200 Obveze prema dobavljačima  1250,00€

    Returns: JournalEntry ili None
    """
    from .models import KontoAccount, JournalEntry, LedgerLine

    company = goods_receipt.company
    if not company:
        return None

    # Idempotency
    prefix = f'GR-{goods_receipt.receipt_number}'
    if JournalEntry.objects.filter(
        company=company, entry_number__startswith=prefix
    ).exists():
        return None

    total_net = goods_receipt.total_purchase  # bez PDV
    if not total_net or total_net <= 0:
        return None

    # PDV — pretpostavljamo standardnu stopu 25% za robu
    # Ako postoji supplier invoice u arhivi — bolje bi bilo uzeti odatle
    # Za sada: ukupno bez PDV = total_purchase, PDV = 25%
    # TODO: kad se AR integrira s Arhivom, uzeti stvarni PDV
    from decimal import Decimal, ROUND_HALF_UP
    vat_rate = Decimal('0.25')
    vat_amount = (total_net * vat_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_with_vat = total_net + vat_amount

    country = getattr(company, 'country', 'HR')
    if country == 'DE':
        inventory_code, inventory_name = '3000', 'Wareneinsatz'
        pretporez_code, pretporez_name = '1576', 'Vorsteuer 19%'
        payable_code,  payable_name   = '1600', 'Verbindlichkeiten'
    else:
        inventory_code, inventory_name = '3000', 'Zalihe robe (nabavna)'
        pretporez_code, pretporez_name = '1400', 'Pretporez'
        payable_code,  payable_name   = '2200', 'Obveze prema dobavljačima'

    entry_num = _next_entry_number(company, 'GR')
    supplier_name = goods_receipt.supplier.name if goods_receipt.supplier else 'Dobavljač'
    date = goods_receipt.date

    je = JournalEntry.objects.create(
        company=company,
        entry_number=entry_num,
        date=date,
        description=(
            f'Primka {goods_receipt.receipt_number} — {supplier_name} '
            f'({goods_receipt.items.count()} artikala)'
        ),
        source_type='purchase',
        is_posted=True,
        created_by=user,
    )

    def _acct(code, name, acct_type):
        a, _ = KontoAccount.objects.get_or_create(
            company=company, code=code,
            defaults={'name': name, 'account_type': acct_type})
        return a

    # D: Zalihe robe
    LedgerLine.objects.create(
        journal_entry=je, account=_acct(inventory_code, inventory_name, 'asset'),
        side='debit', amount=float(total_net),
        description=f'Primka {goods_receipt.receipt_number}')

    # D: Pretporez (PDV na ulazu)
    if vat_amount > 0:
        LedgerLine.objects.create(
            journal_entry=je, account=_acct(pretporez_code, pretporez_name, 'asset'),
            side='debit', amount=float(vat_amount),
            description=f'Pretporez primka {goods_receipt.receipt_number}')

    # P: Obveze prema dobavljaču
    LedgerLine.objects.create(
        journal_entry=je, account=_acct(payable_code, payable_name, 'liability'),
        side='credit', amount=float(total_with_vat),
        description=f'Dobavljač: {supplier_name}')

    # Balans provjera (rounding fix)
    if not je.is_balanced:
        diff = je.total_debit - je.total_credit
        if abs(diff) < Decimal('0.10'):
            inv_line = je.lines.filter(side='debit', account__code=inventory_code).first()
            if inv_line:
                from decimal import Decimal as D
                inv_line.amount = float(D(str(inv_line.amount)) + D(str(diff)))
                inv_line.save(update_fields=['amount'])

    return je
```

---

## MOST 3 — Consumption Tax → Konto 2390

### Problem:
book_pos_session() ne knjizi consumption_tax_amount.
Zakon o lokalnim porezima NN 115/2016 — mora biti na kontu 2390.
PP-MI-PO obrazac postoji ali nema pokriće u konto temeljnici.

### Provjeri:
```bash
sed -n '1161,1300p' konto/services_file.py
grep -n "consumption_tax" konto/services_file.py | head -5
```

### Fix — u book_pos_session(), UNUTAR `with transaction.atomic():`:

Pronađi blok NAKON `# CREDIT: VAT` i PRIJE `# Verify balance`:

```python
# CREDIT: Porez na potrošnju (Zakon o lokalnim porezima čl.35)
# Samo ako postoji consumption_tax_active konfiguracija
ct_total = receipts.aggregate(
    ct=Sum('consumption_tax_amount')
)['ct'] or Decimal('0')

if ct_total > 0:
    ct_acct, _ = KontoAccount.objects.get_or_create(
        company=company, code='2390',
        defaults={
            'name': 'Obveze za porez na potrošnju (JLS)',
            'account_type': 'liability'
        })
    LedgerLine.objects.create(
        journal_entry=je, account=ct_acct,
        side='credit', amount=round(ct_total, 2),
        description=(
            f'Porez na potrošnju smjena #{session.session_number} '
            f'({pos_settings.consumption_tax_jls_name if hasattr(pos_settings, "consumption_tax_jls_name") else "JLS"})'
        ))

    # Korigiraj prihod: prihod se smanjuje za CT iznos
    # (CT je trošak, ne prihod poduzetnika)
    rev_line = je.lines.filter(
        side='credit', account__code=revenue_code
    ).first()
    if rev_line:
        rev_line.amount = round(float(rev_line.amount) - float(ct_total), 2)
        rev_line.save(update_fields=['amount'])
```

NAPOMENA: `pos_settings` = `POSSettings.objects.filter(company=company).first()`
Provjeri je li pos_settings dostupan u tom scope-u:
```bash
grep -n "pos_settings" konto/services_file.py | head -5
```
Ako nije — dodaj na vrh book_pos_session():
```python
from pos.models import POSSettings
pos_settings = POSSettings.objects.filter(company=company).first()
```

---

## MOST 4 — IRA/URA Unified Dashboard

### Problem:
Korisnik mora otvoriti 5 zaslona da vidi tijek: Arhiva → Konto → Invoicing → Procurement → PDV-S.
Nema jednog mjesta gdje vidi: "Ovo je što dugujemo (URA), ovo je što nam duguju (IRA)."

### Provjeri:
```bash
grep -n "def.*dashboard\|def.*pregled" konto/views.py | head -10
grep -n "ura_ira\|knjiga_ura\|IRA\|URA" konto/urls.py | head -10
ls templates/konto/ | grep -i "dashboard\|pregled\|ura\|ira"
```

### Kreiraj: konto/views_ura_ira.py

```python
"""
IRA/URA Unified Dashboard — jedinstven pregled toka dokumenata.
Odlazi: IRA (izdani), Dolazi: URA (ulazni).
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from decimal import Decimal
from datetime import date, timedelta
from core.company_utils import get_user_company


@login_required
def ura_ira_dashboard(request):
    """
    Unified IRA/URA dashboard.

    Prikazuje:
    - Saldo: što nam duguju (IRA) vs što mi dugujemo (URA)
    - Dospjele IRA (preplata/nedospjelo)
    - Dospjele URA (kasne plaćanja dobavljačima)
    - Neproknjiženi dokumenti (Arhiva bez JournalEntry)
    - POS promet ovaj mj. vs Konto proknjiženo
    - Consumption tax dugovanje prema JLS
    """
    company = get_user_company(request)
    if not company:
        return render(request, 'konto/ura_ira_dashboard.html', {'error': True})

    today = date.today()
    month_start = today.replace(day=1)

    # ── IRA — Što nam duguju (izdani računi) ──
    from invoicing.models import Invoice
    ira_qs = Invoice.objects.filter(
        company=company,
        doctype__in=['R', 'FA', 'RN', 'ZR'],
    )
    ira_stats = {
        'ukupno':    ira_qs.aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'neplaceno': ira_qs.filter(
            status__in=['SENT','UNPAID','CONFIRMED','FISCALIZED']
        ).aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'dospjelo': ira_qs.filter(
            status='OVERDUE'
        ).aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'ovaj_mj': ira_qs.filter(
            date_issued__gte=month_start
        ).aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'count_dospjelo': ira_qs.filter(status='OVERDUE').count(),
    }

    # ── URA — Što mi dugujemo (ulazni, primljeni) ──
    from documents.models import ArhivaEntry
    ura_qs = ArhivaEntry.objects.filter(
        company=company,
        source_type__in=['invoice_in', 'eracun', 'primka'],
    )
    ura_stats = {
        'ukupno': ura_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0'),
        'ovaj_mj': ura_qs.filter(doc_date__gte=month_start).aggregate(t=Sum('amount'))['t'] or Decimal('0'),
        'proknjizeno': ura_qs.filter(is_booked=True).count() if hasattr(ArhivaEntry, 'is_booked') else 0,
        'neproknjizeno': ura_qs.filter(
            Q(is_booked=False) | Q(is_booked__isnull=True)
        ).count() if hasattr(ArhivaEntry, 'is_booked') else ura_qs.count(),
        'count': ura_qs.count(),
    }

    # ── POS ovaj mj ──
    from pos.models import POSReceipt, POSSession
    pos_stats = {
        'prihod_mj': POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            paid_at__date__gte=month_start,
            is_training=False,
        ).aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'ct_mj': POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            paid_at__date__gte=month_start,
            consumption_tax_amount__gt=0,
        ).aggregate(t=Sum('consumption_tax_amount'))['t'] or Decimal('0'),
        'r1_count': POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            is_r1=True,
            paid_at__date__gte=month_start,
        ).count(),
    }

    # ── Procurement: narudžbe u tijeku ──
    from procurement.models import PurchaseOrder
    po_stats = {
        'otvorene': PurchaseOrder.objects.filter(
            company=company,
            status__in=['draft','sent','confirmed','partial'],
        ).aggregate(t=Sum('total_amount'))['t'] or Decimal('0'),
        'count': PurchaseOrder.objects.filter(
            company=company,
            status__in=['draft','sent','confirmed','partial'],
        ).count(),
    }

    # ── Saldo pregled ──
    saldo = {
        'potrazujemo': ira_stats['neplaceno'],  # kupci duguju nama
        'dugujemo':    ura_stats['ukupno'] - (ura_stats.get('proknjizeno_iznos', Decimal('0'))),
        'neto': ira_stats['neplaceno'] - ura_stats['ovaj_mj'],
    }

    # Neproknjiženi dokumenti — alarm
    alarms = []
    if ura_stats['neproknjizeno'] > 0:
        alarms.append({
            'tip': 'warning',
            'poruka': f'{ura_stats["neproknjizeno"]} ulaznih računa čeka proknjižavanje',
            'link': '/hr/arhiva/?filter=unparsed',
        })
    if ira_stats['count_dospjelo'] > 0:
        alarms.append({
            'tip': 'danger',
            'poruka': f'{ira_stats["count_dospjelo"]} izdanih računa prekoračilo rok plaćanja',
            'link': '/hr/invoicing/?status=OVERDUE',
        })
    if pos_stats['ct_mj'] > 0:
        alarms.append({
            'tip': 'info',
            'poruka': f'Porez na potrošnju ovaj mj: {pos_stats["ct_mj"]:.2f} EUR — platiti JLS-u',
            'link': '/hr/pos/consumption-tax-report/',
        })

    return render(request, 'konto/ura_ira_dashboard.html', {
        'ira': ira_stats,
        'ura': ura_stats,
        'pos': pos_stats,
        'po':  po_stats,
        'saldo': saldo,
        'alarms': alarms,
        'month_start': month_start,
        'page_title': 'IRA/URA — Tijek dokumenata',
    })
```

### Kreiraj: templates/konto/ura_ira_dashboard.html

Design: 10/10, dark gold, 4 KPI kartice na vrhu, alarms, split view IRA/URA.

```html
{% extends "base.html" %}
{% block title %}IRA/URA Dashboard{% endblock %}
{% block content %}
<div style="max-width:1200px;margin:0 auto;padding:1.5rem 1rem;">

  <!-- HEADER -->
  <div style="margin-bottom:2rem;">
    <h1 style="font-size:1.75rem;font-weight:800;">
      💸 Tijek dokumenata
    </h1>
    <p style="color:var(--text-secondary);font-size:.875rem;">
      Što je pošlo (IRA) · Što je došlo (URA) · Što se duguje
    </p>
  </div>

  <!-- ALARMI -->
  {% for alarm in alarms %}
  <div style="padding:.875rem 1.25rem;border-radius:10px;margin-bottom:.75rem;
    {% if alarm.tip == 'danger' %}background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);
    {% elif alarm.tip == 'warning' %}background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
    {% else %}background:rgba(201,168,76,.08);border:1px solid rgba(201,168,76,.25);{% endif %}
    display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:.875rem;color:var(--text-primary);">
      {% if alarm.tip == 'danger' %}🔴{% elif alarm.tip == 'warning' %}⚠️{% else %}ℹ️{% endif %}
      {{ alarm.poruka }}
    </span>
    <a href="{{ alarm.link }}"
      style="font-size:.78rem;color:var(--gold);font-weight:600;white-space:nowrap;margin-left:1rem;">
      Pregledaj →
    </a>
  </div>
  {% endfor %}

  <!-- SALDO BANNER -->
  <div style="background:linear-gradient(135deg,rgba(201,168,76,.1),var(--surface));
    border:1px solid rgba(201,168,76,.3);border-radius:14px;padding:1.5rem 2rem;
    margin-bottom:2rem;display:flex;gap:2rem;flex-wrap:wrap;align-items:center;">
    <div style="flex:1;min-width:200px;">
      <div style="font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;
        color:var(--text-secondary);margin-bottom:.25rem;">Neto saldo (nam duguju − mi dugujemo)</div>
      <div style="font-size:2.25rem;font-weight:800;color:{% if saldo.neto >= 0 %}#10b981{% else %}#ef4444{% endif %};">
        {% if saldo.neto >= 0 %}+{% endif %}{{ saldo.neto|floatformat:2 }} EUR
      </div>
    </div>
    <div style="display:flex;gap:2rem;flex-wrap:wrap;">
      <div style="text-align:center;">
        <div style="font-size:1.35rem;font-weight:700;color:#10b981;">
          {{ saldo.potrazujemo|floatformat:2 }} EUR
        </div>
        <div style="font-size:.78rem;color:var(--text-secondary);">Kupci nam duguju</div>
      </div>
      <div style="font-size:1.5rem;color:var(--text-muted);">−</div>
      <div style="text-align:center;">
        <div style="font-size:1.35rem;font-weight:700;color:#ef4444;">
          {{ ura.ovaj_mj|floatformat:2 }} EUR
        </div>
        <div style="font-size:.78rem;color:var(--text-secondary);">Mi dugujemo ovaj mj.</div>
      </div>
    </div>
  </div>

  <!-- 4 KPI -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin-bottom:2rem;">

    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;">
      <div style="font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--text-secondary);margin-bottom:.5rem;">
        📤 IRA — Izdani (ovaj mj.)
      </div>
      <div style="font-size:1.75rem;font-weight:800;color:var(--text-primary);">
        {{ ira.ovaj_mj|floatformat:2 }} EUR
      </div>
      <div style="font-size:.8rem;color:var(--text-secondary);margin-top:.25rem;">
        Dospjelo: <span style="color:#ef4444;font-weight:600;">{{ ira.dospjelo|floatformat:2 }} EUR</span>
      </div>
      <a href="/hr/invoicing/" style="display:block;margin-top:.75rem;font-size:.8rem;color:var(--gold);">
        Pregledaj račune →
      </a>
    </div>

    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;">
      <div style="font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--text-secondary);margin-bottom:.5rem;">
        📥 URA — Primljeni (ovaj mj.)
      </div>
      <div style="font-size:1.75rem;font-weight:800;color:var(--text-primary);">
        {{ ura.ovaj_mj|floatformat:2 }} EUR
      </div>
      <div style="font-size:.8rem;color:var(--text-secondary);margin-top:.25rem;">
        Neproknjiženo: <span style="color:#f59e0b;font-weight:600;">{{ ura.neproknjizeno }}</span> dok.
      </div>
      <a href="/hr/arhiva/" style="display:block;margin-top:.75rem;font-size:.8rem;color:var(--gold);">
        Otvori arhivu →
      </a>
    </div>

    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;">
      <div style="font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--text-secondary);margin-bottom:.5rem;">
        🛒 POS promet (ovaj mj.)
      </div>
      <div style="font-size:1.75rem;font-weight:800;color:var(--text-primary);">
        {{ pos.prihod_mj|floatformat:2 }} EUR
      </div>
      <div style="font-size:.8rem;color:var(--text-secondary);margin-top:.25rem;">
        R1 bonova: {{ pos.r1_count }}
        {% if pos.ct_mj > 0 %}
        · CT: <span style="color:var(--gold);">{{ pos.ct_mj|floatformat:2 }} EUR</span>
        {% endif %}
      </div>
      <a href="/hr/pos/" style="display:block;margin-top:.75rem;font-size:.8rem;color:var(--gold);">
        Otvori POS →
      </a>
    </div>

    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;">
      <div style="font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--text-secondary);margin-bottom:.5rem;">
        📦 Narudžbe u tijeku
      </div>
      <div style="font-size:1.75rem;font-weight:800;color:var(--text-primary);">
        {{ po.count }} PO
      </div>
      <div style="font-size:.8rem;color:var(--text-secondary);margin-top:.25rem;">
        Vrijednost: {{ po.otvorene|floatformat:2 }} EUR
      </div>
      <a href="/hr/procurement/" style="display:block;margin-top:.75rem;font-size:.8rem;color:var(--gold);">
        Otvori narudžbe →
      </a>
    </div>

  </div>

  <!-- PDV RECONCILIATION -->
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:2rem;">
    <h3 style="font-size:1rem;font-weight:700;margin-bottom:1rem;">
      📊 PDV pregled — brza provjera
    </h3>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;">
      <div>
        <div style="font-size:.75rem;color:var(--text-secondary);">PDV na izlazu (IRA)</div>
        <div style="font-size:1.25rem;font-weight:700;color:#ef4444;">
          {{ ira.ovaj_mj|floatformat:2 }} × 25% ≈
          {% widthratio ira.ovaj_mj 4 1 %} EUR
        </div>
      </div>
      <div>
        <div style="font-size:.75rem;color:var(--text-secondary);">Pretporez (URA)</div>
        <div style="font-size:1.25rem;font-weight:700;color:#10b981;">
          {{ ura.ovaj_mj|floatformat:2 }} × 25% ≈
          {% widthratio ura.ovaj_mj 4 1 %} EUR
        </div>
      </div>
      <div>
        <div style="font-size:.75rem;color:var(--text-secondary);">Za platiti PDV-u (procjena)</div>
        <div style="font-size:1.25rem;font-weight:700;color:var(--gold);">
          ~ {% widthratio ira.ovaj_mj 4 1 %} EUR
        </div>
      </div>
      {% if pos.ct_mj > 0 %}
      <div style="background:rgba(201,168,76,.06);border-radius:8px;padding:.75rem;">
        <div style="font-size:.75rem;color:var(--text-secondary);">Porez na potrošnju (JLS)</div>
        <div style="font-size:1.25rem;font-weight:700;color:var(--gold);">
          {{ pos.ct_mj|floatformat:2 }} EUR
        </div>
        <div style="font-size:.72rem;color:var(--text-muted);">konto 2390</div>
      </div>
      {% endif %}
    </div>
    <div style="margin-top:1rem;text-align:right;">
      <a href="/hr/konto/pdv-s/" style="font-size:.82rem;color:var(--gold);">
        Otvori PDV-S prijavu →
      </a>
    </div>
  </div>

</div>
{% endblock %}
```

### URL — dodaj u konto/urls.py:
```python
path('ura-ira/', views_ura_ira.ura_ira_dashboard, name='ura_ira_dashboard'),
```

I u sidebar (base.html — ne diras direktno, dodaj u sidebar partial ili dynamic_menu):
```
📊 IRA/URA pregled  →  /hr/konto/ura-ira/
```

---

## MOST 5 — predictive_reorder_check: verificiraj beat

```bash
grep -n "predictive.reorder" core/settings.py | head -5
cat inventory/tasks.py | head -30
cat inventory/reorder.py 2>/dev/null | head -20 || echo "ne postoji"
```

Ako `inventory/reorder.py` ne postoji — kreiraj:
```python
# inventory/reorder.py
from decimal import Decimal

def predict_reorder(item):
    """
    Prediktivna analiza potrebe za narudžbom.
    Vraća: {'urgency': 'critical|warning|ok', 'recommended_qty': Decimal, 'insufficient_data': bool}
    """
    if not item.supplier_id or item.min_quantity <= 0:
        return {'insufficient_data': True}

    if item.quantity <= 0:
        return {'urgency': 'critical', 'recommended_qty': item.max_quantity or item.min_quantity * 3}

    ratio = float(item.quantity) / float(item.min_quantity)
    if ratio <= 1.0:
        return {'urgency': 'critical', 'recommended_qty': item.max_quantity or item.min_quantity * 2}
    if ratio <= 1.5:
        return {'urgency': 'warning', 'recommended_qty': item.min_quantity * 2}
    return {'urgency': 'ok', 'recommended_qty': Decimal('0'), 'insufficient_data': False}
```

Verificiraj beat u settings:
```bash
grep -n "predictive-reorder" core/settings.py | head -3
# Treba biti:
# "predictive-reorder-check": {
#     "task": "inventory.tasks.predictive_reorder_check",
#     "schedule": 86400,  # jednom dnevno
# }
```

Ako nije tamo — dodaj (bez diranja .env):
```bash
grep -n "CELERY_BEAT_SCHEDULE.update" core/settings.py | tail -5
# Dodaj na zadnji update blok
```

---

## MOST 6 — R1 Invoice → eRačun pipeline

### Provjeri:
```bash
grep -n "eracun\|ERacun\|fiscal_handler" invoicing/services/ -r | head -15
grep -n "_create_r1_invoice" pos/services/checkout.py | head -5
```

### Fix — u `_create_r1_invoice()`, NAKON što se Invoice kreira i spremi:

```python
# Pokušaj automatski poslati u eRačun pipeline (B2B)
# Samo ako kupac ima OIB (pravna osoba)
if receipt.buyer_oib and len(receipt.buyer_oib) == 11:
    try:
        from invoicing.services.fiscal_f20 import ERacunFiskalizacija20Handler
        handler = ERacunFiskalizacija20Handler()
        handler.handle(invoice)
    except Exception as _er:
        logger.warning(f'R1 eRačun pipeline: {_er}')
        # Ne blokira — invoice je kreiran, eRačun je bonus
```

---

## MOST 7 — SOURCE_TYPES: dodati 'purchase' i 'ura'

READ: konto/models.py (SOURCE_TYPES lista, linija ~191)

DODAJ:
```python
('purchase',    _('Nabava — primka robe')),
('ura',         _('Ulazni račun (URA)')),
('ira',         _('Izdani račun (IRA)')),
('consumption_tax', _('Porez na potrošnju')),
```

MIGRACIJA:
```bash
venv/bin/python manage.py makemigrations konto --name="add_source_types"
venv/bin/python manage.py migrate 2>&1 | tail -3
```

---

## VERIFIKACIJA — svih 7 mostova

```bash
cd /var/www/fina-connect

venv/bin/python manage.py check 2>&1 | tail -3

# Test M1: po_receive → confirm() poziva se?
venv/bin/python manage.py shell << 'EOF'
from procurement.views import po_receive
import inspect
src = inspect.getsource(po_receive)
print("confirm() poziv:", "gr.confirm()" in src or ".confirm()" in src)
EOF

# Test M2: book_goods_receipt postoji?
venv/bin/python manage.py shell -c "
from konto.services_file import book_goods_receipt
print('book_goods_receipt: OK')
" 2>/dev/null

# Test M3: consumption_tax u book_pos_session?
grep -n "2390\|consumption_tax" konto/services_file.py | head -5

# Test M4: IRA/URA dashboard URL?
venv/bin/python manage.py shell -c "
from django.urls import reverse
print('URA/IRA URL:', reverse('konto:ura_ira_dashboard'))
" 2>/dev/null

# Test M7: SOURCE_TYPES 'purchase' postoji?
venv/bin/python manage.py shell -c "
from konto.models import JournalEntry
types = dict(JournalEntry.SOURCE_TYPES)
print('purchase:', 'purchase' in types)
print('ura:', 'ura' in types)
" 2>/dev/null

venv/bin/python manage.py test konto.tests pos.tests.test_pos_central_engine --verbosity=1 2>&1 | tail -10

git add -A
git commit -m "feat(mostovi): URA/IRA tijek, GR→Konto, consumption_tax→2390, IRA/URA dashboard"
```

---

## DONE KRITERIJI — 10/10 checklist:

Mostovi (backend):
- [ ] po_receive poziva gr.confirm() → zaliha se uvećava
- [ ] book_goods_receipt() kreira JE: D:3000/1400 P:2200
- [ ] book_pos_session knjizi consumption_tax na 2390
- [ ] SOURCE_TYPES ima 'purchase', 'ura', 'ira'
- [ ] predictive_reorder_check u live beat scheduleu

Mostovi (frontend):
- [ ] /hr/konto/ura-ira/ dashboard live
- [ ] Saldo banner: što nam duguju vs što mi dugujemo
- [ ] 4 KPI kartice sa live podacima
- [ ] PDV reconciliation widget
- [ ] Alarmi: dospjelo, neproknjiženo, CT dugovanje

Integracija:
- [ ] R1 Invoice → eRačun pipeline (ako OIB postoji)
- [ ] GoodsReceipt → confirm() → konto JE vezan na primku

Tech:
- [ ] manage.py check: 0 errora
- [ ] Je balanced: svi JE
- [ ] git commit čist

---
STATUS: PENDING — čeka CC Code
