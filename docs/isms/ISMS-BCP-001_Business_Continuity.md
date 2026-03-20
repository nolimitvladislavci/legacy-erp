# Business Continuity Plan (BCP)
## LIMIT Connect ERP Platform

**Dokument:** ISMS-BCP-001
**Verzija:** 1.0
**Datum:** 20.03.2026.

---

## 1. Opseg

Ovaj plan pokriva oporavak LIMIT Connect ERP platforme u slučaju:
- Pada servera (hardware/software)
- Gubitka podataka (DB corruption, ransomware)
- Nedostupnosti ključnih servisa (FINA, Fiskaly, DNS)
- Prirodne katastrofe (data centar)

---

## 2. Kritični sustavi (RTO/RPO)

| Sustav | RTO | RPO | Prioritet |
|--------|-----|-----|-----------|
| **POS blagajna** | 15 min | 0 (offline mode) | KRITIČNO |
| **Web aplikacija** | 30 min | 24h (daily backup) | VISOKO |
| **PostgreSQL baza** | 30 min | 24h | VISOKO |
| **Fiskalizacija (FINA/TSE)** | 2h | 48h (zakonski) | VISOKO |
| **Email/WhatsApp** | 4h | N/A | SREDNJE |
| **Celery tasks** | 1h | N/A | SREDNJE |

**RTO** = Recovery Time Objective (koliko brzo moramo biti online)
**RPO** = Recovery Point Objective (koliko podataka smijemo izgubiti)

---

## 3. Automatski oporavak (implementirano)

### 3.1 Self-healing (svakih 10 min)
**Skripta:** `/usr/local/bin/lc_self_heal.sh`

Automatski restarta:
- Gunicorn (web server)
- Celery Worker (pozadinski zadaci)
- Celery Beat (scheduler)
- Nginx (reverse proxy)
- PostgreSQL (baza)

Emergency akcije:
- Disk >95% → automatski cleanup logova
- Memory >95% → gunicorn restart

### 3.2 Health monitoring (svakih 5 min)
**Skripta:** `/usr/local/bin/lc_health_monitor.sh`

Provjerava:
- HTTPS status (200/302)
- Health endpoint (/health/)
- Disk usage (<90%)
- Memory usage (<90%)

Alert: Email na grosmarkt.online@gmail.com pri promjeni stanja (OK→ALERT).

### 3.3 Automatski backup (svaki dan 03:00)
**Skripta:** `/usr/local/bin/lc_backup.sh`

- PostgreSQL dump → `/var/backups/limit-connect/db_YYYYMMDD.sql.gz` (~24MB)
- Media backup → `media_YYYYMMDD.tar.gz`
- Git auto-commit (code snapshot)
- Retencija: 14 dana
- Integritet: alert ako je dump <10KB

---

## 4. Disaster Recovery procedura

### Scenarij A: Server nedostupan (Hetzner outage)

```
1. Provjeri Hetzner status: https://status.hetzner.com/
2. Ako ETA > 2h:
   a. Podigni novi Hetzner server (Falkenstein ili Nürnberg)
   b. Instaliraj: apt install postgresql nginx python3 python3-venv
   c. Kloniraj Git repo
   d. Pokreni: /usr/local/bin/lc_rebuild.sh YYYYMMDD
   e. Preusmjeri DNS (Namecheap → nova IP)
   f. Certbot za SSL
3. Testiraj: curl https://limit-connect.com/login/
4. Obavijesti korisnike putem WhatsApp
```

**Odgovorna osoba:** Ivan Brtan
**Zamjena:** Nikša Višković

### Scenarij B: Baza podataka oštećena

```
1. Stop servise: systemctl stop gunicorn-fina celery-worker celery-beat
2. Restore zadnji backup:
   gunzip -c /var/backups/limit-connect/db_YYYYMMDD.sql.gz | psql -U viskovic_user fina_erp
3. Pokreni migracije: python manage.py migrate
4. Start servise: systemctl start gunicorn-fina celery-worker celery-beat
5. Provjeri: /health/ endpoint
```

### Scenarij C: FINA CIS nedostupna

```
1. POS nastavlja raditi normalno
2. Računi se izdaju BEZ JIR-a (ZKI se generira lokalno)
3. Na bonu piše: "JIR: Nije ishođen (Offline)"
4. Celery retry task šalje svakih 2 min
5. Zakonski rok: 48 sati za naknadnu fiskalizaciju
6. NE TREBA intervencija — sustav je samopopravljajući
```

### Scenarij D: Fiskaly TSE nedostupna (DE)

```
1. POS nastavlja raditi
2. Na bonu: "TSE AUSGEFALLEN — Nacherfassung erfolgt automatisch"
3. Celery retry za Nacherfassung
4. KassenSichV dopušta offline rad s klauzelom
5. NE TREBA intervencija
```

---

## 5. Kontakt lista za incidente

| Prioritet | Osoba | Kontakt | Uloga |
|-----------|-------|---------|-------|
| 1 | Ivan Brtan | +385 97 609 1655 | Vlasnik, odluke |
| 2 | Nikša Višković | niksa.viskovic (login) | Tehnički, DE tržište |
| 3 | Marija Brtan | +385 97 609 1655 | Knjigovodstvo, revizija |
| 4 | Hetzner Support | support@hetzner.com | Infrastruktura |
| 5 | Fiskaly Support | support@fiskaly.com | TSE problemi |

---

## 6. Testiranje plana

| Test | Učestalost | Zadnji test | Rezultat |
|------|-----------|-------------|---------|
| Backup restore | Kvartalno | 20.03.2026. | PASS (lc_rebuild.sh) |
| Self-heal restart | Kontinuirano | Svakih 10 min | PASS |
| Offline POS | Jednom godišnje | 20.03.2026. | PASS (50/50 testova) |
| DNS failover | Kod migracije | 17.03.2026. | PASS |

---

## 7. Pregled i ažuriranje

Ovaj plan se preispituje:
- Kvartalno (redovni pregled)
- Nakon svakog incidenta
- Kod promjene infrastrukture

**Odobrio:** Ivan Brtan
**Datum:** 20.03.2026.
