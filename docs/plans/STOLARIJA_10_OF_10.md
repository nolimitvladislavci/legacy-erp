# STOLARIJA MODUL — PLAN DO 10/10

**Datum:** 2026-04-13
**Cilj:** EU #1 stolarija modul — Zdenko pilot ready
**Stanje:** Backend 95%, Frontend 90%, Integration 70%

---

## PRONAĐENI BUGOVI

1. **session_detail.html** — prazni `<td>` prije position_number (tablica kriva)
2. **tasks.py** — `settings` korišten ali nije importan u `send_approved_messages`
3. **measure.html** — `</div>` nesting issue u foto sekciji
4. **BOM = 0** za postojeći ProductionOrder — moguće ručno kreiran bez BOM triggera
5. **offer_pdf.html** referencira `m.svg` ali view ne šalje SVG data

## NEDOSTAJE ZA 10/10

### A. Sobna vrata integracija
- voice_parser: dodati 'sobna' → 'interior_door'
- measure form: swing_direction, door_position, wall_thickness_mm, door_standard
- validator: pravila za sobna vrata (visina, debljina zida)
- views.py: spremiti door-specific polja

### B. Komarnik integracija
- measure form: mesh_type, mounting_type
- voice_parser: mesh/mounting mappings
- views.py: spremiti komarnik polja

### C. Dashboard pipeline
- Dodati Production, Installation, Warranty, Service statistike
- Navigacija na sve sub-module
- KPI kartice

### D. SVG wiring
- generate_window_svg → offer_detail, offer_pdf, session_detail
- generate_door_svg → za interior_door/door tipove
- generate_mosquito_svg → za komarnik tipove

### E. PDF generiranje
- Dodati offer_pdf view s WeasyPrint
- URL: /stolarija/ponuda/<id>/pdf/
- warranty_pdf view + URL

### F. Dynamic form
- JS show/hide za door/mosquito fields po element_type

---

## REDOSLIJED IZVRŠAVANJA

1. Fix critical bugs (session_detail, tasks, measure nesting)
2. Sobna vrata + komarnik integracija (voice, form, validator, views)
3. Dynamic measure form (JS)
4. SVG wiring
5. Dashboard upgrade
6. PDF generation
7. E2E test + deploy
