# CC Task — Cockpit: kontrolni gumbi za Ivan (mobitel)

## Što dodati u ivan_cockpit.html

Nova sekcija "Kontrolna ploča" — odmah ispod header statsa.
Velika dugmad, min 56px visine, lako za prst.

### Gumbi — redoslijed po važnosti:

```html
<div class="section-title">⚙️ Kontrole</div>
<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:1rem">

  <!-- Restart Gunicorn -->
  <button class="ctrl-btn" style="--c:#22c55e" onclick="ctrlAction('restart_gunicorn','Restart Gunicorn?')">
    <span style="font-size:1.3rem">🔄</span>
    <span>Restart App</span>
  </button>

  <!-- Restart Celery -->
  <button class="ctrl-btn" style="--c:#3b82f6" onclick="ctrlAction('restart_celery','Restart Celery?')">
    <span style="font-size:1.3rem">⚡</span>
    <span>Restart Celery</span>
  </button>

  <!-- Collectstatic -->
  <button class="ctrl-btn" style="--c:#f59e0b" onclick="ctrlAction('collectstatic','Collectstatic?')">
    <span style="font-size:1.3rem">📦</span>
    <span>Collectstatic</span>
  </button>

  <!-- Migrate -->
  <button class="ctrl-btn" style="--c:#8b5cf6" onclick="ctrlAction('migrate','Pokreni migracije?')">
    <span style="font-size:1.3rem">🗃️</span>
    <span>Migrate DB</span>
  </button>

  <!-- Clear cache -->
  <button class="ctrl-btn" style="--c:#ec4899" onclick="ctrlAction('clear_cache','Obriši cache?')">
    <span style="font-size:1.3rem">🧹</span>
    <span>Clear Cache</span>
  </button>

  <!-- Django check -->
  <button class="ctrl-btn" style="--c:#c9a84c" onclick="ctrlAction('django_check','Pokreni Django check?')">
    <span style="font-size:1.3rem">🩺</span>
    <span>Django Check</span>
  </button>

  <!-- Git status -->
  <button class="ctrl-btn" style="--c:#64748b" onclick="ctrlAction('git_status','Provjeri git status?')">
    <span style="font-size:1.3rem">📋</span>
    <span>Git Status</span>
  </button>

  <!-- Server health -->
  <button class="ctrl-btn" style="--c:#22c55e" onclick="ctrlAction('health','Provjeri health?')">
    <span style="font-size:1.3rem">❤️</span>
    <span>Server Health</span>
  </button>

</div>

<!-- Output panel -->
<div id="ctrl-output" style="display:none;background:#0d1117;border:1px solid #1e293b;border-radius:10px;padding:1rem;margin-bottom:1rem">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
    <span id="ctrl-title" style="font-size:.8rem;font-weight:700;color:#c9a84c"></span>
    <button onclick="document.getElementById('ctrl-output').style.display='none'" 
            style="background:none;border:none;color:#64748b;cursor:pointer;font-size:1rem">✕</button>
  </div>
  <pre id="ctrl-result" style="font-size:.72rem;color:#94a3b8;white-space:pre-wrap;max-height:200px;overflow-y:auto;margin:0;font-family:monospace"></pre>
</div>
```

### CSS za ctrl-btn (dodaj u style blok):
```css
.ctrl-btn {
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:.3rem;padding:.9rem .5rem;min-height:72px;
  background:#111827;border:2px solid var(--c,#333);border-radius:12px;
  color:var(--c,#e2e8f0);font-size:.78rem;font-weight:700;
  cursor:pointer;transition:all .15s;touch-action:manipulation;
  -webkit-tap-highlight-color:transparent;
}
.ctrl-btn:hover,.ctrl-btn:active{background:var(--c,#333);color:#000;transform:scale(.97)}
```

### JS — ctrlAction funkcija:
```javascript
const CTRL_COMMANDS = {
  restart_gunicorn: 'systemctl restart gunicorn-fina && echo DONE',
  restart_celery:   'systemctl restart celery-worker celery-beat && echo DONE',
  collectstatic:    'cd /var/www/fina-connect && venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -5',
  migrate:          'cd /var/www/fina-connect && venv/bin/python manage.py migrate 2>&1 | tail -10',
  clear_cache:      'cd /var/www/fina-connect && venv/bin/python manage.py shell -c "from django.core.cache import cache; cache.clear(); print(\'Cache cleared\')"',
  django_check:     'cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1',
  git_status:       'cd /var/www/fina-connect && git log --oneline -5 && echo "---" && git status --short',
  health:           'systemctl is-active gunicorn-fina celery-worker celery-beat nginx && echo "---" && df -h / | tail -1 && free -h | grep Mem',
};

function ctrlAction(action, confirmMsg) {
  if (!confirm(confirmMsg)) return;
  const cmd = CTRL_COMMANDS[action];
  if (!cmd) return;

  const output = document.getElementById('ctrl-output');
  const result = document.getElementById('ctrl-result');
  const title  = document.getElementById('ctrl-title');

  output.style.display = 'block';
  title.textContent = confirmMsg.replace('?','');
  result.textContent = '⏳ Izvršavam...';
  output.scrollIntoView({behavior:'smooth', block:'nearest'});

  fetch('/api/cockpit/exec/', {
    method: 'POST',
    headers: {'Content-Type':'application/json', 'X-CSRFToken': getCsrf()},
    body: JSON.stringify({cmd: cmd})
  })
  .then(r => r.json())
  .then(d => {
    result.textContent = d.stdout || d.output || d.result || JSON.stringify(d);
    if (d.stderr) result.textContent += '\n[STDERR]\n' + d.stderr;
  })
  .catch(e => { result.textContent = '❌ ' + e.message; });
}
```

### Korak 2 — API endpoint /api/cockpit/exec/

Provjeri postoji li:
```bash
grep -n "cockpit.*exec\|exec.*cockpit" /var/www/fina-connect/core/urls.py
```

Ako ne postoji, dodaj view u core/views.py:
```python
@login_required
def cockpit_exec(request):
    """Superadmin only — izvrši shell komandu s cockpita."""
    from django.http import JsonResponse
    import subprocess, json as json_lib
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    data = json_lib.loads(request.body)
    cmd = data.get('cmd', '').strip()
    if not cmd:
        return JsonResponse({'error': 'No command'}, status=400)
    # Blocked patterns
    BLOCKED = ['rm -rf', 'reboot', 'shutdown', 'mkfs', 'dd if=', 'chmod 777', '> /dev/']
    for b in BLOCKED:
        if b in cmd:
            return JsonResponse({'error': f'Blocked: {b}'}, status=403)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=30, cwd='/var/www/fina-connect')
        return JsonResponse({
            'stdout': r.stdout[:5000],
            'stderr': r.stderr[:1000],
            'code': r.returncode
        })
    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'Timeout (30s)'})
    except Exception as e:
        return JsonResponse({'error': str(e)})
```

Dodaj URL u core/urls.py:
```python
path('api/cockpit/exec/', views.cockpit_exec, name='cockpit_exec'),
```

## Provjere
```bash
cd /var/www/fina-connect
grep -c "cockpit_exec" core/urls.py core/views.py
venv/bin/python manage.py check 2>&1 | tail -2
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/superadmin/ivan/
```

## Javi
- HTTP status cockpita
- Je li cockpit_exec u urls.py i views.py
- Je li ctrl-btn CSS dodan
