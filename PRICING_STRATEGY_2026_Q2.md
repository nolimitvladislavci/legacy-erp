# LIMIT Connect — Pricing Strategija Q2 2026

## Autor: Fenix AI (Claude Opus 4.6)
## Datum: 04.04.2026.
## Za: Nikša Višković, CEO

---

## TRENUTNO STANJE

| Metrika | Vrijednost |
|---------|-----------|
| Ukupno firmi | 96 |
| Na besplatnom POS-u | 77 (80%) |
| Plaćeni Starter | 5 (22 EUR/mj) |
| Plaćeni Enterprise | 1 (189 EUR/mj) |
| Distributor (umbrella) | 7 (359 EUR/mj) |
| **MRR (mjesečni prihod)** | **~2.852 EUR** |
| Django apps (moduli) | 83 |
| U planovima | 48 |
| Bez plana | 24 (novi moduli) |
| Promo kodovi | 0 |
| Umbrella invite kodovi | 0 |

**Problem:** 80% korisnika je na besplatnom planu. Konverzija na plaćene planove ≈ 0%.
Infrastruktura za PromoCode i UmbrellaInviteCode postoji, ali nije aktivirana.

---

## NOVA PRICING ARHITEKTURA

### Princip: "Besplatno → Otkrivanje → Pretplata"

```
BESPLATNO (POS + Arhiva)
    ↓ 30 dana trial svih modula
    ↓ AI preporuka bazirana na korištenju
    ↓ Vaučer od ambasadora (10-30% popust)
PLAĆENI PLAN
    ↓ Rast poslovanja
    ↓ AI preporuča viši plan
UMBRELLA / ENTERPRISE
```

### 5 planova (umjesto 12)

| Plan | Cijena | Za koga | Moduli | Limiti |
|------|--------|---------|--------|--------|
| **BESPLATNO** | 0 EUR | Svi | POS (1 uređaj), arhiva, partneri, inventar, tax_wizard | 1 korisnik, 50 artikala, 100 računa/mj |
| **STARTER** | 19 EUR/mj | Obrti, OPG, mali d.o.o. | + fakture, dokumenti, radni sati, e-račun, PDV-S, projekti, smart import, push | 3 korisnika, 200 artikala, neogr. računi |
| **PROFESSIONAL** | 49 EUR/mj | Srednje firme, ugostiteljstvo | + konto, plaće, gastro, webshop, dostava, rental, fiskalizacija (HR+DE), intelligence, KDS, waiter | 10 korisnika, 1.000 artikala, API pristup |
| **ENTERPRISE** | 149 EUR/mj | Veće firme, specijalizirani | + SVE (lovački, komunalno, utilities, eldercare, fitness, kindergarten, notariat, insurance, traceability) | 50 korisnika, neogr. artikli, premium podrška |
| **UMBRELLA** | Poseban model (vidi dolje) | Knjigovodstveni servisi, distributeri | Svi moduli, svi klijenti, WhiteLabel, API | Neograničeno |

### Posebne kategorije (sponzorirane)

| Kategorija | Cijena | Pokrovitelj | Moduli |
|------------|--------|-------------|--------|
| **Azil / udruga vezana uz azil** | 0 EUR trajno | NO LIMIT udruga | POS + Arhiva + partneri + udruge + memio_pet integracija |
| **Knjižnica / čitaonica** | 9 EUR/mj | — | knjiznica + library + partneri + inventar + radni sati + reports |
| **NO LIMIT Ambasador** | 0 EUR za vlastitu firmu | NO LIMIT udruga | Starter plan besplatno dok je ambasador aktivan |

---

## 3 SCENARIJA ZA UMBRELLA MODEL

### SCENARIJ A: "Fiksna + Po Klijentu" ⭐ PREPORUČENO

```
Baza:    99 EUR/mj (platforma, WhiteLabel, svi moduli za umbrella firmu)
Po klijentu: +9 EUR/mj po aktivnoj firmi (do 20 firmi)
             +7 EUR/mj po firmi (21-50)
             +5 EUR/mj po firmi (51+)
```

**Primjer — Konjik (60 komitenata):**
```
Baza:              99 EUR
Prvih 20:  20 × 9 = 180 EUR
21-50:     30 × 7 = 210 EUR
51-60:     10 × 5 =  50 EUR
─────────────────────────
UKUPNO:            539 EUR/mj  (vs. sadašnjih 359 EUR — rast 50%)
```

**Primjer — Mali distributer (8 komitenata):**
```
Baza:             99 EUR
8 × 9:           72 EUR
─────────────────────────
UKUPNO:          171 EUR/mj
```

| Pro | Contra |
|-----|--------|
| Predvidiv prihod za nas i klijenta | Umbrella plaća i za neaktivne firme |
| Motivira umbrella da donosi nove klijente | Nema revenue-share (manji upside za nas) |
| Jednostavna faktura | Konjik plaća 50% više od danas |
| Skalira linearno | — |

**Prijelaz za Konjik:** Ponuditi 6 mjeseci po staroj cijeni (359 EUR), pa postepeni rast.

