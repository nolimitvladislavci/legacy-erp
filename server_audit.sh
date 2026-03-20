#!/bin/bash

# Boje za ljepši ispis
GREEN='\033[0;32m'
GOLD='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GOLD}=======================================================${NC}"
echo -e "${GOLD}    VISKOVIĆ GROUP ERP - SERVER & SYSTEM AUDIT         ${NC}"
echo -e "${GOLD}=======================================================${NC}"
echo ""

echo -e "${GREEN}[1] SISTEMSKI RESURSI (OS, CPU, RAM, DISK):${NC}"
echo "-------------------------------------------------------"
uname -snrvm
echo ""
echo "Zauzeće memorije:"
free -h
echo ""
echo "Zauzeće diska (Root):"
df -h /
echo ""

echo -e "${GREEN}[2] STATUS KLJUČNIH SERVISA:${NC}"
echo "-------------------------------------------------------"
for service in nginx postgresql redis supervisor gunicorn; do
    if systemctl is-active --quiet $service; then
        echo -e " [✔] $service je ${GREEN}AKTIVAN${NC}"
    else
        echo -e " [!] $service ${RED}NIJE aktivan${NC} ili ne postoji"
    fi
done
echo ""

echo -e "${GREEN}[3] TEŽINA PROJEKTA (/var/www/fina-connect):${NC}"
echo "-------------------------------------------------------"
du -sh /var/www/fina-connect/* | sort -hr | head -n 10
echo ""

echo -e "${GREEN}[4] DJANGO & PYTHON ZDRAVLJE:${NC}"
echo "-------------------------------------------------------"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    python -V
    echo "Ukupno instaliranih Python paketa: $(pip freeze | wc -l)"
    
    echo "Provjera baze (Neprimijenjene migracije):"
    MIGRATIONS=$(python manage.py showmigrations | grep -v "\[X\]" | grep "\[ \]" | wc -l)
    if [ "$MIGRATIONS" -eq "0" ]; then
        echo -e " [✔] Baza je savršeno ažurna (0 neprimijenjenih migracija)."
    else
        echo -e " [!] Upozorenje: Postoji $MIGRATIONS neprimijenjenih migracija!"
    fi
else
    echo -e "${RED}Virtualno okruženje (venv) nije pronađeno!${NC}"
fi
echo ""

echo -e "${GREEN}[5] ZADNJIH 15 LINIJA SISTEMSKOG LOGA (Supervisor/ERP):${NC}"
echo "-------------------------------------------------------"
journalctl -u fina-connect --no-pager -n 15 || echo "Nema zapisa u journalctl za fina-connect servis."

echo ""
echo -e "${GOLD}=======================================================${NC}"
echo -e "${GOLD}AUDIT ZAVRŠEN.${NC}"
