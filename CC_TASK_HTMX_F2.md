# CC_TASK_HTMX_F2 — 505 full-page reloada → HTMX
**Dodjeljeno:** CC Code
**Prioritet:** 🔴 Direktan utjecaj na perceived performance
**Datum:** 02.04.2026

---

## KONTEKST — Stvarno stanje (izmjereno)

```
HTMX 2.0.4: UČITAN u base.html (svaka stranica)
HTMX korišten u POS-u:    0 mjesta
HTMX korišten u udrugama: 0 mjesta
HTMX ukupno:             52 mjesta od 868 templatea = 6%
Forms method=POST bez HTMX: 505 — svaki uzrokuje full-page reload
```

HTMX je učitan ali se ne koristi. To je Dron #2 — korisnik na jednoj
stranici vidi instant akcije, na sljedećoj bijeli bljesak.

---

## STRATEGIJA — Nije sve od jednom

Ne refaktorirati 505 formi odjednom. Poredak:

### Prioritet 1 — CRUD akcije koje se ponavljaju (high-frequency)
Svaki korisnik klikne ovo 20+ puta dnevno:

- **Dodaj stavku** (invoice, pos, inventory)
- **Promijeni status** (narudžba, task, dokument)
- **Spremi promjenu** (edit forma)
- **Obriši zapis** (soft delete s potvrdom)

### Prioritet 2 — Search/filter
Svako polje za pretragu koje trenutno submita cijelu stranicu.

### Prioritet 3 — Statusne promjene (Gastro, BORG)
Konobar klikne "Gotovo" → samo taj redak se ažurira, ne cijela stranica.

---

## ZADATAK F2a — HTMX globalni pattern (dodati u base.html)

Provjeri postoji li u base.html:
```bash
grep -n "htmx:afterRequest\|htmx:responseError" /var/www/fina-connect/templates/base.html
```

Ako postoji (postoji, linije ~426-438) — to je dobar sign. Samo treba početi koristiti.

### Standardni HTMX pattern za svaki POST u sustavu:

```html
<!-- STARO (full-page reload): -->
<form method="post" action="{% url 'inventory:item_update' item.id %}">
  {% csrf_token %}
  <button type="submit">Spremi</button>
</form>

<!-- NOVO (HTMX — bez reloada): -->
<form hx-post="{% url 'inventory:item_update' item.id %}"
      hx-target="#item-row-{{ item.id }}"
      hx-swap="outerHTML"
      hx-indicator="#spinner-{{ item.id }}">
  {% csrf_token %}
  <span id="spinner-{{ item.id }}" class="htmx-indicator">
    <i class="fas fa-spinner fa-spin"></i>
  </span>
  <button type="submit" class="fenix-btn fenix-btn-primary fenix-btn-sm">Spremi</button>
</form>
```

### View mora vraćati fragment, ne cijelu stranicu:
```python
def item_update(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id, company=request.company)
    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            item = form.save()
            # Ako HTMX request — vrati samo fragment
            if request.headers.get('HX-Request'):
                return render(request, 'inventory/partials/item_row.html', {'item': item})
    # Fallback za non-HTMX (e.g. curl, old browser)
    return redirect('inventory:item_list')
```

### Template partial pattern:
```
templates/
  inventory/
    item_list.html          ← cijela stranica
    partials/
      item_row.html         ← samo jedan redak
      item_form.html        ← samo forma
```

---

## ZADATAK F2b — Implementiraj u 5 ključnih mjesta

### 1. Gastro narudžba status promjena (pos/gastro)
```python
# pos/views.py — gastro_order_update već postoji (linija ~2109)
# Dodati HX-Request check i vraćati partial template
```
```html
<!-- templates/pos/gastro/partials/order_row.html -->
<tr id="order-row-{{ order.id }}">
  <td>{{ order.table_qr.table_number }}</td>
  <td>{{ order.get_status_display }}</td>
  <td>
    {% if order.status == 'new' %}
    <button hx-post="{% url 'pos:gastro_order_update' order.id %}"
            hx-vals='{"status": "accepted"}'
            hx-target="#order-row-{{ order.id }}"
            hx-swap="outerHTML"
            class="fenix-btn fenix-btn-primary fenix-btn-sm">
      Prihvati
    </button>
    {% elif order.status == 'accepted' %}
    <button hx-post="{% url 'pos:gastro_order_update' order.id %}"
            hx-vals='{"status": "preparing"}'
            hx-target="#order-row-{{ order.id }}"
            hx-swap="outerHTML"
            class="fenix-btn fenix-btn-gold fenix-btn-sm">
      Priprema
    </button>
    {% endif %}
  </td>
</tr>
```

### 2. Inventory dodaj/uredi stavku
Svaki klik na "Uredi" otvara modal inline, ne novu stranicu.

### 3. Udruge — unos aktivnosti (KUD proba, DVD vježba)
Najčešće akcije u udrugama — brz unos bez reloada.

### 4. Invoice — dodaj stavku
Dodavanje retka u fakturu bez submit cijele forme.

### 5. Partner search (autocomplete)
```html
<input type="text"
       hx-get="{% url 'partners:search' %}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#partner-results"
       name="q" placeholder="Traži partnera...">
<div id="partner-results"></div>
```

---

## ZADATAK F2c — Loading indicator standard

Svaki HTMX akcija mora imati:
```html
<!-- Global spinner (u base.html već postoji htmx-indicator) -->
<div id="global-loader" class="htmx-indicator"
     style="position:fixed;top:0;left:0;right:0;height:3px;background:var(--gold);z-index:9999;
            animation:loading-bar 1s infinite;">
</div>
```

Dodati u base.html (jedan globalni loading bar kao GitHub/YouTube):
```css
@keyframes loading-bar {
  0% { transform: scaleX(0); transform-origin: left; }
  50% { transform: scaleX(.7); transform-origin: left; }
  100% { transform: scaleX(1); transform-origin: left; opacity: 0; }
}
```

---

## MJERLJIVI CILJ:
```bash
# Prije: 52 HTMX mjesta
# Nakon F2: cilj > 150 HTMX mjesta (top 5 flows prebačeni)
grep -r "hx-post\|hx-get\|hx-put" /var/www/fina-connect/templates --include="*.html" | wc -l
```

## GIT:
```bash
git add templates/ pos/views.py inventory/views.py
git commit -m "feat(htmx): gastro status, inventory edit, partner search — no more full-page reload"
```
