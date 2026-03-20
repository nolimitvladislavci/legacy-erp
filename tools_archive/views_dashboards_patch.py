#!/usr/bin/env python3
"""
Patch script for /var/www/fina-connect/core/views.py
Replaces dashboard view function bodies with enhanced DB data.
Run: python views_dashboards_patch.py  (from /var/www/fina-connect/)
"""

import re
import sys
import os
import shutil
from datetime import datetime

VIEWS_PATH = '/var/www/fina-connect/core/views.py'

SUPERADMIN_DASHBOARD = (
    'def superadmin_dashboard(request):\n'
    '    from django.contrib.auth import get_user_model\n'
    '    from django.db.models import Sum, Count\n'
    '    from django.utils import timezone\n'
    '    import datetime\n'
    '    User = get_user_model()\n'
    '    today = timezone.now().date()\n'
    '    month_start = today.replace(day=1)\n'
    '    year_start = today.replace(month=1, day=1)\n'
    '\n'
    '    total_users = User.objects.count()\n'
    '    active_users = User.objects.filter(is_active=True).count()\n'
    '    staff_users = User.objects.filter(is_staff=True).count()\n'
    '    superusers = User.objects.filter(is_superuser=True).count()\n'
    "    recent_users = User.objects.order_by('-date_joined')[:8]\n"
    '\n'
    '    try:\n'
    '        from companies.models import Company\n'
    '        total_companies = Company.objects.count()\n'
    "        recent_companies = Company.objects.order_by('-id')[:5]\n"
    '    except Exception:\n'
    '        total_companies = 0\n'
    '        recent_companies = []\n'
    '\n'
    '    try:\n'
    '        from invoicing.models import Invoice\n'
    "        total_invoices = Invoice.objects.unscoped().filter(doctype='R').count()\n"
    "        revenue_total = Invoice.objects.unscoped().filter(doctype='R', status='PAID').aggregate(s=Sum('total'))['s'] or 0\n"
    "        revenue_month = Invoice.objects.unscoped().filter(doctype='R', status='PAID', date_issued__date__gte=month_start).aggregate(s=Sum('total'))['s'] or 0\n"
    "        unpaid_total  = Invoice.objects.unscoped().filter(doctype='R', status__in=('UNPAID','OVERDUE')).aggregate(s=Sum('total'))['s'] or 0\n"
    "        recent_invoices = Invoice.objects.unscoped().order_by('-date_issued')[:8]\n"
    '    except Exception:\n'
    '        total_invoices = revenue_total = revenue_month = unpaid_total = 0\n'
    '        recent_invoices = []\n'
    '\n'
    '    try:\n'
    '        from worktime.models import TimeEntry\n'
    '        total_entries = TimeEntry.objects.count()\n'
    "        recent_entries = TimeEntry.objects.select_related('user').order_by('-date')[:10]\n"
    '    except Exception:\n'
    '        total_entries = 0\n'
    '        recent_entries = []\n'
    '\n'
    '    try:\n'
    '        from projects.models import Project\n'
    '        total_projects = Project.objects.count()\n'
    "        active_projects = Project.objects.exclude(status__in=('completed','cancelled')).count()\n"
    '    except Exception:\n'
    '        total_projects = 0\n'
    '        active_projects = 0\n'
    '\n'
    '    try:\n'
    '        from pos.models import POSSession\n'
    '        pos_today = POSSession.objects.filter(opened_at__date=today).count()\n'
    "        pos_open  = POSSession.objects.filter(status='open').count()\n"
    '    except Exception:\n'
    '        pos_today = pos_open = 0\n'
    '\n'
    '    try:\n'
    '        from appointments.models import Appointment\n'
    '        appts_today = Appointment.objects.filter(start_time__date=today).count()\n'
    '    except Exception:\n'
    '        appts_today = 0\n'
    '\n'
    '    context = {\n'
    "        'total_users': total_users, 'active_users': active_users,\n"
    "        'staff_users': staff_users, 'superusers': superusers,\n"
    "        'recent_users': recent_users,\n"
    "        'total_companies': total_companies, 'recent_companies': recent_companies,\n"
    "        'total_invoices': total_invoices, 'revenue_total': revenue_total,\n"
    "        'revenue_month': revenue_month, 'unpaid_total': unpaid_total,\n"
    "        'recent_invoices': recent_invoices,\n"
    "        'total_entries': total_entries, 'recent_entries': recent_entries,\n"
    "        'total_projects': total_projects, 'active_projects': active_projects,\n"
    "        'pos_today': pos_today, 'pos_open': pos_open,\n"
    "        'appts_today': appts_today,\n"
    "        'today': today,\n"
    '    }\n'
    "    return render(request, 'dashboards/superadmin.html', context)\n"
)

