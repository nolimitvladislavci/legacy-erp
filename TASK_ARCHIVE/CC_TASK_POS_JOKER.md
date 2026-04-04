# CC_TASK_POS_JOKER — Unified POS Interface

**Status:** IN PROGRESS
**Datum:** 2026-03-27
**Prioritet:** P0 — Arhitekturna promjena

---

## Vizija

Jedan POS template (`pos/joker.html`) servira SVE pos_type-ove.
Profil terminala (pos_type + quick_actions) bira mod — korisnik nikad ne bira POS tip ručno.

**Princip:** "Jedna blagajna, beskonačno lica."

---

## Analiza zatečenog stanja

| Aspekt | Status |
|--------|--------|
| 6 pos_type-ova | quick, retail, restaurant, field, service, reception |
| Checkout service | pos_type se NE koristi (0 referenci) |
| Fiskalizacija | pos_type se NE koristi (0 referenci) |
| Receipt model | nema pos_type polje — svi racuni identični |
| quick vs retail | JEDNA TIPKA razlike (search) |
| quick.html | 1167 linija |
| restaurant.html | 317 linija |
| Quick Actions | vec dinamicke po pos_type (get_default_quick_actions) |

### Ključni uvid
- quick.html = "master" (status bar, cashiers, categories, product grid, basket, payment, PIN, Pfand, voucher, weight, scanner, fiscal shield, offline mode, rental/membership modals)
- restaurant.html = "mini" (table grid 20 stolova, side panel, autocomplete, payment overlay)
- **Spajanje = quick.html + gastro sekcija (conditional)**

---

## Faza 1 — Unified Template (ova sesija)

### 1.1 pos/joker.html
- Bazira se na quick.html (feature-complete)
- Dodaje {% if is_gastro %} blok za table grid
- Gastro: table grid IZNAD product grida, basket ostaje desno
- Svi modali ostaju (rental, membership, PIN, voucher, pfand, weight, scanner)
- Quick Actions panel ostaje — vec je dinamicki

### 1.2 pos_joker_view (unified view)
- Zamjenjuje quick_pos() i restaurant_pos()
- Jedan view, context ovisi o terminal.pos_type:
  - is_gastro = terminal.pos_type == 'restaurant'
  - Ako gastro: dohvati tables + open_receipts
  - Svi: dohvati inventory, categories, cashiers, quick_actions
- Template: pos/joker.html

### 1.3 URL routing
- /pos/joker/<terminal_id>/ — novi kanonski URL
- /pos/quick/<terminal_id>/ → redirect na joker
- /pos/restaurant/<terminal_id>/ → redirect na joker
- Selector (quick_pos_redirect) azuriran — svi idu na joker URL

### 1.4 JS strategija
- pos-quick.js ostaje (master JS)
- pos-restaurant.js ostaje (table management za gastro)
- Joker uključuje oba ako is_gastro, inace samo quick

---

## Faza 2 — Auto-registracija terminala (sljedeca sesija)
## Faza 3 — AI Pulse hint (future)

---

## Checkpoint kriteriji (Faza 1)
- [ ] pos_sim_all.py: 25/25 OK
- [ ] Django check: 0 issues
- [ ] Quick terminal otvara joker → identično kao stari quick
- [ ] Restaurant terminal → stolovi + quick basket
- [ ] Stari URL-ovi rade (redirect)
- [ ] Selector prikazuje sve terminale s joker URL-om
