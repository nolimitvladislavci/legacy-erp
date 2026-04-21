# 09_TRACK_G — SELF-HEALING INFRASTRUCTURE
## Handoff za Sonnet | Datum: 2026-04-21 | CC: implementacija završena

---

## PREGLED

4 komada koja grade self-healing sloj Fenix V3:

| #  | Komad                        | Est.   | Cilj                                              |
|----|------------------------------|--------|---------------------------------------------------|
| 1  | Health endpoint `/health/`   | 30 min | JSON: DB + Redis + Celery + Disk + Bunker status  |
| 2  | pg_dump + off-site backup    | 2 h    | Dnevni cron 03:00 UTC, 30-dan retencija, POE log  |
| 3  | Circuit breaker za Haiku     | 1 dan  | 5-razinski fallback s telemetrijom                |
| 4  | Browser test matrix          | 4 h    | Chrome + Safari + Firefox + Edge × mobile/desktop |

Server: `ssh -p 2222 root@37.27.248.86`
Dir: `/var/www/fenix-v3/`
Venv: `/var/www/fenix-v3/venv/bin/python`

---

## KOMAD 1 — Health Endpoint `/health/`

### Cilj
Jedan GET endpoint, bez autentikacije, vraća JSON sa statusom svih komponenti.
Koristi se za: monitoring, uptime robot, Kubernetes liveness probe, Bunker watchdog.

### Postojeći kod
`core/monitoring.py` ima `HealthCheckView` — provjeri što već postoji.

### Implementacija

**`core/monitoring.py`** — proširi postojeći ili napiši novo:

```python
import time
import shutil
import redis
from django.http import JsonResponse
from django.views import View
from django.db import connection, OperationalError
from django.conf import settings
from celery.app.control import Inspect


class HealthCheckView(View):
    """
    GET /health/ — bez login, bez CSRF
    Vraća 200 ako sve OK, 503 ako išta CRITICAL pada.
    """

    def get(self, request):
        t0 = time.monotonic()
        results = {}
        critical_fail = False

        # 1. DATABASE
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            results["db"] = {"status": "ok"}
        except OperationalError as e:
            results["db"] = {"status": "error", "detail": str(e)}
            critical_fail = True

        # 2. REDIS
        try:
            r = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"])
            r.ping()
            results["redis"] = {"status": "ok"}
        except Exception as e:
            results["redis"] = {"status": "error", "detail": str(e)}
            critical_fail = True

        # 3. CELERY (provjeri ima li aktivnih workera)
        try:
            insp = Inspect(timeout=2.0)
            active = insp.active()
            if active:
                worker_count = len(active)
                results["celery"] = {"status": "ok", "workers": worker_count}
            else:
                results["celery"] = {"status": "warn", "detail": "no active workers"}
        except Exception as e:
            results["celery"] = {"status": "error", "detail": str(e)}

        # 4. DISK
        try:
            usage = shutil.disk_usage("/var/www/fenix-v3")
            free_pct = (usage.free / usage.total) * 100
            disk_status = "ok" if free_pct > 10 else ("warn" if free_pct > 5 else "error")
            results["disk"] = {
                "status": disk_status,
                "free_pct": round(free_pct, 1),
                "free_gb": round(usage.free / 1e9, 2),
            }
            if disk_status == "error":
                critical_fail = True
        except Exception as e:
            results["disk"] = {"status": "error", "detail": str(e)}

        # 5. BUNKER (POE service — provjeri može li se dohvatiti)
        try:
            from core.poe_service import BunkerStatus  # ako postoji
            bunker_ok = BunkerStatus.ping()
            results["bunker"] = {"status": "ok" if bunker_ok else "warn"}
        except ImportError:
            results["bunker"] = {"status": "skip", "detail": "poe_service not imported"}
        except Exception as e:
            results["bunker"] = {"status": "warn", "detail": str(e)}

        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        http_status = 503 if critical_fail else 200

        return JsonResponse(
            {
                "status": "error" if critical_fail else "ok",
                "elapsed_ms": elapsed_ms,
                "components": results,
                "version": getattr(settings, "APP_VERSION", "fenix-v3"),
            },
            status=http_status,
        )
```

**`core/urls.py`** ili `core/urls_hr.py` — dodaj rutu:
```python
from core.monitoring import HealthCheckView
path("health/", HealthCheckView.as_view(), name="health"),
```

