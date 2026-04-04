# CC_TASK: SPLIT PAYMENT (Vezana plaćanja) — POS 10/10
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P0
# Zakonska osnova: Zakon o fiskalizaciji NN 133/2012, čl. 9
# Model je SPREMAN. Gap je u CheckoutService, view i UI.

PRAVILO: READ pos/models.py i pos/services/checkout.py PRVO.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: select_for_update() za sve payment atomic operacije.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.

---

## ZAKONSKI OKVIR (ne skraćivati, implementirati točno)

### NacinPlac za FINA XML — prioritetno pravilo:
  ima CASH/gotovine → 'G'   (čl. 9: gotovinski bon)
  samo CARD         → 'K'
  samo MOBILE/AIRCASH/REVOLUT/CRYPTO → 'O'
  samo ACCOUNT/VIRMAN → 'T'
  Mješovito s gotovinom → uvijek 'G'

### Kusur — zakonski:
  Kusur se daje ISKLJUČIVO na gotovinu (CASH PaymentLine)
  CARD/MOBILE/REVOLUT → change_given = 0 uvijek
  Formula: ako CASH_paid > (total - ostali_nacini) → kusur = CASH_paid - (total - ostali_nacini)

### PDV:
  Nepromijenjeno — na ukupan iznos bona, neovisno o split-u.

---

## KORAK 1 — PROVJERI TEREN

```bash
grep -n "class POSPaymentLine\|payment_lines\|change_given" pos/models.py | head -10
grep -n "payment_method\|amount_paid\|PaymentLine.objects.create" pos/services/checkout.py | head -15
grep -n "payment_method\|amount_paid\|PaymentLine.objects.create" pos/views.py | head -15
grep -n "NacinPlac\|_payment_code" fiscal/providers/hr_fina.py | head -10
grep -n "payment_method\|naplata\|split\|kartica\|gotovina" templates/pos/joker.html 2>/dev/null | head -20
wc -l templates/pos/joker.html
```

---

## KORAK 2 — CheckoutService: split payment payload

READ: pos/services/checkout.py (cijeli process_receipt, ~linija 265-665)

### 2A — Proširiti payload parsing (PARSE sekcija):

Dodaj ODMAH IZA parsiranja `voucher_amount`:

```python
# ── SPLIT PAYMENT PARSING ──
# Podržava dva formata:
# Format A (legacy): payment_method='CASH', amount_paid=100
# Format B (split):  payments=[{method:'CASH',amount:30},{method:'CARD',amount:70}]
raw_payments = payload.get('payments', [])
if raw_payments and isinstance(raw_payments, list):
    # Format B — split payment
    split_payments = []
    for p in raw_payments:
        method = str(p.get('method', p.get('payment_method', 'CASH'))).upper()
        try:
            amt = Decimal(str(p.get('amount', 0) or 0))
        except (InvalidOperation, ValueError):
            amt = Decimal('0')
        if method not in [m.value for m in POSPaymentLine.Method]:
            method = 'CASH'
        if amt > 0:
            split_payments.append({'method': method, 'amount': amt,
                                   'card_ref': str(p.get('card_reference', '') or '')[:100]})
else:
    # Format A — legacy single payment → konvertiraj u array
    split_payments = [{'method': payment_method, 'amount': Decimal('0'), 'card_ref': ''}]
    # amount=0 → izračunat će se pri kreiranju payment linija
```

### 2B — Zamijeniti payment linija kreiranje (na kraju process_receipt, gdje je `POSPaymentLine.objects.create`):

PRONAĐI blok koji kreira PaymentLine (oko linije 600-635 u checkout.py):
```python
# STARO (obriši):
POSPaymentLine.objects.create(
    receipt=receipt, method=payment_method,
    amount=receipt.total, change_given=change
)
```

