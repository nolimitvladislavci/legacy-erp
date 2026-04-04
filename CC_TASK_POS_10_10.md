# CC_TASK: POS 10/10 — Zatvori sve rupe
# Datum: 05.04.2026. | Prioritet: P0 | Rok: 07.04.2026.
#
# MATEMATIKA:
#   joker.html + pos-quick.js = 9.5/10 (UI, shortcuts, offline)
#   Ali: R1 OIB, loyalty earned, upsell u success overlay = NEDOSTAJU u UI
#   quick.html (direktan URL /pos/quick/<id>/) = 6.5/10, nema nove feature
#   Prosjek = 7.8/10 ← ovo je problem
#
# CILJ: jedan POS, jedan standard, 10/10 svuda

PRAVILO: READ templates/pos/joker.html i static/js/pos/pos-quick.js PRIJE svakog WRITE.
PRAVILO: Svaka izmjena mora raditi za SVE pos_type (quick, retail, restaurant, gym, appointment).
PRAVILO: Ne diras backend checkout — samo frontend sloj.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 po završetku.

---

## BLOK 1 — quick.html → redirect na joker [HITNO, 5 min]

### Problem:
`pos:quick_pos` URL rendira `quick.html` (932 linije, bez novih featrsa).
Korisnici s bookmarkom /pos/quick/<id>/ ne vide joker.

### Provjeri:
```bash
grep -n "def quick_pos\b" pos/views.py | head -3
# Trebamo naći view koji rendira 'pos/quick.html'
sed -n '1100,1170p' pos/views.py | grep -n "render\|return\|quick.html"
```

### Fix — pos/views.py, `quick_pos` view:

Pronađi: `return render(request, 'pos/quick.html', {`

ZAMIJENI CIJELU zadnju liniju s:
```python
    # Sve nove terminale preusmjeri na Joker POS
    # quick.html je legacy — sve feature su u joker.html
    return redirect('pos:pos_joker', terminal_id=terminal.pk)
```

PROVJERI da redirect ne stvara petlju:
```bash
grep -n "def pos_joker\|def quick_pos" pos/views.py | head -5
curl -sk "https://limit-connect.com/hr/pos/quick/1/" -o /dev/null -w "%{http_code} %{redirect_url}\n"
```

---

## BLOK 2 — R1 Auto-Invoice: UI u Jokeru [KRITIČNO]

### Problem:
Backend (`_create_r1_invoice` u checkout.py) POSTOJI i radi.
Ali joker.html nema UI za:
1. R1 checkbox ("Izreži R1 / B2B račun")
2. Buyer OIB/VAT input polje
3. Buyer name input

Rezultat: R1 se nikad ne okida jer frontend ne šalje `is_r1=True` i `buyer_oib`.

### Provjeri:
```bash
grep -n "is_r1\|buyer_oib\|buyer_name\|r1.*body\|body.*r1" static/js/pos/pos-quick.js | head -10
grep -n "is_r1\|buyer_oib" pos/views.py | grep "request\.\|POST\.\|get(" | head -10
```

### Fix — joker.html:

Nađi pay-zone div (sadrži `payCash`, `payCard` gumbe) i DODAJ IZNAD pay gumba:

```html
<!-- R1 / B2B RAČUN -->
<div id="r1Zone" style="margin-bottom:8px">
  <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:.82rem;color:var(--text-secondary)">
    <input type="checkbox" id="r1Check" onchange="toggleR1()"
      style="width:16px;height:16px;accent-color:var(--gold)">
    <span>R1 / B2B Račun</span>
  </label>
  <div id="r1Fields" style="display:none;margin-top:6px;display:flex;flex-direction:column;gap:4px">
    <input type="text" id="buyerOib" maxlength="13" placeholder="OIB / VAT ID kupca"
      style="padding:7px 10px;border-radius:8px;border:1px solid var(--border);
      background:var(--surface);color:var(--text);font-size:.85rem;width:100%"
      oninput="oibAutoFill(this.value)">
    <input type="text" id="buyerName" placeholder="Naziv firme (auto-fill)"
      style="padding:7px 10px;border-radius:8px;border:1px solid var(--border);
      background:var(--surface);color:var(--text);font-size:.85rem;width:100%">
  </div>
</div>
```

### Fix — pos-quick.js, `window.pay` funkcija:

Pronađi: `body: JSON.stringify({ items: items, method: method, amount_paid: amtPaid, ...`

DODAJ u JSON body:
```javascript
var r1Check = document.getElementById('r1Check');
var isR1 = r1Check ? r1Check.checked : false;
var buyerOib = isR1 ? (document.getElementById('buyerOib')?.value?.trim() || '') : '';
var buyerName = isR1 ? (document.getElementById('buyerName')?.value?.trim() || '') : '';

// U body JSON:
body: JSON.stringify({
  items: items,
  method: method,
  amount_paid: amtPaid,
  tip_amount: window._tip || 0,
  cashier: window._currentCashier || '',
  cashier_id: window._currentCashierId || '',
  is_r1: isR1,
  buyer_oib: buyerOib,
  buyer_name: buyerName,
}),
```

