"""
POS Chaos Test — Playwright E2E test za offline resilience.
Pokreni: cd /var/www/fina-connect && source venv/bin/activate && python test_pos_kaos.py
"""
import json
import time

from playwright.sync_api import sync_playwright

# --- KONFIGURACIJA ---
BASE_URL = "https://limit-connect.com"
EMAIL = "marija.limit@gmail.com"  # Konjik d.o.o. user
PASSWORD = "KaosTest2026!"
TERMINAL_ID = 1  # BLAGAJNA


def run_chaos_test():
    with sync_playwright() as p:
        print("=" * 60)
        print("  POS CHAOS TEST — Offline Resilience")
        print("=" * 60)

        print("\n[1] Podizem headless Chrome...")
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # ── KORAK 1: Login ──────────────────────────────────────────────────
        print("[2] Logiranje...")
        page.goto(f"{BASE_URL}/login/", wait_until="networkidle", timeout=15000)
        page.fill("input[name='email']", EMAIL)
        page.fill("input[name='password']", PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle", timeout=15000)
        print(f"    OK — URL: {page.url}")

        # ── KORAK 2: Otvori sesiju ako treba ────────────────────────────────
        print("[3] Otvaram POS terminal...")
        page.goto(f"{BASE_URL}/hr/pos/terminal/{TERMINAL_ID}/", wait_until="networkidle", timeout=15000)

        # Provjeri treba li otvoriti sesiju
        page_text = page.content()
        if "Otvori smjenu" in page_text or "opening_cash" in page_text:
            print("    Nema otvorene sesije — otvaram...")
            cash_input = page.locator("input[name='opening_cash']")
            if cash_input.exists():
                cash_input.fill("100")
            submit = page.locator("button[type='submit']")
            if submit.exists():
                submit.first.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                print(f"    Sesija otvorena. URL: {page.url}")
        else:
            print("    Sesija vec otvorena.")

        # ── KORAK 3: Quick POS ──────────────────────────────────────────────
        print("[4] Otvaranje Quick POS...")
        page.goto(f"{BASE_URL}/hr/pos/quick/{TERMINAL_ID}/", wait_until="networkidle", timeout=15000)
        assert "quick" in page.url or "pos" in page.url, f"Nismo na POS: {page.url}"
        print(f"    OK — {page.url}")

        # ── KORAK 4: Blagajnik + PIN ──────────────────────────────────────
        cashier_btns = page.locator(".cashier-btn")
        n_cashiers = cashier_btns.count()
        if n_cashiers > 0:
            print(f"[5] {n_cashiers} blagajnika — klikam prvog...")
            cashier_btns.first.click()
            time.sleep(0.5)
            # PIN modal se otvara — unesu PIN
            pin_modal = page.locator("#pinModal.show, #pinModal.qmodal.show")
            if pin_modal.exists():
                print("    PIN modal otvoren — unosim PIN 1234...")
                pin_input = page.locator("#pinModal input[type='password'], #pinModal input[type='number'], #pinInput")
                if pin_input.exists():
                    pin_input.first.fill("1234")
                    time.sleep(0.3)
                    # Submit PIN
                    pin_submit = page.locator("#pinModal button:has-text('OK'), #pinModal button[type='submit'], #pinSubmit")
                    if pin_submit.exists():
                        pin_submit.first.click()
                    else:
                        pin_input.first.press("Enter")
                    time.sleep(1)
                    print("    PIN unijet")
                else:
                    # Numpad — klik pinKey() gumbe
                    for d in "1234":
                        page.evaluate(f"pinKey('{d}')")
                        time.sleep(0.1)
                    page.evaluate("pinKey('ok')")
                    time.sleep(1.5)
                    print("    PIN unijet (numpad)")
        else:
            print("[5] Nema blagajnika — preskacemo")

        # ── KORAK 5: Dodaj artikle ──────────────────────────────────────────
        prod_btns = page.locator(".prod-btn")
        n_prods = prod_btns.count()
        print(f"[6] Artikli na ekranu: {n_prods}")

        if n_prods == 0:
            print("[FAIL] Nema artikala na POS-u!")
            page.screenshot(path="/tmp/kaos_no_products.png")
            browser.close()
            return False

        clicks = min(3, n_prods)
        for i in range(clicks):
            prod_btns.nth(i).click()
            time.sleep(0.3)
        print(f"    Dodano {clicks} artikala u kosaricu")
        time.sleep(0.5)

        # Provjeri stanje kosare
        pay_btn = page.locator("#payCash")
        pay_enabled = not pay_btn.is_disabled()
        print(f"    Gumb GOTOVINA enabled: {pay_enabled}")

        if not pay_enabled:
            print("[FAIL] GOTOVINA disabled — kosara prazna?")
            page.screenshot(path="/tmp/kaos_cart_empty.png")
            browser.close()
            return False

        # ── KORAK 6: KAOS — Offline ────────────────────────────────────────
        print("\n" + "!" * 50)
        print("  [7] KAOS: GASIM INTERNET!")
        print("!" * 50)
        context.set_offline(True)
        time.sleep(1)

        offline_class = page.evaluate("document.body.classList.contains('pos-offline')")
        print(f"    body.pos-offline: {offline_class}")

        # ── KORAK 7: Plati offline ─────────────────────────────────────────
        print("[8] Klik na GOTOVINA dok smo OFFLINE...")
        pay_btn.click()
        time.sleep(2)

        # ── KORAK 8: Verifikacija ──────────────────────────────────────────
        print("\n[9] VERIFIKACIJA:")

        # A) Success overlay
        overlay = page.locator("#successOverlay")
        overlay_has_show = page.evaluate("document.getElementById('successOverlay').classList.contains('show')")
        print(f"    a) Success overlay .show: {overlay_has_show}")

        # B) Bon #OFF tekst
        suc_text = page.evaluate("document.getElementById('sucNum')?.textContent || ''")
        print(f"    b) sucNum tekst: '{suc_text}'")
        has_off = "OFF" in suc_text

        # C) localStorage offline queue
        queue_raw = page.evaluate("localStorage.getItem('pos_offline_sales') || '[]'")
        try:
            queue = json.loads(queue_raw)
            queue_count = len(queue)
        except (json.JSONDecodeError, ValueError):
            queue_count = 0
        print(f"    c) Offline queue: {queue_count} prodaja(e)")
        if queue_count > 0:
            print(f"       Prva prodaja: {json.dumps(queue[0], indent=2)[:200]}")

        # D) Gumb stanje
        btn_disabled = pay_btn.is_disabled()
        print(f"    d) GOTOVINA disabled (anti-dblclick): {btn_disabled}")

        # ── REZULTAT ───────────────────────────────────────────────────────
        print("\n" + "=" * 50)
        if overlay_has_show and has_off and queue_count > 0:
            print("  [SUCCESS] SUSTAV PREZIVIO PAD MREZE!")
            print("  Racun spusten u offline queue.")
            print("  Overlay prikazuje 'Bon #OFF'.")
            result = True
        elif queue_count > 0:
            print("  [PARTIAL SUCCESS] Queue radi, overlay mozda zatvoren.")
            result = True
        else:
            print("  [FAIL] Offline prodaja NIJE uqueueirana!")
            page.screenshot(path="/tmp/kaos_fail.png")
            print("  Screenshot: /tmp/kaos_fail.png")
            result = False
        print("=" * 50)

        # ── KORAK 9: Vrati internet ────────────────────────────────────────
        print("\n[10] Vracam internet...")
        context.set_offline(False)
        time.sleep(4)

        queue_after = page.evaluate("localStorage.getItem('pos_offline_sales') || '[]'")
        try:
            queue_after_count = len(json.loads(queue_after))
        except (json.JSONDecodeError, ValueError):
            queue_after_count = -1
        print(f"     Queue nakon synca: {queue_after_count} (bilo {queue_count})")

        if queue_after_count == 0:
            print("     [SYNC OK] Offline prodaje sinkronizirane na server!")
        elif queue_after_count < queue_count:
            print("     [PARTIAL SYNC] Neke prodaje sinkronizirane.")
        else:
            print("     [SYNC PENDING] Queue jos nije isprazjen.")

        # Screenshot
        page.screenshot(path="/tmp/kaos_final.png")
        print("\n[DONE] Screenshot: /tmp/kaos_final.png")

        browser.close()
        return result


if __name__ == "__main__":
    success = run_chaos_test()
    exit(0 if success else 1)
