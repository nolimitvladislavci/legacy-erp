# TRAK G — QA / DevOps

**Vlasnik**: QA agent (Sonnet/CC za održavanje)
**File područje**: `qa_lab/`, `.github/workflows/`, monitoring
**NE diraj**: business logic, samo testirati

---

## CILJ

Osigurati da nijedan deploy ne pukne 110 firmi. Svaki commit prošlo Oracle + Time Machine. Svaki tjedan Mutant. Svaki dan Bunker probe.

---

## TRENUTNO STANJE (LIVE)

✅ Već deployed (20–21.04.2026.):

| Komponenta | Lokacija | Status |
|---|---|---|
| Oracle (AST risk analyzer) | `qa_lab/oracle/analyzer.py` | LIVE |
| Time Machine (smoke tests) | `qa_lab/time_machine/smoke_runner.py` | LIVE, 4 critical journeys < 250ms |
| Mutant (mutmut wrapper) | `qa_lab/mutant/runner.py` | LIVE |
| Bunker probe (Playwright) | `qa_lab/bunker/test_login_journey.py` | LIVE |
| Dashboard | `https://limit-connect.com/qa/` | LIVE staff-only |
| Master runner | `qa_lab/run_all.sh` | LIVE |
| GitHub Actions CI | `.github/workflows/qa-lab.yml` | LIVE |
| Pre-commit hook | `.git/hooks/pre-commit-oracle` | LIVE |

---

## SPRINT 1 — Bunker dijagnoza (T1, ovaj tjedan)

**KRITIČNO**: 110 firmi čeka na vratima.

### Akcija G1.1 — Stvarni login pokušaj kao test korisnik

```python
# qa_lab/bunker/test_real_login.py
# Treba test username + password od Ivana

async def test_real_login():
    page.fill('input[name="username"]', os.environ['TEST_USER'])
    page.fill('input[name="password"]', os.environ['TEST_PASS'])
    page.click('button[type="submit"]')
    # Mjeri redirect, capture screenshot ako fail
```

### Akcija G1.2 — Analizirati `accounts/views.py` (Oracle risk 1.00)

Oracle je flagrirao 1526 LOC, 7 signala. Ručno pregledati i dijagnosticirati:
- Je li login flow razdvojen u previše koraka?
- Je li bunker (WebAuthn) confused s klasičnim login?
- Postoji li edge case za korisnike bez WebAuthn?

### Akcija G1.3 — Dodati „Mala Vrata" recovery promijeniti dovoljno?

Trenutno: `<a href="/hr/accounts/small-doors/" class="lc-forgot">Mala Vrata 🚪</a>` — recovery flow.

Test: pokrenuti recovery od test korisnika, mjeriti uspješnost.

### Akcija G1.4 — Bunker fix + redeploy

Nakon dijagnoze, popraviti i ponovno pokrenuti bunker probe.

---

## SPRINT 2 — Monitoring (T2)

### Akcija G2.1 — Sentry je već u Fenix V3

Provjeriti DSN je aktivan za Fenix V3 (memory: SENTRY_DSN = `https://cb865e14...`).

### Akcija G2.2 — Uptime monitoring

- Postaviti **UptimeRobot** (besplatno) na ključne URL-ove:
  - `https://limit-connect.com/`
  - `https://limit-connect.com/hr/accounts/login/`
  - `https://no-limit.world/`
  - `https://no-limit.world/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.pdf`
- Alert: WhatsApp na +49 157 71998747 ako pad > 2 min

### Akcija G2.3 — Log aggregation

Trenutno: log datoteke u `logs/audit.log`. Dodati:
- **Loki** (Grafana stack, free) — agregacija logova
- **Grafana dashboard** — real-time view
- Alternative jeftinije: **Better Stack** ili **Sentry** (već imamo)

---

## SPRINT 3 — Performance (T3–T4)

### Akcija G3.1 — Database query analizator

```python
# qa_lab/perf/slow_queries.py
# Pokreni django-debug-toolbar samo za staff, capture queries > 100ms
```

### Akcija G3.2 — N+1 detector

- `nplusone` package
- Logira u Sentry kad se N+1 detektira

### Akcija G3.3 — Front-end performance

- Lighthouse CI u GitHub Actions
- Cilj: > 90 score na svim ključnim stranicama

---

## SPRINT 4 — Backup + Disaster Recovery (T5–T6)

### Akcija G4.1 — Automatski PostgreSQL backup

```bash
# /etc/cron.daily/fenix-backup
pg_dump fenix_v3_clean | gzip > /backups/fenix_$(date +%F).sql.gz
# Retention: 30 dana
# Off-site: rsync na S3 / drugi server
```

### Akcija G4.2 — Restore drill

Mjesečno: testirati restore na staging server (vrijeme vraćanja, integritet).

### Akcija G4.3 — Embedding backup strategy (kad pgvector dođe)

NE backup-aj vektore. Samo source. Restore regenerira vektore u Celery batchu.

---

## SLJEDEĆA AKCIJA

→ **G1.1 + G1.2**: bunker dijagnoza prioritet jer 110 firmi čeka.

## ZADNJA IZMJENA

| Datum | Tko | Što | Sljedeći korak |
|---|---|---|---|
| 20.04.2026. | Opus | QA Lab v1 deployed (svih 4 kvanta) | Bunker dijagnoza |
| 21.04.2026. | Opus | Plan napisan | G1.1 čim Ivan da test credentials |

## DEPENDENCIES

- **Čeka**: Ivan da test credentials za G1.1
- **Blokira**: H (Udruga registracija nema veze s ovim)
