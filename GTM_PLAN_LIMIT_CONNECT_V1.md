# GTM PLAN — LIMIT Connect — Broj 1 u HR i EU
# Verzija: 1.0 — Sonnet + Gemini synthesis
# Datum: 2026-03-21
# Odobrio: Ivan Brtan

---

## VIZIJA (nepromijenjena)
"Jedini ERP u Hrvatskoj koji radi za pekarnicu, OPG, udrugu i DE GmbH — u istom sustavu.
Bez papira. Otvoreni pristup realnim podacima za državne aparate.
Zakonske promjene integriramo automatski — korisnik ne radi ništa."

---

## REALNA POLAZNA TOČKA (živih podataka — 21.03.2026.)

| Metrika | Vrijednost |
|---|---|
| Kompanije u sustavu | 82 |
| Aktivne pretplate | 12 |
| Ukupno partnera u bazi | 33.270 |
| Fakture Konjik (Marija) | 2.555 / 930k EUR |
| POS terminali Seki | 5 (ali 4 sesije ukupno — problem!) |
| Korpaš fakture | 357 / 185k EUR |
| Pricing planovi | 8 (0 EUR → 359 EUR/mo) |
| Migracija | 369 (sve aplicirano) |

**Kritična rupa:** 33.270 partnera u bazi, 0 outreach kampanja ikad.
**Kritična rupa 2:** Seki ima 5 terminala, koristi ih minimalno.

---

## TRI PARALELNE OSI

### Os 1 — PRODUCT (što gradimo)
### Os 2 — GTM (kako prodajemo)
### Os 3 — OPERATIONS (kako servisiramo)

Sve tri osi moraju ići paralelno. Do sada je bila samo Os 1.

---

## OS 1 — PRODUCT ROADMAP

### P1 — Zero-Touch Onboarding (Geminijev prijedlog — PRIHVAĆEN, proširujem)

**Što postoji:** Sales Wizard (5 koraka), registration/step1-4, OIB validacija, Country Registry
**Što nedostaje:** OIB → auto-lookup, Empty States, onboarding progress tracker

#### P1.1 OIB/Steuernummer Auto-Lookup
```
Korisnik upiše OIB → AJAX → /registration/api/oib-lookup/
→ Sudski registar API (ili FinReg scrape)
→ Vraća: naziv firme, adresa, OIB, pravni oblik, NKD
→ Form se autopopuni
→ Korisnik vidi: sustav je pametan. Forma od 15 polja = forma od 2 polja.
```
**Implementacija:** CC Code — nova view `api_oib_lookup`, AJAX u step1.html
**Rok:** Tjedan 1

#### P1.2 Empty States — "Prijateljski prazni ekrani"
Svaki modul pri prvom loginu ne smije prikazati praznu tablicu.
Mora prikazati:
- Što ovaj modul radi (1 rečenica)
- Veliki gumb s jasnom akcijom ("Izdajte prvi e-Račun")
- Procijenjeno vrijeme: "5 minuta"

**Prioritet moduli:** Dashboard, Invoicing, POS, Arhiva, Konto
**Implementacija:** CC Code — empty_state.html partial + context flag `is_empty`
**Rok:** Tjedan 2

#### P1.3 Onboarding Checklist (vidljiv, gamified)
Nakon registracije: progress bar s 5 koraka.
```
☐ Dodajte logo i podatke firme (2 min)
☐ Kreirajte prvog partnera (1 min)
☐ Izdajte probni račun (3 min)
☐ Povežite blagajnu (5 min) [samo za POS plan]
☐ Pošaljite prvi eRačun (2 min) [samo Professional+]
```
Svaki korak označen → zelena kvačica → progress 0→100%.
**Implementacija:** `companies/onboarding.py` model već postoji — proširiti
**Rok:** Tjedan 2

---

### P2 — Visual Compliance (Geminijev prijedlog — PRIHVAĆEN, ovo je killer feature)

