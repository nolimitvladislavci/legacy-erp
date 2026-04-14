# PLAN: Umbrella Komitenti — 10/10 Rješenje + 2 Inovacije iz Budućnosti

**Status**: DONE ✅
**Datum**: 2026-04-14
**Commit**: e443d53e + 4e63c2ab

---

## IMPLEMENTIRANO

### FAZA 1: Hitni Popravak ✅
- [x] Data integrity: 9 CompanyPartnership kreirano, 6 klijenata raspoređeno u workspace-e
- [x] umbrella_max_children: 72 → 100
- [x] Module inheritance: `get_effective_modules()` u `core/company_utils.py`

### FAZA 2: Dubinski Popravak ✅
- [x] Multi-level switch: `_is_umbrella_ancestor()` — 3 razine dubine
- [x] SubscriptionMiddleware koristi `get_effective_modules` 
- [x] Breadcrumb banner: Konjik → Workspace → Dijete
- [x] Quick Switch dropdown: 300px, padded, scrollable, s headerom

### FAZA 3: Inovacije ✅
- [x] Smart Desk (`/umbrella/smart-desk/`) — AI workload analiza po desk-u
- [x] Client Pulse (`/umbrella/client-pulse/`) — zdravlje klijenata (green/yellow/red)
- [x] ClientHealthScore model + recalculate endpoint
- [x] WorkloadSnapshot model

## Fajlovi Promijenjeni
- `core/company_utils.py` — _is_umbrella_ancestor, get_effective_modules, get_umbrella_home
- `core/views.py` — umbrella_switch_company multi-level
- `core/context_processors.py` — umbrella_context
- `core/settings.py` — context processor registration
- `core/urls.py` — 3 nova URL-a
- `registration/middleware.py` — module inheritance u SubscriptionMiddleware
- `companies/models.py` — WorkloadSnapshot, ClientHealthScore
- `companies/umbrella_views.py` — smart_desk_dashboard, client_pulse_dashboard
- `templates/base.html` — breadcrumb banner + quick switch
- `templates/dashboards/umbrella.html` — Smart Desk + Client Pulse gumbi
- `templates/companies/smart_desk.html` — potpuni template
- `templates/companies/client_pulse.html` — potpuni template
