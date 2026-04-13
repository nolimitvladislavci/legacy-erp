"""
core/management/commands/fill_company_addresses.py

Jednorazni + periodic fill — popuni prazne adrese iz partners_partner podataka.
Logika: za svaku Company bez adrese, pronađi Partner s istim OIB-om koji IMA adresu.

Može se pokretati sigurno više puta (idempotentno).
"""
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Popuni prazne company adrese iz partner podataka (Synesis import)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Samo prikaži što bi napravio')
        parser.add_argument('--vies', action='store_true', help='Pokušaj VIES lookup za firme bez partnera')

    def handle(self, *args, **options):
        from companies.models import Company
        from partners.models import Partner

        dry_run = options['dry_run']
        use_vies = options['vies']

        # Firme bez adrese, s validnim OIB-om (11 znamenki, ne debug)
        empty = Company.objects.filter(
            is_vaulted=False,
        ).filter(
            Q(address__isnull=True) | Q(address='')
        ).exclude(
            Q(oib='') | Q(oib__isnull=True) |
            Q(oib__startswith='SYN') |
            Q(oib__startswith='999') |
            Q(oib__startswith='888') |
            Q(oib__startswith='000')
        ).filter(oib__regex=r'^\d{11}$')

        self.stdout.write(f'Firmi bez adrese s validnim OIB: {empty.count()}')

        filled = 0
        vies_filled = 0
        failed = []

        for company in empty:
            # 1. Probaj iz partnera (Synesis import)
            partner = Partner.objects.filter(
                oib=company.oib,
            ).exclude(
                Q(address__isnull=True) | Q(address='')
            ).order_by('-updated_at').first()

            if partner:
                if dry_run:
                    self.stdout.write(f'  [DRY] {company.name} ({company.oib}) ← {partner.address}, {partner.city} {partner.zip_code}')
                else:
                    company.address = partner.address
                    if partner.city and not company.city:
                        company.city = partner.city
                    if partner.zip_code and not company.zip_code:
                        company.zip_code = partner.zip_code
                    company.save(update_fields=['address', 'city', 'zip_code', 'updated_at'])
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {company.name} ← {partner.address}, {partner.city}'
                    ))
                filled += 1
                continue

            # 2. Probaj VIES lookup
            if use_vies:
                try:
                    from core.business_lookup import lookup_business
                    result = lookup_business(company.oib, 'HR')
                    if result.found and result.address:
                        if dry_run:
                            self.stdout.write(f'  [DRY/VIES] {company.name} ({company.oib}) ← {result.address}, {result.city}')
                        else:
                            company.address = result.address
                            if result.city:
                                company.city = result.city
                            if result.zip_code:
                                company.zip_code = result.zip_code
                            company.save(update_fields=['address', 'city', 'zip_code', 'updated_at'])
                            self.stdout.write(self.style.SUCCESS(
                                f'  ✓ [VIES] {company.name} ← {result.address}, {result.city}'
                            ))
                        vies_filled += 1
                        continue
                except ImportError as e:
                    self.stdout.write(self.style.WARNING(f'  VIES error {company.oib}: {e}'))

            failed.append(f'{company.name} ({company.oib})')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Popunjeno iz partnera: {filled}'))
        if use_vies:
            self.stdout.write(self.style.SUCCESS(f'Popunjeno iz VIES: {vies_filled}'))
        if failed:
            self.stdout.write(self.style.WARNING(f'Nije pronađeno: {len(failed)}'))
            for f in failed[:20]:
                self.stdout.write(f'  ✗ {f}')
