# FENIX AGENT COMMAND CENTER
> "Tri glave, jedan čopor, jedan Ivan koji zapovijedaju."
> Zapis: 2026-04-15 | Status: PLAN — čeka implementaciju

---

## FILOZOFIJA

```
Trenutno: Ivan → piše kod → ručno deploya → agenti REAGIRAJU na events
Željeno:  Ivan → Fenix Soba → piše zadatak → agent IZVRŠAVA → Ivan potvrđuje

TRI GLAVE ČOPORA:
  HAIKU     = Executor  (brz, jeftin, implementacija koda)
  GEMINI    = Researcher (web search, analiza, druga perspektiva)
  DEEPSEEK  = Coder (code review, refaktoring, noćni patrol)
  OPUS      = Starješina (arhitekturalne krize — max 1-2x tjedno)
  SONNET    = Koordinator (Trojstvo arbitar, ovaj razgovor)
```

---

## ARHITEKTURA TOKA

```
FENIX SOBA (browser UI)
  │  Ivan piše zadatak + odabire agenta + bira scope
  ▼
AgentTask (DB model)
  │  status: draft → queued → running
  ▼
Celery Worker (heavy queue)
  │  Agent dobiva instruction + context fajlove
  │
  ├── Tool: read_file(path)        [auto]
  ├── Tool: write_file(path)       [auto + diff prikaz]
  ├── Tool: exec_command(cmd)      [auto ako je whitelist]
  ├── Tool: git_commit(msg)        [BLOKIRA → čeka Ivan]
  ├── Tool: manage.py migrate      [BLOKIRA → čeka Ivan]
  └── Tool: search_web(query)      [auto, Gemini only]
  │
  ▼
AgentTaskLog (svaki korak)
  │  WebSocket stream → Fenix Soba live
  ▼
Ivan: [ODOBRI] ili [ODBACI] ili [NASTAVI s korekcijom]
```

---

## SIGURNOSNI MODEL — 3 RAZINE

```
RAZINA 1 — Auto (bez pitanja):
  read_file     — samo /var/www/fina-connect/
  git_diff/log  — čitanje
  SQL SELECT    — samo
  search_web    — Gemini only
  run_tests     — manage.py test (čitanje)

RAZINA 2 — Auto + log (vidljivo Ivanu):
  write_file    — uvijek kreira .bak, diff vidljiv
  makemigrations — generira, NE aplicira
  manage.py check

RAZINA 3 — Ivan mora kliknuti gumb:
  git commit + push
  manage.py migrate
  restart service
  Svaka naredba izvan whiteliste

NIKAD:
  .env pisanje
  settings.py pisanje
  Destruktivne naredbe (blokira parser)
  Klijentski podaci kroz Haiku/DeepSeek direktni API
```

---

## MODELI

### AgentTask

```python
class AgentTask(models.Model):
    AGENT = [('haiku','Haiku'),('gemini','Gemini'),('deepseek','DeepSeek'),('opus','Opus')]
    STATUS = [
        ('draft','Nacrt'),('queued','U redu'),('running','Izvršava'),
        ('awaiting','Čeka odobrenje'),('approved','Odobreno'),
        ('rejected','Odbijeno'),('done','Gotovo'),('failed','Neuspješno'),
    ]
    SCOPE = [
        ('read','Samo čitanje'),('write','Pisanje fajlova'),
        ('deploy','Migracija+restart'),('research','Web istraživanje'),
    ]
    id            = UUIDField(primary_key=True)
    agent         = CharField(choices=AGENT)
    title         = CharField(max_length=200)
    instruction   = TextField()
    scope         = CharField(choices=SCOPE)
    context_files = JSONField(default=list)   # ['documents/views_scan.py']
    status        = CharField(choices=STATUS, default='draft')
    thinking      = TextField(blank=True)     # chain-of-thought agenta
    plan          = TextField(blank=True)     # što planira napraviti
    output        = TextField(blank=True)     # finalni diff/rezultat
    error         = TextField(blank=True)
    requires_approval = BooleanField(default=False)
    approved_by   = ForeignKey(User, null=True, blank=True)
    approved_at   = DateTimeField(null=True, blank=True)
    tokens_in     = IntegerField(default=0)
    tokens_out    = IntegerField(default=0)
    cost_usd      = DecimalField(max_digits=8, decimal_places=6, default=0)
    created_by    = ForeignKey(User)
    created_at    = DateTimeField(auto_now_add=True)
```

