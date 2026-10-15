"""Harness za ekran IZA nginxa na /otpad/ (Basic prijava, prefiks se skida).

Pokretanje:  OTPAD_JAVNI=https://genesis.limit-connect.com OTPAD_KORISNIK=kelava OTPAD_LOZINKA=... python3 -I test_iza_nginxa.py
Provjerava (Ustav §12.4): preglednici koji su instalirani × 2 teme × 2 širine; konzola 0, neočekivanih 4xx 0, vodoravni skrol 0;
bez prijave 401; tok potvrde (dodaj pretince → vidljiva potvrda) i tok greške (neispravan regal → vidljiva poruka).
POST prolazi kroz proxy (provjera Origin == Host u ekranu). Upisuje pretince R99-P9-01..02 (testna adresa; na produkciji
ih poslije ukloniti nije moguće bez DELETE prava — zato se na produkciji pokreće s OTPAD_BEZ_UPISA=1).
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

JAVNI = os.environ["OTPAD_JAVNI"].rstrip("/")
KOR, LOZ = os.environ["OTPAD_KORISNIK"], os.environ["OTPAD_LOZINKA"]
BEZ_UPISA = os.environ.get("OTPAD_BEZ_UPISA") == "1"
rez = {"p": 0, "f": 0}


def provjeri(uvjet: bool, opis: str) -> None:
    rez["p" if uvjet else "f"] += 1
    print(("PROŠLO  " if uvjet else "PALO    ") + opis)


def cekaj(page, uvjet, s: float = 10.0) -> None:
    """Bez wait_for_function: CSP ekrana (default-src 'self') ne dopušta eval."""
    for _ in range(int(s * 10)):
        if uvjet():
            return
        page.wait_for_timeout(100)


def main() -> int:
    try:
        urllib.request.urlopen(JAVNI + "/otpad/", timeout=10)
        kod = 200
    except urllib.error.HTTPError as e:
        kod = e.code
    provjeri(kod == 401, f"bez prijave → {kod} (očekivano 401)")

    with sync_playwright() as pw:
        preglednici = []
        for ime in ("chromium", "firefox", "webkit"):
            try:
                b = getattr(pw, ime).launch()
                preglednici.append((ime, b))
            except Exception as e:                                               # noqa: BLE001
                print(f"NEPOZNATO {ime} nije instaliran ({str(e).splitlines()[0][:60]})")
        for ime, b in preglednici:
            for tema in ("light", "dark"):
                for sirina in (390, 1280):
                    ctx = b.new_context(http_credentials={"username": KOR, "password": LOZ},
                                        color_scheme=tema, viewport={"width": sirina, "height": 900},
                                        ignore_https_errors=False)
                    page = ctx.new_page()
                    konzola, losi = [], []
                    page.on("console", lambda m: konzola.append(m.text) if m.type == "error" else None)
                    page.on("response", lambda r: losi.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                    page.goto(JAVNI + "/otpad/", wait_until="networkidle")
                    oz = f"[{ime}/{tema}/{sirina}px]"
                    provjeri(page.locator("#tab-trazi").is_visible(), f"{oz} stranica učitana kroz /otpad/")
                    skrol = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                    provjeri(not skrol, f"{oz} nema vodoravnog skrola")
                    for _ in range(50):
                        sw = page.evaluate("navigator.serviceWorker.getRegistration().then(r => r && r.active ? r.scope : null)")
                        if sw:
                            break
                        page.wait_for_timeout(100)
                    provjeri(bool(sw) and sw.endswith("/otpad/"), f"{oz} servisni worker aktivan, opseg /otpad/ ({sw})")
                    ljuska = page.evaluate("caches.keys().then(k => Promise.all(k.map(n => caches.open(n).then(c => c.keys()))))"
                                           ".then(l => l.flat().map(r => new URL(r.url).pathname))")
                    provjeri("/otpad/app.js" in ljuska and not any(x.startswith("/otpad/api/") for x in ljuska),
                             f"{oz} ljuska spremljena pod /otpad/, API nije u cacheu ({sorted(ljuska)[:3]})")
                    page.click("#tab-stalaza")
                    page.wait_for_load_state("networkidle")
                    # tok greške: regal nije broj → poruka na ekranu (namjerni 400)
                    page.fill("#pr-regal", "xx"); page.fill("#pr-polica", "9"); page.fill("#pr-n", "1")
                    page.click("#pr-dodaj")
                    cekaj(page, lambda: page.text_content("#pr-poruka"))
                    t = page.text_content("#pr-poruka") or ""
                    provjeri("greska" in (page.get_attribute("#pr-poruka", "class") or "") and "podrijetlo" not in t,
                             f"{oz} greška validacije vidljiva (ne Origin): {t[:50]!r}")
                    if not BEZ_UPISA:
                        page.fill("#pr-regal", "99"); page.fill("#pr-polica", "9"); page.fill("#pr-n", "2")
                        page.click("#pr-dodaj")
                        cekaj(page, lambda: "greska" not in (page.get_attribute("#pr-poruka", "class") or ""))
                        t = page.text_content("#pr-poruka") or ""
                        provjeri(bool(t) and "greska" not in (page.get_attribute("#pr-poruka", "class") or ""),
                                 f"{oz} potvrda vidljiva (POST kroz proxy): {t[:50]!r}")
                    neocekivani = [x for x in losi if not x.startswith("400 ")]
                    provjeri(not konzola or all("400" in k for k in konzola),
                             f"{oz} konzola bez grešaka osim namjernog 400 ({konzola[:2]})")
                    provjeri(not neocekivani, f"{oz} nema neočekivanih ≥400 odgovora ({neocekivani[:2]})")
                    ctx.close()
            b.close()
    print(f"\nUKUPNO {rez['p'] + rez['f']} · PROŠLO {rez['p']} · PALO {rez['f']}")
    return 1 if rez["f"] else 0


if __name__ == "__main__":
    sys.exit(main())
