"""
═══════════════════════════════════════════════════════════════════════════
synesis/SCHEMA.py — KANONSKA ŠEMA MAPIRANJA SYNESIS MDB → LIMIT CONNECT
═══════════════════════════════════════════════════════════════════════════

Autor: CC Audit 2026-03-22
Verzija: 1.0
Firma: Konjik d.o.o. (OIB: 37590751921)

NAMJENA:
    Ovo je referentni dokument za SVE buduće Synesis importove.
    Svaka promjena u import logici MORA se reflektirati ovdje.

ARHITEKTURA SYNESISA:
    Synesis čuva podatke u Microsoft Access (.mdb) fajlovima.
    Svaki klijent ima svoj folder sa:
        - Storage.mdb  (partneri, artikli, računi, URA, plaće, inventar, banka)
        - Journal.mdb  (dnevnik knjiženja — NIJE KORIŠTEN u importu)
        - UserProfile.mdb (postavke — koristi se samo za OIB ekstrakciju)
        - Attachments.mdb (dokumenti — NIJE KORIŠTEN)
        - Kasa*.mdb     (blagajna — NIJE KORIŠTEN)

    Konjik kao knjigovodstveni servis ima:
        - /synesis/KONJIK/              → vlastiti MDB (Konjikovi podaci)
        - /synesis/KONJIK_ARHIVA/Synesis/{KLIJENT} {GODINA}/  → klijentski MDB-ovi

KRITIČNO PRAVILO:
    Svaki klijentski MDB MORA se importirati u ZASEBNU Company instancu.
    NIKAD ne importirati sve MDB-ove pod istu firmu!
    Koristiti: --per-client ili --filter {KLIJENT}

GREŠKA IZ PROŠLOSTI (2026-03):
    bulk_import_synesis --company "Konjik d.o.o." je uvezao SVE klijente
    pod Konjik record. Rezultat:
    - Konjik sam: D=2.545.113 EUR, 23.755 knjiženja
    - LC nakon importa: D=5.569.339 EUR, 42.494 knjiženja
    - Višak: +3.024.226 EUR, +18.739 knjiženja (69 klijenata)

VALIDACIJA:
    Excel export iz Synesisa (Podaci-KONJIK D.O.O.-2025.xls) služi kao
    referentna baza za validaciju. Nakon čistog importa:
    - Svaki konto MORA imati razliku D i P <= 0.01 EUR
    - Ukupni D mora biti = ukupni P (balansirano)
    - Broj knjiženja mora odgovarati XLS-u (±5% tolerancija za split)
═══════════════════════════════════════════════════════════════════════════
"""

# ═══════════════════════════════════════════════════════════════
# 1. SYNESIS MDB TABLICE → LC MODELI
# ═══════════════════════════════════════════════════════════════