### Fix — toggleR1() i oibAutoFill() funkcije (dodaj u joker.html inline script):
```javascript
function toggleR1() {
  var checked = document.getElementById('r1Check').checked;
  var fields  = document.getElementById('r1Fields');
  fields.style.display = checked ? 'flex' : 'none';
  if (checked) document.getElementById('buyerOib').focus();
}

function oibAutoFill(oib) {
  if (!oib || oib.length < 8) return;
  // Auto-lookup OIB → ime firme
  clearTimeout(window._oibTimer);
  window._oibTimer = setTimeout(function() {
    fetch('/partners/oib-lookup/?oib=' + encodeURIComponent(oib) + '&country=HR', {
      headers: { 'Accept': 'application/json', 'X-CSRFToken': CSRF }
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.name) {
        document.getElementById('buyerName').value = d.name;
      }
    })
    .catch(function() {});
  }, 600);
}
```

---

## BLOK 3 — Loyalty Earned: prikaz u success overlay [UI gap]

### Problem:
Backend ŠALJE `loyalty_earned` u response ali `showSuccess()` ga ne prikazuje.

### Provjeri:
```bash
grep -n "loyalty_earned\|loyalty.*points\|points.*earn" static/js/pos/pos-quick.js | head -5
grep -n "sucTotal\|sucChange\|sucNum\|successOverlay" static/js/pos/pos-quick.js | head -10
```

### Fix — pos-quick.js, u `.then(function(result)` bloku, AFTER `showSuccess(...)`:

```javascript
if (data.ok) {
  lastReceiptUrl = data.print_url || '';
  lastReceiptId = data.receipt_id || null;
  window.lastReceiptId = lastReceiptId;
  window._publicUrl = data.public_url || null;

  var change = method === 'CASH' ? Math.max(0, amtPaid - parseFloat(data.total)) : 0;
  showSuccess(data.receipt_number, data.total, change);

  // DODAJ: Loyalty earned prikaz
  if (data.loyalty_earned && data.loyalty_earned > 0) {
    var loyEl = document.getElementById('sucLoyalty');
    if (!loyEl) {
      loyEl = document.createElement('div');
      loyEl.id = 'sucLoyalty';
      loyEl.style.cssText = 'color:var(--gold);font-size:.9rem;margin-top:4px;font-weight:600';
      var sucNum = document.getElementById('sucNum');
      if (sucNum) sucNum.parentNode.insertBefore(loyEl, sucNum.nextSibling);
    }
    loyEl.textContent = '+' + data.loyalty_earned + ' bodova';
    loyEl.style.display = 'block';
  }

  // DODAJ: AML flag upozorenje
  if (data.aml_flag) {
    fenixToast('⚠️ AML: Gotovinska transakcija >= 10.000 EUR — evidentirano', 'warning');
  }

  clearBasket();
}
```

---

## BLOK 4 — Stock Badge na artiklima u Jokeru [UI gap]

### Problem:
CC Code je dodao `data-qty` na `prod-btn` (commit 711935c4) ali provjeri:
1. Postoje li `data-qty` atributi na artiklima u joker.html?
2. JS koji ih čita i dodaje badge?

### Provjeri:
```bash
grep -n "data-qty\|data-min-qty\|stockBadge\|stock.badge\|stock.*badge" templates/pos/joker.html | head -10
grep -n "data-qty\|stockBadge" static/js/pos/pos-quick.js | head -5
grep -n "stock_alerts" pos/views.py | grep joker | head -3
```

### Fix — joker.html, article grid (prod-btn):

Pronađi gdje se renderiraju artikli (for petlja u joker.html).
Na `<button class="prod-btn"...` DODAJ data atribute:

```html
<button class="prod-btn"
  data-id="{{ item.pk }}"
  data-name="{{ item.name }}"
  data-price="{{ item.unit_price }}"
  data-vat="{{ item.tax_rate.rate|default:'25' }}"
  data-qty="{{ item.quantity|default:'999' }}"
  data-min-qty="{{ item.min_quantity|default:'0' }}"
  ...>
```

Ako `stock_alerts` context postoji (iz joker view), JS u base_pos ili pos-quick.js:
```javascript
// Po učitavanju — oštampaj stock badge na gumbe
document.querySelectorAll('.prod-btn[data-qty]').forEach(function(btn) {
  var qty = parseFloat(btn.dataset.qty || '999');
  var min = parseFloat(btn.dataset.minQty || '0');
  if (qty <= 0) {
    btn.classList.add('out-of-stock');
    var badge = document.createElement('span');
    badge.className = 'stock-badge-zero';
    badge.textContent = 'NEMA';
    btn.appendChild(badge);
  } else if (min > 0 && qty <= min) {
    var badge = document.createElement('span');
    badge.className = 'stock-badge-low';
    badge.textContent = qty.toFixed(0);
    btn.appendChild(badge);
  }
});
```

---

## BLOK 5 — Joker: base_pos.html theme toggle ispravak

