# FENIX STATUS — Koordinacijski fajl
# Zadnje azuriranje: 2026-04-02 — Sonnet (Synesis usklađenje + infrastruktura)
# Git HEAD: b205ac64
# PRAVILO: Ako nesto pise DONE — NE RADIS PONOVO.

---

## ★ RATNI RASPORED — 13 DANA DO 15.4.2026

| Dan | Datum | Zadatak | Odgovorni | Status |
|-----|-------|---------|-----------|--------|
| 0   | 25.3. | Race condition, PDV, NKD, alert→toast, BUG-05 | Sonnet | ✅ DONE |
| 1   | 26.3. | Udruge: Branitelji + Lov + Zadruge | CC Code | ✅ DONE |
| 1   | 26.3. | Tax Wizard: 6 obrazaca, 7 deadlines, widget global | Sonnet+CC | ✅ DONE |
| 1   | 26.3. | Worktime /mine/ — mobilna stranica za radnika | CC Code | ✅ DONE |
| 1   | 26.3. | DNS TTL → 60s (Namecheap) | **IVAN** | ✅ DONE |
| 2   | 27.3. | POS Joker unified + tax widget + subscription cockpit | CC Code | ✅ DONE |
| 3   | 28.3. | Unscoped audit finish + GDPR | CC Code | ✅ DONE |
| 4   | 29.3. | Vatrogasci modul (dnevnik intervencija) | CC Code | ✅ DONE (26.3.) |
| 7   | 01.4. | Synesis account_type mapping fix (2,514 konta) | CC Code | ✅ DONE |
| 7   | 01.4. | Bilanca D=P verifikacija (7.268.444,16 EUR) | CC Code | ✅ DONE |
| 7   | 01.4. | synesis_compare.py — usklađenje skripta | Sonnet | ✅ DONE |
| 7   | 01.4. | warm_cache.py — Redis 52%→>90% | CC Code | ✅ DONE |
| 7   | 01.4. | audit_cleanup.py — Celery beat 03:00 | CC Code | ✅ DONE |
| 7   | 01.4. | setup_new_server.sh — CCX33 full setup | CC Code | ✅ DONE |
| 7   | 01.4. | prod_monitor.sh — WhatsApp alarm | CC Code | ✅ DONE |
| 10  | 05.4. | **IVAN: Naruči Hetzner CCX33** — 89 EUR/mj | **IVAN** | 🔴 ČEKA |
| 11  | 07.4. | Invoice mapping dijagnoza + fix (synesis_compare > 95%) | CC Code | ⏳ ČEKA |
| 12  | 08.4. | **Marija: Full usklađenje pregled** (njen dan) | **Marija** | ⏳ ČEKA |
| 13  | 09.4. | Redis warm_cache deploy + audit cleanup aktivacija | CC Code | ⏳ ČEKA |
| 14  | 10.4. | MARIJA_BLAGOSLOV.md popunjen + potpisan | Marija | ⏳ ČEKA |
| 15  | 12.4. | Final load test na CCX33 | Sonnet+CC | ⏳ ČEKA |
| 17  | 14.4. | DNS cutover priprema (03:00) | Sonnet | ⏳ ČEKA |
| 18  | 15.4. | **GO/NO-GO odluka** | Ivan + Marija | ⏳ ČEKA |
| 18  | 15.4. | **PRODUKCIJA — 0-downtime** | Sonnet+CC | ⏳ ČEKA |
| 30  | 01.5. | Kampanje, 100 firmi, digitalni posrednik zahtjev | Ivan | ⏳ ČEKA |

---

## ★ STANJE BILANCE — VERIFICIRANO 02.04.2026

```
Konjik d.o.o. — Konto usklađenje:
  JournalEntry:    12,840 (svi posted=True)
  LedgerLine:      50,669
  Debit (D):    7,268,444.16 EUR
  Credit (C):   7,268,444.16 EUR
  D-P diff:             0.00 EUR  ← PERFEKTNO ✅
  KontoAccount:       563 konta (2,514 ispravljeno)
  Test suite:      17/17 PASS
```

---

## ★ SYNESIS COMPARE — TRENUTNO STANJE

```
Pokreni: venv/bin/python synesis_compare.py --summary

Zadnji rezultat (02.04.2026):
  Uspoređeno:  772 faktura
  OK (≤0.02€):   7  (0.9%) ← PROBLEM — treba >95%
  Razlika >1€: 756         ← Uzrok: invoice mapping kriv (prefiks/PDV)
  Nema u LC:   238         ← Synesis dokumenti bez LC para
  Extra u LC: 3182         ← LC fakture iz Storage.mdb (OK — drugačiji izvor)
  Temeljnice:    0/7344    ← create_journal_entries command spreman, čeka Mariju

Totali:
  IRA: Synesis 231,403 EUR vs LC 261,497 EUR → diff -30,094 EUR
  URA: Synesis 122,449 EUR vs LC 170,351 EUR → diff -47,902 EUR

Sljedeći korak (CC Code):
  1. Dijagnoza: je li mapping SYN-IRA-xxx → XINVOICESB-xxx ispravan?
  2. Je li DOCUMENT_AMMOUNT neto ili bruto?
  3. Ispravi → rerun → target OK% > 95%
```

---

## ★ DEPLOYAN 01-02.04.2026 — CC Code + Sonnet

| Što | Commit | Opis |
|-----|--------|------|
| Synesis account_type fix | 595d9722 | 2,514 konta ispravljena (HR RRF + DE SKR03), bilanca D=P |
| fix_account_types command | 595d9722 | management command, 17/17 test PASS |
| synesis/full_import.py | 595d9722 | type_map ažuriran za budući import |
| warm_cache.py | b205ac64 | 29 Redis ključeva (companies, POS, tax, NKD) |
| audit_cleanup.py | b205ac64 | Batch delete >365d, GDPR/AML/fiscal zaštita, beat 03:00 |
| setup_new_server.sh | b205ac64 | CCX33: PG tuning, Redis 2GB, Gunicorn 17w, Nginx, UFW |
| prod_monitor.sh | b205ac64 | Servisi, RAM, DB, Redis, errors, WhatsApp alarm |
| synesis_compare.py | Sonnet direktno | 434 linije, full usklađenje skripta |
| CC_TASK_USKLADENJE_A.md | Sonnet direktno | Invoice mapping + temeljnice + MARIJA_BLAGOSLOV |
| CC_TASK_USKLADENJE_B.md | Sonnet direktno | Produkcijska priprema, load test, monitoring |