---

### SCENARIJ B: "Fiksna + Revenue Share"

```
Baza:    149 EUR/mj (platforma + WhiteLabel + svi moduli)
Share:   2% od ukupnog prometa obrađenog kroz POS svih klijenata
Min:     149 EUR/mj (baza je minimum)
Max:     999 EUR/mj (cap)
```

**Primjer — Konjik (60 firmi, procjena 50.000 EUR/mj promet):**
```
Baza:              149 EUR
2% × 50.000:    1.000 EUR → cap na 999 EUR
─────────────────────────
UKUPNO:            999 EUR/mj
```

**Primjer — Mali distributer (8 firmi, 5.000 EUR/mj promet):**
```
Baza:             149 EUR
2% × 5.000:      100 EUR
─────────────────────────
UKUPNO:           249 EUR/mj
```

| Pro | Contra |
|-----|--------|
| Naša cijena raste s uspjehom klijenta | Zahtijeva POS revenue tracking (kompleksno) |
| Cap štiti klijenta od šokova | Firme bez POS-a (čisti konto) ne generiraju share |
| Motivira nas da poboljšamo POS | Konjik plaća 2.8× više — moguć otpor |
| Veliki upside | Neizvjesno, teško planirati cash flow |

---

### SCENARIJ C: "Tier + Portal Fee" ⭐ ALTERNATIVA

```
Tier 1 (do 10 firmi):     199 EUR/mj  — svi moduli, WhiteLabel
Tier 2 (11-30 firmi):     399 EUR/mj  — + API, custom reports
Tier 3 (31-75 firmi):     699 EUR/mj  — + dedicated support, SLA 99.5%
Tier 4 (76+ firmi):       999 EUR/mj  — neograničeno, SLA 99.9%, prioritetni dev
```

**Primjer — Konjik (60 firmi):** Tier 3 = 699 EUR/mj
**Primjer — Mali distributer (8 firmi):** Tier 1 = 199 EUR/mj
**Primjer — Korpaš (5 firmi):** Tier 1 = 199 EUR/mj

| Pro | Contra |
|-----|--------|
| Najprostije — 4 cijene, gotovo | "Cliff" efekt (11. firma = skok sa 199 na 399) |
| Lako komunicirati | Konjik plaća ~2× više |
| Predvidiv MRR | Nema "pay for what you use" filing |
| Umbrella zna unaprijed koliko plaća | Mali distributeri (5 firmi) plaćaju isto kao oni s 10 |

---

## MOJA PREPORUKA: SCENARIJ A + VAUČERI + AI

**Zašto A:** Najfiniji granulitet. Umbrella plaća proporcionalno broju klijenata. Nema cliff efekata. Motivira rast. Jednostavna faktura.

---

## VAUČER SHEMA

### 3 tipa vaučera:

| Kod | Popust | Trajanje | Za koga | Kako se dijeli |
|-----|--------|----------|---------|---------------|
| `NOLIMIT10` | 10% | 12 mjeseci | Bilo tko | Javno — landing, social media |
| `AMBASADOR15` | 15% | Trajno (dok je ambasador aktivan) | Klijenti ambasadora | Ambasador dijeli osobno, QR na dashboardu |
| `PARTNER30` | 30% | 6 mjeseci | Strateški partneri (računovodstveni servisi) | Direktno, kroz sales proces |

### Ambasador mehanika:
```
Ambasador dovede klijenta → klijent dobije 15% popust trajno
                           → ambasador dobije 15% komisije trajno
                           → NO LIMIT udruga pokriva ambasadorov Starter plan
```

**Win-win-win:** Klijent jeftinije, ambasador zarađuje, mi imamo sales force bez troškova.

### Vaučer za azile:
```
Kod: AZIL-NOLIMIT
Tip: full_access
Trajanje: trajno
Pokrovitelj: NO LIMIT udruga
Moduli: POS + Arhiva + partneri + udruge + memio_pet
```

---

## AI MODUL PREPORUKA — "Fenix Advisor"

### Kako radi:
1. **Tracking** — svaka firma koristi module X dana. Fenix bilježi:
   - Koji moduli se koriste
   - Koliko često
   - Koji moduli su otvoreni ali nekorišteni
   - Koji workflow-i se ponavljaju (npr. ručno fakturiranje → preporuči e-Račun)

2. **Trigger** — nakon 14 dana probnog perioda:
   - "Koristite POS 47 puta/tjedan. Za 19 EUR/mj dobijate i fakture, e-račun i konto."
   - "Imate 200+ artikala. Professional plan vam daje neograničeno + webshop."
   - "Vaši zaposlenici rade 160h/mj. Starter plan uključuje evidenciju radnog vremena."

3. **Nudge** — notifikacija u app-u + email jednom tjedno:
   - "3 dana do kraja probnog perioda. Vaš idealni plan: STARTER (19 EUR/mj)"
   - Vaučer ponuda: "Upišite NOLIMIT10 za 10% popust"

