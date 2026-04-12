# FENIX STATUS
# Zadnje azuriranje: 2026-04-12 18:15 (Opus — Advisor + Zlatno dugme + Employee + Livestock)
# Git HEAD: 33ef1597
# Server: gunicorn OK nginx OK celery OK mcp-fina OK | disk 41%

===============================================================

## DANAS (12.04.2026) — Opus sesija

### Faza 4+5 Employee HRM:
  - Self-Service Portal: /worktime/moji-sati/, /moja-placa/, /zahtjevi/
  - Onboarding Wizard: 4 koraka (OIB MOD11, IBAN, PIN, Workspace)
  - KPI kartice, graf sati, projekcija place

### Livestock IKG:
  - FarmIdentification model (JIBG, kartica, posjednik, GPS)
  - Cipiranje/markice: ear_tag_left/right, bolus, chip ISO 11784
  - CroValidator: +6 validatora (JIBG, JZB, UELN, Chip, NKD, VAT)
  - API rate limit 60/min, XSS sanitizacija
  - Goran Labas HR30157757 seedan

### Zlatno Dugme 10/10:
  - Globalni URL /feedback/ (ne samo POS)
  - base.html (ne base_pos.html) — svi korisnici
  - Screenshot upload + BookingSignature audit
  - AI live polling (10s auto-reload)
  - Module registry: zlatna zvjezdica, always_visible
  - 18/18 testova (HR/DE/EN, superadmin+regular)

### Advisor Strategy:
  - core/anthropic_advisor.py — Haiku executor + Opus advisor
  - Trojstvo: max_uses=2 (Sonnet integrirao)
  - Claude Doktor: max_uses=1 (Opus, samo za kriticne)
  - ai_health.py: BEZ advisora (infrastruktura)

### Bugfixevi:
  - #29 POS joker Decimal*float crash — FIXED
  - #27/#28 Company switch — radi u testu (CSRF na mobitelu)
  - 16 starih FISCAL SOS — resolved
  - Panel_auto.html syntax error — FIXED (rusilo 134 stranice)
  - fenix-shell.css desni panel izbocina — FIXED (slide-up drawer)
  - i18n: 15+ hardcodiranih /hr/ linkova → {% url %}
  - Rate limiter: 300→1000/min, login 50→20/5min
  - Smart login: /pocni/ jedini ulaz, existing → login gumb

===============================================================

## AI ARHITEKTURA (3 tocke)

  Trojstvo (Zlatno dugme):
    Haiku → analiza (+ Opus advisor max 2x za kriticne)
    Gemini → analiza (paralelno)
    Sonnet → konsenzus (agreed/conflict)
    Conflict → WhatsApp Ivan

  Claude Doktor (nightly scan):
    Haiku → dijagnostika (+ Opus advisor max 1x za fiscal/cert/score<40)
    Fallback → rule-based preporuke

  ai_health.py:
    Haiku → infrastruktura check (BEZ advisora)

===============================================================

CLAUDE.AI MAX: auto-obnova 27.04.2026. | Mastercard 8859 | ~107 EUR/mj
