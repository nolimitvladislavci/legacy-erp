import logging
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
import django; django.setup()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)

from core.gemini_agent import GeminiAgent

task = open('/var/www/fina-connect/GEMINI_TASK_NOTARIAT2.md').read()

print("=" * 60)
print("GEMINI — NOTARIAT SPRINT 2")
print("=" * 60)

agent = GeminiAgent(max_steps=25)
result = agent.run_task(task)

print("=" * 60)
print("ZAVRSENO")
print("Fajlovi napisani:", agent.files_written)
print("Komande:", len(agent.commands_run))
print("Koraka:", result.get('steps', '?'))
