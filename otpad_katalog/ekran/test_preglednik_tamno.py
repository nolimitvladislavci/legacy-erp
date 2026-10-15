#!/usr/bin/env python3
"""Test u pregledniku (Playwright + Chromium) za tamni dio: 2 teme x 2 širine, cijeli tok kroz sučelje.

Sam stvara privremenu bazu i poslužitelj (kao test_tamno_ekran.py). Pokretanje:
    BRANDS_JS=<put/do/brands.js> python3 -I test_preglednik_tamno.py [mapa_za_snimke]
Za svaku kombinaciju: stranica bez grešaka u konzoli, vodoravni skrol 0, svaka namjerna greška daje čitljivu poruku
na ekranu, gumb je onemogućen s tekstom radnje dok traje zahtjev, svaki uspjeh ima vidljivu potvrdu, slike se vide
(naturalWidth > 0), pa tok: pretinci → novi dio → 3 slike → pranje → test → pakiranje → pretinac → prodaja → nađi.
Svaki odgovor ≥ 400 mora biti namjeran (POST 400/409); GET greška ili 5xx = PAD. Samo Chromium.
"""
import glob
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import uuid

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tamno_ekran as TE  # noqa: E402

H = TE.H
SNIMKE = sys.argv[1] if len(sys.argv) > 1 else None
RUN = uuid.uuid4().hex[:5].upper()


def chromium_put():
    for c in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")):
        return c
    return None


def sporo(page, uzorak, ms=600):
    """Uspori zahtjeve koji odgovaraju uzorku dok se ne pozove sporo_stani (zastavica, bez unroute usred zadrške)."""
    if not hasattr(page, "_spori"):
        page._spori = {}
    if uzorak not in page._spori:
        def h(route):
            if page._spori.get(uzorak):
                page.wait_for_timeout(ms)
            route.continue_()
        page.route(uzorak, h)
    page._spori[uzorak] = True


def sporo_stani(page, uzorak):
    page._spori[uzorak] = False


