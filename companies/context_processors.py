from django.db import DatabaseError
"""
companies/context_processors.py
Injects sidebar_modules into every template context.
Uses companies.module_registry as single source of truth.
"""


def sidebar_modules(request):
    """Add active modules to template context for sidebar rendering."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    try:
        from core.company_utils import get_user_company
        company = get_user_company(request)
        if not company:
            return {}

        from companies.models import CompanyModuleConfig
        from companies.module_registry import (
            MODULES, CATEGORIES, get_quick_actions,
        )

        config = CompanyModuleConfig.objects.filter(company=company).first()

        # Superadmin vidi SVE module, bez ograničenja
        valid_ids = {m['id'] for m in MODULES}
        if request.user.is_superuser:
            enabled = [m['id'] for m in MODULES]
        elif config and config.enabled_modules:
            # Auto-clean stale module IDs
            enabled = [m for m in config.enabled_modules if m in valid_ids]
            if len(enabled) != len(config.enabled_modules):
                config.enabled_modules = enabled
                config.save(update_fields=['enabled_modules'])
        else:
            # Default: show all modules
            enabled = [m['id'] for m in MODULES]

        # Resolve module URLs with i18n prefix
        from django.urls import reverse, NoReverseMatch
        for m in MODULES:
            url_name = m.get('url_name', '')
            if url_name:
                try:
                    m['resolved_url'] = reverse(url_name)
                except NoReverseMatch:
                    m['resolved_url'] = m.get('url', '/')
            else:
                m['resolved_url'] = m.get('url', '/')

        # Build sidebar structure grouped by category
        grouped = []
        for cat_id, cat_info in sorted(CATEGORIES.items(), key=lambda x: x[1]['order']):
            mods = [m for m in MODULES if m.get('category') == cat_id]
            if not mods:
                continue
            # Check if any module in this category is enabled
            has_enabled = any(
                m['id'] in enabled or m.get('always_visible')
                for m in mods
            )
            grouped.append({
                'info': cat_info,
                'modules': mods,
                'has_enabled_modules': has_enabled,
            })

        # Quick actions for enabled modules
        quick_actions = get_quick_actions(enabled)

        return {
            'sidebar_modules': grouped,
            'sidebar_enabled_ids': enabled,
            'sidebar_all_modules': MODULES,
            'sidebar_quick_actions': quick_actions,
        }

    except DatabaseError:
        return {}


def memio_lang_choices(request):
    """Available languages for memio.pet lang switcher."""
    return {
        'lang_choices': [
            ('hr', '🇭🇷', 'Hrvatski'),
            ('de', '🇩🇪', 'Deutsch'),
            ('en', '🇬🇧', 'English'),
            ('tr', '🇹🇷', 'Türkçe'),
            ('el', '🇬🇷', 'Ελληνικά'),
        ]
    }
