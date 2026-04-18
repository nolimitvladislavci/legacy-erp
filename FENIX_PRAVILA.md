# FENIX PRAVILA — USTAV PROJEKTA
> Verzija: 1.0 | Datum: 2026-04-17 | Autoritet: Ivan Brtan (enter)
> Ovo nije preporuka. Ovo je zakon.

---

## PRAVILO 0 — ISTINA I SAMO ISTINA

Sonnet je alfa i omega tehničkih odluka.
Ivan je na enteru — odobrava smjer, ne implementaciju.

**Što to znači konkretno:**
- Ako kod ne valja — kažemo to odmah, jasno, bez omekšavanja
- Ako arhitektura ima grešku — zaustavimo sve i popravimo
- Ako procjena kaže "neće raditi" — to pišemo, čak i ako Ivan želi čuti suprotno
- Laskanje ubija projekte. Mi gradimo, ne hvalimo
- Svaka sesija počinje s `git log` i `FENIX_STATUS.md` — ne s pretpostavkama
- Svaka sesija završava s ažuriranim `FENIX_STATUS.md` — bez iznimke

**Tko što radi:**
```
Ivan     → enter, smjer, poslovne odluke, finalna potvrda
Sonnet   → arhitektura, koordinacija, code review, istina
CC       → izvršenje, implementacija, testovi
Gemini   → istraživanje, autonomni taskovi, monitoring
```

---

## PRAVILO 1 — CILJ JE 13/10, NE 10/10

10/10 je minimum. Gradimo referentni projekt EU-a.
Drugi će kopirati nas. Mi ćemo biti već tri korake ispred.

**Što je 13/10:**
- Svaka funkcija ima glasovnu alternativu (Web Speech API)
- Svaki ekran radi na mobitelu kao na desktopu — identično
- Svaki korisnik koji ne može tipkati može koristiti sve
- AI je pozadinska podrška — ne traži pohvale, samo radi
- Sistem uči iz svakog korištenja bez da pita za dozvolu
- Invalidni korisnici su u prvom planu, ne afterthought

**Tri stvari iz budućnosti (obvezno u svakom modulu):**
1. **Glasovno upravljanje** — svaka akcija dostupna glasom (HR + DE + EN)
2. **AI oblačić** — tihi asistent koji prati rad i proaktivno pomaže,
   s ikonom zvučnika za čitanje naglas (WCAG AAA)
3. **Prediktivni unos** — sistem predlaže sljedeći korak prije nego korisnik misli

---

## PRAVILO 2 — PRISTUPAČNOST NIJE OPCIJA

Invalidi su ambasadori projekta. Oni su u prvom planu.

**Obvezno na SVAKOM ekranu:**
```html
<!-- AI oblačić — uvijek vidljiv, nikad nametljiv -->
<div class="fenix-ai-bubble" role="complementary" aria-label="AI asistent">
  <button class="ai-speak-btn" aria-label="Pročitaj naglas">
    <!-- Ikona oblačića sa zvučnikom -->
    <svg>...</svg>
  </button>
  <div class="ai-message" aria-live="polite">
    <!-- AI poruka — maksimalno 2 rečenice -->
  </div>
</div>

<!-- Glasovni unos — na svakom polju -->
<button class="voice-input-btn" aria-label="Govori umjesto tipkanja"
        data-target="input-id">
  🎤
</button>
```

**WCAG standardi koje poštujemo:**
- AA minimum, AAA cilj
- Contrast ratio ≥ 7:1 za tekst
- Svaki interaktivni element dostupan tipkovnicom
- Screen reader opisi na svemu
- Font min 16px, nikad manji
- Fokus uvijek vidljiv

**Upravljanje:**
- Glas (Web Speech API — HR, DE, EN)
- Tipkovnica (sve bez miša)
- Touch (sve bez sitnih gumba < 44px)
- Forma (klasični unos — uvijek dostupan)

---

## PRAVILO 3 — AI JE POZADINSKA INFRASTRUKTURA

AI nije feature. AI je utilita poput struje — uvijek tu, nikad u centru pažnje.

**AI oblačić — jedina vidljiva AI manifestacija:**
```
┌─────────────────────────────────┐
│  💬 🔊                          │
│  "Pronašao sam 3 slične stavke. │
│   Želite li automatski popuniti?"│
└─────────────────────────────────┘
```

Oblačić se pojavljuje samo kad ima što reći.
Zvučnik čita poruku naglas na klik.
Maksimalno 2 rečenice — nikad više.
Korisnik može isključiti u postavkama.

