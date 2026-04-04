# CC TASK: POS ↔ INVOICING SIMBIOZA — SPRINT 1 (UI Most)
Datum: 04.04.2026. | Rok: 07.04.2026.
Prioritet: VISOK — eliminacija kognitivnog opterećenja korisnika

PRAVILO: READ svaki template PRIJE modifikacije. Nikad ne piši template bez čitanja.
PRAVILO: POSReceipt.invoice je OneToOneField — related_name='pos_receipt'. Koristiti to.
PRAVILO: base.html NE DIRAŠ.
PRAVILO: Nakon svakog koraka: venv/bin/python manage.py check 2>&1 | tail -3
PRAVILO: Svi gumbi touch-first: min-height 44px, min-width 44px.

---

## KORAK 1 — Provjeri stvarno stanje veze POS ↔ Invoice

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from pos.models import POSReceipt
from invoicing.models import Invoice
r = POSReceipt.objects.filter(invoice__isnull=False).first()
if r:
    print('Receipt s invoiceom:', r.pk, '→ Invoice:', r.invoice.number)
else:
    print('Nema recepta s invoiceom jos')
i = Invoice.objects.filter(pos_receipt__isnull=False).first()
if i:
    print('Invoice s POS:', i.number, '← bon:', i.pos_receipt.receipt_number)
" 2>/dev/null | grep -v Warning

---

## KORAK 2 — POS RECEIPT.HTML — Invoice sekcija (R1 gumb + deep link)

READ: /var/www/fina-connect/templates/pos/receipt.html
Provjeri oko linije 260-310 — gdje su akcijski gumbi (ab klasa).

Pronađi blok s gumbima (najvjerojatnije div.ab ili div s class="ab").
NEPOSREDNO PRIJE zatvarajućeg </div> tog bloka dodaj sljedeći HTML:

--- Što dodati (prose opis, CC piše HTML sam) ---
Dodaj sekciju koja provjerava postoji li receipt.invoice.
Ako DA — prikaži zeleni info-bar s ikonom dokumenta, tekstom
"Fiskalni račun: {receipt.invoice.number}" i dva gumba:
  Gumb 1: "📄 Pregledaj R1" → link na /invoicing/{receipt.invoice.pk}/
           stil: secondary, otvara u novom tabu
  Gumb 2: Ako receipt.invoice.status NOT IN ('SENT','PAID') →
           "📤 Pošalji R1" → link na /invoicing/send-email/{receipt.invoice.pk}/
           stil: primary gold

Ako NE (invoice je None) i receipt.status == 'paid' →
prikaži žuti warning-bar:
  "⚠️ Fiskalni račun još nije kreiran"
  Gumb: "Kreiraj R1" → link na /invoicing/create/?from_receipt={receipt.pk}
  (ovaj URL ćemo implementirati u Sprint 2)