ZAMIJENI s:
```python
# NOVO — split payment kreiranje
receipt.recalculate_totals()
total = receipt.total

if split_payments and split_payments[0]['amount'] > 0:
    # Format B — explicitni iznosi
    total_in_payments = sum(p['amount'] for p in split_payments)

    # Validacija: suma ne smije biti manja od total-a
    if total_in_payments < total - Decimal('0.01'):
        raise CheckoutValidationError(
            'SPLIT_UNDERPAID',
            f'Suma plaćanja ({total_in_payments:.2f} EUR) manja od iznosa bona ({total:.2f} EUR).'
        )

    # Kusur — samo na gotovinu
    cash_paid = sum(p['amount'] for p in split_payments if p['method'] == 'CASH')
    non_cash = sum(p['amount'] for p in split_payments if p['method'] != 'CASH')
    cash_change = max(Decimal('0'), cash_paid - (total - non_cash))

    for p in split_payments:
        is_cash = p['method'] == 'CASH'
        POSPaymentLine.objects.create(
            receipt=receipt,
            method=p['method'],
            amount=p['amount'],
            change_given=cash_change if is_cash else Decimal('0'),
            card_reference=p.get('card_ref', ''),
        )
    change = cash_change

else:
    # Format A — legacy: jedan način, puni iznos
    method = split_payments[0]['method'] if split_payments else payment_method
    if method == 'CASH':
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
        receipt=receipt, method=method,
        amount=total, change_given=change,
    )

# Spremi change na receipt
receipt.change_given = change
receipt.save(update_fields=['change_given'])
```

### 2C — Proširiti return dict:
```python
# U return statement — dodaj:
'payments': [
    {'method': pl.method, 'method_display': pl.get_method_display(),
     'amount': float(pl.amount), 'change': float(pl.change_given)}
    for pl in receipt.payment_lines.all()
],
'total_paid': float(sum(pl.amount for pl in receipt.payment_lines.all())),
'change': float(change),
```

---

## KORAK 3 — process_payment view (legacy flow)

READ: pos/views.py (process_payment, linija ~393-430)

ZAMIJENI payment kreiranje:
```python
# STARO:
method = request.POST.get('payment_method', POSPaymentLine.Method.CASH)
amount_paid = Decimal(request.POST.get('amount_paid', str(receipt.total)))
POSPaymentLine.objects.create(receipt=receipt, method=method, amount=receipt.total, change_given=change)

# NOVO — podrška za split iz forme:
import json as _json

# Pokušaj parsirati payments[] iz POST
raw_payments_json = request.POST.get('payments_json', '')
if raw_payments_json:
    try:
        raw_payments = _json.loads(raw_payments_json)
    except Exception:
        raw_payments = []
else:
    raw_payments = []

if raw_payments:
    # Split payment
    total = receipt.total
    non_cash = sum(Decimal(str(p['amount'])) for p in raw_payments if p['method'] != 'CASH')
    cash_paid = sum(Decimal(str(p['amount'])) for p in raw_payments if p['method'] == 'CASH')
    change = max(Decimal('0'), cash_paid - (total - non_cash))
    for p in raw_payments:
        POSPaymentLine.objects.create(
            receipt=receipt,
            method=p['method'].upper(),
            amount=Decimal(str(p['amount'])),
            change_given=change if p['method'].upper() == 'CASH' else Decimal('0'),
            card_reference=str(p.get('card_reference', ''))[:100],
        )
else:
    # Legacy single payment
    method = request.POST.get('payment_method', POSPaymentLine.Method.CASH)
    try:
        amount_paid = Decimal(request.POST.get('amount_paid', str(receipt.total)) or str(receipt.total))
    except Exception:
        amount_paid = receipt.total
    amount_paid = max(amount_paid, receipt.total)
    change = max(Decimal('0'), amount_paid - receipt.total) if method == 'CASH' else Decimal('0')
    POSPaymentLine.objects.create(receipt=receipt, method=method, amount=receipt.total, change_given=change)
```

---

## KORAK 4 — _payment_code() za split (hr_fina.py)

READ: fiscal/providers/hr_fina.py (linija ~161 i ~257)

### 4A — Proširiti _payment_code() za listu:
```python
@staticmethod
def _payment_code(method_or_list):
    """
    Vraća FINA NacinPlac kod.
    Prima: string (legacy) ili list[dict] (split payment).
    
    Prioritetno pravilo (Zakon o fiskalizaciji čl. 9):
      ima CASH → G
      samo CARD → K
      samo MOBILE/REVOLUT/AIRCASH/CRYPTO → O
      samo ACCOUNT/VIRMAN → T
    """
    mapping_single = {
        'cash': 'G', 'gotovina': 'G', 'CASH': 'G',
        'card': 'K', 'kartica': 'K', 'CARD': 'K',
        'transfer': 'T', 'transakcijski': 'T', 'ACCOUNT': 'T',
        'mobile': 'O', 'MOBILE': 'O',
        'revolut': 'O', 'REVOLUT': 'O',
        'aircash': 'O', 'AIRCASH': 'O',
        'crypto': 'O', 'CRYPTO': 'O',
        'voucher': 'G', 'VOUCHER': 'G',  # bon = gotovinska zamjena
    }

    if isinstance(method_or_list, list):
        methods = {str(p.get('method', '')).upper() for p in method_or_list}
        if 'CASH' in methods or 'VOUCHER' in methods:
            return 'G'
        if methods <= {'CARD'}:
            return 'K'
        if methods <= {'ACCOUNT'}:
            return 'T'
        return 'O'

    return mapping_single.get(str(method_or_list), 'O')
```

