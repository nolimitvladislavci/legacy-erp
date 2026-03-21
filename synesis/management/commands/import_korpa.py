"""Korpa import — partneri + fakture iz Synesis MDB u LIMIT Connect."""
import hashlib
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.utils import timezone


FIRMA_MAPA = {
    'kud': {
        'mdb': '/var/www/fina-connect/Korpa/KUD DUKAT VLADISLAVCI 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/KUD DUKAT VLADISLAVCI 2025/Journal.mdb',
        'oib': '12817544866',
        'uvezi_partnere': True,
        'uvezi_artikle': False,
    },
    'dubinsko': {
        'mdb': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/DUBINSKO \xbcI\xb5\xc5ENJE \xbcIZO 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/DUBINSKO \xbcI\xb5\xc5ENJE \xbcIZO 2025/Journal.mdb',
        'oib': '69824516722',
        'uvezi_partnere': True,
        'uvezi_artikle': True,
    },
    'korpas': {
        'mdb': '/var/www/fina-connect/Korpa/KORPA\u0160 d.o.o. 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/KORPA\u0160 d.o.o. 2025/Journal.mdb',
        'oib': '92922919857',
        'uvezi_partnere': False,
        'uvezi_artikle': False,
    },
    'kruljac': {
        'mdb': '/var/www/fina-connect/Korpa/O.P.G. KRULJAC SLA\u0110ANA 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/O.P.G. KRULJAC SLA\u0110ANA 2025/Journal.mdb',
        'oib': '41439993573',
        'uvezi_partnere': False,
        'uvezi_artikle': False,
    },
    'furdi': {
        'mdb': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/FURDI, obrt 2025/Storage.mdb',
        'journal': '/var/www/fina-connect/Korpa/SynesisArhiva/Synesis/Synesis/FURDI, obrt 2025/Journal.mdb',
        'oib': '88069902084',
        'uvezi_partnere': False,
        'uvezi_artikle': False,
    },
}

TIPOVI_FAKTURA = {
    'XINVOICESB': ('invoice_out', 'Izlazna faktura'),
    'URAEU': ('invoice_in', 'Ulazna faktura'),
    'PRIMITAK': ('receipt', 'Primitak'),
    'ITEMINPUT': ('receipt', 'Ulaz robe'),
}


