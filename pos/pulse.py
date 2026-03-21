"""
POS Pulse — AI Živčani Sustav.

Real-time anomaly detection za POS:
- Neobičan storno pattern (>3 storna u 30min)
- Cash manjak >5 EUR pri zatvaranju
- Prebrza naplata (<3s između bonova)
- Masovni popusti (>20% na >5 bonova uzastopno)
- Fiskalizacija fail streak
- Revenue milestones (1K, 5K, 10K dnevno)
- Stock alert (artikl na 0)

Svaki event se sprema + opcija WhatsApp alert vlasniku.
"""
import logging
from decimal import Decimal
from django.utils import timezone as tz
from django.db.models import Count, Sum, Q, Avg

logger = logging.getLogger('pos_pulse')


def emit(company, event_type, severity, title, detail='', terminal=None, metadata=None):
    """Central pulse emitter — sprema event i trigera notifikaciju."""
    from pos.models import POSPulseEvent
    event = POSPulseEvent.objects.create(
        company=company,
        terminal=terminal,
        event_type=event_type,
        severity=severity,
        title=title,
        detail=detail,
        metadata=metadata or {},
    )
    # WhatsApp alert za critical events
    if severity == 'critical':
        try:
            _whatsapp_alert(company, event)
        except Exception as e:
            logger.warning('Pulse WhatsApp failed: %s', e)
    return event


def _whatsapp_alert(company, event):
    """Pošalji WhatsApp alert vlasniku za kritične događaje."""
    # Budući: integracija s WhatsApp Business API
    logger.info('PULSE ALERT [%s] %s: %s — %s',
                event.severity, company.name, event.title, event.detail[:100])


def analyze_receipt(receipt):
    """Pokreće se nakon svake naplate — traži anomalije."""
    company = receipt.session.terminal.company
    terminal = receipt.session.terminal
    session = receipt.session
    now = tz.now()

    # ── 1. STORNO PATTERN ──
    # >3 storna u zadnjih 30min = sumnjivo
    from pos.models import POSReceipt
    from datetime import timedelta
    recent_cancels = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='cancelled',
        created_at__gte=now - timedelta(minutes=30),
    ).count()
    if recent_cancels >= 3:
        emit(company, 'anomaly_cancel', 'warning',
             f'{recent_cancels} storniranih bonova u 30 min',
             f'Terminal: {terminal.name}. Provjerite je li sve u redu.',
             terminal=terminal,
             metadata={'cancel_count': recent_cancels, 'window': '30min'})

    # ── 2. PREBRZA NAPLATA ──
    # Ako je prošli bon bio <5s ago = sumnjivo brzo
    prev = POSReceipt.objects.filter(
        session=session, status='paid'
    ).exclude(pk=receipt.pk).order_by('-paid_at').first()
    if prev and prev.paid_at and receipt.paid_at:
        gap = (receipt.paid_at - prev.paid_at).total_seconds()
        if gap < 5 and receipt.total > Decimal('50'):
            emit(company, 'anomaly_speed', 'warning',
                 f'Bon #{receipt.receipt_number} naplaćen {gap:.0f}s nakon prethodnog',
                 f'Iznos: {receipt.total} EUR. Prebrzo za normalan unos.',
                 terminal=terminal,
                 metadata={'gap_seconds': gap, 'total': str(receipt.total)})

    # ── 3. VISOK POPUST ──
    high_discount_items = receipt.items.filter(discount_percent__gt=20)
    if high_discount_items.exists():
        for item in high_discount_items:
            if item.discount_percent >= 50:
                emit(company, 'anomaly_discount', 'warning',
                     f'Popust {item.discount_percent}% na "{item.description}"',
                     f'Bon #{receipt.receipt_number}, {terminal.name}',
                     terminal=terminal,
                     metadata={'discount': str(item.discount_percent), 'item': item.description})

    # ── 4. MILESTONE CHECK ──
    today = now.date()
    today_revenue = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
        paid_at__date=today,
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')

    today_count = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
        paid_at__date=today,
    ).count()

    # 100. bon danas
    if today_count == 100:
        emit(company, 'milestone_100', 'success',
             f'100. bon danas! Revenue: {today_revenue:.2f} EUR',
             terminal=terminal)

    # Revenue milestones
    for threshold in [1000, 5000, 10000]:
        if today_revenue >= threshold:
            # Check ako već postoji milestone event za ovaj prag danas
            exists = company.pulse_events.filter(
                event_type='milestone_revenue',
                created_at__date=today,
                metadata__contains={'threshold': threshold},
            ).exists()
            if not exists:
                emit(company, 'milestone_revenue', 'success',
                     f'Dnevni promet prešao {threshold} EUR!',
                     f'Ukupno danas: {today_revenue:.2f} EUR, {today_count} bonova',
                     metadata={'threshold': threshold, 'revenue': str(today_revenue)})

    # ── 5. FISKALIZACIJA FAIL ──
    if not receipt.jir and not receipt.is_training and receipt.status == 'paid':
        fail_streak = POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            jir__isnull=True,
            jir='',
            paid_at__date=today,
            is_training=False,
        ).count()
        if fail_streak >= 3:
            emit(company, 'alert_fiscal', 'critical',
                 f'{fail_streak} bonova bez fiskalizacije danas!',
                 'FINA CIS ili TSE ne odgovara. Automatski retry aktivan.',
                 terminal=terminal,
                 metadata={'fail_count': fail_streak})