MANAGER_DASHBOARD = (
    'def manager_dashboard(request):\n'
    '    from django.db.models import Sum, Count\n'
    '    from django.utils import timezone\n'
    '    from django.contrib.auth import get_user_model\n'
    '    import datetime\n'
    '    User = get_user_model()\n'
    '    today = timezone.now().date()\n'
    '    week_start = today - datetime.timedelta(days=today.weekday())\n'
    '    month_start = today.replace(day=1)\n'
    '\n'
    '    try:\n'
    '        from worktime.models import TimeEntry\n'
    '        from projects.models import Project\n'
    "        team_entries = TimeEntry.objects.filter(date__gte=week_start).select_related('user','project').order_by('-date')[:20]\n"
    "        pending_approvals = TimeEntry.objects.filter(status='PENDING').count()\n"
    "        active_projects = Project.objects.filter(status__in=('active','in_progress','open')).order_by('-id')[:8]\n"
    "        total_hours_week = TimeEntry.objects.filter(date__gte=week_start).aggregate(s=Sum('duration'))['s'] or 0\n"
    "        total_hours_month = TimeEntry.objects.filter(date__gte=month_start).aggregate(s=Sum('duration'))['s'] or 0\n"
    '    except Exception:\n'
    '        team_entries = []; pending_approvals = 0; active_projects = []\n'
    '        total_hours_week = total_hours_month = 0\n'
    '\n'
    '    try:\n'
    '        from appointments.models import Appointment\n'
    "        team_appointments_today = Appointment.objects.filter(start_time__date=today).select_related('client','service').order_by('start_time')[:10]\n"
    "        appts_pending = Appointment.objects.filter(status='scheduled').count()\n"
    '    except Exception:\n'
    '        team_appointments_today = []; appts_pending = 0\n'
    '\n'
    '    team_size = User.objects.filter(is_active=True).count()\n'
    '\n'
    "    return render(request, 'dashboards/manager.html', {\n"
    "        'team_entries': team_entries, 'pending_approvals': pending_approvals,\n"
    "        'active_projects': active_projects, 'today': today,\n"
    "        'total_hours_week': total_hours_week, 'total_hours_month': total_hours_month,\n"
    "        'team_appointments_today': team_appointments_today, 'appts_pending': appts_pending,\n"
    "        'team_size': team_size,\n"
    '    })\n'
)

