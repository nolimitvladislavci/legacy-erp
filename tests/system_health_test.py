#!/usr/bin/env python3
import os, sys, subprocess, ssl, socket, re
from datetime import datetime, timedelta
sys.path.insert(0, '/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from django.conf import settings
from django.utils import timezone
passed = 0
warnings = 0
failed = 0
NL = chr(10)
def ok(msg):
    global passed; passed += 1; print(f"  ✅ {msg}")
def warn(msg):
    global warnings; warnings += 1; print(f"  ⚠️  {msg}")
def fail(msg):
    global failed; failed += 1; print(f"  ❌ {msg}")
def section(num, total, title):
    print(NL + f"[{num}/{total}] {title}")
TOTAL = 12
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(NL + "═"*62)
print("  LIMIT CONNECT — System Health Report")
print(f"  {now_str}")
print("═"*62)
section(1, TOTAL, "CELERY CONFIGURATION")
acks = getattr(settings, "CELERY_TASK_ACKS_LATE", None)
ok("ACKS_LATE = True") if acks is True else fail(f"ACKS_LATE = {acks} (expected True)")
reject = getattr(settings, "CELERY_TASK_REJECT_ON_WORKER_LOST", None)
ok("REJECT_ON_WORKER_LOST = True") if reject is True else fail(f"REJECT_ON_WORKER_LOST = {reject}")
soft = getattr(settings, "CELERY_TASK_SOFT_TIME_LIMIT", None)
ok(f"SOFT_TIME_LIMIT = {soft}s") if soft and soft > 0 else fail(f"SOFT_TIME_LIMIT = {soft}")
hard = getattr(settings, "CELERY_TASK_TIME_LIMIT", None)
if hard and soft and hard > soft: ok(f"TIME_LIMIT = {hard}s (> soft {soft}s)")
elif hard: warn(f"TIME_LIMIT = {hard}s (should be > {soft}s)")
else: fail(f"TIME_LIMIT = {hard}")
broker = getattr(settings, "CELERY_BROKER_URL", None)
ok(f"BROKER_URL = {broker}") if broker else fail("BROKER_URL not set")
backend = getattr(settings, "CELERY_RESULT_BACKEND", None)
ok(f"RESULT_BACKEND = {backend}") if backend else fail("RESULT_BACKEND not set")
section(2, TOTAL, "REDIS CONNECTIVITY")
try:
    import redis
    r = redis.Redis.from_url(broker or "redis://127.0.0.1:6379/0")
    ok("Redis PONG - broker reachable") if r.ping() else fail("Redis ping False")
    info = r.info("memory")
    used_mb = info.get("used_memory", 0) / (1024*1024)
    ok(f"Redis memory: {used_mb:.1f} MB (< 100 MB)") if used_mb < 100 else warn(f"Redis memory: {used_mb:.1f} MB")
except ImportError: warn("redis-py not installed")
except Exception as e: fail(f"Redis error: {e}")
section(3, TOTAL, "IMAP PEEK VERIFICATION")
try:
    with open("/var/www/fina-connect/smart_import/tasks.py") as f: src = f.read()
    if "BODY.PEEK[]" in src: ok("Uses BODY.PEEK[] (no auto Seen)")
    elif "RFC822" in src: fail("Uses RFC822 - auto-marks Seen")
    else: warn("Neither BODY.PEEK[] nor RFC822 found")
    if re.search(r"store.*Seen|add_flag.*Seen", src): ok("Explicitly stores Seen flag")
    else: warn("No explicit Seen flag store - relies on PEEK")
except Exception as e: fail(f"Cannot read tasks.py: {e}")
section(4, TOTAL, "IMPORT BATCH INTEGRITY")
try:
    from smart_import.models import ImportBatch
    for code, label in ImportBatch.STATUS:
        cnt = ImportBatch.objects.using("default").filter(status=code).count()
        ok(f"Batches [{label}]: {cnt}")
    threshold = timezone.now() - timedelta(minutes=30)
    stale = ImportBatch.objects.using("default").filter(status__in=["pending","processing"], created_at__lt=threshold).count()
    ok("No stale batches (pending/processing > 30 min)") if stale == 0 else warn(f"{stale} stale batch(es)")
    confirmed = ImportBatch.objects.using("default").filter(status="confirmed")
    orph = confirmed.filter(goods_receipt__isnull=True).count()
    ok(f"All {confirmed.count()} confirmed batches have GoodsReceipt") if orph == 0 else warn(f"{orph} confirmed without GoodsReceipt")
except Exception as e: fail(f"ImportBatch error: {e}")
section(5, TOTAL, "KONTO BALANCE CHECK")
try:
    from konto.models import JournalEntry
    entries = JournalEntry.objects.all()
    te = entries.count()
    unbal = []
    for entry in entries:
        try:
            if not entry.is_balanced(): unbal.append(entry)
        except Exception: pass
    if te == 0: warn("No JournalEntry records")
    elif not unbal: ok(f"All {te} journal entries balanced")
    else:
        fail(f"{len(unbal)}/{te} entries UNBALANCED:")
        for u in unbal[:5]: print(f"      - entry id={u.pk}: {u}")
except ImportError: warn("konto app not available")
except Exception as e: fail(f"JournalEntry error: {e}")
section(6, TOTAL, "DATABASE INTEGRITY")
try:
    from companies.models import Company
    from django.contrib.auth import get_user_model
    from partners.models import Partner
    from inventory.models import InventoryItem
    from invoicing.models import Invoice
    from accounts.models import CompanyMembership
    from registration.models import CompanySubscription
    User = get_user_model()
    data = {"Companies": Company.objects.count(), "Users": User.objects.count(), "Partners": Partner.objects.using("default").count(), "Inventory Items": InventoryItem.objects.using("default").count(), "Invoices": Invoice.objects.using("default").count()}
    for label, cnt in data.items(): ok(f"{label}: {cnt}")
    wm = set(CompanyMembership.objects.values_list("company_id", flat=True).distinct())
    ai = set(Company.objects.values_list("id", flat=True))
    nm = ai - wm
    ok("All companies have user memberships") if not nm else warn(f"{len(nm)} company(ies) without memberships: {nm}")
    si = set(CompanySubscription.objects.values_list("company_id", flat=True).distinct())
    os2 = si - ai
    ok("No orphaned CompanySubscription records") if not os2 else warn(f"Orphaned subscription IDs: {os2}")
except Exception as e: fail(f"DB integrity error: {e}")
section(7, TOTAL, "FAILED IMPORTS CHECK")
try:
    from smart_import.models import ImportBatch
    errs = ImportBatch.objects.using("default").filter(status="error").order_by("-created_at")
    ec = errs.count()
    if ec == 0: ok("No failed import batches")
    else:
        warn(f"{ec} failed import batch(es)")
        for b in errs[:5]:
            cr = b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "?"
            print(f"      - Batch id={b.pk} ({cr}): {b.error_msg[:80] if b.error_msg else str()}")
except Exception as e: fail(f"Failed imports error: {e}")
section(8, TOTAL, "EMAIL RAMPA STATUS")
try:
    from smart_import.models import CompanyMailbox
    mbs = CompanyMailbox.objects.all()
    if not mbs.exists(): warn("No CompanyMailbox records")
    else:
        for mb in mbs:
            lc = mb.last_check.strftime("%Y-%m-%d %H:%M") if mb.last_check else "never"
            if mb.last_error: warn(f"{mb.email_address} -> {mb.company.name} | last: {lc} | ERROR: {mb.last_error[:60]}")
            else: ok(f"{mb.email_address} -> {mb.company.name} | last: {lc} | imported: {mb.total_imported}")
except Exception as e: fail(f"Email Rampa error: {e}")
section(9, TOTAL, "SERVER RESOURCES")
try:
    df = subprocess.check_output(["df","-h","/"], text=True).strip().split(NL)
    if len(df) >= 2:
        p = df[1].split(); pct = int(p[4].replace("%",""))
        ok(f"Disk: {p[4]} of {p[1]} ({p[3]} free)") if pct < 80 else warn(f"Disk HIGH: {p[4]} of {p[1]}")
    mem = subprocess.check_output(["free","-m"], text=True).strip().split(NL)
    if len(mem) >= 2:
        mp = mem[1].split(); avail = int(mp[-1]); tot = int(mp[1])
        ok(f"Memory: {avail} MB available / {tot} MB total") if avail >= 500 else warn(f"Memory LOW: {avail} MB / {tot} MB")
    try:
        sup = subprocess.check_output(["supervisorctl","status"], text=True, stderr=subprocess.STDOUT).strip()
        for line in sup.split(NL):
            line = line.strip()
            if not line: continue
            if "RUNNING" in line: ok(f"Supervisor: {line.split()[0]} RUNNING")
            else:
                sp = line.split()
                fail(f"Supervisor: {sp[0]} {sp[1] if len(sp)>1 else 'UNKNOWN'}")
    except Exception as e: warn(f"Supervisor check: {e}")
except Exception as e: fail(f"Server resources error: {e}")
section(10, TOTAL, "SSL CERTIFICATES")
for domain in ["limit-connect.com", "viskovic-group.de", "fina-connect.online"]:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5); s.connect((domain, 443))
            cert = s.getpeercert()
            exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days = (exp - datetime.utcnow()).days
            if days > 14: ok(f"{domain}: expires {exp:%Y-%m-%d} ({days} days)")
            elif days > 0: warn(f"{domain}: expires {exp:%Y-%m-%d} ({days} days - RENEW!)")
            else: fail(f"{domain}: EXPIRED {exp:%Y-%m-%d}")
    except Exception as e: warn(f"{domain}: SSL check failed - {e}")
