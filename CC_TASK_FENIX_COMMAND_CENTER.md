# CC_TASK — FENIX AGENT COMMAND CENTER
Executor: CC Code | Koordinator: Sonnet | Dan 49 | 2026-04-15
CILJ: #1 AI-powered ERP u EU — Tri glave, jedan Ivan, nema granica.

---
## MISIJA

Ivan sjedi u Fenix Sobi. Piše jedan zadatak.
Agent ga odmah izvršava. Ivan odobri commit. Gotovo.
Ne chatbot. Ne asistent. RADNA SOBA S TRI GLAVE.

---
## KONTEKST

Server: 37.27.248.86 | /var/www/fina-connect
App: borg_ops (vec postoji, tu dodajemo sve)
Channels: Django Channels + Redis AKTIVNI (ws aukcije rade u udruge/)
Tool use: Anthropic SDK 0.83.0 — VERIFICIRAN danas
Haiku: claude-haiku-4-5-20251001 (settings.HAIKU_MODEL)
Sonnet: claude-sonnet-4-5 (settings.CLAUDE_MODEL)
Opus: claude-opus-4-6
Gemini: gemini-2.5-flash (settings.GEMINI_API_KEY)
DeepSeek: deepseek-chat (settings.DEEPSEEK_API_KEY)
asgi.py: samo udruge WS, treba prosiriti u Fazi 4
Migracije: borg_ops do 0009_domainregistry

---
## PRAVILA (obavezno)

1. Citaj modele.py prije pisanja koda — nikad ne pretpostavljaj field name
2. Pravilo 1: globalni fix, ne zakrpa
3. Pravilo 7: svaka ruta u RouteRegistry
4. manage.py check mora proci nakon svake faze
5. Commit nakon svake faze s tocnom porukom

---
## FAZA 1 — MODELI (2h)
Lokacija: borg_ops/models.py (dodaj na kraj, nakon BorgSignal)

### AgentTask model

Importi koji trebaju (dodaj na vrh ako nema):
  import uuid
  from django.conf import settings

Polja:
  id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
  agent = CharField(max_length=10, choices=[
    ('haiku','Claude Haiku — Executor'),
    ('gemini','Gemini — Researcher'),
    ('deepseek','DeepSeek — Coder'),
    ('opus','Claude Opus — Starjesina'),
  ])
  title = CharField(max_length=200)
  instruction = TextField(help_text='Ivan zadatak u prirodnom jeziku')
  scope = CharField(max_length=10, choices=[
    ('read','Samo citanje'),
    ('write','Pisanje fajlova'),
    ('deploy','Migracija + restart'),
    ('research','Web istrazivanje'),
  ], default='read')
  context_files = JSONField(default=list, blank=True)
  status = CharField(max_length=10, choices=[
    ('draft','Nacrt'),('queued','U redu'),('running','Izvrsava se'),
    ('awaiting','Ceka odobrenje'),('approved','Odobreno'),
    ('rejected','Odbijeno'),('done','Gotovo'),('failed','Neuspjesno'),
  ], default='draft')
  agent_plan = TextField(blank=True)
  agent_output = TextField(blank=True)
  agent_summary = TextField(blank=True)
  error_log = TextField(blank=True)
  requires_approval = BooleanField(default=False)
  approval_prompt = TextField(blank=True)
  approved_by = ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                  on_delete=SET_NULL, related_name='approved_agent_tasks')
  approved_at = DateTimeField(null=True, blank=True)
  tokens_in = IntegerField(default=0)
  tokens_out = IntegerField(default=0)
  cost_usd = DecimalField(max_digits=8, decimal_places=6, default=0)
  created_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                null=True, related_name='created_agent_tasks')
  created_at = DateTimeField(auto_now_add=True)
  updated_at = DateTimeField(auto_now=True)
  Meta: ordering=['-created_at'], verbose_name='Agent Task'
  __str__: return f"[{self.agent.upper()}] {self.title} ({self.get_status_display()})"

### AgentTaskLog model

