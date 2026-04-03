#!/bin/bash
# =============================================================
# GEMINI RUN — pokreni Gemini agenta za task
# Korištenje: ./gemini_run.sh UI_REVOLUTION
#             ./gemini_run.sh UI_REVOLUTION 20   (max 20 koraka)
# =============================================================

TASK="${1:-UI_REVOLUTION}"
MAX_STEPS="${2:-25}"
TASK_FILE="/var/www/fina-connect/GEMINI_TASK_${TASK}.md"
LOG_FILE="/var/www/fina-connect/gemini_${TASK}.log"
PID_FILE="/var/www/fina-connect/gemini_${TASK}.pid"

# Provjeri task fajl
if [ ! -f "$TASK_FILE" ]; then
    echo "❌ Task fajl ne postoji: $TASK_FILE"
    echo "   Dostupni taskovi:"
    ls /var/www/fina-connect/GEMINI_TASK_*.md | xargs -I{} basename {} .md | sed 's/GEMINI_TASK_/  → /'
    exit 1
fi

# Provjeri je li već aktivan
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "⚠️  Gemini već radi za task $TASK (PID: $PID)"
        echo "   Prati ga: ./gemini_watch.sh $TASK"
        exit 1
    fi
fi

echo "🚀 Pokrećem Gemini za task: $TASK"
echo "   Task fajl: $TASK_FILE"
echo "   Log: $LOG_FILE"
echo "   Max koraka: $MAX_STEPS"
echo ""

# Pročitaj task iz fajla
TASK_DESC=$(cat "$TASK_FILE")

# Pokreni Django management command u pozadini
nohup /var/www/fina-connect/venv/bin/python /var/www/fina-connect/manage.py shell << PYEOF > "$LOG_FILE" 2>&1 &
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from core.gemini_agent import GeminiAgent

task_desc = """${TASK_DESC}"""

agent = GeminiAgent(max_steps=${MAX_STEPS})
print(f"[START] Gemini agent pokrenut za task: ${TASK}")
print(f"[INFO] Max koraka: ${MAX_STEPS}")
print("="*60)

try:
    result = agent.run_task(task_desc)
    print("="*60)
    print(f"[DONE] Task završen")
    print(f"[STATS] Fajlovi pročitani: {len(agent.files_read)}")
    print(f"[STATS] Fajlovi napisani: {len(agent.files_written)}")
    print(f"[STATS] Komande pokrenute: {len(agent.commands_run)}")
    print(f"[STATS] Koraka ukupno: {result.get('steps', '?')}")
    if agent.files_written:
        print(f"[FILES] Napisano: {', '.join(agent.files_written)}")
except Exception as e:
    print(f"[ERROR] Greška: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo $! > "$PID_FILE"
echo "✅ Gemini pokrenut (PID: $(cat $PID_FILE))"
echo ""
echo "📺 Prati progres:"
echo "   ./gemini_watch.sh $TASK"
echo ""
echo "📋 Ili direktno:"
echo "   tail -f $LOG_FILE"
