# CC_TASK_SERVER_MIGRACIJA_3NODE.md
# Za: CC Code #2 (Track B, B1)
# Datum: 30.03.2026.
# Rok: 08.04.2026.
# Prioritet: P0 — infrastrukturalni preduvjet za sve ostalo
#
# KONTEKST:
# Tri servera zakupljuju Ivan, Marija i Kruljac (po ~131 EUR/mj)
# Trenutno: sve na jednom serveru (Hetzner CCX13, IP: 37.27.248.86)
# Ciljano: 3 odvojena sloja
#
# VAŽNO: Zero downtime migracija. Stari server ostaje aktivan dok
# novi nije 100% verifikiran. DNS switch = zadnji korak.

---

## ARHITEKTURA

```
SERVER 1 — Ivan (37.27.248.86, postojeći)
  Ostaje kao: Redis + Celery workers + cron backup
  NE gasi se — postaje cache/worker layer

SERVER 2 — Marija (novi, CCX33 8vCPU/32GB)
  Postaje: Nginx + Gunicorn (Django app)
  Domena: limit-connect.com → ovaj server

SERVER 3 — Kruljac (novi, CCX33 8vCPU/32GB)  
  Postaje: PostgreSQL 16 + PgBouncer
  Pristupačan samo interno (ne javno)
```

---

## KORAK 1 — Priprema (CC radi ODMAH, čeka servere)

### Kreiraj Ansible strukturu

```bash
mkdir -p /var/www/fina-connect/ansible/{inventory,playbooks,roles}

# Kreiraj inventory template (Ivan popunjava IP adrese kad dobije servere)
cat > /var/www/fina-connect/ansible/inventory/production.ini << 'INI'
[app_servers]
server2 ansible_host=SERVER2_IP ansible_user=root

[database_servers]
server3 ansible_host=SERVER3_IP ansible_user=root

[cache_servers]
server1 ansible_host=37.27.248.86 ansible_user=root

[all:vars]
ansible_python_interpreter=/usr/bin/python3
domain=limit-connect.com
app_dir=/var/www/fina-connect
db_name=fina_erp
db_user=viskovic_user
INI
```

### Kreiraj .env.production template

```bash
cat > /var/www/fina-connect/.env.production.template << 'ENV'
# Server 2 (App) — popunjava se s pravim IP-ovima
DB_HOST=SERVER3_IP
DB_PORT=5432
DB_NAME=fina_erp
DB_USER=viskovic_user
DB_PASSWORD=Viskovic2026

REDIS_URL=redis://SERVER1_IP:6379/0
CELERY_BROKER_URL=redis://SERVER1_IP:6379/0

ALLOWED_HOSTS=limit-connect.com,www.limit-connect.com,SERVER2_IP
SITE_URL=https://limit-connect.com

# Ostalo ostaje isto
SECRET_KEY=<existing>
ENV
```

---

## KORAK 2 — Ansible Playbooks

### 2a. setup_db.yml (Server 3 — PostgreSQL)

```yaml
# ansible/playbooks/setup_db.yml
---
- name: Setup PostgreSQL Database Server
  hosts: database_servers
  become: yes
  
  vars:
    pg_version: "16"
    pg_shared_buffers: "8GB"
    pg_work_mem: "128MB"
    pg_max_connections: "100"
    
  tasks:
    - name: Install PostgreSQL
      apt:
        name:
          - postgresql-16
          - postgresql-client-16
          - pgbouncer
          - python3-psycopg2
        state: present
        update_cache: yes

    - name: Configure PostgreSQL
      template:
        src: templates/postgresql.conf.j2
        dest: /etc/postgresql/16/main/postgresql.conf
      notify: restart postgresql

    - name: Configure pg_hba (allow app server)
      lineinfile:
        path: /etc/postgresql/16/main/pg_hba.conf
        line: "host fina_erp viskovic_user {{ hostvars['server2']['ansible_host'] }}/32 scram-sha-256"
      notify: restart postgresql

    - name: Configure PgBouncer
      template:
        src: templates/pgbouncer.ini.j2
        dest: /etc/pgbouncer/pgbouncer.ini
      notify: restart pgbouncer

    - name: Create database user
      postgresql_user:
        name: "{{ db_user }}"
        password: "{{ db_password }}"
        role_attr_flags: CREATEDB
      become_user: postgres

    - name: Create database
      postgresql_db:
        name: "{{ db_name }}"
        owner: "{{ db_user }}"
      become_user: postgres

    - name: Configure firewall — only allow app server
      ufw:
        rule: allow
        port: 6432  # PgBouncer
        src: "{{ hostvars['server2']['ansible_host'] }}"

  handlers:
    - name: restart postgresql
      service: name=postgresql state=restarted
    - name: restart pgbouncer
      service: name=pgbouncer state=restarted
```

