# ŠEKI NOĆNI KIOSK — ROBOT PRODAVAČ 2.0
# Kreirao: Opus — 2026-03-21
# Kontekst: Europa gradi 2 ulice od Šekija. Ili inoviraš ili se gubiš u konkurenciji.

---

## SITUACIJA — ISTINA IZ PODATAKA

### Tržište (knjige, Synesis, ledger)

| Metrika | Uvijek Friško (Šeki) | Nova Europa (Leonard) | Europa (Sait) |
|---------|---------------------|----------------------|---------------|
| Mj. prihod | ~130.000 EUR | ~95.000 EUR (procjena iz obveza) | nemamo podatak, ali 2015 = 2× Friško |
| Prodavaonice | 3 (Čepin, Vladislavci, Ivanovac) | 1 + nova | 1 + gradi novu |
| Kupci škole | OŠ Dobrše Cesarića, OŠ V.Nazor | OŠ Dr. Franje Tuđmana | — |
| Institucije | Crveni križ, Tajfun, Siv&Mis | Hotel Patria, DVD Petlovac | — |
| Dnevni utržak kase | 3.000-5.000 EUR/dan | nema podatka | nema podatka |
| Knjigovodstvo | — | Konjik 800 EUR/mj | Konjik 900 EUR/mj |
| Dobavljači | — | Metro, Konzum, Lidl, Dukat, Bijelić | — |

### Prijetnja
**Europa gradi novi prostor 2 ulice od Šekija.** Europa je 2015 radila duplo od Friška. Ako se to ponovi — Šeki gubi tržište.

### Prilika
**Šeki završava 2. fazu (pločice).** Sada ili nikad — dok je u građevinskom modu, može ugraditi infrastrukturu za nešto što nitko u Hrvatskoj nema.

---

## KONCEPT: NOĆNI KIOSK — NULA OTPISA, 24/7 PRODAJA

### Problem koji rješavamo
Svaka pekarna u HR baca 10-20% dnevne proizvodnje. U 22:00 se skidaju artikli s polica → otpis → smeće.

### Rješenje
**Hlađeni locker-automat ispred pekarne** (2-4 m²):
- U 22:00 radnik prebaci robu s polica u locker
- Automat prodaje od 22:00 do 06:00 po sniženim cijenama (30-50% popust)
- Kupac skenira QR ili koristi karticu → otvara se pretinac → uzima robu
- U 06:00 pekarna se otvara, automat se prazni, počinje novi dan

### Zašto ovo mijenja igru
1. **0% otpisa** — sve se proda ili donira, ništa ne ide u smeće
2. **24/7 prihod** — pekarna zarađuje i dok spava
3. **ESG priča** — manje bacanja hrane = EU fondovi, medijska priča, etika
4. **Konkurentska prednost** — Europa to nema. Nitko u HR to nema.
5. **Proširiv model** — od 1 lokacije do 50 u Slavoniji

---

## JAPANSKI DOKAZ — YOKOHAMA MODEL (radi od 2024)

**Enmichi Pan pekarna, Yokohama:**
- Zatvara u 19:00, puni lockere neprodanim kruhom
- Popust 20-30%
- Rezultat: **RED ISPRED LOCKERA prije nego ih napune**
- Sav kruh se proda do jutra
- **1,5 tona spašene hrane godišnje PO LOKACIJI**
- Proširili na 7+ lokacija, gradovi kopiraju model

**Ovo nije teorija. Ovo radi.**

---

## HARDWARE — ŠTO KUPITI

### Preporuka za pilot: Hlađeni locker automat

| Opcija | Proizvođač | Cijena | Footprint | Kapacitet | Napomena |
|--------|-----------|--------|-----------|-----------|---------|
| **A (preporuka)** | Penguin Lockers (EU) | na upit (~4-6K EUR) | 1-3 m² modularno | 20-40 pretinaca | EU kvaliteta, Peltier hlađenje, tiho, bez kompresora |
| **B (budget)** | Weimi (Kina→EU) | 2.000-4.500 EUR | 1-2 m² | 54 pretinca | Isprobano u 80+ zemalja, cloud monitoring |
| **C (high-tech)** | Neuroshop (Poljska) | na upit | ~1 m² | AI smart fridge | Grab-and-go, kamere, auto-naplata |
| **D (NL kvaliteta)** | Nextlox (Nizozemska) | na upit | modularno | RFID/QR pristup | Vandal-resistant, robusno |
| **E (najjeftinije)** | Alibaba/Vendlife | 500-3.000 EUR | 1-2 m² | varijabilno | Rizičnije ali za test OK |

