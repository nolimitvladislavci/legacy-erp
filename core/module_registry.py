"""
core/module_registry.py
Central registry for SPECIALIZED modules (udruge, OPG, DVD, KUD, etc.)
with auto-detection, activation/deactivation, and sidebar integration.

General ERP modules live in companies/module_registry.py.
This registry handles domain-specific modules that depend on business_type,
NKD code, or company name keywords.
"""
import logging
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
#  MODULE REGISTRY — specijalizirani moduli po tipu djelatnosti
# ═══════════════════════════════════════════════════════════════════════════

MODULE_REGISTRY = {
    # ── Jezgra (uvijek aktivno za udruge) ──────────────────────────────
    'udruge_core': {
        'name': 'Članovi i članarine',
        'icon': 'fa-users',
        'description': 'Evidencija članova, članarina, donacija',
        'category': 'udruge',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'Članovi', 'url': 'udruge:clan_list', 'icon': 'fa-user'},
            {'name': 'Članarine', 'url': 'udruge:clanarina_list', 'icon': 'fa-credit-card'},
            {'name': 'Donacije', 'url': 'udruge:donacija_list', 'icon': 'fa-heart'},
            {'name': 'Knjiga primitaka', 'url': 'udruge:knjiga_primitaka', 'icon': 'fa-book'},
            {'name': 'Sekcije', 'url': 'udruge:sekcija_list', 'icon': 'fa-layer-group'},
            {'name': 'Dokumenti/Dozvole', 'url': 'udruge:dozvole_pregled', 'icon': 'fa-id-card'},
        ],
        'auto_activate_for': ['udruga', 'zadruga', 'ustanova'],
        'always_on': True,
    },
    'udruge_dogadjaji': {
        'name': 'Događaji i kampanje',
        'icon': 'fa-calendar-alt',
        'description': 'Događaji, kampanje, email marketing, volonteri',
        'category': 'udruge',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'Događaji', 'url': 'udruge:dogadjaj_list', 'icon': 'fa-calendar'},
            {'name': 'Kampanje', 'url': 'udruge:kampanja_list', 'icon': 'fa-bullhorn'},
            {'name': 'Email marketing', 'url': 'udruge:email_kampanja_list', 'icon': 'fa-envelope'},
            {'name': 'Volonteri', 'url': 'udruge:volunteer_list', 'icon': 'fa-hands-helping'},
        ],
        'auto_activate_for': ['udruga'],
        'always_on': True,
    },
    'udruge_fina': {
        'name': 'FINA izvještaji',
        'icon': 'fa-file-invoice',
        'description': 'NPF izvještaji za neprofitne organizacije, EU fondovi',
        'category': 'udruge',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'NPF izvještaji', 'url': 'udruge:fina_reports', 'icon': 'fa-file-excel'},
            {'name': 'EU fondovi', 'url': 'udruge:eu_reports', 'icon': 'fa-flag'},
        ],
        'auto_activate_for': ['udruga'],
        'always_on': True,
    },

    # ── DVD (Dobrovoljno vatrogasno društvo) ───────────────────────────
    'dvd': {
        'name': 'Vatrogasci (DVD)',
        'icon': 'fa-fire-extinguisher',
        'description': 'Oprema, vozila, intervencije, vježbe',
        'category': 'dvd',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'DVD Dashboard', 'url': 'udruge:dvd_dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Oprema', 'url': 'udruge:vatrogasna_oprema_list', 'icon': 'fa-tools'},
            {'name': 'Vozila', 'url': 'udruge:vatrogasno_vozilo_list', 'icon': 'fa-truck'},
            {'name': 'Intervencije', 'url': 'udruge:intervencija_list', 'icon': 'fa-fire'},
            {'name': 'Vježbe', 'url': 'udruge:vjezba_list', 'icon': 'fa-dumbbell'},
            {'name': 'Zvanja', 'url': 'udruge:vatrogasno_zvanje_list', 'icon': 'fa-medal'},
        ],
        'auto_activate_for': [],
        'nkd_codes': ['84.25'],
        'keywords': ['vatrogasno', 'dvd', 'vatrogasci', 'fire'],
    },

    # ── KUD (Kulturno-umjetničko društvo) ──────────────────────────────
    'kud': {
        'name': 'KUD',
        'icon': 'fa-music',
        'description': 'Repertoar, probe, kostimi, nastupi',
        'category': 'kud',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'KUD Dashboard', 'url': 'udruge:kud_dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Repertoar', 'url': 'udruge:repertoar_list', 'icon': 'fa-guitar'},
            {'name': 'Probe', 'url': 'udruge:proba_list', 'icon': 'fa-clock'},
            {'name': 'Kostimi', 'url': 'udruge:kostim_list', 'icon': 'fa-tshirt'},
        ],
        'auto_activate_for': [],
        'nkd_codes': ['90.01', '90.02', '90.04'],
        'keywords': ['kulturno', 'kud', 'folklor', 'tambur', 'zbor', 'drama'],
    },

    # ── Ribolov (ŠRD) ─────────────────────────────────────────────────
    'ribolov': {
        'name': 'Ribolov',
        'icon': 'fa-fish',
        'description': 'Reviri, dozvole, ulovi, poribljavanje',
        'category': 'ribolov',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'Ribolov Dashboard', 'url': 'udruge:ribari_dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Reviri', 'url': 'udruge:revir_list', 'icon': 'fa-water'},
            {'name': 'Dozvole', 'url': 'udruge:ribolovna_dozvola_list', 'icon': 'fa-id-badge'},
            {'name': 'Ulovi', 'url': 'udruge:ulov_list', 'icon': 'fa-fish'},
            {'name': 'Poribljavanje', 'url': 'udruge:poribljavanje_list', 'icon': 'fa-truck-loading'},
            {'name': 'Čuvarska služba', 'url': 'udruge:cuvarska_straza_list', 'icon': 'fa-shield-alt'},
        ],
        'auto_activate_for': [],
        'nkd_codes': ['93.19', '03.12'],
        'keywords': ['ribolov', 'šrd', 'ribari', 'fishing'],
    },

    # ── Pčelarstvo ─────────────────────────────────────────────────────
    'pcelari': {
        'name': 'Pčelarstvo',
        'icon': 'fa-bug',
        'description': 'Pčelinjaci, košnice, tretmani, med',
        'category': 'pcelari',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'Pčelari Dashboard', 'url': 'udruge:pcelari_dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Pčelinjaci', 'url': 'udruge:pcelinjak_list', 'icon': 'fa-home'},
            {'name': 'Košnice', 'url': 'udruge:kosnica_list', 'icon': 'fa-box'},
            {'name': 'Tretmani', 'url': 'udruge:tretman_kosnice_list', 'icon': 'fa-syringe'},
            {'name': 'Med', 'url': 'udruge:med_proizvodnja_list', 'icon': 'fa-jar'},
            {'name': 'Selidbe', 'url': 'udruge:selidba_list', 'icon': 'fa-truck-moving'},
        ],
        'auto_activate_for': [],
        'nkd_codes': ['01.49'],
        'keywords': ['pčelar', 'pčela', 'med', 'košnic', 'beekeep'],
    },

    # ── Rakija / Destilacija ───────────────────────────────────────────
    'rakija': {
        'name': 'Rakija / Destilacija',
        'icon': 'fa-wine-bottle',
        'description': 'Kotlovi, destilacija, trošarina',
        'category': 'rakija',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'Rakija Dashboard', 'url': 'udruge:rakija_dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Kotlovi', 'url': 'udruge:kotao_list', 'icon': 'fa-flask'},
            {'name': 'Destilacije', 'url': 'udruge:destilacija_list', 'icon': 'fa-fire-alt'},
            {'name': 'Proizvodi', 'url': 'udruge:rakija_list', 'icon': 'fa-wine-bottle'},
            {'name': 'Trošarina', 'url': 'udruge:trosarina_list', 'icon': 'fa-receipt'},
        ],
        'auto_activate_for': [],
        'nkd_codes': ['11.01'],
        'keywords': ['rakija', 'destilacij', 'pecar', 'kotao'],
    },

    # ── Voćarstvo ──────────────────────────────────────────────────────
    'vocari': {
        'name': 'Voćarstvo',
        'icon': 'fa-apple-alt',
        'description': 'Voćnjaci, berbe, tretmani',
        'category': 'vocari',
        'url_prefix': '/udruge/',
        'sidebar_items': [
            {'name': 'Voćari Dashboard', 'url': 'udruge:vocari_dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Voćnjaci', 'url': 'udruge:vocnjak_list', 'icon': 'fa-tree'},
            {'name': 'Berbe', 'url': 'udruge:berba_list', 'icon': 'fa-box-open'},
            {'name': 'Tretmani', 'url': 'udruge:tretman_vocnjaka_list', 'icon': 'fa-spray-can'},
        ],
        'auto_activate_for': [],
        'nkd_codes': ['01.24', '01.25'],
        'keywords': ['voćar', 'voćnjak', 'jabuk', 'šljiv', 'fruit'],
    },

    # ── Stočarstvo / Livestock ─────────────────────────────────────────
    'livestock': {
        'name': 'Stočarstvo',
        'icon': 'fa-horse',
        'description': 'Goveda, veterina, mlijeko, parcele',
        'category': 'livestock',
        'url_prefix': '/livestock/',
        'sidebar_items': [
            {'name': 'Stado', 'url': 'livestock:livestock_list', 'icon': 'fa-horse'},
            {'name': 'Parcele', 'url': 'livestock:field_list', 'icon': 'fa-map'},
            {'name': 'Usjevi', 'url': 'livestock:crop_list', 'icon': 'fa-seedling'},
        ],
        'auto_activate_for': ['opg'],
        'nkd_codes': ['01.41', '01.42'],
        'keywords': ['stočar', 'govedar', 'govedo', 'mlijeko', 'cattle'],
    },
    'stolarija': {
        'name': 'Stolarija (ALU/PVC)',
        'icon': 'fa-window-maximize',
        'description': 'Mjerenje, ponuda, proizvodnja, ugradnja, garancija za ALU/PVC stolariju',
        'category': 'proizvodnja',
        'url_prefix': '/stolarija/',
        'sidebar_items': [
            {'name': 'Dashboard', 'url': 'stolarija:dashboard', 'icon': 'fa-tachometer-alt'},
            {'name': 'Nova sesija', 'url': 'stolarija:session_new', 'icon': 'fa-plus'},
            {'name': 'Ponude', 'url': 'stolarija:offer_list', 'icon': 'fa-file-invoice'},
            {'name': 'Garancije', 'url': 'stolarija:warranty_list', 'icon': 'fa-shield-alt'},
        ],
        'auto_activate_for': ['obrt', 'doo'],
        'nkd_codes': ['25.12', '43.32'],
        'keywords': ['stolarija', 'prozor', 'vrata', 'alu', 'pvc', 'staklo', 'window', 'door'],
    },
}

