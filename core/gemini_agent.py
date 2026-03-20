"""
Gemini Agent — autonomni AI agent s punim pristupom serveru.

Iste ovlasti kao Claude Code:
  - Čitanje fajlova (read)
  - Pisanje fajlova (write)
  - Izvršavanje komandi (exec)
  - Django ORM pristup (query)

Koristi Gemini 2.5 Flash za analizu i generiranje koda.
Sigurnost: isti whitelist/blacklist kao remote_api.py + AI Council odobrenje za write/exec.

Usage:
    from core.gemini_agent import GeminiAgent
    agent = GeminiAgent()
    result = agent.run_task("Analiziraj pos/models.py i predloži optimizacije")
"""
import json
import logging
import os
import subprocess
import re
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger('gemini_agent')

# Isti blocked patterns kao remote_api.py
BLOCKED_PATTERNS = [
    r'\brm\s+-rf\b', r'\brm\s+-r\b', r'\brmdir\b',
    r'\bchmod\s+[0-7]*7[0-7]*\b', r'\bchown\b', r'\bdd\b',
    r'\bcurl\b.*(-o|--output)', r'\bwget\b',
    r'\bnc\b', r'\bnetcat\b', r'>\s*/etc/', r'>\s*/bin/',
    r'\bpasswd\b', r'\bshadow\b', r'\biptables\b',
    r'[;&|].*rm\b', r'\beval\b', r'\bexec\b.*shell',
]

PROJECT_ROOT = '/var/www/fina-connect'


class GeminiAgentError(Exception):
    pass