def kombinacija(p, tema, sirina, mapa_slika):
    o = f"{tema}/{sirina}px"
    ok = H.ok
    br = p.chromium.launch(executable_path=chromium_put()) if chromium_put() else p.chromium.launch()
    ctx = br.new_context(viewport={"width": sirina, "height": 900 if sirina > 600 else 800}, color_scheme=tema)
    page = ctx.new_page()
    greske, odgovori = [], []
    page.on("console", lambda m: greske.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.on("pageerror", lambda e: greske.append(str(e)))
    page.on("response", lambda r: odgovori.append((r.request.method, r.status, r.url)) if r.status >= 400 else None)
    page.on("dialog", lambda d: d.accept())

    def skrol(ime):
        v = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(f"[{o}] nema vodoravnog skrola ({ime})", v <= 0, f"višak {v}px")

    def snimka(ime):
        if SNIMKE:
            page.screenshot(path=f"{SNIMKE}/tamno_{ime}_{tema}_{sirina}.png", full_page=True)

    page.goto(TE.URL + "/")
    page.wait_for_load_state("networkidle")
    ok(f"[{o}] nova kartica vidljiva, 0 grešaka u konzoli", page.is_visible("#tab-novi") and not greske, str(greske))
    skrol("početak")

    # ---------- STALAŽA: pretinci ----------
    page.click("#tab-stalaza")
    page.fill("#pr-regal", "0"); page.fill("#pr-polica", "2"); page.fill("#pr-n", "4")
    page.click("#pr-dodaj")
    expect(page.locator("#pr-poruka")).to_contain_text("Regal")
    ok(f"[{o}] neispravan regal → čitljiva poruka na ekranu", "između 1 i 99" in page.inner_text("#pr-poruka"))
    sporo(page, "**/api/pretinci")
    page.fill("#pr-regal", "3")
    page.click("#pr-dodaj")
    expect(page.locator("#pr-dodaj")).to_be_disabled()
    ok(f"[{o}] gumb onemogućen s tekstom 'Dodajem…' tijekom slanja", page.inner_text("#pr-dodaj") == "Dodajem…")
    expect(page.locator("#pr-poruka")).to_contain_text("dodano")
    ok(f"[{o}] potvrda: pretinci dodani", True)
    sporo_stani(page, "**/api/pretinci")
    expect(page.locator("#pretinci-lista .cip-gumb").first).to_be_visible()
    ok(f"[{o}] popis pretinaca prikazan", page.locator("#pretinci-lista .cip-gumb").count() >= 4)
    skrol("stalaža")
    snimka("stalaza")

    # ---------- NOVI DIO ----------
    page.click("#tab-novi")
    page.wait_for_selector("#nd-auto option:nth-child(2)", state="attached")
    page.click("#nd-rodi")
    expect(page.locator("#nd-poruka")).to_contain_text("odaberi auto")
    ok(f"[{o}] bez auta → poruka 'odaberi auto'", True)
    page.select_option("#nd-auto", index=1)
    broj = f"TST {RUN} {tema[:1]}{sirina}"
    page.fill("#nd-broj", broj); page.fill("#nd-naziv", "Alternator")
    sporo(page, "**/api/dio/rodi")
    page.click("#nd-rodi")
    expect(page.locator("#nd-rodi")).to_be_disabled()
    ok(f"[{o}] 'Unosim dio…' i onemogućen gumb", page.inner_text("#nd-rodi") == "Unosim dio…")
    expect(page.locator("#dio-kartica h3").first).to_contain_text("Alternator")
    sporo_stani(page, "**/api/dio/rodi")
    ok(f"[{o}] nakon unosa otvorena kartica dijela (potvrda)", page.is_visible("#dio-kartica"))
    token = re.search(r"oznaka ([A-Z2-7]{16})", page.inner_text("#dio-kartica")).group(1)
    ok(f"[{o}] dio ima oznaku od 16 znakova", len(token) == 16)

    # ---------- SLIKE dijela (3) ----------
    ulaz = page.locator('input[aria-label="Dodaj slike: Slike dijela"]')
    ulaz.set_input_files([f"{mapa_slika}/{tema[:1]}{sirina}_{k}.jpg" for k in range(3)])
    expect(page.locator("#dio-kartica .poruka.ok").first).to_contain_text("Slike su spremljene", timeout=15000)
    expect(page.locator("#dio-kartica .slike img")).to_have_count(3)
    page.wait_for_timeout(800)
    vidljive = page.evaluate("Array.from(document.querySelectorAll('#dio-kartica .slike img')).every(i => i.complete && i.naturalWidth > 0)")
    ok(f"[{o}] 3 slike dijela spremljene i prikazane (naturalWidth > 0)", vidljive)
    skrol("kartica dijela")
    snimka("kartica")

    # ---------- PRANJE ----------
    gumb = page.get_by_role("button", name="Označi oprano")
    ok(f"[{o}] 'Označi oprano' onemogućeno dok nema slike poslije pranja", gumb.is_disabled())
    page.locator('input[aria-label="Dodaj slike: Slika poslije pranja"]').set_input_files(f"{mapa_slika}/{tema[:1]}{sirina}_3.jpg")
    expect(page.get_by_role("button", name="Označi oprano")).to_be_enabled(timeout=15000)
    page.get_by_role("button", name="Označi oprano").click()
    expect(page.locator("#dio-kartica").get_by_text("oprano ✓")).to_be_visible()
    ok(f"[{o}] pranje: potvrda 'oprano ✓'", True)

    # ---------- TEST ----------
    page.get_by_role("button", name="Radi (DRŽI)").click()
    expect(page.locator("#dio-kartica").get_by_text("zadnji test: DRZI")).to_be_visible()
    ok(f"[{o}] test: potvrda 'zadnji test: DRZI'", True)

    # ---------- PAKIRANJE ----------
    ok(f"[{o}] 'Upiši pakiranje' onemogućeno dok nema slike paketa", page.get_by_role("button", name="Upiši pakiranje").is_disabled())
    page.locator('input[aria-label="Dodaj slike: Slika zapakiranog dijela"]').set_input_files(f"{mapa_slika}/{tema[:1]}{sirina}_4.jpg")
    expect(page.get_by_role("button", name="Upiši pakiranje")).to_be_enabled(timeout=15000)
    page.fill("#pak-dim", "velika kutija"); page.fill("#pak-tez", "3200")
    page.get_by_role("button", name="Upiši pakiranje").click()
    expect(page.locator("#dio-kartica")).to_contain_text("npr. 30x20x15")
    ok(f"[{o}] krive dimenzije → čitljiva poruka", True)
    page.fill("#pak-dim", "30x20x15")
    page.get_by_role("button", name="Upiši pakiranje").click()
    expect(page.locator("#dio-kartica").get_by_text("pakirano ✓")).to_be_visible()
    ok(f"[{o}] pakiranje: potvrda 'pakirano ✓'", True)

    # ---------- VRATA prije pretinca ----------
    ok(f"[{o}] prije pretinca nema gumba 'Stavi u prodaju'", page.get_by_role("button", name="Stavi u prodaju").count() == 0)

    # ---------- PRETINAC ----------
    page.wait_for_selector('#pret-sel option[value="R03-P2-01"]', state="attached")
    page.get_by_role("button", name="Spremi u pretinac").click()
    expect(page.locator("#dio-kartica")).to_contain_text("Odaberi pretinac")
    ok(f"[{o}] bez odabira pretinca → čitljiva poruka", True)
    page.select_option("#pret-sel", "R03-P2-01")
    page.get_by_role("button", name="Spremi u pretinac").click()
    expect(page.locator("#dio-kartica").get_by_text("pretinac R03-P2-01").first).to_be_visible()
    ok(f"[{o}] spremljeno u pretinac (potvrda)", True)

    # ---------- VRATA ----------
    expect(page.get_by_role("button", name="Stavi u prodaju")).to_be_visible()
    page.fill("#v-cijena", "abc")
    page.get_by_role("button", name="Stavi u prodaju").click()
    expect(page.locator("#dio-kartica")).to_contain_text("Cijena nije ispravan broj")
    ok(f"[{o}] cijena 'abc' → čitljiva poruka", True)
    page.fill("#v-cijena", "45,50")
    page.get_by_role("button", name="Stavi u prodaju").click()
    expect(page.locator("#dio-kartica")).to_contain_text("razred jamstva nije odabran")
    ok(f"[{o}] bez jamstva → stroj navodi razlog", True)
    page.select_option("#v-razred", "POTROSAC_12M")
    sporo(page, "**/api/dio/*/prodaja")
    page.get_by_role("button", name="Stavi u prodaju").click()
    expect(page.get_by_role("button", name="Provjeravam…")).to_be_disabled()
    ok(f"[{o}] 'Provjeravam…' i onemogućen gumb", True)
    expect(page.locator("#dio-kartica")).to_contain_text("Dio je u prodaji", timeout=15000)
    sporo_stani(page, "**/api/dio/*/prodaja")
    ok(f"[{o}] dio je u prodaji (vidljiva potvrda, cijena 45,50 €)", "45,50" in page.inner_text("#dio-kartica"))
    skrol("poslije prodaje")
    snimka("prodaja")

    # ---------- NAĐI ----------
    page.click("#tab-stalaza")
    page.fill("#nadji-q", token)
    page.click("#btn-nadji")
    expect(page.locator("#nadji-rez .kartica h3").first).to_contain_text("Alternator")
    ok(f"[{o}] nađi po oznaki dijela", True)
    page.fill("#nadji-q", "r03-p2-01")
    page.click("#btn-nadji")
    expect(page.locator("#nadji-rez .naslov-odjeljka")).to_contain_text("R03-P2-01")
    ok(f"[{o}] nađi po adresi pretinca (mala slova)", True)
    # ---------- OBILAZAK pretinca ----------
    expect(page.get_by_role("button", name="Završi obilazak")).to_be_visible()
    sjediste = page.locator("#nadji-rez input[type=checkbox]")
    ok(f"[{o}] obilazak: za svaki dio u pretincu jedna kvačica", sjediste.count() >= 1)
    page.get_by_role("button", name="Završi obilazak").click()
    expect(page.locator("#nadji-rez .poruka")).to_contain_text("nedostaje")
    ok(f"[{o}] obilazak bez označenih dijelova → 'nedostaje' (čitljiva potvrda)", True)
    for i in range(sjediste.count()):
        sjediste.nth(i).check()
    page.get_by_role("button", name="Završi obilazak").click()
    expect(page.locator("#nadji-rez .poruka")).to_contain_text("Sve je na mjestu")
    ok(f"[{o}] obilazak sa svim dijelovima → 'Sve je na mjestu'", True)
    skrol("obilazak")
    snimka("obilazak")

    page.fill("#nadji-q", "ZZZZZZZZ")
    page.click("#btn-nadji")
    expect(page.locator("#nadji-poruka")).to_contain_text("Ništa nije nađeno")
    ok(f"[{o}] ništa nađeno → čitljiva poruka", True)
    skrol("nađi")

    # ---------- sažetak ----------
    ok(f"[{o}] 0 grešaka u konzoli kroz cijeli tok", not greske, str(greske)[:300])
    neocekivano = [x for x in odgovori if not (x[0] == "POST" and x[1] in (400, 409))]
    ok(f"[{o}] svi odgovori ≥ 400 su namjerni (POST 400/409)", not neocekivano, str(neocekivano)[:300])
    br.close()


def main() -> int:
    brands = os.environ.get("BRANDS_JS", "")
    try:
        TE.postavi_bazu(brands)
    except Exception as e:                                                       # noqa: BLE001
        print(f"PRIPREMA PALA: {e}"); return 2
    if SNIMKE:
        os.makedirs(SNIMKE, exist_ok=True)
    mapa = tempfile.mkdtemp(prefix="otpad_foto_")
    from PIL import Image
    for t in ("l", "d"):
        for s in (1280, 390):
            for k in range(5):
                im = Image.new("RGB", (1600, 1200), ((k * 40 + 30) % 256, (k * 70 + 90) % 256, (k * 20 + (60 if t == "l" else 150)) % 256))
                for i in range(0, 1600, 7):
                    im.putpixel((i, (i * (k + 3) + (1 if s == 390 else 2)) % 1200), (255, 255, 255))
                im.save(f"{mapa}/{t}{s}_{k}.jpg", "JPEG", quality=88)
    slike = tempfile.mkdtemp(prefix="otpad_slike_"); os.chmod(slike, 0o700)
    srv = TE.pokreni(TE.PORT, slike)
    try:
        with sync_playwright() as p:
            for tema in ("light", "dark"):
                for sirina in (1280, 390):
                    kombinacija(p, tema, sirina, mapa)
    finally:
        srv.send_signal(signal.SIGTERM)
        shutil.rmtree(slike, ignore_errors=True); shutil.rmtree(mapa, ignore_errors=True)
        try:
            H.psql("postgres", f"DROP DATABASE IF EXISTS {TE.DB}")
        except Exception as e:                                                   # noqa: BLE001
            print(f"upozorenje: čišćenje baze: {e}")
    print(f"\nUKUPNO {H.PASS + H.FAIL} · PROŠLO {H.PASS} · PALO {H.FAIL}")
    return 1 if H.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
