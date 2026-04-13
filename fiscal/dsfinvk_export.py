"""
DSFinV-K Export — Digitale Schnittstelle der Finanzverwaltung für Kassensysteme

Generates the structured CSV ZIP archive required by German tax authorities.
KassenSichV §146a AO: must be available on-demand for Finanzamt audits.

Output: .dsfinvk ZIP containing:
  - cashpointclosing.csv (Z-Abschlüsse / daily closings)
  - transactions.csv (individual transactions)
  - lines.csv (line items per transaction)
  - payment.csv (payment types per transaction)
  - vat.csv (VAT breakdown per transaction)
  - cashregister.csv (master data)
"""
import csv
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

import logging
logger = logging.getLogger(__name__)


def export_dsfinvk(company, date_from: date, date_to: date) -> bytes:
    """
    Generate DSFinV-K compliant ZIP archive.

    Args:
        company: Company model instance
        date_from: Start date (inclusive)
        date_to: End date (inclusive)

    Returns:
        bytes: ZIP file content
    """
    from pos.models import POSReceipt, POSSession
    from fiscal.models import FiscalLog

    buf = io.BytesIO()

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. cashregister.csv — master data
        zf.writestr('cashregister.csv', _build_cashregister(company))

        # 2. Collect receipts in range
        receipts = POSReceipt.objects.filter(
            session__terminal__company=company,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).select_related(
            'session__terminal', 'cashier'
        ).prefetch_related('items').order_by('created_at')

        # 3. transactions.csv
        zf.writestr('transactions.csv', _build_transactions(receipts))

        # 4. lines.csv
        zf.writestr('lines.csv', _build_lines(receipts))

        # 5. payment.csv
        zf.writestr('payment.csv', _build_payments(receipts))

        # 6. vat.csv
        zf.writestr('vat.csv', _build_vat(receipts))

        # 7. cashpointclosing.csv (Z-Abschlüsse)
        sessions = POSSession.objects.filter(
            terminal__company=company,
            opened_at__date__gte=date_from,
            closed_at__date__lte=date_to,
            status='closed',
        ).select_related('terminal').order_by('closed_at')
        zf.writestr('cashpointclosing.csv', _build_closings(sessions))

    return buf.getvalue()


