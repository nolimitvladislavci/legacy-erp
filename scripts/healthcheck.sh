#!/bin/bash
echo "=== LIMIT Connect Health Check ==="
echo "Date: $(date)"
echo ""
echo "Memory: $(free -h | grep Mem | awk '{print $3"/"$2" used, "$7" available"}')"
echo "Swap:   $(free -h | grep Swap | awk '{print $3"/"$2" used"}')"
echo ""
echo "Services:"
for svc in gunicorn-fina celery-worker celery-beat postgresql redis-server nginx; do
  status=$(systemctl is-active $svc 2>/dev/null || echo "N/A")
  printf "  %-20s %s\n" "$svc" "$status"
done
echo ""
echo "Docker:"
docker ps --format "  {{.Names}}: {{.Status}}" 2>/dev/null || echo "  Docker not running"
echo ""
echo "Disk: $(df -h / | tail -1 | awk '{print $3"/"$2" ("$5" used)"}')"
echo "Load: $(uptime | grep -oP 'load average: .*')"
echo "==================================="