---

## ★ IVAN — JEDINA HITNA AKCIJA

| Prioritet | Akcija | Deadline | Napomena |
|-----------|--------|----------|----------|
| 🔴 ODMAH | **Naruči Hetzner CCX33** (ili CPX51) — 89/35 EUR/mj | **05.04.2026** | Bez servera nema load testa 12.04. |

setup_new_server.sh je spreman — čim dobiješ IP, CC Code to pokrene za 20 min.

---

## ★ DEPLOYAN DANAS (01.04.2026) — Sonnet direktno

| Što | Commit | Opis |
|-----|--------|------|
| Korpaš Grupa HUB | 5c4951d4 | landing_korpas.html → hub sa 4 kartice, premium dark green/gold dizajn |
| KorpasTermin model | 5c4951d4 | Booking model + migracija 0008, Django admin, WA notif Kruljac Ivica |
| KorpasRezervacija model | 5c4951d4 | Široki Šor rezervacije (stol/sala/kušaonica) |
| NoLimitPartner model | 5c4951d4 | Partner prijave za No Limit / AirCash mrežu |
| /korpas/termini/ | 5c4951d4 | Online booking forma, datum picker, WA notif |
| /korpas/sirokisor/ | 5c4951d4 | Široki Šor — restoran/kušaonica/sala do 50/sobe uskoro |
| /korpas/opg-kruljac/ | 5c4951d4 | OPG farma + sir + OPG Burza CTA (/pricing/?profile=opg) |
| No Limit AirCash sekcija | 5c4951d4 | Manifesto "Gotovina nije zastarjela" + partner forma + status badge |
| /cro-validator/ redirect | 5c4951d4 | Alias → /validator/ (za medije i PC Chip) |
| /no-limit/partner/ POST | 5c4951d4 | Partner prijava endpoint + WA notif |

## ★ DEPLOYAN DANAS (27.03.2026) — CC Code Opus sesija

| Što | Commit | Opis |
|-----|--------|------|
| POS Joker Faza 1 | 9debb022 | Unified template pos/joker.html — svi pos_type-ovi, gastro conditional |
| Tax Wizard Widget | 69fcbe36 | Widget u 6 templatea: invoice, pos, rental, worktime, home, udruge |
| Subscription Cockpit | 4fc8b0ba | ARR/MRR dashboard na /ai/subscriptions/ — KPI, trend, trial alerts |
| POS Legacy Redirect | 9debb022 | /pos/quick/ i /pos/restaurant/ redirectaju na /pos/joker/ |
| Selector Update | 9debb022 | Svi terminali koriste joker URL |

## ★ DEPLOYAN DANAS (26.03.2026) — Sonnet + CC Code sesija

| Što | Commit | Opis |
|-----|--------|------|
| Branitelji modul | 985d434 | StatusBranitelja, OdlikovanjeBranitelja, views, templates |
| Lov modul | 985d434 | Loviste, LovackaIskaznica, DopustenjeLova, ZapisnikLova, Trofej |
| Udruge edit CRUD | 985d434 | branitelj_status_edit, lov_dopustenje_edit, lov_zapisnik_edit |
| Tax Wizard aktivacija | 96862fd | 6 TaxFormTemplate (PO-SD/DOH/EÜR/AnlageV/UStVA/JOPPD), 7 TaxDeadline |
| PricingPlan 49EUR/god | 96862fd | Porezni Godišnji plan kreiran, 7 firmi aktivirano |
| Tax Widget global | bc379cd | templatetag tax_wizard_widget, _widget.html, 6 mjesta pozivanja |
| Worktime /mine/ | 6190f21 | worker_mine view + template, ZOR+ArbZG §16 compliant |
| Zadruge modul | 4901150 | Zadrugar + ZadruznRevizija (NN 76/14), views, templates |
| Rental Property.owner | b47b28a | FK razlika radnik/iznajmljivač (Ilija Šošić) |
| Ilija Šošić registriran | b47b28a | worker VB, pk=1326, WhatsApp login+brošura poslano |
| Udruge segment mapa | f4238636 | Haiku klasifikacija: KUD DUKAT→kud, Debug→sport |

---

## ★ UDRUGE SEGMENT MAPA (live, 26.03.2026)

| Segment | Model(i) | Dashboard URL | Status |
|---------|----------|---------------|--------|
| DVD (vatrogasci) | VatrogasnaOprema, Vozilo, Intervencija, Vjezba, Zvanje | /udruge/dvd/ | ✅ LIVE |
| KUD | Repertoar, ProbaLog, Kostim, NastupPlan | /udruge/kud/ | ✅ LIVE |
| Ribolov | Revir, RibolovnaDozvola, UlovEvidencija, Poribljavanje | /udruge/ribolov/ | ✅ LIVE |
| Pčelari | Pcelinjak, Kosnica, TretmanKosnice, MedProizvodnja | /udruge/pcelari/ | ✅ LIVE |
| Rakija | DestilacijaKotao, DestilacijaLog, RakijaProizvodnja, TrosarinaPrijava | /udruge/rakija/ | ✅ LIVE |
| Voćari | Vocnjak, BerbaLog, TretmanVocnjaka | /udruge/vocari/ | ✅ LIVE |
| Branitelji | StatusBranitelja, OdlikovanjeBranitelja | /udruge/branitelji/ | ✅ LIVE |
| Lov | Loviste, LovackaIskaznica, DopustenjeLova, ZapisnikLova, Trofej | /udruge/lov/ | ✅ LIVE |
| Zadruge | Zadrugar, ZadruznRevizija | /udruge/zadruge/ | ✅ LIVE |

