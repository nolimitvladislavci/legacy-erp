.PHONY: help dev test lint migrate deploy clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev:  ## Run development server
	cd /var/www/fina-connect && venv/bin/python manage.py runserver 0.0.0.0:8000

test:  ## Run all tests
	cd /var/www/fina-connect && venv/bin/python manage.py test --verbosity=2

lint:  ## Run ruff linter
	cd /var/www/fina-connect && venv/bin/ruff check .

migrate:  ## Run migrations
	cd /var/www/fina-connect && venv/bin/python manage.py migrate

deploy:  ## Deploy to production (restart gunicorn)
	cd /var/www/fina-connect && git pull origin main && venv/bin/pip install -r requirements.txt --quiet && venv/bin/python manage.py migrate --noinput && venv/bin/python manage.py collectstatic --noinput && systemctl restart gunicorn 2>/dev/null || (pkill -HUP -f "gunicorn.*core.wsgi")

clean:  ## Remove .pyc and __pycache__
	find /var/www/fina-connect -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; find /var/www/fina-connect -name "*.pyc" -delete 2>/dev/null

reminders:  ## Send appointment reminders manually
	cd /var/www/fina-connect && venv/bin/python manage.py send_reminders

shell:  ## Django shell
	cd /var/www/fina-connect && venv/bin/python manage.py shell


# ── Code Quality ─────────────────────────────────────────────

lint-fix:  ## Auto-fix lint issues
	cd /var/www/fina-connect && venv/bin/ruff check --fix --exclude venv,tools_archive,migrations .

format:  ## Format code with ruff
	cd /var/www/fina-connect && venv/bin/ruff format --exclude venv,tools_archive,migrations .

quality:  ## Full quality check (lint + test)
	@echo "── Lint ──" && cd /var/www/fina-connect && venv/bin/ruff check --exclude venv,tools_archive,migrations .
	@echo "── Tests ──" && cd /var/www/fina-connect && venv/bin/python manage.py test --keepdb

pre-commit-install:  ## Install pre-commit hooks
	cd /var/www/fina-connect && venv/bin/pip install pre-commit && venv/bin/pre-commit install
