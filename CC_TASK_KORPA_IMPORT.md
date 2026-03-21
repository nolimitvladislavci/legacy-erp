# CC Task — Korpaš komitenti: kompletni uvoz iz Synesis MDB

## Pročitaj prvo
cat /var/www/fina-connect/FENIX_STATUS.md
cat /var/www/fina-connect/synesis/mdb_service.py

## Situacija (ne pretpostavljaj — ovo je stvarno stanje)

### Što je već u bazi (NE UVOZITI PONOVO):
- Korpaš d.o.o.: 307 partnera, 820 artikala — KOMPLET
- O.P.G. Kruljac Slađana: 402 partnera, 230 artikala — KOMPLET
- Furdi, obrt za građevinske radove: 6 partnera, 11 artikala — KOMPLET

### Što treba uvesti:
- **KUD DUKAT VLADISLAVCI**: 83 partnera nedostaje (MDB ima 103, 20 duplikata po OIB-u)
- **Dubinsko Čišćenje Čizo**: MDB ima 0 partnera/artikala — samo fakture iz Journal.mdb
- **Fakture iz Journal.mdb** za SVE firme — dosad nisu uvezene u Arhivu

### MDB putanje:
```
# Korpa direktno (preferiraj ove):
/var/www/fina-connect/Korpa/KORPAŠ d.o.o. 2025/
/var/www/fina-connect/Korpa/O.P.G. KRULJAC SLAĐANA 2025/
/var/www/fina-connect/Korpa/KUD DUKAT VLADISLAVCI 2025/

# SynesisArhiva (identičan sadržaj):
/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/KORPAµ d.o.o. 2025/
/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/FURDI, obrt 2025/
/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/DUBINSKO ¼IµÅENJE ¼IZO 2025/
/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/KUD DUKAT VLADISLAVCI 2025/
/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/O.P.G. KRULJAC SLAÐANA 2025/
```

## KORAK 0 — Pročitaj stvarna polja
```bash
# Company model
grep -n "oib\|name\|is_umbrella\|business_type\|country" /var/www/fina-connect/companies/models.py | head -20

# Partner model
grep -n "^class Partner\|oib\|name\|email\|phone\|iban\|partner_type\|synesis" /var/www/fina-connect/partners/models.py | head -30

# ArhivaEntry model
grep -n "^class ArhivaEntry\|doc_number\|amount\|partner_name\|source_type\|integrity_hash\|zki\|company" /var/www/fina-connect/documents/models.py | head -30

# mdb_service funkcije
grep -n "^def " /var/www/fina-connect/synesis/mdb_service.py
```

## KORAK 1 — Napiši management command

`/var/www/fina-connect/synesis/management/commands/import_korpa.py`

### Što command treba raditi:

```python
# Usage:
# venv/bin/python manage.py import_korpa              -- dry run, samo izvještaj
# venv/bin/python manage.py import_korpa --execute    -- pravi uvoz
# venv/bin/python manage.py import_korpa --only=kud   -- samo KUD
# venv/bin/python manage.py import_korpa --only=fakture  -- samo fakture

# MAPA firmi: MDB folder → Company u bazi
FIRMA_MAPA = {
    'kud': {
        'mdb': '/var/www/fina-connect/Korpa/KUD DUKAT VLADISLAVCI 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/KUD DUKAT VLADISLAVCI 2025/Journal.mdb',
        'company_filter': {'name__icontains': 'KUD Dukat'},
        'uvezi_partnere': True,
        'uvezi_artikle': False,  # KUD nema artikala
    },
    'dubinsko': {
        'mdb': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/DUBINSKO ¼IµÅENJE ¼IZO 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/DUBINSKO ¼IµÅENJE ¼IZO 2025/Journal.mdb',
        'company_filter': {'name__icontains': 'Dubinsko'},
        'uvezi_partnere': True,
        'uvezi_artikle': True,
    },
    'korpas': {
        'mdb': '/var/www/fina-connect/Korpa/KORPAŠ d.o.o. 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/KORPAŠ d.o.o. 2025/Journal.mdb',
        'company_filter': {'name__icontains': 'Korpaš', 'name__icontains': 'Korpa'},
        'uvezi_partnere': False,  # VEĆ UVEZENO
        'uvezi_artikle': False,   # VEĆ UVEZENO
    },
    'kruljac': {
        'mdb': '/var/www/fina-connect/Korpa/O.P.G. KRULJAC SLAĐANA 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/O.P.G. KRULJAC SLAĐANA 2025/Journal.mdb',
        'company_filter': {'name__icontains': 'Kruljac'},
        'uvezi_partnere': False,  # VEĆ UVEZENO
        'uvezi_artikle': False,   # VEĆ UVEZENO
    },
    'furdi': {
        'mdb': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/FURDI, obrt 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/FURDI, obrt 2025/Journal.mdb',
        'company_filter': {'name__icontains': 'Furdi'},
        'uvezi_partnere': False,  # VEĆ UVEZENO
        'uvezi_artikle': False,   # VEĆ UVEZENO
    },
}
```

