"""
SONNET AGENT — Vođa projekta LIMIT Connect
Poziva se svaka 2 sata iz Celery beat.
Svaki poziv = nova instanca, ali FENIX_STATUS + git log = kontinuitet.
"""
import logging
import subprocess
import hashlib
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('sonnet_agent')

SONNET_SYSTEM_PROMPT = """Ti si Sonnet — vođa projekta LIMIT Connect ERP platforme.

TVOJA ULOGA I DUŽNOSTI:
1. VOĐA PROJEKTA — koordiniraš Gemini (executor) i Haiku (classifier)
2. ČUVAR ZAKONA — svaka promjena mora biti u skladu s HR/DE/EU propisima
3. LOVAC NA BUGOVE — pronalaziš kritične greške i odmah ih procesuiraš
4. GLASNIK — Ivanu šalješ samo ono što zahtijeva njegovu pažnju (ne zatrpavati)

PRAVILA PONAŠANJA:
- Uvijek govori istinu, nikad ne prešućuj probleme
- Kritični bug (500 greška, pravni rizik, sigurnosni propust) = odmah WhatsApp Ivanu
- Manji napredak = implementiraj sam, commitaj, javi kratko
- Ako trebaš Ivanovu odluku = jasno formuliraj pitanje, max 3 rečenice
- Nikad ne pitaj za odobrenje na tehničke odluke koje Ivan ne može znati

ZAKONSKI OKVIR (nikad ne kršiti):
- HR: Zakon o fiskalizaciji (NN 133/12+), OIB obveza, ZOR radnici
- DE: ArbZG, DSGVO/GDPR, UStG, EÜR
- EU: Uredba 2016/429 (golubarstvo), eRačun UBL 2.1
- ISO 27001 priprema (Konjik d.o.o. — cilj posrednik)

IVANOV DE BROJ: +491723006985
PLATFORMA: limit-connect.com | Server: 37.27.248.86
"""

SONNET_TASK_TEMPLATE = """
## TVOJ ZADATAK — {timestamp}

### Trenutni kontekst (FENIX_STATUS sažetak):
{fenix_status}

### Zadnjih 10 git commitova:
{git_log}

### System test rezultat (zadnji):
{system_test}

### Aktivni Gemini taskovi:
{gemini_tasks}

### Otvoreni bugovi:
{open_bugs}

---

## ŠTO MORAŠ NAPRAVITI (redoslijed):

1. **PROVJERI** — ima li kritičnih bugova (500 greške, pravni rizik, sigurnost)?
   - Ako DA → odmah piši GEMINI_TASK za fix + WhatsApp Ivanu
   - Ako NE → nastavi na korak 2

2. **PROVJERI** — je li Gemini završio neke taskove od zadnjeg poziva?
   - Ako DA → verificiraj da su testovi zeleni, ažuriraj FENIX_STATUS
   - Ako NE → provjeri je li zaglavljen, pokreni ponovo ako treba

3. **IDENTIFICIRAJ** — koji je sljedeći korak koji možeš napraviti BEZ Ivanove odluke?
   - Manji bugfix → napiši GEMINI_TASK i pokreni
   - Novi feature iz plana → napiši GEMINI_TASK i pokreni

4. **JAVI** — pošalji WhatsApp Ivanu SAMO ako:
   - Kritični bug ili pravni rizik
   - Trebaš njegovu odluku (server, certifikat, API key)
   - Značajan napredak (novi modul live, svi testovi zeleni)

## FORMAT ODGOVORA (JSON):
{{
  "status": "ok|warning|critical",
  "pronadjeni_bugovi": ["bug1", "bug2"],
  "napredak": ["commit1", "commit2"],
  "nova_gemini_zaduzenja": ["task1", "task2"],
  "whatsapp_ivan": true/false,
  "whatsapp_poruka": "tekst poruke ili null",
  "sljedeci_korak": "opis"
}}
"""


def get_fenix_status_summary():
    try:
        with open('/var/www/fina-connect/FENIX_STATUS.md') as f:
            content = f.read()
        # Uzmi samo zadnjih 100 linija
        lines = content.split('\n')
        return '\n'.join(lines[-100:])
    except Exception as e:
        return f"Greška čitanja: {e}"