**AI radi u pozadini:**
- OCR skeniranje dokumenata (Pixtral)
- Automatska kategorizacija arhive
- Prediktivni unos u formama
- Anomaly detection na računima
- Prijevod (HR ↔ DE ↔ EN) automatski
- Glasovna komanda → akcija (bez potvrde za rutinske radnje)

**AI nikad:**
- Ne traži pohvalu
- Ne prekida tok rada
- Ne pokazuje loading spinere dulje od 200ms
- Ne blokira UI dok razmišlja (sve async)

---

## PRAVILO 4 — KOD STANDARDI (magistarski nivo)

```python
# SVAKI model nasljeđuje BaseModel ili TenantModel
# NIKAD direktno models.Model osim u core/

# SVAKI view nasljeđuje FenixView ili PublicView
# NIKAD direktno View ili TemplateView

# SVAKA forma ima aria-label na svakom polju
# SVAKI gumb ima aria-label ili aria-describedby

# SVAKI modul: max 300 linija po fajlu
# Ako je dulje — refaktoriraj, ne patch-aj

# SVAKI commit mora proći:
# 1. python manage.py check --deploy → 0 errors
# 2. ruff check . → 0 errors
# 3. pytest tests/ → 100% pass (ne coverage — pass)
```

**Imenovanje:**
```python
# Modeli — PascalCase, jednina
class Invoice(TenantModel): ...
class CompanyBranch(TenantModel): ...

# Viewovi — PascalCase + sufiks View
class InvoiceListView(FenixView): ...
class InvoiceCreateView(FenixView): ...

# URL nazivi — app_name:action
# invoicing:list, invoicing:create, invoicing:detail

# Template nazivi — app/action.html
# invoicing/list.html, invoicing/detail.html
# invoicing/partials/row.html  ← HTMX partials ovdje
```

---

## PRAVILO 5 — HTMX FILOZOFIJA

Svaka akcija koja mijenja dio stranice = HTMX partial.
Svaka navigacija koja mijenja cijelu stranicu = full page.
Nikad React. Nikad Vue. Nikad jQuery.

```html
<!-- Ispravno — HTMX partial -->
<button hx-post="/invoicing/create/"
        hx-target="#invoice-list"
        hx-swap="afterbegin"
        hx-indicator="#spinner"
        aria-label="Kreiraj novi račun">
  Novi račun
</button>

<!-- Spinner — uvijek isti pattern -->
<div id="spinner" class="htmx-indicator">
  <div class="fenix-spinner" role="status" aria-label="Učitavam..."></div>
</div>
```

**Pravila za HTMX:**
- `hx-indicator` uvijek prisutan — korisnik mora znati da se nešto događa
- `hx-swap="morph"` za kompleksne zamjene (Idiomorph library)
- `hx-push-url` za navigacijske akcije — browser history mora raditi
- WebSockets za real-time (Celery → Django Channels → HTMX swap)

---

## PRAVILO 6 — TAILWIND DESIGN SYSTEM

Ne koristimo random Tailwind klase. Koristimo design tokens.

**Boje (u tailwind.config.js):**
```javascript
fenix: {
  gold:    '#C9A84C',  // primarna akcijska boja
  ink:     '#1A1209',  // tekst
  paper:   '#FAF8F4',  // pozadina
  cream:   '#F0EDE5',  // sekundarna pozadina
  success: '#1D9E75',
  warning: '#BA7517',
  danger:  '#A32D2D',
  info:    '#185FA5',
}
```

**Komponente (jednom definirane, uvijek iste):**
```html
<!-- Primarni gumb -->
<button class="fenix-btn-primary">...</button>

<!-- Sekundarni gumb -->
<button class="fenix-btn-secondary">...</button>

<!-- Kartica -->
<div class="fenix-card">...</div>

<!-- AI oblačić -->
<div class="fenix-ai-bubble">...</div>
```

Sve u `/var/www/fenix-v3/core/static/css/fenix.css` — jedan fajl, uvijek.

---

## PRAVILO 7 — TESTOVI SU DOKUMENTACIJA

Test nije provjera. Test je specifikacija.
Čitaš test → razumiješ što modul radi.