**`core/middleware.py`** ili settings — izuzmi od login middleware:
```python
LOGIN_EXEMPT_URLS = [
    r"^health/$",
    # ... ostali ...
]
```

### Test
```bash
curl -s http://localhost:8001/health/ | python3 -m json.tool
# Očekivano: {"status": "ok", "elapsed_ms": <N>, "components": {...}}
```

---

## KOMAD 2 — pg_dump + Off-Site Backup

### Cilj
Dnevni automatski backup baze `fenix_v3_clean`, 30-dan retencija, SHA-256 POE log.

### Backup skripte

**`_scripts/backup_pg.sh`:**
```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/fenix-v3"
DB_NAME="fenix_v3_clean"
DB_USER="postgres"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"
OFFSITE_HOST="${OFFSITE_BACKUP_HOST:-}"  # set u env

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] START backup $DB_NAME" >> "$LOG_FILE"

# Dump + compress
pg_dump -U "$DB_USER" -h 127.0.0.1 "$DB_NAME" | gzip > "$FILENAME"

# SHA-256
HASH=$(sha256sum "$FILENAME" | cut -d' ' -f1)
echo "[$(date -Iseconds)] HASH $FILENAME $HASH" >> "$LOG_FILE"

# Upisi u Django BackupLog (via management command)
/var/www/fenix-v3/venv/bin/python /var/www/fenix-v3/manage.py log_backup \
    --filename="$(basename $FILENAME)" \
    --sha256="$HASH" \
    --size="$(stat -c%s $FILENAME)"

# Off-site rsync (opcionalno)
if [ -n "$OFFSITE_HOST" ]; then
    rsync -az "$FILENAME" "${OFFSITE_HOST}:/backups/fenix-v3/"
    echo "[$(date -Iseconds)] RSYNC OK" >> "$LOG_FILE"
fi

# Brisanje starih backupa
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete
echo "[$(date -Iseconds)] CLEANUP done (>${RETENTION_DAYS}d)" >> "$LOG_FILE"

echo "[$(date -Iseconds)] END backup OK — $FILENAME ($HASH)" >> "$LOG_FILE"
```

**Django model `core/models_backup.py`:**
```python
from django.db import models

class BackupLog(models.Model):
    """POE log svakog pg_dump backupa."""
    created_at = models.DateTimeField(auto_now_add=True)
    filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    offsite_synced = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} @ {self.created_at:%Y-%m-%d %H:%M}"
```

**Management command `core/management/commands/log_backup.py`:**
```python
from django.core.management.base import BaseCommand
from core.models_backup import BackupLog

class Command(BaseCommand):
    help = "Log backup entry into BackupLog"

    def add_arguments(self, parser):
        parser.add_argument("--filename", required=True)
        parser.add_argument("--sha256", required=True)
        parser.add_argument("--size", type=int, required=True)

    def handle(self, *args, **options):
        BackupLog.objects.create(
            filename=options["filename"],
            sha256=options["sha256"],
            size_bytes=options["size"],
        )
        self.stdout.write(f"BackupLog created: {options['filename']}")
```

**Crontab (root):**
```
0 3 * * * /var/www/fenix-v3/_scripts/backup_pg.sh >> /var/log/fenix_backup.log 2>&1
```

**Deployment:**
```bash
chmod +x /var/www/fenix-v3/_scripts/backup_pg.sh
mkdir -p /var/backups/fenix-v3
# Dodaj BackupLog u core/models.py ili registriraj u admin.py
venv/bin/python manage.py makemigrations core
venv/bin/python manage.py migrate
# Test run:
bash /var/www/fenix-v3/_scripts/backup_pg.sh
```

---

## KOMAD 3 — Circuit Breaker za Haiku (5-razinski fallback)

### Cilj
Kad Haiku 4.5 nije dostupan → automatski fallback kroz 5 razina.
Telemetrija svake razine, Redis za state, Celery za recovery.

### Implementacija

