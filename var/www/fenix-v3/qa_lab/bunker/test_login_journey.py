"""
BUNKER LOGIN JOURNEY — headless probe
Prati cijeli login tok od otvaranja stranice do dashboarda.
Mjeri svaki korak, capture screenshot + console + network na svaki failure.
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

REPORT_DIR = Path("/var/www/fenix-v3/qa_lab/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    {
        "name": "Fenix V3 LIVE",
        "url": "https://limit-connect.com/hr/accounts/login/",
    },
    {
        "name": "Fenix V3 v3 alias",
        "url": "https://v3.limit-connect.com/hr/accounts/login/",
    },
]


async def probe_login(target):
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"bunker_{target['name'].replace(' ','_')}_{run_id}"
    report_path.mkdir(parents=True, exist_ok=True)

    console_log = []
    network_log = []
    errors = []
    timings = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 QALab-Playwright NO-LIMIT-probe"
        )
        page = await context.new_page()

        # --- capture everything ---
        page.on("console", lambda msg: console_log.append({
            "type": msg.type, "text": msg.text,
            "t": datetime.utcnow().isoformat()
        }))
        page.on("pageerror", lambda exc: errors.append({
            "type": "pageerror", "msg": str(exc),
            "t": datetime.utcnow().isoformat()
        }))
        page.on("request", lambda req: network_log.append({
            "event": "request", "method": req.method, "url": req.url,
            "t": datetime.utcnow().isoformat()
        }))
        page.on("response", lambda res: network_log.append({
            "event": "response", "status": res.status, "url": res.url,
            "t": datetime.utcnow().isoformat()
        }))

        # --- step 1: open ---
        t0 = time.time()
        try:
            resp = await page.goto(target["url"], wait_until="domcontentloaded", timeout=15000)
            timings["goto_ms"] = int((time.time() - t0) * 1000)
            timings["http_status"] = resp.status if resp else None
        except Exception as e:
            errors.append({"type": "goto_failed", "msg": str(e)})
            timings["goto_ms"] = int((time.time() - t0) * 1000)

        await page.screenshot(path=str(report_path / "01_loaded.png"), full_page=True)

        # --- step 2: wait for bunker JS ---
        t1 = time.time()
        try:
            await page.wait_for_function(
                "typeof window.PublicKeyCredential !== 'undefined'", timeout=5000
            )
            timings["webauthn_available_ms"] = int((time.time() - t1) * 1000)
        except Exception as e:
            errors.append({"type": "webauthn_not_available", "msg": str(e)})

        # --- step 3: form visible? ---
        has_email = await page.query_selector('input[type="email"], input[name="username"]')
        has_pwd = await page.query_selector('input[type="password"]')
        has_bunker = await page.query_selector('[x-data*="bunker"]')

        timings["has_email_input"] = bool(has_email)
        timings["has_password_input"] = bool(has_pwd)
        timings["has_bunker_element"] = bool(has_bunker)

        # --- step 4: measure interactivity ---
        t2 = time.time()
        try:
            await page.wait_for_selector('input[type="email"], input[name="username"]',
                                           timeout=5000, state="visible")
            timings["email_visible_ms"] = int((time.time() - t2) * 1000)
        except Exception as e:
            errors.append({"type": "email_not_visible", "msg": str(e)})

        await page.screenshot(path=str(report_path / "02_form_ready.png"), full_page=True)

        # --- step 5: Bunker startup probe ---
        t3 = time.time()
        try:
            alpine_state = await page.evaluate("""
                () => {
                  const el = document.querySelector('[x-data*="bunker"]');
                  if (!el || !el._x_dataStack) return { found: false };
                  const data = el._x_dataStack[0];
                  return {
                    found: true,
                    supported: data.supported ?? null,
                    checking: data.checking ?? null,
                    hasDevice: data.hasDevice ?? null,
                    error: data.error ?? null,
                  };
                }
            """)
            timings["alpine_state"] = alpine_state
            timings["alpine_read_ms"] = int((time.time() - t3) * 1000)
        except Exception as e:
            errors.append({"type": "alpine_read_failed", "msg": str(e)})

        await browser.close()

    # --- write full report ---
    report = {
        "run_id": run_id,
        "target": target,
        "timings": timings,
        "errors": errors,
        "console_lines": len(console_log),
        "network_events": len(network_log),
        "console": console_log[-50:],
        "network": [n for n in network_log if n.get("status") and n["status"] >= 400][:30],
    }
    (report_path / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (report_path / "console.log").write_text(
        "\n".join(f"[{l['type']}] {l['text']}" for l in console_log)
    )

    # --- print summary ---
    print("=" * 70)
    print(f"TARGET: {target['name']}  ({target['url']})")
    print(f"REPORT: {report_path}")
    print(f"goto       : {timings.get('goto_ms')} ms (HTTP {timings.get('http_status')})")
    print(f"WebAuthn   : {timings.get('webauthn_available_ms')} ms")
    print(f"email visib: {timings.get('email_visible_ms')} ms")
    print(f"has_email_input: {timings.get('has_email_input')}")
    print(f"has_password_input: {timings.get('has_password_input')}")
    print(f"has_bunker_element: {timings.get('has_bunker_element')}")
    print(f"alpine_state: {timings.get('alpine_state')}")
    print(f"Errors: {len(errors)}")
    for e in errors:
        print(f"  ERR [{e['type']}] {e['msg'][:120]}")
    if [n for n in network_log if n.get("status") and n["status"] >= 400]:
        print("HTTP 4xx/5xx:")
        for n in network_log[:10]:
            if n.get("status") and n["status"] >= 400:
                print(f"  {n['status']} {n['url'][:80]}")
    print("=" * 70)
    return report


async def main():
    results = []
    for target in TARGETS:
        try:
            r = await probe_login(target)
            results.append(r)
        except Exception as e:
            print(f"PROBE FAILED for {target['name']}: {e}")

    # aggregate
    agg_path = REPORT_DIR / f"bunker_AGGREGATE_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    agg_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nAGGREGATE REPORT: {agg_path}")

if __name__ == "__main__":
    asyncio.run(main())
