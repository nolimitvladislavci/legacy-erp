# GEMINI_TASK_PORTAL_SCAN_FINDINGS.md
# Agent: Gemini | Prioritet: VISOK | Datum: 2026-03-25
# Istraživanje + preporuke na temelju Sonnet portal skena

---

## KONTEKST
Sonnet je skenirao kompletan portal i identificirao prilike za optimizaciju.
Tvoj task: dubinska analiza, konkretni nalazi s brojevima, ne samo opis problema.

---

## ZADATAK 1 — N+1 Query analiza (top 5 mjesta)

Pročitaj ove fajlove i za svaki view koji ima N+1 napiši konkretni prefetch_related fix:

**Prioritetni views za analizu:**
- `invoicing/views.py` — invoice list (items, partner, company)
- `pos/views.py` ili `pos/views_v2.py` — receipt list (items, terminal, session)
- `partners/views.py` — partner list (addresses, contacts)
- `konto/views.py` — journal entry list (lines, account)
- `worktime/views.py` — timesheet list (employee, company)

**Format odgovora za svako mjesto:**
```
MODUL: invoicing
VIEW: invoice_list
QUERYSET: Invoice.objects.filter(company=company)
N+1 UZROK: svaki invoice.items.all() u template lopu
FIX: .prefetch_related('items', 'items__tax_rate', 'partner')
PROCJENA UŠTEDE: ~200ms na 50 faktura (1 query → 3 querija ukupno)
```

---

## ZADATAK 2 — Pricing BORG routing analiza

Pročitaj ove fajlove:
- `website/views.py` — `pricing_ai_advisor()` funkcija (BORG scoring logika)
- `registration/constants.py` — `PLAN_FEATURES` i `PLAN_MODULES`
- `registration/models.py` — `PricingPlan` model

**Odgovori:**
1. Je li BORG scoring u `pricing_ai_advisor()` ispravno mapiran na stvarne slugove PricingPlan modela koji postoje u bazi?
2. Koja su mismatch mjesta između `pricing_ai_advisor` score ključeva i `PricingPlan.slug` vrijednosti?
3. Postoje li planovi u PricingPlan bazi koji nemaju PROFILE_PLAN_MAP entry?
4. Prijedlog: napiši ažuriranu `PROFILE_PLAN_MAP` s ispravnim slug-ovima za svih 6 profila (obrtnik, udruga, rental, firma, racunovodja, gastro)

---

## ZADATAK 3 — Celery Beat reliability audit

Pročitaj `core/settings.py` — sekcija `CELERY_BEAT_SCHEDULE` (40+ taskova).

**Pronađi i liste:**
1. Taskovi koji se pokreću svake 30s ili 60s — jesu li vremenski sigurni (idempotentni)?
2. Taskovi bez `max_retries` — koji mogu zaglavljeni ostati zauvijek?
3. Taskovi koji pozivaju vanjski API (FINA, eVisitor, WhatsApp, Peppol) — jesu li wrapped u try/except s alertom?
4. Duplikati — postoje li isti taskovi definirani više puta u `CELERY_BEAT_SCHEDULE` (npr. wizard-cleanup-stale-drafts)?

**Posebna pažnja:** `einvoice-poll-inbox-30s` — pokreće se svakih 30s. Ako traje >30s, ide queue buildup.

---

## ZADATAK 4 — unscoped() cross-tenant risk assessment

Pročitaj `core/managers.py` da razumiješ što `unscoped()` radi.

Zatim pročitaj ove fajlove i pronađi SVA mjesta gdje se `.unscoped()` poziva u view kontekstu
(nije admin, nije seeding, nije migration):

- `invoicing/views.py`
- `pos/views.py` ili `pos/views_v2.py`
- `konto/views.py`
- `partners/views.py`
- `companies/views.py`

**Za svako unscoped() u view:**
```
FAJL: invoicing/views.py:234
KONTEKST: invoice_list view — regularni user request
RAZLOG unscoped(): nepoznat / radi filtra po datumu
RIZIK: HIGH — korisnik vidi fakture SVIH tvrtki
PREPORUKA: zamijeniti s Invoice.objects.filter(company=request.company)
```

---

## ZADATAK 5 — ServiceAgreement onboarding gap

Pročitaj:
- `registration/models_contracts.py` — ServiceAgreement, ServiceProvider, CompanyDocument
- `registration/views.py` — register_step1 do register_step4
- `registration/urls.py`

**Opiši točno što nedostaje za 3-klik registraciju:**
1. Koji step u registracijskom flowu treba prikazati ugovor?
2. Koji view treba kreirati (naziv, URL, template)?
3. Koji ServiceProvider objekt treba postojati u bazi za HR klijente? (hint: Konjik d.o.o., OIB 37590751921)
4. Napiši prijedlog URL-a: `/registration/agreement/<uuid>/sign/`

**Output:** Mini-specifikacija za CC Code task (CC_TASK_3KLIK_REGISTRACIJA.md može koristiti ovo kao temelj)

---

## ZADATAK 6 — Ghost moduli audit

`INSTALLED_APPS` u settings.py sadrži komentare: `# GHOST: 0 data but referenced by tests`

Pročitaj settings.py i pronađi sve ghost module.
Za svaki ghost modul:
1. Provjeri postoji li `views.py` i je li prazan/stub
2. Provjeri imaju li migration fajlove
3. Je li sigurno ih deinstalirati ili ovise o njima drugi moduli?

Ghost moduli koji su označeni: `fitness`, `gastro_menu`.
Vjerojatno ghost: provjeri `insurance`, `virtual_office`, `edik`.

---

## OUTPUT FORMAT
Napiši nalaze u fajl: `GEMINI_SCAN_REPORT_2026_03_25.md`
Svaki zadatak kao posebna sekcija. Konkretni brojevi, ne procjene.
Na kraju: prioritizirana lista akcija za CC Code (TOP 5 od hitno do može pričekati).
