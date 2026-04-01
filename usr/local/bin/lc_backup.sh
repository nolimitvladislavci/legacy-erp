#!/bin/bash
# LIMIT Connect Daily Backup v3 — lokalni + B2 cloud
# Fix v2: pg_dump direktno u file (ne pipe)
# Fix v3: B2 upload ispravno logiran, s3 multipart za velike fajlove

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
        -o /tmp/wa_backup.log 2>&1
}

_b2_upload() {
    local LOCAL_FILE=$1
    local REMOTE_KEY=$2
    local HTTP_CODE
    HTTP_CODE=$(curl -s -o /tmp/b2_upload_out.txt -w "%{http_code}" \
        --aws-sigv4 "aws:amz:eu-central-003:s3" \
        --user "$B2_KEY_ID:$B2_APP_KEY" \
        -T "$LOCAL_FILE" \
        "$B2_ENDPOINT/$B2_BUCKET/$REMOTE_KEY" 2>/tmp/b2_upload_err.txt)
    echo "$HTTP_CODE"
}

log() { echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a $LOG; }

log "=== BACKUP START v3 ==="

# 1. PostgreSQL dump direktno u file
TMPFILE=$(mktemp /tmp/pg_dump_XXXXXX.sql)
pg_dump -U viskovic_user -h 127.0.0.1 fina_erp -f $TMPFILE 2>/tmp/pgdump_err.log
PG_EXIT=$?

if [ $PG_EXIT -ne 0 ]; then
    ERRMSG=$(head -2 /tmp/pgdump_err.log)
    log "FAIL pg_dump exit=$PG_EXIT: $ERRMSG"
    _wa "LIMIT Connect BACKUP FAIL $(date +%d.%m.%Y) pg_dump greska RUCNA INTERVENCIJA POTREBNA"
    rm -f $TMPFILE
    exit 1
fi

gzip -c $TMPFILE > $BACKUP_DIR/db_$DATE.sql.gz
rm -f $TMPFILE

SIZE=$(du -sh $BACKUP_DIR/db_$DATE.sql.gz | cut -f1)
SIZE_BYTES=$(stat -c%s $BACKUP_DIR/db_$DATE.sql.gz)
log "OK lokalni DB backup: $SIZE"

# Size check
if [ $SIZE_BYTES -lt 5000000 ]; then
    log "WARN backup sumnjivo mali: $SIZE_BYTES bytes"
    _wa "LIMIT Connect BACKUP WARN $(date +%d.%m.%Y) DB samo $SIZE ocekivano 89MB PROVJERI SERVER"
fi

# Integrity check
if ! gzip -t $BACKUP_DIR/db_$DATE.sql.gz 2>/tmp/gzip_err.log; then
    log "FAIL gzip integrity db_$DATE.sql.gz"
    _wa "LIMIT Connect BACKUP CORRUPT $(date +%d.%m.%Y) integrity check FAIL"
    exit 1
fi
log "OK integrity check"

# 2. B2 cloud upload
log "INFO B2 upload pocinje: db_$DATE.sql.gz ($SIZE)..."
B2_STATUS=$(_b2_upload "$BACKUP_DIR/db_$DATE.sql.gz" "db/db_$DATE.sql.gz")

if [ "$B2_STATUS" = "200" ]; then
    log "OK B2 upload: db/db_$DATE.sql.gz HTTP 200"
    B2_OK="B2 cloud OK"
else
    B2_ERR=$(head -3 /tmp/b2_upload_out.txt)
    log "WARN B2 upload HTTP $B2_STATUS: $B2_ERR"
    B2_OK="B2 WARN HTTP $B2_STATUS"
    _wa "LIMIT Connect BACKUP B2 WARN $(date +%d.%m.%Y) HTTP $B2_STATUS lokalni backup postoji ali oblak nije azuriran"
fi

# 3. Media backup
tar czf $BACKUP_DIR/media_$DATE.tar.gz \
    -C /var/www/fina-connect media/ \
    --newer-mtime="3 days ago" \
    --exclude="media/cache" 2>/tmp/tar_err.log
if [ $? -eq 0 ] && [ -f $BACKUP_DIR/media_$DATE.tar.gz ]; then
    MEDIA_SIZE=$(du -sh $BACKUP_DIR/media_$DATE.tar.gz | cut -f1)
    log "OK Media backup: $MEDIA_SIZE"
    # B2 upload medija
    B2_MEDIA=$(_b2_upload "$BACKUP_DIR/media_$DATE.tar.gz" "media/media_$DATE.tar.gz")
    [ "$B2_MEDIA" = "200" ] && log "OK B2 media upload" || log "WARN B2 media upload HTTP $B2_MEDIA"
else
    log "SKIP Media (nema novih fajlova)"
fi

# 4. Git snapshot
cd /var/www/fina-connect
git add -A 2>/tmp/git_err.log
git diff --cached --quiet || git commit -m "Auto-snapshot $DATE [cron]" 2>/tmp/git_err.log
GIT_HEAD=$(git log --oneline -1 | cut -d' ' -f1)
log "OK Git: $GIT_HEAD"

# 5. Cleanup starih lokalnih backupa
find $BACKUP_DIR -name "*.gz" -mtime +$KEEP_DAYS -delete
log "OK Cleanup (kept $KEEP_DAYS days)"

# 6. WhatsApp potvrda
TOTAL=$(ls $BACKUP_DIR/db_*.sql.gz 2>/tmp/ls_err.log | wc -l)
_wa "LIMIT Connect BACKUP $(date +%d.%m.%Y %H:%M) lokalni: $SIZE OK $B2_OK Git: $GIT_HEAD cuvam: $TOTAL dana"

log "=== BACKUP DONE ==="
