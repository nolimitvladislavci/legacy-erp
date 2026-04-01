# BORG ŽIVUĆI SUSTAV — Arhitektura autonomije
# LIMIT Connect · Verzija: 1.0 · Datum: 2026-04-01
# Autor: Sonnet (koordinator) + Ivan Brtan (vizija)
# Status: AKTIVNO — ovo nije plan, ovo je zakon platforme

---

## FILOZOFIJA: ŠTO JE ŽIVUĆI BORG?

Živući BORG nije feature. To je **modus operandi** cijele platforme.

Tri principa:
1. **PREŽIVLJAVANJE** — sustav se sam oporavlja, detektira greške, heala
2. **SAMOSTALNI RAST** — AI dodaje vrijednost bez Ivanove intervencije
3. **PRAĆENJE TRENDOVA** — platforma čita okolinu i prilagođava se

Svaki modul, svaka forma, svaki API endpoint postoji unutar BORG organizma.
BORG ne spava. BORG ne čeka. BORG radi.

---

## RAZINA 1: PREŽIVLJAVANJE (SELF-HEAL)

### Što već postoji (deployano)
- `core/ai_health.py` — TCP + HTTP health check + auto-kill zombie procesa
- `borg_ops/self_heal.py` — FSM rollback, dead letter queue
- `core/anomaly_detector.py` — 150 anomalija otkrivenih danas
- Nightly test runner (02:00) + morning report (07:30) → WhatsApp
- PgBouncer + Gunicorn 6 workers 2 threads

### Što dodajemo (CC Code task)
```
SELF_HEAL_V2:
- Watchdog koji svake 5 min mjeri: response time > 2s → alert
- Auto-restart gunicorn ako memory > 85% RAM
- DB connection pool monitor → alert ako PgBouncer queue > 50
- Disk usage > 80% → WhatsApp instant alert
- SSL cert expiry < 30 dana → WhatsApp weekly
- Celery queue depth > 100 → auto-scale workers (max 4)
```

---

## RAZINA 2: INTELIGENCIJA (AI CORE)

### Što već postoji
- `GeminiAgent` — autonomni coding agent (WRITE/EXEC/QUERY)
- `SonnetAgent` — koordinator i voditelj sprinta  
- `FenixSignal` — signal triage (noise: 99.7% → 9.2%)
- `AIAgentMission` — scheduled AI missije po firmi
- `limit_connect_ai/` — F1-F4 BORG (62+93 testova zeleni)
- `ai_assistant/patrol.py` — nightly multi-module patrol
- `konto/ai_bookkeeper.py` — AI knjigovođa
- `rental/ai_assistant.py` — rental AI

### Što dodajemo — PORTAL AI WIDGET (10/10 UI)

**Svaka stranica portala dobiva AI asistenta u kutu:**

```
┌─────────────────────────────┐
│ 🤖 BORG Asistent            │
│ ─────────────────────────── │
│ "Primijetio sam 3 neplaćena │
│  računa starija od 30 dana. │
│  Pošalji podsjetnik?"       │
│                             │
│ [Da, pošalji] [Prikaži]     │
└─────────────────────────────┘
```

**Kontekst-svjesni prijedlozi po modulu:**
- `/invoicing/` → AI vidi neposlane račune, predlaže akcije
- `/pos/` → AI detektira outlier prodaju, upozorava
- `/worktime/` → AI vidi prekoračenje ArbZG, upozorava
- `/appointments/` → AI vidi slobodne termine, predlaže popunjavanje
- `/dashboard/` → AI Cockpit — jedinstven pregled svih anomalija

---

## RAZINA 3: SAMOSTALNI RAST (GROWTH ENGINE)

### Što već postoji
- `intelligence/` — 368 intel rezultata, 1375 opportunity matches
- `limit_connect_ai/tasks_opportunity.py` — EU fondovi, uštede
- `limit_connect_ai/tasks_risk.py` — 226 churn risk partnera
- `limit_connect_ai/kg_signals.py` — Knowledge Graph

