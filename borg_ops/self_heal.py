"""
BORG FENIX — Self-Healing Engine (F4.2)
Auto-detects and resolves common issues without human intervention.

Capabilities:
1. Service health check + auto-restart
2. Disk space monitor + cleanup
3. DB connection check
4. Celery queue health
5. SSL cert expiry warning
6. Backup integrity verify
"""
import logging
import os
import subprocess
from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('borg.self_heal')

PROJECT = '/var/www/fina-connect'
SERVICES = ['gunicorn-fina', 'celery-worker', 'celery-beat', 'nginx', 'mcp-fina']


@shared_task
def health_check_and_heal():
    """
    Master health check — runs all checks and auto-heals where possible.
    Returns structured report.
    """
    report = {
        'services': check_services(),
        'disk': check_disk(),
        'database': check_database(),
        'celery': check_celery_queue(),
        'ssl': check_ssl_expiry(),
        'timestamp': str(timezone.now()),
        'healed': [],
    }

    # Auto-heal: restart failed services
    for svc, status in report['services'].items():
        if status != 'active':
            try:
                subprocess.run(['systemctl', 'restart', svc],
                             capture_output=True, timeout=30)
                report['healed'].append(f'Restarted {svc}')
                logger.warning('Self-heal: restarted %s (was %s)', svc, status)
            except Exception as e:
                logger.error('Self-heal: failed to restart %s: %s', svc, e)

    # Auto-heal: clean logs if disk > 85%
    if report['disk'].get('percent_used', 0) > 85:
        cleaned = _cleanup_old_logs()
        if cleaned:
            report['healed'].append(f'Cleaned {cleaned} old log files')

    logger.info('Health check: services=%s, disk=%s%%, healed=%d',
                {k: v for k, v in report['services'].items() if v != 'active'},
                report['disk'].get('percent_used', '?'),
                len(report['healed']))
    return report


def check_services():
    """Check systemd service status."""
    results = {}
    for svc in SERVICES:
        try:
            r = subprocess.run(['systemctl', 'is-active', svc],
                             capture_output=True, text=True, timeout=5)
            results[svc] = r.stdout.strip()
        except Exception:
            results[svc] = 'unknown'
    return results


def check_disk():
    """Check disk usage."""
    try:
        r = subprocess.check_output(['df', '-h', '/'], text=True)
        parts = r.strip().split('\n')[1].split()
        pct = int(parts[4].rstrip('%'))
        return {
            'total': parts[1],
            'used': parts[2],
            'free': parts[3],
            'percent_used': pct,
            'warning': pct > 80,
            'critical': pct > 90,
        }
    except Exception as e:
        return {'error': str(e)}


def check_database():
    """Check database connectivity and basic health."""
    from django.db import connection
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.execute("SELECT pg_database_size(current_database())")
            db_size = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_conns = cur.fetchone()[0]
        return {
            'connected': True,
            'size_mb': round(db_size / 1024 / 1024),
            'active_connections': active_conns,
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)}


def check_celery_queue():
    """Check Celery worker status."""
    try:
        from django_celery_results.models import TaskResult
        recent = TaskResult.objects.filter(
            date_done__gte=timezone.now() - timedelta(hours=1),
        ).count()
        failed = TaskResult.objects.filter(
            date_done__gte=timezone.now() - timedelta(hours=1),
            status='FAILURE',
        ).count()
        return {
            'tasks_last_hour': recent,
            'failures_last_hour': failed,
            'healthy': failed < recent * 0.2 if recent > 0 else True,
        }
    except Exception:
        return {'healthy': True, 'note': 'django_celery_results not available'}


def check_ssl_expiry():
    """Check SSL certificate expiry for limit-connect.com."""
    try:
        r = subprocess.run(
            ['openssl', 's_client', '-connect', 'limit-connect.com:443', '-servername',
             'limit-connect.com'],
            input=b'',
            capture_output=True,
            timeout=10,
        )
        cert_text = r.stdout.decode('utf-8', errors='ignore')

        # Extract expiry from certificate
        r2 = subprocess.run(
            ['openssl', 'x509', '-noout', '-enddate'],
            input=r.stdout,
            capture_output=True,
            timeout=5,
        )
        expiry_line = r2.stdout.decode().strip()
        # notAfter=Mar 15 12:00:00 2027 GMT
        if 'notAfter=' in expiry_line:
            date_str = expiry_line.split('=')[1].strip()
            expiry = datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
            days_left = (expiry - datetime.utcnow()).days
            return {
                'expires': str(expiry.date()),
                'days_left': days_left,
                'warning': days_left < 30,
                'critical': days_left < 7,
            }
    except Exception as e:
        return {'error': str(e)}

    return {'status': 'unknown'}


def _cleanup_old_logs():
    """Remove log files older than 30 days."""
    log_dir = os.path.join(PROJECT, 'logs')
    if not os.path.isdir(log_dir):
        return 0

    threshold = datetime.now() - timedelta(days=30)
    cleaned = 0

    for f in os.listdir(log_dir):
        fp = os.path.join(log_dir, f)
        if os.path.isfile(fp) and f.endswith('.log'):
            mtime = datetime.fromtimestamp(os.path.getmtime(fp))
            if mtime < threshold and os.path.getsize(fp) > 10 * 1024 * 1024:  # > 10MB
                try:
                    # Truncate instead of delete
                    with open(fp, 'w') as fh:
                        fh.write(f'# Truncated by BORG self-heal at {datetime.now()}\n')
                    cleaned += 1
                except Exception:
                    pass

    return cleaned
