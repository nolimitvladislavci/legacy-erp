"""
fina-connect — Module Launcher | /hr/moduli/
Visual launcher: ikona + ime + opis → klik otvara modul direktno.

Source: companies.module_registry.MODULES + ModuleLink DB (uniportal)
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


CATEGORY_LABELS = {
    'core':          ('🏠', 'Osnovno'),
    'dokumenti':     ('📄', 'Dokumenti'),
    'financije':     ('💶', 'Financije'),
    'poslovanje':    ('💼', 'Poslovanje'),
    'zaposlenici':   ('👥', 'Zaposlenici'),
    'vertikale':     ('🏗️', 'Vertikale'),
    'javne_ustanove':('🏛️', 'Javne ustanove'),
    'komunalno_kat': ('♻️', 'Komunalno'),
    'turizam':       ('🏖️', 'Turizam'),
    'integracije':   ('🔌', 'Integracije'),
    'ai':            ('🧠', 'AI & Automatizacija'),
    'pravne_usluge': ('⚖️', 'Pravne usluge'),
}

CATEGORY_ORDER = [
    'core', 'dokumenti', 'financije', 'poslovanje', 'zaposlenici',
    'vertikale', 'javne_ustanove', 'komunalno_kat', 'turizam',
    'ai', 'integracije', 'pravne_usluge',
]

# FontAwesome → emoji mapping for icon display
FA_TO_EMOJI = {
    'fa-tachometer-alt': '📊', 'fa-file-invoice-dollar': '🧾', 'fa-file-invoice': '📄',
    'fa-archive': '🗂️', 'fa-receipt': '🧾', 'fa-cash-register': '🛒',
    'fa-users': '👥', 'fa-user-tie': '👔', 'fa-building': '🏢',
    'fa-handshake': '🤝', 'fa-gavel': '⚖️', 'fa-bell': '🔔',
    'fa-layer-group': '📦', 'fa-hammer': '🔨', 'fa-hotel': '🏨',
    'fa-shopping-bag': '🛍️', 'fa-seedling': '🌱', 'fa-paw': '🐾',
    'fa-robot': '🤖', 'fa-brain': '🧠', 'fa-shield-alt': '🛡️',
    'fa-check-circle': '✅', 'fa-globe': '🌐', 'fa-plug': '🔌',
    'fa-landmark': '🏛️', 'fa-recycle': '♻️', 'fa-umbrella-beach': '🏖️',
    'fa-euro-sign': '💶', 'fa-briefcase': '💼', 'fa-home': '🏠',
    'fa-th': '⊞', 'fa-cog': '⚙️', 'fa-star': '⭐', 'fa-heart': '❤️',
    'fa-calendar': '📅', 'fa-map-marker-alt': '📍', 'fa-phone': '📞',
    'fa-envelope': '✉️', 'fa-search': '🔍', 'fa-chart-bar': '📊',
    'fa-truck': '🚛', 'fa-warehouse': '🏭', 'fa-tools': '🔧',
    'fa-graduation-cap': '🎓', 'fa-book': '📚', 'fa-newspaper': '📰',
    'fa-music': '🎵', 'fa-camera': '📷', 'fa-video': '🎬',
    'fa-dog': '🐕', 'fa-horse': '🐴', 'fa-leaf': '🍃',
    'fa-flask': '🧪', 'fa-microscope': '🔬', 'fa-stethoscope': '🩺',
    'fa-hospital': '🏥', 'fa-child': '👶', 'fa-female': '👩',
    'fa-male': '👨', 'fa-gamepad': '🎮', 'fa-dumbbell': '💪',
    'fa-futbol': '⚽', 'fa-swimming-pool': '🏊', 'fa-paint-brush': '🎨',
    'fa-store': '🏪', 'fa-industry': '🏭', 'fa-water': '💧',
    'fa-bolt': '⚡', 'fa-fire': '🔥', 'fa-sun': '☀️', 'fa-moon': '🌙',
}


def _fa_to_emoji(icon_str):
    """Pretvori FontAwesome klasu u emoji."""
    if not icon_str:
        return '📦'
    # Already emoji
    if not icon_str.startswith('fa-'):
        return icon_str
    return FA_TO_EMOJI.get(icon_str, '📦')


@login_required
def launcher(request):
    """Launcher stranica — sve ikone + opis + klik → modul."""
    from companies.module_registry import MODULES, CATEGORIES, get_modules_by_category

    q = request.GET.get('q', '').strip().lower()
    cat = request.GET.get('cat', '')

    # Filter modules
    all_modules = MODULES
    if q:
        all_modules = [
            m for m in all_modules
            if q in m.get('name', '').lower()
            or q in m.get('description', '').lower()
            or q in m.get('id', '').lower()
        ]
    if cat:
        all_modules = [m for m in all_modules if m.get('category') == cat]

    # Group by category
    grouped = {}
    for mod in all_modules:
        c = mod.get('category', 'core')
        if c not in grouped:
            grouped[c] = []
        # Enrich with emoji
        mod_copy = dict(mod)
        mod_copy['emoji'] = _fa_to_emoji(mod.get('icon', ''))
        # Resolve URL
        url = mod.get('url', '/')
        if not url.startswith('/'):
            url = f'/hr/{url}'
        mod_copy['resolved_url'] = url
        grouped[c].append(mod_copy)

    # Sort groups
    ordered_groups = []
    for cat_key in CATEGORY_ORDER:
        if cat_key in grouped:
            cat_info = CATEGORIES.get(cat_key, {})
            icon, label = CATEGORY_LABELS.get(cat_key, ('📦', cat_key))
            ordered_groups.append({
                'key': cat_key,
                'icon': icon,
                'label': cat_info.get('name', label),
                'modules': grouped[cat_key],
            })
    for cat_key, mods in grouped.items():
        if cat_key not in CATEGORY_ORDER:
            cat_info = CATEGORIES.get(cat_key, {})
            icon, label = CATEGORY_LABELS.get(cat_key, ('📦', cat_key))
            ordered_groups.append({
                'key': cat_key,
                'icon': icon,
                'label': cat_info.get('name', label),
                'modules': mods,
            })

    # Filter buttons
    cat_filter = []
    used_cats = {m.get('category') for m in MODULES}
    for k in CATEGORY_ORDER:
        if k in used_cats:
            cat_info = CATEGORIES.get(k, {})
            icon, label = CATEGORY_LABELS.get(k, ('📦', k))
            cat_filter.append({'key': k, 'icon': icon, 'label': cat_info.get('name', label)})

    return render(request, 'moduli/launcher.html', {
        'groups': ordered_groups,
        'q': q,
        'cat': cat,
        'cat_filter': cat_filter,
        'total': len(all_modules),
        'is_fina_connect': True,
    })


@login_required
def launcher_api(request):
    """JSON brzi search za command palette."""
    from companies.module_registry import MODULES
    q = request.GET.get('q', '').strip().lower()

    results = []
    for mod in MODULES:
        if q and q not in mod.get('name', '').lower() and q not in mod.get('description', '').lower():
            continue
        url = mod.get('url', '/')
        if not url.startswith('/'):
            url = f'/hr/{url}'
        results.append({
            'icon': _fa_to_emoji(mod.get('icon', '')),
            'name': mod.get('name', ''),
            'description': mod.get('description', ''),
            'url': url,
            'category': mod.get('category', ''),
        })
        if len(results) >= 20:
            break

    return JsonResponse({'results': results, 'q': q, 'total': len(results)})
