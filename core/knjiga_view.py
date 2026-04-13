import os
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.utils import timezone
from django.conf import settings
from django.db import DatabaseError


@user_passes_test(lambda u: u.is_superuser)
def knjiga_pristupnih_podataka(request):
    """Knjiga pristupnih podataka - interno, samo za superadmina."""
    from companies.models import Company
    from django.contrib.auth.models import User
    from accounts.models import UserProfile
    from synesis.models import SynesisConfig
    from pos.models import POSTerminal, POSCashier
    from fiskalizacija.models import FiscalConfig
    from smart_import.models import CompanyMailbox

    # Companies
    all_companies = Company.objects.all().order_by('name')
    main_companies = [c for c in all_companies if not (c.oib or '').startswith('SYN-')]
    syn_companies = [c for c in all_companies if (c.oib or '').startswith('SYN-')]

    # Users
    all_users = User.objects.all().order_by('username')
    users_data = []
    for u in all_users:
        try:
            profile = UserProfile.objects.filter(user=u).first()
            company = profile.company.name if profile and profile.company else 'NO COMPANY'
            role = getattr(profile, 'role', '') if profile else ''
        except DatabaseError:
            company = 'ERROR'
            role = ''
        users_data.append({
            'username': u.username,
            'full_name': (u.first_name + ' ' + u.last_name).strip(),
            'email': u.email,
            'is_staff': u.is_staff,
            'is_superuser': u.is_superuser,
            'company': company,
            'role': role or '',
        })

    active_users = [u for u in users_data if not u['username'].startswith('syn_') and u['username'] != '__testrunner__']
    syn_users = [u for u in users_data if u['username'].startswith('syn_')]

    # Synesis configs
    synesis_data = []
    for sc in SynesisConfig.objects.select_related('company').all():
        synesis_data.append({
            'company': sc.company.name,
            'token': sc.api_token,
            'is_active': sc.is_active,
        })

    # POS
    terminals = []
    for t in POSTerminal.objects.select_related('company').all():
        terminals.append({
            'company': t.company.name,
            'name': t.name,
            'id': t.id,
            'pos_type': t.pos_type,
            'is_active': t.is_active,
        })

    cashiers = []
    for c in POSCashier.objects.select_related('company').all():
        cashiers.append({
            'company': c.company.name,
            'name': c.name,
            'is_active': c.is_active,
        })

    # Fiscal
    fiscal_data = []
    for fc in FiscalConfig.objects.select_related('company').all():
        fiscal_data.append({
            'company': fc.company.name,
            'cert_filename': getattr(fc, 'cert_filename', getattr(fc, 'certificate_file', '')),
            'is_demo': getattr(fc, 'is_demo', getattr(fc, 'test_mode', False)),
            'is_active': getattr(fc, 'is_active', True),
        })

    # Mailboxes
    mailbox_data = []
    for m in CompanyMailbox.objects.select_related('company').all():
        mailbox_data.append({
            'company': m.company.name,
            'email': m.email_address,
            'server': m.imap_server,
            'is_active': m.is_active,
        })

    # API keys from env
    dev_api_token = os.environ.get('DEV_API_TOKEN', getattr(settings, 'DEV_API_TOKEN', 'N/A'))
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', 'N/A')
    secret_key = settings.SECRET_KEY

    context = {
        'generated_at': timezone.now(),
        'companies': all_companies,
        'main_companies': main_companies,
        'syn_companies': syn_companies,
        'users': users_data,
        'active_users': active_users,
        'syn_users': syn_users,
        'synesis_configs': synesis_data,
        'terminals': terminals,
        'cashiers': cashiers,
        'fiscal_configs': fiscal_data,
        'mailboxes': mailbox_data,
        'dev_api_token': dev_api_token,
        'anthropic_key': anthropic_key,
        'secret_key': secret_key,
    }

    return render(request, 'admin/knjiga_pristupnih_podataka.html', context)


@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.role == 'company_admin'))
def knjiga_boljitaka(request):
    """Knjiga boljitaka — kompletni pregled funkcionalnosti i nadogradnji."""
    fmt = request.GET.get('format', 'html')
    from core.company_utils import get_user_company
    company = get_user_company(request)
    context = {'company': company, 'date': timezone.now().strftime('%d.%m.%Y')}

    if fmt == 'pdf':
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        html = render_to_string('core/knjiga_boljitaka.html', context)
        try:
            from xhtml2pdf import pisa
            from io import BytesIO
            buf = BytesIO()
            pisa.CreatePDF(html, dest=buf)
            buf.seek(0)
            response = HttpResponse(buf.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="LIMIT_CONNECT_Knjiga_Boljitaka_%s.pdf"' % timezone.now().strftime('%Y%m%d')
            return response
        except ImportError:
            return HttpResponse(html)

    return render(request, 'core/knjiga_boljitaka.html', context)