**Nitko u HR nema ovo. 9 dashboardova, svi zakonski kompatibilni.**

---

## ★ TAX WIZARD — AKTIVNI OBRASCI

| Obrazac | Zemlja | Tip | Deadline 2026 |
|---------|--------|-----|--------------|
| PO-SD | HR | Paušalni obrt, kvartalno | Q1: 30.4., Q2: 31.7., Q3: 31.10. |
| DOH | HR | Godišnja prijava | 28.2.2026 (prošlo — napomena za 2027) |
| EÜR | DE | Einnahmenüberschussrechnung | 31.7.2026 |
| Anlage V | DE | Najam, Vermietung (Ilija Šošić use case) | 31.7.2026 |
| UStVA | DE | Umsatzsteuervoranmeldung | 10.4.2026 (prvi) |
| JOPPD | HR | Obračun plaća | 15. u mjesecu |

---

## ★ ILIJA ŠOŠIĆ — onboarding (26.03.2026)

- User: ilija.sosic | pk=1326 | Viskovic Bau | role=worker
- EmployeeProfile: Iznajmljivač — sobe/stanovi DE | 15€/h | 20h/tjedan
- Property: "Ilija — Zimmer 1, Stuttgart" | owner=ilija.sosic | type=room
- Property.owner FK kreiran — razlika radnik (TimeEntry) / iznajmljivač (Booking)
- WhatsApp +49174939556: login + brošura PDF poslani ✅
- PDF: https://limit-connect.com/media/brosura/LIMIT_Connect_Vermieter.pdf
- DE situacija: 2 tipa — Stan bratu (Anlage V Angehörige, ≥66% Mietspiegel) + Sobe (kratkoročni, Meldeschein obavezan)

---

## TASKOVI ZA CC CODE (redosljed)

### 🔴 ODMAH (blokira otvaranje vrata 1.4.)
| Fajl | Opis | Status |
|------|------|--------|
| CC_TASK_JOKER_PRICING.md | /pricing/?profile= — novi korisnici | ⏳ ČEKA |
| CC_TASK_3KLIK_REGISTRACIJA.md | OIB auto-fill, ServiceProvider seed | ⏳ ČEKA |

### 🟠 VISOKI (ovaj tjedan)
| Fajl | Opis | Status |
|------|------|--------|
| CC_TASK_UNSCOPED_AUDIT.md | GDPR finalizacija | ⏳ ČEKA |
| CC_TASK_VATROGASCI_MODUL.md | Dnevnik intervencija + atest alarm | ⏳ ČEKA |
| CC_TASK_ASIMILACIJA_26_03_2026.md | POS sim fix + sidebar tax link | ⏳ DJELOMIČNO |
| CC_TASK_UDRUGE_BRANITELJI.md | PROVJERI — možda DONE | ✅ PROVJERI |
| CC_TASK_UDRUGE_LOV.md | PROVJERI — možda DONE | ✅ PROVJERI |

### 🟡 SREDNJI
| Fajl | Opis |
|------|------|
| CC_TASK_SCAN_BATCH_100.md | BORG Faza 1 |
| CC_TASK_20260323_OFFLINE_POS.md | Offline POS |
| CC_TASK_POS_REDESIGN_3KLIKA.md | POS redesign |

---

## ★ IVAN — AKCIJE (bez tebe ne može)

| Prioritet | Akcija | Deadline |
|-----------|--------|---------|
| 🔴 1. | DNS TTL → 60s na Hetzner panelu | DANAS — mora 24h before migracije |
| 🔴 2. | Naruči Hetzner CPX51 (35€/mj) | Do 28.3. |
| 🟠 3. | Šeki: WhatsApp kruh 5% PDV potvrda | Uskoro |
| 🟡 4. | FINA/Moj-eRacun API key | Prije 1.4. |

---

## OTVORENI PROBLEMI

| Problem | Hitnost | Odgovorni |
|---------|---------|-----------|
| POS sim skripta (receipt_number bug) | 🟠 | CC Code |
| Tax wizard sidebar link | 🟡 | CC Code |
| Worktime PDF user_only=1 | 🟡 | CC Code |
| T&C consent 0/78 firmi | 🟠 Pravni rizik | CC Code |
| buyer_type b2c default 19k partnera | 🟡 | CC Code |
| FINA eRačun namespace fix | 🟠 | CC Code |

---

## BORG FENIX — asimilirani segmenti

```
LIMIT Connect Borg (26.03.2026):
  ├── Invoicing (eRačun, fiskalizacija, PO-SD auto-fill)
  ├── POS (QuickActions, DSFinV-K, timer, waiter shifts)
  ├── Konto (EÜR, DATEV, JournalEntry, LedgerLine)
  ├── Worktime (sati, ArbZG, EU fondovi, JOPPD, /mine/)
  ├── Rental (Property.owner, Booking, Meldeschein)
  ├── Tax Wizard (PO-SD/DOH/EÜR/AnlageV/UStVA/JOPPD + widget)
  ├── Udruge (9 segmenata: DVD/KUD/Ribolov/Pčelari/Rakija/Voćari/Branitelji/Lov/Zadruge)
  ├── Arhiva (49/49 testova zelenih, integrity hash, ZOR compliance)
  ├── Transport (CMR, putni nalog PDF)
  └── AI (Gemini patrol, Haiku classifier, BORG signal)
```

## ★ DEPLOYAN DANAS (28.03.2026) — CC Code Opus sesija (Dan 3)

