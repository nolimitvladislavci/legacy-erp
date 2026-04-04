# CC_TASK_INVOICING_BACKLOG — Preostali invoicing fiksevi
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-25

**Čitaj prvo:** FENIX_STATUS.md, invoicing/views.py, templates/invoicing/invoice_list.html

## Kontekst — što je već DONE (ne raditi ponovo)
- K1 ✅ Ponuda/FA/URA u doctype filteru
- K2 ✅ Pretvori u račun gumb
- K3 ✅ Pretvori u predračun gumb
- K4 ✅ Predračun → Račun gumb
- U4 ✅ Full dropdown per row (Ponuda/Predračun/Račun/Storno/e-Račun/Kloniraj/Email/WhatsApp)
- KAMERA ✅ Gumb u headeru, native camera, Smart Import OCR, spinner
- PDF ✅ build_sections() raw SQL, sekcije rade (VIS-AN-2026-003: 2 sekcije, 148KB)
- REDIRECTI ✅ Svi action viewovi redirectaju na invoicing:index (ne više Admin)
- WHATSAPP ✅ Stvarna implementacija s core.whatsapp.send_text i portal linkom

---

## ZADATAK U1 — Visual flow diagram (PO → P → R → S)

Na vrhu invoice_list.html, odmah ispod naslova, dodaj vizualni flow tracker
za dokumente koji imaju `source_document` ili `derived_documents`.

**Samo za active row** (kad korisnik klikne na red, prikaži flow tog dokumenta):
```
[Ponuda PO-2026-001] ──► [Predračun PR-2026-001] ──► [Račun KNJ-2026-0042] ──► [Storno S-2026-001]
  ✅ Prihvaćeno             ✅ Prihvaćeno               ✅ Plaćeno                ✅ Stornirano
```

Implementacija: inline u dropdown ili kao tooltip na hover/klik.
Koristiti `invoice.source_document` i `invoice.derived_documents.all()` za chain.

---

## ZADATAK U2 — Clone s promjenom doctypea

Trenutni `invoice_clone` uvijek kreira `KNJ-YYYY-NNNN` bez obzira na tip.
Popraviti da:
- Ponuda (PO) → clone je nova ponuda s `PO-YYYY-XXXXXX`
- Predračun (P) → clone je novi predračun
- Račun (R) → clone je novi račun
- Clone otvara edit formu (redirect na `invoicing:invoice_edit`)

```python
# invoicing/views.py — invoice_clone view
@login_required
def invoice_clone(request, pk):
    src = get_object_or_404(Invoice, pk=pk)
    now = timezone.now()

    prefix_map = {'PO': 'PO', 'P': 'PR', 'R': 'KNJ', 'A': 'AV', 'GS': 'GS'}
    prefix = prefix_map.get(src.doctype, 'KNJ')
    new_number = f"{prefix}-{now.year}-{now.strftime('%m%d%H%M%S')}"

    clone = _copy_invoice(src, src.doctype, new_number, extra_fields={'source': 'duplicate'})
    clone.created_by = request.user
    clone.status = 'DRAFT'
    clone.validity_date = None  # Reset validity na klonu
    clone.save()

    for item in src.items.all():
        InvoiceItem.objects.create(
            invoice=clone,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            total_price=item.total_price,
            tax_rate=item.tax_rate,
            tax_rate_obj=item.tax_rate_obj,
        )

    messages.success(request, f'Kloniran: {clone.number}')
    return redirect('invoicing:invoice_edit', pk=clone.pk)
```

---

## ZADATAK U3 — Auto-expire ponuda (Celery task)

Ponude koje nisu prihvaćene nakon `validity_date` → automatski postavljaju status `EXPIRED`.

**Celery task** (invoicing/tasks.py):
```python
@app.task(name='invoicing.auto_expire_quotes')
def auto_expire_quotes():
    """Pokreće se svaki dan u 01:00. Postavlja EXPIRED na istekle ponude."""
    from django.utils import timezone
    today = timezone.now().date()
    expired = Invoice.objects.filter(
        doctype='PO',
        status__in=['DRAFT', 'SENT'],
        validity_date__lt=today,
    ).update(status='EXPIRED')
    return f'Expired {expired} ponuda'
```

Dodaj u Celery Beat schedule:
```python
'auto-expire-quotes': {
    'task': 'invoicing.auto_expire_quotes',
    'schedule': crontab(hour=1, minute=0),
},
```

---

## ZADATAK Z1 — Auto-podsjetnik "ponuda ističe za 3 dana"

