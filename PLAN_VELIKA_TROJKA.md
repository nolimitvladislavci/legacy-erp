# PLAN: VELIKA TROJKA — Tri web portala
# Datum: 03.04.2026. | Vođa: Sonnet | Rok: 15.04.2026.
# Domene: limit-connect.com + memio.world + no-limit.world

---

## FILOZOFIJA — TESLA 3

Svaki portal ima JEDNU misiju, JEDNU osobu, JEDNU emociju:

  LIMIT CONNECT  → Marija → "Konačno imam kontrolu nad svojom firmom"
  MEMIO          → Baka   → "Moja unučad će znati tko sam bila"
  NO LIMIT       → Ivan   → "Gotovina je moje pravo, ne privilej"

Sve tri stranice su standalone HTML + Django template.
Nema shared CSS klasa između portala — svaki ima vlastiti identitet.

---

## ═══════════════════════════════════════════════════════
## 1. LIMIT-CONNECT.COM — B2B SaaS Landing
## Stanje: POSTOJI ali tanko (redirect na /hr/ za logiranog)
## Cilj: Konverzija posjetitelja u registriranog korisnika
## ═══════════════════════════════════════════════════════

### Što postoji:
- Portal radi, 96 firmi, 345 korisnika
- /pricing/ stranica postoji
- /no-limit/ stranica postoji (1213 linija, kvalitetna)
- Nema PRAVE landing page za hladne posjetitelje

### Što treba:
- templates/website/landing.html — nova stranica na /
  (umjesto redirecta na /hr/ za nelogiranog)
- Struktura:
  HERO: "ERP za male firme. Bez iznajmljivanja računovođe."
  STATS: 96 firmi · 58 modula · HR+DE fiskalizacija · 29 EUR/mj
  PROOF: Testimonijali (Kruljac Ivica, Šeki, Ilija Šošić)
  MODULI: 6 najvećih (POS, Računi, Radni sati, Arhiva, Udruge, Notariat)
  PRICING: 3 paketa (Starter 9 EUR / Pro 29 EUR / Enterprise)
  CTA: "Besplatna probna verzija — 14 dana"
  FAQ: 5 pitanja (fiskalizacija, sigurnost, migracija iz Synesis, DE podrška)
  FOOTER: Kontakt, social, GDPR, impressum

### Ton: Konkretan, bez BS. "Radi. Odmah. Jeftino."
### Font: Space Grotesk (već na no_limit.html)
### Boje: Tamno (#1a1a2e) + Gold (#c9a84c) + Bijelo

---

## ═══════════════════════════════════════════════════════
## 2. MEMIO.WORLD — B2C/B2Inst Heritage Platform
## Stanje: DOMENA LIVE (302 redirect na /no-limit/)
## Cilj: Emocija + Upis na waiting list
## ═══════════════════════════════════════════════════════

### Što postoji:
- Domena live, SSL aktivan
- Nginx redirect na limit-connect.com/no-limit/
- Platform Covenant SHA-256 definiran
- AION_Pismo_Namjere_2026.pdf generiran

### Što treba:
- /var/www/memio/ → novi Django projekt ILI statična stranica
- Za sada: statična HTML stranica na Nginx (brže, bez Django)
  Lokacija: /var/www/memio/index.html
  Nginx servira direktno (ne proxy na Gunicorn)

