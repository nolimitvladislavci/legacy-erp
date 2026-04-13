# TAX WIZARD — MASTER PLAN
## "Naš TaxFix" — HR fin-tech osvajanje

**Datum kreacije:** 2026-03-24  
**Git branch cilj:** `feature/tax-wizard`  
**MVP launch:** 2027-02-01 (rok DOH 2026)  
**Sezona 2027:** 5.000 korisnika, 150.000€ prihod u 4 tjedna

---

## TROJSTVO + IVAN

| Agent | Uloga | Misija fajl |
|-------|-------|-------------|
| **CC Code** | Executor — gradi infrastrukturu | CC_TASK_TAX_WIZARD_F1.md |
| **Gemini** | AI Motor — deductions engine + AI savjetnik | GEMINI_TASK_TAX_WIZARD_F2.md |
| **Sonnet** | Koordinator — UX wizard + partner portal | SONNET_TASK_TAX_WIZARD_F3.md |
| **Ivan** | Tržište — Marija, HOK, launch | IVAN_TASK_TAX_WIZARD_F4.md |

---

## MOAT (zaštitni jarak koji nitko ne može kopirati)

```
Taxfix:  korisnik tipka → prazna polja → 30 min unosa → submit
NAŠE:    ERP zna sve → korisnik verificira → 5 min → submit
         + računovođa šalje white-label link → viral distribucija
         + IntegrityHash chain → tamper-evident audit log
```

Imamo **3.242.414,57€** fakturiranih primitaka u 2025. samo u testnoj bazi.
To su podaci koji čekaju da se automatski unesu u DOH obrazac.

---

## TEHNIČKI STACK (reciklaža, ne gradnja)

```
Što postoji → Što koristimo
─────────────────────────────────────────────────
ArhivaDocument.integrity_hash → TaxWizardSession.integrity_chain
WizardDraft JSON engine (partners) → TaxWizard step runner
Invoice, TaxPeriod, Payslip → prefill_engine.py
WeasyPrint (invoicing) → DOH PDF generacija
Stripe (payments) → split payment računovođa
Haiku (ai_assistant) → deductions AI savjetnik
WhatsApp (notifications) → rok podsjetnici
```

---

## FAZE

### F1 — Infrastruktura (CC Code, Tjedan 1-2)
- Django app `tax_wizard/`
- Modeli: TaxWizardSession, PartnerTaxAccount  
- IntegrityHash chain
- Prefill engine (invoicing + payroll → wizard)
- URL routing

### F2 — AI Motor (Gemini, Tjedan 2-3)
- Deductions rule engine (12 zakonskih olakšica HR)
- AI Advisor (Haiku) — proaktivne poruke
- "Detektor propuštenog novca"
- Simulator JLS stopa (bez savjeta, samo podaci)

### F3 — UX + Partner Portal (Sonnet, Tjedan 3-4)
- Wizard UI (mobile-first, 5 koraka)
- Računovođa white-label dashboard
- Stripe split payment (30% Marija, 70% LIMIT)
- PDF DOH / ZPP-DOH generacija

### F4 — Tržište (Ivan, Paralelno)
- Marija Brtan onboarding (PartnerTaxAccount)
- HOK kontakt (white-label distribucija)
- Konjik klijenti kao beta testeri
- WhatsApp kampanja plan za veljaču 2027

---

## PRAVNI OKVIR (armirani T&C)

Wizard je **kalkulator**, ne porezni savjetnik.
- Citiramo zakon: "Prema čl. 14. Zakona o porezu na dohodak, koeficijent za dijete je 0,7"
- Ne savjetujemo: nikad "Preporučujemo vam da..."
- Odgovornost isključivo na poreznom obvezniku (T&C korak 0)
- Audit log dokazuje što je korisnik točno potvrdio

---

## POSLOVNI MODEL

| Paket | Cijena | Target |
|-------|--------|--------|
| Kalkulator | 0€ | Akvizicija, SEO |
| ZPP-DOH submit | 9,99€ | Zaposlenici, mladi |
| DOH submit | 29€ | Obrtnici s knjigama |
| Pro Obrtnik | 49€/god | DOH + P-PPI + AI |
| Računovođa paket | 99€/mjes | 3.500 księg. servisa u HR |
| White-label | po dogovoru | HOK, banke, sindikati |

**Provizija partnera:** 30% automatski via Stripe Connect

---

## MILESTONE TRACKER

```
[ ] F1: tax_wizard app struktura kreirana
[ ] F1: TaxWizardSession model + migrations
[ ] F1: PartnerTaxAccount model
[ ] F1: IntegrityHash chain implementiran
[ ] F1: prefill_engine.py — invoicing + payroll podatke vuče
[ ] F1: URL routing + base views
[ ] F2: deductions.py — 12 olakšica, rule engine
[ ] F2: ai_advisor.py — Haiku proaktivne poruke
[ ] F2: JLS stopa simulator (574 JLS u HR)
[ ] F3: Wizard UI — 5 koraka, mobile-first
[ ] F3: Partner dashboard — white-label setup
[ ] F3: Stripe Connect split payment
[ ] F3: PDF DOH generacija (WeasyPrint)
[ ] F4: Marija onboarding — PartnerTaxAccount
[ ] F4: HOK white-label pitch
[ ] F4: WhatsApp kampanja plan
```
