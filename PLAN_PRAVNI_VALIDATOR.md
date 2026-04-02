# PLAN: Pravni Validator — AI-asistirana pravna usluga
**Datum ideje:** 02.04.2026. | **Status:** ZAMRZNUT do post-launch
**Vođa:** Ivan Brtan

---

## Što je i što nije

### JEST:
- AI analiza dokumenata i ugovora
- Compliance checking (GDPR, ZOO, PDV, ZOR, ZJN...)
- Rizik izvještaj s referencama na konkretne zakone
- Template generator za ugovore/pristanke
- Informacijski servis (ne pravni savjet)
- B2B SaaS modul unutar LIMIT Connect + standalone usluga

### NIJE:
- Odvjetnik (zabranjeno bez HKS licence)
- Pravno zastupanje
- Ovjereni pravni akt (bez partnerskog odvjetnika)

---

## Poslovni model

**Tier 1 — Besplatno (LIMIT Connect klijenti)**
- Compliance check pri kreiranju ugovora
- GDPR validator za obrasce
- Automatski alert pri promjeni zakona (već postoji!)

**Tier 2 — 5 EUR/dokument (vanjski korisnici)**
- Upload dokumenta → AI analiza → PDF izvještaj
- Rizik score + preporuke

**Tier 3 — 25 EUR/dokument (s partnerskim odvjetnikom)**
- AI analiza + pregled i potpis licenciranog odvjetnika
- Pravno valjanost za osjetljive dokumente

---

## Tehničko (što već postoji u LIMIT Connect)

```
ComplianceWatchdog → NN + EUR-Lex monitoring ✅
Gemini agent       → analiza dokumenata ✅  
FenixScan OCR      → čitanje dokumenata ✅
WeasyPrint PDF     → izvještaji ✅
partners/wizard    → ugovor template ✅
GDPR service       → čl. 17 implementiran ✅
```

Nedostaje:
- Zakonska baza (HR + EU, strukturirana)
- NLP parser klauzula
- Rizik scoring engine
- Partnerski odvjetnik (1 čovjek koji potpisuje)

---

## Domenski fokus (prioritet)

1. GDPR pristanci (sati.edu, LIMIT Connect klijenti)
2. Radni ugovori (sezonski radnici — već imamo modul)
3. JLS javna nabava (naši komunalni klijenti)
4. Ugovori o udomljavanju (azil modul)
5. HKS uzgojni ugovori (kinologija modul)
6. Ugovori s dobavljačima (OPG, obrti)

---

## Pravna registracija

- d.o.o. za pravne informacijske usluge (ne odvjetničko)
- Obvezni disclaimer na svakom outputu
- Partnerski odvjetnik: 1 licencirani čovjek za Tier 3
- Osiguranje profesionalne odgovornosti

---

## Ime (prijedlozi)

- **LexAI.hr** 
- **PravnikBot** 
- **Lex Fenix** (vezano uz LIMIT Connect brend)
- **BORG Pravnik** (unutarnji naziv)

---
*Zamrznut do 15.04.2026.*
*Direktna veza: sati.edu treba GDPR validator za dječje podatke*
*Direktna veza: LIMIT Connect JLS klijenti trebaju ZJN validator*
