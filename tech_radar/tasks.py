"""
Tech Radar Celery Tasks.

  tech_radar_scan   — svakih 15 min: snima metrike sustava
  capacity_check    — svakih 1h: provjera pragova + alarmiranje
  cleanup_signals   — dnevno: briši signale starije od 90 dana
"""
import os
import logging
import shutil
import subprocess
from decimal import Decimal
from datetime import timedelta

from celery import shared_task
from django.utils import timezone as tz
from django.db import DatabaseError

logger = logging.getLogger('tech_radar')


@shared_task(bind=True, max_retries=1, soft_time_limit=60)
def tech_radar_scan(self):
    """
    Svakih 15 min: snimi stanje sustava u TechSignal.
    Prikuplja: DB, disk, RAM, CPU, Celery, Redis, business metrike.
    """
    from tech_radar.models import TechSignal

    signal = TechSignal(source='auto')
    alerts = []

    # ── DB Metrics ──
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            db_bytes = cur.fetchone()[0]
            signal.db_size_mb = Decimal(str(round(db_bytes / 1024 / 1024, 2)))

            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            signal.db_connections = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
            signal.db_table_count = cur.fetchone()[0]
    except (ValueError, TypeError) as e:
        alerts.append('DB metrics failed: %s' % str(e)[:80])
        logger.warning('Tech radar DB check failed: %s', e)

    # ── Disk ──
    try:
        usage = shutil.disk_usage('/')
        signal.disk_used_pct = Decimal(str(round(usage.used / usage.total * 100, 1)))
        signal.disk_free_gb = Decimal(str(round(usage.free / 1024 / 1024 / 1024, 2)))
    except (ValueError, TypeError) as e:
        alerts.append('Disk check failed: %s' % str(e)[:80])

    # ── Memory ──
    try:
        with open('/proc/meminfo') as f:
            lines = f.readlines()
        mem = {}
        for line in lines[:10]:
            parts = line.split(':')
            if len(parts) == 2:
                key = parts[0].strip()
                val = int(parts[1].strip().split()[0])  # kB
                mem[key] = val
        total = mem.get('MemTotal', 1)
        available = mem.get('MemAvailable', 0)
        signal.memory_used_pct = Decimal(str(round((1 - available / total) * 100, 1)))
        signal.memory_available_mb = available // 1024
    except (ValueError, TypeError) as e:
        alerts.append('Memory check failed: %s' % str(e)[:80])

    # ── CPU Load ──
    try:
        load1, _, _ = os.getloadavg()
        signal.cpu_load_1m = Decimal(str(round(load1, 2)))
    except (ValueError, TypeError):
        pass

    # ── Celery ──
    try:
        from django.core.cache import cache
        # Queue size via Redis
        import redis
        r = redis.from_url(os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/2'))
        signal.celery_queue_size = r.llen('celery') or 0

        # Worker count
        from celery import current_app
        inspect = current_app.control.inspect(timeout=2)
        workers = inspect.active_queues() or {}
        signal.celery_workers = len(workers)
    except ImportError:
        signal.celery_queue_size = -1
        signal.celery_workers = -1

    # ── Redis Memory ──
    try:
        import redis
        r = redis.from_url(os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'))
        info = r.info('memory')
        signal.redis_memory_mb = Decimal(str(round(info.get('used_memory', 0) / 1024 / 1024, 2)))
    except (ValueError, TypeError):
        pass

    # ── Media Size ──
    try:
        result = subprocess.run(
            ['du', '-sm', '/var/www/fina-connect/media/'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            signal.media_size_mb = Decimal(result.stdout.split()[0])
    except (ValueError, TypeError):
        pass

    # ── Business Metrics ──
    try:
        from companies.models import Company
        from django.contrib.auth.models import User
        signal.total_companies = Company.objects.count()
        signal.total_users = User.objects.filter(is_active=True).count()
    except DatabaseError:
        pass

    try:
        from pos.models import POSReceipt
        signal.receipts_today = POSReceipt.objects.filter(
            paid_at__date=tz.now().date()
        ).count()
    except DatabaseError:
        pass

    try:
        from superadmin_ai.models import AIActionLog
        signal.api_calls_today = AIActionLog.objects.filter(
            timestamp__date=tz.now().date()
        ).count()
    except DatabaseError:
        pass

    # ── Active Sessions ──
    try:
        from django.contrib.sessions.models import Session
        signal.active_sessions = Session.objects.filter(
            expire_date__gt=tz.now()
        ).count()
    except DatabaseError:
        pass

    signal.alerts = alerts
    signal.save()

    logger.info(
        '[TECH RADAR] Scan: DB=%sMB Disk=%s%% RAM=%s%% CPU=%s Sessions=%d',
        signal.db_size_mb, signal.disk_used_pct, signal.memory_used_pct,
        signal.cpu_load_1m, signal.active_sessions,
    )

    return {
        'signal_id': str(signal.pk),
        'db_mb': str(signal.db_size_mb),
        'disk_pct': str(signal.disk_used_pct),
        'ram_pct': str(signal.memory_used_pct),
        'alerts': len(alerts),
    }


@shared_task(bind=True, max_retries=1, soft_time_limit=30)
def capacity_check(self):
    """
    Svaki sat: provjeri pragove kapaciteta i alarmira ako treba.
    Čita zadnji TechSignal i uspoređuje s CapacityThreshold.
    """
    from tech_radar.models import TechSignal, CapacityThreshold

    signal = TechSignal.objects.order_by('-timestamp').first()
    if not signal:
        return {'status': 'no_data'}

    # Stariji od 30 min → nema svježeg scana
    if signal.timestamp < tz.now() - timedelta(minutes=30):
        return {'status': 'stale', 'age_min': int((tz.now() - signal.timestamp).total_seconds() / 60)}

    alerts = []
    worst_severity = 'ok'

    checks = {
        'disk_used_pct': signal.disk_used_pct,
        'memory_used_pct': signal.memory_used_pct,
        'db_size_mb': signal.db_size_mb,
        'cpu_load_1m': signal.cpu_load_1m,
        'celery_queue_size': Decimal(str(signal.celery_queue_size)),
        'redis_memory_mb': signal.redis_memory_mb,
    }

    for metric, value in checks.items():
        severity = CapacityThreshold.check_metric(metric, value)
        if severity != 'ok':
            alerts.append({
                'metric': metric,
                'value': str(value),
                'severity': severity,
            })
            if severity == 'critical':
                worst_severity = 'critical'
            elif severity == 'warning' and worst_severity != 'critical':
                worst_severity = 'warning'

    # Update signal severity
    if worst_severity != 'ok':
        signal.severity = worst_severity
        signal.alerts = [a['metric'] + ': ' + a['severity'] for a in alerts]
        signal.save(update_fields=['severity', 'alerts'])

        # Notify superadmins
        from superadmin_ai.tasks import _notify_superadmins
        _notify_superadmins(
            title='Tech Radar: %s' % worst_severity.upper(),
            message='\n'.join(
                '%s = %s (%s)' % (a['metric'], a['value'], a['severity'])
                for a in alerts
            ),
            notification_type='system',
        )

    logger.info('[CAPACITY] Check: %s (%d alerts)', worst_severity, len(alerts))

    return {
        'severity': worst_severity,
        'alerts': alerts,
    }


@shared_task
def cleanup_signals():
    """Dnevno: briši TechSignal starije od 90 dana."""
    from tech_radar.models import TechSignal
    cutoff = tz.now() - timedelta(days=90)
    deleted, _ = TechSignal.objects.filter(timestamp__lt=cutoff).delete()
    logger.info('[TECH RADAR] Cleanup: %d signals deleted', deleted)
    return {'deleted': deleted}