### Tehnički zahtjevi
- **Temperatura:** +2 do +8°C (kruh, peciva, sendviči)
- **Plaćanje:** Kartica + QR kod (naš LIMIT Connect POS) + opcija gotovina
- **Monitoring:** Cloud dashboard — vidimo u realnom vremenu što se prodaje
- **Struja:** 220V standardna utičnica
- **Lokacija:** Ispred pekarne ili na frekventnom mjestu (škola, stanica)

---

## SOFTVER — VEĆ 80% GOTOV (LIMIT Connect)

### Što imamo (LIVE u produkciji):
| Komponenta | Status | Detalj |
|-----------|--------|--------|
| Roba od jučer | ✅ LIVE | `pos_dailydiscount` — automatski popust, public prikaz |
| QR instant open | ✅ LIVE | `/pos/qr/{token}/` — kupac skenira, otvori POS |
| Pickup flow | ✅ LIVE | Naruči → plati → pokupi (pickup_views.py, 227 linija) |
| Webshop public | ✅ LIVE | `/pos/webshop/{slug}/` — javni katalog |
| Fiskalizacija | ✅ LIVE | 3 sloja, 5s timeout, Celery retry, zakonski OK |
| Expiry tracking | ✅ LIVE | `pos_expirybatch` — HACCP batch praćenje |
| Otpis/Kalo | ✅ LIVE | `inventory StockMovement type=writeoff` |

### Što nedostaje (3 taska):
| Task | Opis | Effort |
|------|------|--------|
| Kiosk UI | Touchscreen template za locker ekran | 1 dan |
| Stripe prepayment | Plati online → otvori pretinac | 1 dan |
| Locker API | Signal na automat: "otvori pretinac X" | 1 dan + hardware spec |

---

## NOĆNI KIOSK PROCES — KORAK PO KORAK

```
22:00  Pekarna zatvara
       ↓
       Radnik prebacuje artikle s polica u locker automat
       ↓
       LIMIT Connect automatski:
       - Snižava cijenu 30-50% (pos_dailydiscount)
       - Aktivira noćni meni na webshop_public
       - Šalje push obavijest stalnim kupcima
       ↓
22:00-06:00  AUTOMAT PRODAJE
       Kupac prilazi → skenira QR → vidi meni s cijenama
       → bira artikle → plaća karticom/mobitelom
       → pretinac se otvara → uzima robu
       ↓
       Svaka transakcija:
       - Fiskalizirani račun (automatski)
       - Stock movement (-1 iz zaliha)
       - Real-time dashboard (Šeki vidi na mobitelu)
       ↓
06:00  Pekarna otvara
       Radnik prazni neprodan ostatak (ako ga ima)
       LIMIT Connect generira izvještaj:
       - Prodano noću: X EUR
       - Spašeno od otpisa: X kg
       - Preostalo: X artikala
```

---

## FINANCIJSKI MODEL — ŠEKIJEV SLUČAJ

### Troškovi
| Stavka | Jednokratno | Mjesečno |
|--------|------------|----------|
| Locker automat (Penguin/Weimi) | 4.000 EUR | — |
| Instalacija + struja | 500 EUR | 30 EUR |
| LIMIT Connect POS | — | 35 EUR |
| Stripe provizija | — | ~1.5% prometa |
| **UKUPNO** | **4.500 EUR** | **~70 EUR** |

### Prihodi (konzervativna procjena)
| Metrika | Konzervativno | Realno | Optimistično |
|---------|--------------|--------|-------------|
| Artikala u lockeru | 30 | 50 | 80 |
| Prosj. cijena (s popustom) | 1.50 EUR | 2.00 EUR | 2.50 EUR |
| Prodaja/noć (%) | 50% | 70% | 90% |
| **Prihod/noć** | **22 EUR** | **70 EUR** | **180 EUR** |
| **Prihod/mjesec** | **660 EUR** | **2.100 EUR** | **5.400 EUR** |

