"""
AI Infrastruktura Health Check — BORG Čuvar
============================================
Svaki sat provjerava sve AI API ključeve i servise.
Ako nešto pukne — odmah WhatsApp Ivanu + log.
Ako se samo oporavi — tiho bilježi.

v2 — 2026-03-29: Dodan check_gunicorn() s auto-kill zombie procesa (port 8000).
     Uzrok incidenta: gunicorn zombie držao port, systemd pokazivao "active",
     health check nije vidio problem → Ivan 2 sata nije mogao logirati.
"""
import logging
import os
import subprocess
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('ai_health')

AI_COMPONENTS = [
    'gunicorn',
    'gemini',
    'anthropic_haiku',
    'anthropic_sonnet',
    'waha_whatsapp',
    'celery_worker',
    'celery_beat',
    'redis',
]

_last_status = {}


# ─── GUNICORN CHECK + AUTO-FIX ───────────────────────────────────────────────

def check_gunicorn():
    """
    Provjera gunicorna na 3 razine:
    1. systemd status (surface check)
    2. TCP port 8000 stvarno odgovara (duboki check)
    3. HTTP /health/ vraća 200

    Ako port blokiran zombie procesom → kill + restart automatski.
    """
    import socket
    import requests as req

    # 1. systemd status
    r = subprocess.run(
        ['systemctl', 'is-active', 'gunicorn-fina'],
        capture_output=True, text=True, timeout=5
    )
    systemd_status = r.stdout.strip()

    # 2. Port 8000 stvarno sluša?
    port_open = False
    try:
        with socket.create_connection(('127.0.0.1', 8000), timeout=3):
            port_open = True
    except (ConnectionRefusedError, TimeoutError, OSError):
        port_open = False

    # 3. HTTP check
    http_ok = False
    http_code = None
    try:
        resp = req.get('http://127.0.0.1:8000/health/', timeout=5)
        http_code = resp.status_code
        http_ok = (http_code == 200)
    except Exception:
        http_ok = False

    # ─── DIJAGNOZA ─────────────────────────────────────────────────────────────

    # SLUČAJ 1: sve OK
    if systemd_status == 'active' and port_open and http_ok:
        return True, f'OK (systemd=active, port=open, HTTP=200)'

    # SLUČAJ 2: PORT ZAUZET — zombie proces (Ivan-incident)
    # systemd kaže "active" (restart loop), ali novi gunicorn ne može vezati port
    if systemd_status in ('active', 'activating') and not http_ok:
        logger.error('Gunicorn zombie detektiran — port 8000 zauzet, HTTP ne odgovara. Pokrećem auto-fix.')
        killed = _kill_zombie_port_8000()
        if killed:
            restarted = _restart_gunicorn()
            if restarted:
                return True, 'AUTOFIX: zombie ubijen, gunicorn restartan OK'
            return False, 'AUTOFIX: zombie ubijen, ali restart nije uspio'
        return False, f'Port 8000 blokiran, kill nije uspio (systemd={systemd_status})'

    # SLUČAJ 3: gunicorn potpuno pao
    if systemd_status != 'active':
        logger.error(f'Gunicorn systemd status: {systemd_status}. Pokušavam restart.')
        restarted = _restart_gunicorn()
        return restarted, f'{"AUTOFIX restart OK" if restarted else "Restart NIJE uspio"} (bio: {systemd_status})'

    # SLUČAJ 4: port otvoren ali HTTP ne odgovara (crash u workerima)
    if port_open and not http_ok:
        logger.error(f'Gunicorn port otvoren ali HTTP {http_code}. Pokušavam graceful reload.')
        _graceful_reload_gunicorn()
        return False, f'Workers ne odgovaraju (HTTP={http_code}), reload poslan'

    return False, f'Nepoznato stanje: systemd={systemd_status}, port={port_open}, http={http_ok}'


