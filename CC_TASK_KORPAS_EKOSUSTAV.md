# CC_TASK: KORPAŠ GRUPA — Digitalni ekosustav
# Dodijelio: Sonnet | Datum: 2026-04-01 | Prioritet: 🔴
# Izvršava: CC Code autonomno — čitaj models.py prije svakog koda!

---

## KONTEKST I ARHITEKTURA

Vlasnik svega: Kruljac Ivica | WA: +385913912621 (placeholder — mehaničar dobiva drugi broj naknadno)

```
/korpas/                → NOVA HUB stranica (zamijeni postojeći template koji je OPG priča)
/korpas/termini/        → Online termini Korpaš servis (NOVO)
/korpas/sirokisor/      → Široki Šor (NOVO)
/korpas/opg-kruljac/    → OPG Kruljac Slađana (NOVO — preseli OPG sadržaj iz landing_korpas.html)
/no-limit/              → POSTOJI ✅ — samo dodaj AirCash sekciju
/validator/             → POSTOJI ✅ — ne diraj
/cro-validator/         → NOVI redirect → /validator/
```

NAPOMENA: `landing_korpas.html` trenutno prikazuje OPG/sir priču.
CC Code treba:
1. Sadržaj landing_korpas.html → premjestiti u novi `opg_kruljac.html`
2. landing_korpas.html → pretvoriti u GRUPU HUB

---

## TASK 1 — Korpaš Grupa HUB (refactor landing_korpas.html)

**File:** `templates/website/landing_korpas.html`
**URL:** `/korpas/`

Dizajn: premium, tamno zelena #1a3d2b + zlatna #c9a84c + bijela. Mobile-first.

Struktura:
- NAVBAR: logo "KORPAŠ GRUPA" | linkovi: Servis | Široki Šor | OPG Kruljac | No Limit
- HERO: "Korpaš Grupa — Servis · Okus · Zemlja · Zajednica" | Čepin, Slavonija
- 4 KARTICE (svaka klikabilna, vodi na podstranicu):

  🔧 KORPAŠ SERVIS
  Vulkanizer · Mehaničar teretnih vozila · Dijagnostika · Zamjena ulja · Registracija
  CTA: "Rezerviraj termin →" → /korpas/termini/

  🍷 ŠIROKI ŠOR
  Restoran · Kafić · Kušaonica sira · Najam sale do 50 osoba · Sobe (uskoro)
  CTA: "Rezerviraj stol ili salu →" → /korpas/sirokisor/

  🐄 OPG KRULJAC SLAĐANA
  Farma krava · Mlijeko · Domaći sir · OPG Burza Slavonije
  CTA: "Naruči direktno →" → /korpas/opg-kruljac/

  🤝 UDRUGA NO LIMIT
  AirCash partner · Digitalna sloboda · Lokalna mreža bez kartice
  CTA: "Saznaj više →" → /no-limit/

- SEKCIJA CroXML Verify:
  "🔐 Digitalna sigurnost standarda — Koristimo CroXML Verify, jedini HR validator
  za e-Račune, fiskalizaciju i digitalne potpise."
  Link: "Otvori validator →" → /validator/

- FOOTER: adresa Čepin/Vladislavci, kontakt Kruljac Ivica, Google Maps embed Vladislavci

---

## TASK 2 — Online termini Korpaš servis

**URL:** `/korpas/termini/`
**View:** dodaj u `website/views.py` ili `core/views.py`
**Template:** `templates/website/korpas_termini.html`

Model — provjeri postoji li KorpasTermin, ako ne, kreiraj u `website/models.py`:
```python
class KorpasTermin(models.Model):
    ime = models.CharField(max_length=100)
    telefon = models.CharField(max_length=20)
    VRSTA = [('osobno','Osobno vozilo'),('teretno','Teretno vozilo'),('kombi','Kombi/Van'),('ostalo','Ostalo')]
    vrsta_vozila = models.CharField(max_length=20, choices=VRSTA)
    USLUGE = [
        ('vulkanizacija','Vulkanizacija (zamjena/balansiranje)'),
        ('mehanika','Mehanička dijagnostika'),
        ('obd','OBD dijagnostika (skeniranje)'),
        ('ulje','Zamjena ulja i filtera'),
        ('registracija','Priprema za tehnički pregled'),
        ('ugradnja','Ugradnja opreme'),
        ('ostalo','Ostalo'),
    ]
    usluga = models.CharField(max_length=30, choices=USLUGE)
    datum = models.DateField()
    vrijeme = models.TimeField()
    napomena = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='novi',
        choices=[('novi','Novi'),('potvrdjen','Potvrđen'),('obavljen','Obavljen'),('otkazan','Otkazan')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['datum','vrijeme']
```

