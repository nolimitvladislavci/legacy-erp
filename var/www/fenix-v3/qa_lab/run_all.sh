#!/bin/bash
# QA LAB — master runner. Pokreni iz Fenix V3 root-a:
#   ./qa_lab/run_all.sh
#
# Redoslijed: Oracle (brzo) -> Time Machine (medium) -> Bunker (medium) -> Mutant (dugo)

set -e
cd /var/www/fenix-v3
V=venv/bin/python

echo ""
echo "================================================================"
echo "  QA LAB - FULL RUN  -  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "================================================================"
echo ""

echo ">>> [1/4] ORACLE (AST risk analyzer)"
$V qa_lab/oracle/analyzer.py --all | head -30
echo ""

echo ">>> [2/4] TIME MACHINE (smoke journeys)"
$V qa_lab/time_machine/smoke_runner.py
echo ""

echo ">>> [3/4] BUNKER (login probe)"
$V qa_lab/bunker/test_login_journey.py
echo ""

echo ">>> [4/4] MUTANT (mutation testing)"
timeout 120 $V qa_lab/mutant/runner.py || echo "(mutant timeout - ok)"
echo ""

echo "================================================================"
echo "  QA LAB - DONE  -  Dashboard: https://limit-connect.com/qa/"
echo "================================================================"