#### P2.1 Zeleni štit — "Compliance Status" widget
Trajno vidljiv u navigaciji: 🟢 Usklađeno s propisima 2026
Klikabilno → otvara listu: što je provjerjeno, kada, koji zakon.

Kad se zakon promijeni i CC/Gemini implementiraju → automatski:
- Toast notifikacija svim korisnicima: "Porezna uprava je ažurirala XML shemu. LIMIT Connect je to integrirao. Vi ne radite ništa."
- Zeleni štit mijenja datum na novi

**Implementacija:** `ComplianceWatchItem` model (već u planu Faze 2 AI) + template tag `{% compliance_shield %}`
**Rok:** Tjedan 3

#### P2.2 Changelog koji korisnik vidi
`/changelog/` stranica — svaki deploy koji mijenja zakon = vidljiv unos.
Format: "15.03.2026 — FINA XML shema v3.1 automatski integrirana."
Ne tehnički changelog. Poslovni changelog. Korisnik ga dijeli računovođi.

---

### P3 — Pricing Kalkulator (Geminijev prijedlog — PRIHVAĆEN)

**Što postoji:** 8 pricing planova u bazi (0→359 EUR/mo)
**Što nedostaje:** Javni interaktivni kalkulator na /pricing/

#### Logika kalkulatora:
```
Slider 1: Broj B2B faktura/mjesec (0→500)
Slider 2: Broj zaposlenika (1→50)
Toggle: POS blagajna? Da/Ne
Toggle: Izvoz u DE? Da/Ne
Toggle: Udruga/NPF? Da/Ne

→ Output: "Preporučeni plan: Professional (69 EUR/mo)"
→ Usporedba: "Ručno računovodstvo za isti obujam = 350 EUR/mo"
→ "Uštedite 281 EUR/mo. Povrat investicije: 1. faktura."
```
**Implementacija:** CC Code — `/pricing/` page + vanilla JS kalkulator
**Rok:** Tjedan 1 (visoka vidljivost, brz win)

---

### P4 — HAPIH/JRDŽ Pilot — Proof of Concept za državni sektor

**Što postoji:** InstitutionalAccessToken, 4 read-only endpointa (HAPIH, JRDŽ, Sanitarna, VetIS)
**Što nedostaje:** Prva STVARNA transmisija podataka OPG Kruljac → HAPIH

#### Koraci:
1. Kruljac upiše novo grlo u sustav
2. Sustav automatski šalje HAPIH notification (ako API to podržava)
3. Ako ne — generira XML obrazac koji Kruljac može copy-paste poslati
4. Snimiti ekran → Case Study PDF

**Ovo je najvažniji single dokaz koncepta za državni sektor.**
Kad taj XML prođe → imate referencu vrijedniju od 100 sales poziva.
**Rok:** Tjedan 4 — Gemini task

---

## OS 2 — GTM (Prodaja i akvizicija)

### G1 — Case Studies — 3 živih primjera

Ne generički. Pravi brojevi (s dozvolom ili anonimizirani).

**Case Study 1: Konjik d.o.o. — Računovodstvo**
"Knjižimo 2.555 faktura godišnje. Arhiva preuzima Synesis dokumente automatski.
13.560 partnera u bazi. eRačun ide direktno u FINA CIS."
Ciljna publika: Računovodstveni uredi, odvjetnički uredi, konzultanti

**Case Study 2: Uvijek Friško — Maloprodaja/Pekarna**
"5 POS terminala na 3 lokacije. Fiskalizacija u realu.
Loyalty program. Gastro KDS. Offline mode kad padne internet."
Ciljna publika: Ugostiteljstvo, maloprodaja, pekare, restorani

**Case Study 3: OPG Kruljac — Poljoprivreda**
"Karencija za antibiotike automatski blokira POS prodaju.
Livestock evidencija. HAPIH/JRDŽ API integracija."
Ciljna publika: OPG-ovi, veterinari, zadružni sustavi

**Implementacija:** CC Code — `/case-studies/` stranica
**Rok:** Tjedan 2

---

### G2 — PLG (Product-Led Growth) — Trojanski Konj

