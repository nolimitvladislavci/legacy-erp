# BORG FENIX — PUT DO 10/10
# Datum: 2026-04-01 | Autor: CC Code Opus
# Bazna ocjena: 5.9/10 (112 testova, 29 run, 17 pass, 12 fail/error)

---

## TRENUTNO STANJE (Audit 2026-04-01)

| Kategorija | Ocjena | Ključni problem |
|------------|--------|-----------------|
| Knowledge Graph | 6/10 | Prazan graf, 0 čvorova |
| Opportunity Scanner | 7/10 | 932 matcha, svi 'identified', 0 notified |
| Adaptation Engine | 4/10 | 1 pravilo, 0 izvršenih |
| AI Assistant + Patrol | 7/10 | 1444 patrola, ali 5 konverzacija |
| Intelligence Sources | 5/10 | 6 izvora, 0 rezultata |
| BORG Ops Workflow | 5/10 | 3 kartice, nekorišteno |
| Fenix Signals | 6/10 | 578 signala, 99.7% isti bug |
| Security | 8/10 | exec() u MCP, nema rate limit |
| Testovi | 5/10 | 29 run, 17 pass (59%) |
| Produkcija | 6/10 | Većina modula prazna |
| **PROSJEK** | **5.9/10** | |

---

## FAZA 1 — TEMELJI (Cilj: 7.0/10)
**Trajanje: 1 sesija | Prioritet: KRITIČNO**

### F1.1 — Popraviti 12 failanih testova
- [ ] test_empty_message_rejected → 302 umjesto 400 (auth redirect)
- [ ] test_usage_log_created → AIUsageLog ne nastaje
- [ ] 8 errora — identificirati i popraviti import/setup
- [ ] Cilj: **29/29 PASS**

**Detalj grešaka (2026-04-01):**
- 8 ERRORS: setUpClass u BORGTestBase — svi limit_connect_ai testovi (33 testa blokirano)
- 4 FAILS: ChatAPITest (chat_returns_response, conversation_persisted, empty_message_rejected, usage_log_created)
- 17 OK: intelligence testovi (17/17 PASS) + ai_assistant model testovi
- Prioritet: Fix BORGTestBase.setUpTestData prvo (deblokiraj 33 testa), onda ChatAPI 4 faila
- Fajlovi: ai_assistant/tests.py, limit_connect_ai/tests.py, intelligence/tests.py

### F1.2 — MCP Security hardening
- [ ] Zamijeniti exec() u django_orm tool → safe eval s whitelistom
- [ ] Dodati rate limiting na MCP toolove (max 30 req/min)
- [ ] Sanitizacija SQL inputa u query_db
- [ ] Blocked commands: dodati DROP, DELETE, TRUNCATE, ALTER
- Fajlovi: mcp_server.py

### F1.3 — Fenix Signal dedup + triage
- [ ] Deduplikacija: grupirati iste 404-ke (vapid-public-key × 500+)
- [ ] Auto-resolve poznate 404-ke
- [ ] Signal → Ticket pipeline (novi signali kreiraju ticket)
- Fajlovi: limit_connect_ai/signal_triage.py, models_signal.py

---

## FAZA 2 — AKTIVACIJA (Cilj: 8.0/10)
**Trajanje: 1-2 sesije | Prioritet: VISOK**

### F2.1 — Knowledge Graph seed pipeline
- [ ] Auto-seed iz kontnog plana (KontoAccount → KnowledgeNode type=account)
- [ ] Auto-seed iz partnera (Partner → KnowledgeNode type=partner)
- [ ] Auto-seed iz faktura (Invoice → KnowledgeEdge type=transaction)
- [ ] Firma → NKD → Djelatnost graf
- [ ] Management command: python manage.py kg_seed --company=all
- [ ] Celery periodic task: weekly kg refresh
- Fajlovi: models_knowledge_graph.py, novi services/kg_seeder.py 

### F2.2 — Opportunity lifecycle activation
- [ ] Batch: 932 identified → notified (za firme s emailom)
- [ ] Email template: "Pronašli smo N prilika za uštedu od X EUR"
- [ ] WhatsApp template za Mariju/admina
- [ ] Status workflow: identified → notified → applied → completed → savings_realized
- [ ] Dashboard widget: Top 5 neiskorištenih prilika po firmi
- Fajlovi: models_knowledge_graph.py, novi services/kg_seeder.py 

### F2.3 — NN → Adaptation auto-pipeline
- [ ] NN Scraper → RegulatoryUpdate (već radi)
- [ ] RegulatoryUpdate.post_save signal → auto-generate AdaptationRule kandidat
- [ ] Admin review queue: /admin/adaptation-rules/ → approve/reject
- [ ] Approved rule → auto-apply (tax_rate, config)
- [ ] Notification: "Novi zakon NN 42/2026 — automatski prilagođeno"
- Fajlovi: , signal u 

---

