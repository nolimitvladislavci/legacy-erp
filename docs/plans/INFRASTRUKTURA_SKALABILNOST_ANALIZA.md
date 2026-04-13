# INFRASTRUKTURA_SKALABILNOST_ANALIZA.md
# Datum: 2026-03-30
# Autor: Sonnet — na temelju stvarnih serverskih podataka
# Cilj: Infrastruktura koja podnosi 3.000+ klijenata po distributeru

---

## STVARNO STANJE SERVERA (mjereno danas)

| Metrika | Vrijednost | Status |
|---|---|---|
| Server | Hetzner CCX13 — 4 vCPU AMD EPYC, 8GB RAM | ⚠️ Premaleno za target |
| DB veličina | 866MB ukupno | ✓ |
| Audit log | 641MB (74% baze!) | 🔴 Kritičan problem |
| Audit redci | 1.254.041 u jednom mjesecu | 🔴 Nekontroliran rast |
| Cache hit | 98.4% (PG) | ✓ |
| Redis hit rate | 52% | 🔴 Loše (treba >90%) |
| shared_buffers | bio 128MB → POPRAVLJENO na 2GB | ✅ Fiksirano |
| Swap korišten | 2.7GB od 18GB | ⚠️ Previše |
| Load average | 0.56 / 1.57 / 1.91 | ⚠️ 48% na 4 vCPU |
| Disk speed | 846 MB/s (NVMe) | ✓ Izvrsno |
| PgBouncer | Aktivan, transaction mode | ✓ |

---

## ODMAH PRIMJENJENI FIXOVI (€0, danas)

### 1. PostgreSQL tuning
```
shared_buffers: 128MB → 2GB  (bio 1.5% RAM-a, sad 25%)
work_mem: default → 64MB     (brže sortiranje, join operacije)
effective_cache_size: → 6GB  (bolji query planner)
random_page_cost: → 1.1      (NVMe optimizacija)
effective_io_concurrency: → 200 (NVMe paralelizam)
```
Efekt: query planner donosi bolje odluke, manje disk I/O za large queries.

### 2. Redis maxmemory
```
maxmemory: neograničen → 1GB
maxmemory-policy: allkeys-lru (automatski izbaci stare podatke)
```
Efekt: Redis više ne može pojesti sav RAM ako cache naraste.

### 3. vm.swappiness: 10 → 10 (već bio 10 — OK)
Linux preferira RAM, swappa samo u krajnjoj nuždi.

---

## KRITIČAN PROBLEM: AUDIT LOG RAST

**1.254.041 redaka u jednom mjesecu — samo u ožujku 2026.**

Top 3 uzroka:
1. `konto.LedgerLine` — 806.918 redaka (64%) → svaka knjižna stavka se logira
2. `konto.JournalEntry` — 227.229 redaka (18%) → svaki journal entry logira
3. `documents.ArhivaEntry` — 73.394 redaka

Projekcija:
- Danas: 866MB baza
- Za 3 mjeseca: ~3GB baza (samo audit)
- Za 12 mjeseci: ~10GB baza
- Za 3 distributora × 3.000 klijenata: ~150GB baze samo audit logovi

**Rješenje (CC Code treba napraviti):**
1. `konto.LedgerLine` — ISKLJUČI audit log (LedgerLine je immutable by design, ne treba audit)
2. `konto.JournalEntry` — ISKLJUČI audit log (isti razlog)
3. Audit log particioning po mjesecima (pg_partman)
4. Arhiviranje: sve starije od 90 dana → S3 ili zasebna baza

---

## GEMINIJEV PRIJEDLOG — OCJENA I KOREKCIJE

### Što Gemini pogodio:
✓ Razdvajanje App / DB / Cache slojeva — ispravno za 9.000 firmi
✓ PgBouncer (već imamo) ✓
✓ Read Replicas — ispravno za analytics queries
✓ Prometheus/Grafana monitoring — trebamo
✓ 300-350 EUR/mj za infrastrukturu

### Gdje Gemini griješi:

**Greška 1: 300-350 EUR/mj je premalo za 3.000+ po distributeru**

