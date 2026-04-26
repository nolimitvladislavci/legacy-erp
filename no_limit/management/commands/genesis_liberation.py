"""
manage.py genesis_liberation
Biljezi trenutak kad su oba svjedoka potvrdila i tvorac se odrekao posebnih prava u Krunici.
Zapecat Genesis Liberation Event u ChainBlock registru.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Genesis Liberation Event — Krunica slobodna od tvorca'

    def handle(self, *args, **options):
        from no_limit.models import WitnessConfirmation

        witnesses = WitnessConfirmation.objects.filter(
            document_seal_token='NOLIMIT-GENESIS-0001',
            status='confirmed'
        )

        if witnesses.count() < 2:
            self.stdout.write(self.style.ERROR(
                f'Samo {witnesses.count()}/2 svjedoka potvrdilo. Cekaj potvrdu obaju.'
            ))
            return

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ZIVA ISTINA POTPUNA'))
        self.stdout.write(self.style.SUCCESS('Krunica je slobodna od tvorca.'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        for w in witnesses:
            self.stdout.write(f'  v {w.witness_name} ({w.witness_country}) — {w.confirmed_at}')

        # Pokusaj zapecatiti u ChainBlock (fenix-v3)
        try:
            import sys
            import os
            sys.path.insert(0, '/var/www/fenix-v3')
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

            import django
            django.setup()
            from evalidator.models import ChainBlockPOE

            liberation = ChainBlockPOE.objects.create(
                event_type='genesis_liberation',
                seal_token='NOLIMIT-LIBERATION-0001',
                author='Ivan Brtan',
                title='Genesis Liberation — Krunica slobodna od tvorca',
                description=(
                    'Trenutak kad su oba svjedoka potvrdila autenticnost Genesis Block #0 '
                    'i tvorac se odrekao posebnih prava u Krunica konsenzusnom sustavu. '
                    'Ekosustav postaje zivi, autonomni organizam. '
                    'Svjedoci: ' + ', '.join(w.witness_name for w in witnesses)
                ),
                ip_holder='Konjik d.o.o.',
                technologies=['NO LIMIT', 'ChainBlock', 'Krunica', 'Shamir', '.dok'],
            )
            self.stdout.write(self.style.SUCCESS(
                f'\nChainBlock Liberation Block: #{liberation.block_number}'
            ))
            self.stdout.write(f'Seal: {liberation.seal_token}')
            self.stdout.write(f'Hash: {liberation.sha256_hash}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'ChainBlock nedostupan (nije kriticno): {e}'))

        self.stdout.write(self.style.SUCCESS(
            '\n— Big Tech misli na sljedeci kvartal. NO LIMIT misli na sljedece stoljece. —'
        ))
        self.stdout.write('Ivan Brtan · 2026-04-25 · Vladislavci, Hrvatska')
