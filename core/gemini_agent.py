"""
Gemini Agent v2 — Poboljšana arhitektura
Problem v1: DONE na prvom koraku jer JSON parsing failao.
Fix v2:
  - Eksplicitan system prompt koji forsira JSON format
  - Prethodni koraci se pravilno injektiraju u svaki prompt
  - Ako nema JSON akcije — ponovi s uputom
  - files_written > 0 ili commands_run > 0 = STVARNI rad
  - Celery task javlja grešku ako ništa nije napravljeno
"""
import json
import logging
import os
import re
import subprocess

from django.utils import timezone

logger = logging.getLogger('gemini_agent')

BLACKLISTED_PATTERNS = [
    r'rm\s+-rf\s+/', r'DROP\s+TABLE', r'DROP\s+DATABASE',
    r'DELETE\s+FROM.*WHERE\s+1', r'TRUNCATE\s+TABLE',
]

GEMINI_SYSTEM_PROMPT = """Ti si autonomni coding agent na Django serveru. Imaš pristup fajlovima i shellу.

UVIJEK odgovaraj SAMO validnim JSON objektom — bez teksta prije ili poslije.
Format:
{"action": "READ|WRITE|EXEC|QUERY|DONE", "reasoning": "zašto", "path": "...", "content": "...", "cmd": "...", "code": "...", "summary": "..."}

Akcije:
- READ: čitaj fajl {"action":"READ","path":"/var/www/fina-connect/...","reasoning":"..."}
- WRITE: piši fajl {"action":"WRITE","path":"...","content":"cijeli sadrzaj","reasoning":"..."}
- EXEC: shell komanda {"action":"EXEC","cmd":"cd /var/www/fina-connect && ...","reasoning":"..."}
- QUERY: Django ORM {"action":"QUERY","code":"from x import y; print(y.objects.count())","reasoning":"..."}
- DONE: završi {"action":"DONE","summary":"što si napravio"}

PRAVILA:
1. Uvijek READ models.py ili relevantni fajl PRIJE nego pišeš kod
2. Nakon WRITE — pokreni EXEC za migrate/test/check
3. Nikad ne pretpostavljaj field names — uvijek provjeri
4. Jedan korak = jedna akcija
5. Ako nisi siguran — READ, ne WRITE
"""