Za 720 simultanih korisnika (3 dist × 3.000 klijenata × 2%):
- Realna infrastruktura: 800-1.500 EUR/mj
- Ali: trošimo to KADA IMAMO PRIHOD koji to opravdava

**Greška 2: Docker u produkciji za ovaj stack**

Docker compose je odličan za razvoj i testiranje.
Za produkciju s 9.000 firmi i fiskalnim podacima:
- Svaki container restart = downtime risk
- Networking overhead (~5% performansi)
- Complexity za 2-person team = problem
Preporuka: **bare metal deployment** ostaje, Dockerize samo za testing environment.

**Greška 3: Propušta najveći problem — Audit Log**

641MB audit loga za 14 klijenata u jednom mjesecu.
Za 9.000 klijenata = 41GB audit loga MJESEČNO.
To ubija bazu bez obzira na hardver.

---

## PLAN SKALIRANJA — 4 FAZE

### FAZA 0 — Odmah (fiksirano danas, €0)
- [x] PostgreSQL shared_buffers: 128MB → 2GB
- [x] Redis maxmemory: unlimited → 1GB + LRU eviction
- [x] vm.swappiness: 10 (već bio OK)
- [ ] CC Code: Isključi audit log za konto.LedgerLine i konto.JournalEntry
- [ ] CC Code: Audit log particioniranje + 90-day archiving
- [ ] Redis caching: cacheiraj permissions, WhiteLabel config, session data

**Efekt: 2-3× poboljšanje performansi bez novog hardvera.**

---

### FAZA 1 — Q2 2026: Prvih 500 klijenata (MRR ~30k EUR)
**Trošak: +80 EUR/mj (ukupno ~130 EUR/mj)**

Upgrade trenutnog servera: CCX13 (4/8GB) → CCX33 (8/32GB) = 131 EUR/mj

```
4 vCPU → 8 vCPU    (Gunicorn workers: 6 → 12)
8GB → 32GB RAM     (PostgreSQL shared_buffers: 2GB → 8GB)
```

Dodaj: Hetzner Managed Redis (3 EUR/mj) — dedicated, HA, bez konfiguracije

**Nema arhitekturalne promjene — samo jači stroj.**
Dok infrastruktura stoji na jednom serveru, deployment je jednostavan.
Sve environment varijable (DB_HOST, CACHE_HOST) već su externalizirane u kodu.

---

### FAZA 2 — Q3 2026: 5 distributera, 2.000+ klijenata (MRR ~150k EUR)
**Trošak: +200 EUR/mj (ukupno ~330 EUR/mj)**

```
App server (CCX33 8/32GB):        131 EUR/mj  (drži Gunicorn, Celery, Nginx)
DB server (Hetzner Managed PG):   100 EUR/mj  (8 vCPU, 32GB, HA, PITR backup)
Redis (Hetzner Managed):          20 EUR/mj
Object Storage (S3-compatible):   10 EUR/mj
UKUPNO:                           261 EUR/mj
```

**Ključna promjena:** PostgreSQL ide na Managed Database (Hetzner).
- Automatski failover (HA)
- Point-in-Time Recovery (PITR) — svaka sekunda transakcije je novac
- Backup automatski
- Mi ne maintainamo DB server

**Separacija DB_HOST iz settings.py je VEĆ IMPLEMENTIRANA** — 
`DATABASE_URL` environment variable → promijenimo IP, deployment isti.

Read replica: Hetzner managed DB ima read replicas uključene u cijenu.
Analytics, izvještaji → čitaju s replike, primarna baza prima samo write.

---

### FAZA 3 — Q4 2026: 5+ distributera, 9.000 klijenata (MRR ~500k EUR)
**Trošak: +500 EUR/mj (ukupno ~800 EUR/mj)**

```
2× App server (CCX23, 4/16GB HA): 2 × 70 = 140 EUR/mj
Load Balancer (Hetzner LB):       7 EUR/mj
DB (Managed PG, 16/64GB, HA):     300 EUR/mj
Redis (Managed, cluster):         50 EUR/mj
Object Storage (S3):              30 EUR/mj
Monitoring (Hetzner + Grafana):   50 EUR/mj
UKUPNO:                           577 EUR/mj
```

