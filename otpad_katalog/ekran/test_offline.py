#!/usr/bin/env python3
"""Test rada bez veze (Playwright + Chromium): red slika na uređaju (IndexedDB) i servisni worker.

Pokretanje:  BRANDS_JS=<put/do/brands.js> python3 -I test_offline.py
Kriteriji (upisani prije pokretanja):
  O1 /sw.js se poslužuje (JS, no-cache) · O2 worker se aktivira i sprema ljusku
  O3 bez veze: slika se sprema na uređaj, poruka 'Nema veze…', traka 'Na uređaju čeka 1 slika', u bazi 0 slika
  O4 aplikacija se otvara i BEZ veze (reload), a red na uređaju preživljava ponovno učitavanje
  O5 kad se veza vrati: red se sam isprazni, u bazi 1 slika, traka nestaje, kartica pokazuje sliku
  O6 ista slika dvaput u redu → u bazi 1 (duplikat se tretira kao poslan), red prazan
  O7 slika za dio koji je u međuvremenu otišao u škart → odbijena s porukom, red prazan (ne vrti se u krug)
  O8 dok je poslužitelj nedostupan (5xx/odbijena veza), slika ostaje u redu · O9 0 grešaka u konzoli, 0 vodoravnog skrola
"""
import glob
import os
import shutil
import signal
import sys
import tempfile

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tamno_ekran as TE  # noqa: E402

H = TE.H
ok = H.ok


def chromium_put():
    for c in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")):
        return c
    return None


def novi_dio(naziv: str) -> int:
    auto = TE.q("SELECT id FROM otpad_vozilo ORDER BY id LIMIT 1")[0][0]
    return TE.zahtjev("POST", "/api/dio/rodi", {"otpad_vozilo_id": auto, "naziv": naziv})[1]["id"]


def broj_slika(d: int) -> int:
    return TE.q("SELECT count(*) FROM dio_slika WHERE otpad_dio_id=%s", d)[0][0]


def otvori_dio(page, d: int, naziv: str):
    page.click("#tab-radu")
    page.get_by_role("heading", name=naziv).first.wait_for()
    page.locator("#radu-lista .kartica").filter(has_text=naziv).first.get_by_role("button", name="Otvori").click()
    expect(page.locator("#dio-kartica h3").first).to_contain_text(naziv)


