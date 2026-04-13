# COMPLIANCE_SHIELD — Zakonski štit (Ivan ne ide u zatvor)
# Autor: Sonnet
# Datum: 2026-03-25
# Ovaj fajl = lista svih zakona koji mogu ugroziti Ivana osobno

---

## 🔴 KAZNENA ODGOVORNOST — Fiskalizacija (ZATVORSKA KAZNA)

**Zakon:** Zakon o fiskalizaciji u prometu gotovinom (NN 133/12, 115/16, 106/18)

**Što može ugroziti Ivana:**
- Prodaja bez JIR-a = kazneno djelo
- Duplicirani JIR = kazneno djelo
- Manipulacija ZKI = kazneno djelo
- Software koji omogućava brisanje/izmjenu fiskaliziranih računa = kazneno djelo

**Status u platformi:**
- ✅ `fiscal/service.py` implementiran
- ✅ FiscalLog bilježi sve transakcije
- 🔴 **BUG: Dupli JIR moguć** — nema idempotency checka → FIX u CC_TASK_CONCURRENCY_LOCKOVI.md
- 🔴 **Race condition** → isti fix

**Redovita provjera (GEMINI radi automatski):**
- Svaki tjedan: provjeri FiscalLog za status='error' bez retry-a
- Alarm ako ima bilo koji receipt bez JIR-a koji je stariji od 24h

---

## 🔴 GDPR — Osobni podaci (NOVČANA KAZNA do 20M EUR)

**Zakon:** Uredba (EU) 2016/679 — GDPR, implementirana u HR kao NN 42/18

**Što može ugroziti Ivana:**
- Cross-tenant leak (jedan klijent vidi podatke drugog) → 89 unscoped() poziva
- Osobni podaci bez pravne osnove (OIB klijentima bez ugovora)
- Nedostatak Data Processing Agreement s klijentima (T&C)
- Nema Data Breach procedure

**Status:**
- 🔴 89 unscoped() → CC_TASK_UNSCOPED_AUDIT.md
- 🔴 T&C consent 0/78 firmi → CC_TASK_3KLIK_REGISTRACIJA.md
- 🟡 DPA (Data Processing Agreement) — treba template (Marija Brtan, odvjetnik)
- 🟡 Data Breach procedure — nema dokumentiranog postupka

**Akcija:**
- CC Code fiksira unscoped() ovaj tjedan
- Sonnet priprema DPA template za klijente (sljedeća sesija)

---

## 🟠 PDV ZAKON — Pogrešne stope (POREZNA INSPEKCIJA)

**Zakon:** Zakon o porezu na dodanu vrijednost (NN 73/13 + izmjene)

**Kritične stope:**
| Kategorija | Stopa | Risk |
|------------|-------|------|
| Standardna | 25% | OK |
| Hrana za konzumaciju | 5% | Pekara Šeki — provjeri! |
| Lijekovi, knjige | 5% | N/A za sada |
| Turizam, apartmani | 13% | Rental modul — provjeri! |
| Udruge (neke usluge) | 0% / izuzeće | KUD — provjeri! |

**Action za CC Code:**
```python
# Provjeri default tax_rate u POS stavkama
# Šeki (pekara) mora imati 5% na prehrambene proizvode, ne 25%
# Greška = porezna utaja = Ivan ide u zatvor
```

**Redovita provjera:** Gemini čita PDV zakon izmjene svaka 3 mjeseca

---

## 🟠 ZOR — Zakon o računovodstvu

**Zakon:** NN 78/15 + 134/15 + 120/16

**Relevantno za platformu:**
- Knjige moraju biti čuvane min. 11 godina (arhiva DONE ✅)
- Svaka promjena u knjizi mora biti auditirana (audit trail DONE ✅)
- Elektronička isprava mora imati integritet (hash chain DONE ✅)

**Status:** ✅ Pokriveno

---

## 🟠 AML — Pranje novca (OZBILJNA KAZNENA)

**Zakon:** Zakon o sprječavanju pranja novca i financiranja terorizma (NN 108/17)

**Prag obveze:** Platforma je fintech — ako procesira plaćanja, mora imati AML procedure.
Trenutno: LIMIT Connect NE procesira plaćanja direktno (nije payment processor).
Ako se doda Stripe/integrirani payment → ODMAH treba AML compliance.

**Status:** 🟡 Robot prodavač + Stripe plan → **STANI** dok Marija ne potvrdi AML obvezu

---

## 🟡 NKD NULL — ADMINISTRATIVNI RIZIK

**Zakon:** Zakon o obrtu, Zakon o trgovačkim društvima
86 firmi na platformi nema NKD šifru. Potencijalni problem pri državnim inspekcijama.

**Fix:** CC_TASK_WIZARD_NKD_BULK.md (backlog — nije hitno ali nije zanemarivo)

---

## AUTOMATSKI MONITORING — Gemini Compliance Watchdog

**Gemini čita i prati:**
1. Narodne novine RSS — svaki dan, ključne riječi: fiskalizacija, PDV, ZOR, GDPR
2. EUR-Lex API — EU regulative relevantne za HR
3. FINA objave — promjene u CIS endpointima

**Alarm triggeri:**
- Nova izmjena Zakona o fiskalizaciji → Sonnet i Ivan dobivaju notifikaciju isti dan
- GDPR enforcement action u HR → provjera usklađenosti
- PDV stopa promjena → automatski update u bazi stopa

**Task:** GEMINI_TASK_COMPLIANCE_WATCHDOG_V2.md — već postoji, ovo je nadopuna

---

## SUMMARY — Ivanova osobna odgovornost

| Rizik | Zakon | Kazna | Status | ETA Fix |
|-------|-------|-------|--------|---------|
| Dupli JIR | Fiskalizacija | Zatvor | 🔴 | Ovaj tjedan |
| Cross-tenant leak | GDPR | 20M EUR | 🔴 | Ovaj tjedan |
| Pogrešan PDV Šeki | PDV zakon | Porezna | 🟠 | Provjera odmah |
| T&C consent | GDPR | Upravna | 🟠 | Do 1.4. |
| AML za Stripe | AML zakon | Kaznena | 🟡 | Prije Stripe |
| NKD NULL | Adm. zakon | Novčana | 🟡 | Travanj |
