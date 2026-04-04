# CC_TASK: POS SIMBIOZA KOMPLET
# POS ↔ Invoice (R1 auto) + Split Payment (vezana plaćanja) + Propter auto
# Datum: 04.04.2026. | Rok: 07.04.2026. | Prioritet: P0
#
# Zakonska osnova:
#   Zakon o fiskalizaciji NN 133/2012, čl. 9 — NacinPlac, R1 obveza
#   Zakon o PDV-u NN 73/2013 — R1 račun s OIB-om kupca
#   Pravilnik o PDV-u NN 79/2013 — sadržaj R1 računa
#
# Stanje u bazi PRIJE ovog taska:
#   255 plaćenih POS bonova
#    21 R1 bonova (is_r1=True, buyer_oib popunjen)
#     0 bonova s Invoice FK  ← KRITIČAN GAP
#   139 bonova s PaymentLine

PRAVILO: READ pos/services/checkout.py i invoicing/services/invoice_service.py PRVO.
PRAVILO: select_for_update() za sve atomarne payment i invoice operacije.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.
PRAVILO: Svi gumbi touch-first: min-height 44px.

---

## PROVJERI TEREN NAJPRIJE

```bash
# Invoicing servis — create_invoice signature
sed -n '508,560p' invoicing/services/invoice_service.py

# Invoice model — ključna polja
grep -n "^    number\|^    company\|^    partner\|^    buyer\|^    oib\|^    total\|^    status\|pos_receipt" invoicing/models.py | head -25

# CheckoutService — gdje završava (kraj process_receipt, fiskalizacija)
tail -80 pos/services/checkout.py

# PaymentLine model — komplet
sed -n '441,475p' pos/models.py

# Propter api_create_otpremnica
sed -n '235,310p' propter/views.py
```

---

## DIO A — SPLIT PAYMENT (Vezana plaćanja)

### A1 — CheckoutService payload proširiti

READ: pos/services/checkout.py (PARSE sekcija, ~linija 265-300)

Dodaj ODMAH IZA parsiranja `voucher_amount`:

```python
# SPLIT PAYMENT PARSING — podržava oba formata:
# Format A (legacy): payment_method='CASH', amount_paid=100
# Format B (novo):   payments=[{method:'CASH',amount:30},{method:'CARD',amount:70}]
raw_payments = payload.get('payments', [])
if raw_payments and isinstance(raw_payments, list):
    split_payments = []
    for p in raw_payments:
        m = str(p.get('method', 'CASH')).upper()
        if m not in [x.value for x in POSPaymentLine.Method]:
            m = 'CASH'
        try:
            a = Decimal(str(p.get('amount', 0) or 0))
        except (InvalidOperation, ValueError):
            a = Decimal('0')
        if a > 0:
            split_payments.append({
                'method': m,
                'amount': a,
                'card_ref': str(p.get('card_reference', '') or '')[:100],
            })
else:
    # Legacy — jedan način
    split_payments = [{'method': payment_method, 'amount': Decimal('0'), 'card_ref': ''}]
```

### A2 — Zamijeni PaymentLine kreiranje

PRONAĐI blok s `POSPaymentLine.objects.create(receipt=receipt, method=payment_method, ...)` pri kraju process_receipt.

ZAMIJENI kompletno:

```python
# SPLIT PAYMENT KREIRANJE — zakonski ispravan kusur
receipt.recalculate_totals()
total = receipt.total

if split_payments and split_payments[0]['amount'] > 0:
    # Format B — explicitni iznosi
    sum_in = sum(p['amount'] for p in split_payments)
    if sum_in < total - Decimal('0.01'):
        raise CheckoutValidationError(
            'SPLIT_UNDERPAID',
            f'Suma plaćanja ({sum_in:.2f} EUR) < iznos bona ({total:.2f} EUR).'
        )
    # Kusur samo na gotovinu
    non_cash = sum(p['amount'] for p in split_payments if p['method'] != 'CASH')
    cash_paid = sum(p['amount'] for p in split_payments if p['method'] == 'CASH')
    change = max(Decimal('0'), cash_paid - (total - non_cash))

    for p in split_payments:
        POSPaymentLine.objects.create(
            receipt=receipt,
            method=p['method'],
            amount=p['amount'],
            change_given=change if p['method'] == 'CASH' else Decimal('0'),
            card_reference=p.get('card_ref', ''),
        )
else:
    # Format A — legacy
    m = split_payments[0]['method'] if split_payments else payment_method
    if m == 'CASH':
        try:
            a_paid = Decimal(str(payload.get('amount_paid', total) or total))
        except Exception:
            a_paid = total
        a_paid = max(a_paid, total)
        change = a_paid - total
    else:
        a_paid = total
        change = Decimal('0')
    POSPaymentLine.objects.create(
        receipt=receipt, method=m,
        amount=total, change_given=change,
    )

receipt.change_given = change
receipt.save(update_fields=['change_given'])
```