def main() -> int:
    brands = os.environ.get("BRANDS_JS", "")
    try:
        TE.postavi_bazu(brands)
    except Exception as e:                                                       # noqa: BLE001
        print(f"PRIPREMA PALA: {e}"); return 2
    mapa = tempfile.mkdtemp(prefix="otpad_foto_")
    for k in range(6):
        open(f"{mapa}/{k}.jpg", "wb").write(TE.jpeg(60 + k))
    slike = tempfile.mkdtemp(prefix="otpad_slike_"); os.chmod(slike, 0o700)
    srv = TE.pokreni(TE.PORT, slike)
    try:
        import urllib.request
        with urllib.request.urlopen(TE.URL + "/sw.js") as o:
            ok("O1 /sw.js: 200, JavaScript, no-cache", o.status == 200 and "javascript" in o.headers.get("Content-Type", "") and "no-cache" in o.headers.get("Cache-Control", ""))
        d = novi_dio("Alternator offline")
        with sync_playwright() as p:
            br = p.chromium.launch(executable_path=chromium_put()) if chromium_put() else p.chromium.launch()
            ctx = br.new_context(viewport={"width": 390, "height": 800})
            page = ctx.new_page()
            greske = []
            page.on("console", lambda m: greske.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
            page.on("pageerror", lambda e: greske.append(str(e)))
            page.on("dialog", lambda dl: dl.accept())
            page.goto(TE.URL + "/"); page.wait_for_load_state("networkidle")
            ok("O2 servisni worker se aktivira", page.evaluate("navigator.serviceWorker.ready.then(r => !!r.active)") is True)
            ulaz = 'input[aria-label="Dodaj slike: Slike dijela"]'
            otvori_dio(page, d, "Alternator offline")

            # O3: bez veze
            ctx.set_offline(True)
            page.locator(ulaz).set_input_files(f"{mapa}/0.jpg")
            expect(page.locator("#dio-kartica .poruka.info").first).to_contain_text("Nema veze", timeout=15000)
            ok("O3 bez veze: poruka 'Nema veze… spremljeno na uređaju'", True)
            expect(page.locator(".red-traka")).to_contain_text("Na uređaju čeka 1 slika")
            ok("O3 traka 'Na uređaju čeka 1 slika'", True)
            ok("O3 u bazi još nema slike", broj_slika(d) == 0)

            # O4: ponovno učitavanje bez veze
            page.reload()
            page.wait_for_selector("#tab-novi")
            ok("O4 aplikacija se otvara i bez veze", page.title() == "Auto otpad — dijelovi")
            expect(page.locator(".red-traka")).to_contain_text("Na uređaju čeka 1 slika")
            ok("O4 red na uređaju je preživio ponovno učitavanje", True)

            # O5: veza se vraća
            ctx.set_offline(False)
            for _ in range(80):
                if broj_slika(d) == 1:
                    break
                page.wait_for_timeout(250)
            ok("O5 veza se vratila: slika je sama stigla na poslužitelj", broj_slika(d) == 1, str(broj_slika(d)))
            page.wait_for_timeout(1500)
            ok("O5 traka je nestala ili javlja 'Poslano'", (not page.is_visible(".red-traka")) or "Poslano" in page.inner_text(".red-traka"), page.inner_text(".red-traka") if page.is_visible(".red-traka") else "")

            # O6: duplikat u redu
            page.reload(); page.wait_for_selector("#tab-novi")
            otvori_dio(page, d, "Alternator offline")
            ctx.set_offline(True)
            for _ in range(2):
                page.locator(ulaz).set_input_files(f"{mapa}/1.jpg")
                expect(page.locator("#dio-kartica .poruka.info").first).to_contain_text("Nema veze", timeout=15000)
            expect(page.locator(".red-traka")).to_contain_text("Na uređaju čeka 2 slike")
            ctx.set_offline(False)
            for _ in range(80):
                if broj_slika(d) == 2 and not page.is_visible(".red-traka button"):
                    break
                page.wait_for_timeout(250)
            ok("O6 ista slika dvaput u redu → u bazi samo jedna nova (ukupno 2), red prazan", broj_slika(d) == 2 and not page.is_visible(".red-traka button"), str(broj_slika(d)))

            # O7: dio u međuvremenu u škartu
            d2 = novi_dio("Far offline")
            page.reload(); page.wait_for_selector("#tab-novi")
            otvori_dio(page, d2, "Far offline")
            ctx.set_offline(True)
            page.locator(ulaz).set_input_files(f"{mapa}/2.jpg")
            expect(page.locator("#dio-kartica .poruka.info").first).to_contain_text("Nema veze", timeout=15000)
            TE.zahtjev("POST", f"/api/dio/{d2}/predradnja", {"vrsta": "TESTIRAN", "stanje": "PAD"})
            ctx.set_offline(False)
            expect(page.locator(".red-traka")).to_contain_text("Odbijeno 1", timeout=30000)
            ok("O7 slika za dio u škartu je odbijena s porukom, red je prazan", broj_slika(d2) == 0 and not page.is_visible(".red-traka button"), page.inner_text(".red-traka"))

            # O8: poslužitelj nedostupan (ne mreža preglednika), slika ostaje u redu
            d3 = novi_dio("Branik offline")
            page.reload(); page.wait_for_selector("#tab-novi")
            otvori_dio(page, d3, "Branik offline")
            srv.terminate(); srv.wait(timeout=10)                  # poslužitelj se gasi: zahtjevi padaju s odbijenom vezom
            page.locator(ulaz).set_input_files(f"{mapa}/3.jpg")
            expect(page.locator("#dio-kartica .poruka.info").first).to_contain_text("Nema veze", timeout=20000)
            ok("O8 poslužitelj ugašen: slika ide u red, ne gubi se", True)
            srv = TE.pokreni(TE.PORT, slike)
            for _ in range(160):
                if broj_slika(d3) == 1:
                    break
                page.wait_for_timeout(250)
            page.click("#tab-trazi")
            for _ in range(10):
                if broj_slika(d3) == 1:
                    break
                page.evaluate("window.dispatchEvent(new Event('online'))"); page.wait_for_timeout(1000)
            ok("O8 kad poslužitelj ponovno radi, slika stiže", broj_slika(d3) == 1, str(broj_slika(d3)))

            ok("O9 0 grešaka u konzoli", not greske, str(greske)[:300])
            v = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok("O9 nema vodoravnog skrola", v <= 0, f"{v}px")
            br.close()
    finally:
        try:
            srv.send_signal(signal.SIGTERM)
        except Exception:                                                         # noqa: BLE001
            pass
        shutil.rmtree(slike, ignore_errors=True); shutil.rmtree(mapa, ignore_errors=True)
        try:
            H.psql("postgres", f"DROP DATABASE IF EXISTS {TE.DB}")
        except Exception as e:                                                   # noqa: BLE001
            print(f"upozorenje: čišćenje baze: {e}")
    print(f"\nUKUPNO {H.PASS + H.FAIL} · PROŠLO {H.PASS} · PALO {H.FAIL}")
    return 1 if H.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
