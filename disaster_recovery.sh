#!/bin/bash
# =============================================================================
# disaster_recovery.sh — Restore LIMIT Connect ERP na praznom serveru
# =============================================================================
# USAGE:
#   1. Kupi novi VPS (Ubuntu 22/24, 4GB RAM, 60GB disk)
#   2. SSH na novi server kao root
#   3. wget https://raw.githubusercontent.com/.../disaster_recovery.sh
#      ILI copy-paste ovaj fajl
#   4. chmod +x disaster_recovery.sh && ./disaster_recovery.sh
#   5. Promijeni DNS A record za limit-connect.com na novu IP
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
step() { echo -e "${GREEN}[$(date '+%H:%M:%S')] STEP $1: $2${NC}"; }
warn() { echo -e "${YELLOW}[!] $1${NC}"; }

B2_KEY_ID="0037b5f2dbe58630000000001"
B2_APP_KEY="K003v4ZIC18gc+tpUi9xhJmfvwEe/N0"
B2_BUCKET="limit-connect-arhiva"

echo "============================================"
echo " LIMIT Connect ERP — Disaster Recovery"
echo " $(date)"
echo "============================================"
echo ""

# ── STEP 1: System packages ──
step 1 "Installing system packages..."
apt update -qq
apt install -y -qq postgresql postgresql-contrib nginx redis-server python3 python3-pip python3-venv \
    git supervisor certbot python3-certbot-nginx fail2ban mdbtools \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev \
    libpq-dev build-essential > /dev/null 2>&1

# ── STEP 2: Install B2 CLI ──
step 2 "Installing B2 CLI..."
pip3 install --break-system-packages b2 > /dev/null 2>&1
b2 account authorize "$B2_KEY_ID" "$B2_APP_KEY" > /dev/null 2>&1

# ── STEP 3: Download latest backup ──
step 3 "Downloading latest backup from Backblaze B2..."
mkdir -p /tmp/restore

# Find latest DB backup
LATEST_DB=$(b2 ls "$B2_BUCKET" backups/db/ 2>/dev/null | tail -1)
if [ -z "$LATEST_DB" ]; then
    echo -e "${RED}ERROR: No DB backup found in B2!${NC}"
    exit 1
fi
echo "  DB: $LATEST_DB"
b2 file download "b2://$B2_BUCKET/$LATEST_DB" /tmp/restore/db.sql.gz

# Latest media
LATEST_MEDIA=$(b2 ls "$B2_BUCKET" backups/media/ 2>/dev/null | tail -1)
if [ -n "$LATEST_MEDIA" ]; then
    echo "  Media: $LATEST_MEDIA"
    b2 file download "b2://$B2_BUCKET/$LATEST_MEDIA" /tmp/restore/media.tar.gz
fi

# Latest secrets
LATEST_SECRETS=$(b2 ls "$B2_BUCKET" backups/secrets/ 2>/dev/null | tail -1)
if [ -n "$LATEST_SECRETS" ]; then
    echo "  Secrets: $LATEST_SECRETS"
    b2 file download "b2://$B2_BUCKET/$LATEST_SECRETS" /tmp/restore/secrets.tar.gz
fi

# ── STEP 4: Setup PostgreSQL ──
step 4 "Setting up PostgreSQL..."
sudo -u postgres psql -c "CREATE USER viskovic_user WITH PASSWORD 'Viskovic123!';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE postgres OWNER viskovic_user;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE postgres TO viskovic_user;" 2>/dev/null || true

# Restore DB
echo "  Restoring database..."
gunzip -c /tmp/restore/db.sql.gz | sudo -u postgres psql postgres > /dev/null 2>&1
echo "  Database restored!"

# ── STEP 5: Setup application ──
step 5 "Setting up application..."
mkdir -p /var/www/fina-connect
cd /var/www/fina-connect

# If git repo exists, clone it. Otherwise, we rely on backup.
if [ ! -d ".git" ]; then
    warn "No git repo found. Application code must be restored from backup or git clone."
    warn "Run: git clone <your-repo-url> /var/www/fina-connect"
fi

# Restore secrets
if [ -f /tmp/restore/secrets.tar.gz ]; then
    echo "  Restoring secrets (.env, certs, nginx configs)..."
    tar xzf /tmp/restore/secrets.tar.gz -C / 2>/dev/null || true
fi

# Restore media
if [ -f /tmp/restore/media.tar.gz ]; then
    echo "  Restoring media files..."
    tar xzf /tmp/restore/media.tar.gz -C /var/www/fina-connect/ 2>/dev/null || true
fi

# ── STEP 6: Python venv ──
step 6 "Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1 || warn "requirements.txt not found"

# ── STEP 7: Django setup ──
step 7 "Running Django migrations..."
python manage.py migrate --noinput 2>/dev/null || warn "Migrations failed (DB already has tables)"
python manage.py collectstatic --noinput > /dev/null 2>&1 || true

# ── STEP 8: Permissions ──
step 8 "Setting permissions..."
chown -R www-data:www-data /var/www/fina-connect
mkdir -p /var/run/celery
chown www-data:www-data /var/run/celery

# ── STEP 9: Nginx ──
step 9 "Configuring Nginx..."
if [ -f /etc/nginx/sites-enabled/limit-connect ]; then
    echo "  Nginx config restored from backup"
else
    warn "Nginx config not found! You need to restore it manually."
fi
nginx -t 2>/dev/null && systemctl restart nginx

# ── STEP 10: Systemd services ──
step 10 "Starting services..."
systemctl daemon-reload

# Check if service files exist (restored from backup)
for svc in gunicorn-fina celery-worker celery-beat; do
    if [ -f "/etc/systemd/system/${svc}.service" ]; then
        systemctl enable "$svc"
        systemctl start "$svc"
        echo "  $svc: started"
    else
        warn "$svc.service not found!"
    fi
done

# Redis
systemctl enable redis-server
systemctl start redis-server

# ── STEP 11: SSL (if DNS already points here) ──
step 11 "SSL certificate..."
warn "Run manually after DNS is updated:"
warn "  certbot --nginx -d limit-connect.com -d www.limit-connect.com"

# ── STEP 12: Verify ──
step 12 "Verification..."
echo ""
echo "  PostgreSQL: $(systemctl is-active postgresql)"
echo "  Redis:      $(systemctl is-active redis-server)"
echo "  Nginx:      $(systemctl is-active nginx)"
echo "  Gunicorn:   $(systemctl is-active gunicorn-fina 2>/dev/null || echo 'not started')"
echo "  Celery:     $(systemctl is-active celery-worker 2>/dev/null || echo 'not started')"
echo ""

# Test Django
cd /var/www/fina-connect
source venv/bin/activate
python manage.py shell -c "
from companies.models import Company
from invoicing.models import Invoice
from konto.models import JournalEntry
print(f'  Companies: {Company.objects.count()}')
print(f'  Invoices:  {Invoice.objects.count()}')
print(f'  Konto:     {JournalEntry.objects.count()}')
" 2>/dev/null || warn "Django check failed"

echo ""
echo "============================================"
echo -e " ${GREEN}DISASTER RECOVERY COMPLETE${NC}"
echo " Next steps:"
echo "   1. Update DNS A record to this server IP"
echo "   2. Run: certbot --nginx -d limit-connect.com"
echo "   3. Test: curl https://limit-connect.com/"
echo "============================================"

# Cleanup
rm -rf /tmp/restore
