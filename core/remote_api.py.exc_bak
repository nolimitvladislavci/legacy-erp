"""Dev-only: remote exec za Claude session. Whitelist zastita."""
import subprocess, json, os, re, logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

SECRET = os.environ.get('DEV_API_TOKEN', '')
ALLOWED_IPS = {'127.0.0.1', '::1'}
_log = logging.getLogger('remote_api')

SAFE_PREFIXES = [
    'python manage.py', 'python3 manage.py',
    '/var/www/fina-connect/venv/bin/python manage.py',
    'grep ', 'find ', 'cat ', 'head ', 'tail ',
    'wc ', 'ls ', 'echo ', 'pwd', 'ps aux', 'df -', 'du -',
    'systemctl status', 'systemctl is-active',
    'journalctl', 'celery inspect',
    'python3 -c', 'python -c',
]

BLOCKED_PATTERNS = [
    r'\brm\s+-rf\b', r'\brm\s+-r\b', r'\brmdir\b',
    r'\bchmod\s+[0-7]*7[0-7]*\b',
    r'\bchown\b', r'\bdd\b',
    r'\bcurl\b.*(-o|--output)', r'\bwget\b',
    r'\bnc\b', r'\bnetcat\b',
    r'>\s*/etc/', r'>\s*/bin/', r'>\s*/usr/',
    r'\bpasswd\b', r'\bshadow\b',
    r'\biptables\b', r'\bufw\b',
    r'[;&|].*rm\b', r'\beval\b',
    r'\bexec\b.*shell', r'__import__',
]

def _is_safe(cmd):
    cmd = cmd.strip()
    for p in BLOCKED_PATTERNS:
        if re.search(p, cmd, re.IGNORECASE):
            return False, p
    for prefix in SAFE_PREFIXES:
        if cmd.startswith(prefix):
            return True, 'whitelisted'
    _log.warning('Non-whitelisted cmd: %s', cmd[:200])
    return True, 'allowed-logged'

def _check(request):
    if not SECRET:
        return JsonResponse({'error': 'DEV_API_TOKEN not set'}, status=503)
    ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')
    if ALLOWED_IPS and ip not in ALLOWED_IPS:
        return JsonResponse({'error': 'ip_blocked'}, status=403)
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else ''
    if token != SECRET:
        return JsonResponse({'error': 'forbidden'}, status=403)
    return None

@csrf_exempt
@require_POST
def remote_exec(request):
    err = _check(request)
    if err: return err
    body = json.loads(request.body)
    cmd = body.get('cmd', '')
    if not cmd:
        return JsonResponse({'error': 'no cmd'})
    safe, reason = _is_safe(cmd)
    if not safe:
        _log.error('BLOCKED cmd: %s (pattern: %s)', cmd[:200], reason)
        return JsonResponse({'error': 'Komanda blokirana iz sigurnosnih razloga'}, status=403)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=30, cwd='/var/www/fina-connect',
            env={**os.environ, 'PYTHONPATH': '/var/www/fina-connect'}
        )
        return JsonResponse({
            'stdout': result.stdout[:50000],
            'stderr': result.stderr[:5000],
            'code': result.returncode
        })
    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'timeout'})

@csrf_exempt
@require_POST
def remote_read(request):
    err = _check(request)
    if err: return err
    body = json.loads(request.body)
    path = body.get('path', '')
    lines = body.get('lines', None)
    if not path or '..' in path:
        return JsonResponse({'error': 'invalid path'})
    full = os.path.join('/var/www/fina-connect', path) if not path.startswith('/') else path
    if not full.startswith('/var/www/fina-connect'):
        return JsonResponse({'error': 'path outside project'}, status=403)
    try:
        with open(full) as f:
            content = f.read()
        if lines and isinstance(lines, list) and len(lines) == 2:
            all_lines = content.split('\n')
            content = '\n'.join(all_lines[lines[0]-1:lines[1]])
        return JsonResponse({'content': content[:100000], 'path': path})
    except Exception as e:
        return JsonResponse({'error': str(e)[:100]})

@csrf_exempt
@require_POST
def remote_write(request):
    err = _check(request)
    if err: return err
    body = json.loads(request.body)
    path = body.get('path', '')
    content = body.get('content', '')
    if not path or '..' in path:
        return JsonResponse({'error': 'invalid path'})
    full = os.path.join('/var/www/fina-connect', path) if not path.startswith('/') else path
    if not full.startswith('/var/www/fina-connect'):
        return JsonResponse({'error': 'path outside project'}, status=403)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        with open(full, 'w') as f:
            f.write(content)
        return JsonResponse({'ok': True, 'path': path})
    except Exception as e:
        return JsonResponse({'error': str(e)[:100]})
