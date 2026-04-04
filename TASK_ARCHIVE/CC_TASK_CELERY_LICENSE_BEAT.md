# CC_TASK: CELERY BEAT — License check automation
# Datum: 04.04.2026. | Rok: 05.04.2026. | Prioritet: P1

PRAVILO: READ settings.py i tasks.py PRVO. NE diras .env.

KORAK 1 — PROVJERI:
  grep -n "CELERY_BEAT_SCHEDULE" core/settings.py | head -10
  grep -n "def enter_grace\|def suspend" companies/models.py | head -5
  ls companies/tasks.py 2>/dev/null

KORAK 2 — companies/tasks.py:
  Kreiraj shared_task 'companies.check_licenses'
  Loop: svi LicenseToken → active+expired=enter_grace, grace+expired=suspend
  WhatsApp Ivan (+4915771998747) za svaki event
  Return dict: graced/suspended/warnings count

KORAK 3 — BEAT SCHEDULE:
  READ: core/settings.py zadnji CELERY_BEAT_SCHEDULE.update() blok
  DODAJ:
    CELERY_BEAT_SCHEDULE.update({
        'license-check-6h': {
            'task': 'companies.check_licenses',
            'schedule': 21600,
        },
    })
  Koristi schedule=21600 (sekunde), ne crontab.

KORAK 4 — VERIFY + COMMIT:
  venv/bin/python manage.py check 2>&1 | tail -3
  git add -A
  git commit -m "feat(celery): license-check beat 6h"

DONE: [ ] Task [ ] Beat 6h [ ] WhatsApp notify [ ] check prolazi