### Provjeri:
```bash
grep -n "data-theme\|light\|toggleTheme\|theme.*toggle" templates/pos/base_pos.html | head -5
grep -n "togglePosTheme\|updatePosThemeBtn" static/js/pos/pos-core.js | head -5
```

### Problem:
`base_pos.html` init script: `if(t==='light') setAttribute('dark')` — OBRNUTO!

```javascript
// STARO (krivo):
(function(){var t=localStorage.getItem('fina-theme');if(t==='light')document.documentElement.setAttribute('data-theme','light');})();
// Ne postavljva dark ako je dark

// ISPRAVNO:
(function(){
  var t = localStorage.getItem('fina-theme') || 'dark';  // POS default = dark
  document.documentElement.setAttribute('data-theme', t);
})();
```

PROVJERI postoji li `togglePosTheme()` i radi li ispravno:
```bash
grep -A 15 "function togglePosTheme" static/js/pos/pos-core.js
```

---

## BLOK 6 — pos-quick.js: paySplit() — šalje li loyaly/r1?

### Provjeri:
```bash
grep -n "function paySplit\|window.paySplit" static/js/pos/pos-quick.js | head -3
grep -A 30 "function paySplit\|window.paySplit" static/js/pos/pos-quick.js | head -35
```

### Fix — paySplit() treba iste parametre kao pay():
```javascript
// U paySplit() body JSON, DODAJ:
is_r1: (document.getElementById('r1Check')?.checked || false),
buyer_oib: (document.getElementById('buyerOib')?.value?.trim() || ''),
buyer_name: (document.getElementById('buyerName')?.value?.trim() || ''),
```

---

## BLOK 7 — Z-Report: completeness check

### Provjeri:
```bash
grep -n "def session_zreport\|zreport" pos/views.py | head -5
# Provjeri što Z-report prikazuje
grep -n "consumption_tax\|r1_count\|split_count\|loyalty\|aml" pos/views.py | grep "zreport\|z_report" | head -10
# Provjeri template
grep -n "consumption_tax\|split\|loyalty\|r1" templates/pos/zreport_pdf.html | head -10
```

Z-Report mora sadržavati:
- [ ] Ukupni promet po načinu plaćanja (CASH/CARD/REVOLUT)
- [ ] Porez na potrošnju (consumption_tax_total) → konto 2393
- [ ] R1 računi: broj i ukupni iznos
- [ ] Split payment: broj i ukupni iznos
- [ ] Loyalty bodovi podijeljeni
- [ ] AML flagovi (gotovinska > 10k EUR)

Ako nedostaju → dodaj u context pos/views.py:session_zreport() i template.

---

## VERIFIKACIJA 10/10

```bash
cd /var/www/fina-connect

# 1. quick_pos redirect?
grep -n "redirect.*pos_joker\|return render.*quick.html" pos/views.py | head -5

# 2. R1 u pos-quick.js?
grep -n "is_r1.*buyer_oib\|buyer_oib.*is_r1" static/js/pos/pos-quick.js | head -3

# 3. Loyalty u showSuccess?
grep -n "loyalty_earned\|sucLoyalty" static/js/pos/pos-quick.js | head -5

# 4. base_pos theme fix?
grep -n "fina-theme\|data-theme" templates/pos/base_pos.html | head -3

# 5. Django check
venv/bin/python manage.py check 2>&1 | tail -3

# 6. Restart
systemctl restart gunicorn-fina && sleep 2

# 7. POS live test
curl -sk "https://limit-connect.com/hr/pos/quick/1/" -o /dev/null -w "%{http_code} %{redirect_url}\n"

git add -A
git commit -m "feat(pos-10-10): R1 OIB UI, loyalty overlay, quick→joker redirect, stock badge, split R1, Z-report komplet"
```

---

## DONE KRITERIJI — POS 10/10

Backend (postoji, radi):
- [x] Split payment → backend ✅
- [x] R1 auto-invoice → backend ✅
- [x] Loyalty earn → backend ✅
- [x] AML 10k check → backend ✅
- [x] Consumption tax → konto ✅
- [x] Book pos session → konto ✅
- [x] Offline sync → pos-offline.js ✅

Frontend (ovo je što nedostaje):
- [ ] B1: quick_pos URL → redirect na joker (eliminira legacy)
- [ ] B2: R1 checkbox + OIB input u pay zone
- [ ] B2: toggleR1() + oibAutoFill() funkcije
- [ ] B2: pay() + paySplit() šalju is_r1/buyer_oib
- [ ] B3: loyalty_earned prikaz u success overlay
- [ ] B3: aml_flag toast u success
- [ ] B4: stock badge na prod-btn artiklima
- [ ] B5: base_pos.html theme init ispravak (dark default)
- [ ] B7: Z-report: CT, R1, split, loyalty u PDF

Matematika kad sve bude:
  Backend:       10/10 (već)
  Joker UI:      10/10 (B2+B3+B4+B5)
  quick redirect: 10/10 (B1 — nema više legacy)
  Z-report:      10/10 (B7)
  UKUPNO:        10/10 ← ovo je to