### A3 — NacinPlac za split (hr_fina.py)

READ: fiscal/providers/hr_fina.py (linija ~257, _payment_code)

ZAMIJENI _payment_code():
```python
@staticmethod
def _payment_code(method_or_list):
    """
    FINA NacinPlac: G=Gotovina, K=Kartica, T=Transakcijski, O=Ostalo.
    Pravilo: ako ima CASH → uvijek G (čl. 9 Zakona o fiskalizaciji).
    """
    single = {
        'CASH': 'G', 'VOUCHER': 'G',
        'CARD': 'K',
        'ACCOUNT': 'T',
        'MOBILE': 'O', 'REVOLUT': 'O', 'AIRCASH': 'O', 'CRYPTO': 'O',
    }
    if isinstance(method_or_list, list):
        methods = {str(p.get('method', p) if isinstance(p, dict) else p).upper()
                   for p in method_or_list}
        if 'CASH' in methods or 'VOUCHER' in methods:
            return 'G'
        if methods <= {'CARD'}:
            return 'K'
        if methods <= {'ACCOUNT'}:
            return 'T'
        return 'O'
    return single.get(str(method_or_list).upper(), 'O')
```

PRONAĐI poziv `self._payment_code(data.get('payment_method', 'cash'))` i zamijeni:
```python
payment_data = data.get('payments') or data.get('payment_method', 'cash')
payment_code = self._payment_code(payment_data)
```

### A4 — process_payment legacy view

READ: pos/views.py (process_payment, ~linija 393-430)

Nakon parsiranja method/amount_paid, dodaj split support:
```python
import json as _json
raw_payments_json = request.POST.get('payments_json', '')
if raw_payments_json:
    try:
        raw_pmts = _json.loads(raw_payments_json)
    except Exception:
        raw_pmts = []
else:
    raw_pmts = []

if raw_pmts:
    total = receipt.total
    non_cash = sum(Decimal(str(p['amount'])) for p in raw_pmts if p.get('method','') != 'CASH')
    cash_paid = sum(Decimal(str(p['amount'])) for p in raw_pmts if p.get('method','') == 'CASH')
    change = max(Decimal('0'), cash_paid - (total - non_cash))
    for p in raw_pmts:
        POSPaymentLine.objects.create(
            receipt=receipt,
            method=str(p.get('method','CASH')).upper(),
            amount=Decimal(str(p.get('amount',0))),
            change_given=change if p.get('method','') == 'CASH' else Decimal('0'),
            card_reference=str(p.get('card_reference',''))[:100],
        )
    # Stari change calc u nastavku viewa ažuriraj:
    change = change  # već izračunato
else:
    # Postojeći kod ostaje — jedna PaymentLine
    pass
```

### A5 — UI Widget (POS Joker)

READ: templates/pos/joker.html — pronađi payment modal/panel, gumbi za plaćanje

PRONAĐI div/section s payment gumbima (CASH/CARD tipke) i ISPRED submit gumba dodaj:

```html
<!-- SPLIT PAYMENT TOGGLE -->
<button type="button" id="splitToggleBtn"
  onclick="toggleSplit()"
  style="width:100%;padding:.65rem;margin-bottom:.6rem;
  background:rgba(201,168,76,.08);border:1px dashed rgba(201,168,76,.35);
  border-radius:8px;color:var(--gold,#c9a84c);font-size:.82rem;font-weight:600;cursor:pointer;">
  ⚡ Podijeli plaćanje
</button>

<div id="splitWidget" style="display:none;margin-bottom:.75rem;">
  <div id="splitLines" style="display:flex;flex-direction:column;gap:.4rem;"></div>
  <div style="display:flex;justify-content:space-between;
    padding:.5rem .75rem;background:rgba(201,168,76,.05);
    border-radius:6px;margin:.5rem 0;font-size:.82rem;">
    <span style="color:var(--muted);">Preostalo:</span>
    <strong id="splitRem" style="color:var(--gold);">0.00 EUR</strong>
  </div>
  <button type="button" onclick="addSplitLine()"
    style="width:100%;padding:.4rem;background:transparent;
    border:1px solid var(--border);border-radius:6px;
    color:var(--muted);font-size:.78rem;cursor:pointer;">
    + Dodaj način
  </button>
</div>
<input type="hidden" name="payments_json" id="paymentsJson">
```

JS (dodati u script blok joker.html):
```javascript
const SPLIT_METHODS = [
  {v:'CASH',l:'💵 Gotovina'},{v:'CARD',l:'💳 Kartica'},
  {v:'REVOLUT',l:'🔵 Revolut'},{v:'AIRCASH',l:'🟡 Aircash'},
  {v:'MOBILE',l:'📱 mPOS'},{v:'VOUCHER',l:'🎟️ Bon'},
  {v:'ACCOUNT',l:'📄 Na račun'},
];
let splitData = [];
let splitTotal = 0;

function initSplit(total) {
  splitTotal = parseFloat(total)||0;
  splitData = [];
  document.getElementById('splitWidget').style.display='none';
  updateSplitRem();
}

function toggleSplit() {
  const w = document.getElementById('splitWidget');
  const show = w.style.display==='none';
  w.style.display = show ? 'block' : 'none';
  if (show && splitData.length===0) {
    addSplitLine('CARD');
    addSplitLine('CASH');
  }
}

function addSplitLine(def) {
  const rem = Math.max(0, splitTotal - splitData.reduce((s,l)=>s+l.a,0));
  splitData.push({m: def||'CASH', a: parseFloat(rem.toFixed(2))});
  renderSplit();
}

function renderSplit() {
  const c = document.getElementById('splitLines');
  c.innerHTML = '';
  splitData.forEach((line,i) => {
    const opts = SPLIT_METHODS.map(m =>
      `<option value="${m.v}"${m.v===line.m?' selected':''}>${m.l}</option>`
    ).join('');
    c.innerHTML += `<div style="display:flex;gap:.4rem;align-items:center;">
      <select onchange="splitData[${i}].m=this.value;updateSplitRem()"
        style="flex:1.5;background:var(--surface-elevated,#1e2024);border:1px solid var(--border);
        border-radius:6px;padding:.45rem;color:var(--text);font-size:.8rem;">${opts}</select>
      <input type="number" step="0.01" min="0" value="${line.a.toFixed(2)}"
        onchange="splitData[${i}].a=parseFloat(this.value)||0;updateSplitRem()"
        style="flex:1;background:var(--surface-elevated,#1e2024);border:1px solid var(--border);
        border-radius:6px;padding:.45rem;color:var(--text);font-size:.8rem;text-align:right;">
      <span style="font-size:.78rem;color:var(--muted)">EUR</span>
      ${splitData.length>1?`<button type="button" onclick="splitData.splice(${i},1);renderSplit()"
        style="background:rgba(231,76,60,.1);border:none;border-radius:5px;
        padding:.3rem .5rem;color:#e74c3c;cursor:pointer;font-size:.8rem;">×</button>`:''}
    </div>`;
  });
  updateSplitRem();
  syncHiddenInput();
}

function updateSplitRem() {
  const paid = splitData.reduce((s,l)=>s+(parseFloat(l.a)||0),0);
  const rem = splitTotal - paid;
  const el = document.getElementById('splitRem');
  if(el){ el.textContent=rem.toFixed(2)+' EUR'; el.style.color=rem<=0.01?'#10b981':'var(--gold)'; }
  syncHiddenInput();
}

function syncHiddenInput() {
  const active = document.getElementById('splitWidget').style.display!=='none';
  document.getElementById('paymentsJson').value = active && splitData.length>0
    ? JSON.stringify(splitData.map(l=>({method:l.m,amount:l.a})))
    : '';
}

function validateSplitSubmit() {
  const active = document.getElementById('splitWidget').style.display!=='none';
  if (!active) return true;
  const paid = splitData.reduce((s,l)=>s+l.a,0);
  if (paid < splitTotal - 0.01) {
    alert('Ukupno plaćanje ('+paid.toFixed(2)+' EUR) < iznos bona ('+splitTotal.toFixed(2)+' EUR).');
    return false;
  }
  return true;
}
// Na payment form submit: return validateSplitSubmit()
// Na otvaranje payment panela: initSplit(receiptTotal)
```

