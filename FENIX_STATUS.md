# FENIX STATUS — Koordinacijski fajl
# Zadnje azuriranje: 2026-04-01 — Sonnet (Korpaš ekosustav)
# Git HEAD: ea0027d6
# PRAVILO: Ako nesto pise DONE — NE RADIS PONOVO.

---

## ★ RATNI RASPORED — 20 DANA DO 15.4.2026

| Dan | Datum | Zadatak | Odgovorni | Status |
|-----|-------|---------|-----------|--------|
| 0 | 25.3. | Race condition, PDV, NKD, alert→toast, BUG-05 | Sonnet | ✅ DONE |
| 1 | 26.3. | Udruge: Branitelji + Lov + Zadruge | CC Code | ✅ DONE |
| 1 | 26.3. | Tax Wizard: 6 obrazaca, 7 deadlines, widget global | Sonnet+CC | ✅ DONE |
| 1 | 26.3. | Worktime /mine/ — mobilna stranica za radnika | CC Code | ✅ DONE |
| 1 | 26.3. | DNS TTL → 60s (Namecheap) | **IVAN** | ✅ DONE |
| 2 | 27.3. | POS Joker unified + tax widget + subscription cockpit | CC Code | ✅ DONE |
| 3 | 28.3. | Unscoped audit finish + GDPR | CC Code | ✅ DONE |
| 4 | 29.3. | Vatrogasci modul (dnevnik intervencija) | CC Code | ✅ DONE (26.3.) |
| 10 | 5.4. | Naruči Hetzner CCX33 (Konjik d.o.o.) — 89EUR/mj | **IVAN** | ⏳ ČEKA |
| 12 | 10.4. | Server priprema + load test | Sonnet+CC | ⏳ ČEKA |
| 15 | 15.4. | **PRODUKCIJA GO-LIVE** — 0-downtime | Sonnet | ⏳ ČEKA |
| 15 | 15.4. | **VRATA OTVORENA** — testni korisnici (Marija odobrava) probni pristup | Ivan | ⏳ ČEKA |

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