Polja:
  task = ForeignKey(AgentTask, on_delete=CASCADE, related_name='logs')
  tool_type = CharField(max_length=15, choices=[
    ('think','Razmisljanje'),('plan','Plan'),
    ('read_file','Cita fajl'),('write_file','Pise fajl'),
    ('exec_cmd','Izvrš naredbu'),('git_op','Git operacija'),
    ('search_web','Web pretraga'),('ask_ivan','Pita Ivana'),
    ('diff','Diff prikaz'),('done','Gotovo'),('error','Greska'),
  ])
  tool_input = TextField(blank=True)
  tool_output = TextField(blank=True)
  is_approval_gate = BooleanField(default=False)
  duration_ms = IntegerField(default=0)
  created_at = DateTimeField(auto_now_add=True)
  Meta: ordering=['created_at'], verbose_name='Agent Log'

### Admin (borg_ops/admin.py — dodaj na kraj):
  @admin.register(AgentTask)
  class AgentTaskAdmin(ModelAdmin):
    list_display = ['title','agent','scope','status','cost_usd','created_by','created_at']
    list_filter = ['agent','status','scope']
    readonly_fields = ['id','tokens_in','tokens_out','cost_usd','created_at','updated_at']

  @admin.register(AgentTaskLog)
  class AgentTaskLogAdmin(ModelAdmin):
    list_display = ['task','tool_type','is_approval_gate','duration_ms','created_at']
    readonly_fields = ['created_at']

Naredbe:
  manage.py makemigrations borg_ops
  manage.py migrate
  manage.py check

Commit: feat(command-center): Faza 1 — AgentTask + AgentTaskLog modeli

---
## FAZA 2 — AGENT TOOLS (3h)
Lokacija: borg_ops/agent_tools.py (NOVI FAJL)

Konstante na vrhu:
  PROJECT_ROOT = Path('/var/www/fina-connect')
  BACKUP_DIR = PROJECT_ROOT / '.agent_backups'
  COMMAND_WHITELIST (dict: alias -> shell cmd template)
  BLOCKED_PATHS = {'.env', 'settings.py', 'local_settings.py', 'secrets/'}
  ALLOWED_WRITE_EXTENSIONS = {'.py', '.html', '.css', '.js', '.md', '.json', '.txt'}

RAZINA 1 — Auto:

def read_file(path, max_lines=500) -> dict:
  - _resolve_path provjera
  - Cita UTF-8, truncira na max_lines
  - Vraca: {ok, content, lines, truncated}

def git_diff(args='') -> dict:
  - subprocess git diff args
  - Vraca: {ok, diff[:5000], error}

def run_check() -> dict:
  - subprocess manage.py check
  - Vraca: {ok, output}

def list_directory(path='.') -> dict:
  - Preskoci venv/__pycache__/.git
  - Vraca: {ok, items:[{name,type,size}]}

RAZINA 2 — Auto + log:

def write_file(path, content) -> dict:
  - Provjeri ekstenziju (ALLOWED_WRITE_EXTENSIONS)
  - Backup starog u BACKUP_DIR/filename.YYYYMMDD_HHMMSS.bak
  - Pisi novi sadrzaj
  - Generiraj _simple_diff
  - Vraca: {ok, path, diff, lines_new}

def run_makemigrations(app) -> dict:
  - subprocess manage.py makemigrations app
  - Vraca: {ok, output}

RAZINA 3 — Odobrenje Ivana:

def request_git_commit(msg) -> dict:
  - NE commitira!
  - Vraca: {ok:True, approval_needed:True, action:'git_commit',
            commit_msg:msg, diff_stat:str, prompt:str}

def execute_git_commit(msg) -> dict:
  - SAMO poziva continue_after_approval
  - git add -A && git commit -m msg
  - Vraca: {ok, commit:hash}

def request_migrate(app='') -> dict:
  - Vraca: {ok:True, approval_needed:True, action:'migrate', prompt:str}

def execute_migrate(app='') -> dict:
  - manage.py migrate [app]
  - Vraca: {ok, output}

Pomocne:
def _resolve_path(path) — sigurnosna provjera path traversal
def _simple_diff(old, new, filename) — difflib.unified_diff, max 200 linija
def _tool_log_type(tool_name) -> str — mapira na AgentTaskLog.tool_type