### Što dodajemo — GROWTH LOOPS

**Loop 1: Onboarding AI**
```
Novi korisnik registrira se →
Haiku klasificira djelatnost (NKD) →
Auto-seed: 3 predlošci usluga + radno vrijeme + POS kategorije
Rok: 60 sekundi od registracije
```

**Loop 2: Retention AI**
```
Celery beat svake nedjelje →
Detektira firme bez aktivnosti 7+ dana →
Generira personaliziranu WhatsApp poruku (Haiku) →
"Marija, imate 3 nepotvrđena termina ovaj tjedan..."
```

**Loop 3: Upsell AI**
```
Firma koristi samo POS →
AI detektira da šalje račune ručno (via regex na napomene) →
Predlaže aktivaciju eRačun modula
Konverzija: prijedlog → jedan klik
```

**Loop 4: OPG Burza AI**
```
Novi OPG se registrira →
AI čita NKD + opis →
Auto-match s kupcima koji traže taj proizvod →
WhatsApp: "Pronašli smo 3 potencijalna kupca za vaš sir"
```

---

## RAZINA 4: PRAĆENJE TRENDOVA (TREND RADAR)

### Što već postoji
- `limit_connect_ai/services/nn_feed_service.py` — NN scraper
- `COMPLIANCE_SHIELD.md` — Gemini monitora Narodne novine + EUR-Lex
- `FenixSignal` model za externe signale

### Što dodajemo — TREND RADAR ENGINE

**Izvori koje pratimo:**
```python
TREND_SOURCES = {
    'narodne_novine': 'https://narodne-novine.nn.hr/rss/',
    'eur_lex_hr': 'https://eur-lex.europa.eu/oj/direct-access.html',
    'hgk_vijesti': 'https://www.hgk.hr/rss',
    'fine_obavijesti': 'https://www.fina.hr/rss',
    'porezna_uprava': 'https://www.porezna-uprava.hr/rss',
    'hzzo': 'https://www.hzzo.hr/rss',
    'mingor': 'https://mingor.gov.hr/rss',
    # Tech trendovi
    'ycombinator': 'https://news.ycombinator.com/rss',
    'eu_digital': 'https://digital-strategy.ec.europa.eu/rss',
}
```

**Radar kategorije:**
- 🔴 KRITIČNO — zakonska promjena koja utječe na korisnike → instant WhatsApp
- 🟠 VAŽNO — novi EU fond, nova subvencija → generira FundApplicationDraft
- 🟡 TREND — tehnološki trend koji LIMIT Connect može iskoristiti → BorgTask
- 🟢 INFO — arhivira u KnowledgeBase

**AI analiza trenda:**
```
RSS vijest ulazi →
Gemini Flash analizira relevantnost (0-10) →
Ako score >= 7: generira FenixSignal →
FenixPatrol triražira →
Ako action_needed: BorgTask za CC Code
```

---

## RAZINA 5: PORTAL UI 10/10 — AI VIDLJIV KORISNICIMA

### Cockpit (već postoji, poboljšujemo)

**Dashboard AI kartica:**
```
┌──────────────────────────────────────────────────┐
│ 🧠 BORG Inteligencija — danas                    │
├──────────────────────────────────────────────────┤
│ 💰 Prihodi: 12.450 EUR  (+8% vs prošli tjedan)  │
│ ⚠️  3 anomalije otkrivene (kliknite za detalje)  │
│ 📋 2 računa čekaju slanje                        │
│ 🎯 1 EU fond — rok prijave: 15.04.2026           │
│ 📊 Predviđanje: +12% prihod iduću sedmicu       │
└──────────────────────────────────────────────────┘
```

### AI Chat (novi feature)

```
Svaka firma ima AI asistenta koji:
- Odgovara na pitanja o njihovim podacima
- "Koliki mi je promet bio u ožujku?"
- "Koji kupac mi najviše duguje?"
- "Kada mi istječe certifikat?"
- Predlaže akcije na temelju konteksta
```