def _csv_string(header, rows):
    """Build CSV string from header + row dicts."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=header, delimiter=';',
                            quoting=csv.QUOTE_MINIMAL, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _build_cashregister(company):
    """Kassenidentifikation — master data."""
    from pos.models import POSTerminal
    header = ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'KASSE_BRAND',
              'KASSE_MODELL', 'KASSE_SERIENNR', 'KASSE_SW_BRAND',
              'KASSE_SW_VERSION', 'KASSE_BASISWAEH_CODE']
    rows = []
    for t in POSTerminal.objects.filter(company=company, is_active=True):
        rows.append({
            'Z_KASSE_ID': str(t.pk),
            'Z_ERSTELLUNG': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'Z_NR': '1',
            'KASSE_BRAND': 'LIMIT Connect',
            'KASSE_MODELL': t.pos_type or 'Standard',
            'KASSE_SERIENNR': str(t.pk)[:20],
            'KASSE_SW_BRAND': 'LIMIT Connect',
            'KASSE_SW_VERSION': '2.0',
            'KASSE_BASISWAEH_CODE': 'EUR',
        })
    return _csv_string(header, rows)


def _build_transactions(receipts):
    """Bonkopf — transaction header."""
    header = ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID', 'BON_NR',
              'BON_TYP', 'BON_NAME', 'TERMINAL_ID', 'BON_STORNO',
              'BON_START', 'BON_ENDE', 'BEDIENER_ID', 'BEDIENER_NAME',
              'UMS_BRUTTO', 'KUNDE_NAME', 'KUNDE_ID', 'KUNDE_TYP',
              'BON_NOTIZ', 'TSE_ID', 'TSE_TANR', 'TSE_TA_START',
              'TSE_TA_ENDE', 'TSE_TA_VORGANGSART', 'TSE_TA_SIGZ',
              'TSE_TA_SIG', 'TSE_TA_FEHLER', 'TSE_VORGANGSDATEN']
    rows = []
    for r in receipts:
        is_storno = r.status == 'void'
        rows.append({
            'Z_KASSE_ID': str(r.session.terminal_id),
            'Z_ERSTELLUNG': r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
            'Z_NR': '1',
            'BON_ID': str(r.pk),
            'BON_NR': r.receipt_number or '',
            'BON_TYP': 'Beleg',
            'BON_NAME': 'Kassenbon',
            'TERMINAL_ID': str(r.session.terminal_id),
            'BON_STORNO': 'J' if is_storno else 'N',
            'BON_START': r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
            'BON_ENDE': r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
            'BEDIENER_ID': str(r.cashier_id or ''),
            'BEDIENER_NAME': str(r.cashier) if r.cashier else '',
            'UMS_BRUTTO': str(r.total or 0),
            'KUNDE_NAME': '',
            'KUNDE_ID': '',
            'KUNDE_TYP': '',
            'BON_NOTIZ': '',
            'TSE_ID': '',
            'TSE_TANR': getattr(r, 'tse_transaction_number', ''),
            'TSE_TA_START': '',
            'TSE_TA_ENDE': '',
            'TSE_TA_VORGANGSART': 'Kassenbeleg-V1',
            'TSE_TA_SIGZ': '',
            'TSE_TA_SIG': getattr(r, 'tse_signature', ''),
            'TSE_TA_FEHLER': '',
            'TSE_VORGANGSDATEN': '',
        })
    return _csv_string(header, rows)


def _build_lines(receipts):
    """Bonpos — line items."""
    header = ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID', 'POS_ZEILE',
              'GUTSCHEIN_NR', 'ARTIKELTEXT', 'POS_TERMINAL_ID',
              'GV_TYP', 'GV_NAME', 'INHAUS', 'P_STORNO',
              'AGENTUR_ID', 'ART_NR', 'GTIN', 'WARENGR_ID', 'WARENGR',
              'MENGE', 'FAKTOR', 'EINHEIT', 'STK_BR']
    rows = []
    for r in receipts:
        for i, item in enumerate(r.items.all(), 1):
            rows.append({
                'Z_KASSE_ID': str(r.session.terminal_id),
                'Z_ERSTELLUNG': r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
                'Z_NR': '1',
                'BON_ID': str(r.pk),
                'POS_ZEILE': str(i),
                'GUTSCHEIN_NR': '',
                'ARTIKELTEXT': (item.description or item.name or '')[:60],
                'POS_TERMINAL_ID': str(r.session.terminal_id),
                'GV_TYP': 'Umsatz',
                'GV_NAME': 'Verkauf',
                'INHAUS': 'J',
                'P_STORNO': 'N',
                'AGENTUR_ID': '',
                'ART_NR': str(getattr(item, 'inventory_item_id', '') or ''),
                'GTIN': '',
                'WARENGR_ID': '',
                'WARENGR': '',
                'MENGE': str(item.quantity),
                'FAKTOR': '1',
                'EINHEIT': item.unit if hasattr(item, 'unit') else 'Stk',
                'STK_BR': str(item.total or 0),
            })
    return _csv_string(header, rows)


def _build_payments(receipts):
    """Zahlart — payment types."""
    header = ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID',
              'ZAHLART_TYP', 'ZAHLART_NAME', 'ZAHLWAEH_CODE', 'ZAHLWAEH_BETRAG']
    rows = []
    for r in receipts:
        pm = getattr(r, 'payment_method', 'cash') or 'cash'
        zahlart = 'Bar' if pm in ('cash', 'gotovina', 'bar') else 'Unbar'
        rows.append({
            'Z_KASSE_ID': str(r.session.terminal_id),
            'Z_ERSTELLUNG': r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
            'Z_NR': '1',
            'BON_ID': str(r.pk),
            'ZAHLART_TYP': zahlart,
            'ZAHLART_NAME': pm,
            'ZAHLWAEH_CODE': 'EUR',
            'ZAHLWAEH_BETRAG': str(r.total or 0),
        })
    return _csv_string(header, rows)


def _build_vat(receipts):
    """USt — VAT breakdown."""
    header = ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID',
              'UST_SCHLUESSEL', 'UST_SATZ', 'UST_BRUTTO', 'UST_NETTO', 'UST_UST']
    rows = []
    for r in receipts:
        for item in r.items.all():
            rate = getattr(item, 'tax_rate_value', None) or Decimal('19')
            brutto = item.total or Decimal('0')
            netto = (brutto / (1 + rate / 100)).quantize(Decimal('0.01'))
            ust = brutto - netto
            rows.append({
                'Z_KASSE_ID': str(r.session.terminal_id),
                'Z_ERSTELLUNG': r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
                'Z_NR': '1',
                'BON_ID': str(r.pk),
                'UST_SCHLUESSEL': '1' if rate >= 19 else '2',
                'UST_SATZ': str(rate),
                'UST_BRUTTO': str(brutto),
                'UST_NETTO': str(netto),
                'UST_UST': str(ust),
            })
    return _csv_string(header, rows)


def _build_closings(sessions):
    """Z-Abschlüsse — daily closings."""
    header = ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'Z_SE_ZAEHLER',
              'Z_START_BON_ID', 'Z_ENDE_BON_ID', 'FIRST_BON_ID', 'LAST_BON_ID',
              'Z_SE_BRUTTO', 'Z_SE_NETTO', 'Z_SE_UST']
    rows = []
    for i, s in enumerate(sessions, 1):
        rows.append({
            'Z_KASSE_ID': str(s.terminal_id),
            'Z_ERSTELLUNG': (s.closed_at or s.opened_at).strftime('%Y-%m-%dT%H:%M:%S'),
            'Z_NR': str(i),
            'Z_SE_ZAEHLER': str(i),
            'Z_START_BON_ID': '',
            'Z_ENDE_BON_ID': '',
            'FIRST_BON_ID': '',
            'LAST_BON_ID': '',
            'Z_SE_BRUTTO': str(getattr(s, 'total_sales', 0) or 0),
            'Z_SE_NETTO': '',
            'Z_SE_UST': '',
        })
    return _csv_string(header, rows)
