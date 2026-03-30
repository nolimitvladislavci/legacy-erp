# GEMINI_TASK_PARTNER_ONBOARDING_WORKFLOW.md
# Za: Gemini (autonomni agent) — RADI, ne pitaj dozvolu
# Datum: 2026-03-30
# Prioritet: VISOKO
#
# Gemini je predložio Partner Onboarding workflow — sada ga gradi.
# Paralelno s EU strateškom analizom (GEMINI_TASK_POSREDNIK_EU_ANALIZA.md).
#
# KONTEKST:
# B2B2B model je odobren. Distributer nije klijent — on je kanalni partner.
# Distributer ne koristi SmartEntry za sebe — on dobiva vlasteni link koji
# šalje dalje. Onboarding mora reflektirati tu razliku.

---

## ZADATAK A — Partner onboarding flow (dokument, ne kod)

Napiši detaljni workflow dokument za onboarding novog Distributera:

### Faza 0: Identifikacija (tko je potencijalni distributer?)
- Profil: računovođa koji vodi 20+ klijenata, ili poduzetnik koji poznaje lokalne firme
- Kanal pronalaska: preporuka, LinkedIn, direktni upit
- Kvalifikacijski kriteriji: ima li lokalno tržište, može li osobno servisirati klijente

### Faza 1: Inicijalni razgovor
- Što im pokazujemo? (demo, proof points, reference)
- Koje argumente koristimo? ("battlefield-tested", 72/72 tests, Viskovic-bau DE reference)
- Što oni pitaju? (FAQ za distributer razgovor)
- Kada znamo da su "closing"?

### Faza 2: Ugovor i onboarding (D0-D7)
- Koji dokumenti trebaju biti potpisani? (SaaS Agreement, DPA, NDA)
- Što LIMIT Connect postavlja tehnički? (WhiteLabel, subdomain, InviteCode)
- Što distributer dobiva na D1? (login, brand settings, entry URL, materijali)
- Kako znaju da je sve gotovo?

### Faza 3: Distributer onboardira prve klijente (D7-D30)
- Koji alati im dajemo? (entry URL, QR kod, prezentacija za klijente)
- Kako pratimo njihov napredak? (dashboard metriks)
- Kada interveniramo? (nema nijednog klijenta nakon 2 tjedna)

### Faza 4: Steady state (D30+)
- Kada i kako dolazi billing?
- Tko je njihov kontakt u LIMIT Connect?
- Što se dogodi ako žele proširiti ili otkazati?

---

## ZADATAK B — Sales materijali za distributera

Napiši (u markdown, spremi u /var/www/fina-connect/sales/):

### B1: One-pager za HR distributera (jedna A4 stranica)
Naslov: "Postanite LIMIT Connect distributer u vašoj regiji"
Sadržaj:
- Što je distributer (3 rečenice)
- Financijska matematika: 10 klijenata = X EUR/mj neto
- Što LIMIT Connect daje (softver, support, brand)
- Što distributer daje (lokalno tržište, direct sales, onboarding klijenata)
- Poziv na akciju: kontakt email/WhatsApp

### B2: One-pager za EU partnera (engleski)
Naslov: "LIMIT Connect — White-label fiscal infrastructure for EU markets"
Sadržaj:
- Problem: KassenSichV, XRechnung, 2+ years to build from scratch
- Rješenje: License proven infrastructure (72/72 tests, live DE customer)
- Što je uključeno: KassenSichV adapter, TSE integration, XRechnung, white-label
- Pricing overview (SaaS licence model, ne specifični iznosi)
- Next step: pilot program Q3 2026

### B3: FAQ dokument za obje grupe
Najčešća pitanja s odgovorima. Predvidi barem 15 pitanja po grupi.

---

## ZADATAK C — Certifikat Vault (specifikacija za CC Code)

Gemini je predložio "Certifikat Vault unutar FAL-a."
Razradi što to točno znači tehnički:

### Što pohranjujemo?
- ISO 27001 certifikat (PDF, datum izdavanja, datum isteka, tijelo certifikacije)
- PU licenca za Informacijskog posrednika (HR) ili ekvivalent po državi
- Cyber osiguranje polica (iznos pokrića, istječe kada)
- Penetration test izvješće (datum, firma koja je radila, status)
- DPA ugovor s LIMIT Connect (potpisan, datum)

### Koji su statusi?
- VALID (postoji, ne ističe u 60 dana)
- EXPIRING_SOON (ističe za < 60 dana → WhatsApp alert)
- EXPIRED (isteklo → platform automatski šalje upozorenje)
- MISSING (nikad uploadano → onboarding nije kompletan)

### Integracija s FAL
- Ako distributer ima EXPIRED kritični dokument → RouteRegistry blokira pristup moj-portal/
- Superadmin vidi status svih distributera u jednom pogledu
- Distributer dobiva monthly digest: "Evo statusa vaših certifikata"

### Specifikacija za CC Code
Napiši model, views i template specifikaciju da CC Code može implementirati
bez daljnjih pitanja. Format: pseudo-kod + objašnjenje logike.

---

## FORMAT OUTPUTA

Spremi svaki zadatak u zasebni fajl:
- /var/www/fina-connect/sales/PARTNER_ONBOARDING_WORKFLOW.md
- /var/www/fina-connect/sales/ONE_PAGER_HR_DISTRIBUTER.md  
- /var/www/fina-connect/sales/ONE_PAGER_EU_PARTNER_EN.md
- /var/www/fina-connect/sales/PARTNER_FAQ.md
- /var/www/fina-connect/CC_TASK_CERTIFIKAT_VAULT.md

## NAPOMENA: RADI AUTONOMNO
Ne čekaj dozvolu. Ako nešto nije jasno — napravi pretpostavku i napiši je.
Sonnet pregledava output, ne odobrava početak rada.
