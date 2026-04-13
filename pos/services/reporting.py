"""
POS Reporting Service — centralna logika izvještaja.

Pravila:
- Nema HTTP, nema request, nema JsonResponse — cista poslovna logika
- DB agregati (Sum, Count, annotate) umjesto Python for-petlji
- 4 SQL upita umjesto N+1
- ReportingError = greska poslovne logike
- Koristi se za cashier_full_report (HTML/PDF/JSON) i buduće izvještaje
"""
import logging
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce

logger = logging.getLogger('pos_reporting')

_ZERO = Decimal('0')


class ReportingError(Exception):
    """Greska poslovne logike izvještaja."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class ReportingService:
    """Centralni servis za POS izvještaje."""

    # ── Helper ─────────────────────────────────────────────────

    @staticmethod
    def _empty_report(session, company):
        """Prazan izvještaj za session bez računa."""
        return {
            'session': session,
            'company': company,
            'branch': session.terminal.branch,
            'business_location': session.terminal.business_location,
            'paid_receipts': [],
            'cancelled_receipts': [],
            'refunded_receipts': [],
            'payment_bd': {},
            'tax_bd': {},
            'cashier_bd': {},
            'cash_data': {
                'opening': session.opening_cash,
                'cash_sales': _ZERO,
                'deposits': _ZERO,
                'withdrawals': _ZERO,
                'expected': session.opening_cash,
                'counted': session.closing_cash or _ZERO,
                'difference': (session.closing_cash or _ZERO) - session.opening_cash,
            },
            'deposits': [],
            'total_tips': _ZERO,
            'top_items': [],
            'ai_warnings': [{'level': 'success', 'icon': 'check-circle',
                             'message': 'Sve u redu — nema anomalija u ovoj smjeni'}],
            'ai_enabled': True,
        }

    # ── Data fetching (1 query with prefetch) ──────────────────

    @staticmethod
    def _fetch_receipts(session):
        """Dohvati sve račune — 3 upita umjesto N+1."""
        paid = list(session.receipts.filter(status='paid').select_related(
            'cashier'
        ).prefetch_related(
            'items', 'items__inventory_item', 'payment_lines'
        ))
        cancelled = list(session.receipts.filter(status='cancelled'))
        refunded = list(session.receipts.filter(status='refunded'))
        return paid, cancelled, refunded

    # ── Payment breakdown (DB aggregate) ───────────────────────

    @staticmethod
    def _calc_payment_breakdown(session):
        """1 SQL upit: GROUP BY method, SUM(amount), COUNT(*)."""
        from pos.models import POSPaymentLine
        method_labels = dict(POSPaymentLine.Method.choices)

        rows = (
            POSPaymentLine.objects
            .filter(receipt__session=session, receipt__status='paid')
            .values('method')
            .annotate(count=Count('id'), total=Sum('amount'))
            .order_by('-total')
        )
        breakdown = {}
        for row in rows:
            label = method_labels.get(row['method'], row['method'])
            breakdown[label] = {
                'count': row['count'],
                'total': row['total'] or _ZERO,
            }
        return breakdown

    # ── Tax breakdown (DB aggregate) ───────────────────────────

    @staticmethod
    def _calc_tax_breakdown(session):
        """1 SQL upit: GROUP BY tax_rate, SUM base/tax/total."""
        from pos.models import POSReceiptItem

        rows = (
            POSReceiptItem.objects
            .filter(receipt__session=session, receipt__status='paid')
            .values('tax_rate')
            .annotate(
                total=Coalesce(Sum('total_price'), _ZERO, output_field=DecimalField()),
                # base = total_price / (1 + tax_rate/100) za rate > 0, inace total_price
                total_base=Coalesce(
                    Sum(
                        Case(
                            When(tax_rate__gt=0,
                                 then=F('total_price') / (Value(1) + F('tax_rate') / Value(100))),
                            default=F('total_price'),
                            output_field=DecimalField(max_digits=12, decimal_places=4),
                        )
                    ),
                    _ZERO,
                    output_field=DecimalField(),
                ),
            )
            .order_by('-tax_rate')
        )
        breakdown = {}
        for row in rows:
            rate = row['tax_rate'] if row['tax_rate'] is not None else _ZERO
            rate_str = '%s%%' % rate
            total = row['total']
            base = row['total_base']
            breakdown[rate_str] = {
                'base': base,
                'tax': total - base,
                'total': total,
            }
        return breakdown

    # ── Cashier breakdown (DB aggregate) ───────────────────────

    @staticmethod
    def _calc_cashier_breakdown(session):
        """2 SQL upita: receipts grouped by cashier + tip sums."""
        from pos.models import POSReceipt

        # Upit 1: receipts po blagajniku s payment breakdownom
        receipts = (
            POSReceipt.objects
            .filter(session=session, status='paid')
            .select_related('cashier')
            .annotate(
                cash_amt=Coalesce(
                    Sum('payment_lines__amount',
                        filter=Q(payment_lines__method='CASH')),
                    _ZERO, output_field=DecimalField()),
                card_amt=Coalesce(
                    Sum('payment_lines__amount',
                        filter=Q(payment_lines__method='CARD')),
                    _ZERO, output_field=DecimalField()),
                other_amt=Coalesce(
                    Sum('payment_lines__amount',
                        filter=~Q(payment_lines__method__in=['CASH', 'CARD'])),
                    _ZERO, output_field=DecimalField()),
                tip_amt=Coalesce(
                    Sum('items__total_price',
                        filter=Q(items__is_tip=True)),
                    _ZERO, output_field=DecimalField()),
            )
        )

        breakdown = {}
        for r in receipts:
            name = r.cashier.name if r.cashier else r.note or 'Nepoznat'
            if name not in breakdown:
                breakdown[name] = {
                    'count': 0, 'total': _ZERO,
                    'cash': _ZERO, 'card': _ZERO,
                    'other': _ZERO, 'tips': _ZERO,
                }
            breakdown[name]['count'] += 1
            breakdown[name]['total'] += r.total
            breakdown[name]['cash'] += r.cash_amt
            breakdown[name]['card'] += r.card_amt
            breakdown[name]['other'] += r.other_amt
            breakdown[name]['tips'] += r.tip_amt
        return breakdown

    # ── Cash reconciliation ────────────────────────────────────

    @staticmethod
    def _calc_cash_reconciliation(session):
        """Gotovinski promet: DB agregat za deposits."""
        from pos.models import CashDeposit

        deposits_qs = CashDeposit.objects.filter(session=session)
        agg = deposits_qs.aggregate(
            total_deposits=Coalesce(
                Sum('amount', filter=Q(deposit_type='deposit')),
                _ZERO, output_field=DecimalField()),
            total_withdrawals=Coalesce(
                Sum('amount', filter=Q(deposit_type='withdrawal')),
                _ZERO, output_field=DecimalField()),
        )

        cash_data = {
            'opening': session.opening_cash,
            'cash_sales': session.total_cash_sales,
            'deposits': agg['total_deposits'],
            'withdrawals': agg['total_withdrawals'],
            'expected': session.expected_closing_cash,
            'counted': session.closing_cash or _ZERO,
            'difference': session.cash_difference,
        }
        return cash_data, deposits_qs

    # ── Tips (DB aggregate) ────────────────────────────────────

    @staticmethod
    def _calc_total_tips(session):
        """1 SQL upit: SUM(total_price) WHERE is_tip=True."""
        from pos.models import POSReceiptItem
        result = (
            POSReceiptItem.objects
            .filter(receipt__session=session, receipt__status='paid', is_tip=True)
            .aggregate(total=Coalesce(Sum('total_price'), _ZERO, output_field=DecimalField()))
        )
        return result['total']

    # ── Top selling items (DB aggregate) ───────────────────────

    @staticmethod
    def _calc_top_items(session, limit=10):
        """1 SQL upit: GROUP BY description, SUM(total_price), ORDER BY -total."""
        from pos.models import POSReceiptItem
        rows = (
            POSReceiptItem.objects
            .filter(
                receipt__session=session,
                receipt__status='paid',
                is_tip=False,
                is_pfand_return=False,
            )
            .values('description')
            .annotate(total=Sum('total_price'))
            .order_by('-total')[:limit]
        )
        return [(row['description'] or 'Artikl', float(row['total'])) for row in rows]

    # ── AI Control ─────────────────────────────────────────────

    @staticmethod
    def _generate_ai_warnings(session, paid_count, cancelled_count,
                              cash_data, total_tips, high_discount_count):
        """AI kontrola: anomalije, upozorenja, provjere."""
        warnings = []

        # 1. Cash razlika > 5 EUR
        if abs(cash_data['difference']) > 5:
            warnings.append({
                'level': 'danger',
                'icon': 'exclamation-triangle',
                'message': 'Gotovinska razlika: %s EUR — provjeriti blagajnu!' % cash_data['difference'],
            })

        # 2. Storno > 10% računa
        total_count = paid_count + cancelled_count
        if total_count > 0 and cancelled_count / total_count > 0.1:
            warnings.append({
                'level': 'warning',
                'icon': 'ban',
                'message': '%d/%d računa stornirano (%.0f%%) — neuobičajeno visok postotak' % (
                    cancelled_count, total_count,
                    cancelled_count / total_count * 100
                ),
            })

        # 3. Veliki popusti (> 20%)
        if high_discount_count > 0:
            warnings.append({
                'level': 'warning',
                'icon': 'percentage',
                'message': '%d stavki s popustom > 20%% — provjeriti autorizaciju' % high_discount_count,
            })

        # 4. Smjena preduga (> 12h)
        if session.opened_at and session.closed_at:
            hours = (session.closed_at - session.opened_at).total_seconds() / 3600
            if hours > 12:
                warnings.append({
                    'level': 'info',
                    'icon': 'clock',
                    'message': 'Smjena trajala %.1f sati — zakonski max 10h (ArbZG §3)' % hours,
                })

        # 5. Nema napojnice (restoran)
        if session.terminal.pos_type == 'restaurant' and total_tips == 0 and paid_count > 5:
            warnings.append({
                'level': 'info',
                'icon': 'hand-holding-usd',
                'message': '%d računa bez napojnice — neuobičajeno za restoran' % paid_count,
            })

        # 6. Sve OK
        if not warnings:
            warnings.append({
                'level': 'success',
                'icon': 'check-circle',
                'message': 'Sve u redu — nema anomalija u ovoj smjeni',
            })

        return warnings

    # ── AI helpers (DB aggregate) ──────────────────────────────

    @staticmethod
    def _count_high_discounts(session):
        """Broj stavki s popustom > 20%."""
        from pos.models import POSReceiptItem
        return (
            POSReceiptItem.objects
            .filter(
                receipt__session=session,
                receipt__status='paid',
                discount_percent__gt=20,
            )
            .count()
        )

    # ── Main entry point ───────────────────────────────────────

    @classmethod
    def generate_cashier_report(cls, session, company):
        """
        Glavni motor za blagajnički izvještaj.
        Koristi DB agregate — ~8 SQL upita umjesto N+1.

        Args:
            session: POSSession (mora biti zatvorena)
            company: Company objekt

        Returns:
            dict s kompletnim kontekstom za template

        Raises:
            ReportingError: ako smjena nije zatvorena
        """
        if session.status == 'open':
            raise ReportingError('SESSION_OPEN', 'Smjena mora biti zatvorena za generiranje izvještaja.')

        # Fetch receipts (za template prikaz — prefetch)
        paid, cancelled, refunded = cls._fetch_receipts(session)

        if not paid and not cancelled:
            return cls._empty_report(session, company)

        # DB aggregate calculations
        payment_bd = cls._calc_payment_breakdown(session)
        tax_bd = cls._calc_tax_breakdown(session)
        cashier_bd = cls._calc_cashier_breakdown(session)
        cash_data, deposits = cls._calc_cash_reconciliation(session)
        total_tips = cls._calc_total_tips(session)
        top_items = cls._calc_top_items(session)

        # AI control
        from pos.models import POSSettings
        settings_obj = POSSettings.objects.filter(company=company).first()
        ai_enabled = settings_obj.cashier_report_ai_check if settings_obj else True

        ai_warnings = []
        if ai_enabled:
            high_discount_count = cls._count_high_discounts(session)
            ai_warnings = cls._generate_ai_warnings(
                session, len(paid), len(cancelled),
                cash_data, total_tips, high_discount_count
            )

        # Business location
        bl = session.terminal.business_location
        branch = session.terminal.branch

        return {
            'session': session,
            'company': company,
            'branch': branch,
            'business_location': bl,
            'paid_receipts': paid,
            'cancelled_receipts': cancelled,
            'refunded_receipts': refunded,
            'payment_bd': payment_bd,
            'tax_bd': tax_bd,
            'cashier_bd': cashier_bd,
            'cash_data': cash_data,
            'deposits': deposits,
            'total_tips': total_tips,
            'top_items': top_items,
            'ai_warnings': ai_warnings,
            'ai_enabled': ai_enabled,
        }

    @staticmethod
    def to_json(report_data):
        """Pretvori report_data u JSON-serializabilni dict."""
        return {
            'ok': True,
            'session': report_data['session'].pk,
            'payment_breakdown': {
                str(k): {'count': v['count'], 'total': str(v['total'])}
                for k, v in report_data['payment_bd'].items()
            },
            'tax_breakdown': {
                str(k): {str(kk): str(vv) for kk, vv in v.items()}
                for k, v in report_data['tax_bd'].items()
            },
            'cashier_breakdown': {
                str(k): {str(kk): str(vv) for kk, vv in v.items()}
                for k, v in report_data['cashier_bd'].items()
            },
            'cash': {str(k): str(v) for k, v in report_data['cash_data'].items()},
            'total_tips': str(report_data['total_tips']),
            'ai_warnings': report_data['ai_warnings'],
        }