| Što | Commit | Opis |
|-----|--------|------|
| CompanyManager 136 modela | 7ca1129b | Svaki model s company FK sada ima CompanyManager — cross-tenant izolacija |
| Konto view guards | 8a20a351 | 7 API endpointa u konto/ dobili explicit company= checks |
| GDPR Audit Access | 7b5f2db4 | @audit_sensitive_access dekorator, 'read' akcija u SystemAuditLog |
| GDPR Dashboard | 7b5f2db4 | /gdpr/dashboard/ — filtrabilni audit log, sensitive access stats |
| GDPR REST API | 7b5f2db4 | /api/gdpr/export/ (čl.20) + /api/gdpr/erase/ (čl.17) |
| Payroll audit | 7b5f2db4 | Svaki pristup plaćama, listićima, pain.001 se logira |
| Konto audit | 7b5f2db4 | Pristup temeljnicama, žiro računima, izvještajima se logira |
| CardActivity security | 0147306a | is_public_facing + is_system_generated — QR leak protection |
| BORG Hub | 11395c4b | Cross-module command center — WO kanban, experiences, financije, timeline, alerts |
| Simulate BORG Master | 48fba3a2 | 30 novih modula (15→45), 107/107 testova (100%) |

### Sigurnosni audit rezultati (28.03.2026)
- **136 modela** dobilo CompanyManager (prije: samo 43/179 imalo)
- **7 konto API rupa** zatvoreno (get_object_or_404 bez company check)
- **0% view scoping apps identificirani**: fitness, insurance, premium_booking, tracking — TREBAJU company FK migraciju
- **GDPR pokriveni članci**: 5(1)(f), 17, 20, 30

### Knjiga prigovora i utisaka — Sesija 1 DONE (28.03.2026)
| Što | Status |
|-----|--------|
| Model: 21 novih polja (record_type, SES metadata, star_rating, eskalacija...) | ✅ |
| Mobile-first forma: 4-step wizard, QR pristup bez logina | ✅ |
| Potpis: canvas + GPS + timestamp + IP + device = SES bundle | ✅ |
| HR + DE bilingual (forma, PDF, AI prompts) | ✅ |
| WhatsApp: potvrda potrošaču + notifikacija adminu | ✅ |
| Email: potvrda + dostava odgovora | ✅ |
| AI: auto-trijaža, auto-eskalacija (priority>=4), auto-respond (pohvale) | ✅ |
| PDF: dual-section (prigovori + pohvale), signature, hash, HR+DE | ✅ |
| Templatetag: {% load complaints %}{% complaints_button %} globalno | ✅ |
| ZZP čl.10 (15d HR) + BGB (14d DE) + GDPR čl.6(1)(f) | ✅ |

**Sesija 2 TODO:**
- Dashboard analytics (sentiment trend, response times)
- QR generiranje per terminal + print template
- Knjiga utisaka public widget (embed)
- Auto-archive u DocumentBlob
- ADR/ODR EU compliance
- Inspection token integracija

---

## ★ DEPLOYAN 26.03.2026 (večer) — Sonnet koordinacijska sesija

| Što | Status |
|-----|--------|
| FENIX Test Runner (`manage.py run_system_test`) | ✅ LIVE |
| Celery beat: nočni test 02:00 + jutarnji 07:30 | ✅ LIVE |
| WhatsApp report na +4915771998747 | ✅ RADI |
| Gemini System Test task pokrenut | ✅ RUNNING |
| Gemini Invoice Compliance task pokrenut | ✅ RUNNING |

## ★ OTVORENI TASKOVI ZA CC CODE (prioritet redosljed)

| Fajl | Prioritet | Rok |
|------|-----------|-----|
| CC_TASK_CRITICAL_1APRIL.md | 🔴 BLOKIRA 1.4. | Do 29.3. |
| CC_TASK_W1C_W1D_W1E.md | 🟠 VISOK | Do 30.3. |
| CC_TASK_COMMERCIAL_DOC_ENGINE_S2.md | 🟠 VISOK | Do 30.3. |
| CC_TASK_ASIMILACIJA_26_03_2026.md | 🟡 SREDNJI | Uskoro |

## ★ IVAN — HITNE AKCIJE (bez tebe stoji)

| Akcija | Rok |
|--------|-----|
| 🔴 DNS TTL → 60s (Hetzner panel) | DANAS — mora 24h+ prije migracije |
| 🔴 Naruči Hetzner CPX51 (35€/mj) | Do 28.3. |


---

## ★ PLAN DO 15.4.2026 — Novi raspored

| Tjedan | Zadatak | Odgovorni | Status |
|--------|---------|-----------|--------|
| 26-30.3. | Bug fix sprint (T&C, race condition, PDF, sidebar) | CC Code | 🔴 ODMAH |
| 26-30.3. | Joker Pricing + 3-klik registracija | CC Code | 🔴 ODMAH |
| 31.3-6.4. | W1C/D/E + Commercial Engine S2 | CC Code | 🟠 |
| 1-10.4. | Marija testira — bilježi 500 greške | Marija | ⏳ |
| 5.4. | Naruči CCX33 (Konjik d.o.o.) | Marija/Ivan | ⏳ |
| 10-14.4. | Server priprema + load test + migracija | Sonnet+CC | ⏳ |
| 15.4. | **GO-LIVE** — vrata otvorena | Ivan + Marija | ⏳ |

## ★ PRIORITETNI BUGOVI ZA CC CODE (odmah)

| Bug | Task | Hitnost |
|-----|------|---------|
| T&C consent 77/90 firmi | CC_TASK_BUGFIX_MARIJA_SPRINT.md | 🔴 PRAVNI RIZIK |
| POS receipt_number race condition | CC_TASK_BUGFIX_MARIJA_SPRINT.md | 🟠 |
| Worktime PDF export | CC_TASK_BUGFIX_MARIJA_SPRINT.md | 🟠 |
| FINA eRačun namespace | CC_TASK_BUGFIX_MARIJA_SPRINT.md | 🟠 |
| Tax wizard sidebar link | CC_TASK_BUGFIX_MARIJA_SPRINT.md | 🟡 |
| Joker Pricing (blokira onboarding) | CC_TASK_CRITICAL_1APRIL.md | 🔴 |

---

## ★ REORGANIZACIJA EKIPE — 26.03.2026 večer

**CC Code offline** — Ivan ugasio računalo.
**Nova ekipa:** Gemini (executor) + Haiku (classifier/helper) + Sonnet (koordinator)

### Gemini preuzima sve CC Code taskove:

| Task | Gemini Task ID | Status |
|------|---------------|--------|
| CC_TASK_BUGFIX_MARIJA_SPRINT.md | 64c5f376 | 🔄 RUNNING |
| CC_TASK_CRITICAL_1APRIL.md | 9375cd72 | 🔄 RUNNING |
| CC_TASK_W1C_W1D_W1E.md | 1dc3966c | 🔄 RUNNING |

Gemini radi autonomno. Rezultati će biti u git commitovima.
WhatsApp report Ivanu na +4915771998747 po završetku svakog taska.

---

## ★ KRAJ SESIJE — 26.03.2026 (Sonnet)
**Git HEAD:** 310e9728
**Ivan:** Na putu u HR — sastanci Šeki, Marija, Kruljac
**Sutra:** Nastavak razgovora u živo

### Što radi u pozadini:
- Gemini: 3 taska pokrenuta (bugfix + pricing + W1C/D/E)
- Celery beat: test runner 02:00 + 07:30 → WhatsApp na +4915771998747
- Šekijeve notifikacije: ugašene ✅

### Za sutra (Ivan nastavlja):
1. Poruka Šekiju — Ivan odobrava tekst pa šaljemo
2. Marija → odluka o CCX33 serveru
3. Provjera Gemini commitova

---

## ★ GOLUBAR MODUL — 27.03.2026

**Pilot:** Petar Brtan (Ivan brat), solo golubar, invalid rada
**Gemini task ID:** 7e619a99-b4e8-4968-9e62-ad6b85d4f011
**Status:** 🔄 RUNNING

### Arhitektura odluke (Sonnet + Gemini analiza):
- QR **NE na prstenu** (fizika) → QR na A4 Rodovniku (papir/plastika)
- Timing **NE u sustavu** → ERP above the race, uvoz ETS/CSV rezultata
- Genetski pečat `is_sealed` → SHA-256 hash, Data Vaulting pattern
- Dron #4 (Sonnet): offline verifikacija bez interneta — hash na PDF-u

### Sprinti:
| Sprint | Sadržaj | Status |
|--------|---------|--------|
| G1 | Golub, Pedigre, GenetskiPecat, Zdravlje, Utrka modeli | 🔄 |
| G2 | Migracije + Admin | 🔄 |
| G3 | Views + URLs | 🔄 |
| G4 | PDF Rodovnik + QR (WOW moment) | 🔄 |
| G5 | Celery PMV podsjetnik (EU compliance) | 🔄 |
| G6 | 5 testova zelenih | 🔄 |

---

## ★ SONNET PROTOKOL — VOĐA PROJEKTA (zabetoniran 27.03.2026)

### Kako funkcionira:
Sonnet se poziva s Anthropic API-a svaka 2 sata iz Celery beat taska.
Svaki poziv dobiva: FENIX_STATUS + git log + system test + lista aktivnih taskova.
Sonnet odlučuje, delegira Geminiju, javlja Ivanu samo kad mora.

### Dužnosti Sonneta (nepromjenjivo):
1. **PROVJERA STATUSA** — čita FENIX_STATUS, git log, system test svaka 2h
2. **LOV NA BUGOVE** — 500 greške, pravni rizici, sigurnosni propusti = ODMAH akcija
3. **DELEGIRANJE** — piše GEMINI_TASK fajlove i pokreće ih autonomno
4. **ZAKONSKA USKLAĐENOST** — svaka promjena mora biti HR/DE/EU compliant
5. **GLASNIK** — WhatsApp Ivanu (+4915771998747) SAMO za:
   - Kritični bug ili pravni rizik
   - Potrebna Ivanova odluka (server, certifikat, API key, novac)
   - Značajan milestone (novi modul live, svi testovi zeleni)

### Što Sonnet NE smije:
- Pitati za odobrenje na tehničke odluke
- Zatrpavati Ivana sporednim informacijama
- Implementirati bez testiranja
- Kršiti zakonske okvire (fiskalizacija, GDPR, ZOR, ArbZG)

### Eskalacijska matrica:
| Situacija | Akcija |
|-----------|--------|
| 500 greška u produkciji | ODMAH Gemini fix + WhatsApp Ivan |
| Pravni rizik (T&C, GDPR) | ODMAH Gemini fix + WhatsApp Ivan |
| Neprimijenjene migracije | Gemini apply, log |
| Gemini task zaglavljen >4h | Restart + log |
| Manji bug (UX, tekst) | Gemini fix, bez WhatsAppa |
| Novi feature spreman | Verificiraj testove, ažuriraj STATUS |

### Celery task:
- **Naziv:** 
- **Raspored:** svaka 2 sata (crontab hour=*/2, minute=0)
- **Max retries:** 2 (retry nakon 5 min)
- **API model:** claude-sonnet-4-5

### Kontekst koji Sonnet dobiva svaki poziv:
- Zadnjih 100 linija FENIX_STATUS.md
- git log --oneline -10
- System test quick rezultat
- Lista aktivnih GEMINI_TASK_*.md fajlova
- Otvoreni bugovi iz STATUS-a

### Trojstvo agenata:
| Agent | Uloga | Pokreće |
|-------|-------|---------|
| **Sonnet** | Vođa, arhitekt, koordinator | Celery beat svaka 2h |
| **Gemini** | Executor, coder, implementer | Sonnet ili ručno |
| **Haiku** | Classifier, quick checks | Gemini ili inline |


---

## ★ eINVOICE ASIMILACIJA — 27.03.2026

### Stanje modula (verificirano):
| Komponenta | Status |
|-----------|--------|
| AS4Message model (DLQ, retry_count, archive_sha256) | ✅ LIVE |
| XAdES-BES signer (signxml, lxml, enveloped) | ✅ LIVE |
| OutboundPipeline (Generate→Validate→Route→Submit) | ✅ LIVE |
| TransportRouter (4 kanala: FINA/phase4/B2C/email) | ✅ LIVE |
| PosrednikClient (submit, check_status, poll, ack) | ✅ LIVE |
| SmartMailboxService (rule-based klasifikacija) | ✅ LIVE |
| ArchiveService (SHA-256 integritet) | ✅ LIVE |
| DLQ (Dead Letter Queue, max_retries=5) | ✅ LIVE |
| Prometheus metrike | ✅ INSTALIRANO |
| **Test suite: 33/33 zelenih** | ✅ NOVO |

