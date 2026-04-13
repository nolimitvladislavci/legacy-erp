#!/usr/bin/env python
"""Pokreće Gemini za UI Revolution task."""
import os, sys, logging

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')

import django; django.setup()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)

from core.gemini_agent import GeminiAgent

task = open('/var/www/fina-connect/GEMINI_TASK_UI_REVOLUTION.md').read()

print("="*60)
print("GEMINI AGENT — UI REVOLUTION SPRINT 1+2")
print("="*60)

agent = GeminiAgent(max_steps=20)
result = agent.run_task(task)

print("="*60)
print("ZAVRŠENO")
print(f"Fajlovi napisani: {agent.files_written}")
print(f"Komande:          {agent.commands_run}")
print(f"Koraka:           {result.get('steps','?')}")
