"""Superadmin: FINA certificate upload + fiscalization config."""
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from companies.models import Company

from .fisk import ping_fina
from .models import FiscalConfig

CERTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'certs')


@login_required
def config_view(request):
    if not request.user.profile.is_superadmin:
        return redirect('dashboard')

    # List all companies with their fiscal configs
    companies = Company.objects.all().order_by('name')
    rows = []
    for co in companies:
        try:
            cfg = co.fiscal_config
        except FiscalConfig.DoesNotExist:
            cfg = None
        rows.append({'company': co, 'config': cfg})

    if request.method == 'POST':
        action     = request.POST.get('action')
        company_id = request.POST.get('company_id')
        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            messages.error(request, _('Tvrtka nije pronađena.'))
            return redirect('fiskalizacija:config')

        if action == 'save':
            config, _ = FiscalConfig.objects.get_or_create(company=company)

            # Optional new cert file
            cert_file = request.FILES.get('cert_file')
            if cert_file:
                os.makedirs(CERTS_DIR, exist_ok=True)
                filename  = f'fisk_{company.oib}.p12'
                dest_path = os.path.join(CERTS_DIR, filename)
                with open(dest_path, 'wb') as fh:
                    for chunk in cert_file.chunks():
                        fh.write(chunk)
                config.cert_filename = filename

            # Update password only if provided
            pw = request.POST.get('cert_password', '').strip()
            if pw:
                config.set_password(pw)

            config.ozn_pos_pr = request.POST.get('ozn_pos_pr', '1').strip() or '1'
            config.ozn_nap_ur = request.POST.get('ozn_nap_ur', '1').strip() or '1'
            config.is_demo    = request.POST.get('is_demo') == 'on'
            config.is_active  = request.POST.get('is_active') == 'on'
            config.save()
            messages.success(request, f'Konfiguracija za {company.name} spremljena.')

        elif action == 'test':
            try:
                config = company.fiscal_config
            except FiscalConfig.DoesNotExist:
                messages.error(request, _('Nema konfiguracije za tu tvrtku.'))
                return redirect('fiskalizacija:config')
            ok = ping_fina(config.cert_path, config.get_password(), config.is_demo)
            config.last_test_ok = ok
            config.last_test_at = timezone.now()
            config.save(update_fields=['last_test_ok', 'last_test_at'])
            if ok:
                messages.success(request, '✓ Veza s FINA CIS uspješna!')
            else:
                messages.error(request, _('✗ Veza s FINA CIS nije uspjela.'))

        return redirect('fiskalizacija:config')

    return render(request, 'fiskalizacija/config.html', {
        'rows': rows,
        'page_title': 'Fiskalizacija – FINA certifikati',
    })