### AgentTaskLog

```python
class AgentTaskLog(models.Model):
    TOOL = [
        ('think','Razmišlja'),('read_file','Čita fajl'),
        ('write_file','Piše fajl'),('exec_command','Izvršava naredbu'),
        ('git_op','Git operacija'),('search_web','Web pretraga'),
        ('ask_ivan','Pita Ivana'),('done','Gotovo'),('error','Greška'),
    ]
    task     = ForeignKey(AgentTask, related_name='logs')
    tool     = CharField(choices=TOOL)
    input_data  = TextField(blank=True)
    output_data = TextField(blank=True)
    is_pending_approval = BooleanField(default=False)
    created_at  = DateTimeField(auto_now_add=True)
```

---

## AGENT TOOLS (borg_ops/agent_tools.py)

```python
COMMAND_WHITELIST = [
    'manage.py check', 'manage.py test', 'manage.py showmigrations',
    'manage.py makemigrations', 'git diff', 'git log', 'git status',
    'ruff check', 'wc -l', 'grep',
]

BLOCKED_PATHS = ['.env', 'settings.py', 'secrets/', 'private_keys/']

def read_file(path: str) -> str:
    """Čita fajl, provjerava whitelist puta."""

def write_file(path: str, content: str) -> dict:
    """Piše fajl, kreira .bak, vraća diff."""

def exec_command(cmd: str) -> dict:
    """Izvršava naredbu ako je na whitelisti."""

def git_commit(msg: str) -> str:
    """BLOKIRA — zapisuje u log, čeka Ivan odobrenje."""

def search_web(query: str) -> list:
    """Gemini only — pretražuje web."""
```

---

## WEBSOCKET — FenixAgentConsumer

```python
# borg_ops/consumers_agent.py

class FenixAgentConsumer(AsyncJsonWebsocketConsumer):
    # ws/fenix/agent/<task_id>/

    # Server → Client poruke:
    # {"type": "thinking",   "content": "Analiziram views_scan.py..."}
    # {"type": "tool_start", "tool": "read_file", "input": "path/to/file"}
    # {"type": "tool_end",   "tool": "read_file", "output": "sadržaj..."}
    # {"type": "diff",       "path": "file.py", "diff": "+novo\n-staro"}
    # {"type": "approval",   "message": "Spreman za commit. Odobravaš?"}
    # {"type": "done",       "summary": "3 fajla, 0 grešaka"}
    # {"type": "error",      "error": "check pao: ..."}

    # Client → Server:
    # {"type": "approve"}
    # {"type": "reject"}
    # {"type": "message", "content": "Dodaj i scan_poll"}
```

---

## UI — FENIX SOBA

```
┌─────────────────────────────────────────────────────────┐
│ FENIX SOBA                              [Ivan] [logout] │
├──────────────┬──────────────┬──────────────────────────┤
│  HAIKU       │  GEMINI      │  DEEPSEEK                │
│  Executor    │  Researcher  │  Code Patrol             │
├──────────────┼──────────────┼──────────────────────────┤
│              │              │                          │
│  [chat log]  │  [chat log]  │  [chat log]              │
│  💭 Čitam... │              │                          │
│  📖 Otvaram  │              │                          │
│  ✏️  Pišem..  │              │                          │
│              │              │                          │
│  [DIFF]      │              │                          │
│  +nova linji │              │                          │
│  -stara...   │              │                          │
│              │              │                          │
│  [✅ ODOBRI] │              │                          │
│  [❌ ODBACI] │              │                          │
├──────────────┴──────────────┴──────────────────────────┤
│  Zadatak: [Prepiši scan_upload za ScanToken model    ] │
│  Agent: [Haiku▼] Scope: [write▼] Fajl: [views_scan +]│
│                                          [POŠALJI →]   │
└─────────────────────────────────────────────────────────┘
Sidebar — historija:
  HAIKU [DONE] ARHIVA-1 ScanToken view (15.04.)
  HAIKU [DONE] CompanyMiddleware patch (14.04.)
  HAIKU [AWAIT] scan_poll rewrite ← 23min
  GEMINI [DONE] Europeana API research
```

