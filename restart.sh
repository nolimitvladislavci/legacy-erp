#!/bin/bash
set -e
echo "=== LIMIT CONNECT — Restart ==="
echo "$(date)"
echo ""

cd /var/www/fina-connect

echo "[1/6] Collecting static..."
venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -2

echo "[2/6] Migrations..."
venv/bin/python manage.py migrate --noinput 2>&1 | tail -3

echo "[3/6] Django verify..."
venv/bin/python -c "
import os, django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
django.setup()
from pos.signals import auto_book_pos_session
from invoicing.signals import auto_book_invoice
from payments.integrations import handle_payment_completed
from core.views_search import global_search
print('  All modules OK')
"

echo "[4/6] Restarting gunicorn..."
systemctl restart gunicorn-fina && echo "  Gunicorn: OK"

echo "[5/6] Restarting celery..."
systemctl restart celery-worker celery-beat && echo "  Celery: OK"

echo "[6/6] Reloading nginx..."
nginx -t 2>&1 && systemctl reload nginx && echo "  Nginx: OK"

sleep 2
echo ""
echo "=== STATUS ==="
echo "Gunicorn:  $(systemctl is-active gunicorn-fina)"
echo "Celery-W:  $(systemctl is-active celery-worker)"
echo "Celery-B:  $(systemctl is-active celery-beat)"
echo "Nginx:     $(systemctl is-active nginx)"
echo "Redis:     $(systemctl is-active redis)"
echo "PostgreSQL: $(systemctl is-active postgresql)"
echo ""
echo "HTTP: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health/ 2>/dev/null)"
echo ""
echo "=== DONE — $(date) ==="
