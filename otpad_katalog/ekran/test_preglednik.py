#!/usr/bin/env python3
"""Test sučelja u pregledniku (Playwright + Chromium): 2 teme x 2 širine.

    OTPAD_URL=http://127.0.0.1:8765 python3 test_preglednik.py [mapa_za_snimke_ekrana]

Provjerava: konzola 0 grešaka, 4xx/5xx 0 pri učitavanju, vodoravni skrol 0,
onemogućen gumb + tekst radnje tijekom slanja, čitljive poruke za grešku i potvrdu,
tok duplikata, prepoznavanje broja, XSS (tekst se ne izvršava).
Samo Chromium: Firefox i WebKit u ovom okruženju nisu instalirani.
"""
import glob
import os
import re
import sys
import uuid

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("OTPAD_URL", "http://127.0.0.1:8765")
SNIMKE = sys.argv[1] if len(sys.argv) > 1 else None
RUN = uuid.uuid4().hex[:6].upper()
PROLAZ, PAD = [], []


def provjera(ime, uvjet, detalj=""):
    (PROLAZ if uvjet else PAD).append(ime)
    print(("PROŠLO  " if uvjet else "PALO    ") + ime + ("" if uvjet or not detalj else f" | {detalj}"))


def chromium_put():
    for c in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")):
        return c
    return None


def sporo(page, uzorak, ms=500):
    """Uspori zahtjev da se vidi stanje 'Tražim…' / 'Spremam…'."""
    def h(route):
        page.wait_for_timeout(ms)
        route.continue_()
    page.route(uzorak, h)