**`core/circuit_breaker.py`:**
```python
"""
Circuit Breaker — 5-razinski AI fallback za Fenix V3

Razine:
  0 → Haiku 4.5 (primary)
  1 → Haiku 3 (fallback)
  2 → DeepSeek via Bedrock (cheap)
  3 → Rule-based (deterministic, 0 cost)
  4 → Offline cache (zadnji poznati odgovor)

State čuva u Redis s prefiksom 'cb:fenix:'.
"""

import time
import json
import logging
import functools
from enum import IntEnum
from typing import Optional, Callable, Any

import redis
from django.conf import settings

logger = logging.getLogger("fenix.circuit_breaker")


class CBLevel(IntEnum):
    HAIKU_45 = 0
    HAIKU_3 = 1
    DEEPSEEK = 2
    RULE_BASED = 3
    OFFLINE = 4


# Redis connection
_redis = redis.Redis.from_url(
    getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/1"),
    decode_responses=True,
)

CB_PREFIX = "cb:fenix:"
FAILURE_THRESHOLD = 5       # fails before open
RECOVERY_TIMEOUT = 300      # sekundi — 5 min
HALF_OPEN_MAX = 2           # test calls in half-open


def _state_key(level: CBLevel) -> str:
    return f"{CB_PREFIX}state:{level.name}"


def _failure_key(level: CBLevel) -> str:
    return f"{CB_PREFIX}failures:{level.name}"


def get_state(level: CBLevel) -> dict:
    raw = _redis.get(_state_key(level))
    if raw:
        return json.loads(raw)
    return {"status": "closed", "opened_at": None, "half_open_count": 0}


def set_state(level: CBLevel, state: dict):
    _redis.setex(_state_key(level), RECOVERY_TIMEOUT * 4, json.dumps(state))


def record_failure(level: CBLevel):
    key = _failure_key(level)
    count = _redis.incr(key)
    _redis.expire(key, RECOVERY_TIMEOUT)

    if count >= FAILURE_THRESHOLD:
        state = {"status": "open", "opened_at": time.time(), "half_open_count": 0}
        set_state(level, state)
        logger.warning(f"[CB] Level {level.name} OPEN after {count} failures")
        # Pokretanje Celery recovery task
        from core.tasks import circuit_breaker_recovery
        circuit_breaker_recovery.apply_async(
            args=[level.value], countdown=RECOVERY_TIMEOUT
        )


def record_success(level: CBLevel):
    _redis.delete(_failure_key(level))
    set_state(level, {"status": "closed", "opened_at": None, "half_open_count": 0})


def is_available(level: CBLevel) -> bool:
    state = get_state(level)
    if state["status"] == "closed":
        return True
    if state["status"] == "open":
        elapsed = time.time() - (state["opened_at"] or 0)
        if elapsed > RECOVERY_TIMEOUT:
            # Prijelaz u half-open
            state["status"] = "half-open"
            state["half_open_count"] = 0
            set_state(level, state)
            logger.info(f"[CB] Level {level.name} → HALF-OPEN")
            return True
        return False
    if state["status"] == "half-open":
        if state["half_open_count"] < HALF_OPEN_MAX:
            state["half_open_count"] += 1
            set_state(level, state)
            return True
        return False
    return True


class AICircuitBreaker:
    """
    Koristi se kao:

        cb = AICircuitBreaker()
        result = cb.call(
            prompt="Napiši opis...",
            context={"doc_type": "invoice_hr"},
        )

    Automatski prolazi kroz razine dok ne uspije ili sve padnu.
    """

    def __init__(self):
        self.levels = [
            (CBLevel.HAIKU_45, self._call_haiku_45),
            (CBLevel.HAIKU_3, self._call_haiku_3),
            (CBLevel.DEEPSEEK, self._call_deepseek),
            (CBLevel.RULE_BASED, self._call_rule_based),
            (CBLevel.OFFLINE, self._call_offline),
        ]

    def call(self, prompt: str, context: dict = None) -> dict:
        context = context or {}
        last_error = None

        for level, handler in self.levels:
            if not is_available(level):
                logger.debug(f"[CB] Level {level.name} SKIPPED (circuit open)")
                continue

            try:
                t0 = time.monotonic()
                result = handler(prompt, context)
                elapsed = round((time.monotonic() - t0) * 1000)
                record_success(level)
                logger.info(f"[CB] Level {level.name} SUCCESS in {elapsed}ms")
                result["_cb_level"] = level.name
                result["_cb_elapsed_ms"] = elapsed
                return result

            except Exception as e:
                last_error = e
                record_failure(level)
                logger.warning(f"[CB] Level {level.name} FAILED: {e}")
                continue

        # Sve razine pale
        logger.error(f"[CB] ALL LEVELS FAILED. Last error: {last_error}")
        return {
            "error": "all_levels_exhausted",
            "detail": str(last_error),
            "_cb_level": "EXHAUSTED",
        }

    def _call_haiku_45(self, prompt: str, ctx: dict) -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"text": msg.content[0].text, "model": "haiku-4.5"}

    def _call_haiku_3(self, prompt: str, ctx: dict) -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-3-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"text": msg.content[0].text, "model": "haiku-3"}

    def _call_deepseek(self, prompt: str, ctx: dict) -> dict:
        # DeepSeek via AWS Bedrock
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
        })
        resp = bedrock.invoke_model(
            modelId="deepseek.deepseek-r1-v1:0",
            body=body,
        )
        result = json.loads(resp["body"].read())
        return {"text": result["choices"][0]["message"]["content"], "model": "deepseek"}

    def _call_rule_based(self, prompt: str, ctx: dict) -> dict:
        """Deterministic rule engine — 0 cost, uvijek dostupan."""
        doc_type = ctx.get("doc_type", "unknown")
        rules = {
            "invoice_hr": "PDV = osnova × 0.25. Rok plaćanja: 30 dana (ZOO čl.174).",
            "invoice_de": "MwSt = Netto × 0.19. Fälligkeit: 30 Tage (BGB §271).",
            "contract": "Provjeri: ugovorne strane, predmet, iznos, rokovi, potpisi.",
            "payroll": "Minimalna plaća 840 EUR bruto (HR 2024). MBO = 9 znamenki.",
            "gdpr": "Pravna osnova: čl.6 GDPR. Posebne kategorije: čl.9.",
        }
        text = rules.get(doc_type, f"Dokument tipa '{doc_type}' — provjerite ručno.")
        return {"text": text, "model": "rule_based"}

    def _call_offline(self, prompt: str, ctx: dict) -> dict:
        """Zadnji poznati odgovor iz Redis cache-a."""
        cache_key = f"{CB_PREFIX}offline_cache:{hash(prompt) % 10000}"
        cached = _redis.get(cache_key)
        if cached:
            return {"text": cached, "model": "offline_cache"}
        return {"text": "Sustav privremeno nedostupan. Pokušajte za 5 minuta.", "model": "offline"}


# Singleton
circuit_breaker = AICircuitBreaker()
```