def get_git_log():
    try:
        r = subprocess.run(
            ['git', 'log', '--oneline', '-10'],
            cwd='/var/www/fina-connect',
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip()
    except Exception as e:
        return f"Greška: {e}"


def get_system_test_result():
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('run_system_test', notify='skip', quick=True, stdout=out)
        result = out.getvalue()
        # Uzmi samo summary
        lines = [l for l in result.split('\n') if any(
            k in l for k in ['OK:', 'Kritično:', 'Upozorenja:', 'REPORT']
        )]
        return '\n'.join(lines[:10])
    except Exception as e:
        return f"System test greška: {e}"


def get_active_gemini_tasks():
    try:
        import glob
        tasks = glob.glob('/var/www/fina-connect/GEMINI_TASK_*.md')
        return '\n'.join([t.split('/')[-1] for t in sorted(tasks)])
    except Exception as e:
        return f"Greška: {e}"


def get_open_bugs():
    """Izvuci otvorene bugove iz FENIX_STATUS."""
    try:
        with open('/var/www/fina-connect/FENIX_STATUS.md') as f:
            content = f.read()
        # Nađi OTVORENI PROBLEMI sekciju
        if 'OTVORENI PROBLEMI' in content:
            start = content.index('OTVORENI PROBLEMI')
            section = content[start:start+1000]
            return section[:500]
        return "Nema eksplicitno navedenih bugova u STATUS-u."
    except Exception as e:
        return f"Greška: {e}"


def pozovi_sonnet_api(prompt_text):
    """Pozovi Sonnet API s kontekstom."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model='claude-sonnet-4-5',
            max_tokens=2000,
            system=SONNET_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt_text}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f'Sonnet API greška: {e}')
        return None


def procesiraj_sonnet_odgovor(odgovor_text, poziv_timestamp):
    """Parsiraj JSON odgovor Sonneta i izvrši akcije."""
    import json
    try:
        # Izvuci JSON iz odgovora
        import re
        json_match = re.search(r'\{.*\}', odgovor_text, re.DOTALL)
        if not json_match:
            logger.warning('Sonnet nije vratio JSON odgovor')
            return

        data = json.loads(json_match.group())

        status = data.get('status', 'ok')
        bugovi = data.get('pronadjeni_bugovi', [])
        napredak = data.get('napredak', [])
        novi_taskovi = data.get('nova_gemini_zaduzenja', [])
        whatsapp_ivan = data.get('whatsapp_ivan', False)
        whatsapp_poruka = data.get('whatsapp_poruka', '')
        sljedeci_korak = data.get('sljedeci_korak', '')

        # Log rezultat
        logger.info(f'Sonnet {poziv_timestamp}: status={status}, '
                    f'bugovi={len(bugovi)}, napredak={len(napredak)}, '
                    f'novi_taskovi={len(novi_taskovi)}')

        # Kreiraj nove Gemini taskove ako Sonnet traži
        for task_opis in novi_taskovi:
            if task_opis and len(task_opis) > 20:
                from core.gemini_tasks import run_gemini_task
                result = run_gemini_task.delay(
                    task_description=task_opis,
                    max_steps=40,
                    requested_by=f'Sonnet-auto-{poziv_timestamp}'
                )
                logger.info(f'Pokrenut Gemini task: {result.id}')

        # WhatsApp Ivanu ako Sonnet traži
        if whatsapp_ivan and whatsapp_poruka:
            from core.whatsapp import send_text
            emoji = '🔴' if status == 'critical' else ('🟠' if status == 'warning' else '✅')
            poruka = f"{emoji} SONNET REPORT — {poziv_timestamp}\n\n{whatsapp_poruka}"
            if sljedeci_korak:
                poruka += f"\n\n→ Sljedeći korak: {sljedeci_korak}"
            send_text(phone='+491723006985', message=poruka)
            logger.info('WhatsApp poslan Ivanu')

        # Ažuriraj FENIX_STATUS s rezultatom
        _update_fenix_status(poziv_timestamp, status, bugovi, napredak)

    except json.JSONDecodeError as e:
        logger.error(f'JSON parse greška: {e}\nOdgovor: {odgovor_text[:200]}')
    except Exception as e:
        logger.error(f'Greška procesiranja Sonnet odgovora: {e}')


def _update_fenix_status(timestamp, status, bugovi, napredak):
    """Dodaj kratki zapis u FENIX_STATUS."""
    try:
        entry = f"\n### Sonnet check — {timestamp} | status={status}\n"
        if bugovi:
            entry += f"- Bugovi: {', '.join(bugovi[:3])}\n"
        if napredak:
            entry += f"- Napredak: {', '.join(napredak[:3])}\n"

        with open('/var/www/fina-connect/FENIX_STATUS.md', 'a') as f:
            f.write(entry)
    except Exception as e:
        logger.error(f'FENIX_STATUS update greška: {e}')


def run_sonnet_cycle():
    """Glavni entry point — zove se iz Celery taska svaka 2 sata."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    logger.info(f'🧠 Sonnet cycle start — {timestamp}')

    # Skupi kontekst
    prompt = SONNET_TASK_TEMPLATE.format(
        timestamp=timestamp,
        fenix_status=get_fenix_status_summary(),
        git_log=get_git_log(),
        system_test=get_system_test_result(),
        gemini_tasks=get_active_gemini_tasks(),
        open_bugs=get_open_bugs(),
    )

    # Pozovi Sonnet API
    odgovor = pozovi_sonnet_api(prompt)

    if odgovor:
        procesiraj_sonnet_odgovor(odgovor, timestamp)
        logger.info(f'✅ Sonnet cycle završen — {timestamp}')
    else:
        logger.error(f'❌ Sonnet API nije odgovorio — {timestamp}')