SYNESIS_TO_LC = {
    # ── PARTNERI ──
    'PARTNERS': {
        'lc_model': 'partners.Partner',
        'key_field': 'PARTNER_ID',
        'dedup_by': ['oib', 'name'],  # provjeri oba prije kreacije
        'fields': {
            'PARTNER_ID':        {'lc': 'synesis_id',  'note': 'Interna šifra u Synesisu'},
            'PARTNER_NAME':      {'lc': 'name',        'max_len': 255},
            'PARTNER_VATNUMBER': {'lc': 'oib',         'max_len': 20, 'note': 'OIB ili VAT ID'},
            'PARTNER_MB':        {'lc': 'mb',          'max_len': 20, 'note': 'Matični broj'},
            'CITY_NAME':         {'lc': 'city',        'max_len': 100},
            'CITY_ZIPCODE':      {'lc': 'zip_code',    'max_len': 20},
            'PARTNER_STREET':    {'lc': 'address',     'max_len': 255},
            'PARTNER_IBAN':      {'lc': 'iban',        'max_len': 50},
            'PARTNER_EMAIL':     {'lc': 'email',       'max_len': 100},
            'PARTNER_PHONE':     {'lc': 'phone',       'max_len': 50},
            'PARTNER_MOBILE':    {'lc': 'phone',       'max_len': 50, 'note': 'fallback za phone'},
        },
    },

    # ── ARTIKLI ──
    'ITEMS': {
        'lc_model': 'inventory.InventoryItem',
        'key_field': 'ITEM_ID',
        'dedup_by': ['sku'],
        'fields': {
            'ITEM_ID':       {'lc': 'sku',            'max_len': 50},
            'ITEM_NAME':     {'lc': 'name',           'max_len': 255},
            'ITEM_MEASURE':  {'lc': 'unit',           'max_len': 20, 'default': 'KOM'},
            'ITEM_BARCODE':  {'lc': 'barcode',        'max_len': 50},
            'VAT_RATE':      {'lc': 'tax_rate',       'type': 'decimal'},
            'ITEM_NETPRICE': {'lc': 'purchase_price',  'type': 'decimal'},
            'ITEM_PRICE':    {'lc': 'selling_price',   'type': 'decimal'},
            'ITEMGROUP_NAME':{'lc': 'category',       'max_len': 100},
        },
    },

    # ── KONTNI PLAN ──
    'ACCOUNTS': {
        'lc_model': 'konto.KontoAccount',
        'key_field': 'ACC_NUMBER',
        'dedup_by': ['code'],
        'fields': {
            'ACC_NUMBER': {'lc': 'code',         'max_len': 12},
            'ACC_NAME':   {'lc': 'name',         'max_len': 200},
            'ACC_CLASS':  {'lc': 'account_type', 'note': 'Mapira se kroz CLASS_MAP'},
        },
        'class_map': {
            '0': 'asset',     # Dugotrajna imovina
            '1': 'asset',     # Kratkotrajna imovina
            '2': 'liability', # Obveze
            '3': 'asset',     # Potraživanja (note: u LC ovo je asset)
            '4': 'expense',   # Rashodi
            '5': 'expense',   # Troškovi
            '6': 'expense',   # Roba/Marža
            '7': 'income',    # Prihodi
            '8': 'expense',   # Posebni troškovi
            '9': 'equity',    # Kapital/Dobit
        },
    },

    # ── TEMELJNICE (DNEVNIK KNJIŽENJA) ──
    'ACCOUNTING + TACCOUNTING': {
        'lc_model': 'konto.JournalEntry + konto.LedgerLine',
        'header_table': 'ACCOUNTING',
        'lines_table': 'TACCOUNTING',
        'key_field': 'DIN',
        'dedup_by': ['entry_number'],  # Format: SYN-{year}-{trancode}-{din}
        'header_fields': {
            'DIN':       {'lc': 'internal_id',   'note': 'Document internal number'},
            'TRANCODE':  {'lc': 'trancode',      'note': 'Transaction code (broj temeljnice)'},
            'TRANDATE':  {'lc': 'date',          'type': 'date'},
            'REMARK':    {'lc': 'description',   'max_len': 300},
            'TRANID':    {'lc': 'source_type',   'note': 'INVOICE/PAYROLL/BANK → mapira tip'},
        },
        'line_fields': {
            'DIN':          {'lc': 'FK→journal_entry', 'note': 'Veza na header'},
            'ACC_NUMBER':   {'lc': 'account',         'note': 'FK→KontoAccount'},
            'ACC_DEBIT':    {'lc': 'amount (side=debit)',  'type': 'decimal'},
            'ACC_CREDIT':   {'lc': 'amount (side=credit)', 'type': 'decimal'},
            'ACC_TEXT':     {'lc': 'description',     'max_len': 200},
            'PARTNER_NAME': {'lc': 'description',     'note': 'Appendira se na opis'},
        },
        'rules': {
            'negative_debit': 'Negativni debit → flip to credit',
            'negative_credit': 'Negativni credit → flip to debit',
            'imbalance_tolerance': 'Razlika D-P <= 5.00 EUR → zaokruženje na konto 3999',
            'imbalance_reject': 'Razlika D-P > 5.00 EUR → SKIP s warning',
        },
    },

    # ── IZDANI RAČUNI ──
    'INVOICES + TINVOICES': {
        'lc_model': 'invoicing.Invoice + invoicing.InvoiceItem',
        'header_table': 'INVOICES',
        'lines_table': 'TINVOICES',
        'key_field': 'DIN',
        'header_fields': {
            'DIN':                {'lc': 'internal_id'},
            'INVOICE_NUMBER':     {'lc': 'invoice_number'},
            'INVOICE_DATE':       {'lc': 'issue_date',     'type': 'date'},
            'CUSTOMER_NAME':      {'lc': 'partner.name'},
            'CUSTOMER_VATNUMBER': {'lc': 'partner.oib'},
            'VAT_INVOICEAMMOUNT': {'lc': 'total',          'type': 'decimal'},
            'VAT_AMMOUNT':        {'lc': 'tax_amount',     'type': 'decimal'},
        },
        'line_fields': {
            'DIN':          {'lc': 'FK→invoice'},
            'ITEM_NAME':    {'lc': 'description'},
            'ITEM_AMMOUNT': {'lc': 'total_price',  'type': 'decimal'},
        },
    },

    # ── ULAZNI RAČUNI (URA) ──
    'URAEU + TURAEU': {
        'lc_model': 'konto.JournalEntry (source_type=invoice)',
        'header_table': 'URAEU',
        'lines_table': 'TURAEU',
        'key_field': 'DIN',
        'dedup_by': ['entry_number'],  # Format: URA-{year}-{trancode}
        'header_fields': {
            'DIN':                {'lc': 'internal_id'},
            'TRANCODE':           {'lc': 'trancode'},
            'TRANDATE':           {'lc': 'date',            'type': 'date'},
            'VENDOR_NAME':        {'lc': 'description',     'note': 'URA {br} -- {vendor}'},
            'VAT_INVOICENUMBER':  {'lc': 'description',     'note': 'Broj računa dobavljača'},
            'VAT_INVOICEAMMOUNT': {'lc': 'total_amount',    'type': 'decimal'},
            'VAT_DEDUCTABLE':     {'lc': 'vat_deductable',  'type': 'decimal'},
            'SE_VENDORACCOUNT':   {'lc': 'vendor_konto',    'default': '220'},
            'SE_VATPREPAIDR1ACCOUNT': {'lc': 'vat_konto',   'default': '1405'},
        },
        'fallback_rule': 'Ako TURAEU nema linije → generira D:4000/1405, P:220',
    },

    # ── ZAPOSLENICI ──
    'EMPLOYEES + WORKER': {
        'lc_model': 'worktime.EmployeeProfile',
        'key_field': 'STUFF_ID',
        'fields': {
            'STUFF_ID':          {'lc': 'synesis_id'},
            'STUFF_NAME':        {'lc': 'user.first_name + last_name'},
            'STUFF_OIB':         {'lc': 'oib'},
            'STUFF_DATEOFBIRTH': {'lc': 'date_of_birth', 'type': 'date'},
            'STUFF_CITY':        {'lc': 'city'},
        },
        'note': 'WORKER tablica dopunjuje EMPLOYEES (fallback za datum rođenja, grad)',
    },

    # ── PLAĆE ──
    'PAYROLL2 + TPAYROLL2': {
        'lc_model': 'payroll.PayrollRun + konto.JournalEntry',
        'key_field': 'PAYROLL_YEAR + PAYROLL_MONTH',
        'dedup_by': ['year', 'month'],
        'fields': {
            'PAYROLL_YEAR':          {'lc': 'year'},
            'PAYROLL_MONTH':         {'lc': 'month'},
            'PAYROLL_BRUTTOAMMOUNT': {'lc': 'total_gross', 'type': 'decimal'},
            'PAYROLL_FINALAMMOUNT':  {'lc': 'total_net',   'type': 'decimal'},
            'PAYROLL_TAXTOTAL':      {'lc': 'total_tax',   'type': 'decimal'},
            'USEROIB':               {'lc': 'company.oib', 'note': 'OIB firme za provjeru'},
        },
        'journal_entry': {
            'entry_number': 'PLACA-{year}-{month:02d}',
            'konto_debit':  '4200 (Bruto plaće)',
            'konto_credit': ['2400 (Neto)', '2401 (Porez)', '2402 (Doprinosi)'],
            'balance_rule': 'Razlika → 3999 (Zaokruženja)',
        },
    },

    # ── BANKARSKI RAČUNI ──
    'BANKACCOUNTS + BANK': {
        'lc_model': 'konto.BankAccount',
        'key_field': 'BANK_IBAN',
        'dedup_by': ['iban'],
        'fields': {
            'BANK_IBAN':        {'lc': 'iban',       'min_len': 10},
            'BANK_NAME':        {'lc': 'name'},
            'BANKNAME':         {'lc': 'bank_name',  'note': 'Alternativno polje'},
            'BANK_SWIFT':       {'lc': 'swift'},
            'BANK_BOOKACCOUNT': {'lc': 'konto_account', 'note': 'FK→KontoAccount po code'},
        },
    },

    # ── PRIMKE (MALOPRODAJA) ──
    'RETAIL + TRETAIL': {
        'lc_model': 'inventory.GoodsReceipt + GoodsReceiptItem',
        'header_table': 'RETAIL',
        'lines_table': 'TRETAIL',
        'key_field': 'DIN',
        'note': 'Delegira na synesis.views._import_retail()',
    },
}