section(11, TOTAL, "DOMAIN MIGRATION VERIFICATION")
allowed = getattr(settings, "ALLOWED_HOSTS", [])
csrf_origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", [])
ok("No fina-connect.online in ALLOWED_HOSTS") if "fina-connect.online" not in allowed else warn("fina-connect.online still in ALLOWED_HOSTS")
ok("limit-connect.com in ALLOWED_HOSTS") if "limit-connect.com" in allowed else fail("limit-connect.com NOT in ALLOWED_HOSTS")
ok("CSRF_TRUSTED_ORIGINS has limit-connect.com") if any("limit-connect.com" in o for o in csrf_origins) else fail("CSRF missing limit-connect.com")
try:
    r = subprocess.run(["grep","-rn","FINA-CONNECT","/var/www/fina-connect/templates/"], capture_output=True, text=True, timeout=10)
    lines = [l for l in r.stdout.strip().split(NL) if l]
    refs = [l for l in lines if not any(x in l.lower() for x in ["fiscal","fiskalizacija","fina cert","fina demo","fina cis","fina_cert","fina-connect.online"])]
    if refs:
        warn(f"{len(refs)} template(s) still reference FINA-CONNECT branding:")
        for ref in refs[:5]: print(f"      {ref[:120]}")
    else: ok("No FINA-CONNECT branding in templates")