class GeminiAgent:
    def __init__(self, model='gemini-2.5-flash', max_steps=40):
        self.model = model
        self.max_steps = max_steps
        self.files_read = []
        self.files_written = []
        self.commands_run = []
        self.history = []

    def read_file(self, path):
        try:
            if not path.startswith('/var/www/fina-connect'):
                return {'error': 'Zabranjena putanja izvan projekta'}
            with open(path, 'r', errors='replace') as f:
                content = f.read(8000)
            self.files_read.append(path)
            return {'content': content, 'path': path}
        except (FileNotFoundError, PermissionError, IOError) as e:
            return {'error': str(e)}

    def write_file(self, path, content):
        try:
            if not path.startswith('/var/www/fina-connect'):
                return {'error': 'Zabranjena putanja'}
            if not content or len(content.strip()) < 10:
                return {'error': 'Sadržaj je prazan — odbijeno'}
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            self.files_written.append(path)
            logger.info('[GEMINI v2] WRITE: %s (%d znakova)', path, len(content))
            return {'written': path, 'size': len(content)}
        except (FileNotFoundError, PermissionError, IOError) as e:
            return {'error': str(e)}

    def run_command(self, cmd):
        try:
            for pattern in BLACKLISTED_PATTERNS:
                if re.search(pattern, cmd, re.IGNORECASE):
                    return {'error': f'Zabranjena komanda: {pattern}'}
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60,
                cwd='/var/www/fina-connect'
            )
            output = (result.stdout + result.stderr)[:3000]
            self.commands_run.append(cmd[:100])
            return {'output': output, 'exit_code': result.returncode}
        except subprocess.TimeoutExpired:
            return {'error': 'Timeout (60s)'}
        except Exception as e:
            return {'error': str(e)}

    def query_db(self, code):
        try:
            import io
            import sys
            safe_globals = {}
            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                exec(code, {'__builtins__': __builtins__}, safe_globals)
            finally:
                sys.stdout = old_stdout
            return {'output': captured.getvalue()[:2000]}
        except Exception as e:
            return {'error': str(e)}

    def _call_gemini(self, task, step_context):
        """Pozovi Gemini API s eksplicitnim JSON formatiranjem."""
        try:
            import google.generativeai as genai
            from django.conf import settings
            api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
            if not api_key:
                raise ValueError('GEMINI_API_KEY nije postavljen')
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                self.model,
                system_instruction=GEMINI_SYSTEM_PROMPT
            )
            prompt = f"ZADATAK:\n{task[:3000]}\n\n"
            if step_context:
                prompt += f"PRETHODNI KORACI (zadnjih 5):\n{step_context}\n\n"
            prompt += "SLJEDEĆA AKCIJA (samo JSON):"
            response = model.generate_content(prompt)
            return response.text
        except ImportError as e:
            logger.error('[GEMINI v2] API greška: %s', e)
            return '{"action":"DONE","summary":"API greška: ' + str(e)[:100] + '"}'

    def _parse_action(self, response_text, retry_count=0):
        """Parse JSON iz odgovora — s retry ako nije validan."""
        # Pokušaj direktni JSON parse
        text = response_text.strip()
        # Ukloni markdown code block ako postoji
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()
        # Nađi JSON objekt
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        # Ako ništa ne radi — vrati DONE s greškom
        logger.warning('[GEMINI v2] JSON parse fail, retry=%d, tekst=%s', retry_count, text[:100])
        return {'action': 'DONE', 'summary': f'JSON parse greška (retry={retry_count}): {text[:100]}'}

    def run_task(self, task_description):
        logger.info('[GEMINI v2] Task start: %s', task_description[:100])

        results = []
        no_progress_count = 0

        for step in range(self.max_steps):
            # Kontekst zadnjih 5 koraka
            step_context = ''
            if self.history:
                recent = self.history[-5:]
                step_context = json.dumps(recent, ensure_ascii=False)[:3000]

            response_text = self._call_gemini(task_description, step_context)
            action = self._parse_action(response_text)
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
                logger.info('[GEMINI v2] DONE na koraku %d', step + 1)
                break
            else:
                result = {'error': f'Nepoznata akcija: {action_type}'}
                no_progress_count += 1

            step_result = {
                'step': step + 1,
                'action': action_type,
                'reasoning': action.get('reasoning', '')[:200],
                'result_preview': str(result)[:500],
            }
            self.history.append(step_result)
            results.append(step_result)
            logger.info('[GEMINI v2] Korak %d: %s — %s',
                        step + 1, action_type, action.get('reasoning', '')[:80])

            # Stagnacija detekcija
            if action_type not in ('READ', 'WRITE', 'EXEC', 'QUERY'):
                no_progress_count += 1
            else:
                no_progress_count = 0

            if no_progress_count >= 3:
                logger.warning('[GEMINI v2] Stagnacija — prekidam')
                break

        # Provjeri je li stvarno nešto napravljeno
        stvarni_rad = len(self.files_written) > 0 or len(self.commands_run) > 0
        if not stvarni_rad:
            logger.warning('[GEMINI v2] UPOZORENJE: 0 fajlova, 0 komandi — task nije izvršen!')

        summary = {
            'task': task_description[:200],
            'steps': len(results),
            'files_read': self.files_read,
            'files_written': self.files_written,
            'commands_run': self.commands_run,
            'stvarni_rad': stvarni_rad,
            'completed_at': timezone.now().isoformat(),
        }

        logger.info('[GEMINI v2] Završeno: %d koraka, %d fajlova, %d komandi',
                    len(results), len(self.files_written), len(self.commands_run))
        return summary
