"""
companies/views_modules.py
Module picker — visual grid for enabling/disabling ERP modules.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from core.company_utils import get_user_company


@login_required
def module_picker(request):
    """Module picker — visual grid with toggles."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne firme.')
        return redirect('dashboard')

    from .models import CompanyModuleConfig
    from .module_registry import get_modules_by_category, MODULES

    config, created = CompanyModuleConfig.objects.get_or_create(
        company=company,
        defaults={'enabled_modules': [m['id'] for m in MODULES if m.get('always_visible')]}
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'save':
            enabled = request.POST.getlist('modules')
            # Always include core modules
            for m in MODULES:
                if m.get('always_visible') and m['id'] not in enabled:
                    enabled.append(m['id'])
            config.enabled_modules = enabled
            config.sidebar_order = enabled  # order = selection order
            config.save()
            messages.success(request, f'Spremljeno! {len(enabled)} modula aktivno.')
            return redirect('companies:module_picker')

        elif action == 'ai_recommend':
            recommendations = _ai_recommend(company)
            config.ai_recommended = recommendations
            config.save(update_fields=['ai_recommended'])
            return render(request, 'companies/module_picker.html', {
                'categories': get_modules_by_category(),
                'config': config,
                'ai_recommendations': recommendations,
            })

    # Get counters for each module
    counters = _get_module_counters(company)

    # Inject counters into module dicts for template
    categories = get_modules_by_category()
    for cat_id, cat_data in categories.items():
        for mod in cat_data['modules']:
            mod['counter'] = counters.get(mod['id'], 0)

    return render(request, 'companies/module_picker.html', {
        'categories': categories,
        'config': config,
        'counters': counters,
    })


@login_required
def module_toggle_api(request):
    """AJAX toggle single module on/off."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    body = json.loads(request.body)
    module_id = body.get('module_id', '')
    enabled = body.get('enabled', True)

    company = get_user_company(request)
    from .models import CompanyModuleConfig
    config, _ = CompanyModuleConfig.objects.get_or_create(company=company, defaults={'enabled_modules': []})

    if enabled and module_id not in config.enabled_modules:
        config.enabled_modules.append(module_id)
    elif not enabled and module_id in config.enabled_modules:
        config.enabled_modules.remove(module_id)

    config.sidebar_order = config.enabled_modules
    config.save()

    return JsonResponse({'ok': True, 'enabled': config.enabled_modules})


def _get_module_counters(company):
    """Get record counts for modules that have counter_model."""
    from django.apps import apps
    from .module_registry import MODULES
    counters = {}
    for m in MODULES:
        cm = m.get('counter_model')
        if cm:
            try:
                app_label, model_name = cm.split('.')
                Model = apps.get_model(app_label, model_name)
                counters[m['id']] = Model.objects.filter(company=company).count()
            except Exception:
                counters[m['id']] = 0
    return counters


def _ai_recommend(company):
    """AI-based module recommendation based on company data."""
    from django.apps import apps

    # Gather signals
    signals = {}
    try:
        signals['has_invoices'] = apps.get_model('invoicing', 'Invoice').objects.filter(company=company).count() > 0
        signals['has_partners'] = apps.get_model('partners', 'Partner').objects.filter(company=company).count() > 10
        signals['has_items'] = apps.get_model('inventory', 'InventoryItem').objects.filter(company=company).count() > 0
        signals['has_employees'] = apps.get_model('worktime', 'EmployeeProfile').objects.filter(company=company).count() > 0
        signals['has_konto'] = apps.get_model('konto', 'JournalEntry').objects.filter(company=company).count() > 0
        signals['country'] = getattr(company, 'country', 'HR')
    except Exception:
        pass

    recommendations = ['dashboard', 'invoicing', 'partners']  # always

    if signals.get('has_items'):
        recommendations.extend(['inventory', 'smart_import'])
    if signals.get('has_employees'):
        recommendations.extend(['worktime', 'payroll'])
    if signals.get('has_invoices'):
        recommendations.extend(['eracun', 'konto', 'pdv_s', 'bank'])
    if signals.get('has_konto'):
        recommendations.append('documents')
    if signals.get('country') == 'HR':
        recommendations.append('eracun_inbox')

    return list(dict.fromkeys(recommendations))  # dedupe preserving order