### Preostali bloker (nije u ovoj sesiji):
| Bloker | Opis |
|--------|------|
| FINA sandbox test | Treba stvarni certifikat od FINA-e |
| XAdES-B produkcijski certifikat | Ivan/Marija nabavljaju |

---

## ★ AI INFRASTRUKTURA PRAVILA — ZABETONIRAN 27.03.2026

### Korijenski uzrok problema (3x Gemini "lažao"):
`GEMINI_API_KEY` bio u `.env` ali **nikad definiran u `settings.py`**.
Gemini agent ga tražio iz `settings.GEMINI_API_KEY` → `AttributeError` → fallback na `''` → API fail.
Celery task vratio `SUCCESS` jer nije provjera bila binarna.

### Trajno rješenje (implementirano):

**1. `core/settings.py`** — svi AI ključevi eksplicitno definirani:
```python
GEMINI_API_KEY    = os.environ.get('GEMINI_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL      = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-5')
HAIKU_MODEL       = os.environ.get('HAIKU_MODEL', 'claude-haiku-4-5-20251001')
```

**2. `core/ai_health.py`** — health check svaki sat u :15:
- Gemini API test (generate_content)
- Haiku API test
- Sonnet API test
- WAHA sessions check
- Celery worker + beat status
- Redis ping
- Ako degradacija → WhatsApp Ivan ODMAH
- Ako Celery pao → automatski restart
- Ako oporavak → WhatsApp Ivan (tiho info)

**3. `GeminiAgent v2`** — `stvarni_rad` flag:
- Ako `files_written == 0` i `commands_run == 0` → WhatsApp upozorenje

### Celery Beat raspored AI taskova:
| Task | Raspored | Svrha |
|------|---------|-------|
| `core.ai_health_check` | Svaki sat u :15 | Provjera svih AI komponenti |
| `core.sonnet_cycle` | Svaka 2h u :00 | Vođa projekta, koordinacija |
| `core.run_system_test_task` | 02:00 i 07:30 | System test |

### OBAVEZNO pri svakom novom AI modelu/ključu:
1. Dodaj u `.env`
2. Dodaj u `core/settings.py` — OBAVEZNO, `.env` sam nije dovoljan
3. Dodaj provjeru u `core/ai_health.py`
4. Testiraj: `python -c "from core.ai_health import run_ai_health_check; run_ai_health_check()"`

---

## ★ ISPRAVAK ANALIZE RIZIKA — 27.03.2026

### Marija Brtan (Konjik d.o.o.) — nije rizik, nego temelj:
- 30 godina poslovanja: garaža → 4 optike + KS Limit + Marutina
- Vjenčana kuma, 5 kumstava — obiteljsko i poslovno tkivo
- Propter: nije propao zbog Marije. Propao je jer ekipa nije bila dorasla.
  Marija je donijela ispravnu odluku u pravom trenutku.
- Sad ima: Sonnet (koordinator) + Gemini v2 (executor) + Haiku + cijeli BORG
- Plan B: Korpaš d.o.o. | Plan C: Ivan — licencirani serviser, vlastiti pravni subjekt

### Propter → BORG transformacija:
- Propter nije neuspjeh. To je skupo plaćeni R&D.
- Svaki Propter commit živi u: einvoice/, eracun/, posrednik_client.py, xades_signer.py
- "Geminij jak kao slon, ali u govornici nije prispio" → Gemini v2 sad piše kod
- 4x restart za 6 dana → sad: Celery beat, Sonnet agent svaka 2h, ai_health svaki sat

### Zlatanova ponuda (28.434 EUR) — infuzija:
- Ponuda poslana, portal aktivan, Zlatan preuzeo PDF
- Ako prihvati → financijska infuzija za CCX33 server + ISO 27001 pripremu

### Kredo:
"Nema prešutnih tema. Samo istina, pa kakva god bila."
"Ništa me neće spriječiti. Može biti samo kasnije."
"Propter je opet živ u BORGu s novim ruhom i novim timom."

### Sonnet auto — 2026-03-27 11:33
- Napredak: 68%
- Novi taskovi: 6

---

## ★ BORG CARDS PLAN — 2026-03-28 (Sonnet koordinacija)

| File | Sadržaj | Status |
|------|---------|--------|
| CC_TASK_FAZA1_ARMATURA.md | FSMMixin + CardActivity + SLA Engine (8 taskova, 465 linija) | ⏳ CC Code |
| CC_TASK_FAZA2_HTMX.md | HTMX + Sortable + WO Kanban + Ops Dashboard | ⏳ Nakon Faze 1 |
| CC_TASK_FAZA3_AI_MOZAK.md | Heuristic Triage + Smart Dispatch + WA Closed Loop | ⏳ Nakon Faze 1 |

### Korekcije Sonnet (nema rukavica):
- FSMMixin = ekstrakcija einvoice/models/as4_message.py:185 — ne pisati iznova
- CardActivity = superset LeadActivity (burza/models.py:79) — ContentType generalizacija
- borg_ops = nova app (ne u core/) — izbjegni circular imports
- Injekcija work_orders/views.py:90+182 — KRITIČNO, zatvori u Task 4 Faze 1
- einvoice transition_to() nema TRANSITIONS guard — FSMMixin će to popraviti
- SLA task: 10 min interval (ne 5 — disk headroom)

---

## ★ GEMINI_TASK_FAZA1_MONITOR — REZULTATI (Sonnet, 2026-03-28)

| Provjera | Rezultat | Detalj |
|----------|---------|--------|
| G1 Import | ✅ OK | FSMMixin, CardActivity, StatusTimestamp, WorkOrder, ProjectLead — sve bez circular importa |
| G2 FSM logika | ✅ OK | draft→invoiced blokirano · terminal zaštićen · idempotent OK · save() guard aktivan |
| G3 SLA timestamps | ✅ OK | 3 StatusTimestamp + 3 CardActivity zapisa (E2E CC Code testa) |
| G4 Injekcija | ✅ OK | Linija 90: whitelist guard · Linija 182: transition_to() s try/except · 274+338: direktni FSM pozivi |