def kombinacija(p, tema, sirina):
    oznaka = f"{tema}/{sirina}px"
    br = p.chromium.launch(executable_path=chromium_put()) if chromium_put() else p.chromium.launch()
    ctx = br.new_context(viewport={"width": sirina, "height": 900 if sirina > 600 else 800}, color_scheme=tema)
    page = ctx.new_page()
    greske, losi = [], []
    page.on("console", lambda m: greske.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: greske.append(str(e)))
    page.on("response", lambda r: losi.append((r.status, r.url)) if r.status >= 400 else None)

    page.goto(URL + "/")
    page.wait_for_load_state("networkidle")
    provjera(f"[{oznaka}] stranica se učitala, 0 grešaka u konzoli", not greske, str(greske))
    provjera(f"[{oznaka}] 0 odgovora 4xx/5xx pri učitavanju", not losi, str(losi))
    skrol = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    provjera(f"[{oznaka}] nema vodoravnog skrola (traži)", skrol <= 0, f"višak {skrol}px")
    if SNIMKE:
        page.screenshot(path=f"{SNIMKE}/trazi_{tema}_{sirina}.png")

    # ----- TRAŽI -----
    page.fill("#q", "a")
    page.click("#btn-trazi")
    provjera(f"[{oznaka}] prekratak upit -> poruka o grešci", "barem 2 znaka" in page.inner_text("#poruka-trazi"))

    sporo(page, "**/api/trazi*")
    page.fill("#q", "tst-100-001-a")
    page.click("#btn-trazi")
    expect(page.locator("#btn-trazi")).to_be_disabled()
    provjera(f"[{oznaka}] gumb onemogućen tijekom slanja", page.is_disabled("#btn-trazi"))
    provjera(f"[{oznaka}] tekst gumba 'Tražim…'", page.inner_text("#btn-trazi") == "Tražim…")
    page.wait_for_selector("#rezultati .kartica")
    provjera(f"[{oznaka}] gumb ponovno aktivan s tekstom 'Traži'",
             (not page.is_disabled("#btn-trazi")) and page.inner_text("#btn-trazi") == "Traži")
    tekst = page.inner_text("#rezultati")
    provjera(f"[{oznaka}] broj nađen: Alternator, Focus Mk III, polica", "Alternator" in tekst and "Mk III" in tekst and "A-01-3" in tekst, tekst[:120])
    provjera(f"[{oznaka}] potvrda 'Nađeno' vidljiva", "Nađeno" in page.inner_text("#poruka-trazi"))
    page.unroute("**/api/trazi*")

    page.fill("#q", "NEPOSTOJI9999ZZ")
    page.click("#btn-trazi")
    expect(page.locator("#poruka-trazi")).to_contain_text("Ništa nije nađeno")
    provjera(f"[{oznaka}] prazan rezultat -> jasna poruka", True)

    page.route("**/api/trazi*", lambda r: r.fulfill(status=500, content_type="application/json",
                                                   body='{"greska":"Dogodila se greška na poslužitelju. Pokušaj ponovo."}'))
    page.fill("#q", "focus 2013"); page.click("#btn-trazi")
    expect(page.locator("#poruka-trazi")).to_have_class(re.compile("greska"))
    provjera(f"[{oznaka}] greška 500 -> prevedena poruka na ekranu", "greška na poslužitelju" in page.inner_text("#poruka-trazi"))
    page.unroute("**/api/trazi*")
    page.route("**/api/trazi*", lambda r: r.abort())
    page.click("#btn-trazi")
    expect(page.locator("#poruka-trazi")).to_contain_text("Nema veze")
    provjera(f"[{oznaka}] prekid mreže -> poruka 'Nema veze'", True)
    page.unroute("**/api/trazi*")

    page.fill("#q", "focus 2013"); page.click("#btn-trazi")
    page.wait_for_selector("#rezultati .kartica")
    provjera(f"[{oznaka}] 'focus 2013' -> Focus Mk III", "Focus Mk III" in page.inner_text("#rezultati"))
    skrol = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    provjera(f"[{oznaka}] nema vodoravnog skrola (rezultati)", skrol <= 0, f"višak {skrol}px")
    if SNIMKE:
        page.screenshot(path=f"{SNIMKE}/rezultati_{tema}_{sirina}.png", full_page=True)

    # ----- UNOS -----
    page.click("#tab-unos")
    page.wait_for_selector("#auto option", state="attached")
    page.click("#btn-spremi")
    provjera(f"[{oznaka}] spremanje bez auta -> poruka", "odaberi auto" in page.inner_text("#poruka-unos").lower())

    page.click("#btn-novi-auto")
    page.fill("#tip-q", "Focus 2013")
    page.click("#btn-tip")
    page.wait_for_selector("#tip-lista input[name=tip]")
    page.click("#btn-spremi-auto")
    provjera(f"[{oznaka}] spremanje auta bez vrste -> poruka", "odaberi vrstu auta" in page.inner_text("#poruka-auto").lower())
    page.locator("#tip-lista label").first.click()
    page.click("#btn-spremi-auto")
    expect(page.locator("#novi-auto")).to_be_hidden()
    expect(page.locator("#poruka-unos")).to_contain_text("Auto je dodan")
    provjera(f"[{oznaka}] auto dodan i odabran, poruka vidljiva",
             page.input_value("#auto") != "" and "Auto je dodan" in page.inner_text("#poruka-unos"))

    page.click("#btn-spremi")
    provjera(f"[{oznaka}] bez naziva -> poruka", "naziv dijela" in page.inner_text("#poruka-unos").lower())
    page.fill("#dio-naziv", "Neki dio")
    page.click("#btn-spremi")
    provjera(f"[{oznaka}] bez stanja -> poruka", "stanje dijela" in page.inner_text("#poruka-unos").lower())

    page.fill("#dio-naziv", "")
    page.fill("#dio-broj", "TST 100 002 A")
    page.press("#dio-broj", "Tab")
    page.wait_for_selector("#prepoznato:not([hidden])")
    provjera(f"[{oznaka}] poznati broj -> 'Prepoznato: Anlaser', naziv se sam upisao",
             "Anlaser" in page.inner_text("#prepoznato") and page.input_value("#dio-naziv") == "Anlaser"
             and page.eval_on_selector("#dio-naziv", "e => e.readOnly"))

    page.fill("#polica", "T-1-1"); page.fill("#cijena", "38,5")
    page.check("input[name=stanje][value=B]")
    sporo(page, "**/api/otpad-dijelovi", 500)
    page.click("#btn-spremi")
    expect(page.locator("#btn-spremi")).to_be_disabled()
    provjera(f"[{oznaka}] spremanje: gumb onemogućen + tekst 'Spremam…'", page.inner_text("#btn-spremi") == "Spremam…")
    expect(page.locator("#poruka-unos")).to_have_class(re.compile("ok"))
    provjera(f"[{oznaka}] potvrda 'Spremljeno: Anlaser (TST100002A), polica T-1-1'",
             "Spremljeno: Anlaser (TST100002A), polica T-1-1" in page.inner_text("#poruka-unos"), page.inner_text("#poruka-unos"))
    provjera(f"[{oznaka}] polja očišćena, auto ostaje odabran",
             page.input_value("#dio-broj") == "" and page.input_value("#polica") == "" and page.input_value("#auto") != "")
    expect(page.locator("#zadnji")).to_contain_text("Anlaser")
    provjera(f"[{oznaka}] 'Zadnje uneseno' sadrži novi dio", True)
    page.unroute("**/api/otpad-dijelovi")

    # duplikat
    page.fill("#dio-broj", "tst-100-002-a"); page.press("#dio-broj", "Tab")
    page.wait_for_selector("#prepoznato:not([hidden])")
    page.check("input[name=stanje][value=A]")
    page.click("#btn-spremi")
    page.wait_for_selector("#duplikat:not([hidden])")
    provjera(f"[{oznaka}] duplikat -> upozorenje s gumbom 'Ipak spremi'", "već je unesen" in page.inner_text("#duplikat-tekst"))
    page.click("#btn-duplikat")
    expect(page.locator("#poruka-unos")).to_have_class(re.compile("ok"))
    provjera(f"[{oznaka}] 'Ipak spremi' -> spremljeno", "Spremljeno" in page.inner_text("#poruka-unos"))

    # XSS
    page.fill("#dio-naziv", "<img src=x onerror=window.__xss=1>"); page.check("input[name=stanje][value=C]")
    page.click("#btn-spremi")
    expect(page.locator("#zadnji")).to_contain_text("<img src=x")
    provjera(f"[{oznaka}] XSS: tekst prikazan doslovno, ništa se ne izvršava",
             page.evaluate("window.__xss === undefined") and page.locator("#zadnji img").count() == 0)

    skrol = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    provjera(f"[{oznaka}] nema vodoravnog skrola (unos)", skrol <= 0, f"višak {skrol}px")
    if SNIMKE:
        page.screenshot(path=f"{SNIMKE}/unos_{tema}_{sirina}.png", full_page=True)
    provjera(f"[{oznaka}] 0 grešaka u konzoli nakon cijelog toka", not [g for g in greske if "Failed to load resource" not in g], str(greske))
    br.close()


with sync_playwright() as p:
    for tema in ("light", "dark"):
        for sirina in (390, 1280):
            kombinacija(p, tema, sirina)

print("------")
print(f"PROŠLO: {len(PROLAZ)} | PALO: {len(PAD)}")
sys.exit(1 if PAD else 0)
