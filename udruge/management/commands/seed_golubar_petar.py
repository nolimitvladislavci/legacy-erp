"""
Seed skripta — Golubar Petar Brtan (pilot korisnik)
Popunjava realističan set podataka za demo/testiranje:
  - 1 golubinjak (Čepin, HR-31-2024-0047)
  - 20 golubova s rodovnikom (4 generacije na 5 "zvijezda")
  - 3 utrke (Osijek Sprint, Slavonija Classic, Drava Cup)
  - Rezultati utrka + plasman statistika
  - 2 zdravstvena kartona (PMV, tretman grinje)
  - Genetski pečati na top 3 goluba (aukcija 2025)

Pokretanje:
  venv/bin/python manage.py seed_golubar_petar
  venv/bin/python manage.py seed_golubar_petar --wipe  # briše i ponovo sije
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed demo podataka za Petra Brtana — golubar pilot.'

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true',
                            help='Obriši postojeće golubove i utrke pa ponovo unesi')

    def handle(self, *args, **options):
        from companies.models import Company
        from udruge.models import (
            Golub,
            Golubinjak,
            RezultatUtrke,
            Utrka,
            ZdravstveniZapisGolub,
        )

        try:
            company = Company.objects.get(name__icontains='Petar Brtan')
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                'Firma "Petar Brtan — Golubar" ne postoji. '
                'Registriraj korisnika na /register/ s tim imenom.'))
            return

        self.stdout.write(f'Company: {company.name} [{company.pk}]')

        if options['wipe']:
            RezultatUtrke.objects.filter(golub__company=company).delete()
            Utrka.objects.filter(company=company).delete()
            ZdravstveniZapisGolub.objects.filter(golub__company=company).delete()
            Golub.objects.filter(company=company).delete()
            Golubinjak.objects.filter(company=company).delete()
            self.stdout.write(self.style.WARNING('  Stari podaci obrisani.'))

        with transaction.atomic():
            # ── 1. GOLUBINJAK ─────────────────────────────────────────────
            golubinjak, _ = Golubinjak.objects.get_or_create(
                company=company,
                naziv='Golubinjak Brtan — Čepin',
                defaults={
                    'adresa':      'Antuna Mihanovića 12, 31431 Čepin',
                    'gps_lat':     Decimal('45.5320'),
                    'gps_lng':     Decimal('18.5640'),
                    'eu_reg_broj': 'HR-31-2024-0047',
                    'kapacitet':   60,
                    'aktivan':     True,
                    'napomena':    'Pilot korisnik — brat Ivana Brtana.',
                }
            )
            self.stdout.write(f'  ✓ Golubinjak: {golubinjak}')

            # ── 2. PEDIGREE GOLUBOVI ──────────────────────────────────────
            # Definicija: [prsten, naziv, spol, boja, godina, otac_prsten, majka_prsten]
            GOLUBOVI = [
                # GENERACIJA 3 (pradjedovi — bez roditelja)
                ('HR-2019-00001', 'Grom',         'M', 'plav',        2019, None, None),
                ('HR-2019-00002', 'Latica',        'F', 'bijel',       2019, None, None),
                ('HR-2019-00003', 'Tornado',       'M', 'crn',         2019, None, None),
                ('HR-2019-00004', 'Ruža',          'F', 'crvena_siva', 2019, None, None),

                # GENERACIJA 2 (djedovi)
                ('HR-2021-00010', 'Munja',         'M', 'plav',        2021, 'HR-2019-00001', 'HR-2019-00002'),
                ('HR-2021-00011', 'Bura',          'F', 'bijel',       2021, 'HR-2019-00003', 'HR-2019-00004'),
                ('HR-2021-00012', 'Strijelac',     'M', 'crn',         2021, 'HR-2019-00001', 'HR-2019-00004'),
                ('HR-2021-00013', 'Zvijezda',      'F', 'karirani',    2021, 'HR-2019-00003', 'HR-2019-00002'),

                # GENERACIJA 1 (roditelji top grla)
                ('HR-2023-00100', 'Eros',          'M', 'plav',        2023, 'HR-2021-00010', 'HR-2021-00011'),
                ('HR-2023-00101', 'Afrodita',      'F', 'bijel',       2023, 'HR-2021-00012', 'HR-2021-00013'),
                ('HR-2023-00102', 'Hercules',      'M', 'crn',         2023, 'HR-2021-00010', 'HR-2021-00013'),
                ('HR-2023-00103', 'Helena',        'F', 'crvena_siva', 2023, 'HR-2021-00012', 'HR-2021-00011'),

                # GENERACIJA 0 — Petrova "zvijezda" jata (natjecatelji 2025/26)
                ('HR-2025-00200', 'Perun',         'M', 'plav',        2025, 'HR-2023-00100', 'HR-2023-00101'),
                ('HR-2025-00201', 'Vela',          'F', 'bijel',       2025, 'HR-2023-00102', 'HR-2023-00103'),
                ('HR-2025-00202', 'Oluja',         'M', 'karirani',    2025, 'HR-2023-00100', 'HR-2023-00103'),
                ('HR-2025-00203', 'Drina',         'F', 'crn',         2025, 'HR-2023-00102', 'HR-2023-00101'),
                ('HR-2025-00204', 'Titan',         'M', 'plav',        2025, 'HR-2023-00100', 'HR-2023-00101'),
                ('HR-2025-00205', 'Vesna',         'F', 'crvena_siva', 2025, 'HR-2023-00102', 'HR-2023-00103'),
                ('HR-2025-00206', 'Bojan',         'M', 'crn',         2025, 'HR-2023-00100', 'HR-2023-00101'),
                ('HR-2025-00207', 'Zora',          'F', 'bijel',       2025, 'HR-2023-00102', 'HR-2023-00103'),
            ]

            golub_map = {}  # prsten → Golub objekt

            # Prolaz 1 — kreiraj sve golubove bez roditelja
            for prsten, naziv, spol, boja, god, _, _ in GOLUBOVI:
                g, created = Golub.objects.get_or_create(
                    prsten_broj=prsten,
                    defaults={
                        'company':          company,
                        'golubinjak':       golubinjak,
                        'naziv':            naziv,
                        'spol':             spol,
                        'boja':             boja,
                        'datum_izlijeganja': date(god, 3, 15),
                        'aktivan':          True,
                    }
                )
                if created:
                    g.company = company
                    g.golubinjak = golubinjak
                    g.save()
                golub_map[prsten] = g

            # Prolaz 2 — poveži roditelje
            for prsten, _, _, _, _, otac_pr, majka_pr in GOLUBOVI:
                g = golub_map[prsten]
                changed = False
                if otac_pr and not g.otac:
                    g.otac = golub_map[otac_pr]
                    changed = True
                if majka_pr and not g.majka:
                    g.majka = golub_map[majka_pr]
                    changed = True
                if changed:
                    g.save(update_fields=['otac', 'majka'])

            self.stdout.write(f'  ✓ Golubovi: {len(golub_map)} uneseno')

            # ── 3. GENETSKI PEČATI — top 3 aukcija 2025 ──────────────────
            for prsten in ['HR-2025-00200', 'HR-2025-00202', 'HR-2025-00204']:
                g = golub_map[prsten]
                if not g.is_sealed:
                    g.zapecati(razlog='aukcija_2025')
                    self.stdout.write(f'  🔒 Zapečaćen: {g.naziv} ({prsten}) → {g.genetics_hash[:16]}...')

            # ── 4. UTRKE ──────────────────────────────────────────────────
            UTRKE = [
                {
                    'naziv': 'Osijek Sprint 2025',
                    'datum': date(2025, 4, 20),
                    'startna_tocka': 'Bjelovar',
                    'startna_lat': Decimal('45.8990'),
                    'startna_lng': Decimal('16.8420'),
                    'udaljenost_km': Decimal('98.5'),
                    'organizator': 'KDO Osijek',
                    'broj_natjecatelja': 47,
                    'uvjeti': 'SZ vjetar 15 km/h, vedro',
                    'rezultati': [
                        ('HR-2025-00200', 1,  1, Decimal('1285.50')),   # Perun — 1. place ukupno
                        ('HR-2025-00202', 3,  3, Decimal('1271.20')),   # Oluja — 3.
                        ('HR-2025-00204', 7,  7, Decimal('1248.90')),   # Titan — 7.
                        ('HR-2025-00201', 12, 12, Decimal('1198.30')),
                        ('HR-2025-00203', 18, 18, Decimal('1156.70')),
                    ],
                },
                {
                    'naziv': 'Slavonija Classic 2025',
                    'datum': date(2025, 5, 11),
                    'startna_tocka': 'Virovitica',
                    'startna_lat': Decimal('45.8319'),
                    'startna_lng': Decimal('17.3842'),
                    'udaljenost_km': Decimal('67.2'),
                    'organizator': 'Kinološki klub Slavonija',
                    'broj_natjecatelja': 63,
                    'uvjeti': 'Bez vjetra, magla ujutro',
                    'rezultati': [
                        ('HR-2025-00202', 2,  2, Decimal('1310.40')),   # Oluja — 2.
                        ('HR-2025-00200', 5,  5, Decimal('1289.10')),   # Perun — 5.
                        ('HR-2025-00206', 9,  9, Decimal('1241.60')),
                        ('HR-2025-00204', 14, 14, Decimal('1198.80')),
                    ],
                },
                {
                    'naziv': 'Drava Cup 2025',
                    'datum': date(2025, 6, 8),
                    'startna_tocka': 'Koprivnica',
                    'startna_lat': Decimal('46.1620'),
                    'startna_lng': Decimal('16.8270'),
                    'udaljenost_km': Decimal('124.3'),
                    'organizator': 'Golubar klub Drava',
                    'broj_natjecatelja': 89,
                    'uvjeti': 'JZ vjetar 25 km/h, oblačno',
                    'rezultati': [
                        ('HR-2025-00200', 1,  1, Decimal('1190.20')),   # Perun — pobjednik Drava Cupa
                        ('HR-2025-00204', 4,  4, Decimal('1164.50')),
                        ('HR-2025-00202', 6,  6, Decimal('1148.30')),
                        ('HR-2025-00207', 15, 15, Decimal('1089.70')),
                        ('HR-2025-00201', 22, 22, Decimal('1034.20')),
                    ],
                },
            ]

            for u_data in UTRKE:
                rezultati_data = u_data.pop('rezultati')
                utrka, _ = Utrka.objects.get_or_create(
                    company=company,
                    naziv=u_data['naziv'],
                    datum=u_data['datum'],
                    defaults=u_data,
                )
                for prsten, plac, plac_uk, brzina in rezultati_data:
                    g = golub_map.get(prsten)
                    if g:
                        RezultatUtrke.objects.get_or_create(
                            utrka=utrka,
                            golub=g,
                            defaults={
                                'placiranje':        plac,
                                'placiranje_ukupno': plac_uk,
                                'brzina_mpm':        brzina,
                            }
                        )
                self.stdout.write(f'  ✓ Utrka: {utrka.naziv} ({utrka.broj_natjecatelja} nat.)')

            # ── 5. ZDRAVSTVENI KARTONI ────────────────────────────────────
            ZDRAVLJE = [
                {
                    'golub':        'HR-2025-00200',
                    'datum':        date(2025, 3, 1),
                    'tip':          'PMV',
                    'lijek':        'Colombovac PMV (inaktiv. vakcina)',
                    'doza_ml':      Decimal('0.2'),
                    'veterinar':    'Dr. Tomić, Veterinarska stanica Osijek',
                    'sljedeci':     date(2026, 3, 1),
                    'napomena':     'Godišnja vakcinacija, zakonska obveza',
                },
                {
                    'golub':        'HR-2025-00202',
                    'datum':        date(2025, 3, 1),
                    'tip':          'PMV',
                    'lijek':        'Colombovac PMV (inaktiv. vakcina)',
                    'doza_ml':      Decimal('0.2'),
                    'veterinar':    'Dr. Tomić, Veterinarska stanica Osijek',
                    'sljedeci':     date(2026, 3, 1),
                    'napomena':     'Godišnja vakcinacija, zakonska obveza',
                },
                {
                    'golub':        'HR-2025-00200',
                    'datum':        date(2025, 9, 15),
                    'tip':          'antiparazit',
                    'lijek':        'Ivermektin 1% otopina — grinje (Dermanyssus gallinae)',
                    'doza_ml':      Decimal('0.05'),
                    'veterinar':    'Dr. Tomić, Veterinarska stanica Osijek',
                    'sljedeci':     date(2025, 10, 15),
                    'napomena':     'Preventivni tretman jesen',
                },
            ]

            for z_data in ZDRAVLJE:
                golub = golub_map[z_data.pop('golub')]
                ZdravstveniZapisGolub.objects.get_or_create(
                    golub=golub,
                    datum=z_data['datum'],
                    vrsta=z_data['tip'],
                    defaults={
                        'lijek_preparat':  z_data['lijek'],
                        'doza':            str(z_data['doza_ml']) + ' ml',
                        'veterinar':       z_data['veterinar'],
                        'sljedeci_tretman': z_data['sljedeci'],
                        'napomena':        z_data['napomena'],
                    }
                )
            self.stdout.write(f'  ✓ Zdravstveni zapisi: {len(ZDRAVLJE)} unosa')

        # ── SUMMARY ───────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 55))
        self.stdout.write(self.style.SUCCESS('  Golubar Petar Brtan — seed završen'))
        self.stdout.write(self.style.SUCCESS('═' * 55))
        self.stdout.write(f'  Golubinjak:  {Golubinjak.objects.filter(company=company).count()}')
        self.stdout.write(f'  Golubovi:    {Golub.objects.filter(company=company).count()}')
        self.stdout.write(f'  Utrke:       {Utrka.objects.filter(company=company).count()}')
        self.stdout.write(f'  Rezultati:   {RezultatUtrke.objects.filter(golub__company=company).count()}')
        self.stdout.write(f'  Zdravlje:    {ZdravstveniZapisGolub.objects.filter(golub__company=company).count()}')
        self.stdout.write(f'  Zapečaćeni:  {Golub.objects.filter(company=company, is_sealed=True).count()}')
        self.stdout.write('')
        self.stdout.write('  URL: /udruge/golubar/')
        self.stdout.write('  Perun (HR-2025-00200): 2× pobjednik, zapečaćen')
