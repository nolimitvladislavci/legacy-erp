---
name: Anthropic Advisor Strategy — Trojstvo + Doktor
description: Haiku executor + Opus advisor pattern. 3 integration points. Cost optimization. Beta header advisor-tool-2026-03-01.
type: project
---

# ANTHROPIC ADVISOR STRATEGY — LIMIT Connect

**Datum:** 2026-04-12
**Beta header:** `advisor-tool-2026-03-01`
**Cijena:** Advisor tokeni = Opus cijena, Executor tokeni = Haiku cijena

## ARHITEKTURA

```
Korisnik → Zlatno dugme / Doktor
  → Haiku (executor, jeftino, brzo)
    → Detektira problem
    → Standardan? → Haiku riješava sam
    → Kritičan? → Konzultira Opus (advisor, max N puta)
      → Opus daje duboku analizu
    → Haiku formulira odgovor
```

## 3 TOČKE INTEGRACIJE

### 1. core/anthropic_advisor.py — Shared Utility
```python
haiku_with_advisor(messages, max_tokens=1500, max_uses=1, system=None) -> str
```
- Model: claude-haiku-4-5-20251001 (executor) + claude-opus-4-6 (advisor)
- Beta: `betas=['advisor-tool-2026-03-01']`
- Tool type: `advisor_20260301`
- Logira kada Haiku konzultira Opus

### 2. pos/trojstvo_task.py → _haiku_analiza()
- **max_uses=2** (Trojstvo može konzultirati Opus do 2 puta)
- Aktivira se za: arhitekturalne promjene, sigurnost, FSM, migracije, multi-tenant, fiskalizacija
- System prompt uključuje kontekst: 668+ modela, multi-tenant, FINA certifikati

### 3. limit_connect_ai/tasks_doktor.py → _call_haiku()
- **max_uses=1** (Doktor konzultira Opus max 1 put)
- Aktivira se SAMO za kritične:
  - unfiscalized_count > 0
  - cert_days_left < 30
  - overdue_90_count > 5
  - overall_score < 40
- Standardne dijagnoze (score 40+) → samo Haiku (bez advisor troška)

## COST MODEL

| Scenarij | Executor (Haiku) | Advisor (Opus) | Ukupno |
|----------|-----------------|----------------|--------|
| Standardni bug (Trojstvo) | ~2K tokena | 0 | ~$0.002 |
| Kritični bug (Trojstvo) | ~2K tokena | ~3K tokena | ~$0.05 |
| Doktor standardni | ~1K tokena | 0 | ~$0.001 |
| Doktor kritični | ~1K tokena | ~2K tokena | ~$0.03 |

## PRAVILA

- ai_health.py (infrastruktura) → BEZ advisora (overkill)
- Batch skripte → BEZ advisora (predrago)
- Advisor samo za: zakonski rizik, arhitektura, sigurnost, fiskalizacija
- max_uses strogo ograničen (1-2) da ne eskalira troškove

## FAJLOVI
- `core/anthropic_advisor.py` — utility
- `pos/trojstvo_task.py` — Trojstvo AI (Haiku+Gemini+Sonnet konsenzus)
- `limit_connect_ai/tasks_doktor.py` — Claude Doktor AI