except Exception as e: warn(f"Template grep: {e}")
section(12, TOTAL, "NGINX CONFIGURATION")
try:
    nt = subprocess.run(["nginx","-t"], capture_output=True, text=True, timeout=10)
    ok("nginx -t passed") if nt.returncode == 0 else fail(f"nginx -t FAILED: {nt.stderr.strip()[:100]}")
except Exception as e: fail(f"nginx -t: {e}")
try:
    r = subprocess.run(["grep","-rl","limit-connect.com","/etc/nginx/sites-enabled/"], capture_output=True, text=True, timeout=5)
    ok(f"limit-connect.com server block: {r.stdout.strip()}") if r.stdout.strip() else fail("No limit-connect.com in sites-enabled")
except Exception as e: warn(f"Nginx check: {e}")
try:
    r = subprocess.run(["grep","-rl","fina-connect.online","/etc/nginx/sites-enabled/"], capture_output=True, text=True, timeout=5)
    if r.stdout.strip():
        cf = r.stdout.strip().split(NL)[0]
        rc = subprocess.run(["grep","-E","return.*301|rewrite.*permanent",cf], capture_output=True, text=True, timeout=5)
        ok("fina-connect.online redirect block found") if rc.stdout.strip() else warn("fina-connect.online config but no 301 redirect")
    else: warn("No fina-connect.online config (may be removed)")
except Exception as e: warn(f"Redirect check: {e}")
total = passed + warnings + failed
print(NL + "═"*62)
print(f"  SUMMARY: {passed}/{total} PASSED | {warnings} WARNINGS | {failed} FAILED")
print("═"*62 + NL)
sys.exit(1 if failed > 0 else 0)
