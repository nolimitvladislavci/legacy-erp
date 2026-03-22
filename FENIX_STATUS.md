# FENIX STATUS — Koordinacijski fajl
# Svi agenti citaju OVO prije svakog taska.
# PRAVILO: Ako nesto pise DONE ovdje — NE RADIS PONOVO.
# PRAVILO: Prije nego stavis task u plan — provjeri ovaj fajl.

---

## Zadnje azuriranje
2026-03-23 — Sonnet (Share modal + nav partial + cashier wizard)
Git HEAD: 7d49022 — Share: invite tracking + arhiva/invoicing + nav partial + cashier wizard

---

## Git HEAD
8d44bad — Refactor: cockpit izolacija + globalni dekorator + normalize_phone unifikacija

## Aktivni klijenti
| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Seki Temaj | Uvijek Frisko | POS (3 lok, 5 term), Pickup QR, Booking | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRacun, Invoicing, Konto | LIVE |
| Niksa Viskovic | Viskovic Bau | DE market, GoBD, TSE, DSFinV-K | ONBOARDING |
| Dragan Jakovljevic | Viskovic Bau | Partner (Strategie), superadmin | ONBOARDING |
| Slađana Kruljac | O.P.G. Kruljac + Korpaš d.o.o. | Livestock, Vet, Arhiva | LIVE (obiteljska priča) |

## Korpa klijenti (nova grupa — 22.03.)
| Firma | OIB | User | Email |
|-------|-----|------|-------|
| Korpaš d.o.o. | 92922919857 | katarina.furdi | katarina.furdi@limit-connect.com |
| KUD Dukat Vladislavci | 12817544866 | kud.dukat | kud.dukat@limit-connect.com |
| O.P.G. Kruljac Slađana | 41439993573 | opg_kruljac | opg.kruljac@limit-connect.com |
| Furdi, obrt | 88069902084 | furdi.obrt | furdi.obrt@limit-connect.com |
| Dubinsko Čišćenje Čizo | 69824516722 | cizo.ciscenje | cizo.ciscenje@limit-connect.com |
- Podaci učitani iz Synesis arhive (Storage.mdb Settings)
- Novi korisnici lozinke poslane na +4915771998747 via WhatsApp

## Superadmini
| User | Login | Firma |
|------|-------|-------|
| Ivan Brtan | superadmin / antonio.brtan | Platform owner |
| Marija Brtan | marija.brtan | Konjik d.o.o. |
| Niksa Viskovic | niksa.viskovic | Viskovic Bau |
| Dragan Jakovljevic | dragan.jakovljevic | Viskovic Bau |

---

## DONE — NE DIRATI

### Share Modal + Nav Partial + Cashier Wizard (KOMPLET — 23.03.)
- _share_modal.html: ref_code invite tracking (_shRefCode, _shGetBaseUrl s ?ref=) — DONE
- _share_modal.html: viralni footer s dinamičnim ref linkom — DONE
- templates/includes/_nav_buttons.html: globalni nav partial kreiran — DONE
- arhiva_list.html: share dugme 📤 na svakom dokumentu — DONE
- invoice_list.html: share dugme 📤 na svakom računu + share modal include — DONE
- pos/views.py: cashier_setup view (GET/POST, PIN hash, OIB validacija) — DONE
- pos/urls.py: /hr/pos/cashier/setup/ URL — DONE
- templates/pos/cashier_setup.html: forma s OIB MOD11 JS validacijom — DONE
- onboarding_wizard: Blagajnik korak vodi na /hr/pos/cashier/setup/ — DONE
- Commit: 7d49022

### Cockpit 10/10 (KOMPLET — 22.03.)
- core/cockpit_views.py NOVI FAJL — sve cockpit funkcije izolirane — DONE
- COCKPIT_USERS = frozenset — jedino mjesto za access listu (bilo 5x rasuto) — DONE
- _cockpit_allowed() + _cockpit_guard() shared helpers — DONE
- @cockpit_required() dekorator u permissions/decorators.py — DONE
- core/views.py: 2815 → 2414 linija (-401), 0x _cockpit_users, 0x tim_chat duplikata — DONE
- helpdesk/_normalize_phone delegira na core.whatsapp.normalize_phone — DONE
- Context mismatch fix (users_week, pos_promet, disk_used, mem_used, pos_week...) — DONE
- disk parsing: disk[2]=used, disk[3]=free (bio krivi) — DONE
- pos_by_company: row.b i row.p annotate aliasi — DONE
- JS sendMsg() kompletno prepisan — 63/63 braces balanced — DONE
- JS ctrlAction() + getCsrf() unified — DONE
- Marija WhatsApp gumb + foto upload za sva sjedala — DONE
- partner_signup_api + cockpit API viewovi vraćeni nakon greške — DONE
- Commit: 8d44bad, 9d7a68a, 8b5eb7f

### Livestock/Vet modul bugfixi (22.03.)
- PDF integrity badge duplikat (dvostruki render_to_string) — FIX DONE — DONE
- Robot API auto-zapisuje MilkRecord (jutarnja_l/vecernja_l params) — DONE
- inspector_invalid.html template kreiran — DONE
- WhatsApp notify s phone fallback na UserProfile admin — DONE
- JRDZ scope: species_code='GVD' + sex M/F dodano — DONE
- OPG robot_api_key postavljen u Company.settings — DONE
- OPG i Korpaš phone broj (0976091655) dodan — DONE
- 47 testova napisano u livestock/tests.py (6 klasa) — DONE (izvršavanje u pozadini)