class Command(BaseCommand):
    help = 'Uvoz Korpa partnera i faktura iz Synesis MDB'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Pravi uvoz (inače dry run)')
        parser.add_argument('--only', type=str, help='Samo jedna firma: kud, dubinsko, korpas, kruljac, furdi')
        parser.add_argument('--only-fakture', action='store_true', help='Samo fakture, bez partnera')

    def handle(self, *args, **options):
        execute = options['execute']
        only = options.get('only')
        only_fakture = options.get('only_fakture', False)

        if not execute:
            self.stdout.write(self.style.WARNING('=== DRY RUN (dodaj --execute za pravi uvoz) ===\n'))

        firme = {only: FIRMA_MAPA[only]} if only and only in FIRMA_MAPA else FIRMA_MAPA
        results = []

        for key, conf in firme.items():
            self.stdout.write(self.style.MIGRATE_HEADING('--- %s ---' % key.upper()))

            # Nađi firmu
            from companies.models import Company
            company = Company.objects.filter(oib=conf['oib']).first()
            if not company:
                self.stdout.write(self.style.ERROR('  Firma OIB %s nije pronađena!' % conf['oib']))
                continue
            self.stdout.write('  Firma: %s (OIB: %s)' % (company.name, company.oib))

            partneri_novi = 0
            partneri_skip = 0
            fakture_novi = 0
            fakture_skip = 0

            # Partneri
            if conf['uvezi_partnere'] and not only_fakture:
                mdb_path = conf['mdb']
                if os.path.exists(mdb_path):
                    partneri_novi, partneri_skip = self._uvezi_partnere(company, mdb_path, execute)
                    self.stdout.write('  Partneri: +%d novih, %d preskočeno' % (partneri_novi, partneri_skip))
                else:
                    self.stdout.write(self.style.WARNING('  Storage.mdb ne postoji: %s' % mdb_path))

            # Fakture iz Journal.mdb
            journal_path = conf['journal']
            if os.path.exists(journal_path):
                fakture_novi, fakture_skip = self._uvezi_fakture(company, journal_path, execute)
                self.stdout.write('  Fakture: +%d novih, %d preskočeno' % (fakture_novi, fakture_skip))
            else:
                self.stdout.write(self.style.WARNING('  Journal.mdb ne postoji: %s' % journal_path))

            results.append('%s: +%d partnera, +%d faktura' % (company.name, partneri_novi, fakture_novi))

        # Summary
        self.stdout.write('\n' + self.style.SUCCESS('=== REZULTAT ==='))
        for r in results:
            self.stdout.write('  ' + r)

        if execute:
            with open('/tmp/korpa_import_done.txt', 'w') as f:
                f.write('DONE\n')
                for r in results:
                    f.write(r + '\n')
            self.stdout.write(self.style.SUCCESS('\nDONE — rezultat u /tmp/korpa_import_done.txt'))

    def _uvezi_partnere(self, company, mdb_path, execute):
        from synesis.mdb_service import read_partners
        from partners.models import Partner

        mdb_p = read_partners(mdb_path)
        existing_oibs = set(
            Partner.objects.filter(company=company)
            .exclude(oib='')
            .values_list('oib', flat=True)
        )
        existing_names = set(
            Partner.objects.filter(company=company)
            .values_list('name', flat=True)
        )

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
            if name in existing_names:
                skip += 1
                continue

            if execute:
                Partner.objects.create(
                    company=company,
                    name=name,
                    oib=oib or ('SYN-%s' % p.get('synesis_id', name[:8])),
                    city=(p.get('city') or '').strip(),
                    zip_code=(p.get('zip_code') or '').strip(),
                    address=(p.get('street') or '').strip(),
                    email=(p.get('email') or '').strip(),
                    phone=(p.get('phone') or '').strip(),
                    partner_type='both',
                )
            novi += 1

        return novi, skip

    def _uvezi_fakture(self, company, journal_path, execute):
        from synesis.mdb_service import _mdb_export
        from documents.models import ArhivaEntry

        rows = _mdb_export(journal_path, 'Journal')
        if not rows:
            # Probaj tablice
            from synesis.mdb_service import _mdb_tables
            tables = _mdb_tables(journal_path)
            self.stdout.write('  Journal tablice: %s' % ', '.join(tables[:10]))
            return 0, 0

        uvezeno = 0
        preskoceno = 0

        for row in rows:
            doc_type = (row.get('DOCUMENT') or '').strip()
            if doc_type not in TIPOVI_FAKTURA:
                continue

            source_type, opis = TIPOVI_FAKTURA[doc_type]
            doc_number = str(row.get('DOCUMENT_NUMBER') or row.get('DIN') or '').strip()
            partner_name = str(row.get('DOCUMENT_PARTNER') or row.get('PARTNER_NAME') or '').strip()
            amount_str = str(row.get('DOCUMENT_AMMOUNT') or row.get('AMMOUNT') or '0').replace(',', '.')
            date_str = str(row.get('DOCUMENT_DATE') or row.get('INVOICE_DATE') or '').strip()

            try:
                amount = abs(Decimal(amount_str))
            except (InvalidOperation, ValueError):
                amount = Decimal('0')

            doc_date = None
            for fmt in ('%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d', '%d.%m.%Y', '%d.%m.%Y.'):
                try:
                    doc_date = datetime.strptime(date_str[:10], fmt).date()
                    break
                except (ValueError, IndexError):
                    continue

            if not doc_number:
                preskoceno += 1
                continue

            key = 'SYN-%s-%s' % (doc_type, doc_number)
            if ArhivaEntry.objects.filter(company=company, doc_number=key).exists():
                preskoceno += 1
                continue

            if execute:
                raw = '%s-%s-%s-%s' % (company.pk, key, amount, doc_date)
                h = hashlib.sha256(raw.encode()).hexdigest()

                ArhivaEntry.objects.create(
                    company=company,
                    doc_number=key,
                    doc_date=doc_date or timezone.now().date(),
                    amount=amount,
                    currency='EUR',
                    source_type=source_type,
                    partner_name=partner_name[:200],
                    integrity_hash=h,
                )
            uvezeno += 1

        return uvezeno, preskoceno
