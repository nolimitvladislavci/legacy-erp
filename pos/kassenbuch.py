"""
Blagajnicki dnevnik / Kassenbuch — dnevni gotovinski izvjestaj.

HR: Blagajnicki dnevnik (obavezno za firme s gotovinskim prometom)
DE: Kassenbuch (KassenSichV §146 AO)

Generira PDF/XLSX s dnevnim pregledom uplata/isplata iz blagajne.

Usage:
    from pos.kassenbuch import generate_kassenbuch
    xlsx = generate_kassenbuch(company, date_from, date_to)
"""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill


def generate_kassenbuch(company, date_from=None, date_to=None):
    """
    Blagajnicki dnevnik — dnevni gotovinski promet.

    Svaki red = jedan dan. Stupci:
    Datum | Pocetno stanje | Priljevi (gotovina) | Odljevi | Polozi | Podizanja | Zavrsno stanje
    """
    from pos.models import POSSession, POSReceipt, POSPaymentLine, CashDeposit

    if not date_from:
        date_from = date.today().replace(day=1)
    if not date_to:
        date_to = date.today()

    is_de = company.country in ('DE', 'AT')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Kassenbuch' if is_de else 'Blagajnicki dnevnik'

    bold = Font(bold=True, size=10)
    header_font = Font(bold=True, size=14)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    gold_fill = PatternFill(start_color='F5E6B8', end_color='F5E6B8', fill_type='solid')

    # Header
    ws.merge_cells('A1:H1')
    title = 'KASSENBUCH' if is_de else 'BLAGAJNICKI DNEVNIK'
    ws['A1'] = title
    ws['A1'].font = header_font
    ws['A1'].alignment = Alignment(horizontal='center')

    ws['A3'] = ('Unternehmen:' if is_de else 'Tvrtka:') + ' ' + company.name
    ws['A4'] = ('USt-IdNr.:' if is_de else 'OIB:') + ' ' + (company.vat_id or company.oib)
    ws['A5'] = ('Zeitraum:' if is_de else 'Razdoblje:') + ' %s — %s' % (
        date_from.strftime('%d.%m.%Y'), date_to.strftime('%d.%m.%Y'))

    # Column headers
    row = 7
    if is_de:
        headers = ['Datum', 'Anfangsbestand', 'Bareinnahmen', 'Barausgaben',
                   'Einzahlung (Bank)', 'Entnahme', 'Endbestand', 'Belege']
    else:
        headers = ['Datum', 'Pocetno stanje', 'Gotovinski priljevi', 'Gotovinski odljevi',
                   'Polog u sef/banku', 'Podizanje', 'Zavrsno stanje', 'Broj bonova']

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = bold
        cell.border = border
        cell.fill = gold_fill

    # Data — iterate each day
    current_date = date_from
    running_balance = Decimal('0')
    grand_income = Decimal('0')
    grand_expense = Decimal('0')

    while current_date <= date_to:
        # Find sessions for this day
        sessions = POSSession.objects.filter(
            terminal__company=company,
            opened_at__date=current_date,
        )

        if not sessions.exists():
            current_date += timedelta(days=1)
            continue

        # Opening cash = first session's opening_cash
        opening = sessions.order_by('opened_at').first().opening_cash or Decimal('0')
        if running_balance == 0:
            running_balance = opening

        # Cash receipts (gotovinski priljevi)
        cash_income = POSPaymentLine.objects.filter(
            receipt__session__in=sessions,
            receipt__status='paid',
            method='CASH',
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        # Cash refunds/returns (gotovinski odljevi)
        cash_expense = POSPaymentLine.objects.filter(
            receipt__session__in=sessions,
            receipt__status__in=['refunded', 'cancelled'],
            method='CASH',
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        # Deposits and withdrawals
        try:
            deposits = sessions.first().cash_deposits.filter(
                deposit_type='deposit'
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
            withdrawals = sessions.first().cash_deposits.filter(
                deposit_type='withdrawal'
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        except (ValueError, TypeError):
            deposits = Decimal('0')
            withdrawals = Decimal('0')

        # Receipt count
        receipt_count = POSReceipt.objects.filter(
            session__in=sessions, status='paid',
        ).count()

        # Calculate closing
        closing = running_balance + cash_income - cash_expense + deposits - withdrawals

        # Write row
        row += 1
        ws.cell(row=row, column=1, value=current_date.strftime('%d.%m.%Y')).border = border
        ws.cell(row=row, column=2, value=float(running_balance)).border = border
        ws.cell(row=row, column=2).number_format = '#,##0.00'
        ws.cell(row=row, column=3, value=float(cash_income)).border = border
        ws.cell(row=row, column=3).number_format = '#,##0.00'
        ws.cell(row=row, column=4, value=float(cash_expense)).border = border
        ws.cell(row=row, column=4).number_format = '#,##0.00'
        ws.cell(row=row, column=5, value=float(deposits)).border = border
        ws.cell(row=row, column=5).number_format = '#,##0.00'
        ws.cell(row=row, column=6, value=float(withdrawals)).border = border
        ws.cell(row=row, column=6).number_format = '#,##0.00'
        ws.cell(row=row, column=7, value=float(closing)).border = border
        ws.cell(row=row, column=7).number_format = '#,##0.00'
        ws.cell(row=row, column=8, value=receipt_count).border = border

        grand_income += cash_income
        grand_expense += cash_expense
        running_balance = closing
        current_date += timedelta(days=1)

    # Totals
    row += 1
    ws.cell(row=row, column=1, value='UKUPNO' if not is_de else 'GESAMT').font = bold
    ws.cell(row=row, column=1).border = border
    ws.cell(row=row, column=3, value=float(grand_income)).font = bold
    ws.cell(row=row, column=3).border = border
    ws.cell(row=row, column=3).number_format = '#,##0.00'
    ws.cell(row=row, column=7, value=float(running_balance)).font = bold
    ws.cell(row=row, column=7).border = border
    ws.cell(row=row, column=7).number_format = '#,##0.00'

    # Footer
    row += 3
    ws.cell(row=row, column=1, value='Datum: %s' % date.today().strftime('%d.%m.%Y'))
    ws.cell(row=row, column=5, value='Unterschrift / Potpis: _________________')
    row += 1
    ws.cell(row=row, column=1, value='LIMIT Connect ERP — limit-connect.com').font = Font(size=8, color='888888')

    # Column widths
    for c, w in [('A', 14), ('B', 16), ('C', 16), ('D', 16), ('E', 16), ('F', 14), ('G', 16), ('H', 10)]:
        ws.column_dimensions[c].width = w

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