def _kill_zombie_port_8000():
    """Ubija sve procese koji drže port 8000."""
    try:
        # fuser: ubija sve koji slušaju na 8000/tcp
        r = subprocess.run(
            ['fuser', '-k', '8000/tcp'],
            capture_output=True, text=True, timeout=10
        )
        logger.warning(f'fuser -k 8000/tcp: {r.returncode} | {r.stdout} {r.stderr}')
        # Daj OS-u sekundu da oslobodi port
        import time
        time.sleep(2)
        return True
    except Exception as e:
        logger.error(f'_kill_zombie_port_8000 greška: {e}')
        # Fallback: nađi PID ručno i ubij
        try:
            r2 = subprocess.run(
                ['ss', '-tlnp', 'sport', '=', ':8000'],
                capture_output=True, text=True, timeout=5
            )
            # Parse PID iz ss outputa
            import re
            pids = re.findall(r'pid=(\d+)', r2.stdout)
            for pid in pids:
                subprocess.run(['kill', '-9', pid], timeout=5)
                logger.warning(f'Ubijen PID {pid} koji je držao port 8000')
            import time
            time.sleep(2)
            return bool(pids)
        except Exception as e2:
            logger.error(f'Fallback kill greška: {e2}')
            return False


def _restart_gunicorn():
    """Restarta gunicorn-fina systemd servis."""
    try:
        r = subprocess.run(
            ['systemctl', 'restart', 'gunicorn-fina'],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            import time
            time.sleep(3)
            logger.info('Gunicorn uspješno restartan')
            return True
        logger.error(f'Gunicorn restart greška: {r.stderr}')
        return False
    except Exception as e:
        logger.error(f'_restart_gunicorn iznimka: {e}')
        return False


def _graceful_reload_gunicorn():
    """Šalje HUP signal gunicornu — graceful reload bez downtime."""
    try:
        subprocess.run(
            ['systemctl', 'reload', 'gunicorn-fina'],
            capture_output=True, text=True, timeout=10
        )
        logger.info('Gunicorn graceful reload poslan')
    except Exception as e:
        logger.error(f'_graceful_reload_gunicorn greška: {e}')


# ─── OSTALI CHECKOVI (nepromijenjeni) ────────────────────────────────────────

def check_gemini():
    try:
        key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
        if not key:
            return False, 'GEMINI_API_KEY nije postavljen u settings'
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        r = model.generate_content('OK', generation_config={'max_output_tokens': 5})
        return True, f'OK ({r.text.strip()[:20]})'
    except Exception as e:
        return False, str(e)[:150]


def check_anthropic(model_key='claude-haiku-4-5-20251001'):
    try:
        key = getattr(settings, 'ANTHROPIC_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            return False, 'ANTHROPIC_API_KEY nije postavljen'
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.create(
            model=model_key, max_tokens=5,
            messages=[{'role': 'user', 'content': 'OK'}]
        )
        return True, f'OK ({r.content[0].text.strip()[:20]})'
    except Exception as e:
        return False, str(e)[:150]


def check_waha():
    try:
        if not getattr(settings, 'WAHA_ENABLED', False):
            return None, 'WAHA_ENABLED=False (namjerno)'
        import requests
        url = f"{getattr(settings, 'WAHA_API_URL', 'http://127.0.0.1:3000')}/api/sessions"
        headers = {'X-Api-Key': getattr(settings, 'WAHA_API_KEY', '')}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            sessions = r.json()
            active = [s for s in sessions if s.get('status') == 'WORKING']
            return True, f'{len(active)} aktivnih sesija'
        return False, f'HTTP {r.status_code}'
    except Exception as e:
        return False, str(e)[:100]


def check_celery():
    try:
        r = subprocess.run(
            ['systemctl', 'is-active', 'celery-worker'],
            capture_output=True, text=True, timeout=5
        )
        worker_ok = r.stdout.strip() == 'active'
        r2 = subprocess.run(
            ['systemctl', 'is-active', 'celery-beat'],
            capture_output=True, text=True, timeout=5
        )
        beat_ok = r2.stdout.strip() == 'active'
        if worker_ok and beat_ok:
            return True, 'worker=active, beat=active'
        return False, f'worker={r.stdout.strip()}, beat={r2.stdout.strip()}'
    except Exception as e:
        return False, str(e)[:100]


def reaktiviraj_celery():
    try:
        subprocess.run(
            ['systemctl', 'restart', 'celery-worker', 'celery-beat'],
            timeout=30, capture_output=True
        )
        logger.warning('Celery restartan automatski')
        return True
    except Exception as e:
        logger.error(f'Celery restart greška: {e}')
        return False


def check_redis():
    try:
        import redis as redis_lib
        redis_url = getattr(
            settings, 'CELERY_BROKER_URL',
            getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        )
        r = redis_lib.from_url(redis_url)
        r.ping()
        return True, 'ping OK'
    except Exception as e:
        return False, str(e)[:100]


# ─── GLAVNI CHECK ─────────────────────────────────────────────────────────────

def run_ai_health_check():
    """
    Glavna funkcija — poziva se iz Celery beat svaki sat u :15.
    Sad uključuje gunicorn deep check s auto-fix zombie procesa.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    results = {}
    problems = []
    recovered = []

    # ── GUNICORN (kritični — prvi) ──────────────────────────────────────────
    ok, msg = check_gunicorn()
    results['gunicorn'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Gunicorn: {msg}')
    elif 'AUTOFIX' in msg:
        recovered.append(f'Gunicorn: {msg}')

    # ── AI API ──────────────────────────────────────────────────────────────
    ok, msg = check_gemini()
    results['gemini'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Gemini: {msg}')

    ok, msg = check_anthropic('claude-haiku-4-5-20251001')
    results['haiku'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Haiku: {msg}')

    ok, msg = check_anthropic(getattr(settings, 'CLAUDE_MODEL', 'claude-sonnet-4-5'))
    results['sonnet'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Sonnet: {msg}')

    ok, msg = check_waha()
    results['waha'] = {'ok': ok, 'msg': msg}
    if ok is False:
        problems.append(f'WhatsApp WAHA: {msg}')

    # ── CELERY ──────────────────────────────────────────────────────────────
    ok, msg = check_celery()
    results['celery'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Celery: {msg}')
        if reaktiviraj_celery():
            recovered.append('Celery — automatski restartan')

    # ── REDIS ───────────────────────────────────────────────────────────────
    ok, msg = check_redis()
    results['redis'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Redis: {msg}')

    # ── USPOREDI SA ZADNJIM STATUSOM ────────────────────────────────────────
    nova_greska = False
    for component, result in results.items():
        prev = _last_status.get(component, {}).get('ok', True)
        curr = result['ok']
        if curr is False and prev is not False:
            nova_greska = True
        elif curr is True and prev is False:
            if component not in [r.split(':')[0].lower() for r in recovered]:
                recovered.append(component)
        _last_status[component] = result

    # ── LOG ─────────────────────────────────────────────────────────────────
    ok_count = sum(1 for r in results.values() if r['ok'] is True)
    total = len(results)
    logger.info(
        f'AI Health v2: {ok_count}/{total} OK | '
        f'Problemi: {len(problems)} | Oporavak: {len(recovered)}'
    )
    for p in problems:
        logger.error(f'AI Health PROBLEM: {p}')
    for r in recovered:
        logger.info(f'AI Health OPORAVAK: {r}')

    # ── WHATSAPP IVAN ───────────────────────────────────────────────────────
    if nova_greska or recovered:
        try:
            from core.whatsapp import send_text
            if nova_greska:
                emoji = '🔴'
                naslov = 'BORG PROBLEM — AUTOMATSKA INTERVENCIJA'
                detalji = '\n'.join(f'  • {p}' for p in problems)
                if recovered:
                    detalji += '\n\n✅ Automatski riješeno:\n'
                    detalji += '\n'.join(f'  • {r}' for r in recovered)
            else:
                emoji = '✅'
                naslov = 'BORG OPORAVAK'
                detalji = '\n'.join(f'  • {r}' for r in recovered)

            poruka = (
                f'{emoji} *{naslov}*\n'
                f'⏰ {timestamp}\n\n'
                f'{detalji}\n\n'
                f'Status: {ok_count}/{total} komponenti OK\n'
                f'limit-connect.com/superadmin/ai/'
            )
            send_text(phone='+4915771998747', message=poruka)
        except Exception as e:
            logger.error(f'WhatsApp AI health alert greška: {e}')

    return {
        'timestamp': timestamp,
        'ok_count': ok_count,
        'total': total,
        'problems': problems,
        'recovered': recovered,
        'results': results,
    }
