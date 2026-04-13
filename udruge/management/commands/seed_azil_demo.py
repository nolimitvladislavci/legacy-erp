"""
Seed skripta — Azil demo podaci + Ljubeta iz Novaka (uzgajivačnica rasnih pasa)
Kreira:
  A) Demo azil firma + 15 životinja u različitim statusima
  B) Uzgajivačnica Ljubeta Novak (ako ne postoji, kreira Company)
     + 8 rasnih pasa s rodovnikom i zdravstvenim kartonima

Pokretanje:
  venv/bin/python manage.py seed_azil_demo
  venv/bin/python manage.py seed_azil_demo --wipe
  venv/bin/python manage.py seed_azil_demo --samo-azil
  venv/bin/python manage.py seed_azil_demo --samo-ljubeta
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Seed azil demo + uzgajivačnica Ljubeta Novak.'

    def add_arguments(self, parser):
        parser.add_argument('--wipe',        action='store_true')
        parser.add_argument('--samo-azil',   action='store_true')
        parser.add_argument('--samo-ljubeta', action='store_true')

    def handle(self, *args, **options):
        samo_azil   = options['samo_azil']
        samo_ljubeta = options['samo_ljubeta']
        wipe         = options['wipe']

        if not samo_ljubeta:
            self._seed_azil(wipe)
        if not samo_azil:
            self._seed_ljubeta(wipe)

    # ═══════════════════════════════════════════════════════════════
    # A) AZIL
    # ═══════════════════════════════════════════════════════════════
    def _seed_azil(self, wipe):
        from companies.models import Company
        from udruge.models import (
            Zivotinja, KartonZdravlja, Udomljavanje, AzilIntervencija
        )

        # Pronađi ili kreiraj demo azil firmu
        azil_co, created = Company.objects.get_or_create(
            name='Demo Azil — Udruga za zaštitu životinja Osijek',
            defaults={
                'oib': '99988877701',
                'country': 'HR',
            }
        )
        if created:
            self.stdout.write(self.style.WARNING(
                f'  Nova firma kreirana: {azil_co.name}'))
        else:
            self.stdout.write(f'  Azil firma: {azil_co.name}')

        if wipe:
            Udomljavanje.objects.filter(zivotinja__company=azil_co).delete()
            KartonZdravlja.objects.filter(zivotinja__company=azil_co).delete()
            AzilIntervencija.objects.filter(company=azil_co).delete()
            Zivotinja.objects.filter(company=azil_co).delete()
            self.stdout.write(self.style.WARNING('  Stari azil podaci obrisani.'))

        today = date.today()

        with transaction.atomic():
            # ── Životinje ────────────────────────────────────────────
            # Format: [ime, vrsta, pasmina, spol, dob_proc, boja, nacin, status, dane_u_azilu, mikrocip]
            ZIVOTINJE = [
                # Karantena (svježi dolasci)
                ('Roki',    'pas',   'Mješanac',       'M', 'oko 2 god', 'Žuto-bijeli',  'pronadjen',  'karantena',  3,  ''),
                ('Siva',    'macka', 'Europska kratkodlaka','Z','oko 1 god', 'Siva tigrica', 'pronadjen',  'karantena',  7,  ''),
                ('Bubi',    'pas',   'Mješanac',       'M', 'štene ~3mj','Crno-bijeli',  'ostavljen',  'karantena',  1,  ''),
                ('Luna',    'macka', 'Europska kratkodlaka','Z','oko 3 god', 'Crna',         'priveden',   'karantena',  12, ''),
                # Slobodni za udomljenje
                ('Maks',    'pas',   'Labrador mix',   'M', 'oko 4 god', 'Zlatni',       'pronadjen',  'slobodan',   45, '191100001234567'),
                ('Bella',   'pas',   'Border Collie mix','Z','oko 3 god','Crno-bijeli',  'ostavljen',  'slobodan',   60, '191100002345678'),
                ('Piko',    'pas',   'Mješanac mali',  'M', 'oko 6 god', 'Smeđi',        'pronadjen',  'slobodan',   120,''),
                ('Nina',    'macka', 'Perzijska mix',  'Z', 'oko 5 god', 'Bijela',       'premjesten', 'slobodan',   90, '191100003456789'),
                ('Aron',    'pas',   'Njemački ovčar', 'M', 'oko 2 god', 'Crno-smeđi',  'priveden',   'slobodan',   30, '191100004567890'),
                # Rezervirani
                ('Zara',    'pas',   'Mješanac',       'Z', 'oko 1 god', 'Riđa',         'pronadjen',  'rezerviran', 25, '191100005678901'),
                # Udomljeni (historijski zapisi)
                ('Tobi',    'pas',   'Golden Retriever','M','oko 3 god', 'Zlatni',       'ostavljen',  'udomljen',   180,'191100006789012'),
                ('Mia',     'macka', 'Sijamska mix',   'Z', 'oko 2 god', 'Kremasto-smeđa','pronadjen', 'udomljen',   95, ''),
                # Vraćen vlasniku
                ('Rex',     'pas',   'Rottweiler',     'M', 'oko 5 god', 'Crno-smeđi',  'pronadjen',  'vrácen',     8,  '191100007890123'),
                # Uginuo (prirodna smrt)
                ('Stari',   'pas',   'Mješanac',       'M', 'oko 14 god','Bijelo-sivi',  'ostavljen',  'uginuo',     220,''),
                # Dugo čeka (test za 48h alarm)
                ('Dugo',    'pas',   'Mješanac',       'M', 'oko 7 god', 'Tamno smeđi',  'pronadjen',  'slobodan',   730,''),
            ]

            created_count = 0
            zivotinja_map = {}

            for ime, vrsta, pasmina, spol, dob, boja, nacin, status, dani, mikrocip in ZIVOTINJE:
                datum_ulaska = today - timedelta(days=dani)
                ev_br_exists = Zivotinja.objects.filter(
                    company=azil_co, ime=ime
                ).exists()
                if ev_br_exists:
                    zivotinja = Zivotinja.objects.filter(company=azil_co, ime=ime).first()
                    zivotinja_map[ime] = zivotinja
                    continue

                zivotinja = Zivotinja(
                    company=azil_co,
                    ime=ime,
                    vrsta=vrsta,
                    naziv_pasmina=pasmina,
                    spol=spol,
                    dob_procjena=dob,
                    boja_opis=boja,
                    nacin_primitka=nacin,
                    status=status,
                    datum_ulaska=datum_ulaska,
                    mikrocip=mikrocip,
                    javno_oglaseno=(status == 'slobodan'),
                    napomena_ulaz=f'Demo unos — seed_azil_demo ({datum_ulaska})',
                )
                zivotinja.save()
                zivotinja_map[ime] = zivotinja
                created_count += 1

            self.stdout.write(f'  ✓ Životinje: {created_count} novih (ukupno {len(ZIVOTINJE)})')

            # ── Zdravstveni kartoni ───────────────────────────────────
            ZDRAVLJE = [
                ('Maks',  date(today.year, 2, 10), 'cijepljenje',  'Kombinovano cjepivo (Canigen DHPPi/L)','Dr. Kovač, Vet. stanica Osijek', date(today.year + 1, 2, 10), ''),
                ('Maks',  date(today.year, 2, 10), 'cipiranje',    'Mikročipiranje ISO 11784, LOT: 2024/031','Dr. Kovač, Vet. stanica Osijek', None, 'Chip: 191100001234567'),
                ('Maks',  date(today.year, 2, 15), 'kastracija',   'Kastracija — zakonska obveza skloništa','Dr. Kovač, Vet. stanica Osijek', None, ''),
                ('Bella', date(today.year, 1, 5),  'cijepljenje',  'Kombinovano cjepivo (Canigen DHPPi/L)','Dr. Kovač, Vet. stanica Osijek', date(today.year + 1, 1, 5), ''),
                ('Bella', date(today.year, 1, 5),  'antiparazit',  'Frontline Combo (krpelji, buhe)','Dr. Kovač, Vet. stanica Osijek', date(today.year, 4, 5), ''),
                ('Aron',  date(today.year, 3, 1),  'pregled',      'Ulazni pregled — ozljeda šape (zarasla)','Dr. Kovač, Vet. stanica Osijek', None, 'Prijedlog: fisioterapija'),
                ('Piko',  date(today.year - 1, 8, 1),'cijepljenje','Kombinovano cjepivo', 'Dr. Kovač', date(today.year, 8, 1), ''),
                ('Dugo',  date(today.year - 1, 6, 1),'cipiranje',  'Mikročipiranje', 'Dr. Novak, Vet. amb. Đakovo', None, ''),
                ('Dugo',  date(today.year - 1, 6, 1),'kastracija', 'Kastracija', 'Dr. Novak, Vet. amb. Đakovo', None, ''),
            ]

            zdravlje_count = 0
            for ime, datum, tip, opis, vet, sljedeci, napomena in ZDRAVLJE:
                z = zivotinja_map.get(ime)
                if not z:
                    continue
                _, cr = KartonZdravlja.objects.get_or_create(
                    zivotinja=z,
                    datum=datum,
                    vrsta_tretmana=tip,
                    defaults={
                        'opis': opis + (' | ' + napomena if napomena else ''),
                        'veterinar': vet,
                        'sljedeci_pregled': sljedeci,
                    }
                )
                if cr:
                    zdravlje_count += 1
            self.stdout.write(f'  ✓ Zdravstveni kartoni: {zdravlje_count} novih')

            # ── Udomljavanja ──────────────────────────────────────────
            for ime, oib, adresa, tel in [
                ('Tobi', '12345678901', 'Ul. kralja Tomislava 5, Osijek',  '091-234-5678'),
                ('Mia',  '98765432109', 'Europska avenija 22, Osijek',      '098-765-4321'),
                ('Rex',  '11223344556', 'Vinkovačka 8, Đakovo',            '095-111-2233'),
            ]:
                z = zivotinja_map.get(ime)
                if not z:
                    continue
                tip = 'povrat' if z.status == 'vrácen' else 'trajno'
                Udomljavanje.objects.get_or_create(
                    zivotinja=z,
                    defaults={
                        'datum': today - timedelta(days=10),
                        'ime_prezime': 'Demo Udomitelj',
                        'oib': oib,
                        'adresa': adresa,
                        'telefon': tel,
                        'tip': tip,
                        'ugovor_potpisan': True,
                    }
                )
            self.stdout.write('  ✓ Udomljavanja i povrati: 3 unosa')

        self.stdout.write(self.style.SUCCESS(
            '\n  Azil demo završen → /udruge/azil/'))

    # ═══════════════════════════════════════════════════════════════
    # B) LJUBETA NOVAK — uzgajivačnica rasnih pasa
    # ═══════════════════════════════════════════════════════════════
    def _seed_ljubeta(self, wipe):
        from companies.models import Company
        from udruge.models import Zivotinja, KartonZdravlja

        # Uzgajivačnica — registriramo kao Company, udruge_type=uzgajivacnica
        ljubeta_co, created = Company.objects.get_or_create(
            name='Ljubeta Novak — Uzgajivačnica rasnih pasa Novak',
            defaults={
                'oib':     '55544433321',
                'country': 'HR',
            }
        )
        if created:
            self.stdout.write(self.style.WARNING(
                f'  Nova firma kreirana: {ljubeta_co.name}'))
        else:
            self.stdout.write(f'  Ljubeta firma: {ljubeta_co.name}')

        if wipe:
            KartonZdravlja.objects.filter(zivotinja__company=ljubeta_co).delete()
            Zivotinja.objects.filter(company=ljubeta_co).delete()
            self.stdout.write(self.style.WARNING('  Stari Ljubeta podaci obrisani.'))

        today = date.today()

        with transaction.atomic():
            # Rasni psi Ljubete — Dalmatineri (zaštićena hrvatska pasmina)
            # + Njemački ovčari (Sport/radna kategorija HKS)
            PASI = [
                # Format: [ime, pasmina, spol, dob_god, boja, mikrocip, napomena]
                # Dalmatineri (zaštićena HR pasmina)
                ('Argo von Novak',    'Dalmatiner',      'M', 3, 'Bijela s crnim točkama', '191200001111111',
                 'HKS rodovnica HR-2022-00891. HD-A, PRA-Clear. 2× CAC-HR.'),
                ('Bella von Novak',   'Dalmatiner',      'Z', 2, 'Bijela s crnim točkama', '191200002222222',
                 'HKS rodovnica HR-2023-01205. HD-A, PRA-Clear. Uzgojni pregled položen.'),
                ('Cezar von Novak',   'Dalmatiner',      'M', 4, 'Bijela s jetrenastim točkama', '191200003333333',
                 'HKS rodovnica HR-2021-00673. HD-B1, PRA-Clear. 3× CAC-HR, CACIB Wien 2024.'),
                ('Diana von Novak',   'Dalmatiner',      'Z', 5, 'Bijela s crnim točkama', '191200004444444',
                 'HKS rodovnica HR-2020-00412. Prvak HR u ljepoti 2023. Uzgojni broodstock.'),
                # Njemački ovčari (radni)
                ('Emir vom Schwarz',  'Njemački ovčar',  'M', 3, 'Crno-smeđi', '191200005555555',
                 'Uvoz DE. IPO-1 položen. HD-A2, ED-0. SchH WB radna linija.'),
                ('Fiora vom Schwarz', 'Njemački ovčar',  'Z', 2, 'Crno-smeđi', '191200006666666',
                 'Uvoz DE. HD-A, ED-0. Uzgojni pregled: 2025-03-15.'),
                # Leglo Dalmatiner 2025 — štenad
                ('Grof von Novak',    'Dalmatiner',      'M', 0, 'Bijela s crnim točkama', '191200007777777',
                 'Leglo 2025/A. Otac: Cezar, Majka: Diana. Dostupno za udomljenje od 15.05.2025.'),
                ('Hera von Novak',    'Dalmatiner',      'Z', 0, 'Bijela s jetrenastim točkama', '191200008888888',
                 'Leglo 2025/A. Otac: Cezar, Majka: Diana. Rezervirana.'),
            ]

            pas_map = {}
            created_count = 0
            for ime, pasmina, spol, dob_god, boja, mikrocip, napomena in PASI:
                exists = Zivotinja.objects.filter(company=ljubeta_co, mikrocip=mikrocip).exists()
                if exists:
                    pas = Zivotinja.objects.get(company=ljubeta_co, mikrocip=mikrocip)
                    pas_map[ime] = pas
                    continue

                if dob_god == 0:
                    datum_ulaska = today - timedelta(days=30)
                    dob_proc = 'štene ~2 mj'
                    status = 'slobodan'
                else:
                    datum_ulaska = today - timedelta(days=dob_god * 365)
                    dob_proc = f'~{dob_god} god'
                    status = 'slobodan'

                from django.utils import timezone as tz
                max_uz = Zivotinja.objects.filter(
                    evidencijski_br__startswith='UZ-'
                ).order_by('-evidencijski_br').first()
                if max_uz:
                    last_br = int(max_uz.evidencijski_br.split('-')[-1])
                else:
                    last_br = 0
                ev_br = f"UZ-{tz.now().year}-{last_br + 1 + list(pas_map.keys()).index(ime) if ime in pas_map else last_br + 1:04d}"

                pas = Zivotinja(
                    company=ljubeta_co,
                    evidencijski_br=f"UZ-{tz.now().year}-{(len(pas_map)+1):04d}",
                    ime=ime,
                    vrsta='pas',
                    naziv_pasmina=pasmina,
                    spol=spol,
                    dob_procjena=dob_proc,
                    boja_opis=boja,
                    mikrocip=mikrocip,
                    nacin_primitka='ostavljen',
                    status=status,
                    datum_ulaska=datum_ulaska,
                    javno_oglaseno=(dob_god == 0),
                    napomena_ulaz=napomena,
                )
                pas.save()
                pas_map[ime] = pas
                created_count += 1

            self.stdout.write(f'  ✓ Rasni psi: {created_count} novih (ukupno {len(PASI)})')

            # ── Zdravstveni kartoni za uzgajivačnicu ─────────────────
            ZDRAVLJE = [
                ('Argo von Novak',  date(today.year, 1, 15), 'antiparazit',
                 'Bravecto (fluralaner) — zaštita 3 mj.', 'Dr. Šarić, VET Osijek',
                 date(today.year, 4, 15), 'Preventivna zaštita pred sezonu'),
                ('Cezar von Novak', date(today.year, 2, 1), 'pregled',
                 'Predizložbeni pregled — zubalo, HD kontrola', 'Dr. Šarić, VET Osijek',
                 None, 'Potvrda uzgojne dozvole HKS. RTG HD: A (isti kao 2023.)'),
                ('Diana von Novak', date(today.year, 3, 10), 'pregled',
                 'Bremenitost potvrđena ultrazvukom. Očekivano štenjenje: 05.05.2025.',
                 'Dr. Šarić, VET Osijek', date(today.year, 5, 5), 'Leglo 2025/A — Otac: Cezar'),
                ('Grof von Novak',  date(today.year, 3, 20), 'cipiranje',
                 'Mikročipiranje pri 4 tjedna', 'Dr. Šarić, VET Osijek', None,
                 'Chip: 191200007777777'),
                ('Hera von Novak',  date(today.year, 3, 20), 'cipiranje',
                 'Mikročipiranje pri 4 tjedna', 'Dr. Šarić, VET Osijek', None,
                 'Chip: 191200008888888'),
                ('Emir vom Schwarz', date(today.year, 4, 1), 'pregled',
                 'IPO-1 veterinarski nalaz za natjecanje', 'Dr. Šarić, VET Osijek',
                 None, 'Sve nalaze dostaviti kinološkoj udruzi do 10.04.'),
            ]

            zdravlje_count = 0
            for ime, datum, tip, opis, vet, sljedeci, napomena in ZDRAVLJE:
                z = pas_map.get(ime)
                if not z:
                    continue
                _, cr = KartonZdravlja.objects.get_or_create(
                    zivotinja=z,
                    datum=datum,
                    vrsta_tretmana=tip,
                    defaults={
                        'opis': opis + (' | ' + napomena if napomena else ''),
                        'veterinar': vet,
                        'sljedeci_pregled': sljedeci,
                    }
                )
                if cr:
                    zdravlje_count += 1
            self.stdout.write(f'  ✓ Zdravstveni kartoni (Ljubeta): {zdravlje_count} novih')

        self.stdout.write(self.style.SUCCESS(
            '\n  Ljubeta Novak seed završen → /udruge/azil/'))
        self.stdout.write('  Dalmatineri: Argo, Bella, Cezar, Diana, Grof, Hera')
        self.stdout.write('  Njem. ovčari: Emir, Fiora')
        self.stdout.write('  Leglo 2025/A: Grof + Hera (Cezar × Diana)')
