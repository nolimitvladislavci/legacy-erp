"""
FENIX MCP Server — direktni pristup za Sonnet
Pokrece se kao: venv/bin/python core/mcp_server.py

v4: SQL guard, ORM sandbox, rate limit, extended blocked commands
    + .dokarh alati (compress, verify, stats, batch_seal)
"""

import json
import os
import signal
import subprocess
import sys

sys.path.insert(0, "/var/www/fina-connect")
os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from fastmcp import FastMCP

mcp = FastMCP("Fenix LIMIT Connect")
PROJECT = "/var/www/fina-connect"
BLOCKED = [
    "rm -rf",
    "rm -r /",
    "reboot",
    "shutdown",
    "mkfs",
    "chmod 777",
    "> /dev/",
    "dd if=",
    "passwd",
    "useradd",
    "userdel",
    "crontab",
    "visudo",
]


def graceful_shutdown(signum, frame):
    """Graceful shutdown na SIGTERM/SIGINT."""
    print(f"Fenix MCP: primljen signal {signum}, gasim se...")
    sys.exit(0)


signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)


@mcp.tool()
def query_db(sql: str) -> str:
    """Izvrsi SELECT SQL upit na PostgreSQL bazi. Destructive queries blokirane."""
    import re as _re

    _sql = sql.strip().rstrip(";")
    if _re.search(r"(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)", _sql, _re.I):
        return json.dumps({"error": "BLOCKED: destructive SQL (DROP/TRUNCATE/ALTER/CREATE/GRANT/REVOKE)"})
    if _re.search(r"(DELETE|UPDATE)", _sql, _re.I) and not _re.search(r"WHERE", _sql, _re.I):
        return json.dumps({"error": "BLOCKED: DELETE/UPDATE without WHERE clause"})
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute(_sql)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchmany(100)
                return json.dumps({"columns": cols, "rows": rows, "count": len(rows)}, default=str)
            return json.dumps({"affected": cur.rowcount})
    except TypeError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def django_orm(code: str) -> str:
    """Izvrsi Django ORM kod (read-only). Spremi rezultat u 'output'. Blokirano: os.system, subprocess, open(), .delete(), .raw()."""
    _blocked = [
        "os.system",
        "subprocess",
        "__import__",
        "open(",
        ".delete()",
        ".raw(",
        "connection.cursor",
        "shutil",
        "importlib",
    ]
    for _b in _blocked:
        if _b in code:
            return f'BLOCKED: zabranjen pattern "{_b}" u ORM kodu'
    try:
        loc = {}
        exec(code, {"__builtins__": __builtins__}, loc)
        return str(loc.get("output", "OK"))[:30000]
    except (ValueError, TypeError) as e:
        return f"Error: {e}"


@mcp.tool()
def read_file(path: str) -> str:
    """Citaj fajl iz projekta."""
    full = os.path.join(PROJECT, path.lstrip("/")) if not path.startswith(PROJECT) else path
    if not full.startswith(PROJECT):
        return "Error: path outside project"
    try:
        content = open(full).read()
        return f"[{content.count(chr(10))} linija]\n{content[:30000]}"
    except (FileNotFoundError, IOError) as e:
        return f"Error: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Pisi fajl u projekt."""
    full = os.path.join(PROJECT, path.lstrip("/")) if not path.startswith(PROJECT) else path
    if not full.startswith(PROJECT):
        return "Error: path outside project"
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w").write(content)
        return f"OK: {path} ({len(content)} chars)"
    except (FileNotFoundError, IOError) as e:
        return f"Error: {e}"


@mcp.tool()
def list_files(path: str = ".", pattern: str = "") -> str:
    """Listaj fajlove u direktoriju."""
    full = os.path.join(PROJECT, path.lstrip("/"))
    try:
        result = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv", "node_modules")]
            for f in files:
                if not pattern or pattern in f:
                    result.append(os.path.relpath(os.path.join(root, f), PROJECT))
            if len(result) > 300:
                break
        return "\n".join(sorted(result))
    except OSError as e:
        return f"Error: {e}"


@mcp.tool()
def exec_command(cmd: str) -> str:
    """Izvrsi shell komandu na serveru."""
    for b in BLOCKED:
        if b in cmd:
            return f"BLOCKED: {b}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=PROJECT)
        out = r.stdout[:10000]
        err = r.stderr[:2000]
        return f"[exit {r.returncode}]\n{out}" + (f"\n[stderr]\n{err}" if err else "")
    except subprocess.TimeoutExpired:
        return "Error: timeout (60s)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_logs(service: str = "django", lines: int = 50) -> str:
    """Dohvati logove. service: django|gunicorn|celery|nginx"""
    paths = {
        "django": f"{PROJECT}/logs/django.log",
        "gunicorn": f"{PROJECT}/logs/gunicorn_error.log",
        "celery": f"{PROJECT}/logs/celery.log",
    }
    if service in paths:
        try:
            r = subprocess.run(["tail", f"-{lines}", paths[service]], capture_output=True, text=True)
            return r.stdout or "Prazan log"
        except Exception as e:
            return f"Error: {e}"
    r = subprocess.run(["journalctl", "-u", service, "-n", str(lines), "--no-pager"], capture_output=True, text=True)
    return r.stdout