### Logika uvoza partnera:
```python
def uvezi_partnere(company, mdb_path, dry_run=True):
    from synesis.mdb_service import read_partners
    from partners.models import Partner

    mdb_p = read_partners(mdb_path)
    existing_oibs = set(Partner.objects.filter(company=company).values_list('oib', flat=True))

    novi = 0
    skip = 0
    for p in mdb_p:
        oib = (p.get('oib') or '').strip()
        name = (p.get('name') or '').strip()
        if not name:
            skip += 1
            continue
        if oib and oib in existing_oibs:
            skip += 1
            continue
        if not dry_run:
            Partner.objects.get_or_create(
                company=company,
                oib=oib or '',
                defaults={
                    'name': name,
                    'city': p.get('city', ''),
                    'zip_code': p.get('zip_code', ''),
                    'address': p.get('street', ''),
                    'email': p.get('email', ''),
                    'phone': p.get('phone', ''),
                    'iban': p.get('iban', ''),
                    'partner_type': 'customer',
                    'notes': 'Uvezeno iz Synesis 2025',
                }
            )
            novi += 1
        else:
            novi += 1

    return novi, skip
```

### Logika uvoza faktura iz Journal.mdb u ArhivaEntry:

```python
# Tipovi dokumenata u Journal.mdb:
# XINVOICESB = izlazne fakture
# URAEU = ulazne fakture (URA)
# PRIMITAK = blagajna primici
# ITEMINPUT = ulaz robe/primke

def uvezi_fakture(company, journal_path, dry_run=True):
    from synesis.mdb_service import _mdb_export
    from documents.models import ArhivaEntry
    import hashlib
    from decimal import Decimal, InvalidOperation
    from datetime import datetime

    rows = _mdb_export(journal_path, 'Journal')

    tipovi_faktura = {
        'XINVOICESB': ('invoice_out', 'Izlazna faktura'),
        'URAEU':      ('invoice_in',  'Ulazna faktura'),
        'PRIMITAK':   ('receipt',     'Primka/primitak'),
        'ITEMINPUT':  ('receipt',     'Ulaz robe'),
    }

    uvezeno = 0
    preskoceno = 0

    for row in rows:
        doc_type = row.get('DOCUMENT', '').strip()
        if doc_type not in tipovi_faktura:
            continue

        source_type, opis = tipovi_faktura[doc_type]
        doc_number = str(row.get('DOCUMENT_NUMBER', '') or '').strip()
        partner_name = str(row.get('DOCUMENT_PARTNER', '') or '').strip()
        amount_str = str(row.get('DOCUMENT_AMMOUNT', '0') or '0').replace(',','.')
        date_str = str(row.get('DOCUMENT_DATE', '') or '').strip()

        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            amount = Decimal('0')

        try:
            # Synesis format: MM/DD/YY
            doc_date = datetime.strptime(date_str[:8], '%m/%d/%y').date() if date_str else None
        except:
            doc_date = None

        if not doc_number:
            preskoceno += 1
            continue

        # Provjeri duplikat
        key = f'SYN-{doc_type}-{doc_number}'
        if ArhivaEntry.objects.filter(company=company, doc_number=key).exists():
            preskoceno += 1
            continue

        if not dry_run:
            # integrity hash
            raw = f'{company.id}-{key}-{amount}-{doc_date}'
            h = hashlib.sha256(raw.encode()).hexdigest()

            ArhivaEntry.objects.create(
                company=company,
                doc_number=key,
                doc_date=doc_date,
                amount=amount,
                currency='EUR',
                source_type=source_type,
                partner_name=partner_name[:200],
                description=f'{opis} — uvezeno iz Synesis 2025',
                integrity_hash=h,
            )
            uvezeno += 1
        else:
            uvezeno += 1

    return uvezeno, preskoceno
```

## KORAK 2 — Provjeri ArhivaEntry polja PRIJE pisanja
```bash
grep -n "doc_number\|source_type\|integrity_hash\|partner_name\|description\|currency\|amount\|company\|doc_date" \
  /var/www/fina-connect/documents/models.py | head -30
```
Ako polje ne postoji — NE IZMIŠLJAJ, prilagodi kod.

## KORAK 3 — Pokreni dry run prvo
```bash
cd /var/www/fina-connect
venv/bin/python manage.py import_korpa
```

Očekivani output:
```
=== DRY RUN (--execute za pravi uvoz) ===
KUD Dukat: +83 partnera, 0 artikala, +XXX faktura
Dubinsko: +0 partnera, +0 artikala, +XXX faktura
Korpaš: PRESKOČENO (već uvezeno) — +XXX novih faktura iz Journal
Kruljac: PRESKOČENO (već uvezeno) — +XXX novih faktura iz Journal
Furdi: PRESKOČENO (već uvezeno) — +XXX novih faktura iz Journal
```

## KORAK 4 — Pravi uvoz
```bash
venv/bin/python manage.py import_korpa --execute
```

## KORAK 5 — Verifikacija
```bash
venv/bin/python manage.py shell -c "
from companies.models import Company
from partners.models import Partner
from documents.models import ArhivaEntry

for name in ['Korpaš','Kruljac','KUD Dukat','Furdi','Dubinsko']:
    c = Company.objects.filter(name__icontains=name.split()[0]).first()
    if c:
        p = Partner.objects.filter(company=c).count()
        a = ArhivaEntry.objects.filter(company=c).count()
        print(f'{c.name}: {p} partnera, {a} arhiva zapisa')
"
```

## KORAK 6 — Napiši /tmp/korpa_import_done.txt
Format:
```
DONE
KUD Dukat: +83 partnera, +XXX faktura
Dubinsko: +XXX faktura
Korpaš: +XXX faktura
Kruljac: +XXX faktura
Furdi: +XXX faktura
```

## Definicija DONE
- [ ] KUD Dukat: 83+ partnera uvezeno
- [ ] Fakture iz Journal.mdb u ArhivaEntry za sve firme
- [ ] Nema duplikata (provjeri OIB za partnere)
- [ ] Django check: 0 grešaka
- [ ] /tmp/korpa_import_done.txt postoji
