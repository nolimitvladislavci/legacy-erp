"""
companies/module_registry.py
Central registry of all ERP modules with metadata.
"""

MODULES = [
    # ── CORE (uvijek vidljivi) ──
    {
        'id': 'dashboard',
        'name': 'Nadzorna ploca',
        'icon': 'bi-speedometer2',
        'url': '/dashboard/company/',
        'category': 'core',
        'description': 'Pregled poslovanja, grafovi, obavijesti',
        'always_visible': True,
    },

    # ── DOKUMENTI ──
    {
        'id': 'invoicing',
        'name': 'Racuni',
        'icon': 'bi-receipt',
        'url': '/hr/invoicing/',
        'category': 'dokumenti',
        'description': 'Izdavanje racuna, ponuda, predracuna. Fiskalizacija.',
        'counter_model': 'invoicing.Invoice',
    },
    {
        'id': 'eracun',
        'name': 'e-Racun',
        'icon': 'bi-envelope-paper',
        'url': '/eracun/',
        'category': 'dokumenti',
        'description': 'Slanje i primanje e-racuna. Fiskalizacija 2.0.',
        'counter_model': 'eracun.ERacun',
    },
    {
        'id': 'eracun_inbox',
        'name': 'e-Racun Inbox',
        'icon': 'bi-inbox',
        'url': '/eracun/inbox/',
        'category': 'dokumenti',
        'description': 'Primanje e-racuna od dobavljaca, auto-knjizenje u URA.',
    },
    {
        'id': 'documents',
        'name': 'Arhiva',
        'icon': 'bi-archive',
        'url': '/hr/documents/',
        'category': 'dokumenti',
        'description': 'Dokumenti, ugovori, skenovi. 11-godisnja arhiva.',
    },

    # ── FINANCIJE ──
    {
        'id': 'konto',
        'name': 'Knjigovodstvo',
        'icon': 'bi-journal-text',
        'url': '/konto/',
        'category': 'financije',
        'description': 'Dvostavno knjigovodstvo, kontni plan, temeljnice.',
        'counter_model': 'konto.JournalEntry',
    },
    {
        'id': 'pdv_s',
        'name': 'PDV-S Obrazac',
        'icon': 'bi-calculator',
        'url': '/pdv-s/',
        'category': 'financije',
        'description': 'Automatski izracun i XML export za e-Porezna.',
    },
    {
        'id': 'bank',
        'name': 'Banka',
        'icon': 'bi-bank',
        'url': '/konto/bank/',
        'category': 'financije',
        'description': 'Uvoz izvoda, automatsko pariranje uplata s racunima.',
    },
    {
        'id': 'payments',
        'name': 'Placanja',
        'icon': 'bi-credit-card',
        'url': '/payments/',
        'category': 'financije',
        'description': 'Stripe, PayPal, BTCPay, gotovina. Online placanja.',
    },

    # ── POSLOVANJE ──
    {
        'id': 'partners',
        'name': 'Partneri',
        'icon': 'bi-people',
        'url': '/hr/partners/',
        'category': 'poslovanje',
        'description': 'Kupci, dobavljaci, kontakti. OIB validacija.',
        'counter_model': 'partners.Partner',
    },
    {
        'id': 'inventory',
        'name': 'Skladiste',
        'icon': 'bi-box-seam',
        'url': '/hr/inventory/',
        'category': 'poslovanje',
        'description': 'Artikli, zalihe, primke, inventura. Nabava.',
        'counter_model': 'inventory.InventoryItem',
    },
    {
        'id': 'pos',
        'name': 'POS Blagajna',
        'icon': 'bi-shop',
        'url': '/pos/',
        'category': 'poslovanje',
        'description': 'Maloprodajna blagajna, gastro POS, QR meni.',
    },
    {
        'id': 'work_orders',
        'name': 'Radni nalozi',
        'icon': 'bi-clipboard-check',
        'url': '/hr/work-orders/',
        'category': 'poslovanje',
        'description': 'Servisni nalozi, terenske intervencije.',
    },

    # ── ZAPOSLENICI ──
    {
        'id': 'worktime',
        'name': 'Evidencija rada',
        'icon': 'bi-clock-history',
        'url': '/hr/worktime/',
        'category': 'zaposlenici',
        'description': 'Prijava/odjava, satnica, prekovremeni.',
        'counter_model': 'worktime.EmployeeProfile',
    },
    {
        'id': 'payroll',
        'name': 'Place',
        'icon': 'bi-cash-stack',
        'url': '/payroll/',
        'category': 'zaposlenici',
        'description': 'Obracun placa, JOPPD, isplatne liste.',
    },

    # ── INTEGRACIJE ──
    {
        'id': 'synesis',
        'name': 'Synesis',
        'icon': 'bi-database-gear',
        'url': '/synesis/',
        'category': 'integracije',
        'description': 'Synesis MDB sync, BAT skripta, bidirekcijski uvoz.',
    },
    {
        'id': 'smart_import',
        'name': 'Smart Import',
        'icon': 'bi-cloud-upload',
        'url': '/smart-import/',
        'category': 'integracije',
        'description': 'AI uvoz faktura iz PDF/XML/slike. Gemini Vision.',
    },

    # ── SPECIJALIZIRANI ──
    {
        'id': 'rental',
        'name': 'Smjestaj',
        'icon': 'bi-house-door',
        'url': '/rental/',
        'category': 'specijalizirani',
        'description': 'Robot Hotel — sobe, rezervacije, self-checkin.',
    },
    {
        'id': 'appointments',
        'name': 'Termini',
        'icon': 'bi-calendar-check',
        'url': '/hr/appointments/',
        'category': 'specijalizirani',
        'description': 'Online zakazivanje, podsjetnici, kalendar.',
    },
    {
        'id': 'interventions',
        'name': 'Intervencije',
        'icon': 'bi-exclamation-triangle',
        'url': '/hr/interventions/',
        'category': 'specijalizirani',
        'description': 'Hitne intervencije, SOS forma, WhatsApp obavijesti.',
    },
    {
        'id': 'ai_assistant',
        'name': 'AI Asistent',
        'icon': 'bi-robot',
        'url': '/ai/',
        'category': 'specijalizirani',
        'description': 'AI patrol, anomaly detection, builder.',
    },
    {
        'id': 'udruge',
        'name': 'Udruga',
        'icon': 'bi-people-fill',
        'url': '/udruge/',
        'category': 'specijalizirani',
        'description': 'Clanovi, clanarine, donacije, eventi, EU fondovi, volonteri.',
        'counter_model': 'udruge.Clan',
    },
]

CATEGORIES = {
    'core': {'name': 'Osnovno', 'icon': 'bi-house', 'order': 0},
    'dokumenti': {'name': 'Dokumenti', 'icon': 'bi-file-earmark', 'order': 1},
    'financije': {'name': 'Financije', 'icon': 'bi-currency-euro', 'order': 2},
    'poslovanje': {'name': 'Poslovanje', 'icon': 'bi-briefcase', 'order': 3},
    'zaposlenici': {'name': 'Zaposlenici', 'icon': 'bi-person-badge', 'order': 4},
    'integracije': {'name': 'Integracije', 'icon': 'bi-plug', 'order': 5},
    'specijalizirani': {'name': 'Specijalizirani', 'icon': 'bi-stars', 'order': 6},
}

def get_module(module_id):
    for m in MODULES:
        if m['id'] == module_id:
            return m
    return None

def get_modules_by_category():
    result = {}
    for cat_id, cat_info in sorted(CATEGORIES.items(), key=lambda x: x[1]['order']):
        mods = [m for m in MODULES if m.get('category') == cat_id]
        if mods:
            result[cat_id] = {'info': cat_info, 'modules': mods}
    return result
