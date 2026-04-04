# CC_TASK: T&C Consent Onboarding Flow
## Agent: Claude Code | Prioritet: P0-HITNO | Datum: 2026-03-23

## Kontekst
- `Company.has_signed_tc_consent` polje postoji (migration 0031)
- `@requires_tc_consent` decorator blokira sve FINA/Porezna API pozive
- Trenutno: 0/86 firmi ima `has_signed_tc_consent=True`
- Bez ovoga Knowledge Graph nema pravne osnove za obradu podataka (GDPR)

## Zadatak

### 1. T&C dokument
Kreiraj `/var/www/fina-connect/templates/companies/tc_consent_document.html`
- Pravni tekst za pristanak na obradu podataka (GDPR čl. 6/1b, čl. 13)
- Pokriva: FINA API pozive, VIES provjere, Knowledge Graph obradu
- Verzija: `1.0` — hardkodirana u template
- Datum generiranja: dinamički
- Potpis: checkbox + "Prihvaćam" button

### 2. View + URL
`companies/views.py` — dodaj:
```python
@login_required
def tc_consent_view(request):
    # GET: prikaži dokument
    # POST: spremi has_signed_tc_consent=True, tc_consent_signed_at=now(), tc_consent_version='1.0'
    # Nakon prihvata: redirect na dashboard
```
URL: `/companies/tc-consent/`

### 3. Middleware upozorenje (NE blokiraj — samo upozori)
U `templates/base.html` — dodaj banner koji se prikazuje company_admin/superadmin userima
ako `company.has_signed_tc_consent = False`:
```html
<!-- Prikaži samo ako nema consentа -->
<div class="alert alert-warning" role="alert">
  Za punu funkcionalnost platforme potrebno je prihvatiti uvjete.
  <a href="/companies/tc-consent/">Prihvati uvjete →</a>
</div>
```
Banner se GASI čim firma potpiše.

### 4. Marija first
Nakon implementacije — automatski označi Konjik d.o.o. kao prioritet:
`Company.objects.filter(name__icontains='Konjik').update(...)` — NE, ne radi auto-sign.
Samo osiguraj da je flow funkcionalan i da Marija može sama potpisati kad se sljedeći put prijavi.

## Provjere prije commita
```bash
python manage.py test companies.tests --pattern="*consent*" -v2
```
Ako testovi ne postoje — napiši ih (min. 3):
- test_consent_required_blocks_fina_api
- test_consent_accept_sets_fields
- test_consent_banner_visible_without_consent

## Commit poruka
`T&C: consent onboarding flow, banner, view, tests`
