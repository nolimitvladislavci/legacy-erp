# CC ACTIVE TASK — čitaj ovo prvo
# Ažurirano: 2026-03-21 11:50 — Sonnet

## TRENUTNI TASK
**CC_TASK_LIMIT_AI_FOUNDATION.md**

Kreni odmah. Sve je opisano u tom fajlu.
Kratki sažetak:
1. Kreiraj Django app `limit_connect_ai`
2. Modeli: AIAgentMission, AIReportLog, FundApplicationDraft, ComplianceWatchItem, CampaignPlan
3. Celery tasks: morning_report_all, send_morning_report
4. Views + templates: /ai/missions/, /ai/reports/, /ai/funds/, /ai/cockpit/
5. Migracije + git commit

## KONTEKST
- Pročitaj i LIMIT_CONNECT_AI_PLAN.md za širu sliku
- Testiraj na Konjik d.o.o. (Marija Brtan)
- Ne diraj superadmin_ai/ ni ai_assistant/

## KAD ZAVRŠIŠ
- Upiši DONE u FENIX_STATUS.md
- Ažuriraj ovaj fajl: zapiši što si napravio i koji je sljedeći task
