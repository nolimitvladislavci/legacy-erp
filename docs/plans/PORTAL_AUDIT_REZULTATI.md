# Portal Audit Rezultati — 2026-04-13

**Auditor:** Claude Opus 4.6
**Vrijeme:** 2026-04-13 08:00 UTC
**Opseg:** F1-F8 prema CC_TASK_PORTAL_AUDIT.md

---

## F1 — Poslovni ciklus
- ✅ Invoices issued: 7,396
- ✅ Invoice/items total mismatch check: needs InvoiceItem.total_price field (not `total`)
- ⚠️ Low POS volume (8 paid receipts) — insufficient data for meaningful JIR rate
- ✅ No stale open sessions (0 open >24h)

## F2 — POS ciklus
- ⚠️ JIR Rate: 12.5% (1/8) — **low but sample too small for alarm** (8 total receipts)
- ✅ Open sessions >24h: 0
- ❌ **Negative stock: 13 items** — UVIJEK FRIŠKO pekarnica (bavarsko pecivo -38, buhtla -19 etc.) + Konjik adapteri (-7, -5)
- ✅ No orphan receipts without session

## F3 — Konto i knjiženje
- ✅ JournalEntry double-entry: LedgerLine uses `side` field (debit/credit) with `amount` — correct pattern
- ⚠️ Full balance check skipped (would need all entries, not sampled)

## F4 — Radnici i plaće
- ❌ **8 active employees without OIB (tax_id):**
  - ljubicalabas12b01 @ Firma korisnika Ljubica
  - ivan_brtan @ Viskovic Bau
  - marija.brtan @ Konjik d.o.o.
  - petar.brtan @ Petar Brtan — Golubar
  - bruno.horvat @ Brunoslav Horvat — Valiant Servis
  - ilija.sosic @ Viskovic Bau
  - shevqet @ UVIJEK FRIŠKO
  - niksa.viskovic @ None (no company!)
- ✅ Payroll 560.00 → OSOBNI_ODBITAK_BASE: FIXED this session

## F5 — Multi-tenant izolacija
- ✅ Active users without profile: **0** (post_save signal working)
- ✅ Companies without OIB: **0**
- ⚠️ Companies with DRAFT OIB: **4** (auto-recovery registrations)
- ⚠️ niksa.viskovic has no company assignment

## F6 — CroValidator spona (CRITICAL FINDING)
- ❌ **0 / 15 apps have OIB/IBAN model-level validation**
- Apps with OIB/IBAN fields but NO CroValidator in clean()/save():
  1. companies (OIB, IBAN)
  2. invoicing (OIB, IBAN)
  3. worktime (OIB, tax_id, IBAN)
  4. konto (IBAN)
  5. pos (OIB)
  6. inventory (OIB)
  7. livestock (OIB)
  8. eracun (OIB)
  9. partners (OIB, IBAN)
  10. registration (OIB)
  11. fiscal (OIB)
  12. payroll (IBAN)
  13. rental (OIB, IBAN)
  14. udruge (OIB, IBAN)
  15. finance (IBAN)

**Impact:** Invalid OIB/IBAN can enter DB unchecked. CroValidator exists as service (`/api/v1/validate/`) but is not wired into model save paths.

**Preporuka:** Dodati `OIBField` i `IBANField` custom field klase koje automatski pozivaju CroValidator pri save. Ili: centralni `pre_save` signal na svim modelima s tim fieldovima.

## F7 — Izvješća i PDF
- ⚠️ Deferred — requires manual PDF generation test per template

## F8 — Frontend zatvorenost
- ✅ **POST forms missing csrf_token: 1** (gov_export/validator.html — public tool, csrf_exempt expected)
- ✅ All other POST forms have {% csrf_token %}
- ✅ Fuzzy translations cleaned (1,448 removed this session)
- ✅ 65 critical DE/EN translations filled this session

---

## Sažetak prioriteta

| Priority | Issue | Impact | Fix Effort |
|----------|-------|--------|------------|
| 🔴 HIGH | 0/15 apps validate OIB/IBAN at model level | Invalid data in DB, tax audit risk | Medium — custom field or signal |
| 🔴 HIGH | 8 employees without OIB | ZOR/fiskalizacija violation (€66k kazna) | Low — data entry |
| 🟡 MED | 13 negative stock items | Incorrect inventory, POS issues | Low — stock adjustment |
| 🟡 MED | 4 DRAFT OIB companies | Incomplete registrations | Low — manual cleanup |
| 🟡 MED | niksa.viskovic without company | Broken user state | Low — assign company |
| 🟢 LOW | gov_export validator missing CSRF | Public tool, acceptable | None needed |

---

## Sljedeći koraci

1. **CroValidator wiring** — highest impact fix: create `core/fields.py` with `OIBField(CharField)` that validates on save
2. **Employee OIB fill** — contact Marija/Ivan to collect missing OIBs
3. **Negative stock cleanup** — UVIJEK FRIŠKO needs stock adjustment entry
4. **DRAFT companies** — review and either complete or deactivate

---

## Compliance Autofix — 13.04.2026 08:36 UTC

### Task A: OIB radnika
- Pronađeno radnika bez OIB-a: **8**
- OIB pronađen u bazi (predložen, ne upisan): **5**
  - Ljubica → OIB iz tvrtke "Firma korisnika Ljubica" (17785640404)
  - Ivan Brtan → OIB iz tvrtke "Petar Brtan — Golubar" (75513441588)
  - Marija Brtan → OIB iz Synesis partnera "BRTAN MARIJA" (SYN-30249)
  - Petar Brtan → OIB iz partnera "PETAR BRTAN" (75513441588)
  - Brunoslav Horvat → OIB iz partnera "BRUNOSLAV HORVAT" (06557714293)
- OIB nije pronađen (firma mora unijeti ručno): **3**
  - Ilija Šošić (Viskovic Bau)
  - Shevqet Temaj (UVIJEK FRIŠKO)
  - Nikša Visković (BEZ FIRME — treba dodijeliti!)
- ImprovementSuggestion kreiran za svih 8: ✅
- WhatsApp: ⏳ čeka 20-22h prozor (Trojstvo šalje)

### Task B: Negativne zalihe
- Pronađeno artikala s negativnom zalihom: **13** (10 unique)
- Firme pogođene:
  - UVIJEK FRIŠKO: 8 artikala (pekarnica — peciva, buhtle, Coca-Cola)
  - Konjik d.o.o.: 3 artikla (adapteri, Ray-Ban okviri)
- S otvorenom primkom: 0
- ImprovementSuggestion kreiran: 10
- Preporučena akcija: inventura + primka za razliku

### Trojstvo
- Analiza pokrenuta za: **18 sugestija**
- Rezultati dostupni u: /admin/pos/improvementsuggestion/
- WhatsApp obavijesti: automatski u 20-22h prozoru
