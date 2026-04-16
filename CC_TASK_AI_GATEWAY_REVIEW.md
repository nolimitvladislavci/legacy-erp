# CC TASK: AI Gateway — Code Review + Sigurni Deploy

**Prioritet:** HIGH  
**Agent:** Claude Code (CC)  
**Datum:** 2026-04-16  
**Odobrio:** Sonnet (koordinator)

---

## KONTEKST

DeepSeek je predložio AI Gateway modul koji orkestrira sve AI pozive  
(DeepSeek, Bedrock, budući modeli) kroz centralni Redis session manager.  
**Kod NIJE deployovan.** Postoji samo kao prijedlog u chatu.  
Sonnet je odbio slepi deploy — zahtijeva code review.

---

## ŠTO TREBA NAPRAVITI

### KORAK 1 — Rekonstruiraj predloženi kod
Iz DeepSeekove poruke u chatu, predloženi AI Gateway ima:
- `AIGateway` klasa s Redis session managementom  
- `ConversationSession` dataclass  
- `build_prompt_with_context()` — MAX_HISTORY=50  
- `RateLimiter` klasa (token bucket, po tenantu)  
- `deepseek_chat` vs `deepseek_reasoner` routing  
- FastAPI microservice opcija  
- `has_client_data` flag za GDPR routing (Bedrock vs direct)

Napiši čisti kod u `/var/www/fina-connect/core/ai_gateway.py`  
**BEZ deployja** — samo kreiraj fajl.

### KORAK 2 — Pronađi postojeći DeepSeek kod
```bash
find /var/www/fina-connect -name "*.py" | xargs grep -l "deepseek\|DeepSeek" | grep -v venv | grep -v __pycache__
```
Pročitaj sve relevantne fajlove. Razumij postojeću arhitekturu PRIJE pisanja.

### KORAK 3 — Security audit (5 konkretnih provjera)

**3.1 CORS check**
- Postoji li `allow_origins=["*"]` → zamijeni s `["https://limit-connect.com", "https://memio.pet"]`

**3.2 Rate limiter validacija**
- Provjeri da li `consume()` ima race condition (Redis `get` → `set` nije atomično)  
- Fix: koristi `Redis MULTI/EXEC` ili `pipeline()` s `WATCH`

**3.3 GDPR routing**
- `has_client_data=True` → **mora** ići na AWS Bedrock, **nikad** na direktni DeepSeek API  
- Provjeri da li postoji fallback koji bi zaobišao ovo  
- Fix: `assert not direct_api_fallback if has_client_data`

**3.4 Secret management**
- API keyevi **ne smiju** biti hardcoded  
- Moraju dolaziti iz `settings.DEEPSEEK_API_KEY` → iz `.env`  
- Provjeri `.env` ima li sve varijable

**3.5 Session isolation**
- Redis ključevi moraju biti `ai_gateway:{tenant_id}:{session_id}` — nikad bez tenant prefiksa  
- Provjeri da tenanti ne mogu vidjeti međusobne sesije

### KORAK 4 — Integracija s postojećim kodom

Provjeri kako se DeepSeek trenutno poziva u projektu:
```bash
grep -r "deepseek\|deepseek_auto\|DEEPSEEK" /var/www/fina-connect --include="*.py" | grep -v venv | head -20
```

AI Gateway mora biti **wrapper** — ne smije razbiti postojeće pozive.  
Pattern:
```python
# Staro (ostaje kompatibilno):
deepseek_auto(prompt, has_client_data=False)

# Novo (Gateway wrapa staro):
gateway = AIGateway(tenant_id="limit-connect.com")
gateway.chat(user_message, session_id=..., has_client_data=False)
```

### KORAK 5 — Napiši unit testove
Fajl: `/var/www/fina-connect/core/tests/test_ai_gateway.py`

Minimalni testovi:
1. `test_rate_limiter_blocks_after_limit()`
2. `test_gdpr_routing_uses_bedrock_for_client_data()`
3. `test_session_isolation_between_tenants()`
4. `test_cors_origins_restricted()`
5. `test_history_truncated_at_max()`

### KORAK 6 — Izvještaj za Soneta

Napiši `/var/www/fina-connect/CC_REPORT_AI_GATEWAY.md`:
```
## Nalazi
- Sigurnosni problemi (kritični / srednji / niski)
- Kompatibilnost s postojećim deepseek_auto()
- Procjena rada za deploy (sati)
- Preporuka: deploy DA/NE + uvjeti

## Izmijenjeni/kreirani fajlovi
- ...

## Testovi
- Prolaznost: X/5
```

---

## ŠTO NE RADIŠ
- ❌ Ne deployaš ništa (nema `sudo systemctl restart`, nema migrations)
- ❌ Ne mijenjaš postojeće DeepSeek pozive u produkciji  
- ❌ Ne instaliraš FastAPI (to je opcija za kasniju fazu)
- ❌ Ne commitas bez Sonetovog odobrenja

---

## DEFINICIJA DONE
- [ ] `/var/www/fina-connect/core/ai_gateway.py` kreiran, prolazi security audit
- [ ] 5/5 unit testova prolazi
- [ ] `/var/www/fina-connect/CC_REPORT_AI_GATEWAY.md` napisan
- [ ] Nema promjena u produkcijskom kodu

