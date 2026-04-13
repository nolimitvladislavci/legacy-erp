"""
SuperAdmin AI — Celery tasks za autonomni rad.

Tasks:
  1. ai_watchdog       — Svakih 30 min: health check + process pending actions + token monitor
  2. ai_token_monitor  — Provjera budžeta, notifikacija kad je 80%+ potrošeno
"""
import os
import socket
import subprocess
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, Count
from django.contrib.auth.models import User

from superadmin_ai.models import PendingAIAction
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('superadmin_ai')


# ═══════════════════════════════════════════════════════════════════
# 1. AI WATCHDOG — svakih 30 min
# ═══════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=1, soft_time_limit=120)
def ai_watchdog(self):
    """
    Centralni AI nadzor — pokreće se svakih 30 min.
    1. Health check svih servisa
    2. Automatski obradi AUTONOMOUS pending akcije
    3. Token budget provjera
    4. Notifikacija superadminima ako nešto ne valja
    """
    results = {
        'timestamp': timezone.now().isoformat(),
        'health': {},
        'pending_processed': 0,
        'alerts': [],
    }

    # ── 1. Health checks ──
    results['health'] = _check_all_services()
    failed = [k for k, v in results['health'].items() if not v]
    if failed:
        results['alerts'].append(f"Servisi DOWN: {', '.join(failed)}")

    # ── 2. Process pending actions (AUTONOMOUS only) ──
    results['pending_processed'] = _process_autonomous_pending()

    # ── 3. Token budget monitor ──
    token_alerts = _check_token_budgets()
    results['alerts'].extend(token_alerts)

    # ── 4. AI analiza anomalija (samo kad ima problema) ──
    ai_analysis = _ai_analyze_anomalies(
        results['health'],
        PendingAIAction.objects.filter(status='pending').count()
    )
    if ai_analysis:
        results['ai_analysis'] = ai_analysis
        results['alerts'].append('AI analiza: %s' % ai_analysis[:100])

    # ── 5. Notify if alerts ──
    if results['alerts']:
        _notify_superadmins(
            title='AI Watchdog Alert',
            message='\n'.join(results['alerts']),
            notification_type='system',
        )

    # ── Log to AIActionLog ──
    from .models import AIActionLog
    AIActionLog.objects.create(
        company=None,
        module='superadmin_ai',
        action_type='watchdog_run',
        access_level=3,
        outcome='executed',
        details=results,
    )

    return results


def _check_all_services():
    """Quick health check svih servisa."""
    checks = {}

    # PostgreSQL
    try:
        from django.db import connection
        with connection.cursor() as c:
            c.execute('SELECT 1')
        checks['postgresql'] = True
    except Exception:
        checks['postgresql'] = False

    # Redis
    try:
        from django.core.cache import cache
        cache.set('_watchdog', 'ok', 10)
        checks['redis'] = cache.get('_watchdog') == 'ok'
    except Exception:
        checks['redis'] = False

    # Gunicorn (port 8000)
    checks['gunicorn'] = _port_open(8000)

    # Razbibriga AI (port 8001)
    checks['razbibriga_ai'] = _port_open(8001)

    # Razbibriga WS (port 3001)
    checks['razbibriga_ws'] = _port_open(3001)

    return checks


def _port_open(port, host='127.0.0.1'):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _process_autonomous_pending():
    """Automatski obradi pending akcije za AUTONOMOUS module."""
    from .models import PendingAIAction, AIModulePermission, AIActionLog

    pending = PendingAIAction.objects.filter(status='pending')
    processed = 0

    for action in pending:
        level = AIModulePermission.get_level(action.company, action.module)
        if level == AIModulePermission.ACCESS_AUTONOMOUS:
            # Auto-approve
            action.status = 'approved'
            action.reviewed_at = timezone.now()
            action.save(update_fields=['status', 'reviewed_at'])

            AIActionLog.objects.create(
                company=action.company,
                module=action.module,
                action_type=f'auto_approve_{action.action_type}',
                access_level=level,
                outcome='executed',
                details={'action_id': str(action.id), 'auto': True},
            )
            processed += 1

    return processed


# ═══════════════════════════════════════════════════════════════════
# 2. TOKEN MONITOR
# ═══════════════════════════════════════════════════════════════════