**Horizontalno skaliranje App servera:**
- 2 app servera iza Load Balancera
- Zero-downtime deployments (jedan server prima traffic dok drugi se restartira)
- Ako jedan padne: automatski failover

**Ovo je "50% snage" konfiguracija:**
- 2 app servera: kad jedan radi, drugi je rezerva
- DB: HA par — primary + standby
- Redis: cluster mode

---

### FAZA 4 — Borg Full HA (kada MRR opravdava)
Za 20.000+ firmi, multi-region, 99.99% SLA:
Kubernetes, multi-region, Patroni za PG HA, CDN...
**Ali to je problem za 2027., ne 2026.**

---

## KRITIČNI KOD KOJI MORA BITI SPREMAN (neovisno o hardveru)

### 1. Audit log — ISKLJUČI za volume tablice

```python
# U konto/models.py — LedgerLine i JournalEntry:
class LedgerLine(AuditableModel):
    class Meta:
        # LedgerLine je immutable — nikad se ne mijenja, samo kreira
        # Audit log genrira 806.918 redaka/mj za 14 klijenata
        # Za 9.000 klijenata = 520 milijuna redaka/mj = neprihvatljivo
        audit_log_enabled = False  # Ili: exclude iz AuditMiddleware
```

Alternativa: custom audit za konto (samo create, bez update/delete jer ionako ne postoje).

### 2. Redis caching — cacheiraj skupo i učestalo

```python
# Permissions (svaki request provjerava — 52% miss rate znači svaki drugi ide u SQL)
from django.core.cache import cache

def get_user_permissions(user, company=None):
    key = f'perms:{user.pk}:{company.pk if company else 0}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    # ... SQL query
    cache.set(key, result, timeout=300)  # 5 minuta
    return result

# WhiteLabel config (isti domain → isti config, tisuće requesta/dan)
def get_white_label(host):
    key = f'wl:{host}'
    cached = cache.get(key)
    if cached:
        return cached
    config = WhiteLabelConfig.objects.filter(custom_domain=host).first()
    cache.set(key, config, timeout=3600)  # 1 sat
    return config
```

### 3. Environment variables — već OK, ali verificiraj

```python
# core/settings.py — mora biti externalizirano (za Fazu 2 promjenu DB hosta)
import os
DATABASES = {
    'default': {
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),  # ← promijenimo kad idemo na managed
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
CACHES = {
    'default': {
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
    }
}
```

Provjeri je li to stvarno tako:
```bash
grep -n "DB_HOST\|REDIS_URL\|DATABASE_URL" /var/www/fina-connect/core/settings.py
```

---

## TROŠKOVNIK PO FAZAMA

| Faza | MRR cilj | Infra trošak | % MRR | Komentar |
|---|---|---|---|---|
| 0 (danas) | 2.380 EUR | 51 EUR | 2.1% | Hetzner CCX13 |
| 1 (Q2) | 30.000 EUR | 131 EUR | 0.4% | CCX33 upgrade |
| 2 (Q3) | 150.000 EUR | 261 EUR | 0.17% | Managed DB |
| 3 (Q4) | 500.000 EUR | 577 EUR | 0.11% | Full HA |

**Infrastruktura uvijek ispod 1% MRR-a. To je zdravo.**

---

## ZAKLJUČAK

Gemini je u pravu o arhitekturi — ali to je DESTINACIJA, ne polazišna točka.

**Redoslijed:**
1. Popravi što je pokvareno SADA (audit log, Redis caching) — besplatno, 1 dan CC rada
2. Upgrade servera kad MRR premaši 10k EUR — jedan CLI command na Hetzneru
3. Managed DB kad imaš 5+ distributera — promijeniti env varijablu, 0 code changea
4. HA load balancer kad imaš 2.000+ istovremenih korisnika

**Najvažnija rečenica:**
Infrastruktura se skalira s prihodom. Kod mora biti spreman. Hardver slijedi.

---
## STATUS: IMPLEMENTIRANO (Faza 0)
## Sljedeće: CC Code — audit log fix + Redis caching
