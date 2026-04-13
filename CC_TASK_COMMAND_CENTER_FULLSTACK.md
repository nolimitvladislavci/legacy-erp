# COMMAND CENTER — FULL STACK PLAN
> Status: IN PROGRESS | Agent: Opus | Start: 2026-04-13

## FAZA 1: UI Shell ✅ DONE (commit 47ddca92)
- 13 template fragmenata
- Sidebar nav
- views_settings.py dispatcher
- Module toggle endpoint

## FAZA 2: Backend Wiring (IN PROGRESS)
### 2A: Main view delegation — company_settings() mora delegirati na views_settings za nove tabove
### 2B: Website tab POST handler — save theme, branding, content, SEO
### 2C: Booking tab inline CRUD — services + resources + working hours
### 2D: Fiscal certificate upload handler
### 2E: Subscription upgrade flow (link to registration/upgrade)
### 2F: AI tab — real patrol status, trojstvo, suggestions from DB
### 2G: Webshop tab — inline product stats, delivery config save
### 2H: Integrations — all save handlers

## FAZA 3: AI Integration
### 3A: Module AI recommendations (NKD-based auto-suggest)
### 3B: AI patrol status from PatrolReport model
### 3C: AI suggestions from ImprovementSuggestion model

## FAZA 4: Testing & Polish
### 4A: Svaki tab renderira se bez greške
### 4B: Svaki POST handler sprema u DB
### 4C: HTMX partial loading radi za sve tabove
### 4D: Mobile responsive provjera