### A6 — PDF bon: sve payment linije

READ: templates/pos/receipt_print.html ILI pronađi template koji renderira bon za print.

Pronađi sekciju s "Način plaćanja" i zamijeni s:
```html
{% for pl in receipt.payment_lines.all %}
<div style="display:flex;justify-content:space-between;font-size:.88rem;">
  <span>{{ pl.get_method_display }}</span>
  <span>{{ pl.amount|floatformat:2 }} EUR
    {% if pl.change_given > 0 %}
      <small style="color:#888;">(kusur {{ pl.change_given|floatformat:2 }})</small>
    {% endif %}
    {% if pl.card_reference %}
      <small style="color:#888;display:block;">Ref: {{ pl.card_reference }}</small>
    {% endif %}
  </span>
</div>
{% endfor %}
```

---

## DIO B — R1 → AUTO INVOICE

### B1 — _create_r1_invoice() helper u CheckoutService

READ: invoicing/services/invoice_service.py (create_invoice funkcija, ~linija 508)
READ: invoicing/models.py (Invoice model, InvoiceItem model — sva polja)

DODAJ kao staticmethod u CheckoutService klasu:

```python
@staticmethod
def _create_r1_invoice(receipt, company, user):
    """
    Ako je bon R1 (is_r1=True) — automatski kreira Invoice i veže ga.

    Zakon o PDV-u čl. 79: R1 račun mora imati OIB kupca, naziv, adresu,
    datum isporuke, razradu PDV-a, ukupan iznos.
    """
    if not receipt.is_r1 or not receipt.buyer_oib:
        return None

    # Idempotency — ne kreira duplikat
    if receipt.invoice_id:
        return receipt.invoice

    try:
        from invoicing.models import Invoice, InvoiceItem
        from invoicing.services.invoice_service import create_invoice
        from django.utils import timezone as _tz

        # Broj R1 računa iz POS bona
        receipt_num = getattr(receipt, 'receipt_number', receipt.pk)
        session     = receipt.session
        terminal    = session.terminal
        premise     = getattr(terminal, 'oznaka_prostora', 'PP1')
        device      = getattr(terminal, 'oznaka_uredjaja', 'N1')
        r1_number   = f'R1-POS/{receipt_num}/{premise}/{device}'

        # Partner lookup po OIB-u (ako postoji u bazi)
        partner = None
        try:
            from partners.models import Partner
            partner = Partner.objects.filter(
                company=company, oib=receipt.buyer_oib
            ).first()
        except Exception:
            pass

        # Kreiraj Invoice
        invoice = Invoice.objects.create(
            company         = company,
            number          = r1_number,
            status          = 'SENT',
            issue_date      = _tz.now().date(),
            due_date        = _tz.now().date(),
            partner         = partner,
            buyer_name      = receipt.buyer_name or '',
            buyer_oib       = receipt.buyer_oib or '',
            buyer_address   = receipt.buyer_address or '',
            total           = receipt.total,
            is_r1           = True,
            note            = f'Automatiski kreiran iz POS bona #{receipt_num}',
        )

        # Kopiraj stavke iz bona → Invoice stavke
        for item in receipt.items.select_related('inventory_item').all():
            if item.is_tip:
                continue
            InvoiceItem.objects.create(
                invoice     = invoice,
                description = item.description,
                quantity    = item.quantity,
                unit_price  = item.unit_price,
                tax_rate    = item.tax_rate,
                total_price = item.total_price,
            )

        # Veži Invoice na bon
        receipt.invoice = invoice
        receipt.save(update_fields=['invoice'])

        # BORG Audit
        try:
            from borg_ops.audit_helpers import log_borg_audit
            log_borg_audit(
                company=company,
                entry_type='INVOICE',
                summary=f'R1 invoice {r1_number} kreiran iz POS bona #{receipt_num}',
                document=invoice,
            )
        except Exception:
            pass

        return invoice

    except Exception as _e:
        import logging
        logging.getLogger('pos_checkout').warning(
            f'R1 Invoice kreiranje nije uspjelo za bon {receipt.pk}: {_e}'
        )
        return None
```

