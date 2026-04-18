# PLAN_066 — CI/CD Pipeline

## Cilj
Automatski pipeline: push → test → lint → deploy. GitHub Actions za test/lint. Deployment script koji sysadmin može pokrenuti jednom komandom. Zero-downtime deploy uz Gunicorn socket reload.

## Strategija
- **CI**: GitHub Actions — pytest + ruff + mypy na svaki push/PR
- **CD**: Manual trigger deploy script na serveru (nije auto-deploy na main — previše rizično za solo projekt)
- **Zero downtime**: Gunicorn graceful reload (SIGHUP) — ne restartira workere odjednom

## GitHub Actions: CI Pipeline
Fajl: `.github/workflows/ci.yml`

```yaml
name: Fenix V3 CI

on:
  push:
    branches: [main, develop, "feature/**"]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-22.04
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: fenix_test
          POSTGRES_USER: fenix
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
        ports:
          - 6379:6379
    
    env:
      DATABASE_URL: postgresql://fenix:testpass@localhost:5432/fenix_test
      REDIS_URL: redis://localhost:6379/0
      SECRET_KEY: ci-secret-key-not-for-production
      DEBUG: "true"
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
      AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      GOOGLE_AI_API_KEY: ${{ secrets.GOOGLE_AI_API_KEY }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: requirements/base.txt
      
      - name: Install dependencies
        run: |
          pip install -r requirements/test.txt
      
      - name: Run ruff linter
        run: ruff check .
      
      - name: Run ruff formatter check
        run: ruff format --check .
      
      - name: Run mypy type check
        run: mypy fenix/ --ignore-missing-imports
        continue-on-error: true  # warnings, ne blokiraj deploy
      
      - name: Run Django system check
        run: python manage.py check --settings=config.settings.test
      
      - name: Run migrations check (no actual migration)
        run: python manage.py migrate --check --settings=config.settings.test
      
      - name: Run pytest
        run: |
          pytest \
            --reuse-db \
            --cov=. \
            --cov-report=xml \
            --cov-report=term-missing \
            --tb=short \
            -x \
            -q
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          file: coverage.xml
        continue-on-error: true

  security-scan:
    runs-on: ubuntu-22.04
    needs: test
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run bandit security scan
        run: |
          pip install bandit
          bandit -r fenix/ -ll -x tests/,*/migrations/
        continue-on-error: true
      
      - name: Check for secrets in code
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Deploy Script: deploy.sh
```bash
#!/bin/bash
# deploy.sh — pokrenuti na serveru: ./deploy.sh [branch]
# Zero-downtime deploy Fenix V3

set -e  # exit on error

BRANCH=${1:-main}
APP_DIR="/var/www/fenix-v3"
VENV="$APP_DIR/venv/bin"
LOG_FILE="/var/log/fenix/deploy.log"

echo "=== Fenix V3 Deploy: $(date) ===" | tee -a "$LOG_FILE"
echo "Branch: $BRANCH" | tee -a "$LOG_FILE"

# 1. Pull code
cd "$APP_DIR"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"
echo "✓ Code updated" | tee -a "$LOG_FILE"

# 2. Install/update dependencies
"$VENV/pip" install -r requirements/production.txt --quiet
echo "✓ Dependencies installed" | tee -a "$LOG_FILE"

# 3. Django checks (ABORT if check fails)
"$VENV/python" manage.py check --deploy 2>&1 | tee -a "$LOG_FILE"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "✗ Django check FAILED — aborting deploy" | tee -a "$LOG_FILE"
    exit 1
fi
echo "✓ Django checks passed" | tee -a "$LOG_FILE"

# 4. Migrate (with backup first)
echo "Creating DB backup..." | tee -a "$LOG_FILE"
pg_dump -U fenix fenix_v3 > "/var/backups/fenix/pre-deploy-$(date +%Y%m%d_%H%M).sql"
"$VENV/python" manage.py migrate --no-input 2>&1 | tee -a "$LOG_FILE"
echo "✓ Migrations applied" | tee -a "$LOG_FILE"

# 5. Collect static
"$VENV/python" manage.py collectstatic --no-input --clear 2>&1 | tee -a "$LOG_FILE"
echo "✓ Static files collected" | tee -a "$LOG_FILE"

