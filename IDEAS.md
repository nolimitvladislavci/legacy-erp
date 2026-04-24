# IDEAS — Append-Only Backlog

> Pravilo: nikad ne brišemo, samo dodajemo.
> Format: `[ID] [STATUS] Opis`
> Status: 💡 nova | 🔄 razmatrana | ✅ implementirana | ❌ odbačena

---

## Ideje

- [I-001] ✅ 3-slojni memory sistem (ADR + IDEAS + KONTEKST) — implementirano CC_TASK_MEMORY_SYSTEM
- [I-002] ✅ Git hook upozorenje za FENIX_STATUS.md — pre-commit hook LIVE
- [I-003] ✅ CLI log-session alat za brzo bilježenje konteksta — /usr/local/bin/log-session LIVE
- [I-004] 🔄 Weekly AI digest (cron + Claude API) — odgođeno, planirati za sprint +2

## [I-005] ✅ Module Launcher — /hr/moduli/ LIVE (2026-04-24)
**Status:** IMPLEMENTIRANO

Bootstrap dark card grid, live search debounce 300ms.
Čita iz `companies.module_registry.MODULES` (95+ modula).
FA_TO_EMOJI konverzija (50+ FA ikona → emoji).
Route u `core/urls.py` direktno (ne u companies/urls.py — inače bi bio /hr/companies/moduli/).
Sidebar: launcher gumb na vrhu `_sidebar_modules.html`.

## [I-006] 💡 form_toolbar v2 port iz fenix-v3 (2026-04-24)
**Status:** TODO — VISOK prioritet

Fenix V3 form_toolbar v2 LIVE. fina-connect nema form toolbar nikakav.
Kopirati `templates/components/form_toolbar.html` iz fenix-v3, prilagoditi.
Uključiti u: documents/arhiva/upload.html, smart_import, svaku formu s text inputom.
UniPortal endpointi već postoje u fina-connect (Sprint 5).
