# TASK: Stolarija AI Enhancement — 3 stavke
# Autor: Opus
# Datum: 2026-04-10
# Status: IN PROGRESS

## Stavka 5: Admin registracija (15min)
- [ ] Registriraj ProductionOrder, BOMItem, InstallationOrder, InstallationChecklist, HandoverProtocol
- [ ] manage.py check

## Stavka 3: Predictive Service Score (3h)
- [ ] RiskProfile model ili computed property na WindowWarranty
- [ ] Rule-based risk scoring: materijal + lokacija + starost + okov
- [ ] Location risk factor: primorje/kontinent/planina (iz adrese)
- [ ] Predicted issue categories: brtva, okov, kondenzacija, deformacija
- [ ] Risk dashboard view za firmu
- [ ] Celery task: weekly risk recalculation
- [ ] Template: risk overview + per-warranty detail

## Stavka 4: AI Email/Service Agent — Human-in-loop (4-5h)
- [ ] ServiceMessage model (inbound/outbound, ai_draft, approved, sent)
- [ ] Inbound email handler (Django mailbox ili polling)
- [ ] Gemini/Anthropic integration za draft odgovor
- [ ] Multimodal: image analysis za slike u emailu
- [ ] Sentiment analysis sloj (eskalacija na negativan ton)
- [ ] AI draft dashboard (lista pending drafts, approve/edit/reject)
- [ ] Outbound: slanje odobrenog drafta emailom
- [ ] BookingSignature audit na svaki AI draft + approval
- [ ] Celery task: check inbox + generate drafts