### 2b. setup_app.yml (Server 2 — Django)

```yaml
# ansible/playbooks/setup_app.yml
---
- name: Setup Application Server
  hosts: app_servers
  become: yes
  
  tasks:
    - name: Install dependencies
      apt:
        name:
          - python3.12
          - python3.12-venv
          - nginx
          - git
          - build-essential
          - libpq-dev
          - gettext
        state: present
        update_cache: yes

    - name: Create app user
      user:
        name: www-data
        system: yes

    - name: Clone repository
      git:
        repo: "git@github.com:YOUR_REPO/fina-connect.git"
        dest: "{{ app_dir }}"
        version: master
        force: yes
      # Alternativa: rsync iz Server 1

    - name: Create virtualenv and install packages
      pip:
        requirements: "{{ app_dir }}/requirements.txt"
        virtualenv: "{{ app_dir }}/venv"
        virtualenv_command: python3.12 -m venv

    - name: Copy production .env
      template:
        src: templates/env.production.j2
        dest: "{{ app_dir }}/.env"
        owner: www-data
        mode: '0600'

    - name: Run migrations
      django_manage:
        command: migrate
        app_path: "{{ app_dir }}"
        virtualenv: "{{ app_dir }}/venv"
        settings: core.settings

    - name: Collect static files
      django_manage:
        command: collectstatic --noinput
        app_path: "{{ app_dir }}"
        virtualenv: "{{ app_dir }}/venv"

    - name: Configure Gunicorn systemd service
      template:
        src: templates/gunicorn.service.j2
        dest: /etc/systemd/system/gunicorn-fina.service
      notify:
        - reload systemd
        - restart gunicorn

    - name: Configure Nginx
      template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-available/limit-connect
      notify: reload nginx

    - name: Enable nginx site
      file:
        src: /etc/nginx/sites-available/limit-connect
        dest: /etc/nginx/sites-enabled/limit-connect
        state: link

  handlers:
    - name: reload systemd
      systemd: daemon_reload=yes
    - name: restart gunicorn
      service: name=gunicorn-fina state=restarted
    - name: reload nginx
      service: name=nginx state=reloaded
```

### 2c. setup_cache.yml (Server 1 — Redis + Celery)

```yaml
# ansible/playbooks/setup_cache.yml
---
- name: Configure Cache/Worker Server (Server 1 - existing)
  hosts: cache_servers
  become: yes

  tasks:
    - name: Configure Redis to listen on all interfaces
      lineinfile:
        path: /etc/redis/redis.conf
        regexp: '^bind '
        line: 'bind 0.0.0.0'
      notify: restart redis

    - name: Set Redis password
      lineinfile:
        path: /etc/redis/redis.conf
        regexp: '^# requirepass'
        line: 'requirepass {{ redis_password }}'
      notify: restart redis

    - name: Allow Redis from app server only
      ufw:
        rule: allow
        port: 6379
        src: "{{ hostvars['server2']['ansible_host'] }}"

    - name: Update Celery to point to new DB
      template:
        src: templates/celery.env.j2
        dest: /etc/environment
      notify: restart celery

  handlers:
    - name: restart redis
      service: name=redis state=restarted
    - name: restart celery
      service: name=celery-worker state=restarted
```

---

## KORAK 3 — Migracija baze (Zero Downtime)