```python
# SVAKI test opisuje SCENARIJ, ne implementaciju
def test_invoice_fiscalization_generates_jir():
    """
    Scenarij: Marija kreira račun za Gašić d.o.o.
    Sustav mora generirati JIR i ZKI u roku 3 sekunde.
    FINA mock vraća uspjeh.
    """
    # Arrange
    company = CompanyFactory(fiscalization_enabled=True)
    invoice = InvoiceFactory(company=company)

    # Act
    result = fiscalize_invoice(invoice)

    # Assert
    assert result.jir is not None
    assert len(result.jir) == 36  # UUID format
    assert result.zki is not None

# SVAKI modul ima minimum:
# - test_model_creation (happy path)
# - test_model_validation (edge cases)
# - test_view_get (200 OK)
# - test_view_post_valid (redirect)
# - test_view_post_invalid (form errors)
# - test_accessibility (aria-label presence)
```

---

## PRAVILO 8 — DEPLOY BEZ STRAHA

Svaki deploy mora biti reverzibilan u 60 sekundi.

```bash
# Deploy protokol
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --check  # provjeri bez izvršenja
python manage.py migrate          # izvrši
python manage.py collectstatic --noinput
systemctl reload gunicorn-fenix-v3

# Rollback ako nešto ne radi
git revert HEAD --no-edit
python manage.py migrate
systemctl reload gunicorn-fenix-v3
```

**Nikad:**
- `--run-syncdb` u produkciji
- Migracije koje brišu podatke bez provjere
- Deploy u petak popodne
- Deploy bez prethodnog `python manage.py check --deploy`

---

## PRAVILO 9 — ZAŠTO SMO BROJ 1 U EU

Ovo nije marketing. Ovo je arhitekturna činjenica.

**Što konkurencija nema, a mi imamo:**

```
Synesis (HR):
  ✗ Desktop app, Windows only
  ✗ Nema cloud, nema API
  ✗ Nema AI, nema glasovnog unosa
  ✗ Nema mobile
  ✓ Ima tržišni udio — ali stari

Minimax/4D (SI/HR):
  ✗ Nema AI integraciju
  ✗ Nema WhatsApp workflow
  ✗ Nema pristupačnost za invalide
  ✗ Nema offline mode
  ✓ Ima UI — ali generički

DATEV (DE):
  ✗ Monopol cijenom, ne kvalitetom
  ✗ Nema mobile-first
  ✗ Nema WhatsApp-IN
  ✗ Nema AI OCR
  ✓ Ima integracije s bankama

Fenix v3 (HR/DE):
  ✓ AI u svakom modulu — pozadinsko, tiho, efikasno
  ✓ WhatsApp kao primarni UI (Invisible UI)
  ✓ Pristupačnost kao temelj, ne addon
  ✓ Glasovni unos na svim jezicima
  ✓ Mobile-first koji radi offline
  ✓ HR fiscalizacija + DE GoBD/DATEV
  ✓ Umbrella — 1 ured, 80 firmi, 1 klik
  ✓ Open data za državne institucije
  ✓ GDPR by design, ne by compliance
```

**Zašto nas kopiraju, a ne obrnuto:**
Naši korisnici su invalidi, male obrtnice, pekari i stolarije.
To su korisnici koje SAP ignoriše, Minimax ne razumije, DATEV ne želi.
Mi smo jedini koji smo rekli: "Taj korisnik zaslužuje 13/10 iskustvo."
Kad to dokažemo — svi ostali moraju slijediti ili nestati.

---

## PRAVILO 10 — ŽIVI ORGANIZAM

Fenix v3 nije projekt s krajem. To je živi organizam.

**Ciklus razvoja:**
```
Tjedan 1-2: Gradnja (CC + Gemini)
Tjedan 3:   Testiranje s pravim korisnicima
Tjedan 4:   Analiza feedback-a (Sonnet)
Tjedan 5:   Sljedeći ciklus počinje

Nikad:
  - "Gotovo je" — uvijek ima što poboljšati
  - "Dovoljno dobro" — minimum je 13/10
  - "Kasnije ćemo to" — ako je važno, radi se sada
```

**Praćenje budućnosti:**
- Gemini čita Narodne novine RSS svaki dan
- Gemini čita EUR-Lex svaki dan
- Sonnet analizira svaki tjedan: "Što je novo u AI toolingu?"
- CC implementira: minimalno 3 nove funkcije iz budućnosti po rezervoaru

---

## VERZIJA I PROMJENE

Svaka promjena pravila = novi git commit s porukom:
`docs: FENIX_PRAVILA v[X.Y] — [što se promijenilo]`

Pravila se mijenjaju samo uz eksplicitnu odluku Ivana + Soneta.
Nikad agenti sami ne mijenjaju pravila.

---

*"Mi smo primjer drugima. Oni će po našem primjeru kopirati nas,
a mi ćemo biti živi organizam koji se neprestano razvija."*
— Ivan Brtan, 2026-04-17, 08:49 CEST