# Category display metadata
MODULE_CATEGORIES = {
    'udruge': {'name': 'Udruge — Osnovno', 'icon': 'fa-users', 'order': 0},
    'dvd': {'name': 'Vatrogasci (DVD)', 'icon': 'fa-fire-extinguisher', 'order': 1},
    'kud': {'name': 'Kultura (KUD)', 'icon': 'fa-music', 'order': 2},
    'proizvodnja': {'name': 'Proizvodnja i obrt', 'icon': 'fa-industry', 'order': 10},
    'ribolov': {'name': 'Ribolov (ŠRD)', 'icon': 'fa-fish', 'order': 3},
    'pcelari': {'name': 'Pčelarstvo', 'icon': 'fa-bug', 'order': 4},
    'rakija': {'name': 'Rakija / Destilacija', 'icon': 'fa-wine-bottle', 'order': 5},
    'vocari': {'name': 'Voćarstvo', 'icon': 'fa-apple-alt', 'order': 6},
    'livestock': {'name': 'Stočarstvo / OPG', 'icon': 'fa-horse', 'order': 7},
}


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_module(module_key):
    """Return module dict by key, or None."""
    mod = MODULE_REGISTRY.get(module_key)
    if mod:
        return {'key': module_key, **mod}
    return None


def get_active_modules(company):
    """
    Return list of active module keys for a company.
    Combines: always_on modules (by business_type) + explicitly enabled modules.
    """
    if not company:
        return []

    business_type = getattr(company, 'business_type', '')
    active = set()

    # 1. Always-on modules matching business_type
    for key, mod in MODULE_REGISTRY.items():
        if mod.get('always_on') and business_type in mod.get('auto_activate_for', []):
            active.add(key)

    # 2. Explicitly enabled modules from CompanyModuleConfig
    try:
        from companies.models import CompanyModuleConfig
        config = CompanyModuleConfig.objects.filter(company=company).first()
        if config and config.enabled_modules:
            for m in config.enabled_modules:
                if m in MODULE_REGISTRY:
                    active.add(m)
    except DatabaseError as e:
        logger.warning("get_active_modules error: %s", e)

    return sorted(active)


