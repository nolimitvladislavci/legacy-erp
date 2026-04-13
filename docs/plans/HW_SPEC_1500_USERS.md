# HW_SPEC_1500_USERS — Novo gnijezdo specifikacija
# Datum: 2026-03-25 | Autor: Sonnet
# Trenutni server: 37.27.248.86 (Hetzner) — 4 CPU, 8GB RAM, 150GB SSD
# Cilj: 1.500 aktivnih korisnika, 150 istovremenih blagajni

---

## Trenutno stanje — bottleneck analiza

| Resurs | Sada | Limit za 1.500 korisnika |
|--------|------|--------------------------|
| CPU | 4 vCPU | Minimum 8 vCPU |
| RAM | 8 GB (4 GB dostupno) | Minimum 16 GB |
| Disk | 150 GB (35% korišteno = 52 GB) | 300 GB SSD NVMe |
| Gunicorn workers | 3 | 9-12 (formula: 2×CPU+1) |
| DB size | 834 MB | Rast ~100 MB/mj = 2 GB za godinu |
| Postgres connections | 5 aktivnih | Pgbouncer obavezan pri 150+ |

**Kritični bottleneck:** 3 Gunicorn workera = max 3 istovremena zahtjeva.
150 blagajni × prosječno 0.5 req/s = 75 req/s. Sadašnji setup puca na ~10 req/s.

---

## Preporučena konfiguracija — Novo gnijezdo

### Opcija A — Hetzner Dedicated (preporučeno)
```
Model:    AX52 ili CPX51
CPU:      AMD Ryzen 9 5900X (12 jezgri / 24 threada)
RAM:      64 GB DDR4 ECC
Disk:     2× 512 GB NVMe SSD (RAID 1)
Network:  1 Gbps uplink
Lokacija: Falkenstein (DE) — blizu HR, GDPR EU
Cijena:   ~85 EUR/mj (dedicated) ili ~35 EUR/mj (CPX51 VPS)
```

### Opcija B — Hetzner CPX51 VPS (brža migracija, jeftinija)
```
CPU:      16 vCPU AMD
RAM:      32 GB
Disk:     360 GB SSD
Cijena:   35,77 EUR/mj
Skaliranje: upgrade u 1 klik ako treba više
```

**Preporuka: Opcija B za sada (CPX51).** Kada prođeš 500 klijenata → dedicated.

---

## Stack konfiguracija za 1.500 korisnika

### Gunicorn
```bash
# /etc/systemd/system/gunicorn-fina.service
ExecStart=.../gunicorn core.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 17 \           # 2×8CPU+1
  --worker-class gthread \  # threading, bolji I/O
  --threads 4 \             # 4 threada po workeru = 68 concurrent
  --timeout 60 \            # smanjiti sa 300 — ubija zombie workere brže
  --max-requests 2000 \
  --max-requests-jitter 100 \
  --graceful-timeout 30 \
  --preload
```

### PgBouncer — OBAVEZAN
```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
fina_connect = host=127.0.0.1 port=5432 dbname=fina_connect

[pgbouncer]
pool_mode = transaction    # transakcijski pooling — najmanji footprint
max_client_conn = 500      # max 500 klijenata čeka
default_pool_size = 25     # 25 realnih Postgres konekcija
min_pool_size = 5
reserve_pool_size = 10
```

### PostgreSQL tuning (`/etc/postgresql/16/main/postgresql.conf`)
```
max_connections = 50        # PgBouncer upravljna, ne direktno
shared_buffers = 4GB        # 25% RAM-a
effective_cache_size = 12GB # 75% RAM-a
work_mem = 64MB
maintenance_work_mem = 1GB
wal_buffers = 64MB
checkpoint_completion_target = 0.9
random_page_cost = 1.1      # SSD
effective_io_concurrency = 200
```

### Redis
```
# /etc/redis/redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""                     # ne snimaj na disk — Celery je ephemeral
```

### Nginx
```nginx
worker_processes auto;       # = broj CPU jezgri
worker_connections 2048;

upstream gunicorn {
    server 127.0.0.1:8000;
    keepalive 64;
}

# Rate limiting za fiskalizaciju (sprečava DDoS na FINA)
limit_req_zone $binary_remote_addr zone=fiscal:10m rate=10r/s;
```

### Celery
```bash
# Povećaj workere za Celery (sada vjerojatno 2-4)
celery -A core worker --concurrency=8 --max-tasks-per-child=500
celery -A core beat
```

---

## 0-Downtime migracija — protokol za 1.4.

### Pripreme (danas-sutra)
1. Naruči CPX51 na Hetzner — IP adresa za DNS
2. `git clone` na novi server, venv, migracije
3. Postavi PgBouncer + nova Postgres konfiguracija
4. Testiraj: `ab -n 1000 -c 50 https://novo-ip/health/` — load test

### Migracija (1.4. u 03:00 — najmanji promet)
```bash
# 1. Stari server — READ ONLY mode (1 minuta)
# /etc/nginx/sites-enabled: dodaj maintenance.html za POST zahtjeve

# 2. pg_dump + prenos
pg_dump -Fc fina_connect > /tmp/fina_backup.dump
rsync -avz /tmp/fina_backup.dump novi_server:/tmp/

# 3. Novi server — restore
pg_restore -d fina_connect /tmp/fina_backup.dump

# 4. rsync media/minio
rsync -avz /var/www/fina-connect/media/ novi_server:/var/www/fina-connect/media/
rsync -avz /var/www/fina-connect/minio-data/ novi_server:/var/www/fina-connect/minio-data/

# 5. DNS switch (TTL mora biti na 60s 24h unaprijed)
# A record: limit-connect.com → novi IP

# 6. Provjera
curl https://limit-connect.com/health/
# Očekivani downtime: 5-15 minuta
```

### Post-migracija (1.4. u 04:00)
- Monitoring: `htop`, `pg_stat_activity`, nginx access log
- Gunicorn logs: `journalctl -u gunicorn-fina -f`
- Smoke test: login, kreiraj račun, fiskaliziraj

---

## Troškovi

| Stavka | Sada | Novo |
|--------|------|------|
| Server (Hetzner CPX51) | ~20 EUR/mj | 35 EUR/mj |
| Domene (sve) | ≈10 EUR/mj | 10 EUR/mj |
| MinIO storage | 0 (lokalno) | 0 (lokalno) |
| **Ukupno** | **~30 EUR/mj** | **~45 EUR/mj** |

Pri 100 klijenata × 9,99 EUR = 999 EUR prihoda → infrastruktura je 4,5% troška. ✅

---

## Kada upgrade na dedicated?

Trigger: `htop` pokazuje CPU sustained > 70% kroz 1 sat.
Ili: broj aktivnih korisnika > 800.
Hetzner dedicated AX52: ~85 EUR/mj, migracija < 2h.
