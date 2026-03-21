# FENIX ŠIRENJE — Samoširivi Sustav
# "Svaki dokument je sjeme. Svaki korisnik je stablo. Mreža raste sama."
# Kreirao: Opus — 21.03.2026
# Ovlast: Ivan Brtan — potpuna, svi resursi, cilj #1 u HR

---

## VIZIJA

LIMIT Connect prestaje biti softver koji se prodaje.
Postaje **mreža koja se širi sama** — kao blockchain, kao kripto layeri.

Svaka faktura koju korisnik pošalje = reklama.
Svaki bon koji kupac dobije = sjeme.
Svaka autopraonica, pekarna, OPG, veterinar = novi čvor u mreži.

**Cilj: #1 platforma za male poduzetnike u Hrvatskoj.**

---

## ARHITEKTURA — 6 LAYERA

```
┌─────────────────────────────────────────────────────┐
│  LAYER 5 — NOVE INDUSTRIJE (novi lanci)             │
│  Pekarne · Autopraonice · OPG · Veterinari · ...    │
├─────────────────────────────────────────────────────┤
│  LAYER 4 — INSTITUCIJE (validatori)                  │
│  HAPIH · JRDZ · VetIS · Sanitarna · Porezna         │
├─────────────────────────────────────────────────────┤
│  LAYER 3 — KRAJNJI KUPCI → NOVI KORISNICI            │
│  Hotel Patria vidi fakturu → registrira se           │
├─────────────────────────────────────────────────────┤
│  LAYER 2 — KOMITENTI (širitelji)                     │
│  Europa · Uvijek Friško · OPG-ovi · Autopraonice     │
├─────────────────────────────────────────────────────┤
│  LAYER 1 — DISTRIBUTERI (prvi čvorovi)               │
│  Konjik d.o.o. (66 komitenata) · budući partneri     │
├─────────────────────────────────────────────────────┤
│  LAYER 0 — LIMIT CONNECT PLATFORMA (genesis block)   │
│  Ivan Brtan · Fenix tim · AI jezgra                  │
└─────────────────────────────────────────────────────┘
```

---

## MEHANIZMI SAMOŠIRENJA

### 1. SVAKA FAKTURA = REKLAMA
- PDF footer: "Powered by LIMIT Connect · limit-connect.com/start"
- QR kod s referral kodom izdavatelja
- Konjik: 2.500 faktura/god → 2.500 reklamnih kontakata besplatno
- **Status: IMPLEMENTIRATI ODMAH**

### 2. SVAKI POS BON = MIKRO-REKLAMA
- Footer: "Powered by LIMIT Connect · limit-connect.com"
- Šeki: 100+ bonova/dan = 3.000 kontakata/mj
- **Status: IMPLEMENTIRATI ODMAH**

### 3. e-RAČUN PORTAL = LANDING PAGE
- CTA: "Želite slati e-Račune besplatno? → Registriraj se"
- Svaki primatelj e-Računa = potencijalni korisnik
- **Status: IMPLEMENTIRATI ODMAH**

### 4. OPG/BESPLATNI KORISNICI = AMBASADORI
- Personalizirani QR plakat s ref_code
- "Powered by LIMIT Connect AI" na svakom prodajnom mjestu
- Besplatni POS u zamjenu za ambasadorstvo
- **Status: KREIRATI PLAKATE**

### 5. AUTOPRAONICE = FREKVENTNI BILLBOARDI
- Letak na zidu: "Plati mobitelom · Powered by LIMIT Connect AI"
- 50 kupaca/dan × 30 dana = 1.500 skeniranja/mj po lokaciji
- Miroslav Konjik = pilot
- **Status: AUTOPRAONICA TEMPLATE + LETAK**

### 6. PEKARNE = NOĆNI KIOSK + 24/7 REKLAMA
- Locker automat s QR i LIMIT Connect brandingom
- Svaki kupac koji skenira = kontakt
- Šeki = pilot, 3 lokacije
- **Status: KIOSK UI + LOCKER API**

### 7. VETERINARI = INSTITUCIONALNI MOST
- Vet obrasci za HAPIH/JRDZ već imaju "Powered by LIMIT CONNECT"
- Svaki farmer koji vidi → potencijalni OPG korisnik
- Institucija koristi → legitimnost
- **Status: AKTIVAN — proširiti**

### 8. REFERRAL LANAC S PROVIZIJOM
- AgentReferral: 20% provizija, 12 mjeseci
- Svaki partner zarađuje na preporukama
- Motivacija: pasivni prihod za distributere
- **Status: POSTOJI — AKTIVIRATI**

---

## IMPLEMENTACIJSKI PLAN

### SPRINT 1 — "Svaki dokument = reklama" (1 dan)

| # | Zadatak | Effort | File |
|---|---------|--------|------|
| 1.1 | "Powered by" footer na PDF fakture | 30 min | invoicing/templates/invoicing/invoice_hr.html |
| 1.2 | "Powered by" footer na POS bon | 15 min | pos/ receipt templates |
| 1.3 | CTA na e-Račun public portal | 15 min | templates/eracun/public_invoice.html |
| 1.4 | "Powered by" na webshop public | 10 min | templates/webshop/public/shop.html |
| 1.5 | Referral QR na invoice PDF | 30 min | invoicing/services/pdf_service.py |

