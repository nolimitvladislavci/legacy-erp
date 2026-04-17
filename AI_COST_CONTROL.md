# AI COST CONTROL — LIMIT Connect
> Kreirao: Sonnet 4.6 (claude.ai Max plan) — 2026-04-17
> Razlog: Neplaniranih ~$149 API troškova 01-17.04.2026 zbog Claude Code (Opus 4.6)

---

## NAČELO: JEDAN PLAN, NULA SURPRIZA

**Jedini dozvoljen trošak za AI: Max Plan ($200/mj na claude.ai)**

Sve ostalo se **gasi ili zamjenjuje besplatnim/Bedrock alternativama.**

---

## ŠTO SE DESILO (Post-mortem)

| Datum | Uzrok | Trošak |
|-------|-------|--------|
| 14.04 | Claude Code + Sonnet 4.6 s prompt cachingom (Zlatni Kod sprint) | ~$40 |
| 16.04 | Claude Code + Opus 4.6 (ARHIVA, PLAY.EU sesije) | ~$59 |
| 17.04 | Opus 4.6 nastavak | ~$11 |
| 01-13.04 | Haiku/Sonnet platformski pozivi (normalni) | ~$39 |
| **UKUPNO** | | **~$149** |

**Korijen problema:** Claude Code nema upozorenje kad prelazi na skupe modele.
Opus 4.6 = $15/M input + $75/M output. Jedna duga sesija = $20-50.

---

## PRAVILA OD DANAS

### PRAVILO 1 — Claude Code: SAMO Max plan, nikad API key
```
NIKAD: claude --api-key sk-ant-...
UVIJEK: claude (prijavljen na Max plan account)
```

### PRAVILO 2 — Platforma (limit-connect.com): SAMO Haiku
```python
# settings.py — ovo je MAKSIMUM za platformske pozive
CLAUDE_MODEL = "claude-haiku-4-5-20251001"   # ~$0.25/M — prihvatljivo
HAIKU_MODEL  = "claude-haiku-4-5-20251001"   # isto
# Sonnet i Opus su ZABRANJENI za automatske platformske pozive
```

### PRAVILO 3 — Trojstvo consensus: DeepSeek via Bedrock (besplatno iz EU)
```
DeepSeek Devstral (code review) → AWS Bedrock Frankfurt = GDPR OK, nema extra troška
Pixtral (invoice scan) → AWS Bedrock Frankfurt = OK
Claude = SAMO za user-facing, Haiku
```

### PRAVILO 4 — Gemini Agent: vlastiti API key (besplatno/jeftino)
```
Gemini 1.5 Flash = praktički besplatan za naše volumene
GEMINI_API_KEY u .env → ne ide na Anthropic billing
```

### PRAVILO 5 — MCP pristup u claude.ai: MAX PLAN POKRIVA
```
claude.ai sesije (ove!) + MCP tools + server pristup = $200/mj flat
NEMA extra naplate za MCP tool calls unutar claude.ai
```

---

## CLAUDE CODE — UPUTE ZA KORIŠTENJE

### A) Claude Code iz terminala (lokalno, na Ivanovom računalu)

**Instalacija (ako već nije):**
```bash
npm install -g @anthropic-ai/claude-code
```

**ISPRAVNA prijava (Max plan, bez API troška):**
```bash
claude login
# Otvorit će browser → prijaviti se s Max plan accountom
# Nakon toga: claude radi na Max planu, nema API naplate
```

**Provjera da si na Max planu (ne API keyu):**
```bash
claude --version
# U ~/.claude.json NE smije biti "apiKey" polje postavljeno
# Ili: cat ~/.claude.json | grep -i "api\|key\|token"
```

**Ako slučajno ima API key postavljen — ukloni:**
```bash
claude config remove apiKey
# ili ručno editirati ~/.claude.json i ukloniti apiKey polje
```

**ZABRANJENE naredbe:**
```bash
# NIKAD OVO:
claude --api-key sk-ant-api03-...
ANTHROPIC_API_KEY=sk-ant-... claude
export ANTHROPIC_API_KEY=sk-ant-...  # ako je ovo postavljeno, claude koristi API!
```

**Provjera environment varijable (kritično!):**
```bash
echo $ANTHROPIC_API_KEY
# Mora biti PRAZNO kada radiš na Max planu
# Ako nije prazno: unset ANTHROPIC_API_KEY
```

**Preporučeni model za Claude Code sesije:**
```bash
# Sonnet je dovoljan za 99% coding zadataka
claude --model claude-sonnet-4-5
# Haiku za brze provjere
claude --model claude-haiku-4-5-20251001
# Opus NIKAD u redovnom radu
```