CSS klase za bar:
.inv-bar {
  margin: .75rem 1.25rem;
  padding: .75rem 1rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  flex-wrap: wrap;
}
.inv-bar.ok { background: rgba(76,175,125,.12); border: 1px solid var(--green); }
.inv-bar.warn { background: rgba(234,179,8,.1); border: 1px solid #ca8a04; }
.inv-bar-info { font-size: .85rem; font-weight: 600; }
.inv-bar-meta { font-size: .75rem; color: var(--muted); }
.inv-bar-actions { display: flex; gap: .5rem; flex-wrap: wrap; }

---

## KORAK 3 — POS RECEIPT.HTML — R1 kupac modal (OIB na bonu)

READ: /var/www/fina-connect/templates/pos/receipt.html
Provjeri postoji li buyer_oib sekcija u formi.

Ako receipt.status == 'open' i receipt.buyer_oib je prazan:
Dodaj mali collapsible panel (collapsed by default) s labelom "R1 račun (firma)":
  Input OIB kupca (buyer_oib) s gumbom "Lookup" koji poziva /api/invoicing/partner-oib/?oib=X
  Input Naziv kupca (buyer_name) — auto-fill iz OIB lookup
  Input Adresa kupca (buyer_address) — auto-fill
  Gumb "Spremi R1 podatke" → POST na /pos/receipt/{receipt.pk}/update-buyer/ (novi endpoint, korak 5)

---

## KORAK 4 — INVOICING INDEX.HTML — POS badge + deep link

READ: /var/www/fina-connect/invoicing/templates/invoicing/index.html

Pronađi tablicu računa (najvjerojatnije <table> ili grid s listom faktura).
U svakom retku fakture dodaj uvjetno: ako invoice.pos_receipt postoji:
  Badge odmah uz broj računa:
  <a href="/pos/receipt/{invoice.pos_receipt.pk}/"
     class="pos-badge"
     title="POS bon #{invoice.pos_receipt.receipt_number} — klikni za detalje">
    🏪 #{invoice.pos_receipt.receipt_number}
  </a>

CSS za badge (dodaj u <style> blok tog templatea):
.pos-badge {
  display: inline-flex;
  align-items: center;
  background: rgba(201,168,76,.1);
  border: 1px solid var(--gold, #c9a84c);
  color: var(--gold, #c9a84c);
  border-radius: 4px;
  padding: .15rem .45rem;
  font-size: .72rem;
  font-weight: 600;
  text-decoration: none;
  margin-left: .4rem;
  transition: background .15s;
}
.pos-badge:hover {
  background: rgba(201,168,76,.22);
}

NAPOMENA: Badge je deep link — klik otvara POS receipt detalj, ne modal.
Horvoje je primijetio da modal dodaje kompleksnost; deep link je čišći i mobilno kompatibilan.

---

## KORAK 5 — NOVI ENDPOINT: update-buyer na POS receiptu

READ: /var/www/fina-connect/pos/views.py (prvih 30 linija — provjeri importse)
READ: /var/www/fina-connect/pos/urls.py

Dodaj view na kraj pos/views.py:

```python
@require_POST
@login_required
def receipt_update_buyer(request, receipt_id):
    """Sprema R1 kupac podatke na bon (OIB, naziv, adresa)."""
    from pos.models import POSReceipt
    try:
        receipt = POSReceipt.objects.get(pk=receipt_id,
                                          session__terminal__company=request.user.userprofile.company)
    except POSReceipt.DoesNotExist:
        return JsonResponse({'error': 'Bon nije pronađen'}, status=404)
    
    receipt.buyer_oib = request.POST.get('buyer_oib', '').strip()
    receipt.buyer_name = request.POST.get('buyer_name', '').strip()
    receipt.buyer_address = request.POST.get('buyer_address', '').strip()
    receipt.save(update_fields=['buyer_oib', 'buyer_name', 'buyer_address'])
    
    return JsonResponse({'ok': True, 'buyer_oib': receipt.buyer_oib})
```

Dodaj URL u pos/urls.py:
path('receipt/<int:receipt_id>/update-buyer/', views.receipt_update_buyer, name='receipt_update_buyer'),

---

## KORAK 6 — UNIFIED DAILY WIDGET na dashboardu

READ: /var/www/fina-connect/invoicing/views.py (funkcija index, linije 48-130)
READ: /var/www/fina-connect/invoicing/templates/invoicing/index.html (header/stats sekcija)

U invoicing/views.py funkciji index() dodaj POS agregat:

```python
from datetime import date
from pos.models import POSReceipt

today = date.today()
pos_today = POSReceipt.objects.filter(
    session__terminal__company=company,
    session__opened_at__date=today,
    status='paid'
).aggregate(
    total=Sum('total'),
    count=Count('id')
)
pos_total_today = pos_today['total'] or 0
pos_count_today = pos_today['count'] or 0
```

Dodaj u context: 'pos_total_today': pos_total_today, 'pos_count_today': pos_count_today

U invoicing/templates/invoicing/index.html u stats kartice sekciji dodaj novi card:

Unified Daily Card — prikazuje:
  - Invoice prihod danas (već postoji u kontekstu)
  - POS prihod danas (novo)
  - UKUPNO = zbroj oba
  - Vizualno: dvije linije s labelama + debela linija ukupno
  - Boja: zelena ako > jučer, crvena ako < jučer (bez jučer podataka — samo zelena)

HTML card:
```html
{% if pos_total_today or inv_today %}
<div class="stat-card unified-today">
  <div class="stat-label">💰 Ukupno danas</div>
  <div class="unified-breakdown">
    <span class="ub-row">
      <span class="ub-label">📄 Fakturirano</span>
      <span class="ub-val">{{ inv_today|floatformat:2 }} EUR</span>
    </span>
    <span class="ub-row">
      <span class="ub-label">🏪 POS blagajna</span>
      <span class="ub-val">{{ pos_total_today|floatformat:2 }} EUR</span>
    </span>
  </div>
  <div class="stat-value" style="color:var(--green)">
    {{ inv_today|add:pos_total_today|floatformat:2 }} EUR
  </div>
  <div class="stat-sub">{{ pos_count_today }} POS bona + {{ inv_count_today }} računa</div>
</div>
{% endif %}
```

CSS:
```css
.unified-today { border-left: 3px solid var(--green); }
.unified-breakdown { margin: .5rem 0; }
.ub-row { display: flex; justify-content: space-between; font-size: .78rem;
           padding: .2rem 0; color: var(--muted); }
.ub-val { font-weight: 600; color: var(--text); }
```

---

## KORAK 7 — AI PARTNER HINT endpoint (Sprint 2 foundation)

READ: /var/www/fina-connect/invoicing/views.py (grep za api_oib_lookup, linije ~1445)

Dodaj novi view ODMAH ISPOD api_oib_lookup:

```python
@login_required
def api_partner_hint(request):
    """
    AI Partner Assistant — bez Geminija, čisti ORM.
    Vraća povijest suradnje s partnerom za pametno popunjavanje fakture.
    """
    oib = request.GET.get('oib', '').strip()
    if not oib:
        return JsonResponse({'hint': None})
    
    company = request.user.userprofile.company
    from invoicing.models import Invoice
    from django.db.models import Avg, Count, Sum
    from datetime import timedelta
    from django.utils import timezone
    
    qs = Invoice.objects.filter(company=company, partner_oib=oib)
    
    if not qs.exists():
        return JsonResponse({'hint': None, 'msg': 'Novi partner — nema povijesti'})
    
    # Analiza
    total_count = qs.count()
    unpaid_count = qs.filter(status__in=['UNPAID', 'OVERDUE']).count()
    paid_qs = qs.filter(status='PAID')
    
    # Prosječno kašnjenje plaćanja (gruba procjena)
    avg_days = 0
    
    # Top artikli ovog partnera
    from invoicing.models import InvoiceItem
    top_items = (InvoiceItem.objects
                 .filter(invoice__company=company, invoice__partner_oib=oib)
                 .values('description')
                 .annotate(cnt=Count('id'), avg_price=Avg('unit_price'))
                 .order_by('-cnt')[:3])
    
    # Zadnji doctype i valuta
    last_inv = qs.order_by('-created_at').first()
    
    # Upozorenje
    warning = None
    if unpaid_count >= 3:
        warning = f'⚠️ {unpaid_count} neplaćenih računa!'
    elif unpaid_count >= 1:
        warning = f'ℹ️ {unpaid_count} neplaćen račun'
    
    return JsonResponse({
        'hint': {
            'total_invoices': total_count,
            'unpaid_count': unpaid_count,
            'warning': warning,
            'last_doctype': last_inv.doctype if last_inv else 'R',
            'last_currency': last_inv.currency if last_inv else 'EUR',
            'last_payment_method': last_inv.payment_method if last_inv else 'TRANSAKCIJSKI',
            'top_items': list(top_items),
            'partner_name': last_inv.partner_name if last_inv else '',
        }
    })
```

Dodaj URL u invoicing/urls.py:
path('api/partner-hint/', views.api_partner_hint, name='api_partner_hint'),

---

## KORAK 8 — AI Partner Hint UI u invoice_create formi

READ: /var/www/fina-connect/invoicing/templates/invoicing/create.html
ILI READ: /var/www/fina-connect/templates/invoicing/invoice_form.html
(provjeri koji se koristi za kreiranje novog računa)

Pronađi OIB input polje za partnera.
Nakon OIB inputa dodaj:

```html
<div id="partner-hint-panel" class="partner-hint" style="display:none">
  <div class="ph-header">
    <span class="ph-icon">🧠</span>
    <span class="ph-title">Poznati partner</span>
    <span id="ph-warning" class="ph-warning"></span>
  </div>
  <div class="ph-body">
    <div class="ph-row">
      <span class="ph-label">Ukupno računa</span>
      <span id="ph-total" class="ph-val"></span>
    </div>
    <div class="ph-row">
      <span class="ph-label">Zadnji tip</span>
      <span id="ph-doctype" class="ph-val"></span>
    </div>
    <div class="ph-row">
      <span class="ph-label">Valuta</span>
      <span id="ph-currency" class="ph-val"></span>
    </div>
    <div id="ph-items" class="ph-items"></div>
  </div>
  <div class="ph-actions">
    <button type="button" onclick="applyPartnerHint()" class="btn btn-xs btn-gold">
      ✓ Primijeni prethodne stavke
    </button>
  </div>
</div>
```

JavaScript (dodaj u <script> blok):
```javascript
let _partnerHintData = null;

async function fetchPartnerHint(oib) {
  if (!oib || oib.length < 11) return;
  try {
    const r = await fetch(`/invoicing/api/partner-hint/?oib=${oib}`);
    const data = await r.json();
    if (data.hint) {
      _partnerHintData = data.hint;
      showPartnerHint(data.hint);
    }
  } catch(e) {}
}

function showPartnerHint(h) {
  const panel = document.getElementById('partner-hint-panel');
  if (!panel) return;
  document.getElementById('ph-total').textContent = h.total_invoices + ' računa';
  document.getElementById('ph-doctype').textContent = h.last_doctype || 'R';
  document.getElementById('ph-currency').textContent = h.last_currency || 'EUR';
  const warn = document.getElementById('ph-warning');
  warn.textContent = h.warning || '';
  warn.style.color = h.unpaid_count >= 3 ? '#ef4444' : '#ca8a04';
  
  if (h.top_items && h.top_items.length) {
    let html = '<div class="ph-label" style="margin-top:.5rem">Česte stavke:</div>';
    h.top_items.forEach(it => {
      html += `<div class="ph-item-row">
        <span>${it.description}</span>
        <span class="ph-item-price">${parseFloat(it.avg_price).toFixed(2)} EUR</span>
      </div>`;
    });
    document.getElementById('ph-items').innerHTML = html;
  }
  panel.style.display = 'block';
}

function applyPartnerHint() {
  // Popuni valuta i način plaćanja iz hinta
  if (!_partnerHintData) return;
  const curr = document.querySelector('[name="currency"]');
  if (curr) curr.value = _partnerHintData.last_currency || 'EUR';
  const pay = document.querySelector('[name="payment_method"]');
  if (pay) pay.value = _partnerHintData.last_payment_method || 'TRANSAKCIJSKI';
}

// Povezi na OIB input (trigger na blur ili nakon OIB lookup-a)
document.addEventListener('DOMContentLoaded', function() {
  const oibInput = document.querySelector('[name="partner_oib"], #partner_oib, #id_partner_oib');
  if (oibInput) {
    oibInput.addEventListener('blur', () => fetchPartnerHint(oibInput.value.trim()));
  }
  // Ako postoji OIB lookup gumb, povezi i na njega:
  const lookupBtn = document.querySelector('[data-oib-lookup], #oib-lookup-btn');
  if (lookupBtn) {
    lookupBtn.addEventListener('click', () => {
      setTimeout(() => fetchPartnerHint(oibInput?.value.trim()), 800);
    });
  }
});
```

CSS:
```css
.partner-hint {
  background: rgba(201,168,76,.06);
  border: 1px solid rgba(201,168,76,.3);
  border-radius: 8px;
  padding: .875rem 1rem;
  margin-top: .5rem;
  font-size: .82rem;
}
.ph-header { display: flex; align-items: center; gap: .5rem; margin-bottom: .6rem; font-weight: 700; }
.ph-icon { font-size: 1.1rem; }
.ph-warning { margin-left: auto; font-weight: 600; font-size: .8rem; }
.ph-row { display: flex; justify-content: space-between; padding: .2rem 0;
           border-bottom: 1px solid rgba(255,255,255,.05); }
.ph-label { color: var(--muted); }
.ph-val { font-weight: 600; }
.ph-item-row { display: flex; justify-content: space-between; 
               padding: .2rem 0; color: var(--muted); font-size: .78rem; }
.ph-item-price { color: var(--gold); font-weight: 600; }
.ph-actions { margin-top: .75rem; }
```

---

## KORAK 9 — Finalna provjera i commit

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -3
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5

# Provjera 5 ključnih URL-ova:
EXEC: curl -s -o /dev/null -w "invoice index: %{http_code}\n" https://limit-connect.com/invoicing/ -L --cookie "sessionid=test"
EXEC: curl -s -o /dev/null -w "partner hint API: %{http_code}\n" https://limit-connect.com/invoicing/api/partner-hint/?oib=12345678901
EXEC: curl -s -o /dev/null -w "limit-connect home: %{http_code}\n" https://limit-connect.com/

EXEC: cd /var/www/fina-connect && git add -A && git commit -m "feat(simbioza-s1): POS↔Invoice most, partner hint AI, unified daily widget, R1 gumb na bonu"

DONE kriterij:
- receipt.html prikazuje Invoice sekciju (inv-bar) ako postoji invoice
- invoicing/index.html prikazuje pos-badge s deep linkom
- /invoicing/api/partner-hint/ vraća JSON
- Unified daily widget vidljiv na invoice dashboardu
- manage.py check: 0 errors
- git commit postoji

---

## SPRINT 2 PREVIEW (za Gemini, rok 09.04.):
- Celery task pos_invoice_daily_briefing (07:30)
- WhatsApp poruka s dnevnim sažetkom
- ImprovementSuggestion → WhatsApp Ivan notifikacija odmah (ne samo Celery)
- from_receipt parametar u invoice create (auto-fill iz bona)