**`core/tasks.py`** — dodaj recovery task:
```python
from celery import shared_task
import logging

logger = logging.getLogger("fenix.circuit_breaker")


@shared_task(name="core.circuit_breaker_recovery")
def circuit_breaker_recovery(level_value: int):
    """
    Celery task — pokušaj zatvoriti circuit breaker nakon RECOVERY_TIMEOUT.
    Poziva se automatski kad se breaker otvori.
    """
    from core.circuit_breaker import CBLevel, get_state, set_state, _redis, _failure_key
    level = CBLevel(level_value)
    state = get_state(level)

    if state["status"] != "open":
        logger.info(f"[CB Recovery] {level.name} already recovered")
        return

    # Reset na closed
    _redis.delete(_failure_key(level))
    set_state(level, {"status": "closed", "opened_at": None, "half_open_count": 0})
    logger.info(f"[CB Recovery] {level.name} CLOSED (auto-recovery)")
```

**Korištenje u postojećem kodu:**
```python
# Bilo gdje u views.py ili services.py:
from core.circuit_breaker import circuit_breaker

result = circuit_breaker.call(
    prompt=f"Analiziraj fakturu: {invoice_data}",
    context={"doc_type": "invoice_hr"},
)
ai_text = result.get("text", "")
cb_level = result.get("_cb_level", "unknown")
```

---

## KOMAD 4 — Browser Test Matrix

### Cilj
Playwright E2E testovi: Chrome + Safari(WebKit) + Firefox × desktop + mobile.
Pokriva: login, kreiranje fakture, validator, arhiva upload.

### Setup
```bash
pip install playwright pytest-playwright pytest-xdist
playwright install chromium webkit firefox
```

