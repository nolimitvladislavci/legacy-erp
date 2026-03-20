"""Management command: python manage.py seed_konto [--company_id=X] [--country=HR|DE]"""
from django.core.management.base import BaseCommand
from konto.models import KontoAccount


HR_CHART = [
    # (code, name, account_type)
    ('0100', 'Nematerijalna imovina', 'asset'),
    ('0200', 'Materijalna imovina', 'asset'),
    ('0300', 'Dugotrajna financijska imovina', 'asset'),
    ('1000', 'Žiro račun', 'asset'),
    ('1010', 'Devizni račun', 'asset'),
    ('1100', 'Blagajna', 'asset'),
    ('1200', 'Potraživanja od kupaca', 'asset'),
    ('1300', 'Potraživanja od zaposlenih', 'asset'),
    ('1400', 'Pretporez (ulazni PDV)', 'asset'),
    ('1500', 'Potraživanja od države', 'asset'),
    ('1600', 'Dani avansi', 'asset'),
    ('2000', 'Kratkoročne obveze', 'liability'),
    ('2100', 'Obveze za plaće', 'liability'),
    ('2200', 'Obveze prema dobavljačima', 'liability'),
    ('2300', 'Obveze za poreze i doprinose', 'liability'),
    ('2400', 'Obveze za PDV', 'liability'),
    ('2500', 'Primljeni avansi', 'liability'),
    ('2600', 'Ostale kratkoročne obveze', 'liability'),
    ('2700', 'Dugoročne obveze', 'liability'),
    ('2800', 'Obveze po kreditima', 'liability'),
    ('3000', 'Zalihe', 'asset'),
    ('3100', 'Zalihe sirovina', 'asset'),
    ('3200', 'Zalihe gotovih proizvoda', 'asset'),
    ('3300', 'Zalihe trgovačke robe', 'asset'),
    ('4000', 'Materijalni troškovi', 'expense'),
    ('4100', 'Troškovi sirovina i materijala', 'expense'),
    ('4200', 'Troškovi energije', 'expense'),
    ('4300', 'Troškovi usluga', 'expense'),
    ('4400', 'Ostali materijalni troškovi', 'expense'),
    ('4500', 'Troškovi osoblja (plaće)', 'expense'),
    ('4600', 'Doprinosi na plaće', 'expense'),
    ('4700', 'Amortizacija', 'expense'),
    ('4800', 'Ostali troškovi poslovanja', 'expense'),
    ('4900', 'Financijski rashodi', 'expense'),
    ('5000', 'Troškovi reprezentacije', 'expense'),
    ('5100', 'Troškovi prijevoza', 'expense'),
    ('5200', 'Troškovi najma', 'expense'),
    ('5300', 'Troškovi osiguranja', 'expense'),
    ('5400', 'Troškovi telefona i interneta', 'expense'),
    ('7000', 'Prihodi od prodaje', 'income'),
    ('7100', 'Prihodi od usluga', 'income'),
    ('7200', 'Prihodi od najma', 'income'),
    ('7300', 'Prihodi od kamata', 'income'),
    ('7400', 'Tečajne razlike (prihod)', 'income'),
    ('7500', 'Financijski prihodi', 'income'),
    ('7600', 'Ostali prihodi', 'income'),
    ('9000', 'Temeljni kapital', 'equity'),
    ('9100', 'Kapitalne rezerve', 'equity'),
    ('9200', 'Zadržana dobit', 'equity'),
    ('9300', 'Dobit/gubitak tekuće godine', 'equity'),
]