# ═══════════════════════════════════════════════════════════════
# 2. SYNESIS EXCEL EXPORT ŠEMA (za validaciju)
# ═══════════════════════════════════════════════════════════════

SYNESIS_EXCEL_SHEETS = {
    'Dnevnik_knjiženja': {
        'columns': [
            'DATUM_KNJIZENJA',   # DATETIME → date
            'NAZIV_DOKUMENTA',   # CHAR(20) — tip dokumenta (PKV promet, Izvod, URA, Račun...)
            'BROJ_DOKUMENTA',    # DOUBLE → int — broj temeljnice
            'ORG_DIO',           # CHAR(30) — organizacijski dio (prazno za mali obrt)
            'KONTO',             # CHAR(12) — šifra konta
            'SIFRA_PARTNERA',    # DOUBLE → int — FK na Partneri
            'OPIS_KNJIZENJA',    # CHAR(25) — opis stavke
            'DUGUJE',            # DOUBLE → Decimal(12,2)
            'POTRAZUJE',         # DOUBLE → Decimal(12,2)
        ],
        'validation': {
            'balance': 'SUM(DUGUJE) MUST == SUM(POTRAZUJE)',
            'tolerance': '0.01 EUR',
        },
    },
    'Kontni_Plan': {
        'columns': ['KONTO', 'NAZIV_KONTA', 'VRSTA_ANALITIKE'],
    },
    'Knjiga_URA': {
        'columns': [
            'DATUM_KNJIŽENJA', 'BROJ', 'BROJ_RAČUNA', 'DATUM_RAČUNA',
            'DOBAVLJAČ', 'MJESTO', 'OIB',
            'OSNOVICA_5', 'OSNOVICA_10', 'OSNOVICA_25',
            'IZNOS_RAČUNA_S_PDV', 'PRETPOREZ',
            'ODBIJA_SE_5', 'NE_ODBIJA_SE_5', 'ODBIJA_SE_10',
            'NE_ODBIJA_SE_10', 'ODBIJA_SE_25', 'NE_ODBIJA_SE_25',
            'OPIS',
        ],
    },
    'Dnevnik_inventara': {
        'columns': [
            'DATUM', 'NAZIV_DOKUMENTA', 'BROJ', 'ŠIFRA_INVENTARA',
            'NAZIV_INVENTARA', 'OPIS', 'KONTO_NABAVE',
            'DUGUJE', 'POTRAŽUJE', 'KONTO_ISPRAVKA',
            'ISPRAVAK_DUGUJE', 'ISPRAVAK_POTRAŽUJE',
        ],
    },
    'Partneri': {
        'columns': ['SIFRA_PARTNERA', 'NAZIV_PARTNERA', 'PARTNER_OIB', 'MJESTO', 'ADRESA'],
    },
    'Opis_Tablica': {
        'columns': ['NAZIV_TABLICE', 'OPIS_TABLICE'],
        'note': 'Metadata — schema opisi za svaku tablicu',
    },
}


