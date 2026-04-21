"""
TIME MACHINE — smoke test runner + auto-rollback.
Pokreće kritične headless journey-e. Ako previše padne, git revert na HEAD~1.

Bez shadow-a na produkciji (opasno). Umjesto toga: smoke-before-deploy.
"""
import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

REPORT_DIR = Path("/var/www/fenix-v3/qa_lab/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://limit-connect.com"

# Kritični journey-i — ako pada, udruga gubi korisnike
JOURNEYS = [
    {
        "name": "landing_loads",
        "url": "/",
        "assert_selector": "body",
        "max_ms": 3000,
        "critical": True,
    },
    {
        "name": "login_page_loads",
        "url": "/hr/accounts/login/",
        "assert_selector": 'input[name="username"]',
        "max_ms": 3000,
        "critical": True,
    },
    {
        "name": "register_page_loads",
        "url": "/hr/accounts/register/",
        "assert_selector": "form",
        "max_ms": 3000,
        "critical": True,
    },
    {
        "name": "small_doors_recovery",
        "url": "/hr/accounts/small-doors/",
        "assert_selector": "body",
        "max_ms": 3000,
        "critical": True,
    },
    {
        "name": "no_limit_landing",
        "url": "https://no-limit.world/",
        "assert_selector": "#genesis",
        "max_ms": 5000,
        "critical": False,
    },
    {
        "name": "genesis_pdf_available",
        "url": "https://no-limit.world/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.pdf",
        "assert_status": 200,
        "max_ms": 3000,
        "critical": False,
    },
]


async def run_journey(page, j):
    url = j["url"] if j["url"].startswith("http") else BASE_URL + j["url"]
    t0 = time.time()
    result = {"name": j["name"], "url": url, "passed": False,
              "duration_ms": 0, "error": None}
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=j["max_ms"])
        result["http_status"] = resp.status if resp else None
        if "assert_status" in j and resp and resp.status != j["assert_status"]:
            result["error"] = f"Expected HTTP {j['assert_status']}, got {resp.status}"
        elif "assert_selector" in j:
            try:
                await page.wait_for_selector(j["assert_selector"], timeout=2000)
                result["passed"] = True
            except Exception:
                result["error"] = f"Selector not found: {j['assert_selector']}"
        else:
            result["passed"] = True
        result["duration_ms"] = int((time.time() - t0) * 1000)
        if result["duration_ms"] > j["max_ms"]:
            result["passed"] = False
            result["error"] = f"TOO SLOW: {result['duration_ms']}ms > {j['max_ms']}ms"
    except Exception as e:
        result["error"] = str(e)[:200]
        result["duration_ms"] = int((time.time() - t0) * 1000)
    return result


async def run_all():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report = {"run_id": run_id, "started_at": datetime.now(timezone.utc).isoformat(),
              "journeys": [], "summary": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        for j in JOURNEYS:
            r = await run_journey(page, j)
            r["critical"] = j["critical"]
            report["journeys"].append(r)
        await browser.close()

    total = len(report["journeys"])
    passed = sum(1 for r in report["journeys"] if r["passed"])
    critical_failed = sum(1 for r in report["journeys"]
                          if r["critical"] and not r["passed"])
    report["summary"] = {
        "total": total, "passed": passed, "failed": total - passed,
        "critical_failed": critical_failed,
    }
    report["should_rollback"] = critical_failed > 0

    report_path = REPORT_DIR / f"time_machine_{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2))
    latest = REPORT_DIR / "time_machine_latest.json"
    latest.write_text(json.dumps(report, indent=2))

    # print summary
    print("=" * 78)
    print(f"TIME MACHINE run {run_id}")
    print(f"Passed: {passed}/{total}  |  Critical failed: {critical_failed}")
    print("-" * 78)
    for r in report["journeys"]:
        marker = "OK " if r["passed"] else "!! "
        crit = "[CRITICAL]" if r["critical"] and not r["passed"] else ""
        err = f" -- {r['error']}" if r["error"] else ""
        print(f"  {marker} {r['duration_ms']:>5}ms  {r['name']:30}  {crit}{err}")
    print("=" * 78)
    return report


def auto_rollback_if_needed(report):
    if not report.get("should_rollback"):
        return False
    print("\n*** CRITICAL FAILURE - rollback triggered ***")
    try:
        # soft revert — napravi novi commit koji vrača HEAD~1
        subprocess.check_call(
            ["git", "-C", "/var/www/fenix-v3", "revert", "--no-edit", "HEAD"]
        )
        subprocess.check_call(
            ["systemctl", "reload", "gunicorn-fenix-v3.service"]
        )
        print("Revert done + service reloaded.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Rollback FAILED: {e}")
        return False


if __name__ == "__main__":
    import sys
    report = asyncio.run(run_all())
    if "--autorollback" in sys.argv:
        auto_rollback_if_needed(report)
    sys.exit(0 if not report["should_rollback"] else 1)
