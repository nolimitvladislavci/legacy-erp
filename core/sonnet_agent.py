"""
SONNET AUTONOMOUS AGENT v2 — BORG Sprint Mode
==============================================
Ivan definira sprint → Sonnet ga razlaže → delegira Geminiju →
verificira rezultate → kreira sljedeće taskove → eskalira SAMO kad mora.

Ivan ne treba biti online. BORG radi sam.

Escalacija SAMO za:
  1. Novac (server, certifikat, API key naknada)
  2. Pravni potpis (T&C, ugovor, zahtjev PU)
  3. Pristupni podatak koji nije na serveru
  4. Kritična greška koja ne može biti automatski popravljena

SVE OSTALO → Sonnet odlučuje i izvršava.
"""
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('sonnet_agent')

IVAN_PHONE = '+4915771998747'

# ── System prompt za Sonneta ──────────────────────────────────────────────────
SONNET_SYSTEM = """Ti si Sonnet — autonomni vođa projekta LIMIT Connect ERP platforme.

MISIJA: BORG na 10/10. Broj 1 u HR i EU.
PLATFORMA: limit-connect.com | Django/Python | PostgreSQL | Redis | Celery

AUTONOMIJA:
- Možeš kreirati, modificirati i brisati kod
- Možeš pokretati Gemini taskove
- Možeš commitati u git
- Možeš restartati servise
- Možeš slati WhatsApp Ivanu

ESKALIRAŠ IVANU SAMO ZA:
1. Novac (server, certifikat, licenca)  
2. Pravni potpis (ugovor, zahtjev)
3. Pristupni podatak koji nije u .env
4. Kritična greška >2h bez rješenja

PRAVILA:
- Uvijek čitaj FENIX_STATUS.md i CLAUDE.md prije odluke
- Uvijek verificiraj da je Gemini stvarno napisao kod (files_written > 0)
- Commitaj nakon svake promjene
- Nikad ne kršiš: HR/DE/EU zakonske okvire, GDPR, fiskalizaciju
- Istina uvijek — nikad ne prešućuješ problem

FORMAT ODGOVORA — uvijek JSON:
{
  "procjena": "opis trenutnog stanja",
  "kritični_problemi": ["..."],
  "napravljeno_od_zadnjeg": ["..."],
  "sljedeći_taskovi": [
    {"naziv": "...", "prioritet": "KRITIČNO|VISOKO|SREDNJE", "opis": "...", "agent": "gemini|direktno"}
  ],
  "eskalacija_ivan": false,
  "eskalacija_razlog": null,
  "whatsapp_ivan": false,
  "whatsapp_poruka": null,
  "sprint_cilj_napredak": "X%"
}
"""

# ── Context builder ───────────────────────────────────────────────────────────
def _get_full_context():
    """Skupi sav kontekst koji Sonnet treba za odluku."""
    ctx = {}

    # FENIX_STATUS — cijeli (ne samo zadnjih 100 linija)
    try:
        with open('/var/www/fina-connect/FENIX_STATUS.md') as f:
            ctx['fenix_status'] = f.read()[-8000:]  # zadnjih 8000 znakova
    except (FileNotFoundError, PermissionError, IOError) as e:
        ctx['fenix_status'] = f'Greška: {e}'

    # CLAUDE.md
    try:
        with open('/var/www/fina-connect/CLAUDE.md') as f:
            ctx['claude_md'] = f.read()[-4000:]
    except (FileNotFoundError, PermissionError, IOError) as e:
        ctx['claude_md'] = f'Greška: {e}'

    # Git log zadnjih 20 commitova
    try:
        r = subprocess.run(['git', 'log', '--oneline', '-20'],
                           cwd='/var/www/fina-connect', capture_output=True, text=True, timeout=10)
        ctx['git_log'] = r.stdout.strip()
    except (ValueError, AttributeError) as e:
        ctx['git_log'] = 'N/A'

    # Git diff --stat (zadnji commit)
    try:
        r = subprocess.run(['git', 'diff', '--stat', 'HEAD~1', 'HEAD'],
                           cwd='/var/www/fina-connect', capture_output=True, text=True, timeout=10)
        ctx['git_last_diff'] = r.stdout.strip()[:2000]
    except (ValueError, AttributeError) as e:
        ctx['git_last_diff'] = 'N/A'

    # System test
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('run_system_test', notify='skip', quick=True, stdout=out)
        lines = [l for l in out.getvalue().split('\n') if any(
            k in l for k in ['OK:', 'Kritično:', 'Upozorenja:', 'REPORT', '✅', '🔴', '🟠']
        )]
        ctx['system_test'] = '\n'.join(lines[:10])
    except ImportError as e:
        ctx['system_test'] = f'Greška: {e}'

    # Aktivni Gemini taskovi i njihovi rezultati
    try:
        import glob
        task_files = glob.glob('/var/www/fina-connect/GEMINI_TASK_*.md') + \
                     glob.glob('/var/www/fina-connect/CC_TASK_*.md')
        ctx['aktivni_taskovi'] = '\n'.join(os.path.basename(f) for f in sorted(task_files))
    except OSError as e:
        ctx['aktivni_taskovi'] = 'N/A'

    # Sprint cilj (ako postoji)
    try:
        with open('/var/www/fina-connect/SPRINT_CILJ.md') as f:
            ctx['sprint_cilj'] = f.read()
    except (FileNotFoundError, PermissionError, IOError) as e:
        ctx['sprint_cilj'] = 'Nema definiranog sprint cilja.'

    # Django check i migracije
    try:
        r = subprocess.run(
            ['/var/www/fina-connect/venv/bin/python', 'manage.py',
             'showmigrations', '--plan'],
            cwd='/var/www/fina-connect', capture_output=True, text=True, timeout=30
        )
        pending = [l for l in r.stdout.split('\n') if '[ ]' in l]
        ctx['pending_migracije'] = f'{len(pending)} neprimijenjenih' if pending else '0 neprimijenjenih'
    except (ValueError, AttributeError) as e:
        ctx['pending_migracije'] = 'N/A'

    # AI health
    try:
        from core.ai_health import run_ai_health_check
        health = run_ai_health_check()
        ctx['ai_health'] = f"{health['ok_count']}/{health['total']} OK | Problemi: {health['problems']}"
    except ImportError as e:
        ctx['ai_health'] = f'Greška: {e}'

    return ctx