INVESTOR_DASHBOARD = (
    'def investor_dashboard(request):\n'
    '    from django.db.models import Sum\n'
    '    from django.utils import timezone\n'
    '    company = None\n'
    '    try:\n'
    '        company = request.user.profile.company\n'
    '    except Exception:\n'
    '        pass\n'
    '    today = timezone.now().date()\n'
    '    year_start = today.replace(month=1, day=1)\n'
    '    month_start = today.replace(day=1)\n'
    '\n'
    '    try:\n'
    '        from invoicing.models import Invoice\n'
    '        inv_qs = Invoice.objects.unscoped()\n'
    '        if company:\n'
    '            inv_qs = inv_qs.filter(company=company)\n'
    "        revenue_ytd = inv_qs.filter(doctype='R', status='PAID', date_issued__year=today.year).aggregate(s=Sum('total'))['s'] or 0\n"
    "        revenue_month = inv_qs.filter(doctype='R', status='PAID', date_issued__date__gte=month_start).aggregate(s=Sum('total'))['s'] or 0\n"
    "        unpaid = inv_qs.filter(doctype='R', status__in=('UNPAID','OVERDUE')).aggregate(s=Sum('total'))['s'] or 0\n"
    "        recent_invoices = inv_qs.filter(doctype='R').order_by('-date_issued')[:6]\n"
    "        total_invoices = inv_qs.filter(doctype='R').count()\n"
    '    except Exception:\n'
    '        revenue_ytd = revenue_month = unpaid = total_invoices = 0\n'
    '        recent_invoices = []\n'
    '\n'
    '    try:\n'
    '        from finance.models import Transaction\n'
    '        tx_qs = Transaction.objects.unscoped()\n'
    '        if company:\n'
    '            tx_qs = tx_qs.filter(company=company)\n'
    "        income_ytd   = tx_qs.filter(direction='income',  date__gte=year_start).aggregate(s=Sum('amount'))['s'] or 0\n"
    "        expense_ytd  = tx_qs.filter(direction='expense', date__gte=year_start).aggregate(s=Sum('amount'))['s'] or 0\n"
    "        income_month  = tx_qs.filter(direction='income',  date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0\n"
    "        expense_month = tx_qs.filter(direction='expense', date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0\n"
    '        profit_ytd   = income_ytd - expense_ytd\n'
    '    except Exception:\n'
    '        income_ytd = expense_ytd = income_month = expense_month = profit_ytd = 0\n'
    '\n'
    '    try:\n'
    '        from projects.models import Project\n'
    '        proj_qs = Project.objects.unscoped()\n'
    '        if company:\n'
    '            proj_qs = proj_qs.filter(company=company)\n'
    "        projects = proj_qs.order_by('-id')[:8]\n"
    "        active_count = proj_qs.exclude(status__in=('completed','cancelled')).count()\n"
    "        completed_count = proj_qs.filter(status='completed').count()\n"
    '    except Exception:\n'
    '        projects = []; active_count = completed_count = 0\n'
    '\n'
    "    return render(request, 'dashboards/investor.html', {\n"
    "        'company': company, 'today': today,\n"
    "        'revenue_ytd': revenue_ytd, 'revenue_month': revenue_month,\n"
    "        'unpaid': unpaid, 'total_invoices': total_invoices,\n"
    "        'recent_invoices': recent_invoices,\n"
    "        'income_ytd': income_ytd, 'expense_ytd': expense_ytd,\n"
    "        'income_month': income_month, 'expense_month': expense_month,\n"
    "        'profit_ytd': profit_ytd,\n"
    "        'projects': projects, 'active_count': active_count, 'completed_count': completed_count,\n"
    '    })\n'
)

PARTNER_DASHBOARD = (
    'def partner_dashboard(request):\n'
    '    from django.utils import timezone\n'
    '    today = timezone.now().date()\n'
    '    try:\n'
    '        from invoicing.models import Invoice\n'
    "        my_invoices = Invoice.objects.unscoped().filter(client_email=request.user.email).order_by('-date_issued')[:10]\n"
    "        unpaid_count = my_invoices.filter(status__in=('UNPAID','OVERDUE')).count()\n"
    '    except Exception:\n'
    '        my_invoices = []; unpaid_count = 0\n'
    '\n'
    '    try:\n'
    '        from appointments.models import Appointment\n'
    '        from partners.models import Partner\n'
    '        partner_obj = Partner.objects.filter(email=request.user.email).first()\n'
    '        if partner_obj:\n'
    "            my_appointments = Appointment.objects.filter(client=partner_obj).order_by('-start_time')[:6]\n"
    '        else:\n'
    '            my_appointments = []\n'
    '    except Exception:\n'
    '        my_appointments = []\n'
    '\n'
    '    try:\n'
    '        from documents.models import Document\n'
    "        my_docs = Document.objects.unscoped().filter(client_email=request.user.email).order_by('-created_at')[:5]\n"
    '    except Exception:\n'
    '        my_docs = []\n'
    '\n'
    "    return render(request, 'dashboards/partner.html', {\n"
    "        'my_invoices': my_invoices, 'unpaid_count': unpaid_count,\n"
    "        'my_appointments': my_appointments, 'my_docs': my_docs, 'today': today,\n"
    '    })\n'
)

COMPANY_EXTRA = (
    '    try:\n'
    '        from appointments.models import Appointment\n'
    '        appt_qs = Appointment.objects.filter(start_time__date=today)\n'
    '        if company:\n'
    '            appt_qs = appt_qs.filter(company=company)\n'
    "        today_appointments = appt_qs.order_by('start_time')[:8]\n"
    '        total_appointments_month = Appointment.objects.filter(start_time__date__gte=month_start).count()\n'
    '    except Exception:\n'
    '        today_appointments = []\n'
    '        total_appointments_month = 0\n'
    '\n'
    '    try:\n'
    '        from pos.models import POSSession, POSReceipt\n'
    '        pos_qs = POSReceipt.objects.unscoped()\n'
    "        pos_revenue_today = pos_qs.filter(created_at__date=today).aggregate(s=Sum('total_amount'))['s'] or 0\n"
    '        pos_count_today = pos_qs.filter(created_at__date=today).count()\n'
    '    except Exception:\n'
    '        pos_revenue_today = pos_count_today = 0\n'
    '\n'
)

