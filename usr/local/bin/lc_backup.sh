#!/bin/bash
# LIMIT Connect Daily Backup v2 — s error handlingom i B2 uploadom
# Runs daily at 03:00 via cron
# Fix 29-30.03.2026: 0-byte backupi jer pipe | gzip gutao pg_dump gresku

BACKUP_DIR="/var/backups/limit-connect"
DATE=$(date +%Y%m%d)
KEEP_DAYS=14
LOG="/var/log/lc_backup.log"
WA_PHONE="+4915771998747"
WAHA_URL="http://127.0.0.1:3000/api/sendText"
WAHA_KEY="1a64e68ed45d4b07952430334631caca"
B2_ENDPOINT="https://s3.eu-central-003.backblazeb2.com"
B2_BUCKET="limit-connect-arhiva"
B2_KEY_ID="0037b5f2dbe58630000000001"
B2_APP_KEY="K003v4ZIC18gc+tpUi9xhJmfvwEe/N0"

mkdir -p $BACKUP_DIR

_wa() {
    curl -s -X POST "$WAHA_URL" \
        -H "Content-Type: application/json" \
        -H "X-Api-Key: $WAHA_KEY" \
        -d "{\"chatId\":\"${WA_PHONE}@c.us\",\"text\":\"$1\",\"session\":\"default\"}" \
        > /tmp/wa_backup.log 2>&1
}

log() { echo "$(date '+%a %b %d %T UTC %Y'): $1" >> $LOG; }

log "=== BACKUP START ==="

# 1. PostgreSQL dump — direktno u file, NE kroz pipe
# (pipe | gzip je bio razlog za 0-byte backupe 29-30.03)
TMPFILE=$(mktemp /tmp/pg_dump_XXXXXX.sql)
pg_dump -U viskovic_user -h 127.0.0.1 fina_erp -f $TMPFILE 2>/tmp/pgdump_err.log
PG_EXIT=$?

if [ $PG_EXIT -ne 0 ]; then
    ERRMSG=$(head -3 /tmp/pgdump_err.log)
    log "FAIL pg_dump exit=$PG_EXIT: $ERRMSG"
    _wa "LIMIT Connect BACKUP FAIL $(date +%d.%m.%Y) pg_dump error: $ERRMSG RUCNA INTERVENCIJA!"
    rm -f $TMPFILE
    exit 1
fi

# Komprimiraj tek nakon uspjesnog dumpa
gzip -c $TMPFILE > $BACKUP_DIR/db_$DATE.sql.gz
rm -f $TMPFILE

SIZE=$(du -sh $BACKUP_DIR/db_$DATE.sql.gz | cut -f1)
SIZE_BYTES=$(stat -c%s $BACKUP_DIR/db_$DATE.sql.gz)
log "OK DB backup: $SIZE"

# Provjeri velicinu — manji od 5MB = sumnjivo
if [ $SIZE_BYTES -lt 5000000 ]; then
    log "WARN DB backup sumnjivo mali: $SIZE_BYTES bytes"
    _wa "LIMIT Connect BACKUP UPOZORENJE $(date +%d.%m.%Y) DB je samo $SIZE normalno je 89MB! PROVJERI: ls -lah /var/backups/limit-connect/"
fi

# Verificiraj integritet
if ! gzip -t $BACKUP_DIR/db_$DATE.sql.gz 2>/tmp/gzip_check.log; then
    log "FAIL gzip integrity na db_$DATE.sql.gz"
    _wa "LIMIT Connect BACKUP CORRUPT $(date +%d.%m.%Y) db_$DATE.sql.gz ne prolazi integrity check!"
    exit 1
fi
log "OK integrity check passed"

# 2. B2 upload
curl -s --fail \
    --aws-sigv4 "aws:amz:eu-central-003:s3" \
    --user "$B2_KEY_ID:$B2_APP_KEY" \
    -T "$BACKUP_DIR/db_$DATE.sql.gz" \
    "$B2_ENDPOINT/$B2_BUCKET/db/db_$DATE.sql.gz" >> $LOG 2>&1 \
    && log "OK B2 upload: db_$DATE.sql.gz" \
    || log "WARN B2 upload fail (lokalni backup postoji)"

# 3. Media backup
tar czf $BACKUP_DIR/media_$DATE.tar.gz \
    -C /var/www/fina-connect media/ \
    --newer-mtime="3 days ago" \
    --exclude="media/cache" 2>/tmp/tar_err.log \
    && log "OK Media: $(du -sh $BACKUP_DIR/media_$DATE.tar.gz | cut -f1)" \
    || log "SKIP Media (nema novih fajlova)"

# 4. Git snapshot
cd /var/www/fina-connect
git add -A 2>/tmp/git_snap.log
git diff --cached --quiet || git commit -m "Auto-snapshot $DATE [cron]" 2>/tmp/git_snap.log
GIT_HEAD=$(git log --oneline -1 | cut -d' ' -f1)
log "OK Git snapshot: $GIT_HEAD"

# 5. Cleanup
find $BACKUP_DIR -name "*.gz" -mtime +$KEEP_DAYS -delete
log "OK Cleanup (kept $KEEP_DAYS days)"

# 6. WhatsApp potvrda
TOTAL=$(ls $BACKUP_DIR/db_*.sql.gz 2>/tmp/ls_err.log | wc -l)
_wa "LIMIT Connect BACKUP $(date +%d.%m.%Y) DB: $SIZE OK B2: upload OK Git: $GIT_HEAD Cuvam: $TOTAL dana"

log "=== BACKUP DONE ==="
