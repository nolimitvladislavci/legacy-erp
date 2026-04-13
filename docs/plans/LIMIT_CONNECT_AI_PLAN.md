# LIMIT Connect AI — Master Plan
# Kreirao: Sonnet (koordinator) — 2026-03-21
# Cilj: Potpuna AI automatizacija svih poslovnih procesa za sve korisnike sustava
# Status: ODOBREN — Ivan Brtan

---

## VIZIJA

Svaki klijent sustava dobiva osobnog AI poslovnog asistenta koji:
- Autonomno prati i aplicira na EU fondove
- Provjerava zakonsku usklađenost i upozorava na promjene
- Planira i izvršava marketinške kampanje
- Šalje jutarnji/tjedni izvještaj na WhatsApp + email
- Komunicira s klijentom u prirodnom jeziku o poslovnim prilikama

Trojstvo (Sonnet + CC Code + Gemini) radi 24/7 u pozadini.
Klijent dobiva rezultate — ne procese.

---

## ARHITEKTURA

### Novi app: `limit_connect_ai`
Centralni mozak — koordinira sve AI aktivnosti po klijentu.
Zamjenjuje raspršenu logiku iz superadmin_ai + ai_assistant + intelligence.

### Modeli (novi)
```
AIAgentMission       — što agent radi za kompaniju (misija s ciljem, prioritetom, frekvencijom)
AIScheduledTask      — Celery beat integracija s AI kontekstom
AIConversationChannel — gdje korisnik prima poruke (whatsapp/email/chat)
AIReportLog          — history svih poslatih izvještaja
FundApplicationDraft — draft EU aplikacija za review
ComplianceWatchItem  — praćenje zakonskih promjena s rokom
CampaignPlan         — AI-generirani plan kampanje
```

### Integracije (postojeće, proširiti)
- `core/whatsapp.py` — send_text, send_document, send_image
- `intelligence/` — FundOpportunity, IntelligenceResult
- `udruge/` — Kampanja model
- `superadmin_ai/` — Agent Gateway, permission sustav
- `ai_assistant/` — 26 AI alata, tool_handlers

---

## FAZE RAZVOJA

---

### FAZA 1 — Temelj (CC Code)
**Rok: ~1 tjedan**
**Odgovorni agent: CC Code**
**Task fajl: CC_TASK_LIMIT_AI_FOUNDATION.md**

#### 1.1 Novi Django app `limit_connect_ai`
- `apps.py`, `models.py`, `views.py`, `urls.py`, `admin.py`
- Registrirati u settings.py + migrate

#### 1.2 Modeli
```python
AIAgentMission:
  - company (FK)
  - mission_type: CHOICES (daily_report, fund_watch, compliance_watch, campaign_planner, stock_alert, custom)
  - title, description
  - is_active (bool)
  - frequency: CHOICES (hourly, daily, weekly, monthly, on_trigger)
  - next_run (datetime)
  - last_run (datetime)
  - config (JSONField) — parametri misije
  - notify_channel: CHOICES (whatsapp, email, both, chat)
  - notify_target (phone/email string)
  - created_by (FK User)

AIReportLog:
  - company (FK)
  - mission (FK AIAgentMission)
  - report_type (str)
  - content (TextField) — tekst izvještaja
  - sent_via (whatsapp/email/both)
  - sent_at (datetime)
  - status (sent/failed/pending)
  - ai_tokens_used (int)

FundApplicationDraft:
  - company (FK)
  - fund_opportunity (FK FundOpportunity iz intelligence app)
  - status: CHOICES (draft, review_pending, approved, submitted, rejected)
  - eligibility_score (0-100)
  - eligibility_notes (TextField)
  - draft_content (JSONField) — predpopulirana polja
  - created_at, updated_at
  - reviewed_by (FK User, null)
  - submitted_at (datetime, null)

ComplianceWatchItem:
  - company (FK)
  - law_reference (str) — npr. "Zakon o fiskalizaciji čl. 12"
  - description (TextField)
  - status: CHOICES (compliant, action_needed, in_progress, waived)
  - deadline (date, null)
  - assigned_to (FK User, null)
  - ai_notes (TextField)
  - last_checked (datetime)

CampaignPlan:
  - company (FK)
  - title (str)
  - campaign_type: CHOICES (promo, newsletter, seasonal, event, loyalty, eu_fund)
  - target_audience (str)
  - message_template (TextField)
  - channel: CHOICES (whatsapp, email, both)
  - planned_date (datetime)
  - status: CHOICES (draft, approved, sent, cancelled)
  - ai_suggestion (bool) — je li AI predložio
  - estimated_reach (int)
  - actual_reach (int, default 0)
  - created_by (FK User)
```

#### 1.3 Jutarnji report Celery task
```python
# limit_connect_ai/tasks.py
@shared_task
def morning_report_all():
    """07:30 svaki dan — šalje jutarnji sažetak svim klijentima."""
    for mission in AIAgentMission.objects.filter(
        is_active=True, mission_type='daily_report',
        next_run__lte=timezone.now()
    ):
        send_morning_report.delay(mission.id)

@shared_task
def send_morning_report(mission_id):
    """Per-klijent jutarnji report — AI generira, šalje WhatsApp/email."""
    # 1. Dohvati podatke iz AI alata (POS promet, zalihe, neplaćeni, compliance)
    # 2. Pozovi Claude Haiku za sažetak
    # 3. Pošalji WhatsApp + email
    # 4. Logiraj u AIReportLog
```