Geminijev prijedlog je točan. Proširujem:

#### G2.1 Veterinarski portal kao distribucijski kanal
- Veterinar dobiva besplatan pristup (InstitutionalAccessToken)
- Koristi FenixCamera za skeniranje ušnih markica na OPG-u
- Farmer vidi podatke → pita "što je ovo?" → registrira se
- 1 veterinar = 20 OPG-ova = 20 potencijalnih klijenata

#### G2.2 Računovođa kao distribucijski kanal
- Marija (Konjik) je već na Distributor planu
- Svaki njezin klijent koji se registrira → Marija dobiva komisiju
- Agent dashboard već postoji (/hr/register/agent/)
- **Aktivirati Mariju kao agenta je trenutno najveći neiskorištenosti resurs**

#### G2.3 Referral program — automatizirati
Referral QR kodovi već postoje (?ref=REF-XXXXX).
Nedostaje: automatska aktivacija provizije, tracking dashboard.
**Implementacija:** Proširiti SalesLead model — CC Code tjedan 3

---

### G3 — Spavači u bazi — 70 kompanija

82 kompanije u sustavu, 12 aktivnih pretplata.
**70 kompanija ima podatke ali ne plaća ništa.**

Segmentacija:
- **Tier A (odmah kontaktirati):** Agrovladislavci (723 partnera), Fast (5k partnera), Glazbeni centar Mai (387 faktura), M-Team (579 partnera), Nova Europa (606 partnera)
- **Tier B (nurture sekvenca):** 20-50 partnera, 0 faktura → oni su u sustavu ali ne koriste ključne module
- **Tier C (cleanup):** Firme bez aktivnosti — pitati žele li nastaviti ili obrisati

**Automatizirana sekvenca (Gemini + WhatsApp):**
Tjedan 1: "Primijetili smo da imate 723 partnera u sustavu ali niste koristili fakturiranje."
Tjedan 2: "Evo kako Konjik d.o.o. s 13.560 partnera radi [link case study]"
Tjedan 3: "Probni period Professional plana — 30 dana besplatno"

---

### G4 — Pricing stranica — psihološki dizajn

**Trenutni plan (u bazi):**
- POS Besplatno: 0 EUR
- Micro: 10 EUR
- Arhiva + AI: 47 EUR
- POS + Arhiva: 35 EUR
- Starter: 22 EUR
- Professional: 69 EUR ← ANCHOR PLAN
- Enterprise: 189 EUR
- Distributor: 359 EUR

**Preporuka:** Professional (69 EUR) mora biti vizualno istaknuti "most popular."
Kalkulator dokazuje ROI matematički — ne emocijama.
"69 EUR/mo. Jedan sat računovođinog vremena. Vi dobivate 20 sati uštede."

---

## OS 3 — OPERATIONS (Servisiranje klijenata)

### O1 — Šeki problem: RIJEŠITI OVAJ TJEDAN

Šeki ima 5 terminala. 4 sesije ukupno. Ovo nije prihvatljivo.

**Akcija odmah (Sonnet → Ivan → Šeki):**
Pitanje za Ivana: Zna li Šeki login za svaki terminal? Ima li internet problema na Vladislavicima?

**Trajan fix (CC Code Faza 1):**
morning_report za Šekija: svaki dan u 07:00
"Jučerašnji promet: Čepin 0 EUR, Vladislavci 0 EUR, Ivanovac 0 EUR.
Sva tri terminala imaju 0 transakcija. Je li sve u redu?"

Ako terminal ima 0 bonova 3 dana zaredom → automatski WhatsApp alarm Ivanu.

### O2 — Marija račun s 0 — status

Baza je čista: 0 faktura s iznosom 0 u Konjik d.o.o.
Problem je u UI prikazu arhivskog dokumenta, ne u podacima.
Najvjerojatnije: Synesis uvezeni dokument koji nema `total` rendered u template.
**Akcija:** Ivan odgovara Mariji: "Baza je ispravna, gledam prikaz, popravljam danas."
CC Code: provjeri invoice_hr.html i arhivski detail view za edge case total=0 display.

