"""
FENIX MCP Server — direktni pristup za Sonnet
Pokrece se kao: venv/bin/python core/mcp_server.py
"""
import os, sys, subprocess, json
sys.path.insert(0, '/var/www/fina-connect')
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from fastmcp import FastMCP

mcp = FastMCP("Fenix LIMIT Connect")
PROJECT = '/var/www/fina-connect'
BLOCKED = ['rm -rf', 'reboot', 'shutdown', 'mkfs', 'chmod 777', '> /dev/']


@mcp.tool()
def query_db(sql: str) -> str:
    """Izvrsi SQL upit na PostgreSQL bazi."""
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
    """Izvrsi Django ORM kod. Spremi rezultat u varijablu 'output'."""
    try:
        loc = {}
        exec(code, {'__builtins__': __builtins__}, loc)
        return str(loc.get('output', 'OK'))
    except Exception as e:
        return f'Error: {e}'


@mcp.tool()
def read_file(path: str) -> str:
    """Citaj fajl iz projekta."""
    full = os.path.join(PROJECT, path.lstrip('/')) if not path.startswith(PROJECT) else path
    if not full.startswith(PROJECT):
        return 'Error: path outside project'
    try:
        content = open(full).read()
        return f'[{content.count(chr(10))} linija]\n{content[:30000]}'
    except Exception as e:
        return f'Error: {e}'


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Pisi fajl u projekt."""
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
                    result.append(os.path.relpath(os.path.join(root, f), PROJECT))
            if len(result) > 300:
                break
        return '\n'.join(sorted(result))
    except Exception as e:
        return f'Error: {e}'


@mcp.tool()
def exec_command(cmd: str) -> str:
    """Izvrsi shell komandu na serveru."""
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


@mcp.tool()
def get_logs(service: str = 'django', lines: int = 50) -> str:
    """Dohvati logove. service: django|gunicorn|celery|nginx"""
    paths = {
        'django':   f'{PROJECT}/logs/django.log',
        'gunicorn': f'{PROJECT}/logs/gunicorn_error.log',
        'celery':   f'{PROJECT}/logs/celery.log',
    }
    if service in paths:
        try:
            r = subprocess.run(['tail', f'-{lines}', paths[service]], capture_output=True, text=True)
            return r.stdout or 'Prazan log'
        except Exception as e:
            return f'Error: {e}'
    r = subprocess.run(['journalctl', '-u', service, '-n', str(lines), '--no-pager'],
                      capture_output=True, text=True)
    return r.stdout


@mcp.tool()
def system_status() -> str:
    """Server health: disk, memory, servisi."""
    try:
        disk = subprocess.check_output(['df', '-h', '/'], text=True).split('\n')[1].split()
        mem = subprocess.check_output(['free', '-h'], text=True).split('\n')[1].split()
        services = {}
        for s in ['gunicorn-fina', 'celery-worker', 'nginx', 'fenix-mcp']:
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
def restart_service(service: str) -> str:
    """Restart servisa. service: gunicorn|celery|nginx|all"""
    allowed = {
        'gunicorn': 'systemctl restart gunicorn-fina',
        'celery': 'systemctl restart celery-worker celery-beat',
        'nginx': 'systemctl restart nginx',
        'all': 'systemctl restart gunicorn-fina celery-worker celery-beat',
    }
    if service not in allowed:
        return f'Unknown. Options: {list(allowed.keys())}'
    r = subprocess.run(allowed[service], shell=True, capture_output=True, text=True)
    return f'OK: {service} restarted' if r.returncode == 0 else f'Error: {r.stderr}'


if __name__ == '__main__':
    print('Fenix MCP Server na http://127.0.0.1:8765')
    mcp.run(transport='sse', host='127.0.0.1', port=8765)
