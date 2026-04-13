"""
Management command: fix_account_types

Ispravlja account_type za KontoAccount prema HR RRF ili DE SKR standardu.
Razlikuje HR i DE firme po company.country polju.

HR RRF:
  0=dugotr.imovina(asset), 1=kratkotr.imovina(asset), 2=kratkoroč.obveze(liability)
  3=zalihe(asset), 4-6=troškovi(expense), 7=prihodi(revenue)
  8=rezultat(equity, osim 803/810=expense), 9=kapital+dugoroč.obveze

DE SKR03:
  0=dugotr.imovina(asset), 1=financ.imovina+obveze(mixed), 2=kapital(equity)
  3=zalihe(asset), 4=prihodi(revenue), 5-6=troškovi(expense)
  7=troškovi(expense), 8=financ.rashodi/prihodi(mixed), 9=statistički
"""
from django.core.management.base import BaseCommand
from konto.models import KontoAccount
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


# ── HR RRF ──
HR_TYPE_MAP = {
    '0': 'asset', '1': 'asset', '2': 'liability', '3': 'asset',
    '4': 'expense', '5': 'expense', '6': 'expense', '7': 'revenue',
}
HR_CLASS8_MAP = {
    '800': 'equity', '801': 'equity', '802': 'equity',
    '803': 'expense', '804': 'equity', '810': 'expense',
    '811': 'liability', '89': 'equity',
}
HR_CLASS9_LIABILITY = ('94', '95', '96')

# ── DE SKR03 ──
DE_TYPE_MAP = {
    '0': 'asset', '3': 'asset',
    '4': 'revenue', '5': 'expense', '6': 'expense', '7': 'expense',
}
DE_CLASS1_MAP = {
    '10': 'asset', '11': 'asset', '12': 'asset', '13': 'asset', '14': 'asset',
    '15': 'asset', '16': 'liability', '17': 'liability', '18': 'liability',
    '19': 'liability',
}
DE_CLASS2_MAP = {
    '20': 'equity', '21': 'equity', '22': 'equity', '23': 'equity',
    '24': 'liability', '25': 'liability', '26': 'liability',
    '27': 'liability', '28': 'liability', '29': 'equity',
}
DE_CLASS8_MAP = {
    '80': 'expense', '81': 'expense', '82': 'expense',
    '83': 'income', '84': 'income', '85': 'income',
    '86': 'expense', '87': 'expense', '88': 'income', '89': 'equity',
}


class Command(BaseCommand):
    help = 'Ispravlja account_type prema HR RRF / DE SKR standardu'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--company', type=str, help='Filter po imenu firme')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        company_filter = options.get('company')

        qs = KontoAccount.objects.select_related('company').all()
        if company_filter:
            qs = qs.filter(company__name__icontains=company_filter)

        fixed = 0
        unchanged = 0
        by_country = {'HR': 0, 'DE': 0, 'other': 0}

        for acc in qs.iterator():
            code = acc.code.strip()
            if not code or not code[0].isdigit():
                unchanged += 1
                continue

            country = (acc.company.country or 'HR').upper() if acc.company else 'HR'
            new_type = self._determine_type(code, country)

            if new_type and new_type != acc.account_type:
                if not dry_run:
                    acc.account_type = new_type
                    acc.save(update_fields=['account_type'])
                fixed += 1
                by_country[country if country in ('HR', 'DE') else 'other'] += 1
            else:
                unchanged += 1

        mode = "DRY RUN" if dry_run else "APPLIED"
        self.stdout.write(f"\nfix_account_types [{mode}]")
        self.stdout.write(f"  Fixed: {fixed} (HR:{by_country['HR']}, DE:{by_country['DE']})")
        self.stdout.write(f"  Unchanged: {unchanged}")

        if fixed > 0 and not dry_run:
            self.stdout.write(self.style.SUCCESS(f"{fixed} konto racuna ispravljeno."))
        elif fixed > 0:
            self.stdout.write(self.style.WARNING(
                f"{fixed} bi bilo ispravljeno. Pokreni bez --dry-run."))
        else:
            self.stdout.write(self.style.SUCCESS("Svi tipovi su ispravni."))

    def _determine_type(self, code, country='HR'):
        klasa = code[0]

        if country == 'DE':
            return self._determine_de(code, klasa)
        return self._determine_hr(code, klasa)

    def _determine_hr(self, code, klasa):
        if klasa == '8':
            for plen in (4, 3, 2):
                if code[:plen] in HR_CLASS8_MAP:
                    return HR_CLASS8_MAP[code[:plen]]
            return 'equity'
        if klasa == '9':
            if len(code) >= 2 and code[:2] in HR_CLASS9_LIABILITY:
                return 'liability'
            return 'equity'
        return HR_TYPE_MAP.get(klasa)

    def _determine_de(self, code, klasa):
        if klasa == '1' and len(code) >= 2:
            return DE_CLASS1_MAP.get(code[:2], 'asset')
        if klasa == '2' and len(code) >= 2:
            return DE_CLASS2_MAP.get(code[:2], 'equity')
        if klasa == '8' and len(code) >= 2:
            return DE_CLASS8_MAP.get(code[:2], 'expense')
        return DE_TYPE_MAP.get(klasa)