### SPRINT 2 — "Aktivacija postojeće infrastrukture" (1 dan)

| # | Zadatak | Effort | File |
|---|---------|--------|------|
| 2.1 | Aktivirati AgentReferral za Konjik | 10 min | partners/models.py |
| 2.2 | Generirati ref QR za sve OPG-ove | 30 min | management command |
| 2.3 | Referral tracking na registraciji | 30 min | registration/views.py |
| 2.4 | Agent dashboard — live statistike | 2 sata | registration/views.py |

### SPRINT 3 — "Novi vertikali" (3 dana)

| # | Zadatak | Effort | File |
|---|---------|--------|------|
| 3.1 | Autopraonica template | 1 dan | pos/views.py + template |
| 3.2 | Noćni kiosk UI | 1 dan | pos/views.py + template |
| 3.3 | ISU fiskalizacija za samoposlužne uređaje | 1 dan | invoicing/ |

### SPRINT 4 — "Premium moduli" (1 tjedan)

| # | Zadatak | Effort | File |
|---|---------|--------|------|
| 4.1 | Fleet modul (OIB tracking, mjesečni izvještaj) | 3 dana | novi modul |
| 4.2 | Stripe prepayment za kiosk/autopraonice | 1 dan | payments/ |
| 4.3 | Loyalty program aktivacija za nove vertikale | 1 dan | pos/models.py |
| 4.4 | Landing page /robot-pekara/ + /autopraonica/ | 1 dan | website/ |

### SPRINT 5 — "Scale" (ongoing)

| # | Zadatak | Effort |
|---|---------|--------|
| 5.1 | 10 autopraonica onboarding | 2 tjedna |
| 5.2 | 5 pekarna onboarding (noćni kiosk) | 2 tjedna |
| 5.3 | PR: "Prva digitalna autopraonica u Slavoniji" | 1 dan |
| 5.4 | PR: "Pekar iz Čepina uveo noćnog robota" | 1 dan |
| 5.5 | EU fond aplikacija (food waste + digitalizacija SME) | 2 tjedna |

---

## PROJEKCIJA RASTA

```
         KONTAKTI/MJ        KORISNICI         MRR (EUR)
         ──────────         ─────────         ─────────
DANAS:        100            ~10 aktivnih      1.745
MJESEC 1:   7.500            ~15               2.200
MJESEC 3:  30.000            ~50               4.500
MJESEC 6:  75.000            ~150              8.000
GODINA 1: 200.000            ~500             20.000+

Eksponencijalni rast: svaki novi korisnik generira
nove kontakte koji generiraju nove korisnike.
Lanac se ne prekida. Mreža raste sama.
```

---

## EKONOMIKA LAYERA

### Layer 0 — Platforma (mi)
- Trošak: server + development (postojeći)
- Prihod: SaaS pretplate + payment processing margin

### Layer 1 — Distributeri (Konjik i budući)
- Trošak za njih: 0 (dio pretplate komitenata)
- Prihod za njih: 20% provizija na preporuke (AgentReferral)
- Motivacija: pasivni prihod

### Layer 2 — Korisnici (pekarne, autopraonice, OPG)
- Trošak za njih: 0-69 EUR/mj
- Benefit: digitalizacija, fiskalizacija, fleet, loyalty
- Motivacija: zakonska obaveza (ISU) + ušteda + inovacija

### Layer 3 — Krajnji kupci
- Trošak: 0
- Benefit: mobilno plaćanje, digitalni računi, loyalty
- Motivacija: convenience

### Layer 4 — Institucije
- Trošak: 0 (API tokeni besplatni)
- Benefit: digitalni pristup podacima umjesto papira
- Motivacija: efikasnost

**Svaki layer zarađuje ili štedi. Nitko ne gubi. Zato se mreža širi.**

---

## POVEZANI DOKUMENTI

| Dokument | Sadržaj |
|----------|---------|
| SEKI_NOCNI_KIOSK_PLAN.md | Kompletni plan za noćni kiosk + zakonski okvir |
| ROBOT_PRODAVAC_PLAN.md | Robot prodavač dnevni mod + komercijalni model |
| CC_TASK_ROBOT_PRODAVAC_KOMPLET.md | 5 implementacijskih taskova |
| SEKI_KOMUNIKACIJA.md | Go-to-market za Šekija |
| LIMIT_CONNECT_AI_PLAN.md | AI master plan |

---

## OVLAST

Ivan Brtan, 21.03.2026:
> "Odriješene su ti ruke i ovlašten si da svim raspoloživim
> sredstvima završimo ovaj projekat do 100% i broj 1 u HR."

Svi agenti (Opus, Sonnet, Haiku) imaju autoritet za implementaciju.
Cilj je jasan. Pravac je definiran. Izvršavamo.

---

Zadnje ažuriranje: 2026-03-21 — Opus