@shared_task(bind=True, soft_time_limit=30)
def ai_token_monitor(self):
    """
    Provjeri AI token budžet i pošalji obavijest kad je 80%+ potrošeno.
    Provjerava i Gemini i Claude budžet.
    """
    alerts = _check_token_budgets()
    if alerts:
        _notify_superadmins(
            title='AI Token Budget Upozorenje',
            message='\n'.join(alerts),
            notification_type='system',
        )
    return {'alerts': alerts}


def _check_token_budgets():
    """Provjeri Gemini i Claude token budžete."""
    alerts = []
    today = timezone.now().date()
    now = timezone.now()
    hour_ago = now - timedelta(hours=1)

    # ── Gemini budget ──
    GEMINI_DAILY_LIMIT = 200
    GEMINI_HOURLY_LIMIT = 30
    GEMINI_TOKEN_DAILY_LIMIT = 500_000

    try:
        from smart_import.models import GeminiUsageLog

        daily_calls = GeminiUsageLog.objects.filter(
            called_at__date=today
        ).count()

        hourly_calls = GeminiUsageLog.objects.filter(
            called_at__gte=hour_ago
        ).count()

        daily_tokens = GeminiUsageLog.objects.filter(
            called_at__date=today
        ).aggregate(total=Sum('input_tokens'))['total'] or 0

        daily_cost = GeminiUsageLog.objects.filter(
            called_at__date=today
        ).aggregate(total=Sum('cost_eur'))['total'] or Decimal('0')

        # 80% threshold alerts
        if daily_calls >= int(GEMINI_DAILY_LIMIT * 0.8):
            pct = round(daily_calls / GEMINI_DAILY_LIMIT * 100)
            alerts.append(
                f'⚠ Gemini dnevni pozivi: {daily_calls}/{GEMINI_DAILY_LIMIT} ({pct}%)'
            )

        if hourly_calls >= int(GEMINI_HOURLY_LIMIT * 0.8):
            pct = round(hourly_calls / GEMINI_HOURLY_LIMIT * 100)
            alerts.append(
                f'⚠ Gemini satni pozivi: {hourly_calls}/{GEMINI_HOURLY_LIMIT} ({pct}%)'
            )

        if daily_tokens >= int(GEMINI_TOKEN_DAILY_LIMIT * 0.8):
            pct = round(daily_tokens / GEMINI_TOKEN_DAILY_LIMIT * 100)
            alerts.append(
                f'⚠ Gemini dnevni tokeni: {daily_tokens:,}/{GEMINI_TOKEN_DAILY_LIMIT:,} ({pct}%)'
            )

    except (ValueError, TypeError) as e:
        logger.warning(f'Gemini budget check failed: {e}')

    # ── Claude budget ──
    CLAUDE_HOURLY_LIMIT = 30  # per user, but we check global

    try:
        from ai_assistant.models import AIUsageLog

        daily_claude_calls = AIUsageLog.objects.filter(
            created_at__date=today
        ).count()

        daily_claude_cost = AIUsageLog.objects.filter(
            created_at__date=today
        ).aggregate(total=Sum('cost_estimate'))['total'] or Decimal('0')

        daily_claude_tokens = AIUsageLog.objects.filter(
            created_at__date=today
        ).aggregate(
            input=Sum('input_tokens'),
            output=Sum('output_tokens'),
        )
        input_t = daily_claude_tokens['input'] or 0
        output_t = daily_claude_tokens['output'] or 0

        # Alert if daily cost exceeds $1
        if daily_claude_cost > Decimal('1.00'):
            alerts.append(
                f'⚠ Claude dnevni trošak: ${daily_claude_cost:.4f} ({daily_claude_calls} poziva, {input_t:,}+{output_t:,} tokena)'
            )

        # Alert if more than 200 calls/day
        if daily_claude_calls >= 160:
            alerts.append(
                f'⚠ Claude dnevni pozivi: {daily_claude_calls} (visoka aktivnost)'
            )

    except (ValueError, TypeError) as e:
        logger.warning(f'Claude budget check failed: {e}')

    return alerts


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def ai_council_executor(self):
    """
    Svakih 10 min: skenira PendingAIAction s status='approved'
    i sprovodi ih kroz AIOperativeExecutor.
    """
    from .models import PendingAIAction
    from .executor import AIOperativeExecutor, AIExecutionError
    from django.contrib.auth.models import User

    # AI system user — kreira se ako ne postoji
    system_user, _ = User.objects.get_or_create(
        username='ai_system',
        defaults={
            'first_name': 'AI', 'last_name': 'System',
            'is_active': True, 'is_staff': False,
        }
    )

    approved = PendingAIAction.objects.filter(status='approved')
    executed = 0
    failed = 0

    for action in approved:
        # Samo executor-kompatibilni moduli
        if action.module not in ('b2b_procurement', 'dynamic_pricing', 'haccp_logistics'):
            continue

        try:
            AIOperativeExecutor.execute_approved_action(action.pk, system_user)
            executed += 1
        except AIExecutionError as e:
            logger.warning('[AI EXECUTOR] Action %s failed: %s', action.pk, e.message)
            failed += 1
        except Exception as e:
            logger.error('[AI EXECUTOR] Unexpected error on %s: %s', action.pk, e, exc_info=True)
            failed += 1

    if executed or failed:
        logger.info('[AI EXECUTOR] Cron: %d executed, %d failed', executed, failed)

    return {'executed': executed, 'failed': failed}