def _call_sonnet(context: dict) -> dict:
    """Pozovi Sonnet API s punim kontekstom."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""
## KONTEKST SESIJE — {datetime.now().strftime('%Y-%m-%d %H:%M')}

### Sprint cilj:
{context.get('sprint_cilj', 'Nije definiran')}

### AI Health:
{context.get('ai_health', 'N/A')}

### System test:
{context.get('system_test', 'N/A')}

### Pending migracije:
{context.get('pending_migracije', 'N/A')}

### Git log (zadnjih 20):
{context.get('git_log', 'N/A')}

### Zadnji commit diff:
{context.get('git_last_diff', 'N/A')}

### Aktivni taskovi:
{context.get('aktivni_taskovi', 'N/A')}

### FENIX STATUS (zadnjih 8000 znakova):
{context.get('fenix_status', 'N/A')}

### CLAUDE.md:
{context.get('claude_md', 'N/A')}

---

Na temelju ovog konteksta, donesi odluke i vrati JSON odgovor.
Identificiraj što je napravljeno od zadnjeg ciklusa, što je sljedeće,
koji su kritični problemi i treba li eskalirati Ivanu.
"""
        response = client.messages.create(
            model=getattr(settings, 'CLAUDE_MODEL', 'claude-sonnet-4-5'),
            max_tokens=3000,
            system=SONNET_SYSTEM,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return _parse_response(response.content[0].text)
    except Exception as e:
        logger.error(f'Sonnet API greška: {e}')
        return {'greška': str(e), 'eskalacija_ivan': True,
                'eskalacija_razlog': f'Sonnet API pao: {e}'}


def _parse_response(text: str) -> dict:
    """Parsiraj JSON iz Sonnet odgovora."""
    try:
        text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text.strip(), flags=re.MULTILINE)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'JSON parse greška: {e}')
    return {'procjena': text[:500], 'eskalacija_ivan': False}


def _izvrsi_odluke(odluke: dict, timestamp: str):
    """Izvrši sve što je Sonnet odlučio."""

    # Pokretanje Gemini taskova
    novi_taskovi = odluke.get('sljedeći_taskovi', [])
    for task in novi_taskovi:
        if task.get('agent') == 'gemini' and task.get('opis'):
            try:
                from core.gemini_tasks import run_gemini_task
                r = run_gemini_task.delay(
                    task_description=task['opis'],
                    max_steps=60,
                    requested_by=f'Sonnet-auto-{timestamp}'
                )
                logger.info(f'Pokrenut Gemini task: {task["naziv"]} → {r.id}')
            except ImportError as e:
                logger.error(f'Gemini task greška: {e}')

    # WhatsApp Ivanu
    if odluke.get('whatsapp_ivan') and odluke.get('whatsapp_poruka'):
        try:
            from core.whatsapp import send_text
            eskalacija = odluke.get('eskalacija_ivan', False)
            emoji = '🔴' if eskalacija else '📊'
            napredak = odluke.get('sprint_cilj_napredak', '?')
            poruka = (
                f'{emoji} SONNET REPORT — {timestamp}\n'
                f'Sprint napredak: {napredak}\n\n'
                f'{odluke["whatsapp_poruka"]}'
            )
            if eskalacija and odluke.get('eskalacija_razlog'):
                poruka += f'\n\n⚠️ TREBA TVOJA ODLUKA:\n{odluke["eskalacija_razlog"]}'
            send_text(phone=IVAN_PHONE, message=poruka)
            logger.info('WhatsApp poslan Ivanu')
        except ImportError as e:
            logger.error(f'WhatsApp greška: {e}')

    # Ažuriraj FENIX_STATUS s kratkim zapisom
    try:
        kratki = {
            'timestamp': timestamp,
            'napredak': odluke.get('sprint_cilj_napredak', '?'),
            'kritični': odluke.get('kritični_problemi', []),
            'novi_taskovi': len(novi_taskovi),
        }
        entry = (
            f'\n### Sonnet auto — {timestamp}\n'
            f'- Napredak: {kratki["napredak"]}\n'
            f'- Novi taskovi: {kratki["novi_taskovi"]}\n'
        )
        if kratki['kritični']:
            entry += '- Kritični: ' + ', '.join(kratki['kritični'][:3]) + '\n'
        with open('/var/www/fina-connect/FENIX_STATUS.md', 'a') as f:
            f.write(entry)
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error(f'FENIX_STATUS update greška: {e}')


def run_sonnet_cycle():
    """Glavni entry point — Celery beat svaka 2h."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    logger.info(f'🧠 Sonnet v2 cycle — {timestamp}')

    context = _get_full_context()
    odluke = _call_sonnet(context)
    _izvrsi_odluke(odluke, timestamp)

    logger.info(f'✅ Sonnet cycle završen — napredak: {odluke.get("sprint_cilj_napredak", "?")}')
    return odluke
