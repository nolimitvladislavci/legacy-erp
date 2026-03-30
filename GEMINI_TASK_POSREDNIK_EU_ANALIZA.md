# GEMINI_TASK_POSREDNIK_EU_ANALIZA.md
# Za: Gemini (autonomni agent)
# Datum: 2026-03-30
# Prioritet: STRATEŠKI — Ivan čita output direktno
#
# KONTEKST:
# LIMIT Connect je ERP/POS SaaS platforma koja ima tehničke komponente
# za postati infrastruktura za digitalne posrednike u HR i EU.
# Već postoji: KassenSichV adapter (DE), XRechnung/ZUGFeRD (u razvoju),
# HR fiskalizacija (kompletna), GDPR compliance, live DE klijent (Viskovic-bau.de)
#
# IVAN TREBA: Stratešku analizu koja mu daje konkretne argumente
# za razgovor s potencijalnim HR i EU partnerima.

---

## ZADATAK

Istraži i napiši analizu za sljedeće:

### 1. EU REGULATORNA MAPA 2025-2028

Za svaku državu: HR, DE, AT, SI, CZ, PL, SK — napiši:
- Koji zakon uvodi obavezu e-fiskalizacije / e-računa
- Rok primjene (datum stupanja na snagu)
- Što mora imati digitalni posrednik (certifikati, licence, tijela koja odobravaju)
- Trenutni vodeći softver na tržištu (tko dominira)
- Procijeni: jesu li lokalne firme nezadovoljne trenutnim rješenjem?

Fokus: DE (KassenSichV 2.0), AT (RKSV), SI (FURS eDavki)

### 2. COMPETITIVE LANDSCAPE — Tko prodaje white-label fiscal SaaS u EU

Traži firme koje:
- Prodaju SaaS licencu za fiskalnu infrastrukturu (ne direktno krajnjim korisnicima)
- Imaju white-label model (posrednik ih koristi pod vlastitim brendom)
- Naplaćuju B2B licensing fee

Za svaku firmu napiši: naziv, država, model naplate, tko im je klijent, slabosti.
Ovo su potencijalni konkurenti LIMIT Connect u licensing prostoru.

### 3. PRICING BENCHMARK

Koliko vrijedi SaaS licenca za fiscal middleware u EU?

Istraži:
- Koliko košta DATEV SaaS licenca (DE)
- Koliko košta Lexware licenca (DE)
- Koliko košta Sage X3 licenca (EU)
- Koliko košta BMD NTCS licenca (AT)
- Što naplaćuju custom fiscal API provideri (Fiskaly, Taxdoo, Candis)

Output: rasponi cijena za B2B SaaS licencu, po modelu (per-seat, flat, revenue share)

### 4. PROCJENA VELIČINE TRŽIŠTA

Za Scenarij A (HR regionalni posrednici):
- Koliko ima PU-registriranih Informacijskih posrednika u HR?
- Koliko tvrtki u HR ima >10 klijenata koje bi mogli onboardati?
- Koji gradovi/regije su potencijalna mjesta za regionalnog posrednika?

Za Scenarij B (EU licenca):
- Koliko SaaS providera u DE traži KassenSichV rješenje za preprodaju?
- Koliko računovodstvenih ureda u DE bi moglo postati digitalni posrednik?
- Koji je trend: konsolidacija (par velikih igrača) ili fragmentacija (mnogo malih)?

### 5. RISK MATRICA

Za svaki scenarij (HR posrednik, EU licenca, hybrid):
- Regulatorni rizici: što se dogodi ako zakon promijeni zahtjeve?
- Ovisnost rizik: ako 1 EU licencee otpada, koliki je financijski udar?
- Reputacijski rizik: ako licencee napravi grešku prema klijentu
- Operativni rizik: koji je minimalni team za podršku 5 EU licensee-a?
- Preporučene mjere za svaki rizik

### 6. UGOVORNI OKVIR

Što mora sadržavati SaaS Licensing Agreement za EU partnera?
- SLA zahtjevi (uptime, response time, support tiers)
- Data processing (GDPR — DPA između LIMIT Connect i licensee)
- Intellectual property (što licensee smije, što ne smije)
- Termination clause (što se dogodi s njihovim klijentima ako raskid)
- Liability cap (do kojeg iznosa LIMIT Connect odgovara za greške)

Nije potrebno pisati pravni dokument — napiši što su ključne točke za razgovor s odvjetnikom.

---

## FORMAT OUTPUTA

Napiši markdown dokument spreman za čitanje.
Bez akademskog tona — konkretni podaci, konkretne preporuke.
Ako nešto ne možeš pronaći, napiši "PODATAK NIJE DOSTUPAN — preporučujem direktni upit."
Na kraju: jedna tablica s preporukom koji scenarij krenuti prvi i zašto.

Spremi output kao: POSREDNIK_EU_STRATESKA_ANALIZA_2026.md

---

## SEKUNDARNI ZADATAK (ako ostane kapaciteta)

Pronađi 5 konkretnih firmi u DE koje:
- Imaju >50 zaposlenika
- Bave se maloprodajom ili ugostiteljstvom
- Možda trebaju KassenSichV rješenje

Za svaku: naziv, grad, procjena veličine, kontakt ako postoji javno.
Ovo su potencijalni prvi EU klijenti za cold outreach.