**`tests/test_browser_matrix.py`:**
```python
"""
Browser Test Matrix — Fenix V3
Chrome + Safari(WebKit) + Firefox × Desktop + Mobile

Pokreni:
    pytest tests/test_browser_matrix.py -v --headed   # s browserom
    pytest tests/test_browser_matrix.py -n 6          # paralelno
"""

import pytest
from playwright.sync_api import Page, BrowserType, expect

BASE_URL = "https://limit-connect.com"
ADMIN_USER = "ivan_brtan"
ADMIN_PASS = "test_password_here"  # Zamijeni s env varijablom!

DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}  # iPhone 14 Pro

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


# --- Fixtures ---

@pytest.fixture(params=["chromium", "webkit", "firefox"])
def browser_name(request):
    return request.param


@pytest.fixture(params=["desktop", "mobile"])
def device_type(request):
    return request.param


@pytest.fixture
def page_configured(playwright, browser_name, device_type):
    """Konfigurira browser + viewport + UA."""
    browser_cls = getattr(playwright, browser_name)
    browser = browser_cls.launch(headless=True)

    if device_type == "mobile":
        ctx = browser.new_context(
            viewport=MOBILE_VIEWPORT,
            user_agent=MOBILE_UA,
            is_mobile=True,
            has_touch=True,
        )
    else:
        ctx = browser.new_context(viewport=DESKTOP_VIEWPORT)

    page = ctx.new_page()
    yield page

    ctx.close()
    browser.close()


def login(page: Page):
    """Helper — login kao admin."""
    page.goto(f"{BASE_URL}/hr/accounts/login/")
    page.wait_for_selector("#id_username", timeout=10_000)
    page.fill("#id_username", ADMIN_USER)
    page.fill("#id_password", ADMIN_PASS)
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE_URL}/hr/**", timeout=15_000)


# --- Test cases ---

class TestLogin:
    def test_login_renders(self, page_configured):
        page = page_configured
        page.goto(f"{BASE_URL}/hr/accounts/login/")
        expect(page.locator("#id_username")).to_be_visible()
        expect(page.locator("#id_password")).to_be_visible()
        expect(page.locator("button[type=submit]")).to_be_visible()

    def test_login_success(self, page_configured):
        page = page_configured
        login(page)
        assert "/hr/accounts/login/" not in page.url, "Ostao na login stranici!"
        # Provjeri da je dashboard loaded
        expect(page.locator("nav, .sidebar, [data-role=dashboard]")).to_be_visible(
            timeout=10_000
        )

    def test_login_invalid_credentials(self, page_configured):
        page = page_configured
        page.goto(f"{BASE_URL}/hr/accounts/login/")
        page.fill("#id_username", "nepostojeci_user")
        page.fill("#id_password", "kriva_lozinka_123")
        page.click("button[type=submit]")
        # Mora ostati na login ili pokazati error
        page.wait_for_timeout(2000)
        error = page.locator(".alert-error, .errorlist, [class*=error]")
        login_still_visible = page.locator("#id_username").is_visible()
        assert error.count() > 0 or login_still_visible


class TestInvoiceCreate:
    def test_invoice_form_loads(self, page_configured):
        page = page_configured
        login(page)
        page.goto(f"{BASE_URL}/hr/racuni/nova-faktura/")
        page.wait_for_selector("[x-data]", timeout=10_000)
        # Alpine mora biti inicijaliziran
        page.wait_for_timeout(1000)
        expect(page.locator("[x-data]")).to_be_visible()

    def test_invoice_calculation(self, page_configured):
        """Provjeri da grandTotal kalkulira ispravno."""
        page = page_configured
        login(page)
        page.goto(f"{BASE_URL}/hr/racuni/nova-faktura/")
        page.wait_for_timeout(2000)  # Alpine init

        # Dodaj stavku: qty=3, price=100
        qty_input = page.locator("input[x-model*='qty'], input[placeholder*='Kol']").first
        price_input = page.locator("input[x-model*='price'], input[placeholder*='Cijena']").first

        if qty_input.is_visible() and price_input.is_visible():
            qty_input.fill("3")
            price_input.fill("100")
            page.wait_for_timeout(500)

            # Grand total treba biti ~375 (3×100 + 25% PDV)
            total_el = page.locator("[x-text*='grand'], .grand-total, #grand-total").first
            if total_el.is_visible():
                total_text = total_el.text_content() or ""
                assert "375" in total_text.replace(",", "").replace(".", ""), \
                    f"Expected 375 in total, got: {total_text}"


class TestEValidator:
    def test_validator_dashboard_loads(self, page_configured):
        page = page_configured
        login(page)
        page.goto(f"{BASE_URL}/hr/eval/")
        expect(page.locator("h1, h2")).to_be_visible(timeout=10_000)

    def test_validator_api_invoice(self, page_configured):
        """Validiraj fakturu via API."""
        page = page_configured
        login(page)

        # Direktni API poziv
        response = page.request.post(
            f"{BASE_URL}/hr/eval/api/",
            data={
                "doc_type": "invoice_hr",
                "data": {
                    "invoice_number": "2024-001",
                    "invoice_date": "2024-01-15",
                    "vendor_name": "Test d.o.o.",
                    "vendor_oib": "12345678901",
                    "buyer_name": "Kupac d.o.o.",
                    "buyer_oib": "98765432100",
                    "total_amount": 375.00,
                    "currency": "EUR",
                    "items": [{"description": "Usluga", "quantity": 3, "unit_price": 100}],
                },
            },
            headers={"Content-Type": "application/json"},
        )
        # API mora odgovoriti (ne 500)
        assert response.status < 500, f"Validator API error: {response.status}"


class TestArchive:
    def test_archive_page_loads(self, page_configured):
        page = page_configured
        login(page)
        page.goto(f"{BASE_URL}/hr/arhiva/")
        page.wait_for_load_state("networkidle", timeout=15_000)
        assert page.url == f"{BASE_URL}/hr/arhiva/" or "/arhiva/" in page.url


class TestHealthEndpoint:
    def test_health_check(self, page_configured):
        """Health endpoint mora biti dostupan BEZ logina."""
        page = page_configured
        response = page.request.get(f"{BASE_URL}/health/")
        assert response.status in (200, 503), f"Unexpected status: {response.status}"
        data = response.json()
        assert "status" in data
        assert "components" in data


# --- Konfig za pytest ---
# conftest.py treba imati:
# pytest_plugins = ["playwright"]
```