HAIKU_TOOLS lista (za Anthropic API):
  Definiraj tool definitions za:
  read_file, write_file, run_check, git_diff, request_git_commit,
  list_directory, run_makemigrations
  Svaki: {name, description, input_schema: {type:object, properties, required}}

Commit: feat(command-center): Faza 2 — agent_tools.py sigurnosni sloj

---
## FAZA 3 — CELERY WORKERS (4h)
Lokacija: borg_ops/tasks_agent.py (NOVI FAJL)

COST_PER_TOKEN dict:
  haiku:    {in: 0.80/1M, out: 4.00/1M}
  gemini:   {in: 0.075/1M, out: 0.30/1M}
  deepseek: {in: 0.27/1M, out: 1.10/1M}
  opus:     {in: 15.0/1M, out: 75.0/1M}

@shared_task execute_agent_task(task_id):
  - queue='heavy', soft_time_limit=1800, bind=True, max_retries=0
  - status='running', _ws_send started
  - Dispatch na _run_haiku/_run_gemini/_run_deepseek/_run_opus
  - Na Exception: status='failed', _log error, _ws_send error

_run_haiku(task):
  1. system = _build_system_prompt('haiku', task)
  2. messages = [user: _build_user_message(task)]
  3. LOOP max 20 iteracija:
     a. client.messages.create(HAIKU_MODEL, tools=HAIKU_TOOLS, messages)
     b. Broji tokens, azuriraj total_in/out
     c. Za svaki blok:
        - type=='text': _log think, _ws_send thinking
        - type=='tool_use': dodaj u tool_calls lista
     d. Ako stop_reason=='end_turn' i nema tool_calls:
        → task.status='done', agent_summary, _save_cost, WS done, RETURN
     e. Za svaki tool_call: result = _execute_tool(task, tool_call)
        - Ako result.get('approval_needed'):
          → status='awaiting', requires_approval=True, approval_prompt
          → Spremi messages u agent_output (JSON, zadnjih 10)
          → _save_cost, save, _ws_send approval, RETURN (stani)
     f. messages += assistant response + tool_results
  4. Limit: status='failed', error='Max iteracija'

_run_gemini(task):
  - google.generativeai, gemini-2.5-flash
  - Ako scope='research': dodaj WEB SEARCH hint u prompt
  - model.generate_content(prompt)
  - Spremi u agent_summary[:3000]
  - Tokens iz usage_metadata
  - status='done', WS done

_run_deepseek(task):
  - deepseek_reasoner() za write/deploy
  - deepseek_direct() za read/research
  - Spremi u agent_summary
  - cost_usd = Decimal('0.001') aprox

_run_opus(task):
  - client.messages.create('claude-opus-4-6', max_tokens=3000, NO tools)
  - Samo savjet, bez akcija
  - Spremi, _save_cost

@shared_task continue_after_approval(task_id, approved):
  - Ako not approved: status='rejected', WS rejected, RETURN
  - Citaj task.approval_prompt, trazi 'commit' ili 'migrate'
  - Ako 'commit': izvuci commit_msg iz approval_prompt, execute_git_commit
  - Ako 'migrate': execute_migrate
  - approved_by=task.created_by, approved_at=now, requires_approval=False
  - status='done', WS approved

@shared_task check_awaiting_tasks():
  - Trazi AgentTask status='awaiting', updated_at < now - 30min
  - Za svaki: send_text('+4915771998747', poruka s linkom)

_execute_tool(task, tool_call) -> dict:
  - Mapira tool_call.name na funkciju iz agent_tools
  - Mjeri duration_ms
  - _log s input/output
  - _ws_send tool_start i tool_end
  - Za write_file: _ws_send diff
  - Vraca result dict

_ws_send(task_id, data):
  - get_channel_layer().group_send(f'agent_task_{task_id}', {type:'agent_message', data:data})
  - Wrappano u try/except

_build_system_prompt(agent, task) -> str
_build_user_message(task) -> str (instruction + context fajlovi)
_gather_context_files(task) -> str (citaj svaki path iz task.context_files)
_log(task, tool_type, input_d, output_d, duration_ms=0)
_save_cost(task, tokens_in, tokens_out, agent)

