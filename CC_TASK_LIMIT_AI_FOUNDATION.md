# CC_TASK_LIMIT_AI_FOUNDATION
# Izvršava: Claude Code
# Koordinira: Sonnet
# Prioritet: VISOK
# Datum: 2026-03-21

## OBAVEZNO PRIJE POČETKA
1. Pročitaj FENIX_STATUS.md
2. Pročitaj LIMIT_CONNECT_AI_PLAN.md (CIJELI)
3. git log --oneline -5 da vidiš gdje smo

## CILJ
Kreirati novi Django app `limit_connect_ai` — centralni mozak AI automatizacije.
Ovo je Faza 1. Bez ovoga nema Faze 2 i 3.

## KONKRETAN ZADATAK

### 1. Kreiraj app
```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp limit_connect_ai
```
Registriraj u settings.py u INSTALLED_APPS.

### 2. models.py — TOČNO KAKO JE OPISANO U PLANU
Modeli (sve s UUID primary key):
- AIAgentMission
- AIReportLog
- FundApplicationDraft
- ComplianceWatchItem
- CampaignPlan

OBAVEZNO: Pročitaj companies/models.py i accounts/models.py PRIJE nego napišeš FK.
Ne pretpostavljaj nazive polja.

### 3. tasks.py — Celery taskovi
```python
morning_report_all()    # poziva per-klijent task za sve aktivne misije
send_morning_report(mission_id)  # generira i šalje report
```

Format WhatsApp poruke (iz PLANA):
🌅 *Dobro jutro, [Ime]!*
Ovo je tvoj AI sažetak za [datum]:
📊 *Promet:* X EUR
📦 *Zalihe:* [status]
💰 *Otvoreni računi:* X (Y EUR)
⚖️ *Compliance:* OK
🏛️ *Fondovi:* [status]

Koristi Claude Haiku za generiranje teksta (ANTHROPIC_API_KEY iz env).
Koristi core/whatsapp.py za slanje (provjeri signature PRIJE korištenja).

### 4. Celery Beat u settings.py
```python
CELERY_BEAT_SCHEDULE = {
    ...existing...,
    'morning-report': {'task': 'limit_connect_ai.tasks.morning_report_all', 'schedule': crontab(hour=7, minute=30)},
    'fund-check': {'task': 'limit_connect_ai.tasks.fund_check_all', 'schedule': crontab(hour=9, minute=0)},
    'compliance-check': {'task': 'limit_connect_ai.tasks.compliance_check_all', 'schedule': crontab(hour=8, minute=0, day_of_week=1)},
    'campaign-suggestions': {'task': 'limit_connect_ai.tasks.campaign_suggestions_all', 'schedule': crontab(hour=10, minute=0, day_of_week=5)},
}
```

### 5. views.py — 4 osnovne stranice
- `/ai/missions/` — lista + CRUD misija
- `/ai/reports/` — history reporta
- `/ai/funds/` — EU aplikacije (lista + detail)
- `/ai/cockpit/` — per-klijent AI cockpit (POS + zalihe + compliance + fondovi)

### 6. Templates
Koristi `{% extends "base.html" %}`.
Cockpit template treba kartice: Promet / Zalihe / Računi / Compliance / Fondovi.
Svaka kartica ima status (zelena/narančasta/crvena).

### 7. admin.py
Registriraj sve modele s list_display i list_filter.

### 8. Migracije + test
```bash
venv/bin/python manage.py makemigrations limit_connect_ai
venv/bin/python manage.py migrate
```

### 9. Na kraju OBAVEZNO:
- git add -A && git commit -m "limit_connect_ai Faza 1: modeli, tasks, views, cockpit"
- Upiši DONE u FENIX_STATUS.md pod sekciju "limit_connect_ai Faza 1"
- Javi Sonnet što si napravio i ako ima otvorenih pitanja

## NAPOMENE
- Ne diraj superadmin_ai/ — nadopunjujemo, ne zamjenjujemo
- Ne diraj ai_assistant/ — 26 alata ostaju, koristit ćemo ih iz tasks.py
- Ako nešto nije jasno — STANI i napiši u FENIX_STATUS.md pitanje za Sonnet
- Testiraj s Konjik d.o.o. firmom (Marija Brtan)

## GOTOVO KAD:
- [ ] App se učitava bez grešaka (manage.py check)
- [ ] Sve migracije aplicirane
- [ ] /ai/cockpit/ se prikazuje za logiranog korisnika
- [ ] morning_report_all task se može pokrenuti ručno
- [ ] git commit napravljen