### 4B — Proširiti poziv _payment_code u fiscalize():
```python
# PRONAĐI liniju:
payment_code = self._payment_code(data.get('payment_method', 'cash'))

# ZAMIJENI s:
# Pokušaj dobiti split payments listu, fallback na string
payment_data = data.get('payments') or data.get('payment_method', 'cash')
payment_code = self._payment_code(payment_data)
```

---

## KORAK 5 — POS Joker UI (split payment widget)

READ: templates/pos/joker.html — pronađi payment/naplata sekciju

DODAJ split payment widget u payment modal/panel. Umetni ISPRED submit gumba:

```html
<!-- SPLIT PAYMENT WIDGET -->
<div id="splitPaymentPanel" style="margin-bottom:1rem;">

  <!-- Toggle gumb -->
  <button type="button" onclick="toggleSplitPayment()"
    id="splitToggleBtn"
    style="width:100%;padding:.6rem;background:rgba(201,168,76,.08);
    border:1px dashed rgba(201,168,76,.4);border-radius:8px;
    color:var(--gold);font-size:.82rem;font-weight:600;cursor:pointer;margin-bottom:.75rem;">
    ⚡ Podijeli plaćanje (gotovina + kartica...)
  </button>

  <!-- Split forma (skrivena inicijalno) -->
  <div id="splitForm" style="display:none;">
    <p style="color:var(--muted);font-size:.78rem;margin-bottom:.75rem;">
      Dodajte načine plaćanja. Zbrojevi moraju pokriti ukupan iznos.
    </p>

    <div id="splitLines">
      <!-- Dinamički se dodaju linije -->
    </div>

    <!-- Preostalo za plaćanje -->
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:.6rem .75rem;background:rgba(201,168,76,.05);border-radius:6px;
      margin-bottom:.75rem;font-size:.85rem;">
      <span style="color:var(--muted);">Preostalo:</span>
      <strong id="splitRemaining" style="color:var(--gold);">0.00 EUR</strong>
    </div>

    <button type="button" onclick="addSplitLine()"
      style="width:100%;padding:.5rem;background:transparent;
      border:1px solid var(--border);border-radius:6px;
      color:var(--muted);font-size:.8rem;cursor:pointer;margin-bottom:.5rem;">
      + Dodaj način plaćanja
    </button>
  </div>

  <!-- Hidden input koji se šalje na server -->
  <input type="hidden" name="payments_json" id="paymentsJson">
</div>

<script>
const PAYMENT_METHODS = [
  {value:'CASH',   label:'💵 Gotovina'},
  {value:'CARD',   label:'💳 Kartica'},
  {value:'MOBILE', label:'📱 Mobilno (mPOS)'},
  {value:'REVOLUT',label:'🔵 Revolut'},
  {value:'AIRCASH',label:'🟡 Aircash'},
  {value:'VOUCHER',label:'🎟️ Bon/Voucher'},
  {value:'ACCOUNT',label:'📄 Na račun'},
];

let splitLines = [];
let receiptTotal = 0;

function initSplitWidget(total) {
  receiptTotal = parseFloat(total) || 0;
  splitLines = [];
  document.getElementById('splitForm').style.display = 'none';
  document.getElementById('splitToggleBtn').style.display = 'block';
  updateSplitRemaining();
}

function toggleSplitPayment() {
  const form = document.getElementById('splitForm');
  const isVisible = form.style.display !== 'none';
  form.style.display = isVisible ? 'none' : 'block';
  if (!isVisible && splitLines.length === 0) {
    addSplitLine('CARD');
    addSplitLine('CASH');
  }
}

function addSplitLine(defaultMethod) {
  const idx = splitLines.length;
  const remaining = Math.max(0, receiptTotal - splitLines.reduce((s,l)=>s+l.amount,0));
  const line = {idx, method: defaultMethod || 'CASH', amount: remaining, card_ref: ''};
  splitLines.push(line);
  renderSplitLines();
}

function removeSplitLine(idx) {
  splitLines = splitLines.filter((_,i) => i !== idx);
  splitLines.forEach((l,i) => l.idx = i);
  renderSplitLines();
}

function renderSplitLines() {
  const container = document.getElementById('splitLines');
  container.innerHTML = '';
  splitLines.forEach((line, i) => {
    const opts = PAYMENT_METHODS.map(m =>
      `<option value="${m.value}" ${m.value===line.method?'selected':''}>${m.label}</option>`
    ).join('');
    container.innerHTML += `
      <div style="display:flex;gap:.5rem;margin-bottom:.5rem;align-items:center;">
        <select onchange="splitLines[${i}].method=this.value;updateSplitRemaining()"
          style="flex:1.5;background:var(--surface-elevated);border:1px solid var(--border);
          border-radius:6px;padding:.5rem;color:var(--text);font-size:.82rem;">${opts}</select>
        <input type="number" step="0.01" min="0"
          value="${line.amount.toFixed(2)}"
          onchange="splitLines[${i}].amount=parseFloat(this.value)||0;updateSplitRemaining()"
          style="flex:1;background:var(--surface-elevated);border:1px solid var(--border);
          border-radius:6px;padding:.5rem;color:var(--text);font-size:.82rem;text-align:right;">
        <span style="color:var(--muted);font-size:.8rem;">EUR</span>
        ${splitLines.length > 1 ? `<button type="button" onclick="removeSplitLine(${i})"
          style="background:rgba(231,76,60,.1);border:none;border-radius:6px;
          padding:.4rem .6rem;color:#e74c3c;cursor:pointer;">×</button>` : ''}
      </div>
    `;
  });
  updateSplitRemaining();
  updateHiddenInput();
}

function updateSplitRemaining() {
  const paid = splitLines.reduce((s,l)=>s+(parseFloat(l.amount)||0), 0);
  const rem = receiptTotal - paid;
  const el = document.getElementById('splitRemaining');
  if (!el) return;
  el.textContent = rem.toFixed(2) + ' EUR';
  el.style.color = rem <= 0.01 ? '#10b981' : 'var(--gold)';
  updateHiddenInput();
}

function updateHiddenInput() {
  const isSplit = document.getElementById('splitForm').style.display !== 'none';
  if (isSplit && splitLines.length > 0) {
    document.getElementById('paymentsJson').value = JSON.stringify(
      splitLines.map(l => ({method:l.method, amount:parseFloat(l.amount)||0}))
    );
  } else {
    document.getElementById('paymentsJson').value = '';
  }
}

function validateSplitBeforeSubmit() {
  const isSplit = document.getElementById('splitForm').style.display !== 'none';
  if (!isSplit) return true;
  const paid = splitLines.reduce((s,l)=>s+(parseFloat(l.amount)||0), 0);
  if (paid < receiptTotal - 0.01) {
    alert('Ukupno plaćanje (' + paid.toFixed(2) + ' EUR) manje od iznosa bona (' + receiptTotal.toFixed(2) + ' EUR). Dopunite plaćanje.');
    return false;
  }
  return true;
}

// Inicijaliziraj kad se poznaje total (pozivati iz POS JS-a):
// initSplitWidget(receiptTotal);
</script>
```