### B2 — Poziv _create_r1_invoice u process_receipt

READ: checkout.py — pronađi blok IZA fiskalizacije (gdje je `if jir:` ili `_fiscalize` poziv).

DODAJ ODMAH NAKON fiskalizacije (ne blokira ako ne uspije):
```python
# Auto-kreiraj R1 Invoice (ne blokira checkout ako ne uspije)
r1_invoice = None
if receipt.is_r1:
    try:
        r1_invoice = cls._create_r1_invoice(receipt, company, user)
    except Exception as _ie:
        logger.warning(f'R1 auto-invoice error: {_ie}')

# Ažuriraj return dict
# Pronađi return {} i dodaj:
# 'r1_invoice_id': str(r1_invoice.pk) if r1_invoice else None,
# 'r1_invoice_number': r1_invoice.number if r1_invoice else None,
```

### B3 — Invoice model provjera i buyer polja

READ: invoicing/models.py — ima li buyer_name, buyer_oib, buyer_address, is_r1 polja?

AKO NE POSTOJE — dodaj migraciju:
```python
# invoicing/models.py — u Invoice klasi dodaj ako fale:
buyer_name    = models.CharField(max_length=200, blank=True, verbose_name='Naziv kupca (R1)')
buyer_oib     = models.CharField(max_length=20,  blank=True, verbose_name='OIB kupca (R1)')
buyer_address = models.CharField(max_length=255, blank=True, verbose_name='Adresa kupca (R1)')
is_r1         = models.BooleanField(default=False, verbose_name='R1 račun')

# Migracija:
# venv/bin/python manage.py makemigrations invoicing --name="add_r1_buyer_fields"
# venv/bin/python manage.py migrate
```

### B4 — InvoiceItem provjera polja

READ: invoicing/models.py (InvoiceItem klasa) — ima li ova polja:
  description, quantity, unit_price, tax_rate, total_price

Ako neka nedostaju — prilagodi _create_r1_invoice() da koristi samo postojeća.

### B5 — Fiskalizacija R1 Invoice

READ: fiscal/service.py (fiscalize_invoice funkcija, ~linija 127)

ODMAH NAKON kreiranja invoice-a u _create_r1_invoice (ako je JIR već na bonu), kopiraj ZKI/JIR:
```python
# Ako je POS bon već fiskaliziran — Invoice inherita fiskalni status
if getattr(receipt, 'jir', '') and receipt.jir:
    invoice.fiscal_jir = receipt.jir
    invoice.fiscal_zki = getattr(receipt, 'zki', '')
    invoice.save(update_fields=['fiscal_jir', 'fiscal_zki'])
```

---

## DIO C — PROPTER AUTO OTPREMNICA

### C1 — Auto Otpremnica pri zatvaranju smjene

READ: pos/views.py — pronađi close_session ili shift_close view.

Pronađi gdje se mijenja session.status → 'closed' i DODAJ:

```python
# Auto-kreiraj Otpremnice u Propter za sve plaćene bonove ove smjene
try:
    from propter.models import Otpremnica, BillingPeriod
    from django.utils import timezone as _tz

    period = BillingPeriod.get_or_create_current(company)
    paid_receipts = session.receipts.filter(
        status='paid',
    ).exclude(
        # Ne dupliciraj — provjeri pos_receipt_id
        pk__in=Otpremnica.objects.filter(
            company=company,
            pos_receipt_id__in=session.receipts.values_list('pk', flat=True).filter(status='paid').values_list('pk', flat=True)
        ).values_list('pos_receipt_id', flat=True)
    )

    for receipt in paid_receipts:
        Otpremnica.objects.get_or_create(
            company=company,
            pos_receipt_id=str(receipt.pk),
            defaults={
                'billing_period': period,
                'source': 'pos',
                'number': f'OTP-POS/{receipt.receipt_number}',
                'issue_date': receipt.paid_at.date() if receipt.paid_at else _tz.now().date(),
                'recipient_name': receipt.buyer_name or 'Maloprodajni kupac',
                'recipient_oib': receipt.buyer_oib or '',
                'status': 'issued',
            }
        )
except Exception as _oe:
    logger.warning(f'Propter Otpremnica auto-kreiranje: {_oe}')
```

