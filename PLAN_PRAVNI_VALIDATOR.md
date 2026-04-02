# PLAN: Pravni Validator — AI-asistirana pravna usluga
**Datum ideje:** 02.04.2026. | **Status:** ZAMRZNUT do post-launch
**Vođa:** Ivan Brtan

---

## Ekosustav — Tri stupa

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  AI VALIDATOR   │ →  │  ODVJETNIK       │ →  │  JAVNI BILJEŽNIK    │
│                 │    │  (partner)       │    │  Šimašek — Osijek   │
│  Analiza        │    │  Savjet          │    │  Ovjera / Solemniz. │
│  Rizik score    │    │  Potpis          │    │  Javna vjera        │
│  Predlozi       │    │  Odgovornost     │    │  ELEKTRONIČKI AKT   │
│                 │    │                  │    │  (remote, video)    │
│  5 EUR/dok      │    │  25 EUR/dok      │    │  50-150 EUR/dok     │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
         ↑                      ↑                         ↑
    LIMIT Connect           Partnerstvo              Partnerstvo
    infrastruktura          (topli kontakt)          Šimašek — bivši
                                                     klijent (potrošni
                                                     materijal)
```

---

## Zašto je Javni Bilježnik treći stup (ne opcija)

Bez ovjere javnog bilježnika NISU valjani:
- Osnivanje d.o.o. / j.d.o.o.
- Ugovor o nekretnini
- Punomoć za promet nekretnina
- Hipoteka
- Nasljeđivanje
- Bračni ugovor
- Digitalni posrednik (FINA proces — relevantno za nas!)
- Sudski depoziti

**Zaključak:** Za svaki ozbiljan pravni proces — bilježnik je obavezan korak.
Bez Šimašekove "šape" — lanac nije zatvoren.

---

## Elektronički javnobilježnički akt — konkurentska prednost

**HR Zakon o javnom bilježništvu (NN 78/93 + izmjene 2020):**
Od 2020. — bilježnik može ovjeravati dokumente **remotely**:
- Video poziv + kvalificirani elektronički potpis
- Klijent ne mora dolaziti u ured
- Pravno isto valjano kao fizički dolazak

**LIMIT Connect integracija:**
```
Klijent u Njufringenu → uploadá dokument → AI validator →
odvjetnik pregleda online → Šimašek ovjerava video pozivom →
dokument valjan u HR i EU
```

**Nitko u HR/regiji nema ovo integrirano u SaaS platformu.**

---

## Poslovni model — tri tiera

**Tier 1 — Besplatno (LIMIT Connect klijenti)**
- Compliance check pri kreiranju ugovora
- GDPR validator za obrasce
- Automatski alert pri promjeni zakona

**Tier 2 — 5 EUR/dokument**
- AI analiza + Rizik score + PDF izvještaj
- Preporuke za izmjene

**Tier 3 — 25 EUR/dokument (s odvjetnikom)**
- AI analiza + pregled licenciranog odvjetnika + potpis

**Tier 4 — 75-200 EUR/dokument (puni pravni akt)**
- AI + odvjetnik + Šimašek ovjera
- Remote video notarizacija
- Pravno valjanost HR + EU

---

## Šimašek — partnerstvo

- Bivši klijent (potrošni materijal) — topli kontakt
- Javni bilježnik Osijek
- Predložiti: % od svakog Tier 4 dokumenta
- Ili: fiksna godišnja naknada za ekskluzivni partnerski status
- Njegova vrijednost: legitimitet, pravna valjanost, javna vjera

**Prijedlog za razgovor s Šimašekom:**
"Imamo AI platformu koja priprema dokumente — trebamo bilježnika
koji ih ovjerava remotely. Dajemo ti pristup platformi + % od naplate."

---

## Tehničko (što već postoji)

```
ComplianceWatchdog → NN + EUR-Lex monitoring ✅
Gemini agent       → analiza dokumenata ✅
FenixScan OCR      → čitanje dokumenata ✅
WeasyPrint PDF     → izvještaji ✅
partners/wizard    → ugovor template ✅
GDPR service       → čl. 17 implementiran ✅
Vault trezor       → sigurno čuvanje dokumenata ✅
```

Nedostaje:
- Zakonska baza (HR + EU, strukturirana)
- NLP parser klauzula po članku
- Rizik scoring engine
- Video poziv modul (integracija Zoom/Meet za bilježnika)
- Kvalificirani elektronički potpis (KEP) modul
- Partnerski odvjetnik (1 čovjek)

---

## Domenski fokus (prioritet)

1. GDPR pristanci (sati.edu — dječji podaci, roditeljska suglasnost)
2. Osnivanje d.o.o. za klijente (Šimašek direktno)
3. Radni ugovori (sezonski radnici — već imamo modul)
4. JLS javna nabava — ZJN compliance
5. Ugovori o udomljavanju (azil modul)
6. HKS uzgojni ugovori (kinologija)
7. FINA digitalni posrednik ovjera

---

## Pravna registracija platforme

- d.o.o. za pravne informacijske usluge
- Disclaimer obavezan: "Ovo je informacijska usluga, ne pravni savjet"
- Partnerski odvjetnik potpisuje Tier 3+
- Šimašek ovjerava Tier 4
- Osiguranje profesionalne odgovornosti

---

## Ime (prijedlozi)

- **LexFenix.hr** (vezano uz LIMIT Connect brend)
- **Lex.hr** (ako je slobodno)
- **PravniValidator.hr**
- **BORG Pravnik** (interni naziv)

---

## Veze s ostalim planovima

- sati.edu → GDPR validator za roditeljske pristanke (Tier 1)
- LIMIT Connect → ComplianceWatchdog za JLS klijente (Tier 1/2)
- FINA posrednik → ovjera potrebna (Tier 4, Šimašek direktno)
- Kruljac/OPG → ugovori o zakupu, nabavi (Tier 3)

---
*Zamrznut do 15.04.2026. — GO-LIVE LIMIT Connect ima prioritet*
*Šimašek: kontaktirati nakon 15.04. — topli kontakt, bivši klijent*