```bash
#!/bin/bash
# zero_downtime_db_migration.sh
# Pokreći na Server 1, NAKON što je Server 3 konfiguriran

set -e

SERVER3_IP="<Server3_IP>"
DB_NAME="fina_erp"
DB_USER="viskovic_user"

echo "=== Faza 1: Dump baze s Server 1 ==="
PGPASSWORD=Viskovic2026 pg_dump \
  -U $DB_USER \
  -h 127.0.0.1 \
  -d $DB_NAME \
  -F c \
  -f /tmp/migration_$(date +%Y%m%d_%H%M).dump

echo "Dump veličina: $(du -sh /tmp/migration_*.dump | tail -1)"

echo "=== Faza 2: Transfer na Server 3 ==="
scp /tmp/migration_*.dump root@$SERVER3_IP:/tmp/

echo "=== Faza 3: Restore na Server 3 ==="
ssh root@$SERVER3_IP << 'REMOTE'
PGPASSWORD=Viskovic2026 pg_restore \
  -U viskovic_user \
  -h 127.0.0.1 \
  -d fina_erp \
  -F c \
  --no-owner \
  /tmp/migration_*.dump
echo "Restore OK"
REMOTE

echo "=== Faza 4: Verifikacija ==="
ssh root@$SERVER3_IP "PGPASSWORD=Viskovic2026 psql -U viskovic_user -h 127.0.0.1 -d fina_erp -c 'SELECT count(*) FROM invoicing_invoice;'"

echo "=== Faza 5: Prebaci .env na Server 2 ==="
# Samo promijeni DB_HOST
ssh root@<Server2_IP> "sed -i 's/DB_HOST=127.0.0.1/DB_HOST=$SERVER3_IP/' /var/www/fina-connect/.env"
ssh root@<Server2_IP> "systemctl restart gunicorn-fina"

echo "=== GOTOVO — Verifikacija ==="
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/health/
```

---

## KORAK 4 — Verifikacija po serverima

```bash
# Server 2 (App) — provjeri
curl -s https://limit-connect.com/health/ | python3 -m json.tool
curl -s -o /dev/null -w "%{time_total}s" https://limit-connect.com/hr/login/

# Server 3 (DB) — provjeri
PGPASSWORD=Viskovic2026 psql -U viskovic_user -h <Server3_IP> -p 6432 -d fina_erp \
  -c "SELECT count(*) FROM invoicing_invoice; SELECT count(*) FROM partners_partner;"

# Server 1 (Cache) — provjeri  
redis-cli -h <Server1_IP> -a <password> ping
redis-cli -h <Server1_IP> -a <password> info memory | grep used_memory_human

# Celery workers — provjeri
celery -A core inspect active --timeout=5
```

---

## KORAK 5 — Commit

```bash
git add ansible/ .env.production.template
git commit -m "infra: Ansible 3-node setup — Server 2 (app) + Server 3 (db) + Server 1 (cache)

Ansible playbooks:
  setup_db.yml    — PostgreSQL 16 + PgBouncer na Server 3
  setup_app.yml   — Nginx + Gunicorn na Server 2
  setup_cache.yml — Redis + Celery na Server 1

zero_downtime_db_migration.sh:
  pg_dump → scp → pg_restore → .env update → restart

Zero downtime: stari server ostaje live dok novi nije 100% OK
DNS switch: zadnji korak, u 5 minuta

Kapacitet: 3.000+ firmi, 720 istovremenih korisnika, 50% headroom"
```

---

## NAPOMENE

1. Ivan popunjava SERVER2_IP i SERVER3_IP čim dobije servere (01.04.)
2. Redis password — postavi u Ansible vault (ne hardkodiraj)
3. SSH ključevi — postaviti PRIJE pokretanja playbooka
4. DB migracija se radi u 04:00 (minimalan traffic)
5. DNS TTL: smanjiti na 300s dan prije migracije (za brzi fallback)
6. Stari server (Server 1) ostaje 30 dana kao backup → backup cron nastavlja raditi

---

## STATUS: ČEKA IP ADRESE NOVIH SERVERA
## Narudžba: Ivan, 01.04.2026.
## Deployment: 08.04.2026.
