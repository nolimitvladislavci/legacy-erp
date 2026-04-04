"""
companies/module_registry.py
Central registry of ALL ERP modules with metadata, pricing tiers, and sidebar config.

This is the SINGLE SOURCE OF TRUTH for:
- Which modules exist
- Their sidebar appearance (icon, URL, category)
- Which pricing tier includes them
- Module dependencies

Sidebar is dynamically generated from this registry based on CompanyModuleConfig.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  PRICING TIERS — koji plan uključuje što
# ═══════════════════════════════════════════════════════════════════════════

TIER_FREE = 'free'           # Besplatno zauvijek
TIER_STARTER = 'starter'     # 19 EUR/mj
TIER_PROFESSIONAL = 'pro'    # 39 EUR/mj
TIER_ENTERPRISE = 'enterprise'  # 79 EUR/mj
TIER_VERTICAL = 'vertical'   # Vertikalni addon (9-19 EUR/mj)

TIER_META = {
    TIER_FREE:         {'name': 'Besplatno', 'price': 0, 'color': '#22c55e'},
    TIER_STARTER:      {'name': 'Starter', 'price': 19, 'color': '#3b82f6'},
    TIER_PROFESSIONAL: {'name': 'Professional', 'price': 39, 'color': '#c9a84c'},
    TIER_ENTERPRISE:   {'name': 'Enterprise', 'price': 79, 'color': '#a855f7'},
    TIER_VERTICAL:     {'name': 'Vertikala', 'price': 9, 'color': '#f97316'},
}


# ═══════════════════════════════════════════════════════════════════════════
#  CATEGORIES — grupiranje u sidebaru
# ═══════════════════════════════════════════════════════════════════════════

CATEGORIES = {
    'core':           {'name': 'Osnovno',        'icon': 'fa-home',              'order': 0},
    'dokumenti':      {'name': 'Dokumenti',      'icon': 'fa-file-invoice',      'order': 1},
    'financije':      {'name': 'Financije',      'icon': 'fa-euro-sign',         'order': 2},
    'poslovanje':     {'name': 'Poslovanje',     'icon': 'fa-briefcase',         'order': 3},
    'zaposlenici':    {'name': 'Zaposlenici',    'icon': 'fa-user-tie',          'order': 4},
    'vertikale':      {'name': 'Vertikale',      'icon': 'fa-layer-group',       'order': 5},
    'javne_ustanove':  {'name': 'Javne ustanove', 'icon': 'fa-landmark',         'order': 6},
    'komunalno_kat':  {'name': 'Komunalno',      'icon': 'fa-recycle',           'order': 7},
    'turizam':        {'name': 'Turizam',        'icon': 'fa-umbrella-beach',    'order': 8},
    'integracije':    {'name': 'Integracije',    'icon': 'fa-plug',              'order': 9},
    'ai':             {'name': 'AI & Automatizacija', 'icon': 'fa-robot',        'order': 10},
    'pravne_usluge':  {'name': 'Pravne usluge',    'icon': 'fa-gavel',             'order': 11},
}


# ═══════════════════════════════════════════════════════════════════════════
#  MODULE REGISTRY — svi moduli
# ═══════════════════════════════════════════════════════════════════════════

MODULES = [
    # ══════════════════════════════════════════════════════════════════════
    #  CORE — uvijek vidljivi
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'dashboard',
        'name': 'Nadzorna ploča',
        'icon': 'fa-tachometer-alt',
        'url': '/',
        'url_name': 'dashboard',
        'category': 'core',
        'tier': TIER_FREE,
        'description': 'Pregled poslovanja, grafovi, obavijesti',
        'always_visible': True,
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  DOKUMENTI
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'invoicing',
        'name': 'Računi',
        'icon': 'fa-file-invoice-dollar',
        'url': '/invoicing/',
        'url_name': 'invoicing:index',
        'category': 'dokumenti',
        'tier': TIER_FREE,
        'description': 'Izdavanje računa, ponuda, predračuna. Fiskalizacija.',
        'price_addon': 0,
        'quick_action': {'label': 'Nova transakcija', 'url': '/invoicing/canvas/', 'icon': 'fa-bolt', 'color': '#c9a84c'},
    },
    {
        'id': 'eracun',
        'name': 'e-Račun',
        'icon': 'fa-file-invoice',
        'url': '/eracun/',
        'url_name': 'eracun:dashboard',
        'category': 'dokumenti',
        'tier': TIER_STARTER,
        'description': 'Slanje i primanje e-računa. FINA certificirano.',
        'price_addon': 0,
    },
    {
        'id': 'einvoice',
        'name': 'Smart Mailbox',
        'icon': 'fa-brain',
        'url': '/einvoice/inbox/',
        'url_name': 'einvoice:inbox',
        'category': 'dokumenti',
        'tier': TIER_STARTER,
        'description': 'AI inbox triage, automatski URA import.',
        'price_addon': 0,
    },
    {
        'id': 'documents',
        'name': 'Arhiva',
        'icon': 'fa-archive',
        'url': '/documents/',
        'url_name': 'documents:index',
        'category': 'dokumenti',
        'tier': TIER_FREE,
        'description': 'Dokumenti, ugovori, skenovi. 11-godišnja arhiva.',
        'price_addon': 0,
        'quick_action': {'label': 'Upload dokumenta', 'url': '/hr/documents/arhiva/upload/', 'icon': 'fa-cloud-upload-alt', 'color': '#c9a84c'},
    },

    # ══════════════════════════════════════════════════════════════════════
    #  FINANCIJE
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'konto',
        'name': 'Knjigovodstvo',
        'icon': 'fa-book',
        'url': '/konto/',
        'url_name': 'konto:dashboard',
        'category': 'financije',
        'tier': TIER_STARTER,
        'description': 'Dvostavno knjigovodstvo, kontni plan, temeljnice.',
        'price_addon': 0,
    },
    {
        'id': 'pdv_s',
        'name': 'PDV-S Obrazac',
        'icon': 'fa-calculator',
        'url': '/pdv-s/',
        'url_name': 'pdv_s:dashboard',
        'category': 'financije',
        'tier': TIER_STARTER,
        'description': 'Automatski izračun i XML export za e-Porezna.',
        'price_addon': 0,
    },
    {
        'id': 'finance',
        'name': 'Financije',
        'icon': 'fa-chart-line',
        'url': '/finance/',
        'url_name': 'finance:dashboard',
        'category': 'financije',
        'tier': TIER_STARTER,
        'description': 'Banka, izvodi, cashflow, automatsko pariranje.',
        'price_addon': 0,
    },
    {
        'id': 'payments',
        'name': 'Plaćanja',
        'icon': 'fa-credit-card',
        'url': '/payments/',
        'url_name': 'payments:dashboard',
        'category': 'financije',
        'tier': TIER_STARTER,
        'description': 'Stripe, PayPal, BTCPay, gotovina.',
        'price_addon': 0,
    },
    {
        'id': 'tax_wizard',
        'name': 'Tax Wizard',
        'icon': 'fa-hat-wizard',
        'url': '/tax-wizard/',
        'url_name': 'tax_wizard:dashboard',
        'category': 'financije',
        'tier': TIER_STARTER,
        'description': 'Automatski porezni obrasci, JOPPD, PO-SD.',
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  POSLOVANJE
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'partners',
        'name': 'Partneri',
        'icon': 'fa-handshake',
        'url': '/hr/partners/',
        'url_name': 'partners:partner_list',
        'category': 'poslovanje',
        'tier': TIER_FREE,
        'description': 'Kupci, dobavljači, kontakti. OIB validacija.',
        'price_addon': 0,
    },
    {
        'id': 'inventory',
        'name': 'Skladište',
        'icon': 'fa-boxes',
        'url': '/hr/inventory/',
        'url_name': 'inventory:list',
        'category': 'poslovanje',
        'tier': TIER_FREE,
        'description': 'Artikli, zalihe, primke, inventura.',
        'price_addon': 0,
    },
    {
        'id': 'pos',
        'name': 'POS Blagajna',
        'icon': 'fa-cash-register',
        'url': '/pos/',
        'url_name': 'pos:dashboard',
        'category': 'poslovanje',
        'tier': TIER_FREE,
        'description': 'Maloprodajna blagajna, gastro POS, QR meni.',
        'price_addon': 0,
        'accent_color': '#22c55e',
        'quick_action': {'label': 'POS Blagajna', 'url': '/pos/', 'icon': 'fa-cash-register', 'color': '#22c55e'},
    },
    {
        'id': 'work_orders',
        'name': 'Radni nalozi',
        'icon': 'fa-tools',
        'url': '/work-orders/',
        'url_name': 'work_orders:list',
        'category': 'poslovanje',
        'tier': TIER_STARTER,
        'description': 'Servisni nalozi, terenske intervencije.',
        'price_addon': 0,
    },
    {
        'id': 'procurement',
        'name': 'Nabava',
        'icon': 'fa-file-invoice',
        'url': '/procurement/',
        'url_name': 'procurement:list',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Narudžbenice, ponude dobavljača, approval workflow.',
        'price_addon': 0,
    },
    {
        'id': 'marketplace',
        'name': 'Grossmarkt',
        'icon': 'fa-store',
        'url': '/marketplace/',
        'url_name': 'marketplace:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'B2B tržnica, online narudžbe, OPG burza.',
        'price_addon': 0,
    },
    {
        'id': 'delivery',
        'name': 'Dostava',
        'icon': 'fa-truck',
        'url': '/delivery/consolidated/',
        'url_name': 'delivery:consolidated',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Rute, konsolidacija, dostavljači.',
        'price_addon': 0,
    },
    {
        'id': 'webshop',
        'name': 'Webshop',
        'icon': 'fa-shopping-cart',
        'url': '/webshop/',
        'url_name': 'webshop:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Online trgovina, kategorije, košarica.',
        'price_addon': 0,
    },
    {
        'id': 'traceability',
        'name': 'LOT Slijedivost',
        'icon': 'fa-barcode',
        'url': '/traceability/',
        'url_name': 'traceability:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'LOT praćenje, rok trajanja, HACCP, BOM normativi.',
        'price_addon': 0,
    },
    {
        'id': 'reports',
        'name': 'Izvještaji',
        'icon': 'fa-chart-bar',
        'url': '/reports/',
        'url_name': 'reports:index',
        'category': 'poslovanje',
        'tier': TIER_STARTER,
        'description': 'Analitika, grafovi, export.',
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  ZAPOSLENICI
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'worktime',
        'name': 'Evidencija rada',
        'icon': 'fa-clock',
        'url': '/hr/worktime/',
        'url_name': 'worktime:ts_worker',
        'category': 'zaposlenici',
        'tier': TIER_STARTER,
        'description': 'Clock in/out, satnica, prekovremeni, analitika.',
        'price_addon': 0,
    },
    {
        'id': 'payroll',
        'name': 'Plaće',
        'icon': 'fa-money-check-alt',
        'url': '/payroll/',
        'url_name': 'payroll:dashboard',
        'category': 'zaposlenici',
        'tier': TIER_PROFESSIONAL,
        'description': 'Obračun plaća, JOPPD, isplatne liste.',
        'price_addon': 0,
    },
    {
        'id': 'seasonal',
        'name': 'Sezonski radnici',
        'icon': 'fa-sun',
        'url': '/sezonci/',
        'url_name': 'seasonal:dashboard',
        'category': 'zaposlenici',
        'tier': TIER_STARTER,
        'description': 'Sezonski ugovori, evidencija, isplate.',
        'price_addon': 0,
    },
    {
        'id': 'appointments',
        'name': 'Termini',
        'icon': 'fa-calendar-check',
        'url': '/hr/appointments/',
        'url_name': 'appointments:list',
        'category': 'zaposlenici',
        'tier': TIER_STARTER,
        'description': 'Online zakazivanje, podsjetnici, kalendar.',
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  VERTIKALE — specijalizirani moduli po djelatnosti
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'udruge',
        'name': 'Udruge',
        'icon': 'fa-users',
        'url': '/udruge/',
        'url_name': 'udruge:dashboard',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Članovi, članarine, donacije, eventi, EU fondovi.',
        'price_addon': 9,
        'auto_for': ['udruga', 'zadruga', 'ustanova'],
        'sub_modules': ['dvd', 'kud', 'ribolov', 'pcelari', 'rakija', 'vocari', 'golubar'],
    },
    {
        'id': 'rental',
        'name': 'Smještaj',
        'icon': 'fa-key',
        'url': '/rental/',
        'url_name': 'rental:dashboard',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Robot Hotel — sobe, rezervacije, eVisitor, self-checkin.',
        'price_addon': 14,
        'auto_for': ['rental', 'turizam'],
    },
    {
        'id': 'experiences',
        'name': 'Doživljaji',
        'icon': 'fa-mountain-sun',
        'url': '/experiences/',
        'url_name': 'experiences:dashboard',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Agro-turizam, degustacije, radionice, Flock.',
        'price_addon': 9,
    },
    {
        'id': 'livestock',
        'name': 'Stočarstvo',
        'icon': 'fa-horse',
        'url': '/livestock/',
        'url_name': 'livestock:livestock_list',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Goveda, veterina, mlijeko, parcele.',
        'price_addon': 9,
        'auto_for': ['opg'],
    },
    {
        'id': 'pets',
        'name': 'Uzgajalište ljubimaca',
        'icon': 'fa-paw',
        'url': '/livestock/pets/',
        'url_name': 'livestock:pet_list',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Psi, mačke, konji — rodovnice, zdravstveni kartoni, AI prepoznavanje.',
        'price_addon': 5,
    },
    {
        'id': 'fitness',
        'name': 'Fitness & Wellness',
        'icon': 'fa-dumbbell',
        'url': '/fitness/',
        'url_name': 'fitness:dashboard',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Članarine, treninzi, rezervacije, QR pristup.',
        'price_addon': 9,
    },
    {
        'id': 'insurance',
        'name': 'Osiguranje',
        'icon': 'fa-shield-alt',
        'url': '/insurance/',
        'url_name': 'insurance:dashboard',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Police, štete, agenti, provizije.',
        'price_addon': 14,
    },
    {
        'id': 'gastro_menu',
        'name': 'Gastro meni',
        'icon': 'fa-utensils',
        'url': '/gastro/menu/',
        'url_name': 'gastro_menu:menu_list',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'QR meni, alergeni, digitalni jelovnik.',
        'price_addon': 4,
    },
    {
        'id': 'premium_booking',
        'name': 'Booking portal',
        'icon': 'fa-calendar-alt',
        'url': '/booking/',
        'url_name': 'premium_booking:portal',
        'category': 'vertikale',
        'tier': TIER_VERTICAL,
        'description': 'Javni booking portal, online plaćanje.',
        'price_addon': 9,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  JAVNE USTANOVE
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'kindergarten',
        'name': 'Vrtić',
        'icon': 'fa-child',
        'url': '/vrtic/',
        'url_name': 'kindergarten:dashboard',
        'category': 'javne_ustanove',
        'tier': TIER_VERTICAL,
        'description': 'Grupe, djeca, prisustvo, dnevni izvještaji, roditeljski portal.',
        'price_addon': 14,
    },
    {
        'id': 'eldercare',
        'name': 'Dom za starije',
        'icon': 'fa-house-user',
        'url': '/dom/',
        'url_name': 'eldercare:dashboard',
        'category': 'javne_ustanove',
        'tier': TIER_VERTICAL,
        'description': 'Sobe, korisnici, mjesečne naplate, smjene, obavijesti.',
        'price_addon': 14,
    },
    {
        'id': 'knjiznica',
        'name': 'Knjižnica',
        'icon': 'fa-book-reader',
        'url': '/knjiznica/',
        'url_name': 'knjiznica:dashboard',
        'category': 'javne_ustanove',
        'tier': TIER_VERTICAL,
        'description': 'Posudba, članovi, gamifikacija, NSK statistika, portal.',
        'price_addon': 14,
    },
    {
        'id': 'library',
        'name': 'Knjižnica Pro',
        'icon': 'fa-book-open',
        'url': '/library/',
        'url_name': 'library:dashboard',
        'category': 'javne_ustanove',
        'tier': TIER_VERTICAL,
        'description': 'MARC21, digitalni sadržaji, autori, kopije, javni portal.',
        'price_addon': 19,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  KOMUNALNO
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'komunalno',
        'name': 'Komunalno',
        'icon': 'fa-recycle',
        'url': '/komunalno/',
        'url_name': 'komunalno:dashboard',
        'category': 'komunalno_kat',
        'tier': TIER_VERTICAL,
        'description': 'Reciklažna dvorišta, kvote, kiosk UI.',
        'price_addon': 14,
    },
    {
        'id': 'zeleni_otok',
        'name': 'Zeleni Otok',
        'icon': 'fa-leaf',
        'url': '/zeleni-otok/',
        'url_name': 'zeleni_otok:dashboard',
        'category': 'komunalno_kat',
        'tier': TIER_VERTICAL,
        'description': 'Vaga integracija, e-ONTO export, kiosk prljave ruke.',
        'price_addon': 9,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  TURIZAM
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'burza',
        'name': 'Burza OPG',
        'icon': 'fa-shopping-basket',
        'url': '/burza/',
        'url_name': 'burza:dashboard',
        'category': 'turizam',
        'tier': TIER_VERTICAL,
        'description': 'Online tržnica, OPG proizvodi, narudžbe.',
        'price_addon': 4,
    },


    # ══════════════════════════════════════════════════════════════════════
    #  PROIZVODNJA (MRP)
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'production',
        'name': 'Proizvodnja',
        'name_de': 'Produktion',
        'icon': 'fa-industry',
        'url': '/proizvodnja/',
        'url_name': 'production:dashboard',
        'category': 'vertikale',
        'tier': TIER_PROFESSIONAL,
        'description': 'BOM recepture, radni nalozi, QC, troškovi.',
        'price_addon': 14,
        'children': [
            {
                'id': 'production_bom',
                'name': 'Sastavnice (BOM)',
                'icon': 'fa-list-check',
                'url': '/proizvodnja/bom/',
                'url_name': 'production:bom_list',
            },
            {
                'id': 'production_orders',
                'name': 'Radni nalozi',
                'icon': 'fa-clipboard-list',
                'url': '/proizvodnja/nalozi/',
                'url_name': 'production:order_list',
            },
            {
                'id': 'production_workstations',
                'name': 'Radne stanice',
                'icon': 'fa-gears',
                'url': '/proizvodnja/stanice/',
                'url_name': 'production:workstation_list',
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    #  INTEGRACIJE
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'synesis',
        'name': 'Synesis',
        'icon': 'fa-database',
        'url': '/synesis/',
        'url_name': 'synesis:dashboard',
        'category': 'integracije',
        'tier': TIER_PROFESSIONAL,
        'description': 'Synesis MDB sync, bidirekcijski uvoz.',
        'price_addon': 0,
    },
    {
        'id': 'smart_import',
        'name': 'Smart Import',
        'icon': 'fa-file-import',
        'url': '/smart-import/',
        'url_name': 'smart_import:upload',
        'category': 'integracije',
        'tier': TIER_STARTER,
        'description': 'AI uvoz faktura iz PDF/XML/slike. Gemini Vision.',
        'price_addon': 0,
    },
    {
        'id': 'propter',
        'name': 'Propter ESG',
        'icon': 'fa-leaf',
        'url': '/propter/',
        'url_name': 'propter:dashboard',
        'category': 'integracije',
        'tier': TIER_PROFESSIONAL,
        'description': 'ESG izvještavanje, carbon footprint.',
        'price_addon': 0,
    },
    {
        'id': 'data_migration',
        'name': 'Data Migration',
        'icon': 'fa-exchange-alt',
        'url': '/data-migration/',
        'url_name': 'data_migration:dashboard',
        'category': 'integracije',
        'tier': TIER_ENTERPRISE,
        'description': 'Migracija podataka iz drugih sustava.',
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  AI & AUTOMATIZACIJA
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'ai_assistant',
        'name': 'AI Asistent',
        'icon': 'fa-robot',
        'url': '/ai/',
        'url_name': 'ai_assistant:dashboard',
        'category': 'ai',
        'tier': TIER_PROFESSIONAL,
        'description': 'AI patrol, anomaly detection, auto-booking.',
        'price_addon': 0,
    },
    {
        'id': 'intelligence',
        'name': 'Intelligence',
        'icon': 'fa-brain',
        'url': '/intelligence/',
        'url_name': 'intelligence:dashboard',
        'category': 'ai',
        'tier': TIER_ENTERPRISE,
        'description': 'BI dashboard, napredna analitika, knowledge graph.',
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  OPERATIVNO (sidebar-only, ne prodaju se zasebno)
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'helpdesk',
        'name': 'Helpdesk',
        'icon': 'fa-headset',
        'url': '/helpdesk/',
        'url_name': 'helpdesk:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Tiketi, SLA, korisnička podrška.',
        'price_addon': 0,
    },
    {
        'id': 'interventions',
        'name': 'Intervencije',
        'icon': 'fa-ambulance',
        'url': '/interventions/',
        'url_name': 'interventions:list',
        'category': 'poslovanje',
        'tier': TIER_STARTER,
        'description': 'Hitne intervencije, SOS forma, WhatsApp.',
        'price_addon': 0,
    },
    {
        'id': 'maintenance',
        'name': 'Održavanje',
        'icon': 'fa-cogs',
        'url': '/maintenance/',
        'url_name': 'maintenance:list',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Preventivno i korektivno održavanje.',
        'price_addon': 0,
    },
    {
        'id': 'tracking',
        'name': 'Tracking',
        'icon': 'fa-map-marker-alt',
        'url': '/tracking/',
        'url_name': 'tracking:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'GPS praćenje vozila, geozone.',
        'price_addon': 0,
    },
    {
        'id': 'outreach',
        'name': 'CRM / Outreach',
        'icon': 'fa-envelope-open-text',
        'url': '/outreach/',
        'url_name': 'outreach:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Email kampanje, lead scoring.',
        'price_addon': 0,
    },
    {
        'id': 'calculator',
        'name': 'Kalkulator',
        'icon': 'fa-calculator',
        'url': '/calculator/',
        'url_name': 'calculator:index',
        'category': 'poslovanje',
        'tier': TIER_FREE,
        'description': 'Poslovni kalkulatori.',
        'price_addon': 0,
    },
    {
        'id': 'assessment',
        'name': 'Procjene',
        'icon': 'fa-clipboard-list',
        'url': '/assessment/',
        'url_name': 'assessment:index',
        'category': 'poslovanje',
        'tier': TIER_STARTER,
        'description': 'Procjene, checkliste, inspekcije.',
        'price_addon': 0,
    },
    {
        'id': 'virtual_office',
        'name': 'Virtualni ured',
        'icon': 'fa-laptop-house',
        'url': '/virtual-office/',
        'url_name': 'virtual_office:dashboard',
        'category': 'poslovanje',
        'tier': TIER_PROFESSIONAL,
        'description': 'Projekti, zadaci, timski rad.',
        'price_addon': 0,
    },
    {
        'id': 'gov_export',
        'name': 'Državni exporti',
        'icon': 'fa-landmark',
        'url': '/gov-export/',
        'url_name': 'gov_export:dashboard',
        'category': 'integracije',
        'tier': TIER_STARTER,
        'description': 'FINA, e-Porezna, HZMO XML exporti.',
        'price_addon': 0,
    },
    {
        'id': 'aml',
        'name': 'AML',
        'icon': 'fa-user-shield',
        'url': '/aml/',
        'url_name': 'aml:dashboard',
        'category': 'integracije',
        'tier': TIER_ENTERPRISE,
        'description': 'Anti-money laundering provjere.',
        'price_addon': 0,
    },

    # ══════════════════════════════════════════════════════════════════════
    #  PRAVNE USLUGE — Bilježnik + Odvjetnik + Dimnjačar
    # ══════════════════════════════════════════════════════════════════════
    {
        'id': 'odvjetnik',
        'name': 'Odvjetnički ured',
        'icon': 'fa-gavel',
        'url': '/notariat/pravnik/',
        'url_name': 'notariat:pravnik_dashboard',
        'category': 'pravne_usluge',
        'tier': 'vertical',
        'description': 'Predmeti, billable sati, rokovi, fakturiranje po predmetu.',
        'price_addon': 19,
    },
    {
        'id': 'biljeznik',
        'name': 'Javni bilježnik',
        'icon': 'fa-file-contract',
        'url': '/notariat/pravnik/',
        'url_name': 'notariat:pravnik_dashboard',
        'category': 'pravne_usluge',
        'tier': 'vertical',
        'description': '10 predložaka, tarifa kalkulator, PDF ovjera, CroValidator.',
        'price_addon': 24,
    },
    {
        'id': 'dimnjacari',
        'name': 'Dimnjačarska služba',
        'icon': 'fa-fire',
        'url': '/notariat/dimnjacari/',
        'url_name': 'notariat:dimnjacari_dashboard',
        'category': 'pravne_usluge',
        'tier': 'vertical',
        'description': 'Evidencija pregleda NN 103/15, PDF potvrde, godišnji plan.',
        'price_addon': 14,
    },
]
# ═══════════════════════════════════════════════════════════════════════════
#  LOOKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════

# Build fast lookup dict
_MODULE_MAP = {m['id']: m for m in MODULES}


def get_module(module_id):
    """Return module dict by id, or None."""
    return _MODULE_MAP.get(module_id)


def get_modules_by_category():
    """Return modules grouped by category, ordered."""
    result = {}
    for cat_id, cat_info in sorted(CATEGORIES.items(), key=lambda x: x[1]['order']):
        mods = [m for m in MODULES if m.get('category') == cat_id]
        if mods:
            result[cat_id] = {'info': cat_info, 'modules': mods}
    return result


def get_modules_for_tier(tier):
    """Return all modules included in a given tier (and below)."""
    tier_order = [TIER_FREE, TIER_STARTER, TIER_PROFESSIONAL, TIER_ENTERPRISE]
    if tier not in tier_order:
        return [m for m in MODULES if m.get('tier') == TIER_FREE]
    max_idx = tier_order.index(tier)
    included_tiers = set(tier_order[:max_idx + 1])
    return [m for m in MODULES if m.get('tier') in included_tiers]


def get_addon_modules():
    """Return modules that cost extra (vertikale)."""
    return [m for m in MODULES if m.get('price_addon', 0) > 0]


def get_quick_actions(enabled_ids):
    """Return quick action buttons for enabled modules."""
    actions = []
    for m in MODULES:
        if m['id'] in enabled_ids and m.get('quick_action'):
            actions.append({**m['quick_action'], 'module_id': m['id']})
    return actions


def calculate_monthly_price(tier, addon_module_ids):
    """Calculate total monthly price for tier + addon modules."""
    base = TIER_META.get(tier, {}).get('price', 0)
    addon_total = sum(
        _MODULE_MAP[mid].get('price_addon', 0)
        for mid in addon_module_ids
        if mid in _MODULE_MAP
    )
    return base + addon_total


def get_all_module_ids():
    """Return set of all registered module IDs."""
    return set(_MODULE_MAP.keys())
