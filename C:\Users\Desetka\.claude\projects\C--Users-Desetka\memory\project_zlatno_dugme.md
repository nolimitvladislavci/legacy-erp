---
name: Zlatno Dugme — Feedback + AI Trojstvo sustav
description: Globalni feedback sustav. Screenshot, WhatsApp/Email, AI analiza (Haiku+Gemini+Sonnet+Opus advisor). 18/18 testova.
type: project
---

# ZLATNO DUGME — Kompletni sustav

**Datum:** 2026-04-12
**Status:** 10/10, deployano, testirano HR/DE/EN

## URL-ovi
- `/hr/feedback/` — globalni (i18n: /de/feedback/, /en/feedback/)
- `/hr/pos/improvements/` — legacy alias (radi)
- Sidebar: zlatna zvjezdica u core kategoriji, always_visible

## FLOW
1. Korisnik klikne ⭐ → upiše naslov + opis + screenshot
2. Odabere: WhatsApp / Email / Samo spremi
3. POST → kreira ImprovementSuggestion + BookingSignature audit
4. WhatsApp notifikacija Ivanu (IVAN_PHONE)
5. Celery → trojstvo_rijesi(suggestion_id)
6. Haiku analizira (+ Opus advisor za kritične, max_uses=2)
7. Gemini analizira (paralelno)
8. Sonnet uspoređuje → konsenzus ili conflict
9. Agreed (≥65%) → log, auto-reviewed
10. Conflict → WhatsApp Ivanu s oba prijedloga

## MODEL: ImprovementSuggestion (pos/models.py:1292)
- company, author, source (user/system/anonymous)
- title, description, category, priority (1-5)
- status (new/reviewed/accepted/done/rejected)
- haiku_proposal, gemini_proposal, ai_resolution
- trojstvo_status (pending/agreed/conflict/error)

## FAJLOVI
- `pos/views.py` → improvement_list, improvement_update
- `pos/trojstvo_task.py` → trojstvo_rijesi (Celery)
- `templates/pos/improvement_list.html` — extends base.html
- `core/urls.py` → /feedback/ alias
- `companies/module_registry.py` → feedback modul

## TESTOVI: 18/18 pass
- Superadmin + regular user
- GET + POST
- HR + DE + EN
- BookingSignature audit
- Screenshot upload
- WhatsApp sending