### Korpa firme registracija (22.03.)
- 5 firmi: email, address, zip, IBAN popunjeni iz Synesis Settings — DONE
- 3 nova korisnika kreirana (kud.dukat, furdi.obrt, cizo.ciscenje) — DONE
- 2 postojeća korisnika email ažuriran (katarina.furdi, opg_kruljac) — DONE
- Lozinke poslane na +4915771998747 WhatsApp — DONE

### [SVE PRETHODNO IZ PRETHODNIH SESIJA — NEPROMIJENJENO]
### Udruge modul (KOMPLET)
### FINA izvjestaji (KOMPLET)
### DE KassenSichV (KOMPLET)
### EU Fondovi + Volonteri (KOMPLET)
### AML + Napojnice + Voucheri (KOMPLET)
### Payments (KOMPLET)
### i18n (FAZA 1 KOMPLET)
### POS Offline (KOMPLET)
### FenixCamera (KOMPLET — 19 templatea)
### Transport modul Faza 1 (KOMPLET)
### Korpa Synesis Import (KOMPLET)
### Knjiga boljitaka (12/21)
### Infrastruktura (KOMPLET)
### Sales + Onboarding (KOMPLET)
### Dokumenti + PDF (KOMPLET)
### Mobile (KOMPLET)
### MCP Server (KOMPLET)
### WhatsApp (KOMPLET)
### Tim Chat (KOMPLET)
### Country Registry (KOMPLET)
### AI Tools v2 (KOMPLET)
### Livestock modul (KOMPLET — V1+V2+V3)
### Intelligence modul (KOMPLET)
### VetIS + Vet Portal (KOMPLET)
### Institutional API (KOMPLET)
### limit_connect_ai Faza 1 (KOMPLET)
### GTM Foundation (KOMPLET)
### Invoice-Powered Growth Engine (KOMPLET)
### Predarhiva Bulk OCR (KOMPLET)
### Predkomora — Smart Import Review (KOMPLET)
### Fiskalizacija bug fix (KOMPLET)
### Hash Chain — Kriptografski Audit Trail (KOMPLET)
### PLG Virus — Viralni Footer (KOMPLET)
### OIB / VAT Validator (KOMPLET)
### POS QR Instant Open (KOMPLET)
### Šeki Robot Prodavač — Plan (KOMPLET)

---

## TASKOVI ZA AGENTE

### Aktivni task fajlovi na serveru
| Fajl | Agent | Prioritet |
|------|-------|-----------|
| CC_TASK_20260322_SHARE_NAV_WIZARD.md | CC | **VISOK** |
| CC_TASK_20260322_MULTI_KONOBAR_PRETPLATE.md | CC | **VISOK** |
| CC_TASK_POS_REDESIGN_3KLIKA.md | CC | **VISOK** |
| CC_TASK_ROBOT_PRODAVAC_KOMPLET.md | CC | SREDNJI |
| CC_TASK_TESTS_PREDKOMORA.md | CC | SREDNJI |
| GEMINI_TASK_TESTS_HASHCHAIN.md | Gemini | SREDNJI |
| GEMINI_TASK_LIMIT_AI_COMPLIANCE.md | Gemini | SREDNJI |
| CC_TASK_20260322_BACKLOG.md | — | REFERENCA |

### Nedostaje — treba napisati
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi workflow Faza 2 (bio najavljen, fajl ne postoji)

---

## OTVORENO — treba raditi

### Livestock — još nedostaje
- sex polje direktno na Livestock modelu (trenutno se izvodi iz vrste — nije precizno) — OTVORENO
- Testovi (47 komada) — provjeriti rezultate izvršavanja

### DE Compliance
- Fiskaly sandbox test (treba API kljuceve) — CEKA
- DATEV SKR03/04 kontni plan — OTVORENO
- DATEV Buchungsstapel export — OTVORENO
- Steuernummer validacija (validate_steuernummer_de) — NEDOSTAJE

### Knjiga boljitaka (preostalo — 9/21)
- B-01 Offline cross-device sync — DJELOMICNO
- B-05 WaiterShift heartbeat — OTVORENO
- B-06 Konobar race condition — DJELOMICNO
- B-09 QR error toast — DJELOMICNO
- B-10 Claim race condition — DJELOMICNO
- B-11 QR bez emaila loyalty — OTVORENO
- B-13 Kitchen API rate limit — OTVORENO
- B-17 OCR confidence — OTVORENO
- B-21 Print QR label — DJELOMICNO

### Transport Faza 2
- CMR automatski iz TransportOrder — OTVORENO
- Multi-country routing UI — OTVORENO
- Kabotaža counter (max 3/7 dana) — OTVORENO
- Driver PWA kompletni — OTVORENO

### LIMIT Connect AI — Faze 2-4
- CC_TASK_LIMIT_AI_FUNDS.md — EU fondovi workflow — TREBA NAPISATI
- GEMINI_TASK_LIMIT_AI_COMPLIANCE.md — ComplianceWatchdog — SPREMAN ZA GEMINI
