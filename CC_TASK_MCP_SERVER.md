# CC Task — FENIX MCP Server

## Što gradimo
MCP (Model Context Protocol) server koji Sonnet može direktno koristiti
bez MD fajlova, bez base64, bez Dev API posrednika.

## Instalacija

```bash
cd /var/www/fina-connect
venv/bin/pip install fastmcp --break-system-packages
venv/bin/pip install mcp --break-system-packages
```

## Fajl: /var/www/fina-connect/core/mcp_server.py

```python
"""
FENIX MCP Server — direktni pristup za Sonnet
Pokreće se kao: venv/bin/python core/mcp_server.py
Port: 8765 (lokalno), eksponiran kroz nginx na /mcp/
"""
import os, sys, subprocess, json
sys.path.insert(0, '/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from fastmcp import FastMCP

mcp = FastMCP("Fenix LIMIT Connect")

PROJECT = '/var/www/fina-connect'
BLOCKED = ['rm -rf', 'reboot', 'shutdown', 'mkfs', 'chmod 777']

# ── 1. Baza ─────────────────────────────────────────────────
@mcp.tool()
def query_db(sql: str) -> str:
    """Izvrši SQL upit na PostgreSQL bazi. Samo SELECT preporučeno."""
    from django.db import connection
    try:
        with connection.cursor() as cur:
            cur.execute(sql)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchmany(100)
                return json.dumps({'columns': cols, 'rows': rows, 'count': len(rows)}, default=str)
            return json.dumps({'affected': cur.rowcount})
    except Exception as e:
        return json.dumps({'error': str(e)})

@mcp.tool()
def django_orm(code: str) -> str:
    """Izvrši Django ORM kod. Primjer: from pos.models import POSReceipt; output=POSReceipt.objects.count()"""
    try:
        loc = {}
        exec(code, {'__builtins__': __builtins__}, loc)
        return str(loc.get('output', 'OK — nema output varijable'))
    except Exception as e:
        return f'Error: {e}'

# ── 2. Fajlovi ──────────────────────────────────────────────
@mcp.tool()
def read_file(path: str) -> str:
    """Čitaj fajl iz projekta. Path relativno od /var/www/fina-connect/"""
    full = os.path.join(PROJECT, path.lstrip('/')) if not path.startswith(PROJECT) else path
    if not full.startswith(PROJECT):
        return 'Error: path outside project'
    try:
        content = open(full).read()
        lines = content.count('\n')
        return f'[{lines} linija]\n{content[:30000]}'
    except Exception as e:
        return f'Error: {e}'

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Piši fajl u projekt."""
    full = os.path.join(PROJECT, path.lstrip('/')) if not path.startswith(PROJECT) else path
    if not full.startswith(PROJECT):
        return 'Error: path outside project'
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, 'w').write(content)
        return f'OK: {path} ({len(content)} chars)'
    except Exception as e:
        return f'Error: {e}'

@mcp.tool()
def list_files(path: str = '.', pattern: str = '') -> str:
    """Listaj fajlove u direktoriju."""
    full = os.path.join(PROJECT, path.lstrip('/'))
    try:
        result = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'venv', 'node_modules')]
            for f in files:
                if not pattern or pattern in f:
                    rel = os.path.relpath(os.path.join(root, f), PROJECT)
                    result.append(rel)
            if len(result) > 200:
                break
        return '\n'.join(sorted(result))
    except Exception as e:
        return f'Error: {e}'

# ── 3. Shell ────────────────────────────────────────────────
@mcp.tool()
def exec_command(cmd: str) -> str:
    """Izvrši shell komandu na serveru."""
    for b in BLOCKED:
        if b in cmd:
            return f'BLOCKED: {b}'
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=60, cwd=PROJECT)
        out = r.stdout[:10000]
        err = r.stderr[:2000]
        return f'[exit {r.returncode}]\n{out}' + (f'\n[stderr]\n{err}' if err else '')
    except subprocess.TimeoutExpired:
        return 'Error: timeout (60s)'
    except Exception as e:
        return f'Error: {e}'

# ── 4. Logovi ───────────────────────────────────────────────
@mcp.tool()
def get_logs(service: str = 'django', lines: int = 50) -> str:
    """Dohvati logove. service: django|nginx|gunicorn|celery"""
    paths = {
        'django':   f'{PROJECT}/logs/django.log',
        'gunicorn': f'{PROJECT}/logs/gunicorn_error.log',
        'celery':   f'{PROJECT}/logs/celery.log',
    }
    if service in paths:
        try:
            r = subprocess.run(['tail', f'-{lines}', paths[service]],
                             capture_output=True, text=True)
            return r.stdout or 'Prazan log'
        except Exception as e:
            return f'Error: {e}'
    elif service == 'nginx':
        r = subprocess.run(['journalctl', '-u', 'nginx', '-n', str(lines), '--no-pager'],
                          capture_output=True, text=True)
        return r.stdout
    return f'Unknown service: {service}'

# ── 5. Live podaci ──────────────────────────────────────────
@mcp.tool()
def system_status() -> str:
    """Server health: disk, memory, servisi, Django check."""
    try:
        disk = subprocess.check_output(['df', '-h', '/'], text=True).split('\n')[1].split()
        mem = subprocess.check_output(['free', '-h'], text=True).split('\n')[1].split()
        services = {}
        for s in ['gunicorn-fina', 'celery-worker', 'nginx']:
            r = subprocess.run(['systemctl', 'is-active', s], capture_output=True, text=True)
            services[s] = r.stdout.strip()
        return json.dumps({
            'disk': {'used': disk[2], 'free': disk[3], 'percent': disk[4]},
            'memory': {'used': mem[2], 'total': mem[1]},
            'services': services,
        }, indent=2)
    except Exception as e:
        return f'Error: {e}'

@mcp.tool()
def pos_today() -> str:
    """POS statistike za danas."""
    from pos.models import POSReceipt
    from django.utils import timezone
    from django.db.models import Sum, Count
    today = timezone.now().date()
    qs = POSReceipt.objects.filter(created_at__date=today, status='paid')
    by_company = list(
        qs.values('session__terminal__company__name')
          .annotate(promet=Sum('total'), bonovi=Count('id'))
          .order_by('-promet')
    )
    return json.dumps({
        'datum': str(today),
        'ukupno_eur': str(qs.aggregate(t=Sum('total'))['t'] or 0),
        'bonovi': qs.count(),
        'po_kompaniji': by_company,
    }, default=str, indent=2)

@mcp.tool()
def active_subscriptions() -> str:
    """Lista aktivnih pretplata s MRR."""
    from registration.models import CompanySubscription
    subs = CompanySubscription.objects.filter(is_active=True).select_related('company').order_by('-monthly_fee')
    result = [{'company': s.company.name, 'plan': s.plan, 'mrr': str(s.monthly_fee)} for s in subs]
    total = sum(float(s.monthly_fee or 0) for s in subs)
    return json.dumps({'mrr_total': total, 'count': len(result), 'subscriptions': result}, indent=2)

@mcp.tool()
def restart_service(service: str) -> str:
    """Restart servisa. service: gunicorn|celery|nginx"""
    allowed = {
        'gunicorn': 'systemctl restart gunicorn-fina',
        'celery': 'systemctl restart celery-worker celery-beat',
        'nginx': 'systemctl restart nginx',
        'all': 'systemctl restart gunicorn-fina celery-worker celery-beat',
    }
    if service not in allowed:
        return f'Unknown service. Options: {list(allowed.keys())}'
    r = subprocess.run(allowed[service], shell=True, capture_output=True, text=True)
    return f'OK: {service} restarted' if r.returncode == 0 else f'Error: {r.stderr}'

# ── Start ────────────────────────────────────────────────────
if __name__ == '__main__':
    mcp.run(transport='sse', host='127.0.0.1', port=8765)
```

