"""
AI Infrastruktura Health Check — BORG Čuvar
============================================
Svaki sat provjerava sve AI API ključeve i servise.
Ako nešto pukne — odmah WhatsApp Ivanu + log.
Ako se samo samo oporavi — tiho bilježi.

Trajno rješenje za problem: GEMINI_API_KEY u .env ali ne u settings.
"""
import logging
import os
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('ai_health')

AI_COMPONENTS = [
    'gemini',
    'anthropic_haiku',
    'anthropic_sonnet',
    'waha_whatsapp',
    'celery_worker',
    'celery_beat',
    'redis',
]

# Cache zadnjeg poznatog statusa — da ne spammamo WhatsApp
_last_status = {}


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
        import subprocess
        r = subprocess.run(['systemctl', 'is-active', 'celery-worker'],
                           capture_output=True, text=True, timeout=5)
        worker_ok = r.stdout.strip() == 'active'
        r2 = subprocess.run(['systemctl', 'is-active', 'celery-beat'],
                            capture_output=True, text=True, timeout=5)
        beat_ok = r2.stdout.strip() == 'active'
        if worker_ok and beat_ok:
            return True, 'worker=active, beat=active'
        return False, f'worker={r.stdout.strip()}, beat={r2.stdout.strip()}'
    except Exception as e:
        return False, str(e)[:100]


def check_redis():
    try:
        import redis as redis_lib
        from django.conf import settings
        redis_url = getattr(settings, 'CELERY_BROKER_URL',
                            getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
        r = redis_lib.from_url(redis_url)
        r.ping()
        return True, f'ping OK'
    except Exception as e:
        return False, str(e)[:100]


def reaktiviraj_celery():
    """Pokušaj restart ako Celery nije aktivan."""
    import subprocess
    try:
        subprocess.run(['systemctl', 'restart', 'celery-worker', 'celery-beat'],
                       timeout=30, capture_output=True)
        logger.warning('Celery restartan automatski')
        return True
    except Exception as e:
        logger.error(f'Celery restart greška: {e}')
        return False


def run_ai_health_check():
    """
    Glavna funkcija — poziva se iz Celery beat svaki sat.
    Vraća dict s rezultatima i šalje WhatsApp ako nešto pukne.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    results = {}
    problems = []
    recovered = []

    # --- PROVJERE ---
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
    if ok is False:  # None = namjerno disabled
        problems.append(f'WhatsApp WAHA: {msg}')

    ok, msg = check_celery()
    results['celery'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Celery: {msg}')
        # Automatski restart
        if reaktiviraj_celery():
            recovered.append('Celery — automatski restartan')

    ok, msg = check_redis()
    results['redis'] = {'ok': ok, 'msg': msg}
    if not ok:
        problems.append(f'Redis: {msg}')

    # --- USPOREDI S ZADNJIM STATUSOM ---
    nova_greska = False
    for component, result in results.items():
        prev = _last_status.get(component, {}).get('ok', True)
        curr = result['ok']
        if curr is False and prev is not False:
            nova_greska = True  # degradacija
        elif curr is True and prev is False:
            recovered.append(component)  # oporavak
        _last_status[component] = result

    # --- LOG ---
    ok_count = sum(1 for r in results.values() if r['ok'] is True)
    total = len(results)
    logger.info(f'AI Health: {ok_count}/{total} OK | Problemi: {len(problems)} | Oporavak: {len(recovered)}')

    for p in problems:
        logger.error(f'AI Health PROBLEM: {p}')
    for r in recovered:
        logger.info(f'AI Health OPORAVAK: {r}')

    # --- WHATSAPP IVAN --- samo kod novih grešaka ili oporavka
    if nova_greska or recovered:
        try:
            from core.whatsapp import send_text
            if nova_greska:
                emoji = '🔴'
                naslov = 'AI INFRASTRUKTURA PROBLEM'
                detalji = '\n'.join(f'  • {p}' for p in problems)
            else:
                emoji = '✅'
                naslov = 'AI INFRASTRUKTURA OPORAVAK'
                detalji = '\n'.join(f'  • {r}' for r in recovered)

            poruka = (
                f'{emoji} {naslov}\n'
                f'⏰ {timestamp}\n\n'
                f'{detalji}\n\n'
                f'Status: {ok_count}/{total} komponenti OK\n'
                f'https://limit-connect.com/superadmin/ai/'
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