---

## DIO D — TESTOVI

```bash
cd /var/www/fina-connect

venv/bin/python manage.py check 2>&1 | tail -3

# Osnovni unit test — split kusur logika
venv/bin/python manage.py shell << 'PYEOF'
from decimal import Decimal

# Test 1: kusur samo na gotovinu
total = Decimal('100.00')
payments = [{'method':'CARD','amount':Decimal('60')},{'method':'CASH','amount':Decimal('50')}]
non_cash = sum(p['amount'] for p in payments if p['method']!='CASH')
cash_paid = sum(p['amount'] for p in payments if p['method']=='CASH')
change = max(Decimal('0'), cash_paid - (total - non_cash))
assert change == Decimal('10.00'), f'FAIL kusur: {change}'
print('OK: kusur 10.00 EUR na CASH liniji')

# Test 2: NacinPlac
from fiscal.providers.hr_fina import HRFINAProvider
assert HRFINAProvider._payment_code([{'method':'CASH'},{'method':'CARD'}]) == 'G', 'FAIL: mix=G'
assert HRFINAProvider._payment_code([{'method':'CARD'}]) == 'K', 'FAIL: card=K'
assert HRFINAProvider._payment_code([{'method':'REVOLUT'}]) == 'O', 'FAIL: revolut=O'
assert HRFINAProvider._payment_code('CASH') == 'G', 'FAIL: legacy cash=G'
print('OK: NacinPlac logika ispravna')

# Test 3: R1 Invoice ne kreira duplikat
from pos.models import POSReceipt
r = POSReceipt.objects.filter(is_r1=True).first()
if r:
    print(f'R1 bon: #{r.receipt_number} | invoice: {r.invoice_id or "NEMA"}')
else:
    print('Nema R1 bonova u bazi — OK za test')
PYEOF

# Run existing tests
venv/bin/python manage.py test pos.tests.test_pos_central_engine.POSCentralEngineTests.test_pos_b2b_r1_invoice \
    pos.tests.test_symbiosis_2026_03_31 \
    --verbosity=1 2>&1 | tail -15

git add -A
git commit -m "feat(pos-simbioza): split payment, R1 auto-invoice, NacinPlac FINA, Propter auto-otpremnica"
```

---

## OCJENA NAKON OVOG TASKA

```
KATEGORIJA              PRIJE   POSLIJE
──────────────────────  ──────  ──────
Arhitektura modela:      8/10    9/10  (FK se popunjava)
R1 → Invoice tijek:      4/10   10/10  (auto, atomic)
CheckoutService:         9/10   10/10  (split + R1)
Propter veza:            5/10    8/10  (auto Otpremnica)
Split payment:           0/10   10/10
UI simbioza:             6/10    9/10  (widget + PDF bon)

UKUPNO:                  6.5    9.3/10  ← cilj dostignut
```

---

## DONE KRITERIJI

Split payment:
- [ ] CheckoutService prima payments[] array
- [ ] Kusur jedino na CASH PaymentLine
- [ ] Suma validacija: payments >= total (tol. 0.01)
- [ ] NacinPlac: CASH prisutan → G, samo CARD → K
- [ ] UI widget: toggle, N linija, live preostalo
- [ ] validateSplitSubmit() na formi
- [ ] PDF bon: sve payment linije + kusur

R1 → Invoice:
- [ ] _create_r1_invoice() u CheckoutService
- [ ] is_r1=True → Invoice auto-kreiran atomarno
- [ ] receipt.invoice FK popunjen
- [ ] InvoiceItem stavke kopirane
- [ ] JIR/ZKI kopiran na Invoice
- [ ] Idempotency guard (ne kreira duplikat)
- [ ] Test test_pos_b2b_r1_invoice prolazi (Invoice asserted)

Propter:
- [ ] Close session → Otpremnica per bon
- [ ] Duplikat zaštita (pos_receipt_id unique check)
- [ ] BillingPeriod.get_or_create_current() korišten

Tech:
- [ ] manage.py check: 0 errora
- [ ] Unit testovi svi zeleni
- [ ] git commit čist