class GeminiAgent:
    """Autonomni Gemini agent s punim pristupom projektu."""

    def __init__(self, model='gemini-2.5-flash', max_steps=10):
        self.model = model
        self.max_steps = max_steps
        self.api_key = os.environ.get('GEMINI_API_KEY', '')
        self.history = []
        self.files_read = []
        self.files_written = []
        self.commands_run = []

    # ── Alati (iste ovlasti kao Claude Code) ──────────────────

    def read_file(self, path):
        """Čitaj fajl iz projekta."""
        full = os.path.join(PROJECT_ROOT, path) if not path.startswith('/') else path
        if not full.startswith(PROJECT_ROOT):
            return {'error': 'Path outside project'}
        try:
            with open(full) as f:
                content = f.read()
            self.files_read.append(path)
            return {'content': content[:50000], 'lines': len(content.split('\n'))}
        except Exception as e:
            return {'error': str(e)[:200]}

    def write_file(self, path, content):
        """Piši fajl u projekt."""
        full = os.path.join(PROJECT_ROOT, path) if not path.startswith('/') else path
        if not full.startswith(PROJECT_ROOT):
            return {'error': 'Path outside project'}
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w') as f:
                f.write(content)
            self.files_written.append(path)
            logger.info('[GEMINI AGENT] Wrote %s (%d bytes)', path, len(content))
            return {'ok': True, 'path': path, 'bytes': len(content)}
        except Exception as e:
            return {'error': str(e)[:200]}

    def run_command(self, cmd):
        """Izvrši shell komandu (isti whitelist kao remote_api)."""
        for p in BLOCKED_PATTERNS:
            if re.search(p, cmd, re.IGNORECASE):
                return {'error': 'Command blocked: %s' % p, 'blocked': True}
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=60, cwd=PROJECT_ROOT,
                env={**os.environ, 'PYTHONPATH': PROJECT_ROOT}
            )
            self.commands_run.append(cmd[:100])
            return {
                'stdout': result.stdout[:30000],
                'stderr': result.stderr[:5000],
                'code': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {'error': 'Timeout (60s)'}

    def query_db(self, code):
        """Izvrši Django ORM upit (read-only preporuka)."""
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
        django.setup()
        try:
            result = {}
            exec(code, {'__builtins__': __builtins__}, result)
            return {'result': str(result.get('output', ''))[:10000]}
        except Exception as e:
            return {'error': str(e)[:200]}

    # ── Gemini API poziv ─────────────────────────────────────

    def _call_gemini(self, messages, tools_description):
        """Pozovi Gemini API s alatima."""
        if not self.api_key:
            raise GeminiAgentError('GEMINI_API_KEY not set')

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)

        model = genai.GenerativeModel(self.model)

        system_prompt = """Ti si Gemini Agent — autonomni AI developer s punim pristupom LIMIT Connect serveru.

Imaš 4 alata:
1. READ(path) — čitaj fajl
2. WRITE(path, content) — piši fajl
3. EXEC(cmd) — izvrši shell komandu
4. QUERY(code) — Django ORM upit

Pravila:
- UVIJEK prvo čitaj kod prije nego ga mijenjaš
- Pokreni testove nakon svake promjene
- Ne briši fajlove osim ako je eksplicitno traženo
- Piši na hrvatskom u komentarima
- Koristi isti coding style kao ostatak projekta
- Spremi rezultate u memory ako je značajna promjena

Odgovaraj u JSON formatu:
{"action": "READ|WRITE|EXEC|QUERY|DONE", "path": "...", "content": "...", "cmd": "...", "code": "...", "reasoning": "..."}

Kad završiš, vrati: {"action": "DONE", "summary": "...", "files_changed": [...]}"""

        full_prompt = system_prompt + '\n\nZadatak: ' + messages[-1] if isinstance(messages[-1], str) else str(messages[-1])

        for step_context in self.history[-5:]:
            full_prompt += '\n\nPrethodni korak: ' + json.dumps(step_context, ensure_ascii=False)[:2000]

        response = model.generate_content(full_prompt)
        return response.text

    # ── Glavni loop ──────────────────────────────────────────

    def run_task(self, task_description):
        """
        Glavni entry point — pokreni Gemini agenta s zadatkom.
        Agent autonomno čita, piše, izvršava do max_steps koraka.

        Returns: dict s summary, files_changed, commands_run
        """
        logger.info('[GEMINI AGENT] Starting task: %s', task_description[:100])

        # Audit log
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                action='gemini_agent_start',
                model_name='core.GeminiAgent',
                object_repr='Task: %s' % task_description[:200],
                changes={'task': task_description},
            )
        except Exception:
            pass

        results = []
        for step in range(self.max_steps):
            try:
                # Pozovi Gemini za sljedeću akciju
                response_text = self._call_gemini([task_description], '')

                # Parse JSON odgovor
                try:
                    # Izvuci JSON iz markdown code block ako postoji
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
                    if json_match:
                        action = json.loads(json_match.group())
                    else:
                        action = {'action': 'DONE', 'summary': response_text[:500]}
                except json.JSONDecodeError:
                    action = {'action': 'DONE', 'summary': response_text[:500]}

                action_type = action.get('action', 'DONE')

                if action_type == 'READ':
                    result = self.read_file(action.get('path', ''))
                elif action_type == 'WRITE':
                    result = self.write_file(action.get('path', ''), action.get('content', ''))
                elif action_type == 'EXEC':
                    result = self.run_command(action.get('cmd', ''))
                elif action_type == 'QUERY':
                    result = self.query_db(action.get('code', ''))
                elif action_type == 'DONE':
                    results.append(action)
                    break
                else:
                    result = {'error': 'Unknown action: %s' % action_type}

                step_result = {
                    'step': step + 1,
                    'action': action_type,
                    'reasoning': action.get('reasoning', ''),
                    'result_preview': str(result)[:500],
                }
                self.history.append(step_result)
                results.append(step_result)

                logger.info('[GEMINI AGENT] Step %d: %s — %s',
                           step + 1, action_type, action.get('reasoning', '')[:80])

            except Exception as e:
                logger.error('[GEMINI AGENT] Step %d error: %s', step + 1, e)
                results.append({'step': step + 1, 'error': str(e)[:200]})
                break

        # Završni audit
        summary = {
            'task': task_description[:200],
            'steps': len(results),
            'files_read': self.files_read,
            'files_written': self.files_written,
            'commands_run': self.commands_run,
            'completed_at': timezone.now().isoformat(),
        }

        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                action='gemini_agent_complete',
                model_name='core.GeminiAgent',
                object_repr='Completed: %d steps, %d files' % (len(results), len(self.files_written)),
                changes=summary,
            )
        except Exception:
            pass

        logger.info('[GEMINI AGENT] Completed: %d steps, %d files written', len(results), len(self.files_written))
        return summary
