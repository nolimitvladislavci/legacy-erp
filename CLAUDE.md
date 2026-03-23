# LIMIT Connect — Upute za AI agente
*Ažurirano: 22.03.2026 22:00 — Sonnet (usklađivanje)*

---

## Server
```
root@37.27.248.86 | /var/www/fina-connect
. venv/bin/activate
systemctl restart gunicorn-fina celery-worker celery-beat
```

## Pravila — UVIJEK

1. **Tema:** crna-zlatna (`--black:#0a0a0a`, `--gold:#c9a84c`), fontovi Cormorant Garamond + Barlow
2. **Branding:** "LIMIT Connect" — NE "Fina Connect", NE "ERP"
3. **Slogan:** "Fiskalizacija u džepu"
4. **HTML forme:** native `<label><input type="radio">` — NIKAD JavaScript onclick za selekciju. Mora raditi na mobitelu.
5. **Tenant isolation:** SVAKI query mora imati `company=` filter.
6. **Prije pisanja koda:** pročitaj stvarna polja iz models.py. Ne pretpostavljaj nazive (greške bile: grand_total umjesto total, PaymentMethod umjesto Method).
7. **Istina uvijek:** nikad prešutjeti problem, bug, rizik ili bolju opciju.
8. **Revolucionarne stvari** (MCP, arhitekturne promjene): proaktivno reći, ne čekati da Ivan pita.

---

## Task fajlovi

- **Naming:** `CC_TASK_YYYYMMDD_OPIS.md` (datum obavezan)
- **Jednokratni:** napiši → agent odradi → obriši
- **Nikad > 10 aktivnih** — prioritiziraj i obriši stare
- **Trajni kontekst** ide u CLAUDE.md ili FENIX_STATUS.md, ne u task fajlove
- **Koordinacijski fajl:** `FENIX_STATUS.md` — čitaj SVAKI TASK. Ako je DONE tamo — NE RADIŠ PONOVO.

---

## Aktivni task fajlovi (22.03.2026)

| Fajl | Opis | Agent | Prioritet |
|------|------|-------|-----------|
| `CC_TASK_20260322_SHARE_NAV_WIZARD.md` | Share invite tracking + nav partial + cashier wizard | CC | **VISOK** |
| `CC_TASK_20260322_MULTI_KONOBAR_PRETPLATE.md` | Multi-konobar PIN preuzimanje + pretplate + logo POS | CC | **VISOK** |
| `CC_TASK_POS_REDESIGN_3KLIKA.md` | POS 3 klika — TaxRate seed, wizard, cashier OIB | CC | **VISOK** |
| `CC_TASK_ROBOT_PRODAVAC_KOMPLET.md` | Robot prodavač — Šeki pilot (kiosk, Stripe, QR plakati) | CC | SREDNJI |
| `CC_TASK_TESTS_PREDKOMORA.md` | 15 testova StagingFileHeader + Predkomora | CC | SREDNJI |
| `GEMINI_TASK_TESTS_HASHCHAIN.md` | 13 testova Hash Chain + PLG chain_link_safe | Gemini | SREDNJI |
| `GEMINI_TASK_LIMIT_AI_COMPLIANCE.md` | ComplianceWatchdog Faza 2 | Gemini | SREDNJI |
| `CC_TASK_20260322_BACKLOG.md` | Konsolidirani backlog | — | REFERENCA |

**Napomena:** CC_TASK_LIMIT_AI_FUNDS.md naveden u STATUS-u ali fajl ne postoji — treba napisati.

---

## Arhitektura — ključni moduli

### Cockpit (refaktorizirano 22.03. — commit 8d44bad)
- `core/cockpit_views.py` — **NOVI FAJL** — sve cockpit funkcije izolirane iz core/views.py
- `COCKPIT_USERS = frozenset(...)` — jedino mjesto za access listu (bio rasut 5x)
- `_cockpit_allowed(user)` + `_cockpit_guard(request)` — shared helpers
- `@cockpit_required()` dekorator u `permissions/decorators.py`
- `core/views.py` smanjen 2815 → 2414 linija
- `helpdesk/whatsapp_webhook.py` → delegira normalize_phone na `core.whatsapp.normalize_phone`

### Share sistem
- `templates/includes/_share_modal.html` — globalni share modal (WhatsApp, Email, QR, Print, Copy)
- Pozivanje: `openShare({type:'receipt'|'invoice'|'document', id:123, title:'...'})` 
- Trenutno uključen samo u: `pos/quick.html`, `pos/receipt_list.html`
- **NEDOSTAJE** na: arhivi, invoicingu, partnerima