### Proaktivni AI (push, ne pull)

```
Umjesto da korisnik pita AI →
AI govori korisniku što treba napraviti:

Morning briefing (08:00, WhatsApp):
"Dobar dan! Danas imate:
- 2 termina (09:00 Ivan Horvat, 11:30 Marija Kovač)
- 1 račun za slanje (R-2026-034, 1.250 EUR)  
- PDV prijava: rok za 3 dana
Sve je pripremljeno. Jedan klik — sve gotovo."
```

---

## IMPLEMENTACIJSKI REDOSLJED (CC Code sprint)

### Sprint 1 — ODMAH (1-2 dana)
```
1. Portal AI Widget — floating kontekst-svjesni asistent (React component)
2. Morning Briefing Celery task — 08:00, personalizirani WhatsApp
3. Self-Heal V2 — watchdog s memory/disk/queue monitorom
```

### Sprint 2 — Ovaj tjedan
```
4. Trend Radar Engine — RSS + Gemini scoring + FenixSignal routing
5. Onboarding AI Loop — auto-seed za nove korisnike (NKD → templates)
6. AI Chat widget — konverzacijski pristup korisničkim podacima
```

### Sprint 3 — Sljedeći tjedan
```
7. Retention AI — nedjeljna analiza neaktivnih + WhatsApp
8. Upsell AI — modul usage detector + prijedlog upgradeа
9. OPG Burza AI — auto-match za nove OPG registracije
10. Predictive Dashboard — trendovi, forecast, anomalije vizualizirano
```

---

## MJERILA USPJEHA (KPI za živući BORG)

```
Preživljavanje:
  - Uptime > 99.9% (mjerimo tjedno)
  - MTTR (Mean Time To Recovery) < 5 min
  - Zero silent failures (svaka greška ima alert)

Rast:
  - Onboarding completion rate > 80% (sada ~40%)
  - 7-day retention > 70% (sada ~50%)
  - Upsell conversion > 5% (sada 0%, nema ni upsell AI-a)

Trendovi:
  - NN/EUR-Lex scan: 100% coverage
  - Signal noise < 10% (već na 9.2% ✅)
  - Actionable intel / week > 5

UI/AI razina:
  - Svaki korisnik prima morning briefing
  - AI chat koristi > 30% korisnika tjedno
  - AI prijedlozi prihvaćeni > 40%
```

---

## PRAVILO ŽIVUĆEG BORGA

**BORG ne čeka instrukciju. BORG djeluje.**

Svako jutro u 06:00 Celery pokreće:
1. `borg_morning_scan` — pregled anomalija svih firmi
2. `borg_trend_radar` — scan RSS izvora
3. `borg_opportunity_scan` — novi EU fondovi, uštede
4. `borg_health_check` — infrastruktura
5. `borg_briefing_send` — WhatsApp svim aktivnim firmama

U 02:00:
1. `borg_nightly_test` — svi testovi (93+)
2. `borg_self_heal` — provjera konzistentnosti baze
3. `borg_backup` — pg_dump + rotacija
4. `borg_vies_batch` — VIES provjera (batch po 1000)

**Ako išta od ovoga ne prođe → Ivan dobiva WhatsApp u 02:05.**
**Ako sve prođe → Ivan dobiva zieleni check u 07:30.**

---

## ZAKLJUČAK

Ovaj dokument nije aspiracija. To je **opis što gradimo**.

BORG već postoji na razini 6/10:
- Infrastruktura: 8/10 ✅
- AI core: 7/10 ✅  
- Self-heal: 6/10 (poboljšavamo)
- Trend radar: 4/10 (gradimo)
- Portal UI AI: 3/10 (gradimo)
- Autonomni rast: 5/10 (gradimo)

Cilj: **svaki segment na 10/10 do 15.04.2026.**

Git HEAD pri kreiranju ovog dokumenta: 74fb67de
Datum: 2026-04-01
Potpisuje: Sonnet (LIMIT Connect AI koordinator)