def get_sidebar_items(company):
    """
    Return flat list of sidebar items for all active modules,
    grouped by category for rendering.

    Returns: [
        {
            'category_key': 'udruge',
            'category_name': 'Udruge — Osnovno',
            'category_icon': 'fa-users',
            'order': 0,
            'modules': [
                {
                    'key': 'udruge_core',
                    'name': 'Članovi i članarine',
                    'icon': 'fa-users',
                    'items': [{'name': ..., 'url': ..., 'icon': ...}, ...]
                },
                ...
            ]
        },
        ...
    ]
    """
    active_keys = get_active_modules(company)
    if not active_keys:
        return []

    grouped = {}
    for key in active_keys:
        mod = MODULE_REGISTRY.get(key)
        if not mod:
            continue
        cat = mod.get('category', 'other')
        if cat not in grouped:
            cat_info = MODULE_CATEGORIES.get(cat, {'name': cat.title(), 'icon': 'fa-folder', 'order': 99})
            grouped[cat] = {
                'category_key': cat,
                'category_name': cat_info['name'],
                'category_icon': cat_info['icon'],
                'order': cat_info['order'],
                'modules': [],
            }
        grouped[cat]['modules'].append({
            'key': key,
            'name': mod['name'],
            'icon': mod['icon'],
            'items': mod.get('sidebar_items', []),
        })

    return sorted(grouped.values(), key=lambda x: x['order'])


