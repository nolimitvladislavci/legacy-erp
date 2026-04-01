# CC_TASK_USKLADENJE_B — Produkcijska priprema (serveri, cache, audit)
**Dodjeljeno:** CC Code Instance B
**Ne dira:** synesis_compare.py, invoicing/, konto/ (to je A)
**Deadline:** 12.04.2026 (final load test 12.04., GO/NO-GO 15.04.)
**Status:** TODO

---

## KONTEKST — što čeka do produkcije

```
15.04. → Trio serveri LIVE, prazne baze
01.05. → Kampanje, 100 firmi
Blokeri:
  - Redis hit rate 52% (treba >90%)
  - Audit log 641MB = 74% baze (eksplodirat će)
  - Hetzner CCX33 nije naručen (Ivan naručuje do 05.04.)
  - Load test samo na starom serveru
```

---

## ZADATAK B1 — Redis cache warming (hit rate 52% → >90%)

### Dijagnoza:
```bash
redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses|hit_rate"
redis-cli INFO keyspace
redis-cli --scan --pattern "*" | head -20
```

### Zašto je 52%:
Svaki restart Gunicorna praznio Redis cache. Nema cache warming na startu.

### Rješenje — cache warming script:
Kreirati `core/management/commands/warm_cache.py`:

```python
"""
Pokreće se automatski nakon gunicorn restart-a.
Predpuni Redis s najčešće dohvaćanim podacima.
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache

class Command(BaseCommand):
    help = 'Predpuni Redis cache za produkciju'

    def handle(self, *args, **options):
        from companies.models import Company
        from inventory.models import InventoryItem

        # 1. Sve aktivne kompanije (koriste se na svakom requestu)
        companies = list(Company.objects.filter(is_active=True).values(
            'id', 'name', 'oib', 'country', 'subscription_plan'
        ))
        cache.set('all_active_companies', companies, 3600)

        # 2. POS terminali po company
        from pos.models import POSTerminal
        for terminal in POSTerminal.objects.filter(is_active=True).select_related('company'):
            key = f'pos_terminal_{terminal.id}'
            cache.set(key, {
                'id': str(terminal.id),
                'name': terminal.name,
                'company_id': str(terminal.company_id),
                'pos_type': terminal.pos_type,
            }, 1800)

        # 3. Tax rates (globalne, mijenjaju se rijetko)
        from companies.models import TaxRate
        for country in ['HR', 'DE', 'AT', 'SI']:
            rates = list(TaxRate.objects.filter(country=country).values())
            cache.set(f'tax_rates_{country}', rates, 86400)  # 24h

        # 4. NKD kodovi (statički)
        from companies.models import NKDCode
        if NKDCode.objects.exists():
            nkd = list(NKDCode.objects.values('code', 'name', 'category')[:500])
            cache.set('nkd_codes_top500', nkd, 86400)

        self.stdout.write(self.style.SUCCESS(
            f'Cache warm: {len(companies)} companies, tax rates HR/DE/AT/SI, POS terminali'
        ))
```

### Dodati u gunicorn startup:
```bash
# U /etc/systemd/system/gunicorn-fina.service — ExecStartPost:
ExecStartPost=/var/www/fina-connect/venv/bin/python /var/www/fina-connect/manage.py warm_cache
```

### Provjeri rezultat:
```bash
systemctl restart gunicorn-fina
sleep 5
redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
# Hit rate treba porasti
```

---

## ZADATAK B2 — Audit log particioniranje (641MB → kontroliran rast)

### Provjeri što je audit log model:
```bash
grep -rn "class.*Log\|class.*Audit\|class.*AuditLog" \
  /var/www/fina-connect/core/models.py | head -10
# Ili:
grep -rn "audit" /var/www/fina-connect/core/models.py | head -10
```