Celery task koji šalje WhatsApp/email kompaniji kad ponuda ističe za 3 dana.

```python
@app.task(name='invoicing.quote_expiry_reminder')
def quote_expiry_reminder():
    from django.utils import timezone
    target_date = (timezone.now() + timezone.timedelta(days=3)).date()
    expiring = Invoice.objects.filter(
        doctype='PO',
        status__in=['DRAFT', 'SENT'],
        validity_date=target_date,
    ).select_related('company', 'partner')

    for quote in expiring:
        try:
            company = quote.company
            portal = f'https://limit-connect.com/hr/invoicing/client/{quote.client_token}/'
            msg = (
                f"⚠️ *Ponuda ističe za 3 dana*\n"
                f"{quote.number} — {quote.client_name}\n"
                f"Iznos: {quote.total} {quote.currency}\n"
                f"Rok: {quote.validity_date.strftime('%d.%m.%Y')}\n"
                f"Portal: {portal}"
            )
            # Pošalji na admin WhatsApp firme
            admin_phone = (company.settings or {}).get('admin_whatsapp', '')
            if admin_phone:
                from core.whatsapp import send_text
                send_text(admin_phone, msg, company_id=company.id)
        except Exception:
            pass
```

---

## ZADATAK Z2 — Client portal "Prihvaćam ponudu" gumb

Na stranici `/hr/invoicing/client/<token>/`, za ponude (doctype=PO) u statusu SENT/DRAFT:
dodaj prominentni gumb "✅ Prihvaćam ponudu".

```python
# invoicing/views.py — client_portal view
# Dodaj handling za POST ?action=accept_quote
if request.method == 'POST' and request.POST.get('action') == 'accept_quote':
    if invoice.doctype == 'PO' and invoice.status in ('DRAFT', 'SENT'):
        invoice.status = 'ACCEPTED'
        invoice.save(update_fields=['status'])
        # Notifikacija kompaniji
        try:
            from core.whatsapp import send_text
            admin_phone = (invoice.company.settings or {}).get('admin_whatsapp', '')
            if admin_phone:
                send_text(admin_phone,
                    f"✅ *Ponuda prihvaćena!*\n{invoice.number} — {invoice.client_name}\n{invoice.total} {invoice.currency}",
                    company_id=invoice.company.id)
        except Exception:
            pass
        messages.success(request, 'Hvala! Vaša potvrda je zabilježena.')
```

HTML na client_portal template:
```html
{% if invoice.doctype == 'PO' and invoice.status in 'DRAFT,SENT' %}
<form method="post">
  {% csrf_token %}
  <input type="hidden" name="action" value="accept_quote">
  <button type="submit" class="btn btn-success btn-lg w-100 mt-3">
    ✅ Prihvaćam ponudu
  </button>
</form>
{% endif %}
```

---

## ZADATAK Z3 — Conversion rate metrika

U `invoicing/views.py` → `index()` view, dodaj u `totals` dict:
```python
total_quotes = all_inv.filter(doctype='PO').count()
accepted_quotes = all_inv.filter(doctype='PO', status='ACCEPTED').count()
totals['quote_conversion'] = round(accepted_quotes / total_quotes * 100, 1) if total_quotes else 0
totals['total_quotes'] = total_quotes
totals['accepted_quotes'] = accepted_quotes
```

U template `invoice_list.html`, dodaj stats karticu:
```html
<div class="inv-stat">
  <div>
    <div class="num" style="color:#c9a84c">{{ totals.quote_conversion }}%</div>
    <div class="lbl">Konverzija ponuda ({{ totals.accepted_quotes }}/{{ totals.total_quotes }})</div>
  </div>
  <div style="...font-size:1.1rem">📊</div>
</div>
```

---

## DONE kriterij

- [ ] U1: Flow diagram vidljiv na hoveru/kliku na red u listi
- [ ] U2: Clone kreira isti doctype s ispravnim prefiksom, otvara edit
- [ ] U3: Celery task `auto_expire_quotes` registriran i testiran
- [ ] Z1: `quote_expiry_reminder` task puca 3 dana prije expiry, šalje WhatsApp
- [ ] Z2: "Prihvaćam ponudu" gumb na client portal, notifikacija kompaniji
- [ ] Z3: Conversion rate metrika u stats baru invoice liste
- [ ] Commit: "feat(invoicing): U1-U3 + Z1-Z3 — flow diagram, clone fix, expiry, client accept, metrics"