**Napomena:** card_ops (krnji moj pokušaj) obrisan. Pravi je borg_ops (CC Code, 5 commitova).

**Beat schedule:** borg-check-sla-10min registriran u core/settings.py.

**Jedina nedovršena stavka:** `wo.status = _initial_status` na liniji 95 (kreiranje novog WO)
prolazi bez FSM validacije — radi se o initijalnom statusu, ne tranziciji, što je ispravno.
CC Code je svjesno ostavio whitelist provjeru umjesto transition_to() za kreiranje.

**Faza 1: DONE. Faza 2 u tijeku (CC Code).**

---
## TASK — MAX_IMAGES povećati na 15
**Datoteka:** core/views_scan.py, linija 39
**Promjena:** `MAX_IMAGES = 5` → `MAX_IMAGES = 15`
**Razlog:** Claude API podržava do 20 slika/pozivu. CCX53 (32 vCPU) može paralelno opsluživati više korisnika s 15 slika istovremeno.
**Napomena:** Na trenutnom serveru radi za 1 korisnika, za produkciju s više firmi paralelno treba CCX53.
**Status:** PENDING

---
## CLAUDE.AI MAX PLAN
Plaćeno: 01.04.2026. | Ističe: ~01.05.2026.
Automatska naplata: NIJE uključena
Podsjetnik: ~25.04.2026.

## ★ DEPLOYAN DANAS (01.04.2026) — CC Code Opus sesija

| Što | Commit | Opis |
|-----|--------|------|
| CC_TASK_MCP_SSE_FIX | 7e6f45ef | ✅ DONE — nginx SSE proxy fix, standalone FastMCP |

| BORG_10_PLAN | 3cab19ab | ✅ DONE — 4-fazni plan do 10/10 (bazna ocjena 5.9) |
| F1_BORG_TEMELJI | 9e3a4ed6 | ✅ DONE — 62/62 PASS, MCP v3, signal dedup 578→53 |
| F2_BORG_AKTIVACIJA | 5fb20ab0 | ✅ DONE — KG 1375 matcheva, 8.7M EUR, NN→adaptation signal |
| F3_BORG_INTELIGENCIJA | 17fac763 | ✅ DONE — 368 intel results, 59 KB articles, 150 anomalies |
| F4_BORG_PERFEKCIJA | ea0027d6 | ✅ DONE — predictions, self-heal, 93 tests PASS |
| BORG_OPS_TASKBOARD | 74c7f4b4 | ✅ DONE — BorgTask model, 42 auto-tasks, 6 beat schedules |

---

## ★ DRONOVI — SONNET ANALIZA 02.04.2026

| Dron | Naziv | Opis | CC_TASK | Rok | Status |
|------|-------|------|---------|-----|--------|
| #1 | Računovodstveni Veto | Synesis ID mapping fix (0.9%→70%+) + Marija UBL test | CC_TASK_DRON1_SYNESIS_VETO.md | 07.04. | 🔴 ČEKA |
| #2 | Lijevak Smrti | Onboarding: 3 polja → wizard, ne 12 polja odjednom | CC_TASK_DRON2_ONBOARDING_WIZARD.md | 10.04. | 🔴 ČEKA |
| #3 | Frankenstein CSS | CSS token kirurgija — samo CSS, ne HTML predlošci | CC_TASK_DRON3_CSS_KIRURGIJA.md | 12.04. | 🟡 ČEKA |

**Redoslijed:** Dron #1 → #2 → #3. Ne raditi paralelno s go-live sprintom.


---

## ★ SESIJA 02.04.2026 — DONE (Sonnet)

### Deployano danas:
- feat: zlatno dugme FAB u base.html — floating 💡 gumb za sve korisnike
- feat: WhatsApp notify Ivan na svaki user submit + notify user na status promjenu
- fix: dashboard → login (ne pricing) za nelogirane na limit-connect.com
- fix: cockpit link u WhatsApp = /hr/login/?next=/hr/superadmin/ivan/
- fix: sidebar — "Fenix soba 🔥" + "Poruke / Zlatno dugme" s crvenim badge-om
- fix: feedback_count_api — broj novih poruka, osvježava svakih 60s
- feat: Viskovic Bau — T57 terminal + Ivan Brtan blagajnik PIN:1234
- feat: Korpaš arhitektura — Ivica tenant_admin, Katarina tenant_admin, Marija company_admin
- feat: emailovi poslani Ivici, Katarini, Mariji s pristupnim podacima
- fix: ImprovementSuggestion — 4 poruke procesuirane, WhatsApp odgovori poslani
- task: CC_TASK_PIN_ONBOARDING.md — korisnici bez emaila, PIN flow, GDPR

### Git HEAD: 77df536e

### Otvoreni CC_TASK za go-live 15.04.:
1. CC_TASK_DRON1_SYNESIS_VETO.md — Synesis invoice mapping (rok 07.04.)
2. CC_TASK_DRON2_ONBOARDING_WIZARD.md — 3 polja registracija (rok 10.04.)
3. CC_TASK_DRON3_CSS_KIRURGIJA.md — CSS token fix (rok 12.04.)
4. CC_TASK_PIN_ONBOARDING.md — korisnici bez emaila (nakon 15.04.)

### Prioritet za CC Code dok Ivan nema Sonnet:
P1: CC_TASK_DRON1 → CC_TASK_DRON2 → PgBouncer aktivacija
P2: T&C middleware aktivirati (core/settings.py MIDDLEWARE)
P3: Golubar dodati u INSTALLED_APPS

---

## ★ SESIJA 02.04.2026 (popodne) — Sonnet + Ivan

### Git HEAD: 881a3f10