### U bazi već postoji:
- `BorgInsight` model — AI zapažanja po firmi
- `BorgSignal` model — signali o ponašanju
- `intelligence` app — analytics engine
- `registration/borg_advisor.py` — AI plan preporuka

---

## KNJIŽNICA / ČITAONICA — POSEBAN TRETMAN

**Zašto odvojeno:** Knjižnice su javne ustanove, financirane iz proračuna općine, ali često nemaju vlastiti IT. Miješanje s općinskim ERP-om kreira GDPR probleme (korisnici knjižnice ≠ građani općine).

### Plan: "Knjižnica" — 9 EUR/mj
```
Moduli: knjiznica, library, partneri (članovi), inventar (knjige),
        reports, worktime, documents
Limiti: 5 korisnika, neogr. knjiga, neogr. članova
Posebno: QR code za člansku iskaznicu, self-checkout integracija
```

### Zašto 9 EUR a ne besplatno:
- Javne ustanove imaju budžet za IT — 9 EUR je simbolično
- Filtrira neozbiljne prijave
- Pokriva server cost za tu firmu
- Udruga NO LIMIT može sponzorirati i ovo ako treba

---

## AMBASADOR MODEL — "Zelena grana"

### Problem: Ambasadori su osobe s invaliditetom. Trebaju jednostavan, dostojanstven posao.

### Rješenje: 3 razine ambasadora

| Razina | Naziv | Uvjet | Komisija | Beneficije |
|--------|-------|-------|----------|-----------|
| 1 | **Ambasador** | Doveo 1+ klijenta | 15% trajno | Besplatni Starter plan, vaučeri za dijeljenje |
| 2 | **Senior Ambasador** | 5+ aktivnih klijenata | 18% trajno | Besplatni Professional plan, prioritetna podrška |
| 3 | **Partner** | 15+ klijenata ILI 1.000+ EUR/mj komisije | 20% trajno | Besplatni Enterprise plan, vlastiti WhiteLabel subdomena |

### Onboarding flow:
```
1. Prijava → NO LIMIT verificira invaliditet (rješenje HZMO)
2. Aktivacija → email s uputama + QR kod za dijeljenje
3. Dashboard → /moji-klijenti/ (već postoji)
4. Mjesečna isplata komisije do 15. u mjesecu
5. AI prati performanse → nudge za napredovanje u razinu
```

### Financijski model:
```
Ambasador dovede 10 Starter klijenata:
  10 × 19 EUR = 190 EUR/mj prihod
  10 × 19 × 15% = 28.50 EUR/mj komisija ambasadoru
  NO LIMIT pokriva ambasadorov Starter: 19 EUR/mj
  ────────────────────────────────────
  Neto za LIMIT Connect: 190 - 28.50 - 19 = 142.50 EUR/mj
  Ambasador zarađuje: 28.50 EUR/mj (+ besplatan plan)
```

Za 10 ambasadora s po 10 klijenata:
- **Prihod:** 1.900 EUR/mj
- **Komisije:** 285 EUR/mj
- **NO LIMIT pokroviteljstvo:** 190 EUR/mj
- **Neto:** 1.425 EUR/mj (+50% MRR samo od ambasadora)

---

## PROJEKCIJA MRR — 6 MJESECI

### Pretpostavke:
- 10 ambasadora aktivno, svaki 5 klijenata u 6 mj
- Konjik prelazi na Scenarij A
- 20% besplatnih firmi konvertira na Starter nakon AI nudge-a
- 3 nova umbrella distributera

| Mjesec | Bespl. | Starter | Prof. | Enterpr. | Umbrella | MRR |
|--------|--------|---------|-------|----------|----------|-----|
| Apr 26 | 77 | 5 | 0 | 1 | 7 | 2.852 EUR |
| Maj | 70 | 15 | 2 | 1 | 7 | 3.291 EUR |
| Jun | 60 | 25 | 5 | 2 | 8 | 4.322 EUR |
| Jul | 55 | 35 | 8 | 2 | 8 | 5.429 EUR |
| Avg | 50 | 45 | 12 | 3 | 9 | 6.838 EUR |
| Sep | 45 | 55 | 18 | 4 | 10 | 8.573 EUR |

**Rast: 2.852 → 8.573 EUR/mj = 3× u 6 mjeseci**

---

## SLJEDEĆI KORACI

1. **Odmah:** Seedati vaučere (NOLIMIT10, AMBASADOR15, PARTNER30, AZIL-NOLIMIT)
2. **Odmah:** Consolidirati 12 planova u 5 + specijalne kategorije
3. **Ovaj tjedan:** Aktivirati AI Advisor nudge (probni period 30 dana → preporuka)
4. **Ovaj tjedan:** Ažurirati landing pricing sekciju
5. **Sljedeći tjedan:** Onboarding 5 ambasadora (NO LIMIT udruga kontaktira HZMO)
6. **Mjesec dana:** Pregovor s Konjik o Scenariju A prijelazu

---

*Generirao: Fenix AI (Claude Opus 4.6) — 04.04.2026.*
*Za implementaciju: Nikša potvrdi scenarij → ja implementiram u kodu.*