# ═══════════════════════════════════════════════════════════════
# 3. FOLDER STRUKTURA SYNESIS ARHIVE
# ═══════════════════════════════════════════════════════════════

ARCHIVE_STRUCTURE = """
/var/www/fina-connect/synesis/
├── KONJIK/                          ← Konjik vlastiti podaci
│   ├── Storage.mdb                  ← Glavni MDB (partneri, artikli, računi)
│   ├── Journal.mdb                  ← Dnevnik (NE KORISTI SE u importu)
│   ├── UserProfile.mdb              ← Postavke (OIB ekstrakcija)
│   ├── Attachments.mdb              ← Dokumenti (NE KORISTI SE)
│   └── Kasa2025-01.mdb             ← Blagajna (NE KORISTI SE)
│
├── KONJIK_ARHIVA/Synesis/           ← Klijentske baze
│   ├── AGROVLADISLAVCI 2025/        ← Svaki klijent = 1 folder
│   │   ├── Storage.mdb
│   │   └── Journal.mdb
│   ├── ARAMBAŠIĆ 2025/
│   │   ├── Storage.mdb
│   │   └── Journal.mdb
│   ├── FAST 2025/                   ← Najveći klijent (5037 partnera)
│   │   ├── Storage.mdb
│   │   └── Journal.mdb
│   └── ... (69 klijenata)
│
└── management/commands/
    └── bulk_import_synesis.py       ← Import skripta
"""


