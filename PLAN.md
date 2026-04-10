# FENIX MASTER PLAN — 2026-04-10
# Azurirano: 2026-04-10 22:30 (Opus + Seki)
# Status: SVE 10 STAVKI ZAVRSENO

===============================================================
  PLAN KOMPLETIRAN — 10/10 DONE
===============================================================

## ZAVRSENO DANAS (10.04.2026)

| # | Stavka | Tko | Commit |
|---|--------|-----|--------|
| 1 | POS: 10 firmi POSSettings + Konjik fiscal + guard | Opus | 7719d896 |
| 2 | POS BookingSignature hooks (open/close/storno) | Opus | 3b65e0a3 |
| 3 | Archive Readonly plan + auto-downgrade + login | Opus | 54b93e8f |
| 4 | Arhiva AI: 15,816 zapisa status fix | Opus | (data fix) |
| 5 | Silvija WS#5 | Opus | SKIP (vec bila) |
| 6 | Shell: 3 nova panela (payroll/helpdesk/inventory) | Opus | (in 447c57f2) |
| 7 | Dashboard workspace redirect za workere | Opus | 63092572 |
| 8 | Stolarija frontend: 4 templatea (prod/install/handover) | Opus | 985dd7d0 |
| 9 | Stolarija servis views + warranty portal + Celery | Seki | 447c57f2 |
| 10 | KonjikStol cleanup (model + views + migration) | Seki | b327513a |

===============================================================

## SLJEDECI PRIORITETI (11-15.04.)

  1. Load test priprema (CCX33, 12.04.)
  2. GO/NO-GO priprema (15.04.)
  3. Stolarija: Zdenko pilot test (seed data postoji: 12 profila, 12 stakala)
  4. PDF generiranje ponuda + garancija (WeasyPrint)
  5. WhatsApp slanje ponude kupcu (WAHA)

## POZNATI BUGOVI (LOW prioritet)

  - nginx: protocol options redefined warnings (kozmeticki, 30 warnova)
  - FenixScan OCR: graceful fallback nedostaje
  - Arhiva: 4,537 zapisa bez ai_proposal (pos_receipt/invoice bez datoteke)
  - 8 CC_TASK_*.md fajlova na disku (arhivski, mogu se obrisati)