### Struktura memio.world:
  HERO:
    Naslov: "Neka te pamte kakav jesi bio."
    Podnaslov: "Digitalni sef za obiteljska sjećanja — zaštićen, garantiran 10 godina."
    CTA: "Prijavi se na waiting list" (email forma)

  PROBLEM (emotivni blok):
    3 slike/ikone:
    "Fotografija bez imena" → zaborav generacija
    "Google photos se gasi" → digitalni kolonijalizam
    "Baka nema koga pitati" → institucionalni jaz

  RJEŠENJE — 4 features:
    TimeCapsule: "Snimi poruku danas. Unuk primi za 18. rođendan."
    Alias identitet: "Dijete = Štrumf. Bez emaila, bez broja."
    Zimski san: "Zamrzni, ne briši. Vrati se kad hoćeš."
    Platform Covenant: SHA-256 potpisana obveza — 10g arhive

  TRŽIŠTE (socijalni dokaz):
    "700.000+ Hrvata u dijaspori."
    "Svaki želi djeci sačuvati jezik i korijen."
    "9,99 EUR/mj — jedna kava u Stuttgartu."

  PARTNERI:
    NO LIMIT udruga | Konjik d.o.o. | Muzej Slavonije (uskoro)

  WAITING LIST FORMA:
    Email + Ime + "Iz koje zemlje?" (HR/DE/AT/CH/Ostalo)
    Submit → sprema u bazu (novi model) + WhatsApp Ivan

  FOOTER:
    Platform Covenant tekst (skraćen)
    SHA-256 hash (kad bude generiran)
    © 2026 Konjik d.o.o. | NO LIMIT udruga

### Ton: Poetski, topao, obiteljski. "Tvoja priča zaslužuje vječnost."
### Font: Cormorant Garamond (serif, dostojanstveno) + Space Grotesk
### Boje: Kremasta (#faf8f4) + Tamna tinta (#1a1209) + Gold (#c9a84c)
### Nema dark mode — dokument tema uvijek

---

## ═══════════════════════════════════════════════════════
## 3. NO-LIMIT.WORLD — Udruga landing + Član prijave
## Stanje: DOMENA REGISTRIRANA, DNS čeka
## Cilj: Misija udruge + Prijave članova + EU projekt
## ═══════════════════════════════════════════════════════

### Što postoji:
- no_limit.html (1213 linija) na /no-limit/ unutar limit-connect.com
- Kvalitetna stranica s manifestom, osnivačima, AirCash sekcijom
- Partner prijava forma (/no-limit/partner/)

### Što treba:
- Premjestiti/kopirati na no-limit.world kao standalone
- Dodati: sekcija MEMIO projekt (Creative Europe prijava)
- Dodati: Marija Čačić kao voditeljica projekta
- Dodati: Membership forma (učlani se u udrugu)
- Dodati: EU projekti sekcija (Creative Europe, Erasmus+)

### DNS zadatak:
  A zapis: @ → 37.27.248.86
  A zapis: www → 37.27.248.86
  TTL: 60 sekundi

### Nginx: novi blok /etc/nginx/sites-available/no-limit-world
### Ton: Manifesto. Borben. "Gotovina je sloboda."
### Font: Bebas Neue + Space Grotesk (već u no_limit.html)
### Boje: Paper (#f4f1eb) + Slate (#1a1a2e) + Gold

---

## ═══════════════════════════════════════════════════════
## REDOSLJED IMPLEMENTACIJE
## ═══════════════════════════════════════════════════════

Dan 1 (danas, 03.04.):
  [x] memio.world — DNS + SSL + Nginx DONE
  [ ] memio.world — statična stranica (Gemini, ~2h)
  [ ] no-limit.world — DNS setup (Ivan)

Dan 2 (04.04. — Uskrs, Hrvoje vikend):
  [ ] no-limit.world — SSL + Nginx + kopija no_limit.html
  [ ] no-limit.world — dopune (Marija, EU projekti, membership)

Dan 3 (05.04.):
  [ ] limit-connect.com — nova landing page (CC Code)
  [ ] Waiting list model za MEMIO (CC Code)

Dan 4-7 (06-09.04.):
  [ ] SEO meta tagovi za sve tri stranice
  [ ] Google Analytics / Plausible (privacy-first)
  [ ] OG slike za social share

---

## GEMINI TASK ODMAH: memio.world statična stranica

Kreirati: /var/www/memio/index.html
Nginx servis: direktno iz /var/www/memio/
Bez Django, bez Gunicorn — čisti HTML+CSS+JS

Sadržaj prema planu gore (poetski ton, serif font, kremasta boja,
TimeCapsule + Alias + Zimski san + Platform Covenant + waiting list forma).