## Systemd service: /etc/systemd/system/fenix-mcp.service

```bash
cat > /etc/systemd/system/fenix-mcp.service << 'UNIT'
[Unit]
Description=Fenix MCP Server
After=network.target gunicorn-fina.service

[Service]
User=root
WorkingDirectory=/var/www/fina-connect
ExecStart=/var/www/fina-connect/venv/bin/python core/mcp_server.py
Restart=always
RestartSec=5
Environment=DJANGO_SETTINGS_MODULE=core.settings

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable fenix-mcp
systemctl start fenix-mcp
sleep 2
systemctl is-active fenix-mcp
```

## Nginx proxy: dodaj u limit-connect config

```bash
# U /etc/nginx/sites-enabled/limit-connect
# Unutar server bloka, dodaj:
location /mcp/ {
    proxy_pass http://127.0.0.1:8765/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 300s;
}
```

```bash
nginx -t && systemctl reload nginx
```

## Provjera

```bash
# MCP server radi?
systemctl is-active fenix-mcp

# SSE endpoint dostupan?
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/mcp/

# Test direktno
curl -s http://127.0.0.1:8765/health 2>/dev/null || echo "Provjeri port"
```

## Za Sonnet (Ivan dodaje u claude.ai Settings)

URL: https://limit-connect.com/mcp/

## Javi
- systemctl is-active fenix-mcp
- HTTP status https://limit-connect.com/mcp/
- Broj alata: grep -c "@mcp.tool" core/mcp_server.py