def _ai_analyze_anomalies(health_results, pending_count):
    """
    Claude Haiku analizira health rezultate i daje preporuke.
    Poziva se samo ako ima problema — ne troši tokene kad je sve OK.
    """
    import json as _json
    failed_services = [k for k, v in health_results.items() if not v]
    if not failed_services and pending_count == 0:
        return None

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        context = {
            'failed_services': failed_services,
            'pending_actions': pending_count,
            'timestamp': timezone.now().strftime('%d.%m.%Y %H:%M'),
        }
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{
                'role': 'user',
                'content': (
                    'Ti si AI nadzornik sustava. Analiziraj ovu situaciju i daj kratku '
                    'preporuku (2-3 rečenice, HR jezik, konkretan sljedeći korak):\n\n'
                    + _json.dumps(context, ensure_ascii=False)
                )
            }]
        )
        return response.content[0].text
    except (TypeError, ValueError) as e:
        logger.warning('AI watchdog analysis failed: %s', e)
        return None


@shared_task(bind=True, soft_time_limit=60)
def escalate_stale_pending(self):
    """
    Svakih 4h: Eskalacija pending AI akcija.
    > 24h → email superadminu
    > 48h → auto-reject
    """
    from .models import AIActionLog

    now = timezone.now()
    stale_24h = now - timedelta(hours=24)
    stale_48h = now - timedelta(hours=48)

    # Auto-reject starije od 48h
    expired = PendingAIAction.objects.filter(
        status='pending',
        created_at__lte=stale_48h,
    )
    expired_count = 0
    for action in expired:
        action.status = 'expired'
        action.review_note = 'Auto-expired: nije odobreno u 48h'
        action.save(update_fields=['status', 'review_note'])
        AIActionLog.objects.create(
            company=action.company, module=action.module,
            action_type='auto_expire_%s' % action.action_type,
            access_level=2, outcome='failed',
            details={'reason': 'timeout_48h', 'action_id': str(action.id)},
        )
        expired_count += 1

    # Eskalacija za 24-48h stare
    warning_actions = PendingAIAction.objects.filter(
        status='pending',
        created_at__lte=stale_24h,
        created_at__gt=stale_48h,
    )

    if warning_actions.exists():
        count = warning_actions.count()
        _notify_superadmins(
            title='%d AI akcija čeka odobrenje >24h' % count,
            message=(
                '%d AI prijedloga čeka vaše odobrenje već duže od 24 sata.\n'
                'Stariji zahtjevi biti će automatski odbijeni za 24h.\n'
                'Pregledajte na: /superadmin/ai/'
            ) % count,
            notification_type='system',
        )

    return {'expired': expired_count, 'escalated': warning_actions.count()}


def _notify_superadmins(title, message, notification_type='system'):
    """Pošalji notifikaciju svim superadminima."""
    try:
        from notifications.services import notify_bulk
        admins = User.objects.filter(is_superuser=True, is_active=True)
        if admins.exists():
            notify_bulk(
                recipients=list(admins),
                notification_type=notification_type,
                title=title,
                message=message,
                url='/superadmin/ai/',
            )
    except DatabaseError as e:
        logger.error(f'Failed to notify superadmins: {e}')
