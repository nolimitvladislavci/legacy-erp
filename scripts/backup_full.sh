#!/bin/bash
set -euo pipefail
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/www/fina-connect/backups/migration_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

echo "=== LIMIT Connect Full Backup ==="
echo "Timestamp: ${TIMESTAMP}"

echo "[1/5] PostgreSQL dump..."
pg_dump -U viskovic_user -h localhost fina_erp --format=custom --compress=6 -f "${BACKUP_DIR}/fina_erp.dump" 2>/dev/null && echo "  OK" || echo "  FAIL"

echo "[2/5] Certifikati..."
tar czf "${BACKUP_DIR}/certs.tar.gz" -C / etc/limit-connect/certs/ 2>/dev/null && echo "  OK" || echo "  SKIP"

echo "[3/5] MinIO S3 data..."
tar czf "${BACKUP_DIR}/minio-data.tar.gz" -C /var/www/fina-connect minio-data/ 2>/dev/null && echo "  OK" || echo "  SKIP"

echo "[4/5] Media..."
tar czf "${BACKUP_DIR}/media.tar.gz" -C /var/www/fina-connect media/ --exclude="media/cache" 2>/dev/null && echo "  OK" || echo "  SKIP"

echo "[5/5] Config..."
mkdir -p "${BACKUP_DIR}/config"
cp /var/www/fina-connect/core/settings.py "${BACKUP_DIR}/config/" 2>/dev/null || true
cp /var/www/fina-connect/docker-compose.infra.yml "${BACKUP_DIR}/config/" 2>/dev/null || true
cp /etc/systemd/system/gunicorn-fina.service "${BACKUP_DIR}/config/" 2>/dev/null || true
cp /etc/systemd/system/celery-*.service "${BACKUP_DIR}/config/" 2>/dev/null || true
cp /etc/nginx/sites-enabled/fina* "${BACKUP_DIR}/config/" 2>/dev/null || true

TOTAL=$(du -sh "${BACKUP_DIR}" | cut -f1)
echo ""
echo "=== DONE: ${BACKUP_DIR} (${TOTAL}) ==="
echo "scp -r ${BACKUP_DIR} root@NEW_SERVER:/tmp/migration/"