#### 1.4 Celery Beat registracija
- Dodati u settings.py CELERY_BEAT_SCHEDULE
- morning_report_all: 07:30 svaki dan
- fund_check_all: 09:00 svaki dan
- compliance_check_all: ponedjeljak 08:00
- campaign_suggestions_all: petak 10:00

#### 1.5 Basic views + templates
- `/ai/missions/` — lista aktivnih misija za klijenta
- `/ai/reports/` — history poslatih izvještaja
- `/ai/funds/` — EU aplikacije
- `/ai/compliance/` — pravni status

---

### FAZA 2 — EU Fondovi + Compliance (Gemini + CC)
**Rok: ~2 tjedna**
**Odgovorni: CC Code (modeli/logic) + Gemini (AI evaluation)**
**Task fajlovi: CC_TASK_LIMIT_AI_FUNDS.md + GEMINI_TASK_LIMIT_AI_COMPLIANCE.md**

#### 2.1 EU Fondovi — full workflow
```
[Intelligence pronađe fond] 
    → AIEligibilityCheck (Gemini evaluira tvrtku vs. uvjete natječaja)
    → FundApplicationDraft (AI predpopulira iz Company podataka)
    → [Korisnik review + odobrenje]
    → [AI šalje / upute za slanje]
    → Status tracking
```

**AIEligibilityCheck logika:**
- Čita: Company (djelatnost, veličina, OIB, godina osnivanja)
- Čita: FundOpportunity (eligibility_criteria, max_amount, deadline)
- Daje: score 0-100, notes "Ispunjavate uvjete jer X, ali ne Y"
- Automatski kreira Draft ako score >= 60

**FundApplicationDraft predpopuliranje:**
- Naziv tvrtke, OIB, adresa → iz Company modela
- Financijski podaci → iz konto/invoicing
- Opis projekta → AI generira draft na temelju djelatnosti
- Dokumenti → popis što treba priložiti

#### 2.2 Compliance Watchdog
```
[Gemini patrolira zakonske izvore noću]
    → Detektira promjenu zakona relevantnu za klijenta
    → Kreira ComplianceWatchItem s rokom
    → WhatsApp upozorenje klijentu
    → CC Code kreira task za implementaciju (ako je tehnički)
    → Sonnet koordinira review
```

**Praćeni zakoni po klijentu:**
- HR klijenti: Zakon o fiskalizaciji, PDV, eRačun, ZOR, Zakon o radu
- DE klijenti: KassenSichV, GoBD, UStG, DATEV promjene
- Udruge: Zakon o udrugama, NPF pravilnik, EU fond pravila
- OPG/livestock: Veterinarski zakon, HAPIH pravilnik, EU Reg 2019/6

#### 2.3 Legal Sources monitoring
- Gemini nightly patrol proširiti za: NN.hr, EUR-Lex, FINA obavijesti, ePorezi
- Cache rezultata 24h
- Diff detection — javi samo novo

---

### FAZA 3 — Kampanje + Per-klijent cockpit (Gemini)
**Rok: ~1 tjedan**
**Odgovorni: Gemini (AI logika) + CC Code (frontend)**
**Task fajlovi: GEMINI_TASK_LIMIT_AI_CAMPAIGNS.md + CC_TASK_LIMIT_AI_COCKPIT.md**

#### 3.1 CampaignPlanner AI
```
[Svaki petak 10:00 — AI analizira klijenta]
    → Provjeri: promet zadnji tjedan, sezone, neiskorištene kontakte
    → Generiraj 2-3 prijedloga kampanje s tekstom poruke
    → Pošalji Ivanu/klijentu na odobrenje (WhatsApp)
    → Nakon odobrenja: automatski zakazano slanje
```

**Primjeri AI sugestija:**
- Seki: "Petak je, imaš 847 kontakata. Predlažem: 'Vikend ponuda — burek 2+1 do nedjelje 🥐' — šaljem?"
- Marija: "Rok za predaju PDV-a je za 5 dana. Šaljem podsjetnik svim klijentima?"
- Nikša: "Detektirao sam 3 nova B2B leada iz Stuttgarta. Kreiram ponudu?"

#### 3.2 Per-klijent AI cockpit (nije superadmin panel)
Template: `/ai/cockpit/` ili integrirano u base.html sidebar

Sadržaj (generirano AI jutros):
```
📊 Promet danas: 1.247 EUR (+12% vs utorak)
📦 Zalihe: 3 artikla ispod minimuma
💰 Neplaćeni: 4 računa (12.840 EUR)
⚖️ Compliance: SVE OK
🏛️ EU fondovi: 2 nova natječaja — eligibilitet 78%
📅 Sljedeće: Predaja PDV-a za 5 dana
```