### Trenutno stanje:
```sql
-- Pokreni u psql:
SELECT
    relname AS table,
    pg_size_pretty(pg_total_relation_size(relid)) AS size,
    n_live_tup AS rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

### Rješenje — retention policy (Celery task):
Kreirati `core/tasks/audit_cleanup.py`:

```python
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def cleanup_old_audit_logs():
    """
    Briše audit logove starije od 90 dana.
    Pokreće se svake noći u 03:00.
    Čuva sve logove za fakture i POS (financijska evidencija = 8 god).
    Briše samo: login logove, view logove, search logove.
    """
    cutoff = timezone.now() - timedelta(days=90)

    # Provjeri koji je pravi model — prilagodi import
    try:
        from core.models import AuditLog
        deleted, _ = AuditLog.objects.filter(
            created_at__lt=cutoff,
            action__in=['VIEW', 'LOGIN', 'LOGOUT', 'LIST', 'SEARCH']
        ).delete()
        return f"Obrisano {deleted} audit log zapisa starijih od 90 dana"
    except ImportError:
        # Fallback — nađi pravi model
        return "AuditLog model nije pronađen — provjeri core/models.py"
```

### Dodati u Celery beat raspored (core/celery.py ili settings.py):
```python
# Provjeri gdje je celery beat config:
grep -rn "beat_schedule\|CELERYBEAT" /var/www/fina-connect/core/ | head -10

# Dodati:
'cleanup-audit-logs': {
    'task': 'core.tasks.audit_cleanup.cleanup_old_audit_logs',
    'schedule': crontab(hour=3, minute=0),
},
```

### PostgreSQL particioniranje (za budućnost — ne sad):
```sql
-- Bilješka za DBA: kada audit tablica premaši 2GB,
-- implementirati range particioniranje po created_at (monthly)
-- ALTER TABLE core_auditlog PARTITION BY RANGE (created_at);
-- Nije hitno za 15.04. ali je plan za Q3.
```

---

## ZADATAK B3 — Novi server konfiguracija (čeka Ivan narudžbu)

**Preduvjet:** Ivan naruča Hetzner CCX33 do 05.04.

### Kada server bude dostupan (IP):

#### 3a. Osnovna konfiguracija:
```bash
# Kreiraj setup skriptu za novi server
cat > /var/www/fina-connect/scripts/setup_new_server.sh << 'SETUP'
#!/bin/bash
# LIMIT Connect — novi server setup
# Pokreni kao root na svježem Ubuntu 24.04

set -e

# System
apt-get update && apt-get upgrade -y
apt-get install -y python3.12 python3-pip postgresql-16 nginx redis-server \
  git build-essential libpq-dev mdbtools python3-venv

# PostgreSQL tuning za CCX33 (8 CPU, 16GB RAM)
cat >> /etc/postgresql/16/main/postgresql.conf << 'PG'
shared_buffers = 4GB
work_mem = 128MB
effective_cache_size = 12GB
random_page_cost = 1.1
effective_io_concurrency = 200
max_connections = 200
wal_buffers = 64MB
checkpoint_completion_target = 0.9
PG

# Redis config
echo "maxmemory 2gb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf

# Gunicorn workers = 2 * CPU + 1 = 17 za CCX33
echo "Gunicorn workers: 17"
echo "PgBouncer: install and configure"
SETUP
chmod +x /var/www/fina-connect/scripts/setup_new_server.sh
```

#### 3b. Migracija podataka (prazna baza):
```bash
# Na novom serveru: prazna baza, samo struktura
# NE kopirati test podatke (Synesis 2025 ostaje samo na dev serveru)
venv/bin/python manage.py migrate
venv/bin/python manage.py warm_cache
# Bez seed podataka — sve kreće od nule
```

#### 3c. DNS cutover plan:
```
Korak 1: Deploy na novi server, testiraj na IP adresi direktno
Korak 2: Smanji TTL limit-connect.com na 60s (već napravljeno)
Korak 3: Prebaci DNS u 03:00 (najmanji promet)
Korak 4: Monitoraj 30 min — ako greška, revert u 5 min
```

---

## ZADATAK B4 — Final load test na novom serveru

Pokrenuti NAKON što je novi server konfiguriran:

```bash
cd /var/www/fina-connect/loadtest

