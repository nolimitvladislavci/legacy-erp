# FENIX STATUS — Koordinacijski fajl
# Zadnje azuriranje: 2026-03-27 — CC Code Opus (POS Joker sesija)
# Git HEAD: 4fc8b0ba
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
| WhatsApp report na +491723006985 | ✅ RADI |
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