**CLAUDE.md — globalna pravila za svaki projekt:**
```bash
# Kreirati u svakom projektu /var/www/fina-connect/CLAUDE.md
# Claude Code čita ovo automatski na početku svake sesije
```

---

### B) Claude Code na serveru (root@37.27.248.76)

**Situacija:** Claude Code je instaliran na serveru i koristi se za Gemini task agenta.
Problem: ako ANTHROPIC_API_KEY postoji u env → UVIJEK koristi API (naplaćuje se!)

**Provjera trenutnog stanja:**
```bash
ssh root@37.27.248.76
echo $ANTHROPIC_API_KEY        # treba biti prazno!
cat /root/.claude.json | grep -i api  # ne smije biti apiKey
cat /var/www/fina-connect/.env | grep ANTHROPIC  # ovo je OK za platformu
```

**Problem:** Na serveru je `.env` s `ANTHROPIC_API_KEY` za Django platformu.
Claude Code na serveru može "pokupiti" tu varijablu i koristiti API!

**Fix — izolacija API keya samo za Django, ne za shell:**
```bash
# U /etc/systemd/system/fina-connect.service — API key samo za gunicorn
# NE u /etc/environment ili /root/.bashrc

# Provjeri je li u bashrc:
grep ANTHROPIC /root/.bashrc /root/.profile /etc/environment 2>/dev/null
# Ako postoji — ukloniti!
```

**Na serveru Claude Code NIJE za interaktivni rad — samo za Gemini agenta.**
Gemini agent (core/gemini_agent.py) treba API key samo za Django process, ne za shell.

**Zaključak za server:** Claude Code na serveru = ne koristiti interaktivno.
Sve CC Code zadatke raditi lokalno na Ivanovom računalu (Max plan).

---

## PLATFORMA — HITNI FIX MODELA

Ovi redovi u settings.py moraju biti ovako (ne Sonnet, ne Opus):

```python
# /var/www/fina-connect/core/settings.py
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
HAIKU_MODEL  = os.environ.get("HAIKU_MODEL", "claude-haiku-4-5-20251001")
```

I u anthropic_advisor.py:
```python
# /var/www/fina-connect/core/anthropic_advisor.py
HAIKU_MODEL  = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-haiku-4-5-20251001"  # downgrade na Haiku dok troškovi nisu pod kontrolom
```

---

## ZAMJENA PLANA — AI STACK BEZ SURPRIZA

| Zadatak | Stari pristup | Novi pristup | Trošak |
|---------|--------------|--------------|--------|
| Ivan dev sesije | Claude Code (API) | claude.ai Max plan + MCP | $0 extra |
| Trojstvo code review | Claude Opus/Sonnet API | DeepSeek Devstral (Bedrock) | AWS (minimalno) |
| Invoice scan (Pixtral) | Bedrock | Bedrock | AWS (minimalno) |
| Platformski AI pozivi | Haiku API | Haiku API (Haiku ostaje) | ~$5-15/mj |
| Gemini agent | Gemini API | Gemini API (vlastiti key) | ~$0 za naše volumene |
| Dugi coding taskovi | Opus CC | claude.ai Max plan sesije | $0 extra |

**Cilj: API billing < $20/mj (samo Haiku za platformu)**

---

## MONITORING — PRATITI SVAKI TJEDAN

```bash
# Na kraju svake radne nedjelje provjeriti:
# https://console.anthropic.com/settings/billing → Usage
# Ako je > $20 u tjednu → STOP, debug koji poziv uzrokuje

# Na serveru — log AI poziva:
grep "anthropic\|claude\|haiku" /var/log/fina-connect/gunicorn.log | tail -50
```

---

## ZNAMO U ŠTO SMO SE UPUSTILI

Gradimo SaaS platformu s AI kao core featureom na bootstrapped budžetu.
Pravilo je jednostavno: **AI mora biti profitabilan, ne trošak.**

Trenutni model:
- Platforma naplaćuje klijentima (Šeki, Marija, Nikša...)
- AI trošak mora biti < 5% prihoda
- Max plan ($200) = fiksni trošak, predvidiv
- API = varijabilni trošak, nepredvidiv → minimizirati

Kad platforma naraste na 500+ firmi i AI postane value add koji klijenti plaćaju →
tek tada API billing ima smisla jer je pokriven prihodom.

**Do tada: Max plan + DeepSeek + Gemini = nula surpriza.**