PRONAĐI payment submit gumb u joker.html i dodaj `validateSplitBeforeSubmit()`:
```html
<!-- PRONAĐI submit formu za plaćanje i dodaj onsubmit ili onclick: -->
onsubmit="return validateSplitBeforeSubmit()"
```

PRONAĐI gdje se inicijalizira payment modal i dodaj:
```javascript
initSplitWidget(totalAmount); // totalAmount = varijabla s ukupnim iznosom bona
```

---

## KORAK 6 — PDF BON — prikaži sve payment linije

READ: templates/pos/receipt_print.html ili fiscal/receipt_pdf.html — gdje se ispisuje bon

PRONAĐI sekciju "Način plaćanja" i zamijeni:
```html
<!-- STARO: jedna linija -->
<div>{{ receipt.payment_method_display }}</div>

<!-- NOVO: sve linije -->
{% for pl in receipt.payment_lines.all %}
<div style="display:flex;justify-content:space-between;">
  <span>{{ pl.get_method_display }}</span>
  <span>{{ pl.amount|floatformat:2 }} EUR
    {% if pl.change_given > 0 %} (kusur: {{ pl.change_given|floatformat:2 }}){% endif %}
  </span>
</div>
{% endfor %}
```

---

## KORAK 7 — FISKALIZACIJA integracija

