"""
EU Fund reports generator — timesheet, in-kind report, godisnje izvjesce.

Usage:
    from worktime.services.eu_reports import (
        generate_volunteer_timesheet,
        generate_inkind_report,
        generate_annual_volunteer_report,
    )
"""
import io
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill


def generate_volunteer_timesheet(company, user, month, year, project_code='', skip_audit=False):
    """
    Generira EU-kompatibilan timesheet za volontera (PDF-ready XLSX).
    Obavezan dokument za EU reviziju: potpis, projekt, sati, monetizacija.

    Uključuje 3 EU audit provjere (osim ako skip_audit=True):
    1. Double-Dipping — preklapanje sati
    2. Mjesečni fond — max radni dani × 8h
    3. Potpisi — approved_by + approved_at obavezni
    """
    from worktime.models import TimeEntry, EmployeeProfile

    profile = getattr(user, 'employeeprofile', None)
    hourly_value = profile.volunteer_hourly_value if profile else Decimal('5.00')

    entries = TimeEntry.objects.filter(
        user=user, company=company,
        date__year=year, date__month=month,
        is_volunteer_work=True, status='APPROVED',
    ).order_by('date')

    if project_code:
        entries = entries.filter(grant_project_code=project_code)

    entries_list = list(entries)

    # EU Audit Guard — 3 nagazne mine
    if not skip_audit and entries_list:
        try:
            from worktime.services.eu_audit_guard import EUAuditGuard
            EUAuditGuard.pre_export_audit(user, year, month, entries_list)
        except ImportError as e:
            # Logira ali ne blokira — caller odlučuje da li je fatal
            import logging
            logging.getLogger('eu_audit').warning('EU audit warning: %s', e)
            # Dodajemo warning u output
            audit_warning = str(e)
        else:
            audit_warning = None
    else:
        audit_warning = None

    wb = Workbook()
    ws = wb.active
    ws.title = 'Timesheet'

    bold = Font(bold=True, size=10)
    header_font = Font(bold=True, size=14)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    # Header
    ws.merge_cells('A1:G1')
    ws['A1'] = 'EVIDENCIJA VOLONTERSKOG RADA — TIMESHEET'
    ws['A1'].font = header_font
    ws['A1'].alignment = Alignment(horizontal='center')

    ws['A3'] = 'Organizacija:'
    ws['B3'] = company.name
    ws['A4'] = 'OIB organizacije:'
    ws['B4'] = company.oib
    ws['A5'] = 'Volonter:'
    ws['B5'] = user.get_full_name() or user.username
    ws['A6'] = 'OIB volontera:'
    ws['B6'] = profile.tax_id if profile else ''
    ws['A7'] = 'Sifra EU projekta:'
    ws['B7'] = project_code or 'N/A'
    ws['A8'] = 'Mjesec/Godina:'
    ws['B8'] = '%02d/%d' % (month, year)
    ws['A9'] = 'Satnica (EUR/h):'
    ws['B9'] = float(hourly_value)
    ws['A10'] = 'Ugovor o volontiranju:'
    ws['B10'] = str(profile.volunteer_contract_date) if profile and profile.volunteer_contract_date else 'NEDOSTAJE!'

    for r in range(3, 11):
        ws.cell(row=r, column=1).font = bold

    # Table header
    row = 12
    headers = ['Datum', 'Od', 'Do', 'Sati', 'Opis aktivnosti', 'Projekt', 'Vrijednost (EUR)']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = bold
        cell.border = border
        cell.fill = PatternFill(start_color='E8E8E8', end_color='E8E8E8', fill_type='solid')

    total_hours = Decimal('0')
    total_value = Decimal('0')

    for entry in entries:
        row += 1
        ws.cell(row=row, column=1, value=entry.date.strftime('%d.%m.%Y.')).border = border
        ws.cell(row=row, column=2, value=str(entry.start_time or '')).border = border
        ws.cell(row=row, column=3, value=str(entry.end_time or '')).border = border
        ws.cell(row=row, column=4, value=float(entry.duration)).border = border
        ws.cell(row=row, column=5, value=entry.description[:80]).border = border
        ws.cell(row=row, column=6, value=entry.grant_project_code).border = border
        ws.cell(row=row, column=7, value=float(entry.grant_monetary_value)).border = border
        ws.cell(row=row, column=7).number_format = '#,##0.00'
        total_hours += entry.duration
        total_value += entry.grant_monetary_value

    # Totals
    row += 1
    ws.cell(row=row, column=3, value='UKUPNO:').font = bold
    ws.cell(row=row, column=3).border = border
    ws.cell(row=row, column=4, value=float(total_hours)).font = bold
    ws.cell(row=row, column=4).border = border
    ws.cell(row=row, column=7, value=float(total_value)).font = bold
    ws.cell(row=row, column=7).border = border
    ws.cell(row=row, column=7).number_format = '#,##0.00'

    # Audit warning (ako postoji)
    if audit_warning:
        row += 2
        ws.cell(row=row, column=1, value='UPOZORENJE / WARNUNG:')
        ws.cell(row=row, column=1).font = Font(bold=True, color='FF0000', size=10)
        row += 1
        ws.cell(row=row, column=1, value=str(audit_warning)[:200])
        ws.cell(row=row, column=1).font = Font(color='FF0000', size=9)

    # ── Potpisni blok (EU Audit Trail) ──
    # Dvostruki: HR + DE za međunarodne projekte
    row += 3
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    ws.cell(row=row, column=1, value=(
        'Izjavljujem pod kaznenom i materijalnom odgovornošću da su navedeni sati '
        'stvarno odrađeni na navedenom projektu.'
    ))
    ws.cell(row=row, column=1).font = Font(italic=True, size=8)
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    ws.cell(row=row, column=1, value=(
        'Ich erkläre unter strafrechtlicher und materieller Verantwortung, dass die '
        'angegebenen Stunden tatsächlich im genannten Projekt geleistet wurden.'
    ))
    ws.cell(row=row, column=1).font = Font(italic=True, size=8, color='666666')

    row += 2
    ws.cell(row=row, column=1, value='Potpis volontera / Unterschrift Freiwillige(r):')
    ws.cell(row=row, column=1).font = bold
    ws.cell(row=row, column=5, value='Potpis voditelja / Unterschrift Projektleiter(in):')
    ws.cell(row=row, column=5).font = bold
    row += 2
    ws.cell(row=row, column=1, value='_________________________')
    ws.cell(row=row, column=5, value='_________________________')
    row += 1
    ws.cell(row=row, column=1, value=user.get_full_name())
    if profile and profile.tax_id:
        ws.cell(row=row, column=2, value='OIB: %s' % profile.tax_id)

    # Voditelj — izvuci iz approved_by zadnjeg entry-ja
    approver_name = ''
    approved_timestamp = ''
    if entries_list:
        last_approved = next((e for e in reversed(entries_list) if e.approved_by), None)
        if last_approved:
            approver_name = last_approved.approved_by.get_full_name() or last_approved.approved_by.username
            if last_approved.approved_at:
                approved_timestamp = last_approved.approved_at.strftime('%d.%m.%Y. %H:%M:%S')
    ws.cell(row=row, column=5, value=approver_name or 'M.P.')

    row += 1
    ws.cell(row=row, column=5, value='Datum odobrenja: %s' % (approved_timestamp or '__.__.____'))
    ws.cell(row=row, column=5).font = Font(size=8, color='666666')

    row += 2
    ws.cell(row=row, column=1, value='Generirano / Erstellt: %s | LIMIT Connect v2026.03' % (
        timezone.now().strftime('%d.%m.%Y. %H:%M')
    ))
    ws.cell(row=row, column=1).font = Font(size=7, color='999999')

    # Column widths
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 8
    ws.column_dimensions['C'].width = 8
    ws.column_dimensions['D'].width = 8
    ws.column_dimensions['E'].width = 40
    ws.column_dimensions['F'].width = 18
    ws.column_dimensions['G'].width = 15

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_inkind_report(company, year, quarter=None):
    """
    EU In-Kind Contribution Report — kvartalni za eKohezija.
    Svi volonterski sati monetizirani po projektu.
    """
    from worktime.models import TimeEntry

    filters = {
        'company': company,
        'is_volunteer_work': True,
        'date__year': year,
        'status': 'APPROVED',
    }
    if quarter:
        month_start = (quarter - 1) * 3 + 1
        month_end = quarter * 3
        filters['date__month__gte'] = month_start
        filters['date__month__lte'] = month_end

    entries = TimeEntry.objects.filter(**filters)

    # Group by project
    by_project = entries.values('grant_project_code').annotate(
        total_hours=Sum('duration'),
        total_value=Sum('grant_monetary_value'),
        volunteer_count=Count('user', distinct=True),
    ).order_by('grant_project_code')

    wb = Workbook()
    ws = wb.active
    ws.title = 'In-Kind Report'

    bold = Font(bold=True, size=10)
    header_font = Font(bold=True, size=14)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    ws.merge_cells('A1:F1')
    ws['A1'] = 'EU IN-KIND CONTRIBUTION REPORT — VOLUNTEER HOURS'
    ws['A1'].font = header_font

    period = 'Q%d/%d' % (quarter, year) if quarter else str(year)
    ws['A3'] = 'Organisation: %s (OIB: %s)' % (company.name, company.oib)
    ws['A4'] = 'Period: %s' % period

    row = 6
    headers = ['Project Code', 'Volunteers', 'Total Hours', 'Hourly Rate (EUR)', 'Total Value (EUR)', 'Method']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = bold
        cell.border = border

    grand_hours = Decimal('0')
    grand_value = Decimal('0')

    for proj in by_project:
        row += 1
        code = proj['grant_project_code'] or 'Bez projekta'
        hours = proj['total_hours'] or Decimal('0')
        value = proj['total_value'] or Decimal('0')
        rate = value / hours if hours else Decimal('0')

        ws.cell(row=row, column=1, value=code).border = border
        ws.cell(row=row, column=2, value=proj['volunteer_count']).border = border
        ws.cell(row=row, column=3, value=float(hours)).border = border
        ws.cell(row=row, column=4, value=float(rate)).border = border
        ws.cell(row=row, column=4).number_format = '#,##0.00'
        ws.cell(row=row, column=5, value=float(value)).border = border
        ws.cell(row=row, column=5).number_format = '#,##0.00'
        ws.cell(row=row, column=6, value='Unit cost (EC Decision)').border = border
        grand_hours += hours
        grand_value += value

    row += 1
    ws.cell(row=row, column=2, value='TOTAL').font = bold
    ws.cell(row=row, column=3, value=float(grand_hours)).font = bold
    ws.cell(row=row, column=5, value=float(grand_value)).font = bold
    ws.cell(row=row, column=5).number_format = '#,##0.00'

    row += 3
    ws.cell(row=row, column=1, value='Certified by: _________________________')
    ws.cell(row=row+1, column=1, value='Date: %s' % date.today().strftime('%d.%m.%Y.'))

    for c in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws.column_dimensions[c].width = 18

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_annual_volunteer_report(company, year):
    """
    Godisnje izvjesce za Ministarstvo rada o volontiranju.
    Rok: 31. ozujka za prethodnu godinu.
    Sadrzaj: broj volontera, sati, dobne skupine, aktivnosti.
    """
    from worktime.models import TimeEntry, EmployeeProfile
    from django.contrib.auth.models import User

    # Svi volonteri ove firme koji su radili ove godine
    volunteer_profiles = EmployeeProfile.objects.filter(
        company=company, is_volunteer=True,
    ).select_related('user')

    volunteer_users = [p.user for p in volunteer_profiles]

    entries = TimeEntry.objects.filter(
        user__in=volunteer_users,
        company=company,
        is_volunteer_work=True,
        date__year=year,
        status='APPROVED',
    )

    total_hours = entries.aggregate(s=Sum('duration'))['s'] or Decimal('0')
    total_value = entries.aggregate(s=Sum('grant_monetary_value'))['s'] or Decimal('0')

    # Per-volunteer breakdown
    per_volunteer = entries.values('user__first_name', 'user__last_name', 'user__pk').annotate(
        hours=Sum('duration'),
        value=Sum('grant_monetary_value'),
    ).order_by('-hours')

    # Per task type
    per_type = entries.values('task_type').annotate(
        hours=Sum('duration'),
        count=Count('id'),
    ).order_by('-hours')

    # Per month
    per_month = entries.values('date__month').annotate(
        hours=Sum('duration'),
    ).order_by('date__month')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Godisnje izvjesce'

    bold = Font(bold=True, size=10)
    header_font = Font(bold=True, size=14)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    gold_fill = PatternFill(start_color='F5E6B8', end_color='F5E6B8', fill_type='solid')

    ws.merge_cells('A1:F1')
    ws['A1'] = 'GODISNJE IZVJESCE O VOLONTIRANJU'
    ws['A1'].font = header_font
    ws['A1'].alignment = Alignment(horizontal='center')

    ws['A3'] = 'Organizacija: %s' % company.name
    ws['A4'] = 'OIB: %s' % company.oib
    ws['A5'] = 'Godina: %d' % year
    ws['A6'] = 'Datum izvjesca: %s' % date.today().strftime('%d.%m.%Y.')
    ws['A7'] = 'Rok predaje: 31.03.%d.' % (year + 1)

    # Sumarno
    row = 9
    ws.cell(row=row, column=1, value='SUMARNO').font = Font(bold=True, size=12)
    row += 1
    summary = [
        ('Ukupno volontera:', len(volunteer_users)),
        ('Ukupno sati:', float(total_hours)),
        ('Monetizirana vrijednost (EUR):', float(total_value)),
        ('S ugovorom o volontiranju:', sum(1 for p in volunteer_profiles if p.volunteer_contract_date)),
        ('Bez ugovora:', sum(1 for p in volunteer_profiles if not p.volunteer_contract_date)),
    ]
    for label, val in summary:
        ws.cell(row=row, column=1, value=label).font = bold
        ws.cell(row=row, column=2, value=val)
        row += 1

    # Per volunteer table
    row += 1
    ws.cell(row=row, column=1, value='VOLONTERI — PREGLED PO OSOBAMA').font = Font(bold=True, size=12)
    row += 1
    for col, h in enumerate(['Ime i prezime', 'Sati', 'Vrijednost (EUR)'], 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = bold
        cell.border = border
        cell.fill = gold_fill

    for v in per_volunteer:
        row += 1
        name = '%s %s' % (v['user__first_name'] or '', v['user__last_name'] or '')
        ws.cell(row=row, column=1, value=name.strip()).border = border
        ws.cell(row=row, column=2, value=float(v['hours'])).border = border
        ws.cell(row=row, column=3, value=float(v['value'])).border = border
        ws.cell(row=row, column=3).number_format = '#,##0.00'

    # Per month
    row += 2
    ws.cell(row=row, column=1, value='MJESECNI PREGLED').font = Font(bold=True, size=12)
    row += 1
    months_hr = ['Sijecanj','Veljaca','Ozujak','Travanj','Svibanj','Lipanj',
                 'Srpanj','Kolovoz','Rujan','Listopad','Studeni','Prosinac']
    for m in per_month:
        row += 1
        ws.cell(row=row, column=1, value=months_hr[m['date__month']-1]).border = border
        ws.cell(row=row, column=2, value=float(m['hours'])).border = border

    # Per activity type
    row += 2
    ws.cell(row=row, column=1, value='AKTIVNOSTI PO VRSTI').font = Font(bold=True, size=12)
    row += 1
    for t in per_type:
        row += 1
        ws.cell(row=row, column=1, value=t['task_type']).border = border
        ws.cell(row=row, column=2, value=float(t['hours'])).border = border
        ws.cell(row=row, column=3, value=t['count']).border = border

    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 18

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
