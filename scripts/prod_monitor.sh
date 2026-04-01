#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# LIMIT Connect — Production monitoring (prvi dan)
# Pokreni: watch -n 300 ./scripts/prod_monitor.sh
# Ili:     while true; do bash scripts/prod_monitor.sh; sleep 300; done
# ═══════════════════════════════════════════════════════════════

DATETIME=$(date '+%d.%m.%Y %H:%M:%S')
echo "═══════════════════════════════════════════════════"
echo "  LIMIT Connect Monitor — $DATETIME"
echo "═══════════════════════════════════════════════════"

# ── Services ──
echo ""
echo "SERVISI:"
for svc in gunicorn-fina celery-worker celery-beat nginx redis-server postgresql; do
    STATUS=$(systemctl is-active $svc 2>/dev/null || echo "not-found")
    if [ "$STATUS" = "active" ]; then
        echo "  ✓ $svc"
    else
        echo "  ✗ $svc — $STATUS"
    fi
done

# ── Resources ──
echo ""
echo "RESURSI:"
MEM=$(free -m | grep Mem | awk '{printf "  RAM: %dMB / %dMB (%.0f%%)\n", $3, $2, $3/$2*100}')
echo "$MEM"
DISK=$(df -h /var/www 2>/dev/null | tail -1 | awk '{print "  Disk: " $3 " / " $2 " (" $5 ")"}')
echo "$DISK"
LOAD=$(cat /proc/loadavg | awk '{print "  Load: " $1 " " $2 " " $3}')
echo "$LOAD"

# ── Database ──
echo ""
echo "BAZA:"
DB_CONN=$(psql -U limitconnect -d fina_erp -c "SELECT count(*) FROM pg_stat_activity WHERE state='active';" -t 2>/dev/null | tr -d ' ' || echo "?")
DB_SIZE=$(psql -U limitconnect -d fina_erp -c "SELECT pg_size_pretty(pg_database_size('fina_erp'));" -t 2>/dev/null | tr -d ' ' || echo "?")
echo "  Aktivnih konekcija: $DB_CONN"
echo "  Velicina baze: $DB_SIZE"

# ── Redis ──
echo ""
echo "REDIS:"
REDIS_HITS=$(redis-cli INFO stats 2>/dev/null | grep "keyspace_hits:" | awk -F: '{print $2}' | tr -d '\r')
REDIS_MISS=$(redis-cli INFO stats 2>/dev/null | grep "keyspace_misses:" | awk -F: '{print $2}' | tr -d '\r')
REDIS_MEM=$(redis-cli INFO memory 2>/dev/null | grep "used_memory_human:" | awk -F: '{print $2}' | tr -d '\r')
if [ -n "$REDIS_HITS" ] && [ -n "$REDIS_MISS" ]; then
    TOTAL=$((REDIS_HITS + REDIS_MISS))
    if [ "$TOTAL" -gt 0 ]; then
        RATE=$((REDIS_HITS * 100 / TOTAL))
        echo "  Hit rate: ${RATE}% ($REDIS_HITS hits / $REDIS_MISS misses)"
    fi
fi
echo "  Memory: ${REDIS_MEM:-?}"

# ── Celery ──
echo ""
echo "CELERY:"
QUEUE_LEN=$(redis-cli LLEN celery 2>/dev/null || echo "?")
echo "  Queue length: $QUEUE_LEN"

# ── Errors (zadnjih 5 min) ──
echo ""
echo "GRESKE (5 min):"
ERR_GUN=$(journalctl -u gunicorn-fina --since "5 minutes ago" 2>/dev/null | grep -ci "ERROR" || echo "0")
ERR_CEL=$(journalctl -u celery-worker --since "5 minutes ago" 2>/dev/null | grep -ci "ERROR" || echo "0")
echo "  Gunicorn: $ERR_GUN"
echo "  Celery: $ERR_CEL"

# ── Response time (quick check) ──
echo ""
echo "RESPONSE TIME:"
RT=$(curl -s -o /dev/null -w "%{time_total}" http://localhost:8000/ 2>/dev/null || echo "?")
echo "  Homepage: ${RT}s"

# ── Alarm ──
TOTAL_ERR=$((ERR_GUN + ERR_CEL))
if [ "$TOTAL_ERR" -gt 5 ]; then
    echo ""
    echo "⚠️  ALARM: $TOTAL_ERR gresaka u zadnjih 5 minuta!"
    # WhatsApp alarm via curl to WAHA
    # curl -s -X POST http://localhost:3000/api/sendText \
    #   -H "Content-Type: application/json" \
    #   -d "{\"chatId\":\"385976091655@c.us\",\"text\":\"PROD ALARM: $TOTAL_ERR errors in 5min\"}" \
    #   > /dev/null 2>&1
fi

echo ""
echo "═══════════════════════════════════════════════════"
