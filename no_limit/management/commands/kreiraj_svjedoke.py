"""
manage.py kreiraj_svjedoke
Kreira WitnessConfirmation zapise za Genesis Block svjedoke i ispisuje WhatsApp linkove.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Kreira svjedoke za NO LIMIT Genesis Block i ispisuje WhatsApp linkove'

    def handle(self, *args, **options):
        from no_limit.models import WitnessConfirmation

        witnesses_data = [
            {
                'witness_name': 'Niksa Viskovic',
                'witness_phone': '',
                'witness_organization': 'Viskovic Bau Gewerbe',
                'witness_country': 'Njemacka',
                'witness_role': 'partner',
                'document_title': 'Genesis Block #0 — NO LIMIT udruga, osnivacki akt i Triple DNA patent',
                'document_description': (
                    'Svjedocite autenticnosti Genesis Block #0 NO LIMIT udruge iz Vladislavaca, '
                    'Hrvatske. Dokument je zapecacen 19.04.2026. i biljezi osnivanje udruge, '
                    'izumitelja Ivana Brtana i nositelja IP prava Konjik d.o.o. '
                    'Vase svjedocenje se pohranjuje kriptografski i postaje dio javnog registra.'
                ),
                'document_seal_token': 'NOLIMIT-GENESIS-0001',
                'document_sha256': '6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658',
                'document_url': 'https://no-limit.world/static/udruga_no_limit/NO_LIMIT_Genesis_Block_0.pdf',
                'created_by': 'Ivan Brtan',
                'expires_at': timezone.now() + datetime.timedelta(days=30),
            },
            {
                'witness_name': 'Ive Kovacevic',
                'witness_phone': '',
                'witness_organization': '',
                'witness_country': 'Hrvatska',
                'witness_role': 'external',
                'document_title': 'Genesis Block #0 — NO LIMIT udruga, osnivacki akt i Triple DNA patent',
                'document_description': (
                    'Svjedocite autenticnosti Genesis Block #0 NO LIMIT udruge iz Vladislavaca, '
                    'Hrvatske. Dokument je zapecacen 19.04.2026. i biljezi osnivanje udruge, '
                    'izumitelja Ivana Brtana i nositelja IP prava Konjik d.o.o. '
                    'Vase svjedocenje se pohranjuje kriptografski i postaje dio javnog registra.'
                ),
                'document_seal_token': 'NOLIMIT-GENESIS-0001',
                'document_sha256': '6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658',
                'document_url': 'https://no-limit.world/static/udruga_no_limit/NO_LIMIT_Genesis_Block_0.pdf',
                'created_by': 'Ivan Brtan',
                'expires_at': timezone.now() + datetime.timedelta(days=30),
            },
        ]

        for data in witnesses_data:
            obj, created = WitnessConfirmation.objects.get_or_create(
                witness_name=data['witness_name'],
                document_seal_token=data['document_seal_token'],
                defaults=data,
            )
            action = 'Kreiran' if created else 'Vec postoji'
            url = f"https://fina-connect.online/no-limit/svjedok/{obj.token}/"
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"{action}: {obj.witness_name}")
            self.stdout.write(f"Organizacija: {obj.witness_organization or 'Privatna osoba'}")
            self.stdout.write(f"Drzava: {obj.witness_country}")
            self.stdout.write(f"Status: {obj.status}")
            self.stdout.write(self.style.SUCCESS(f"LINK ZA SLANJE: {url}"))
            self.stdout.write(f"\nWhatsApp poruka:")
            self.stdout.write(f"---")
            self.stdout.write(f"Postovani {obj.witness_name.split()[0]},")
            self.stdout.write(f"")
            self.stdout.write(f"Molim Vas da budete vanjski svjedok autenticnosti Genesis Block #0")
            self.stdout.write(f"NO LIMIT udruge iz Vladislavaca.")
            self.stdout.write(f"")
            self.stdout.write(f"Kliknite na link ispod, procitajte kratki opis i potvrdite svjedocenje:")
            self.stdout.write(url)
            self.stdout.write(f"")
            self.stdout.write(f"Link vrijedi 30 dana. Hvala!")
            self.stdout.write(f"Ivan Brtan")
            self.stdout.write(f"---")