# 6. Build Tailwind CSS (ako se koristi JIT build)
if [ -f "package.json" ]; then
    npm run build:css 2>&1 | tee -a "$LOG_FILE"
    echo "✓ CSS built" | tee -a "$LOG_FILE"
fi

# 7. Set permissions
chown -R www-data:www-data "$APP_DIR"
find "$APP_DIR/logs" -type f -exec chown www-data:www-data {} \;
echo "✓ Permissions set" | tee -a "$LOG_FILE"

# 8. Graceful Gunicorn reload (zero downtime!)
# SIGHUP = reload workers without dropping connections
kill -HUP $(cat /var/run/fenix-v3.pid)
echo "✓ Gunicorn reloaded (zero downtime)" | tee -a "$LOG_FILE"

# 9. Restart Celery workers (brief downtime — acceptable for async tasks)
systemctl restart fenix-v3-celery-worker
systemctl restart fenix-v3-celery-beat
echo "✓ Celery restarted" | tee -a "$LOG_FILE"

# 10. Health check
sleep 3
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health/)
if [ "$HTTP_STATUS" != "200" ]; then
    echo "✗ Health check FAILED (HTTP $HTTP_STATUS) — investigate!" | tee -a "$LOG_FILE"
    exit 1
fi
echo "✓ Health check passed (HTTP 200)" | tee -a "$LOG_FILE"

echo "=== Deploy COMPLETED: $(date) ===" | tee -a "$LOG_FILE"
```

## Config struktura (settings split)
```
config/
    settings/
        base.py       ← zajednička konfiguracija
        development.py ← DEBUG=True, console email, SQLite opcija
        test.py       ← test baza, disable AI calls
        production.py ← env() čitanje, security headers, Sentry
```

## config/settings/test.py
```python
from .base import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("TEST_DATABASE_NAME", default="fenix_test"),
        "USER": env("DATABASE_USER", default="fenix"),
        "PASSWORD": env("DATABASE_PASSWORD", default="testpass"),
        "HOST": env("DATABASE_HOST", default="localhost"),
        "PORT": "5432",
        "TEST": {"NAME": "fenix_test"},
    }
}

# Deaktiviraj AI u testovima (osim integration testova)
AI_GATEWAY_MOCK = True

# Brži password hasher u testovima
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Email u memoriji
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Celery sinhrono
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

## requirements/struktura
```
requirements/
    base.txt        ← Django, psycopg2, celery, redis, boto3, ...
    production.txt  ← -r base.txt + gunicorn, sentry-sdk, whitenoise
    development.txt ← -r base.txt + django-debug-toolbar, ipython
    test.txt        ← -r base.txt + pytest-django, factory-boy, coverage, ruff, mypy, bandit
```

## Makefile (developer shortcuts)
```makefile
.PHONY: test lint format check migrate run

test:
	pytest --tb=short -q

test-cov:
	pytest --cov=. --cov-report=html

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

check:
	python manage.py check

migrate:
	python manage.py makemigrations
	python manage.py migrate

run:
	python manage.py runserver 0.0.0.0:8000

celery:
	celery -A config worker -l info -Q default,heavy

shell:
	python manage.py shell_plus

deploy:
	./deploy.sh main
```

## Pre-commit hooks (.pre-commit-config.yaml)
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: detect-private-key
```

## Branch strategija
```
main          ← produkcija, zaštićen branch
develop       ← integracija novih feature-a
feature/XXX   ← individual features
hotfix/XXX    ← hitni fixevi direktno na main
```

- PR na main: obavezno 1 review + CI zeleno
- Direktni push na main: zatvoren (osim hotfix)
- develop → main: merge commit (ne rebase — čuva historiju)

## Monitoring deploymenta
Nakon deploymenta:
1. Sentry (PLAN_064) automatski označava novi release
2. Health endpoint vraća commit hash (za verifikaciju)
3. Slack/WhatsApp notifikacija vlasniku (opcionalno — WAHA)

```python
# health endpoint proširiti s verzijom (PLAN_064):
def get_version_info():
    import subprocess
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=settings.BASE_DIR,
            text=True,
        ).strip()
        return {"commit": commit, "deployed_at": settings.DEPLOY_TIMESTAMP}
    except Exception:
        return {"commit": "unknown"}
```
