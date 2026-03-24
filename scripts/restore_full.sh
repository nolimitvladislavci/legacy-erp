#!/bin/bash
set -euo pipefail
BACKUP_DIR="${1:?Usage: restore_full.sh /path/to/migration_XXXXXX}"

echo "=== LIMIT Connect Full Restore ==="
echo "Source: ${BACKUP_DIR}"

echo "[1/5] PostgreSQL restore..."
if [ -f "${BACKUP_DIR}/fina_erp.dump" ]; then
  sudo -u postgres dropdb --if-exists fina_erp
  sudo -u postgres createdb fina_erp -O viskovic_user
  sudo -u postgres pg_restore -d fina_erp "${BACKUP_DIR}/fina_erp.dump" --no-owner --role=viskovic_user 2>/dev/null && echo "  OK" || echo "  WARNINGS (normal)"
fi

echo "[2/5] Certifikati..."
if [ -f "${BACKUP_DIR}/certs.tar.gz" ]; then
  tar xzf "${BACKUP_DIR}/certs.tar.gz" -C / && echo "  OK" || echo "  FAIL"
fi

echo "[3/5] MinIO S3 data..."
if [ -f "${BACKUP_DIR}/minio-data.tar.gz" ]; then
  tar xzf "${BACKUP_DIR}/minio-data.tar.gz" -C /var/www/fina-connect/ && echo "  OK" || echo "  FAIL"
fi

echo "[4/5] Media..."
if [ -f "${BACKUP_DIR}/media.tar.gz" ]; then
  tar xzf "${BACKUP_DIR}/media.tar.gz" -C /var/www/fina-connect/ && echo "  OK" || echo "  FAIL"
fi

echo "[5/5] Migracije..."
cd /var/www/fina-connect && . venv/bin/activate && python manage.py migrate --noinput 2>/dev/null && echo "  OK" || echo "  FAIL"

echo ""
echo "=== RESTORE DONE ==="
echo "Next: docker compose -f docker-compose.infra.yml up -d"
echo "      systemctl restart gunicorn-fina celery-worker celery-beat"