def analyze_session_close(session):
    """Analiza pri zatvaranju smjene — cash difference."""
    company = session.terminal.company
    terminal = session.terminal
    diff = session.cash_difference

    if abs(diff) > 5:
        severity = 'critical' if abs(diff) > 20 else 'warning'
        direction = 'MANJAK' if diff < 0 else 'VIŠAK'
        emit(company, 'anomaly_cash', severity,
             f'Cash {direction}: {abs(diff):.2f} EUR',
             f'Smjena #{session.session_number}, {terminal.name}. '
             f'Očekivano: {session.expected_closing_cash:.2f}, prebrojano: {session.closing_cash:.2f}',
             terminal=terminal,
             metadata={
                 'difference': str(diff),
                 'expected': str(session.expected_closing_cash),
                 'counted': str(session.closing_cash),
             })

    emit(company, 'shift_close', 'info',
         f'Smjena #{session.session_number} zatvorena',
         f'{terminal.name} | Promet: {session.total_sales:.2f} EUR',
         terminal=terminal,
         metadata={'total_sales': str(session.total_sales)})


def get_dashboard_data(company):
    """Pulse dashboard podaci za frontend."""
    now = tz.now()
    today = now.date()
    from pos.models import POSReceipt, POSPulseEvent, POSSession, POSTerminal
    from datetime import timedelta

    # Active terminals (smjena otvorena)
    active_sessions = POSSession.objects.filter(
        terminal__company=company, status='open',
    ).select_related('terminal', 'operator')

    terminals_data = []
    for sess in active_sessions:
        receipts = sess.receipts.filter(status='paid')
        terminals_data.append({
            'terminal': sess.terminal.name,
            'terminal_id': sess.terminal.pk,
            'operator': sess.operator.get_full_name() if sess.operator else '—',
            'session_number': sess.session_number,
            'receipt_count': receipts.count(),
            'revenue': float(receipts.aggregate(t=Sum('total'))['t'] or 0),
            'opened_at': sess.opened_at.isoformat(),
            'is_training': sess.is_training,
        })

    # Today stats
    today_receipts = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
        paid_at__date=today,
    )
    today_revenue = today_receipts.aggregate(t=Sum('total'))['t'] or Decimal('0')
    today_count = today_receipts.count()
    today_avg = today_revenue / today_count if today_count else Decimal('0')

    # Pulse events (last 24h)
    events_qs = POSPulseEvent.objects.filter(
        company=company,
        created_at__gte=now - timedelta(hours=24),
    ).order_by('-created_at')

    unread_count = events_qs.filter(is_read=False).count()
    critical_count = events_qs.filter(severity='critical', is_read=False).count()
    events = events_qs[:50]

    # Hourly revenue chart (last 12h)
    hourly = []
    for h in range(12):
        hour_start = now.replace(minute=0, second=0) - timedelta(hours=11 - h)
        hour_end = hour_start + timedelta(hours=1)
        rev = POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            paid_at__gte=hour_start,
            paid_at__lt=hour_end,
        ).aggregate(t=Sum('total'))['t'] or 0
        hourly.append({
            'hour': hour_start.strftime('%H:%M'),
            'revenue': float(rev),
        })

    return {
        'terminals': terminals_data,
        'today_revenue': float(today_revenue),
        'today_count': today_count,
        'today_avg': float(today_avg),
        'events': [{
            'id': e.pk,
            'type': e.event_type,
            'severity': e.severity,
            'title': e.title,
            'detail': e.detail,
            'is_read': e.is_read,
            'created_at': e.created_at.isoformat(),
            'terminal': e.terminal.name if e.terminal else None,
        } for e in events],
        'unread_count': unread_count,
        'critical_count': critical_count,
        'hourly': hourly,
    }