DE_CHART = [
    # SKR03 (Standardkontenrahmen)
    ('0100', 'Immaterielle Vermögensgegenstände', 'asset'),
    ('0200', 'Sachanlagen', 'asset'),
    ('0400', 'Finanzanlagen', 'asset'),
    ('1000', 'Kasse', 'asset'),
    ('1200', 'Forderungen aus Lieferungen und Leistungen', 'asset'),
    ('1300', 'Sonstige Forderungen', 'asset'),
    ('1400', 'Forderungen §13b UStG', 'asset'),
    ('1500', 'Sonstige Vermögensgegenstände', 'asset'),
    ('1571', 'Vorsteuer 7%', 'asset'),
    ('1576', 'Vorsteuer 19%', 'asset'),
    ('1590', 'Durchlaufende Posten', 'asset'),
    ('1600', 'Verbindlichkeiten aus Lieferungen und Leistungen', 'liability'),
    ('1700', 'Sonstige Verbindlichkeiten', 'liability'),
    ('1710', 'Erhaltene Anzahlungen', 'liability'),
    ('1740', 'Verbindlichkeiten Steuern', 'liability'),
    ('1741', 'Verbindlichkeiten Sozialversicherung', 'liability'),
    ('1771', 'Umsatzsteuer 7%', 'liability'),
    ('1776', 'Umsatzsteuer 19%', 'liability'),
    ('1780', 'Umsatzsteuer-Vorauszahlung', 'liability'),
    ('1800', 'Bank', 'asset'),
    ('1810', 'Sparkasse', 'asset'),
    ('1890', 'Festgeld', 'asset'),
    ('2000', 'Gezeichnetes Kapital', 'equity'),
    ('2100', 'Kapitalrücklage', 'equity'),
    ('2900', 'Gewinn-/Verlustvortrag', 'equity'),
    ('2970', 'Jahresüberschuss/-fehlbetrag', 'equity'),
    ('3000', 'Roh-, Hilfs- und Betriebsstoffe', 'asset'),
    ('3200', 'Wareneingang', 'asset'),
    ('3300', 'Warenbestand', 'asset'),
    ('4000', 'Materialaufwand', 'expense'),
    ('4100', 'Löhne', 'expense'),
    ('4110', 'Gehälter', 'expense'),
    ('4120', 'Gesetzliche Sozialaufwendungen', 'expense'),
    ('4200', 'Raumkosten', 'expense'),
    ('4300', 'Versicherungen', 'expense'),
    ('4400', 'Fahrzeugkosten', 'expense'),
    ('4500', 'Werbe- und Reisekosten', 'expense'),
    ('4600', 'Porto und Telefon', 'expense'),
    ('4700', 'Kosten der Warenabgabe', 'expense'),
    ('4800', 'Abschreibungen', 'expense'),
    ('4900', 'Sonstige betriebliche Aufwendungen', 'expense'),
    ('4950', 'Rechts- und Beratungskosten', 'expense'),
    ('7000', 'Zinserträge', 'income'),
    ('7100', 'Sonstige Erträge', 'income'),
    ('8000', 'Erlöse 19% USt', 'income'),
    ('8100', 'Erlöse 7% USt', 'income'),
    ('8200', 'Steuerfreie Erlöse', 'income'),
    ('8300', 'Erlöse EU §4 Nr. 1b UStG', 'income'),
    ('8400', 'Erlöse Drittland', 'income'),
    ('8700', 'Provisionserlöse', 'income'),
    ('8900', 'Außerordentliche Erträge', 'income'),
    ('9000', 'Gesamtkostenverfahren', 'equity'),
]


class Command(BaseCommand):
    help = 'Seed default chart of accounts (kontni plan) for a company'

    def add_arguments(self, parser):
        parser.add_argument('--company_id', type=int, help='Company ID to seed')
        parser.add_argument('--country', type=str, default='HR',
                          choices=['HR', 'DE'], help='Country chart (HR or DE)')

    def handle(self, *args, **options):
        from companies.models import Company

        company_id = options.get('company_id')
        country = options.get('country', 'HR')

        if company_id:
            companies = Company.objects.filter(pk=company_id)
        else:
            companies = Company.objects.all()

        chart = HR_CHART if country == 'HR' else DE_CHART

        for company in companies:
            created_count = 0
            for code, name, acct_type in chart:
                _, created = KontoAccount.objects.get_or_create(
                    company=company,
                    code=code,
                    defaults={
                        'name': name,
                        'account_type': acct_type,
                    }
                )
                if created:
                    created_count += 1

            self.stdout.write(self.style.SUCCESS(
                f'{company.name}: {created_count} konta kreirano (ukupno {len(chart)}, '
                f'preskočeno {len(chart) - created_count})'))