Forma: ime, telefon, vrsta vozila, usluga, datum (min=today), vrijeme (08:00-17:00, korak 30min), napomena
Submit → spremi u bazu → WhatsApp na +385913912621:
  "🔧 NOVI TERMIN KORPAŠ\n{ime} | {telefon}\n{usluga} | {vrsta_vozila}\n{datum} u {vrijeme}"
Korisnik vidi: "✅ Termin primljen! Kontaktirat ćemo vas u roku 2h."
Admin: registriraj KorpasTermin u Django admin

Migracija: `venv/bin/python manage.py makemigrations && venv/bin/python manage.py migrate`

---

## TASK 3 — Široki Šor

**URL:** `/korpas/sirokisor/`
**Template:** `templates/website/sirokisor.html`

Dizajn: slavonski ambient — cigla #8b3a2a + pšenica #e8d5a3 + tamno drvo #2d1b0e

Sekcije:
- HERO: "Široki Šor — gdje se Slavonija osjeća kao kod kuće" | Vladislavci
- 🍽️ Restoran & Kafić — slavonska kuhinja, domaći sir OPG Kruljac, domaće vino
- 🧀 Kušaonica sira — degustacija, rezervacija za grupe
- 🎉 Najam sale — kapacitet do 50 osoba, oprema (stolovi/stolice/razglas), za fešte/rođendane/slavlja
- 🛏️ Sobe — "Uskoro dostupno — dozvole u procesu" (siva kartica, nedostupno)

Rezervacijska forma:
  Ime | Telefon | Vrsta (Stol/Sala/Kušaonica) | Datum | Broj gostiju | Napomena
  → WhatsApp +385913912621: "🍷 REZERVACIJA ŠIROKI ŠOR\n..."
  → Ekran: "Rezervacija primljena! Potvrdit ćemo u roku 2h."

Galerija: 6 placeholder kartica (emoji + opis) — slike Kruljac šalje naknadno
Lokacija: Vladislavci, embed Google Maps

---

## TASK 4 — OPG Kruljac Slađana

**URL:** `/korpas/opg-kruljac/`
**Template:** `templates/website/opg_kruljac.html`

PRESELI sadržaj iz trenutnog `landing_korpas.html` (OPG/sir/farma priča je već tamo, iskoristi CSS i strukturu).
Dodaj novu sekciju na dnu:

🌾 OPG BURZA SLAVONIJE I BARANJE
"OPG Kruljac Slađana osnivački je član OPG Burze Slavonije — zajednička platforma
za direktnu prodaju mlijeka, sira, povrća, voća, rakije i meda. Bez posrednika."

CTA kartica:
  "Priključi se burzi kao OPG → " → /pricing/?profile=opg
  Opis: "Registracija besplatna. Plaćaš samo kad prodaš."

Narudžba direktno (forma):
  Ime | Telefon/Email | Proizvod (dropdown: sir/mlijeko/jogurt/ostalo) | Količina | Adresa dostave
  → WhatsApp +385913912621

---

## TASK 5 — No Limit: dodaj AirCash sekciju

**File:** `templates/website/no_limit.html` (postoji, samo DODAJ sekciju — ne briši ništa!)

Dodaj PRIJE footera novu sekciju:

### 💳 AirCash — Most između gotovine i digitalnog

KONCEPT (stavi ovo kao razmišljanje na stranicu — nije još službeno partnerstvo):

AirCash radi ovako: ulaže se gotovina → dobiva se digitalni saldo → plaća se karticom.
To je JEDINI sustav koji čuva pravo na gotovinu u digitalnom svijetu.
No Limit udruga to prepoznaje i javno podržava taj model.

---

STRUKTURA SEKCIJE na no_limit.html:

BLOK 1 — "Zašto podržavamo AirCash" (manifesto ton, nije reklama)
Naslov: "Gotovina nije zastarjela. Sustav je zastario."
Tekst (manifesto, slobodan stil):
  Banke tjeraju ljude na digitalno. Gotovina nestaje tiho.
  Ali što ako netko ne želi bankovni račun? Što ako želi platiti novčanicom
  ali koristiti sve prednosti digitalne kartice?
  AirCash je odgovor: uplatite gotovinu — dobijete digitalni saldo —
  platite karticom gdje god kartice rade.
  No Limit podržava ovaj model jer spaja oba svijeta bez prisile.

