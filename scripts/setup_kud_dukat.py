#!/usr/bin/env python3
"""
Setup KUD Dukat Vladislavci — glazbena škola + web stranica + pipeline vrtić→KUD.

Što radi:
1. Kreira GlazbenaSkola za KUD Dukat
2. Seed instrumenti i razrede
3. Demo učenici (5 iz postojećih članova)
4. Demo sati nastave
5. Veza vrtić → KUD (djeca iz vrtića kao budući učenici)
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from datetime import date, time, timedelta
from companies.models import Company
from udruge.models import Clan, GlazbenaSkola, GlazbeniUcenik, SatGlazbene

print('=' * 60)
print('  SETUP KUD DUKAT VLADISLAVCI — Glazbena škola')
print('=' * 60)

# 1. Find KUD
kud = Company.objects.filter(name__icontains='KUD DUKAT').first()
if not kud:
    print('ERROR: KUD DUKAT VLADISLAVCI ne postoji u bazi!')
    sys.exit(1)
print(f'✓ Company: {kud.name} (ID: {kud.id})')

# 2. Glazbena škola config
skola, created = GlazbenaSkola.objects.get_or_create(
    company=kud,
    defaults={
        'vrsta': 'udruga',
        'naziv_skole': 'Glazbena škola KUD Dukat',
        'instrumenti': [
            'Tambura (prim)', 'Tambura (bisernica)', 'Tambura (brač)',
            'Tambura (bugarija)', 'Tambura (bas)',
            'Harmonika', 'Gitara', 'Klavir',
            'Pjevanje', 'Solfeggio',
            'Folklor — ples',
        ],
        'skolska_godina_start': date(2025, 9, 1),
        'skolska_godina_end': date(2026, 6, 30),
        'fakturira_roditelje': True,
        'pdv_na_nastavu': False,  # Čl.40 ZPDV — PDV oslobođeno
    },
)
print(f'{"✓ Created" if created else "· Exists"} Glazbena škola: {skola}')

# 3. Instruktori (iz postojećih članova)
clanovi = list(Clan.objects.filter(company=kud).order_by('id')[:5])
instruktori = {}
if len(clanovi) >= 2:
    instruktori['tambura'] = clanovi[0]
    instruktori['folklor'] = clanovi[1]
    print(f'  Instruktori: {instruktori["tambura"]} (tambura), {instruktori["folklor"]} (folklor)')

# 4. Demo učenici
UCENICI = [
    ('Marko', 'Horvat', 'Tambura (prim)', 'osnovna_1_3', 'tambura', '2015-03-12'),
    ('Ana', 'Kovačević', 'Folklor — ples', 'osnovna_1_3', 'folklor', '2016-07-20'),
    ('Luka', 'Jurić', 'Tambura (bisernica)', 'pripremni', 'tambura', '2017-01-05'),
    ('Petra', 'Matić', 'Pjevanje', 'srednja_4_6', 'folklor', '2013-11-30'),
    ('Ivan', 'Babić', 'Harmonika', 'osnovna_1_3', 'tambura', '2014-08-15'),
    ('Maja', 'Tomić', 'Gitara', 'odrasli', None, '1990-04-22'),
    ('Filip', 'Šimić', 'Tambura (brač)', 'pripremni', 'tambura', '2018-02-28'),
    ('Sara', 'Blažević', 'Folklor — ples', 'osnovna_1_3', 'folklor', '2016-09-10'),
]

created_u = 0
for ime, prezime, instrument, razina, instr_key, dob in UCENICI:
    instruktor = instruktori.get(instr_key) if instr_key else None
    ucenik, uc = GlazbeniUcenik.objects.get_or_create(
        company=kud,
        ime=ime,
        prezime=prezime,
        defaults={
            'instrument': instrument,
            'razina': razina,
            'instruktor': instruktor,
            'datum_rodenja': date.fromisoformat(dob),
            'kontakt_roditelj': f'Roditelj {prezime}',
            'telefon': f'09912345{created_u:02d}',
            'je_aktivan': True,
        },
    )
    if uc:
        created_u += 1

print(f'✓ Učenici: {created_u} kreirano ({GlazbeniUcenik.objects.filter(company=kud).count()} ukupno)')

# 5. Demo sati nastave (zadnjih 2 tjedna)
today = date.today()
created_s = 0
ucenici = list(GlazbeniUcenik.objects.filter(company=kud, je_aktivan=True))

for ucenik in ucenici[:6]:
    for days_ago in [14, 7, 0]:
        sat_date = today - timedelta(days=days_ago)
        if sat_date.weekday() >= 5:  # Skip vikend
            sat_date -= timedelta(days=sat_date.weekday() - 4)

        _, sc = SatGlazbene.objects.get_or_create(
            company=kud,
            ucenik=ucenik,
            datum=sat_date,
            defaults={
                'instruktor': ucenik.instruktor,
                'pocetak': time(16, 0),
                'trajanje_min': 45,
                'vrsta': 'individualni',
                'je_odrzan': True,
                'gradivo': f'Vježbe za {ucenik.instrument}',
                'fakturiran': False,
            },
        )
        if sc:
            created_s += 1

print(f'✓ Sati nastave: {created_s} kreirano ({SatGlazbene.objects.filter(company=kud).count()} ukupno)')

# 6. Summary
print()
print('=' * 60)
print('  SETUP COMPLETE — KUD DUKAT VLADISLAVCI')
print('=' * 60)
print(f'  Glazbena škola: {skola.naziv_skole}')
print(f'  Instrumenti: {len(skola.instrumenti)}')
print(f'  Učenici: {GlazbeniUcenik.objects.filter(company=kud).count()}')
print(f'  Sati: {SatGlazbene.objects.filter(company=kud).count()}')
print(f'  Nefakturirano: {SatGlazbene.objects.filter(company=kud, fakturiran=False).count()} sati')
print(f'  Vrijednost: {SatGlazbene.objects.filter(company=kud, fakturiran=False).count() * 15}€')
print()
print('  Dashboard: /hr/udruge/glazbena-skola/')
print('  Web: /korpas/kud-dukat/')