### Spašeno od otpisa
- 30-80 artikala/dan × 30 dana = 900-2.400 artikala/mj
- Po prosječnoj nabavnoj 1 EUR = **900-2.400 EUR/mj spašeno**

### ROI
- **Konzervativno:** 4.500 / 660 = **7 mjeseci**
- **Realno:** 4.500 / 2.100 = **2 mjeseca**
- **Optimistično:** 4.500 / 5.400 = **25 dana**

Plus ušteda od nultog otpisa: **ROI realno pod 2 mjeseca.**

---

## ŠEKIJEVA KONKURENTSKA PREDNOST vs EUROPA

| Aspekt | Europa (sadašnje stanje) | Šeki + Noćni Kiosk |
|--------|------------------------|-------------------|
| Radno vrijeme | 06:00-22:00 | **00:00-24:00** |
| Otpis | 10-20% (standardno) | **~0%** |
| Noćni prihod | 0 EUR | **660-5.400 EUR/mj** |
| Trošak rada noću | N/A | **0 EUR (automat)** |
| PR/medijska priča | nema | **"Prva pekarna u HR s noćnim robotom"** |
| ESG/EU fondovi | ne | **da — food waste reduction** |
| Google vidljivost | ne | **/robot-pekara/ SEO** |
| Kupac iskustvo | klasično | **24/7, QR, mobilno plaćanje** |

**Europa može kopirati proizvod. Ne može kopirati inovaciju.**

---

## PLAN IZVRŠENJA

### FAZA 1 — Odmah (ovaj tjedan)
- [x] Analiza tržišta Europa vs Uvijek Friško (DONE — ova sesija)
- [x] Istraživanje locker automata (DONE — ova sesija)
- [ ] Poslati Šekiju poruku s konceptom + Yokohama primjerom
- [ ] Kontaktirati Penguin Lockers i Weimi za ponude

### FAZA 2 — Tjedan 1-2
- [ ] Kiosk UI template (touchscreen)
- [ ] "Roba od jučer" → "Noćni kiosk" automatski transfer flow
- [ ] Stripe prepayment integracija
- [ ] Ponude za hardware — odabir dobavljača

### FAZA 3 — Tjedan 3-4
- [ ] Hardware narudžba
- [ ] Locker API integracija (ovisno o odabranom hardwareu)
- [ ] Test na jednoj lokaciji (Čepin)

### FAZA 4 — Mjesec 2
- [ ] Pilot live — Čepin
- [ ] Praćenje: prodaja/noć, otpis %, zadovoljstvo kupaca
- [ ] Case study za medije

### FAZA 5 — Mjesec 3+
- [ ] Vladislavci + Ivanovac
- [ ] PR: "Prva pekarna u Hrvatskoj bez otpisa hrane"
- [ ] EU fond aplikacija (food waste reduction)
- [ ] Marko Pinjuh — komercijalizacija za ostale pekarne

---

## MEDIJSKA PRIČA (BESPLATNI PR)

Naslov: **"Čepinski pekar uveo robota koji prodaje kruh noću — otpad od hrane pao na nulu"**

Zašto će mediji to pokupiti:
1. Food waste je EU tema #1 — regulativa ide 2027
2. Robot + pekarna = vizualno privlačno za TV
3. Lokalna priča iz Slavonije (ne Zagreb opet)
4. ESG angle — djeca u školi uče o održivosti, a pekar u Čepinu to živi
5. Tehnološka priča — QR, automatska fiskalizacija, cloud monitoring

Kontakti: Glas Slavonije, HRT regionalne vijesti, Index.hr tech rubrika, Osječki podcast

---

## VEZA S POSTOJEĆIM LIMIT CONNECT PLANOM

Ovaj Noćni Kiosk je **modul unutar Robot Prodavač** koncepta:

```
ROBOT PRODAVAČ (LIMIT Connect)
├── Dnevni mod: QR narudžba bez blagajnika (LIVE)
├── Noćni mod: Locker automat + roba od jučer (NOVO)
├── Kiosk UI: Touchscreen za obje namjene (u izradi)
├── Fiskalizacija: Automatska 24/7 (LIVE)
└── Dashboard: Real-time prodaja/otpis/stock (LIVE)
```

Nije novi proizvod. **Proširenje postojećeg.**

---

Zadnje ažuriranje: 2026-03-21 — Opus
