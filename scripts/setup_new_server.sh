#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# LIMIT Connect — novi server setup (Hetzner CCX33)
# Pokreni kao root na svježem Ubuntu 24.04
# Usage: bash setup_new_server.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

echo "═══════════════════════════════════════════════════"
echo "  LIMIT Connect — Server Setup (CCX33)"
echo "  $(date '+%d.%m.%Y %H:%M')"
echo "═══════════════════════════════════════════════════"

# ── 1. System packages ────────────────────────────────────────
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
  python3.12 python3.12-venv python3-pip \
  postgresql-16 postgresql-client-16 \
  nginx redis-server \
  git build-essential libpq-dev \
  mdbtools \
  certbot python3-certbot-nginx \
  htop iotop nethogs \
  ufw fail2ban

# ── 2. PostgreSQL tuning (CCX33: 8 CPU, 16GB RAM) ────────────
echo "[2/8] Configuring PostgreSQL for CCX33..."
cat >> /etc/postgresql/16/main/postgresql.conf << 'PG'

# LIMIT Connect CCX33 tuning
shared_buffers = 4GB
work_mem = 128MB
effective_cache_size = 12GB
random_page_cost = 1.1
effective_io_concurrency = 200
max_connections = 200
wal_buffers = 64MB
checkpoint_completion_target = 0.9
log_min_duration_statement = 500
PG

systemctl restart postgresql

# Create DB and user
sudo -u postgres psql << 'SQL'
CREATE USER limitconnect WITH PASSWORD 'CHANGE_ME_BEFORE_DEPLOY';
CREATE DATABASE fina_erp OWNER limitconnect ENCODING 'UTF8' LC_COLLATE 'hr_HR.UTF-8' LC_CTYPE 'hr_HR.UTF-8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE fina_erp TO limitconnect;
SQL

# ── 3. Redis config ───────────────────────────────────────────
echo "[3/8] Configuring Redis..."
cat >> /etc/redis/redis.conf << 'REDIS'

# LIMIT Connect
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
REDIS
systemctl restart redis-server

# ── 4. Application directory ──────────────────────────────────
echo "[4/8] Setting up application..."
mkdir -p /var/www/fina-connect
cd /var/www/fina-connect

# Clone repo (replace with your actual repo URL)
# git clone git@github.com:limit-connect/fina-connect.git .

python3.12 -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt
# python manage.py migrate
# python manage.py warm_cache
# python manage.py collectstatic --noinput

# ── 5. Gunicorn systemd ──────────────────────────────────────
echo "[5/8] Configuring Gunicorn..."
cat > /etc/systemd/system/gunicorn-fina.service << 'GUNICORN'
[Unit]
Description=LIMIT Connect Gunicorn
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/fina-connect
Environment="DJANGO_SETTINGS_MODULE=core.settings"
ExecStart=/var/www/fina-connect/venv/bin/gunicorn core.wsgi:application \
  --bind unix:/run/gunicorn-fina.sock \
  --workers 17 \
  --worker-class gthread \
  --threads 2 \
  --timeout 120 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --access-logfile /var/www/fina-connect/logs/gunicorn-access.log \
  --error-logfile /var/www/fina-connect/logs/gunicorn-error.log
ExecStartPost=/var/www/fina-connect/venv/bin/python /var/www/fina-connect/manage.py warm_cache
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
GUNICORN

# ── 6. Celery systemd ────────────────────────────────────────
echo "[6/8] Configuring Celery..."
cat > /etc/systemd/system/celery-worker.service << 'CELERY'
[Unit]
Description=LIMIT Connect Celery Worker
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/fina-connect
Environment="DJANGO_SETTINGS_MODULE=core.settings"
ExecStart=/var/www/fina-connect/venv/bin/celery -A core worker \
  --loglevel=info \
  --concurrency=4 \
  -Q default,celery
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
CELERY

cat > /etc/systemd/system/celery-beat.service << 'BEAT'
[Unit]
Description=LIMIT Connect Celery Beat
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/fina-connect
Environment="DJANGO_SETTINGS_MODULE=core.settings"
ExecStart=/var/www/fina-connect/venv/bin/celery -A core beat \
  --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
BEAT

# ── 7. Nginx ─────────────────────────────────────────────────
echo "[7/8] Configuring Nginx..."
cat > /etc/nginx/sites-available/limit-connect << 'NGINX'
server {
    listen 80;
    server_name limit-connect.com www.limit-connect.com;

    location / {
        proxy_pass http://unix:/run/gunicorn-fina.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 50M;
    }

    location /static/ {
        alias /var/www/fina-connect/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/fina-connect/media/;
        expires 7d;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/limit-connect /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# ── 8. Firewall + security ───────────────────────────────────
echo "[8/8] Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# ── Done ──────────────────────────────────────────────────────
mkdir -p /var/www/fina-connect/logs
mkdir -p /var/www/fina-connect/exports

systemctl daemon-reload
systemctl enable gunicorn-fina celery-worker celery-beat nginx

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Server setup COMPLETE"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Sljedeci koraci:"
echo "  1. Promijeni PostgreSQL password u setup scripti"
echo "  2. Deploy kod (git clone ili rsync)"
echo "  3. pip install -r requirements.txt"
echo "  4. python manage.py migrate"
echo "  5. python manage.py collectstatic"
echo "  6. certbot --nginx -d limit-connect.com"
echo "  7. systemctl start gunicorn-fina celery-worker celery-beat"
echo "  8. Pokreni load test"
echo ""
