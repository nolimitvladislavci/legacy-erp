# BORG SPRINT CILJ — Ivan Brtan
# Zadnje ažuriranje: 2026-03-29 — Sonnet audit
## Autonomno izvršava Sonnet agent svaka 2 sata

## CILJ: BORG 10/10 — Produkcija 15.04.2026
## simulate_borg: 114/114 (100%) — VERIFIED

---

## ✅ DONE — Verificirano

| Task | Commit | Napomena |
|------|--------|----------|
| Joker Pricing /hr/pricing/ | bf13a0 | HTTP 200, "Cijene — LIMIT Connect" |
| 3-klik registracija + OIB auto-fill | 48c62edc | /hr/register/ HTTP 200, step1-4 flow |
| T&C consent middleware | core/middleware ForceTCMiddleware | 14/91 potpisalo — middleware blokira ostale |
| PgBouncer | 20c6c506 | active, 11 konekcija za 200 usera |
| Load test 150 korisnika | 760daa65 | 0 failures, P95<1.3s |
| Race condition POS | bf13a4a0 | 3 drona neutralizirana |
| Warehouse W1 (base) | CC_TASK_W1C_W1D_W1E | Items/StockMovement postoji |
| PropterSoba security | f026f1f4 | 16 issues zatvoreno |
| Design System 6 partials | cba1bc4c | stat_card, kanban_column, timeline... |
| BORG Hub | 6f5e5004 | /hub/ live |
| Experiences 12 templates | prethodna sesija | 23/23 simulate_borg |
| CardActivity is_public_facing | 0147306a | sigurnosna zaštita za QR |
| simulate_borg 45 modula | 48fba3a2 | 114/114 (100%) |
| Golubar (u udruge app) | 547b4cdb + udruge/urls.py | /hr/udruge/golubar/ live |

---

## ❌ OSTAJE — Stvarno preostalo do 15.4.

### KRITIČNO (blokira launch)
- [ ] **Backup verification** — `/var/backups/` ima sys backupe, ali NE backup baze
  - Napraviti: `pg_dump fina_connect | gzip > /var/backups/fina_connect_$(date +%Y%m%d).sql.gz`
  - Celery beat task za dnevni backup
  - Test restore procedure

### VISOKO
- [ ] **REST API stub** — /api/v1/ → 404, treba za channel manager (H2.1)
  - Minimalno: invoices, partners, inventory (read-only)
- [ ] **DE lokalizacija minimum** — POS interface za Nikša (nema .po fajlova za DE)
  - Minimalno: POS screen labels, invoice PDF headers

### SREDNJE (nice-to-have za launch)
- [ ] **Commercial Doc Engine Sprint 2** (AI sloj) — CC_TASK postoji
- [ ] **ISO 27001 gap analiza** — dokument

---

## IVAN — AKCIJE (samo tebi)
1. **5.4.2026** — Naruči Hetzner CCX33 (89€/mj, Konjik d.o.o.)
2. **Uskoro** — Kontakt Kruljac Ivica (pilot OPG)
3. **Uskoro** — Pošalji brošuru Viktoru (Didin Konak)
4. **Uskoro** — 2-3 računovođe u Slavoniji (30+ klijenata)

## ESKALACIJA — SAMO za:
1. Naručiti CCX33 server
2. FINA certifikat za produkciju
3. Platiti za dodatne API ključeve
