"""
Cache warming — predpuni Redis s najčešće dohvaćanim podacima.
Pokreće se automatski nakon gunicorn restart-a (ExecStartPost).

Korištenje:
  python manage.py warm_cache
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import DatabaseError


class Command(BaseCommand):
    help = 'Predpuni Redis cache za produkciju'

    def handle(self, *args, **options):
        warmed = 0

        # 1. Sve aktivne kompanije (koriste se na svakom requestu)
        from companies.models import Company
        companies = list(Company.objects.all().values(
            'id', 'name', 'oib', 'country',
        ))
        cache.set('all_active_companies', companies, 3600)
        warmed += 1
        self.stdout.write(f'  Companies: {len(companies)}')

        # 2. POS terminali po company
        try:
            from pos.models import POSTerminal
            terminals = POSTerminal.objects.filter(is_active=True).select_related('company')
            for terminal in terminals:
                key = f'pos_terminal_{terminal.id}'
                cache.set(key, {
                    'id': str(terminal.id),
                    'name': terminal.name,
                    'company_id': str(terminal.company_id),
                    'pos_type': terminal.pos_type,
                }, 1800)
                warmed += 1
            self.stdout.write(f'  POS terminals: {terminals.count()}')
        except DatabaseError as e:
            self.stdout.write(f'  POS terminals: skip ({e})')

        # 3. Tax rates (globalne, mijenjaju se rijetko)
        try:
            from companies.models import TaxRate
            for country in ['HR', 'DE', 'AT', 'SI']:
                rates = list(TaxRate.objects.filter(country=country).values())
                if rates:
                    cache.set(f'tax_rates_{country}', rates, 86400)
                    warmed += 1
            self.stdout.write('  Tax rates: HR/DE/AT/SI')
        except DatabaseError as e:
            self.stdout.write(f'  Tax rates: skip ({e})')

        # 4. NKD kodovi (statički)
        try:
            from companies.models import NKDCode
            if NKDCode.objects.exists():
                nkd = list(NKDCode.objects.values('code', 'name_hr', 'section')[:500])
                cache.set('nkd_codes_top500', nkd, 86400)
                warmed += 1
                self.stdout.write(f'  NKD codes: {len(nkd)}')
        except DatabaseError as e:
            self.stdout.write(f'  NKD codes: skip ({e})')

        # 5. Module registry (koristi se za sidebar/nav)
        try:
            from companies.module_registry import MODULE_REGISTRY
            cache.set('module_registry', MODULE_REGISTRY, 86400)
            warmed += 1
            self.stdout.write(f'  Module registry: {len(MODULE_REGISTRY)} modules')
        except ImportError:
            pass

        # 6. Regulatory sources (za BORG)
        try:
            from limit_connect_ai.models_knowledge_graph import RegulatorySource
            sources = list(RegulatorySource.objects.filter(is_active=True).values(
                'id', 'name', 'source_type', 'scrape_interval_hours'))
            cache.set('regulatory_sources', sources, 3600)
            warmed += 1
        except DatabaseError:
            pass

        self.stdout.write(self.style.SUCCESS(f'\nCache warm complete: {warmed} keys set'))
