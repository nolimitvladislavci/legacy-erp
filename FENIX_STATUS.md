# FENIX STATUS
# Zadnje azuriranje: 2026-04-05 — MCP fix
# Git HEAD: 403be822
# Server: gunicorn ✅ nginx ✅ mcp-fina ✅ | disk 39%

---

SESIJA 05-06.04.2026. — SAŽETAK

Commiti (Sonnet + CC):
  403be822  feat(mega-7): TriKey + CostCenter + Honorari + FINA parser + Pricing + Registration
  c8735f93  docs(fenix): TriKey konfiguracija + cjenik + OIB
  da7c397f  feat(auth): TriKey — 3 ključa za 1 bravu
  d7ac9388  docs(strategy): Konkurencija 2026 — tržišna analiza
  8e4f68b3  feat(sales): 3 Pupilla rupe zatvorene (cjenici, narudžbe, saldakonti)
  232e3dc8  feat(production): MRP 10/10 — Pupillina prednost zatvorena
  a3624e06  fix: register page — 409KB skripti maknuto, light theme CSS
  3a55e598  fix: nginx static cache immutable→must-revalidate (1h)
  eb57d0c8  fix: memio_pet views .using('memio_pets') — 302→200

---

NOVO U OVOJ SESIJI:

  memio.pet:
    - 12/12 HTTP audit ✅
    - .using('memio_pets') fix na svim views
    - 3 test firme obrisane (Tonka, Dado, Firma d.o.o.)

  Register stranica:
    - 409KB JS maknuto (html5-qrcode, fenix-scan, fenix-camera, fenix-permissions)
    - Light/dark toggle fix (data-theme atribut → CSS var match)
    - CSS cache: immutable→must-revalidate 1h

  Production MRP (CC — 35 fajlova, ~5.829 linija):
    - 7 modela: BOM, BOMLine, WorkCenter, ProductionOrder...
    - FSM 7 stanja, BOMCostEngine, MRPPlanner
    - Konto knjiženje (6000/6100/6200/1300)
    - 53 testa zeleno
    - URL: /hr/proizvodnja/

  Mega-7 sprint (CC — 45 fajlova, 5.430 linija):
    - honorari/ — 4 modela, HR porezni obračun, JOPPD
    - konto/parsers.py — camt.053 XML + CSV + MT940
    - konto/cost_center — profitni centri + budget tracking
    - accounts/trikey — login + status templates
    - registration/trikey — OIB auto-fill flow
    - landing pricing — 5 kartica (0/9/19/49/149€)

  Pricing strategija:
    - Pupilla analiza završena (57 modula, 7.844€ vs LIMIT Connect)
    - Pricing plan kreiran (18 planova, 5 segmenata)
    - MRR čišćenje: ghost MRR -846€ (3 test firme)
    - Realni MRR: 1.534€/mj
    - Konjik Scenarij A (639€) — razgovor pending (Ivan)

---

LIVE AUDIT REZULTATI (06.04.):
  ✅ memio.pet: 16/16
  ✅ Production: /hr/proizvodnja/ radi (302→login)
  ✅ Honorari: /hr/honorari/ radi (302→login)
  ✅ Konto cost-centers + bank upload: radi
  ✅ TriKey login: 200 OK
  ✅ Pricing + Landing: 200 OK
  ⚠️  Django check: 0 errors (6 warnings — stare, nema novih)
  ✅ Migracije: sve aplicirane [X]

  NOTE: /radna-mjesta/ ne postoji — CC koristio /stanice/
        /honorari/nova/ ne postoji — CC koristio /novi/
        → funkcionalni ekvivalent, drugačiji URL-ovi

---

RATNI RASPORED:
  07.04. | QA + final audit                     | CC+Sonnet| 🔥
  08.04. | Marija dry-run + ambasador brief      | Marija   | ⏳
  12.04. | Load test (CCX33)                    | CC       | ⏳
  14.04. | DNS cutover priprema                  | Ivan     | ⏳
  15.04. | GO/NO-GO + PRODUKCIJA                 | Ivan+Marija | ⏳

PENDING (Ivan):
  - Konjik razgovor: Scenarij A (639€/mj umjesto 359€)
  - Gmail OAuth credentials
  - memio.hr registracija
  - EUIPO MEMIO trademark
  - HZZ Osijek kvotni upit (10 ambasadora)
  - Marija: email brief 08.04.

PRICING (dogovoriti finalno):
  - Micro: 9€ ili 10€?
  - Starter: 19€ ili 22€?
  - Professional: 49€ ili 69€?
  - Komunalni jednokratni: 990€/1.990€ OK?
  - Računovođa: odvojen plan ili Professional?

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