Commit: feat(command-center): Faza 3 — Celery agentic workers

---
## FAZA 4 — WEBSOCKET (2h)

NOVI FAJL: borg_ops/consumers_agent.py

class FenixAgentConsumer(AsyncJsonWebsocketConsumer):
  room = f'agent_task_{task_id}'

  connect():
    - task_id iz url_route kwargs
    - Provjeri auth: not authenticated ili not (is_superuser or is_staff) -> close()
    - group_add, accept
    - send_json init + _get_task_state

  receive_json(content):
    type='approve'  -> continue_after_approval.delay(task_id, True)
    type='reject'   -> continue_after_approval.delay(task_id, False)
    type='start'    -> AgentTask.objects.filter(pk=task_id, status='draft').update(status='queued')
                       execute_agent_task.delay(task_id)
    type='ping'     -> send_json pong + state

  agent_message(event):
    -> send_json(event['data'])

  @database_sync_to_async _get_task_state():
    Vraca dict s task podacima + logs[:50]

NOVI FAJL: borg_ops/routing.py
  from django.urls import re_path
  from . import consumers_agent
  websocket_urlpatterns = [
    re_path(r'ws/fenix/agent/(?P<task_id>[0-9a-f-]+)/$',
            consumers_agent.FenixAgentConsumer.as_asgi())
  ]

IZMJENA: core/asgi.py
  Uvezi oba routing modula:
    from udruge.routing import websocket_urlpatterns as auction_ws
    from borg_ops.routing import websocket_urlpatterns as agent_ws
  URLRouter(auction_ws + agent_ws)

Commit: feat(command-center): Faza 4 — WebSocket FenixAgentConsumer

---
## FAZA 5 — UI FENIX SOBA (4h)

NOVI TEMPLATE: templates/borg_ops/fenix_soba.html

Header (full width):
  "FENIX SOBA" naslov (zlatno)
  Danasnji troskovi: .XX | Ukupno taskova: N | Ceka odobrenje: N

3 kolone (CSS grid, desktop row, mobile column):
  Svaka kolona = jedan agent (HAIKU / GEMINI / DEEPSEEK)
  Header kolone: ime agenta, model, boja pozadine (razlicita po agentu)
  
  Chat log (scrollable, min-height 400px, monospace za kod):
    Poruke s emoji ikonama po tool_type
    Auto-scroll na dno

  Diff prikaz (visibilty:hidden dok nema diffa):
    + linije: #d4edda zelena
    - linije: #f8d7da crvena
    max-height 300px overflow-y scroll

  Approval box (display:none dok status != awaiting):
    Zlatni border, pulsira animacijom
    Tekst approval_prompt
    [ODOBRI] gumb zeleni, [ODBACI] gumb crveni
    VELIKI, 50px height

  Input forma (sticky na dnu kolone):
    textarea placeholder "Zapovijedaj..."
    select: scope [read/write/research/deploy]
    input: context fajlovi (comma-separated)
    button [POŠALJI] zlatni, siri se na full width

Sidebar (lijevo, 220px, collapsible):
  "Historija" naslov
  Lista zadnjih 20 AgentTask:
    [HAIKU] fix scan_upload (done) /bin/sh.004
    [GEMINI] EU deadlines (done) /bin/sh.0006
    Klik → ucitava task u chat

JS WebSocket logika (vanilla JS, bez frameworka):
  Poseban ws objekt za svaki aktivni task
  wsHandlers objekt mapira type na DOM akciju:
    'thinking'   -> appendMessage(col, '💭', content, 'grey')
    'tool_start' -> appendMessage(col, icon(tool), input, 'blue')
    'tool_end'   -> updateLastMessage(col, output)
    'diff'       -> showDiff(col, path, diff)
    'approval'   -> showApprovalBox(col, message)
    'done'       -> appendMessage(col, '✅', summary, 'green')
    'error'      -> appendMessage(col, '❌', error, 'red')
    'approved'   -> hideApprovalBox(col)
    'rejected'   -> hideApprovalBox(col)
  
  createTask(agent, instruction, scope, context_files):
    POST /hr/borg/api/agent-task/create/
    Odgovor: {ok:true, task_id}
    ws[task_id] = new WebSocket(...)
    ws.onopen -> ws.send({type:'start'})