def is_module_active(company, module_key):
    """Check if a specific module is active for a company."""
    return module_key in get_active_modules(company)


def auto_detect_modules(company):
    """
    Detect which specialized modules should be activated based on:
    1. business_type (udruga, opg, etc.)
    2. NKD code
    3. Company name keywords
    Returns list of module keys that should be activated.
    """
    if not company:
        return []

    detected = []
    business_type = getattr(company, 'business_type', '')
    company_name = (getattr(company, 'name', '') or '').lower()

    # Get NKD code string
    nkd_code_str = ''
    try:
        nkd = getattr(company, 'nkd_code', None)
        if nkd:
            nkd_code_str = getattr(nkd, 'code', '') or ''
    except Exception:
        logger.exception("Company operation failed")

    for key, mod in MODULE_REGISTRY.items():
        # 1. Auto-activate by business_type
        if business_type in mod.get('auto_activate_for', []):
            detected.append(key)
            continue

        # 2. Match by NKD code
        if nkd_code_str:
            for nkd_pattern in mod.get('nkd_codes', []):
                if nkd_code_str.startswith(nkd_pattern):
                    detected.append(key)
                    break
            else:
                # 3. Match by company name keywords (only if NKD didn't match)
                for kw in mod.get('keywords', []):
                    if kw.lower() in company_name:
                        detected.append(key)
                        break
        else:
            # No NKD — try keywords
            for kw in mod.get('keywords', []):
                if kw.lower() in company_name:
                    detected.append(key)
                    break

    return list(dict.fromkeys(detected))  # dedupe preserving order


def activate_module(company, module_key):
    """Activate a module for a company. Returns True if newly activated."""
    if module_key not in MODULE_REGISTRY:
        raise ValueError(f"Nepoznat modul: {module_key}")

    from companies.models import CompanyModuleConfig
    config, _ = CompanyModuleConfig.objects.get_or_create(
        company=company,
        defaults={'enabled_modules': []}
    )

    if module_key not in config.enabled_modules:
        config.enabled_modules = list(config.enabled_modules) + [module_key]
        config.save(update_fields=['enabled_modules', 'updated_at'])
        logger.info("Modul '%s' aktiviran za %s", module_key, company.name)
        return True
    return False


def deactivate_module(company, module_key):
    """Deactivate a module for a company. Returns True if was active."""
    # Don't allow deactivating always_on modules
    mod = MODULE_REGISTRY.get(module_key)
    if mod and mod.get('always_on'):
        business_type = getattr(company, 'business_type', '')
        if business_type in mod.get('auto_activate_for', []):
            raise ValueError(
                f"Modul '{module_key}' je obavezan za tip '{business_type}' "
                f"i ne može se deaktivirati."
            )

    from companies.models import CompanyModuleConfig
    config = CompanyModuleConfig.objects.filter(company=company).first()
    if not config:
        return False

    if module_key in config.enabled_modules:
        new_list = [m for m in config.enabled_modules if m != module_key]
        config.enabled_modules = new_list
        config.save(update_fields=['enabled_modules', 'updated_at'])
        logger.info("Modul '%s' deaktiviran za %s", module_key, company.name)
        return True
    return False


def get_all_modules_grouped():
    """Return all modules grouped by category — for admin module picker."""
    grouped = {}
    for key, mod in MODULE_REGISTRY.items():
        cat = mod.get('category', 'other')
        if cat not in grouped:
            cat_info = MODULE_CATEGORIES.get(cat, {'name': cat.title(), 'icon': 'fa-folder', 'order': 99})
            grouped[cat] = {
                'info': cat_info,
                'modules': [],
            }
        grouped[cat]['modules'].append({'key': key, **mod})

    return dict(sorted(grouped.items(), key=lambda x: x[1]['info'].get('order', 99)))
