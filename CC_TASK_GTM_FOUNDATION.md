# CC_TASK_GTM_FOUNDATION
# Izvršava: CC Code (paralelno s LIMIT_AI_FOUNDATION)
# Koordinira: Sonnet
# Prioritet: VISOK
# Datum: 2026-03-21

## OBAVEZNO PRIJE POČETKA
Pročitaj GTM_PLAN_LIMIT_CONNECT_V1.md — cijeli.

## 3 KONKRETNA ZADATKA (redosljed bitan)

---

### ZADATAK 1 — OIB Auto-Lookup (registration/step1)

#### Novi endpoint:
`/registration/api/oib-lookup/` — GET ?oib=12345678901&country=HR

Logika:
1. Provjeri OIB format (11 cifara za HR)
2. Pokušaj dohvatiti iz sudskog registra ili iz postojeće Company baze
3. Ako postoji u bazi → vrati podatke (firma možda već postoji)
4. Ako ne → pokušaj https://sudreg.pravosudje.hr/registar/f?p=150 scrape ILI
   vrati `{"found": false}` — bolje ništa nego error
5. Vrati JSON: `{"found": true, "name": "...", "address": "...", "oib": "...", "legal_form": "..."}`

#### AJAX u step1.html:
- Input za OIB — na blur event → fetch `/registration/api/oib-lookup/`
- Ako found=true → autofill polja name, address
- Prikaži zeleni checkmark + "Pronašli smo vašu firmu u registru"
- Ako found=false → polja ostaju prazna, bez errora

PAZI: Pročitaj registration/views.py i registration/models.py PRIJE.
Ne pretpostavljaj polja u CompanyRegistration modelu.

---

### ZADATAK 2 — Pricing Kalkulator (/pricing/)

Javna stranica, ne treba login.

#### HTML stranica na /pricing/:
- Prikaži 4 plana (Starter 22€, Professional 69€, Enterprise 189€, Distributor 359€)
- Professional vizualno istaknut (badge "Najpopularnije")
- Interaktivni kalkulator:
  - Slider: "Broj faktura/mj" (0→300, korak 10)
  - Toggle: "Trebam POS blagajnu" Da/Ne
  - Toggle: "Poslovanje u Njemačkoj" Da/Ne
  - Toggle: "Udruga/neprofitna org." Da/Ne
- Logika JS:
  - <30 faktura + bez POS → Starter (22€)
  - 30+ faktura ILI POS → Professional (69€)
  - DE poslovanje ILI 150+ faktura → Enterprise (189€)
  - Uvijek: "Ručno računovodstvo za isti obujam ≈ {X}€/mj" (faktura*2€ + 150€ base)
  - "Uštedite {Y}€ godišnje s LIMIT Connect"
- CTA gumb: "Počnite besplatno 30 dana"

Pročitaj registration/models.py (PricingPlan) i dohvati planove iz baze
(ili hardkodiraj ako je lakše — ali koristiti stvarne cijene: 22/69/189/359).

---

### ZADATAK 3 — Empty States za 3 ključna modula

Kreiraj reusable partial: `templates/partials/empty_state.html`

```html
{% comment %}
Parametri: title, subtitle, cta_text, cta_url, icon (fa klasa)
{% endcomment %}
```

Implementiraj u:
1. **invoicing/index.html** — ako nema faktura:
   "Izdajte prvi račun — 3 minute"
   CTA → /invoicing/wizard/

2. **partners/list.html ili partner index** — ako nema partnera:
   "Dodajte prvog klijenta — 1 minuta"
   CTA → /partners/create/

3. **inventory index** — ako nema artikala:
   "Dodajte prvi artikl na zalihu — 2 minute"
   CTA → /inventory/item/new/

PAZI: Pročitaj stvarne template nazive i view kontekste PRIJE nego implementiraš.
Provjeri je li queryset dostupan u kontekstu. Ne dodavaj extra DB query u view ako
postoji bolji način (npr. `{% if object_list %}` u template).

---

## NA KRAJU
- git add -A && git commit -m "GTM: OIB lookup + pricing kalkulator + empty states"
- Upiši DONE u FENIX_STATUS.md
- Ažuriraj CC_ACTIVE_TASK.md