---

## REDOSLIJED IMPLEMENTACIJE

```
FAZA 1 — Modeli (2h) — CC Code
  AgentTask + AgentTaskLog + AgentToolPermission
  Migracija + admin
  Seed: tool permissions po agentu

FAZA 2 — Alati (3h) — CC Code
  borg_ops/agent_tools.py
  Whitelist parser, backup logika, diff generator

FAZA 3 — Celery Workers (4h) — CC Code
  borg_ops/tasks_agent.py
  execute_haiku_task, execute_gemini_task, execute_deepseek_task
  Agentic loop s tool use (Anthropic tool_use API)
  Status update + WebSocket broadcast

FAZA 4 — WebSocket (2h) — CC Code
  borg_ops/consumers_agent.py
  core/asgi.py routing update

FAZA 5 — UI Fenix Soba (4h) — CC Code
  templates/borg_ops/fenix_soba.html
  URL /hr/borg/fenix-soba/
  RouteRegistry: AUTHENTICATED, samo Ivan + superadmin
  JS: WebSocket client, diff renderer, odobri/odbaci

FAZA 6 — Integracija (1h) — CC Code
  Link iz AI cockpit-a
  WhatsApp ako agent čeka odobrenje >30 min
  Trojstvo → "Pošalji Haiku-u" gumb na ImprovementSuggestion

UKUPNO: ~16h CC Code rada
```

---

## TROŠKOVI

```
HAIKU:    ~$0.004/task (3 lipe)
GEMINI:   ~$0.0006/task (ispod lipe)
DEEPSEEK: ~$0.001/task (ispod lipe)
OPUS:     ~$0.30/task (22 lipe) — MAX 1-2x tjedno

Procjena 5 taskova/dan:
  150 Haiku + 30 Gemini + 60 DeepSeek + 10 Opus = ~$3.68/mj (2.68€)
```

---

## PRIMJERI (Ivan piše)

```
→ HAIKU:
  "Prepiši scan_mobile_page i scan_upload u documents/views_scan.py
  da koriste ScanToken model umjesto Redis sesija.
  Context: documents/views_scan.py, documents/models.py"

→ GEMINI:
  "Istraži Creative Europe 2026 deadlines za small cooperation.
  Treba: deadline, iznos, broj partnera, link na poziv."

→ DEEPSEEK:
  "Analiziraj documents/views_arhiva.py — N+1 problemi s prijedlozima."

→ OPUS (rijetko):
  "Kada separirati memio_world u zasebni servis? Rizici? Timing?"
```

---

## INTEGRACIJA S TROJSTVOM

```
Trojstvo (reaktivan):  korisnik zlatno dugme → AI analiza problema
Command Center (proaktivan): Ivan direktna zapovijed → agent izvršava

Most: Trojstvo nalaz → "Pošalji Haiku-u" gumb →
      AgentTask se kreira prepopulirana → Haiku odmah rješava
```

---

## ZAŠTITA

```
1. Izolacija — agent vidi SAMO whitelist puteve
2. Backup — write_file kreira .bak uvijek
3. Diff — Ivan vidi razliku PRIJE commita
4. Timeout — 24h neaktivnosti = auto-odbijeno
5. Rollback — "Vrati" gumb = git revert jednim klikom
6. Audit — AgentTaskLog nikad se ne briše
7. Rate limit — max 3 paralelna Haiku taska, 1 Opus/dan
8. Klijentski podaci — NIKAD kroz Haiku direktni API
```