# Test s 150 concurrent (prethodni rezultat: 453 req/s, p99=56ms)
# Na CCX33 target: >800 req/s, p99<30ms
locust -f locustfile.py --headless \
  --users 150 --spawn-rate 10 \
  --host http://NEW_SERVER_IP \
  --run-time 60s \
  --csv loadtest_ccx33_150

# Test s 500 concurrent
locust -f locustfile.py --headless \
  --users 500 --spawn-rate 20 \
  --host http://NEW_SERVER_IP \
  --run-time 120s \
  --csv loadtest_ccx33_500

# GO ako:
# - p99 < 200ms na 500 concurrent
# - Error rate < 0.1%
# - Memory < 80% na peak
echo "Provjeri: cat loadtest_ccx33_500_stats.csv"
```

---

## ZADATAK B5 — Monitoring dashboard za prvi dan produkcije

Kreirati `scripts/prod_monitor.sh` koji se pokreće svakih 5 minuta na prvom danu:

```bash
#!/bin/bash
# Pokreni: watch -n 300 ./scripts/prod_monitor.sh
DATETIME=$(date '+%d.%m.%Y %H:%M')

echo "=== LIMIT Connect Monitor — $DATETIME ==="

# Aktivni korisnici (Gunicorn workers)
echo -n "Active requests: "
ps aux | grep gunicorn | grep -v grep | wc -l

# Baza
echo -n "DB connections: "
psql -U limitconnect -c "SELECT count(*) FROM pg_stat_activity WHERE state='active';" -t 2>/dev/null | tr -d ' '

# Redis
echo -n "Redis hit rate: "
redis-cli INFO stats | grep keyspace_hits | awk -F: '{print $2}' | tr -d '\r'

# Memory
free -h | grep Mem | awk '{print "RAM: " $3 "/" $2}'

# Disk
df -h /var/www | tail -1 | awk '{print "Disk: " $3 "/" $2 " (" $5 ")"}'

# Gunicorn errors zadnjih 5 min
ERR=$(journalctl -u gunicorn-fina --since "5 minutes ago" | grep -c "ERROR" || true)
echo "Errors (5min): $ERR"

# Ako >5 grešaka — WhatsApp alarm
if [ "$ERR" -gt 5 ]; then
  echo "⚠️  ALARM: $ERR greška u zadnjih 5 minuta!"
fi
```

---

## KOORDINACIJA S TASK A:

| Fajl | Task A | Task B |
|---|---|---|
| synesis_compare.py | PIŠE | NE DIRA |
| invoicing/ | PIŠE | NE DIRA |
| konto/ | PIŠE | NE DIRA |
| core/management/commands/warm_cache.py | NE DIRA | PIŠE |
| core/tasks/audit_cleanup.py | NE DIRA | PIŠE |
| scripts/setup_new_server.sh | NE DIRA | PIŠE |
| loadtest/ | NE DIRA | PIŠE |

---

## TIMELINE:

```
05.04. Ivan naruča CCX33
06.04. B3 — server setup script gotov
07.04. A1-A3 — dijagnoza + fix razlika
08.04. A4 — testni suite zeleni
09.04. B1 — Redis warm_cache deploy
09.04. B2 — audit cleanup Celery task deploy
10.04. A5 — MARIJA_BLAGOSLOV.md kreiran s rezultatima
11.04. Marija pregled (njen dan — ne smetati)
12.04. B4 — final load test na CCX33
13.04. B5 — monitoring script deploy
14.04. DNS cutover priprema
15.04. GO/NO-GO odluka
```

## GIT:
```bash
git add core/management/commands/warm_cache.py \
        core/tasks/audit_cleanup.py \
        scripts/setup_new_server.sh \
        scripts/prod_monitor.sh
git commit -m "feat(infra): cache warming, audit cleanup, server setup, load test config"
git log --oneline -3
```
Update FENIX_STATUS.md.
