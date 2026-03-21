# CC ACTIVE TASK — čitaj ovo prvo
# Ažurirano: 2026-03-21 12:30 — CC Code (Opus)

## ZAVRŠEN TASK
**CC_TASK_LIMIT_AI_FOUNDATION.md** — DONE

### Što je napravljeno:
1. Django app `limit_connect_ai` — kreiran i registriran u INSTALLED_APPS
2. 5 modela (svi UUID PK): AIAgentMission, AIReportLog, FundApplicationDraft, ComplianceWatchItem, CampaignPlan
3. 4 Celery taska: morning_report_all (07:30), fund_check_all (09:00), compliance_check_all (pon 08:00), campaign_suggestions_all (pet 10:00)
4. send_morning_report — dohvati POS/zalihe/račune, Claude Haiku generira tekst, šalje WhatsApp/email
5. 4 viewa: cockpit, missions (CRUD), reports, funds
6. 4 HTML templatea: ai_cockpit, ai_missions, ai_reports, ai_funds
7. Admin: svih 5 modela s list_display + list_filter
8. CELERY_BEAT_SCHEDULE: 4 nova taska
9. Migracije aplicirane (0001 + 0002)
10. URL: /ai-cockpit/ (cockpit, missions, reports, funds)

### Verifikacija:
- [x] manage.py check — 0 issues
- [x] Sve migracije aplicirane
- [x] URL routing radi (/hr/ai-cockpit/cockpit/ etc.)
- [x] Models + tasks import OK
- [x] Git commitano

## SLJEDEĆI TASK
**CC_TASK_LIMIT_AI_FUNDS.md** — EU fondovi workflow (Faza 2)
Čeka Sonnet review + odobrenje za nastavak.
