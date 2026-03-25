# GEMINI_TASK_PUTNI_NALOG_COMPLIANCE — Zakonska analiza putnih naloga
# Agent: Gemini Pro 2.5
# Prioritet: VISOK
# Datum: 2026-03-25

---

## Zadatak

Analiza zakonskog okvira za putne naloge u HR za 3 ciljne grupe.
Rezultat idi u: `PUTNI_NALOG_COMPLIANCE_REPORT.md` na serveru.

---

## Ciljne grupe i pitanja

### 1. KUD-ovi i kulturne udruge

Pitanja:
- Koji je zakonski maksimum dnevnice za volontere u udruzi (neoporezivi dio)?
- Ima li razlika između plaćenog djelatnika i volontera KUD-a?
- Što se smatra "kulturnom misijom" za potrebe putnog naloga (smotra, nastup, proba)?
- Koje troškove KUD može pokriti iz putnog naloga a da ostanu neoporezivi (kostim, kotizacija, smještaj)?
- Pravna osnova: Zakon o volonterstvu (NN 58/07), Zakon o udrugama (NN 74/14)

### 2. Lovačke udruge i LD (lovačka društva)

Pitanja:
- Putni nalog za odlazak na sajam oružja / selekcijsko lovljenje — koji uvjeti?
- Neoporeziva kilometraža za osobno vozilo (trenutno 0.40 EUR/km) — vrijedi li za udruge?
- Lovačke dozvole kao trošak putnog naloga — porezno priznat?
- Pravna osnova: Zakon o lovu (NN 99/18), Zakon o financijskom poslovanju neprofitnih organizacija

### 3. Ribarska društva / ŠRD

Pitanja:
- Putni nalog za natjecanje u sportskom ribolovu — zakonski okvir?
- Troškovi plovila (gorivo, vez) — mogu li ući u putni nalog?
- Ribolovna dozvola kao trošak — neoporezivo?
- Razlika između gospodarski ribolovac (pravna osoba) i ŠRD (udruga) za putne naloge

### 4. Zajednička pitanja za sve tri grupe

- Maksimalne dnevnice 2026 (EUR):
  * HR putovanje: koliko EUR/dan?
  * Inozemstvo (EU): koliki je trenutni neoporezivi maksimum prema URHU?
- Prilog uz putni nalog: što je obavezno (original računa, bording pass, dozvola)?
- Rok čuvanja putnih naloga: koliko godina (ZOR standard)?
- Tko potpisuje putni nalog u udruzi: predsjednik, blagajnik ili oboje?

---

## Format outputa

`PUTNI_NALOG_COMPLIANCE_REPORT.md` treba sadržavati:

```markdown
# Putni nalog — Compliance Report 2026
## 1. Dnevnice — Neoporezivi maksimumi
## 2. KUD specifičnosti
## 3. Lovačke udruge specifičnosti  
## 4. Ribarska društva specifičnosti
## 5. Obvezni priloži
## 6. Obračun kilometraže — formula
## 7. Konto knjiženje (za Mariju Brtan)
## 8. Rizici i crvene linije
```

---

## Sekundarni zadatak: Upsell argumenti

Za svaku grupu napiši 1-2 rečenice zašto im treba LIMIT Connect putni nalog umjesto papira:
- KUD: "Predsjednik kreira nalog na mobitelu na autobusu prema smotri..."
- Lovci: "Prilaže sliku lovačke dozvole direktno u aplikaciju..."
- Ribari: "PDF s potpisom predsjednika za poreznu inspekciju jednim klikom..."

Ove rečenice idu direktno u GTM_PLAN kao prodajni argumenti.