BLOK 2 — "Kako funkcionira AirCash" (edukativno, 3 koraka)
  1. 💵 Uplati gotovinu — na AirCash prodajnom mjestu (kiosk, trafikа, partner)
  2. 📱 Dobiješ digitalni saldo — na AirCash kartici ili aplikaciji  
  3. 💳 Plaćaš svugdje — gdje god Mastercard/Visa rade — bez bankovnog računa

BLOK 3 — "No Limit × AirCash" (status: u razgovoru, transparentno)
  Dizajn: žuta info-kartica s ikonom ⚡
  Naslov: "Što radimo"
  Tekst: "No Limit udruga u razgovoru je s AirCash timom o formalnom partnerstvu.
  Cilj: sva No Limit mjesta postaju AirCash punjenja i prodajna mjesta.
  Uplatite gotovinu kod Korpaša, platite digitalno u Širokom Šoru.
  Lokalno. Bez banke između."
  Badge: "🟡 Status: U pregovorima — pratite novosti"

BLOK 4 — Partneri mreža (placeholder, rast će)
  Grid kartica — za sada:
  - 🔧 Korpaš Servis — Vladislavci
  - 🍷 Široki Šor — Vladislavci  
  - 🐄 OPG Kruljac Slađana — Vladislavci
  - ➕ "Pridruži svoju firmu" → forma ispod

BLOK 5 — Postani No Limit partner (forma)
  "Zalijepi naljepnicu. Prihvaćaj gotovinu. Daj kupcima slobodu."
  Forma: Naziv firme | OIB | Kontakt osoba | Telefon | Adresa
  Submit → WhatsApp +385913912621:
    "🏷️ NOVI NO LIMIT PARTNER
{firma} | {oib}
{kontakt} | {telefon}
{adresa}"
  Ekran: "Primili smo tvoj zahtjev! Kontaktirat ćemo te u 48h."

BLOK 6 — Link AirCash
  "Saznaj više o AirCash sustavu → aircash.eu" (external, target="_blank")
  Sitna napomena: "No Limit nema komercijalnu suradnju s AirCash-om.
  Podržavamo ih jer vjerujemo u isti princip: financijska sloboda je pravo, ne privilegija."

---
DIZAJN NAPOMENA: Cijela AirCash sekcija ima tamnu pozadinu (--slate iz postojećeg CSS-a)
s gold akcentima. Manifesto ton — nije corporate, nije reklama. Slobodan, direktan.

---

## TASK 6 — URL routing (sve odjednom)

U `core/urls.py` dodaj:
```python
from django.views.generic import RedirectView
# Korpaš ekosustav
path("korpas/termini/", website_views.korpas_termini, name='korpas_termini'),
path("korpas/sirokisor/", TemplateView.as_view(template_name='website/sirokisor.html'), name='sirokisor'),
path("korpas/opg-kruljac/", TemplateView.as_view(template_name='website/opg_kruljac.html'), name='opg_kruljac'),
# CRO Validator alias
path("cro-validator/", RedirectView.as_view(url='/validator/', permanent=False), name='cro_validator'),
```

Provjeri da `/korpas/termini/` view postoji u website/views.py — ako ne, dodaj:
```python
def korpas_termini(request):
    from website.models import KorpasTermin  # ili pravi path
    if request.method == 'POST':
        # spremi termin, pošalji WA, vrati success
        ...
    return render(request, 'website/korpas_termini.html', {})
```

---

## REDOSLJED

```
TASK 6 (URLs) → TASK 1 (HUB) → TASK 2 (termini+model+migracija) → TASK 3 (Široki Šor) → TASK 4 (OPG) → TASK 5 (No Limit AirCash)
```

---

## COMMITS

```
feat: Korpaš Grupa HUB landing — 4 entiteta, premium dizajn
feat: KorpasTermin model + migracija + termini booking view
feat: Široki Šor landing — restoran/kušaonica/sala/sobe
feat: OPG Kruljac landing + OPG Burza CTA (preseljeno iz landing_korpas)
feat: No Limit AirCash sekcija — partneri, QR, postani partner forma
fix: /cro-validator/ redirect → /validator/
```

## PO ZAVRŠETKU

```bash
cd /var/www/fina-connect && git log --oneline -8
systemctl status gunicorn-fina
```

Ažuriraj FENIX_STATUS.md:
- Korpaš Ekosustav → DONE (datum + svi commit hashovi)
- Dodaj URL-ove u BORG popis