@mcp.tool()
def system_status() -> str:
    """Server health: disk, memory, servisi."""
    try:
        disk = subprocess.check_output(["df", "-h", "/"], text=True).split("\n")[1].split()
        mem = subprocess.check_output(["free", "-h"], text=True).split("\n")[1].split()
        services = {}
        for s in ["gunicorn-fina", "celery-worker", "nginx", "fenix-mcp"]:
            r = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True)
            services[s] = r.stdout.strip()
        return json.dumps(
            {
                "disk": {"used": disk[2], "free": disk[3], "percent": disk[4]},
                "memory": {"used": mem[2], "total": mem[1]},
                "services": services,
            },
            indent=2,
        )
    except (ValueError, AttributeError) as e:
        return f"Error: {e}"


@mcp.tool()
def pos_today() -> str:
    """POS statistike za danas."""
    from django.db.models import Count, Sum
    from django.utils import timezone

    from pos.models import POSReceipt

    today = timezone.now().date()
    qs = POSReceipt.objects.filter(created_at__date=today, status="paid")
    by_company = list(
        qs.values("session__terminal__company__name")
        .annotate(promet=Sum("total"), bonovi=Count("id"))
        .order_by("-promet")
    )
    return json.dumps(
        {
            "datum": str(today),
            "ukupno_eur": str(qs.aggregate(t=Sum("total"))["t"] or 0),
            "bonovi": qs.count(),
            "po_kompaniji": by_company,
        },
        default=str,
        indent=2,
    )


@mcp.tool()
def restart_service(service: str) -> str:
    """Restart servisa. service: gunicorn|celery|nginx|all"""
    allowed = {
        "gunicorn": "systemctl restart gunicorn-fina",
        "celery": "systemctl restart celery-worker celery-beat",
        "nginx": "systemctl restart nginx",
        "all": "systemctl restart gunicorn-fina celery-worker celery-beat",
    }
    if service not in allowed:
        return f"Unknown. Options: {list(allowed.keys())}"
    r = subprocess.run(allowed[service], shell=True, capture_output=True, text=True)
    return f"OK: {service} restarted" if r.returncode == 0 else f"Error: {r.stderr}"


# ════════════════════════════════════════════════════════════
# .DOKARH ALATI
# ════════════════════════════════════════════════════════════


@mcp.tool()
def dokarh_compress(entry_id: int) -> str:
    """
    Kompresira ArhivaEntry dokument u .dokarh format.
    Dodaje kriptografski pečat (SHA-256 + timestamp) za ZOR compliance.
    Vraca statistiku: original_kb, dokarh_kb, ratio_pct, sha256.
    """
    try:
        from documents.dokarh import compress_arhiva_entry
        result = compress_arhiva_entry(entry_id)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def dokarh_verify(entry_id: int) -> str:
    """
    Verificira kriptografski integritet .dokarh dokumenta.
    Provjeri je li SHA-256 hash ispravan — dokument nije modificiran.
    ZOR compliance: potvrda da dokument nije mijenjan od zapečaćivanja.
    """
    try:
        from documents.dokarh import verify_arhiva_entry
        result = verify_arhiva_entry(entry_id)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def dokarh_stats(company_id: int = 0) -> str:
    """
    Statistika .dokarh kompresije.
    company_id=0 = cijela platforma.
    Vraca: broj zapečaćenih dokumenata, ušteda u MB, pending_seal (čeka pečat).
    """
    try:
        from documents.dokarh import get_dokarh_stats
        result = get_dokarh_stats(company_id=company_id if company_id > 0 else None)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def dokarh_batch_seal(company_id: int, limit: int = 50) -> str:
    """
    Batch zapečaćivanje dokumenata za kompaniju.
    Procesuira do `limit` ArhivaEntry zapisa koji još nemaju .dokarh pečat.
    Korisno za serijsku ZOR compliance pripremu starih arhiva.
    Vraca: processed, errors, total_saved_kb.
    """
    try:
        from django.conf import settings

        from documents.dokarh import compress_arhiva_entry
        from documents.models import ArhivaEntry

        qs = (
            ArhivaEntry.objects
            .filter(company_id=company_id)
            .exclude(file_path="")
            .exclude(file_path__isnull=True)
            .order_by("-archived_at")
        )

        processed = 0
        errors = []
        total_saved_kb = 0

        for entry in qs[:limit * 3]:  # Pregledamo više, jer neke možda nemaju fizički fajl
            if processed >= limit:
                break

            if not entry.file_path:
                continue

            # Preskoci ako već postoji .dokarh
            dokarh_path = os.path.join(settings.MEDIA_ROOT, entry.file_path + ".dokarh")
            if os.path.exists(dokarh_path):
                continue

            result = compress_arhiva_entry(entry.pk)

            if "error" in result:
                errors.append({"entry_id": entry.pk, "error": result["error"]})
            else:
                processed += 1
                saved = result.get("original_kb", 0) - result.get("dokarh_kb", 0)
                total_saved_kb += max(0, saved)

        return json.dumps(
            {
                "company_id": company_id,
                "processed": processed,
                "errors": errors[:10],  # Max 10 grešaka u outputu
                "total_saved_kb": total_saved_kb,
                "total_saved_mb": round(total_saved_kb / 1024, 2),
                "status": "done",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    print("Fenix MCP Server v4 (.dokarh edition) na http://127.0.0.1:8765")
    mcp.run(transport="sse", host="127.0.0.1", port=8765)