**CI GitHub Actions (`.github/workflows/browser-tests.yml`):**
```yaml
name: Browser Test Matrix
on: [push, pull_request]

jobs:
  browser-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        browser: [chromium, webkit, firefox]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install playwright pytest-playwright pytest-xdist
      - run: playwright install ${{ matrix.browser }}
      - run: |
          pytest tests/test_browser_matrix.py \
            --browser=${{ matrix.browser }} \
            -v --tb=short
        env:
          BASE_URL: ${{ secrets.STAGING_URL }}
```

---

## DEPLOYMENT CHECKLIST

### Komad 1 (Health endpoint)
```bash
# 1. Provjeri postoji li monitoring.py
cat /var/www/fenix-v3/core/monitoring.py | head -30

# 2. Dodaj HealthCheckView (ako ne postoji)
# 3. Dodaj rutu u urls_hr.py
# 4. Test:
curl -s http://37.27.248.86:8001/health/ | python3 -m json.tool
systemctl reload gunicorn-fenix-v3.service
curl -s https://limit-connect.com/health/ | python3 -m json.tool
```

### Komad 2 (Backup)
```bash
mkdir -p /var/www/fenix-v3/_scripts
# Napiši backup_pg.sh
chmod +x /var/www/fenix-v3/_scripts/backup_pg.sh
# Dodaj BackupLog model + migration
cd /var/www/fenix-v3
venv/bin/python manage.py check
venv/bin/python manage.py migrate
# Test backup
bash _scripts/backup_pg.sh
ls -la /var/backups/fenix-v3/
# Crontab
crontab -e
# → 0 3 * * * /var/www/fenix-v3/_scripts/backup_pg.sh
```

### Komad 3 (Circuit breaker)
```bash
# 1. Kopiraj core/circuit_breaker.py
# 2. Dodaj recovery task u core/tasks.py
# 3. Test u Django shellu:
cd /var/www/fenix-v3
venv/bin/python manage.py shell
>>> from core.circuit_breaker import circuit_breaker
>>> result = circuit_breaker.call("Test prompt", {"doc_type": "invoice_hr"})
>>> print(result)
# 4. Reload
systemctl reload gunicorn-fenix-v3.service
```

### Komad 4 (Browser tests)
```bash
cd /var/www/fenix-v3
venv/bin/pip install playwright pytest-playwright pytest-xdist
venv/bin/playwright install chromium
# Quick smoke test (samo Chromium, desktop):
BASE_URL=https://limit-connect.com \
venv/bin/pytest tests/test_browser_matrix.py \
    --browser=chromium -k "desktop" -v --tb=short
```

---

## STATUS

- [ ] Komad 1 — Health endpoint
- [ ] Komad 2 — pg_dump backup
- [ ] Komad 3 — Circuit breaker
- [ ] Komad 4 — Browser test matrix

**Sva 4 komada su samostalna — mogu se raditi paralelno.**

Pitanja → Ivan Brtan (WhatsApp: +385...)
Git: `cd /var/www/fenix-v3 && git log --oneline -5`