# ═══════════════════════════════════════════════════════════════
# 4. PRAVILA IMPORTA
# ═══════════════════════════════════════════════════════════════

IMPORT_RULES = {
    'GOLDEN_RULE': 'Svaki MDB = zasebna Company. NIKAD sve u jednu.',

    'dedup_strategy': {
        'partners':    'Provjeri OIB pa ime. Ako postoji → skip.',
        'items':       'Provjeri SKU. Ako postoji → skip.',
        'accounts':    'update_or_create po code. Uvijek ažuriraj ime.',
        'temeljnice':  'entry_number = SYN-{year}-{trancode}-{din}. Ako postoji → skip.',
        'ura':         'entry_number = URA-{year}-{trancode}. Ako postoji → skip.',
        'invoices':    'Delegira na synesis.views._import_invoices(). Po broju računa.',
        'employees':   'Delegira na synesis.views._import_employees(). Po OIB-u.',
        'payroll':     'get_or_create po (year, month). Ako postoji → skip.',
        'bank':        'update_or_create po IBAN-u.',
    },

    'negative_amounts': {
        'rule': 'Negativni debit → pretvoriti u credit. Negativni credit → pretvoriti u debit.',
        'reason': 'Synesis ponekad koristi negativne iznose za storniranja.',
    },

    'balance_tolerance': {
        'threshold': 5.00,  # EUR
        'action': 'Razlika <= 5 EUR → dodaj zaokruženje na konto 3999',
        'reject': 'Razlika > 5 EUR → SKIP temeljnicu s warningom',
    },

    'date_formats': [
        '%m/%d/%y %H:%M:%S',  # US format (najčešći u Synesisu)
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%y',
        '%m/%d/%Y',
        '%d.%m.%Y',           # HR format
        '%Y-%m-%d',           # ISO
        '%Y-%m-%d %H:%M:%S',
    ],

    'validation_after_import': {
        'step_1': 'Učitaj Excel export iz Synesisa za istu firmu',
        'step_2': 'Za svaki konto usporedi SUM(DUGUJE) i SUM(POTRAZUJE)',
        'step_3': 'Razlika po kontu mora biti <= 0.01 EUR',
        'step_4': 'Ukupno D mora biti == ukupno P (balansirano)',
        'step_5': 'Broj knjiženja: LC vs XLS, razlika <= 5%',
    },
}


# ═══════════════════════════════════════════════════════════════
# 5. ISPRAVNA KOMANDA ZA IMPORT
# ═══════════════════════════════════════════════════════════════

CORRECT_USAGE = """
# ── ISPRAVNO: svaki klijent u svoju firmu ──
python manage.py bulk_import_synesis --per-client --type all

# ── ISPRAVNO: samo Konjik ──
python manage.py bulk_import_synesis --company "Konjik d.o.o." --filter "KONJIK D.O.O." --type all

# ── ISPRAVNO: jedan specifičan klijent ──
python manage.py bulk_import_synesis --per-client --filter "AGROVLADISLAVCI" --type all

# ── ANALIZA bez importa ──
python manage.py bulk_import_synesis --analyze

# ── DRY RUN (preview) ──
python manage.py bulk_import_synesis --per-client --dry-run

# ═══ POGREŠNO — NIKAD NE RADITI ═══
# python manage.py bulk_import_synesis --company "Konjik d.o.o." --type all
# ↑ OVO UVOZI SVE KLIJENTE U KONJIK!
"""


# ═══════════════════════════════════════════════════════════════
# 6. CLEANUP PROCEDURA (za popravak pogrešnog importa)
# ═══════════════════════════════════════════════════════════════

CLEANUP_PROCEDURE = """
1. Identificiraj entry_number prefikse koji NISU Konjikovi:
   - KONJIK D.O.O. 2025 → OVO JE ISPRAVNO
   - FAST 2025, AGROVLADISLAVCI 2025, ... → OVO OBRISATI

2. Iz SynesisLog dohvati sve importirane source foldere za Konjik

3. Obriši LedgerLine + JournalEntry za tuđe entry_numbere

4. Obriši tuđe partnere (provjeri da nisu referencirani u računima)

5. Obriši tuđe artikle (provjeri inventory referencije)

6. Reimportiraj sa --per-client

7. Validiraj Konjik vs Excel (razlika po kontu <= 0.01 EUR)
"""