READ: pos/services/checkout.py — gdje se poziva fiscalize_pos_receipt()

ODMAH ISPOD poziva fiskalizacije dodaj payment_data u receipt za fiscal service:
```python
# Pripremi payment data za fiscal provider
receipt._split_payments = list(receipt.payment_lines.values('method', 'amount'))

jir = fiscalize_pos_receipt(receipt)
```

READ: fiskalizacija/fisk.py (ili fiscal/service.py) — gdje se čita receipt za XML

DODAJ u fiscaliz_receipt():
```python
# NacinPlac — split payment prioritet
split_payments = getattr(receipt, '_split_payments', None) or \
    list(receipt.payment_lines.values_list('method', flat=True))

if split_payments:
    if isinstance(split_payments[0], dict):
        methods = {p['method'] for p in split_payments}
    else:
        methods = set(split_payments)

    if 'CASH' in methods or 'VOUCHER' in methods:
        nacin_plac = 'G'
    elif methods <= {'CARD'}:
        nacin_plac = 'K'
    elif methods <= {'ACCOUNT'}:
        nacin_plac = 'T'
    else:
        nacin_plac = 'O'
else:
    nacin_plac = 'G'  # Default gotovina
```

---

## KORAK 8 — VERIFY + TESTOVI

```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -3

# Unit test split payment logike:
venv/bin/python manage.py shell << 'EOF'
from decimal import Decimal
from pos.models import POSPaymentLine

# Simuliraj split: 60 EUR CARD + 50 EUR CASH = 110, total=100, kusur=10
total = Decimal('100.00')
payments = [
    {'method': 'CARD', 'amount': Decimal('60.00')},
    {'method': 'CASH', 'amount': Decimal('50.00')},
]
non_cash = sum(p['amount'] for p in payments if p['method'] != 'CASH')
cash_paid = sum(p['amount'] for p in payments if p['method'] == 'CASH')
change = max(Decimal('0'), cash_paid - (total - non_cash))
print(f'Total: {total}, CARD: 60, CASH: 50, Kusur: {change}')
assert change == Decimal('10.00'), f'Kusur pogrešan: {change}'
print('OK: Kusur izračun ispravan')

# NacinPlac test
from fiscal.providers.hr_fina import HRFINAProvider
code_split = HRFINAProvider._payment_code([{'method':'CASH'},{'method':'CARD'}])
assert code_split == 'G', f'Split CASH+CARD mora biti G, dobio: {code_split}'
code_card = HRFINAProvider._payment_code([{'method':'CARD'}])
assert code_card == 'K', f'Samo CARD mora biti K, dobio: {code_card}'
print('OK: NacinPlac logika ispravna')
EOF

systemctl restart gunicorn-fina && sleep 2
git add -A
git commit -m "feat(split-payment): vezana placanja — CASH+CARD+REVOLUT, kusur logika, NacinPlac fiskalizacija"
```

---

## DONE KRITERIJI:

UI:
- [ ] Split toggle gumb vidljiv u POS payment panelu
- [ ] Moguće dodati N linija (metoda + iznos)
- [ ] Preostalo za plaćanje live update
- [ ] Validacija: suma >= total prije submita
- [ ] Mobile 10/10 (min-height 44px svi gumbi)

Logika:
- [ ] CheckoutService prima payments[] array
- [ ] Kusur samo na CASH liniji
- [ ] Validacija: suma payments >= total (tolerancija 0.01)
- [ ] Legacy format (payment_method string) radi dalje

Fiskalizacija:
- [ ] NacinPlac = G ako ima CASH
- [ ] NacinPlac = K ako samo CARD
- [ ] NacinPlac = O za REVOLUT/AIRCASH/MOBILE
- [ ] Idempotency guard radi dalje

PDF bon:
- [ ] Sve payment linije na bonu
- [ ] Kusur prikazan uz CASH liniju
- [ ] Autorizacijski kod uz CARD liniju (ako postoji)

Tech:
- [ ] manage.py check: 0 errora
- [ ] Unit testovi prolaze (kusur + NacinPlac)
- [ ] git commit čist