### O3 — Onboarding SLA

Svaki novi klijent mora u roku 24h dobiti:
1. WhatsApp dobrodošlica s prvim korakom
2. AI cockpit aktiviran (nakon Faze 1)
3. Onboarding checklist poslan emailom

**Ovo eliminira "Ivane, pomozi" faktor.**

---

## TIMELINE — 4 TJEDNA DO TRŽIŠNE POZICIJE

### Tjedan 1 (odmah)
| Tko | Što | Output |
|---|---|---|
| CC Code | limit_connect_ai Faza 1 (AKTIVAN TASK) | App + modeli + jutarnji report |
| CC Code | /pricing/ kalkulator | Javna pricing stranica |
| CC Code | OIB auto-lookup | AJAX endpoint |
| Sonnet | Šeki problem dijagnoza | WhatsApp poruka Šekiju |
| Ivan | Odgovor Mariji | Bug report za CC |

### Tjedan 2
| Tko | Što | Output |
|---|---|---|
| CC Code | Empty States svi ključni moduli | Onboarding UX 4→7/10 |
| CC Code | /case-studies/ stranica | 3 case studija live |
| CC Code | Onboarding checklist | Progress tracker |
| Gemini | Compliance Watchdog Faza 2 | ComplianceWatchItem |

### Tjedan 3
| Tko | Što | Output |
|---|---|---|
| CC Code | Visual Compliance / Zeleni štit | Compliance widget u nav |
| CC Code | /changelog/ poslovni | Changelog live |
| Gemini | Campaign suggestions | CampaignPlanner |
| CC Code | Referral tracking dashboard | Agent aktivacija |

### Tjedan 4
| Tko | Što | Output |
|---|---|---|
| Gemini | HAPIH pilot s Kruljcem | Case Study PDF |
| CC Code | Per-klijent AI cockpit | Svi klijenti imaju cockpit |
| Sonnet | End-to-end test + demo Ivan | Review svega |
| Ivan + Sonnet | Kampanja za spavače Tier A | 5 novih aktivacija |

---

## KPI — KAKO ZNAMO DA SMO BROJ 1

| KPI | Danas | Cilj 30 dana | Cilj 90 dana |
|---|---|---|---|
| Aktivne pretplate | 12 | 20 | 50 |
| Onboarding UX score | 4/10 | 7/10 | 9/10 |
| Tržišna pozicija | 2/10 | 5/10 | 8/10 |
| Šeki dnevni bonovi | ~0/dan | 30+/dan | 50+/dan |
| Outreach kampanje poslane | 0 | 3 | 20 |
| Case Studies live | 0 | 3 | 5 |
| HAPIH pilot transmisija | 0 | 0 | 1 (dokaz koncepta) |

---

## ŠTO GEMINI PREDLAŽE A SONNET DODAJE

**Gemini:** OIB lookup, Empty States, Visual Compliance, PLG/Trojanski konj, HAPIH pilot
→ SVE PRIHVAĆENO. Geminijev GTM_V1 je validan inženjerski pristup.

**Sonnet dodaje:**
1. **Marija kao agent — odmah.** Ona ima 13.560 partnera i distributor plan. Aktivirati agent dashboard = besplatni sales force koji već postoji.
2. **Šeki je test slučaj br.1, ne showcasecase.** Dok Šeki ne kuca svaki dan, nemamo pravo govoriti o skaliranju. Fix je IT triage, ne novi feature.
3. **Changelog vidljiv korisnicima** — svaka zakonska integracija mora biti vidljiva. Trenutno se dogodi u gitu, korisnik ne zna. Ovo je direktno oružje protiv churna.
4. **70 spavača je pravi pipeline** — akvizicija izvana je skuplja od aktivacije unutra. Tier A kontaktirati ovaj tjedan.

---

## ZADNJE AZURIRANJE
2026-03-21 — Sonnet (koordinator) — GTM Plan V1, synthesis Gemini + Sonnet + živih podataka