### Nav buttons
- `templates/includes/_nav_buttons.html` — **TREBA KREIRATI**
- Pattern: Natrag / Odustani / [Submit Nastavi →]
- Pozivanje: `{% include "includes/_nav_buttons.html" with back_url="..." forward_label="..." cancel_url="..." %}`

### POS
- `pos/models.py` → `POSCashier` model: name, pin_hash, oib, set_pin(), check_pin()
- `templates/pos/onboarding.html` → wizard s koracima (progress bar)
- `templates/pos/quick.html` → glavna blagajna (share modal tu postoji)
- Multi-konobar: PIN preuzimanje → bon bilježi cashier OIB
- Besplatni plan: 1 terminal, soft banner pri otvaranju 2. terminala

### Livestock/Vet (bugfixi 22.03.)
- PDF integrity badge: bio dvostruki `render_to_string` — POPRAVLJENO
- Robot API: auto-zapisuje MilkRecord (params: jutarnja_l, vecernja_l)
- `inspector_invalid.html` template kreiran
- WhatsApp notify: phone fallback na UserProfile admin
- JRDZ scope: species_code='GVD' + sex M/F dodano
- OPG robot_api_key postavljen u Company.settings
- **OTVORENO:** `sex` polje direktno na Livestock modelu (trenutno se izvodi iz vrste — nije precizno)
- 47 testova u `livestock/tests.py` (6 klasa)

### Arhiva / Smart Import
- `templates/documents/arhiva_list.html` → lista dokumenata (nema share)
- `smart_import/` → Predkomora OCR pipeline
  - `StagingBatch` → `StagingFile` → `StagingFileHeader`
  - `extract_invoice_header()` — Gemini OCR za zaglavlje
  - `auto_match_partner()` — OIB → Partner auto-spajanje

### Hash Chain (commit 73a0701)
- `pos/hashchain.py` → ChainLink, append_receipt(), verify_chain(), verify_single()

### PLG Virus (commit 81ee45a)
- `templates/pos/includes/_viral_footer.html` — share/promo footer na svim dokumentima

### OIB / VAT Lookup
- `core/oib_validator.py` → validate_oib_hr() ISO 7064, validate_vat_id() HR/DE/AT/SI
- `core/business_lookup.py` → lookup_business(tax_id, country, company)
  - HR: VIES → FINA Info.BIZ → fallback
  - DE: VIES (USt-IdNr) — Kleinunternehmer = ručni unos
  - **NEDOSTAJE:** validate_steuernummer_de() za lokalni DE porezni broj

---

## Aktivni klijenti

| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Seki Temaj | Uvijek Friško | POS (3 lok, 5 term), Pickup QR, Booking | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRačun, Invoicing, Konto | LIVE |
| Nikša Visković | Viskovic Bau | DE market, GoBD, TSE, DSFinV-K | ONBOARDING |
| Dragan Jakovljevic | Viskovic Bau | Partner (Strategie), superadmin | ONBOARDING |
| Slađana Kruljac | O.P.G. Kruljac + Korpaš d.o.o. | Livestock, Vet, Arhiva | LIVE |

### Korpa grupa (registrirane 22.03.)
| Firma | OIB | User | Email |
|-------|-----|------|-------|
| Korpaš d.o.o. | 92922919857 | katarina.furdi | katarina.furdi@limit-connect.com |
| KUD Dukat Vladislavci | 12817544866 | kud.dukat | kud.dukat@limit-connect.com |
| O.P.G. Kruljac Slađana | 41439993573 | opg_kruljac | opg.kruljac@limit-connect.com |
| Furdi, obrt | 88069902084 | furdi.obrt | furdi.obrt@limit-connect.com |
| Dubinsko Čišćenje Čizo | 69824516722 | cizo.ciscenje | cizo.ciscenje@limit-connect.com |

### Superadmini
| User | Firma |
|------|-------|
| superadmin / antonio.brtan | Platform owner (Ivan Brtan) |
| marija.brtan | Konjik d.o.o. |
| niksa.viskovic | Viskovic Bau |
| dragan.jakovljevic | Viskovic Bau |

---

## Git HEAD
`8d44bad` — Refactor: cockpit izolacija + globalni dekorator + normalize_phone unifikacija