## FAZA 3 — INTELIGENCIJA (Cilj: 9.0/10)
**Trajanje: 2-3 sesije | Prioritet: SREDNJI**

### F3.1 — Intelligence pipeline konsolidacija
- [ ] Spojiti NN feed + Intelligence izvore u jedinstven scheduler
- [ ] Svaki izvor: scrape → LLM analiza → IntelligenceResult → FundOpportunity
- [ ] APPRRR, eKohezija, HAPIH → realni fund scraping
- [ ] Alert za relevantne fondove: WhatsApp + email + dashboard
- [ ] Cilj: >50 IntelligenceResult-a, >10 FundOpportunity-ja
- Fajlovi: , 

### F3.2 — AI Assistant aktivacija
- [ ] Onboarding flow: automatski predloži chat kad korisnik prvi put uđe
- [ ] Quick actions: "Provjeri PDV", "Stanje računa", "Neplaćene fakture"
- [ ] Context-aware: chat zna za firmu, partnere, fakture korisnika
- [ ] Knowledge Article auto-generation iz patrol reporta
- [ ] Cilj: >50 konverzacija/mjesec
- Fajlovi: , 

### F3.3 — BORG Ops → Work Order integration
- [ ] CardActivity: povezati s work_orders, pos, invoicing
- [ ] Dispatch engine: automatski assignaj task najbližem radniku
- [ ] Business hours: automatski racunaj SLA breach
- [ ] Real-time status board: /borg/ops/board/
- Fajlovi: , 

### F3.4 — Cross-company anomaly alerts
- [ ] Automatski detektiraj: isti OIB, različit buyer_type → alert
- [ ] Automatski detektiraj: isti OIB, ukupni dug >10K EUR → alert
- [ ] Weekly digest email za umbrella admina
- Fajlovi: 

---

## FAZA 4 — PERFEKCIJA (Cilj: 10/10)
**Trajanje: 2-3 sesije | Prioritet: NIZAK (ali neophodan)**

### F4.1 — Test coverage 100%
- [ ] Svaki modul: ≥90% coverage
- [ ] E2E testovi: Playwright za portal, dashboard, POS
- [ ] Load test: locust za MCP, API, portal
- [ ] Cilj: 150+ testova, 0 failures
- Fajlovi: svi test fajlovi

### F4.2 — Predictive analytics
- [ ] Cash flow prediction (30/60/90 dana) iz invoice historije
- [ ] Churn prediction: koji partner neće platiti
- [ ] Seasonal demand: POS prodaja po mjesecima → forecast
- [ ] Revenue optimization: preporuči cijenu po artiklu
- Fajlovi: novi 

### F4.3 — Self-healing BORG
- [ ] Patrol detektira grešku → automatski kreira fix PR
- [ ] Health check: auto-restart servisa ako pada
- [ ] Auto-scaling: detektiraj load spike → alert
- [ ] Auto-backup verify: provjeri backup integritet
- Fajlovi: models_knowledge_graph.py, novi services/kg_seeder.py 

### F4.4 — Sonnet Agent full autonomy
- [ ] Sprint planning: Sonnet razlaže zadatke → delegira
- [ ] Code review: automatski reviewaj PR-ove
- [ ] Deployment: zero-downtime deploy pipeline
- [ ] Monitoring: real-time error → fix loop
- Fajlovi: 

---

## METRIKE ZA PRAĆENJE

| Metrika | Danas | F1 | F2 | F3 | F4 |
|---------|-------|----|----|----|----|
| Test pass rate | 59% | 100% | 100% | 100% | 100% |
| Test count | 29 | 35+ | 60+ | 100+ | 150+ |
| KG nodes | 0 | 0 | 500+ | 2000+ | 5000+ |
| Opportunity lifecycle | 0% | 0% | 50% | 90% | 100% |
| Adaptation rules | 1 | 1 | 5+ | 20+ | auto |
| Intelligence results | 0 | 0 | 10+ | 50+ | 100+ |
| AI conversations/mj | 5 | 5 | 20+ | 50+ | 100+ |
| Signal resolution | 0% | 20% | 60% | 90% | 99% |
| MCP security | 60% | 95% | 95% | 99% | 99% |
| **UKUPNA OCJENA** | **5.9** | **7.0** | **8.0** | **9.0** | **10.0** |

---

## COMMIT LOG

| Datum | Faza | Opis | Hash |
|-------|------|------|------|
| 2026-04-01 | Audit | Inicijalna analiza, plan kreiran | — |
| | F1.1 | | |
| | F1.2 | | |
| | F1.3 | | |

---

## PRAVILA
1. Svaka faza se committa zasebno
2. Testovi moraju prolaziti PRIJE commita
3. FENIX_STATUS.md se ažurira nakon svake faze
4. Ovaj fajl (BORG_10_PLAN.md) je source of truth za BORG napredak
5. NE PRESKAČI FAZE — svaka gradi na prethodnoj
