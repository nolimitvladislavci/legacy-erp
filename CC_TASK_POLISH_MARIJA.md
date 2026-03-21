## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Poliranje za Mariju (revizor/knjigovođa)

## Kontekst
Marija je revizor i knjigovođa. Vidi greške koje programer ne vidi.
Nije tester — ona je KUPAC. Svaka vizualna greška je razlog za odustajanje.

## Provjeri PRVO što Marija vidi
```bash
# Koji URL koristi za arhivu?
grep -rn "arhiva" /var/www/fina-connect/documents/urls.py
# Kako se briše unos?
grep -rn "delete\|arhiva_delete" /var/www/fina-connect/documents/views.py | head -20
# Što template prikazuje za 0 iznos?
grep -n "amount\|iznos\|total\|0\.00\|€0" /var/www/fina-connect/templates/documents/arhiva_list.html | head -20
```

## Zadatak 1 — Arhiva: filter 0-iznos zapisa

Problem: Marija vidi račune s iznosom 0.00 EUR.
Ovo su test/garbage unosi koji ne bi smjeli biti vidljivi.

U `documents/views.py`, u `arhiva_list` view, pronađi glavni queryset i dodaj filter:
```python
# Sakrij unose s iznosom 0 osim ako korisnik eksplicitno traži
if not request.GET.get('show_zero', ''):
    qs = qs.exclude(total_amount=0)
```

Ili alternativno — ako `total_amount` nije uvijek 0 za prazne, provjeri koji field:
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from documents.models import ArhivaEntry
from companies.models import Company
# Provjeri Konjik unose
c = Company.objects.get(name__icontains='Konjik')
zero = ArhivaEntry.objects.filter(company=c, total_amount=0)
print('Zero iznos unosi:', zero.count())
print('Field names:', [f.name for f in ArhivaEntry._meta.fields if 'amount' in f.name.lower() or 'total' in f.name.lower() or 'iznos' in f.name.lower()])
"
```

## Zadatak 2 — Arhiva: instant delete bez refresh

Problem: Marija obriše unos, ali on ostaje na ekranu dok ne refreša.

Dodaj delete endpoint:
```python
# U documents/views.py
@login_required
@require_POST  
def arhiva_delete(request, entry_id):
    from django.http import JsonResponse
    entry = get_object_or_404(ArhivaEntry, pk=entry_id, company=get_user_company(request))
    entry.delete()
    return JsonResponse({'ok': True})
```

Dodaj URL u documents/urls.py:
```python
path('arhiva/<int:entry_id>/delete/', views.arhiva_delete, name='arhiva_delete'),
```

Dodaj JS u arhiva_list.html — pronađi delete gumb i zamijeni s AJAX:
```javascript
function deleteEntry(id, rowEl) {
    if (!confirm('Obrisati ovaj unos?')) return;
    fetch(`/hr/documents/arhiva/${id}/delete/`, {
        method: 'POST',
        headers: {'X-CSRFToken': getCsrf()}
    }).then(r => r.json()).then(d => {
        if (d.ok) {
            rowEl.style.transition = 'opacity 0.3s';
            rowEl.style.opacity = '0';
            setTimeout(() => rowEl.remove(), 300);
        }
    });
}
```

## Zadatak 3 — Arhiva: prazna lista poruka

Ako queryset vrati 0 rezultata — prikaži lijepu poruku umjesto prazne tablice:
```html
{% if not page_obj.object_list %}
<div style="text-align:center;padding:3rem;color:#64748b;">
    <div style="font-size:2rem;margin-bottom:.5rem">📂</div>
    <div style="font-weight:600">Nema dokumenata</div>
    <div style="font-size:.85rem;margin-top:.25rem">
        {% if q %}Nema rezultata za "{{ q }}"{% else %}Arhiva je prazna{% endif %}
    </div>
</div>
{% endif %}
```

## Zadatak 4 — Generalni UI: loading stanja

Na svim AJAX gumbima koji rade nešto → dodaj disabled + spinner dok čeka:
```javascript
// Pattern koji koristiš svuda:
function withLoading(btn, fn) {
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    fn().finally(() => {
        btn.disabled = false;
        btn.innerHTML = orig;
    });
}
```

## Zadatak 5 — Arhiva: sortiranje po datumu (default newest first)

Provjeri je li default sort `-doc_date` ili `-archived_at`.
Marija očekuje najnovije gore. Ako nije tako — popravi.

## Redoslijed
1. Zadatak 1 (filter 0 iznos) — NAJHITNIJE, Marija to vidi odmah
2. Zadatak 2 (instant delete) — HITNO
3. Zadatak 3 (prazna lista) — brzo
4. Zadatak 4 (loading) — kad stigneš
5. Zadatak 5 (sort) — provjeri je li problem

## Provjera na kraju
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl reload gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/documents/arhiva/
```

## PRAVILA
- Čitaj models.py prije pretpostavki o field imenima
- Backup svaki template prije promjene
- Svaka promjena = django check
- Marija ne smije vidjeti 500 grešku
