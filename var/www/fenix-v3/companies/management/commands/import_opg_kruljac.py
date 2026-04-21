from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Import OPG Kruljac Sladana iz fina-connect u Fenix V3'

    def handle(self, *args, **kwargs):
        from companies.models import Company
        from accounts.models import CompanyMembership

        with transaction.atomic():
            # 1. Korisnik
            user, created = User.objects.get_or_create(
                username='opg_kruljac_sladana',
                defaults={
                    'email': 'opg.kruljac@limit-connect.com',
                    'first_name': 'Slađana',
                    'last_name': 'Kruljac',
                    'is_active': True,
                }
            )
            if created:
                user.set_password('Kruljac2026!')
                user.save()
                self.stdout.write(self.style.SUCCESS(f'  Korisnik kreiran: {user.username}'))
            else:
                self.stdout.write(f'  Korisnik već postoji: {user.username}')

            # 2. Kompanija
            company, c_created = Company.objects.get_or_create(
                oib='41439993573',
                defaults={
                    'name': 'OPG Kruljac Slađana',
                    'short_name': 'OPG Kruljac',
                    'entity_type': 'opg',
                    'oib': '41439993573',
                    'nkd_code': '01.41',
                    'nkd_description': 'Uzgoj mliječnih goveda',
                    'activity_description': (
                        'OPG specijaliziran za uzgoj mliječnih goveda s robotiziranom farmom '
                        '(Lely A5 robot za mužnju). Kapacitet: 50 muznih krava (proširenje na 200 planira se). '
                        'Djelatnosti: primarna proizvodnja mlijeka, uzgoj i prodaja teladi, '
                        'prerada mlijeka (sirana), prerada mesa (mini klaonica), '
                        'biogas postrojenje 300 kW, solarni paneli 100 kW, '
                        'embriotransfer laboratorij, edukacijsko-prezentacijski centar, '
                        'agroturizam s noćenjem i učionicama.'
                    ),
                    'address': 'Kralja Tomislava 275',
                    'city': 'Vladislavci',
                    'postal_code': '31404',
                    'county': 'Osječko-baranjska',
                    'country': 'HR',
                    'iban': 'HR4224020061140216521',
                    'bank_name': 'Erste banka',
                    'vat_status': 'not_registered',
                    'website': 'https://limit-connect.com/opg/kruljac-sladana/',
                    'language': 'hr',
                    'currency': 'EUR',
                    'ai_enabled': True,
                    'notes': (
                        'lely_robot_api_key: LELY-KRULJAC-A5-2024-DEMO\n'
                        'lely_farm_id: HR-VLD-050\n'
                        'import_source: fina-connect (ID: f333a08a)\n'
                        'eu_project: DA-RURALIS-2026 (u pripremi)\n'
                        'hbor_1726: kredit za modernizaciju u pripremi\n'
                        'biogas_capacity_kw: 300\n'
                        'solar_capacity_kw: 100\n'
                        'current_cows: 50\n'
                        'target_cows: 200\n'
                    ),
                    'is_active': True,
                }
            )
            if c_created:
                self.stdout.write(self.style.SUCCESS(f'  Kompanija kreirana: {company.name}'))
            else:
                self.stdout.write(f'  Kompanija već postoji: {company.name}')

            # 3. Membership
            membership, m_created = CompanyMembership.objects.get_or_create(
                user=user,
                company=company,
                defaults={
                    'role': CompanyMembership.Role.OWNER,
                    'is_default': True,
                }
            )
            if m_created:
                self.stdout.write(self.style.SUCCESS(f'  Membership kreiran: owner'))
            else:
                self.stdout.write(f'  Membership već postoji')

        self.stdout.write(self.style.SUCCESS('\nOPG Kruljac Sladana uspjesno importiran!'))
        self.stdout.write(f'  Login: opg_kruljac_sladana / Kruljac2026!')
        self.stdout.write(f'  URL:   https://limit-connect.com/opg/kruljac-sladana/')
        self.stdout.write(f'  OIB:   41439993573')