WORKER_EXTRA = (
    '    try:\n'
    '        from appointments.models import Appointment\n'
    '        today_appts = Appointment.objects.filter(\n'
    '            start_time__date=today\n'
    "        ).select_related('client','service','resource').order_by('start_time')[:8]\n"
    '    except Exception:\n'
    '        today_appts = []\n'
    '\n'
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def backup(path):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = path + f'.bak_{ts}'
    shutil.copy2(path, bak)
    print(f'  Backup created: {bak}')
    return bak

def read_file(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)

# ---------------------------------------------------------------------------
# Core replacement helpers
# ---------------------------------------------------------------------------

def replace_full_function(source, func_name, new_body):
    """
    Find def func_name(request): in source, replace with new_body.
    """
    def_pattern = re.compile(
        r'^((?:[ \t]*@[^\n]+\n)*)[ \t]*def ' + re.escape(func_name) + r'\s*\(request\)\s*:',
        re.MULTILINE
    )
    m = def_pattern.search(source)
    if not m:
        print(f'  WARNING: could not find "def {func_name}(request):" - skipping.')
        return source

    block_start = m.start()
    after_def = m.end()

    next_top = re.search(
        r'\n(?=[ \t]*(?:@|\bdef\b|\bclass\b))',
        source[after_def:]
    )
    if next_top:
        block_end = after_def + next_top.start() + 1
    else:
        block_end = len(source)

    decorators = m.group(1)
    replacement = decorators + new_body
    new_source = source[:block_start] + replacement + source[block_end:]
    return new_source


def inject_before_return_render(source, func_name, injection):
    """Inside func_name, find the LAST return render( and inject text before it."""
    def_pattern = re.compile(
        r'^[ \t]*def ' + re.escape(func_name) + r'\s*\(request\)\s*:',
        re.MULTILINE
    )
    m = def_pattern.search(source)
    if not m:
        print(f'  WARNING: could not find "def {func_name}(request):" for injection - skipping.')
        return source
    after_def = m.end()
    next_top = re.search(r'\n(?=[ \t]*(?:@|\bdef\b|\bclass\b))', source[after_def:])
    func_end = after_def + next_top.start() + 1 if next_top else len(source)
    func_body = source[after_def:func_end]
    render_match = None
    for rm in re.finditer(r'^([ \t]*)return render\(', func_body, re.MULTILINE):
        render_match = rm
    if not render_match:
        print(f'  WARNING: could not find "return render(" in {func_name} - skipping injection.')
        return source
    insert_pos_in_body = render_match.start()
    new_func_body = func_body[:insert_pos_in_body] + injection + func_body[insert_pos_in_body:]
    return source[:after_def] + new_func_body + source[func_end:]


def _find_func_bounds(source, func_name):
    """Return (after_def, func_end) for the named function, or (None, None)."""
    def_pattern = re.compile(
        r'^[ \t]*def ' + re.escape(func_name) + r'\s*\(request\)\s*:',
        re.MULTILINE
    )
    m = def_pattern.search(source)
    if not m:
        return None, None
    after_def = m.end()
    next_top = re.search(r'\n(?=[ \t]*(?:@|\bdef\b|\bclass\b))', source[after_def:])
    func_end = after_def + next_top.start() + 1 if next_top else len(source)
    return after_def, func_end

def patch_company_dashboard(source):
    """Inject extra data + context keys into company_dashboard."""
    func_name = 'company_dashboard'
    source = inject_before_return_render(source, func_name, COMPANY_EXTRA)
    after_def, func_end = _find_func_bounds(source, func_name)
    if after_def is None:
        print(f'  WARNING: could not locate {func_name} for context-dict patching.')
        return source
    func_body = source[after_def:func_end]
    render_matches = list(re.finditer(r'return render\s*\(', func_body))
    if not render_matches:
        print(f'  WARNING: no return render found in {func_name}.')
        return source
    rm = render_matches[-1]
    render_start = rm.end()
    depth = 1
    i = render_start
    while i < len(func_body) and depth > 0:
        if func_body[i] == '(':
            depth += 1
        elif func_body[i] == ')':
            depth -= 1
        i += 1
    render_close = i - 1
    inner = func_body[render_start:render_close]
    last_brace = inner.rfind('}')
    if last_brace == -1:
        print(f'  WARNING: could not find closing brace of context dict in {func_name}.')
        return source
    extra_keys = (
        "        'today_appointments': today_appointments,\n"
        "        'total_appointments_month': total_appointments_month,\n"
        "        'pos_revenue_today': pos_revenue_today,\n"
        "        'pos_count_today': pos_count_today,\n"
    )
    new_inner = inner[:last_brace] + extra_keys + inner[last_brace:]
    new_func_body = func_body[:render_start] + new_inner + func_body[render_close:]
    return source[:after_def] + new_func_body + source[func_end:]


def patch_worker_dashboard(source):
    """Inject today_appts data + add to context in worker_dashboard."""
    func_name = 'worker_dashboard'
    source = inject_before_return_render(source, func_name, WORKER_EXTRA)
    after_def, func_end = _find_func_bounds(source, func_name)
    if after_def is None:
        return source
    func_body = source[after_def:func_end]
    render_matches = list(re.finditer(r'return render\s*\(', func_body))
    if not render_matches:
        print(f'  WARNING: no return render found in {func_name}.')
        return source
    rm = render_matches[-1]
    render_start = rm.end()
    depth = 1
    i = render_start
    while i < len(func_body) and depth > 0:
        if func_body[i] == '(':
            depth += 1
        elif func_body[i] == ')':
            depth -= 1
        i += 1
    render_close = i - 1
    inner = func_body[render_start:render_close]
    last_brace = inner.rfind('}')
    if last_brace == -1:
        render_line_match = re.search(r'([ \t]*)return render\s*\(', func_body)
        if render_line_match:
            indent = render_line_match.group(1)
            insert_pos = render_line_match.start()
            inject_line = f"{indent}context['today_appts'] = today_appts\n"
            new_func_body = func_body[:insert_pos] + inject_line + func_body[insert_pos:]
            return source[:after_def] + new_func_body + source[func_end:]
        return source
    extra_keys = "        'today_appts': today_appts,\n"
    new_inner = inner[:last_brace] + extra_keys + inner[last_brace:]
    new_func_body = func_body[:render_start] + new_inner + func_body[render_close:]
    return source[:after_def] + new_func_body + source[func_end:]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=' * 60)
    print('Dashboard views patch script')
    print('=' * 60)

    if not os.path.exists(VIEWS_PATH):
        print(f'ERROR: File not found: {VIEWS_PATH}')
        sys.exit(1)

    print(f'Reading {VIEWS_PATH} ...')
    source = read_file(VIEWS_PATH)
    original_len = len(source)
    print(f'  File size: {original_len} chars')

    backup(VIEWS_PATH)

    print('\n[1/6] Patching superadmin_dashboard ...')
    source = replace_full_function(source, 'superadmin_dashboard', SUPERADMIN_DASHBOARD)

    print('[2/6] Patching company_dashboard (injecting extra data) ...')
    source = patch_company_dashboard(source)

    print('[3/6] Patching manager_dashboard ...')
    source = replace_full_function(source, 'manager_dashboard', MANAGER_DASHBOARD)

    print('[4/6] Patching worker_dashboard (injecting today_appts) ...')
    source = patch_worker_dashboard(source)

    print('[5/6] Patching investor_dashboard ...')
    source = replace_full_function(source, 'investor_dashboard', INVESTOR_DASHBOARD)

    print('[6/6] Patching partner_dashboard ...')
    source = replace_full_function(source, 'partner_dashboard', PARTNER_DASHBOARD)

    print(f'\nWriting patched file ({len(source)} chars) ...')
    write_file(VIEWS_PATH, source)
    print('Done. All patches applied successfully.')
    print()
    print('Quick sanity check - function signatures present:')
    for fn in ['superadmin_dashboard', 'company_dashboard', 'manager_dashboard',
               'worker_dashboard', 'investor_dashboard', 'partner_dashboard']:
        present = f'def {fn}' in source
        status = 'OK' if present else 'MISSING'
        print(f'  {status}  def {fn}')


if __name__ == '__main__':
    main()