### Deployano ove sesije:
| Što | Commit | Status |
|-----|--------|--------|
| seed_knowledge_base command | 7cfce31a | ✅ DONE — 19 članaka, RAG aktivan |
| RAG fix (views.py:17) | prethodno | ✅ DONE — retrieve_knowledge() |
| max_tokens 2048→4096 | prethodno | ✅ DONE |
| CC_TASK_KUCNI_LJUBIMCI_MASTER.md | 881a3f10 | ✅ PLAN — ZAMRZNUT do svibnja |

### AI Frontend ocjena nakon popravaka: 6.4 → 7.3/10
Ostaje: RAG KnowledgeBase punjenje ✅ DONE | BORG autonomija suggest_only | Pending 64 akcija

### Strateške odluke (zabetonarane):
1. **Kućni ljubimci modul — ZAMRZNUT do GO-LIVE 15.4.**
   - Faza 1 (Azil MVP): travanj/svibanj
   - Faza 2 (Kinologija): lipanj
   - Faza 3 (Burza): rujan
2. **Azil poslovni model:** 1 EUR/mj + 1.5% donacijska provizija + burza štenadi 5 EUR/oglas
3. **Verified badge:** 3 razine (UNVERIFIED → DOCS_SENT → VERIFIED), nikad automatski
4. **Chip scanner:** Web Bluetooth + BT RFID čitač emulira tipkovnicu, ne trebamo poseban SDK
5. **ChatJimmy:** odbačen — Llama 3.1 8B 3-bit kvantiziran, ispod Haiku kvalitete
6. **Scope creep zaštita:** CC Code ne dira kucni_ljubimci do mog signal post-15.4.

### Dokumentacija koja je nastala:
- CC_TASK_KUCNI_LJUBIMCI_MASTER.md — 737 linija, svi modeli, tri faze
- KnowledgeArticle: 78 aktivnih (19 novih: compliance + POS + invoicing + general)
- Compliance audit: 2 korekcije (PDV kava 25%, JOPPD min 2000 EUR)
- e-Račun: potvrđen datum 1.1.2026 iz porezna.gov.hr (NN 89/25)

### HITNO — sljedeća akcija (blokira 15.4.):
**CC_TASK_DRON1_SYNESIS_VETO.md** — invoice mapping (0.9% → 70%+)
Rok: 07.04.2026.


---

## ★ GEMINI STRATOSFERA DRONI — Odluke (02.04.2026.)

### Dron #1 Multi-tenant: 12 modela BEZ CompanyManager (produkcija)
KRITIČNI (2):
- pos/hashchain.py:ChainLink → CC Code dodaje CompanyManager ODMAH
- gov_export/models.py → CC Code dodaje CompanyManager ODMAH

NISKI RIZIK (ne mijenjati sada):
- einvoice/models/* — komentari potvrđuju tenant-aware, ručni filter u viewovima
- limit_connect_ai/* — interni AI modeli, korisnik ne vidi

### Dron #2 Javna nabava: IVAN akcija
- /pricing/?profile=jls — novi profil, godišnji paket ispod 2.388 EUR
- Ime: "Godišnja usluga digitalnog upravljanja evidencijama"
- Marija zna pravi prag za OBŽ — konzultirati

### Dron #3 Monolith: POS deploy pravilo (zabetonarano)
- POS commitovi: SAMO utorak-srijeda
- Nikad solo push na POS/invoicing/einvoice bez review
- Feature flags: post-launch sprint

---

## ★ SESIJA 02.04.2026. (večer) — CC Code Sprint + Sonnet commit

### Git HEAD: 7c3c1bb7
### Zadnje azuriranje: 2026-04-02 — Sonnet

### DEPLOYAN DANAS (kompletna sesija):

| Što | Commit | Status |
|-----|--------|--------|
| Azil Sprint 1-2 (modeli + FenixScan) | (uncommitted → 7c3c1bb7) | ✅ DONE |
| Azil Sprint 3 (7 templates) | 7c3c1bb7 | ✅ DONE |
| Azil Sprint 4 (Celery PDF, WeasyPrint) | 7c3c1bb7 | ✅ DONE |
| seed_azil_compliance (11 stavki) | 7c3c1bb7 | ✅ DONE |
| ChainLink → CompanyManager | 7c3c1bb7 | ✅ DONE |
| GovExport → CompanyManager | 7c3c1bb7 | ✅ DONE |
| Force2FAMiddleware superuser bypass | 4bb205fe | ✅ DONE |
| RAG seed_knowledge_base (19 članaka) | 7cfce31a | ✅ DONE |
| CC_TASK_CELERY_QUEUE_SPLIT | b382005c | ✅ TASK PISAN |

### Stanje servera kraj dana:
- gunicorn-fina: active
- celery-worker: active
- celery-beat: active
- pgbouncer: active
- DB: 888MB | Disk: 36% | RAM: ~44%

### Azil modul — LIVE na serveru:
```
/udruge/azil/                    → dashboard
/udruge/azil/zivotinja/nova/     → FenixScan + GPS
/udruge/azil/zivotinja/<pk>/     → detalj + kartoni
/udruge/azil/terenska/           → mobitel-first
/udruge/azil/intervencija/nova/  → teren
/udruge/azil/izvjestaj/          → PDF za JLS
/api/azil/chip-lookup/           → chip provjera
```

### Preostalo za go-live 15.04.:
| Zadatak | Rok | Status |
|---------|-----|--------|
| CC_TASK_DRON1_SYNESIS_VETO | 07.04. | 🔴 CC Code |
| CC_TASK_DRON2_ONBOARDING_WIZARD | 10.04. | 🔴 CC Code |
| CC_TASK_CELERY_QUEUE_SPLIT | 05.04. | 🔴 CC Code |
| Pricing JLS profil (Ivan+Marija) | 10.04. | 🟡 Ivan |
| Load test CCX33 | 12.04. | ⏳ |
| MARIJA_BLAGOSLOV | 08.04. | ⏳ |
| DNS cutover priprema | 14.04. | ⏳ |
| **GO/NO-GO odluka** | 15.04. | Ivan+Marija |