WhatsApp verzija: isti sadržaj, emoji-friendly, kraće

#### 3.3 Tim Chat proširenje
- Korisnik može pitati AI direktno iz tim chata
- AI odgovara u ime trojstva
- "Seki: koliko sam zaradio ovaj tjedan?" → AI dohvaća podatke → odgovara

---

### FAZA 4 — Autonomija (dugoročno)
**Rok: ~1 mjesec**
**Svi agenti**

#### 4.1 Self-improving misije
- AI prati koji izvještaji se čitaju, na što korisnik reagira
- Automatski prilagođava frekvenciju i sadržaj

#### 4.2 Proaktivni business advisor
- AI detektira prilike: "Tvoj konkurent je zatvorio — ima slobodnih 200 klijenata u tvom gradu"
- Predlaže akcije s konkretnim koracima

#### 4.3 Multi-agent orchestration
- Sonnet prima zahtjev korisnika → razlaže na subtaskove → delegira CC/Gemini
- Results se agregiraju → Sonnet formira finalni odgovor
- Sve logira u AIActionLog za audit

---

## KOMUNIKACIJA S KORISNICIMA

### Format WhatsApp jutarnjeg reporta
```
🌅 *Dobro jutro, [Ime]!*
Ovo je tvoj AI sažetak za [datum]:

📊 *Promet:* X EUR (jučer Y EUR)
📦 *Zalihe:* [OK / 3 artikla ispod min]
💰 *Otvoreni računi:* X (Y EUR)
⚖️ *Compliance:* [SVE OK / Upozorenje: ...]
🏛️ *Fondovi:* [Ništa novo / 2 nova natječaja!]

Tvoj AI asistent — LIMIT Connect
```

### Format tjednog summaryja (ponedjeljak 08:00)
- Prethodni tjedan vs. plan
- 3 prilike za ovu sedmicu
- Rokovi koji se bliže

### Format compliance upozorenja (instant)
```
⚠️ *Zakonska promjena*
[Naziv zakona / pravilnika]
Relevantno za: [tvoja djelatnost]
Rok za usklađivanje: [datum]
Što treba napraviti: [konkretni koraci]
```

---

## PRAVILA ZA AGENTE (sva trojica čitaju)

1. **Sonnet** koordinira, ne izvršava — piše taskove, čita STATUS, komunicira s Ivanom
2. **CC Code** izvršava kod — ne planira arhitekturu samostalno, pita Sonnet
3. **Gemini** autonomno istražuje — piše nalaze u GEMINI_TASK_*.md, čeka Sonnet review
4. Svaka AI akcija prema klijentu ide kroz `agent_gateway` i logira se
5. Kampanje i fondovi UVIJEK idu na odobrenje klijenta prije slanja
6. Compliance upozorenja — instant, bez čekanja odobrenja
7. Jutarnji report — automatski, bez odobrenja

---

## REDOSLJED IMPLEMENTACIJE

```
TJEDAN 1:
[CC Code] limit_connect_ai app + modeli + migracije
[CC Code] Celery beat schedule + morning_report task
[CC Code] Basic views + templates (cockpit, missions, reports)
[Sonnet]  Review + test na Konjik d.o.o. klijentu

TJEDAN 2:
[CC Code] FundApplicationDraft workflow
[Gemini]  AIEligibilityCheck logika
[CC Code] Frontend za EU fondove
[Sonnet]  Review + demo Mariji Brtan

TJEDAN 3:
[Gemini]  ComplianceWatchdog + zakonski izvori
[CC Code] ComplianceWatchItem views + notifikacije
[Sonnet]  Review + test na Nikša/DE compliance

TJEDAN 4:
[Gemini]  CampaignPlanner AI logika
[CC Code] CampaignPlan CRUD + approval flow
[CC Code] Per-klijent cockpit dashboard
[Sonnet]  End-to-end test sva 3 klijenta → demo Ivanu
```

---

## TASK FAJLOVI (kreirati sljedeće)

1. `CC_TASK_LIMIT_AI_FOUNDATION.md` — Faza 1, CC Code
2. `GEMINI_TASK_LIMIT_AI_COMPLIANCE.md` — Faza 2, Gemini
3. `CC_TASK_LIMIT_AI_FUNDS.md` — Faza 2, CC Code
4. `GEMINI_TASK_LIMIT_AI_CAMPAIGNS.md` — Faza 3, Gemini
5. `CC_TASK_LIMIT_AI_COCKPIT.md` — Faza 3, CC Code

---

## USPJEH IZGLEDA OVAKO

- Seki prima WhatsApp u 07:30 s prometom i stanjem blagajne
- Marija automatski dobiva upozorenje 5 dana prije PDV roka
- Nikša automatski vidi nove B2B leade iz Njemačke s AI-generiranom porukom
- EU fond aplikacija ide od "pronašli smo natječaj" do "draft spreman za review" bez ičijeg ručnog rada
- Novi zakon → ComplianceWatchItem → CC_TASK za implementaciju — sve automatski

---
Zadnje ažuriranje: 2026-03-21 — Sonnet — Master plan kreiran i odobren