VIEW: borg_ops/views.py — dodaj:
  @login_required
  def fenix_soba(request):
    if not request.user.is_superuser: return redirect('borg_ops:index')
    recent_tasks = AgentTask.objects.all().order_by('-created_at')[:20]
    today_cost = ... aggregate Sum cost_usd za danas
    pending = AgentTask.objects.filter(status='awaiting').count()
    return render(..., {recent_tasks, today_cost, pending})

  @login_required
  @require_POST
  @csrf_exempt  [NE! koristi @csrf_protect i X-CSRFToken header]
  def create_agent_task(request):
    data = json.loads(request.body)
    task = AgentTask.objects.create(
      agent=data['agent'], title=data.get('title', data['instruction'][:80]),
      instruction=data['instruction'], scope=data.get('scope','read'),
      context_files=data.get('context_files',[]),
      status='draft', created_by=request.user
    )
    return JsonResponse({'ok': True, 'task_id': str(task.pk)})

borg_ops/urls.py — dodaj:
  path('fenix-soba/', views.fenix_soba, name='fenix_soba')
  path('api/agent-task/create/', views.create_agent_task, name='create_agent_task')

RouteRegistry:
  'fenix_soba': AccessLevel.AUTHENTICATED
  'create_agent_task': AccessLevel.AUTHENTICATED

Commit: feat(command-center): Faza 5 — Fenix Soba UI

---
## FAZA 6 — INTEGRACIJA (1h)

6.1 Link u AI Cockpit (limit_connect_ai/views.py):
  ai_cockpit context += {
    'fenix_soba_url': reverse('borg_ops:fenix_soba'),
    'pending_agent_tasks': AgentTask.objects.filter(status='awaiting').count()
  }
  Template ai_cockpit.html: dodaj banner ako pending > 0

6.2 ImprovementSuggestion veza (pos/views.py ili improvement_detail):
  Gumb "Pošalji Haiku-u" na detail stranicu suggestiona
  POST na create_agent_task s:
    agent='haiku', scope='write',
    instruction=f"Rijesi ovaj problem: {s.title}\n{s.description}",
    title=f'Fix: {s.title[:80]}'

6.3 Celery Beat za check_awaiting_tasks:
  core/settings.py → CELERY_BEAT_SCHEDULE:
  'agent-awaiting-check': {
    'task': 'borg_ops.tasks_agent.check_awaiting_tasks',
    'schedule': 900
  }
  Restart celery-beat servis.

6.4 Obnovi FENIX_STATUS.md:
  GORIVO: FENIX SOBA → status + postotak
  SESIJA LOG: 6 commitova
  DASHBOARD: agent_tasks_today statistika
  BACKLOG: ukloni B-01 do B-03 ako su riješeni

6.5 Final manage.py check i git log --oneline -10

Commit: feat(command-center): Faza 6 — Integracija + Celery Beat

---
## ZAVRŠNI IZVJEŠTAJ

FENIX SOBA STATUS:
  AgentTask model:           [OK/FAIL]
  AgentTaskLog model:        [OK/FAIL]
  agent_tools.py:            [OK/FAIL]
  Haiku worker (tool_use):   [OK/FAIL]
  Gemini worker:             [OK/FAIL]
  DeepSeek worker:           [OK/FAIL]
  Opus worker:               [OK/FAIL]
  WebSocket consumer:        [OK/FAIL]
  asgi.py routing:           [OK/FAIL]
  UI Fenix Soba:             [OK/FAIL]
  RouteRegistry:             [OK/FAIL]
  IS veza (Haiku-u gumb):    [OK/FAIL]
  WhatsApp alert (30min):    [OK/FAIL]
  manage.py check:           [OK/FAIL]
  Commit Faza 1: {hash}
  Commit Faza 2: {hash}
  Commit Faza 3: {hash}
  Commit Faza 4: {hash}
  Commit Faza 5: {hash}
  Commit Faza 6: {hash}

AŽURIRAJ FENIX_STATUS.md NA KRAJU.
