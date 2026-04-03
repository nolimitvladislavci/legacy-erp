#!/bin/bash
# =============================================================
# GEMINI WATCH — pratiti Gemini agenta u realnom vremenu
# Korištenje: ./gemini_watch.sh [task_name]
# =============================================================

TASK="${1:-UI_REVOLUTION}"
LOG_FILE="/var/www/fina-connect/gemini_${TASK}.log"
PID_FILE="/var/www/fina-connect/gemini_${TASK}.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

header() {
    clear
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  🤖 GEMINI AGENT — PRAĆENJE U REALNOM VREMENU${NC}"
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════${NC}"
    echo -e "  Task: ${YELLOW}${TASK}${NC}"
    echo -e "  Log:  ${LOG_FILE}"
    echo -e "  Datum: $(date '+%d.%m.%Y %H:%M:%S')"
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════${NC}"
    echo ""
}

# Status ažuriran svake 2 sekunde
watch_loop() {
    while true; do
        header

        # Provjeri je li Gemini aktivan
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo -e "  Status: ${GREEN}● AKTIVAN${NC} (PID: $PID)"
            else
                echo -e "  Status: ${RED}● ZAVRŠEN${NC}"
                rm -f "$PID_FILE"
            fi
        else
            echo -e "  Status: ${YELLOW}● ČEKA / NIJE POKRENUT${NC}"
        fi

        echo ""
        echo -e "${BOLD}─── ZADNJI KORACI ────────────────────────────${NC}"

        # Prikaži zadnjih 25 linija loga
        if [ -f "$LOG_FILE" ]; then
            tail -25 "$LOG_FILE" | while IFS= read -r line; do
                if echo "$line" | grep -q "WRITE"; then
                    echo -e "  ${GREEN}✍  $line${NC}"
                elif echo "$line" | grep -q "EXEC"; then
                    echo -e "  ${YELLOW}⚡ $line${NC}"
                elif echo "$line" | grep -q "READ"; then
                    echo -e "  ${CYAN}👁  $line${NC}"
                elif echo "$line" | grep -q "DONE"; then
                    echo -e "  ${GREEN}${BOLD}✅ $line${NC}"
                elif echo "$line" | grep -q "ERROR\|greška\|Greška\|UPOZORENJE"; then
                    echo -e "  ${RED}❌ $line${NC}"
                elif echo "$line" | grep -q "Korak\|step"; then
                    echo -e "  ${BLUE}→  $line${NC}"
                else
                    echo -e "  $line"
                fi
            done
        else
            echo -e "  ${YELLOW}Čekam pokretanje Gemini agenta...${NC}"
        fi

        echo ""
        echo -e "${BOLD}─── GIT AKTIVNOST ────────────────────────────${NC}"
        cd /var/www/fina-connect && git log --oneline -3 2>/dev/null | while read line; do
            echo -e "  ${GREEN}●${NC} $line"
        done

        echo ""
        echo -e "${BOLD}─── PROMIJENENI FAJLOVI ──────────────────────${NC}"
        cd /var/www/fina-connect && git diff --name-only 2>/dev/null | head -10 | while read f; do
            echo -e "  ${YELLOW}~${NC} $f"
        done

        echo ""
        echo -e "  ${CYAN}[Osvježava se svake 3 sekunde. CTRL+C za izlaz]${NC}"
        sleep 3
    done
}

watch_loop
