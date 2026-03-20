from companies.models import ServiceTemplate

ServiceTemplate.objects.all().delete()

templates = [
    # ── FRIZER ─────────────────────────────────────────────────────────────
    ('frizer', 'Šišanje muško',           'kom',  12.00, 25, 'Muški salon',  1),
    ('frizer', 'Šišanje žensko (kratka)', 'kom',  25.00, 25, 'Ženski salon', 2),
    ('frizer', 'Šišanje žensko (duga)',   'kom',  35.00, 25, 'Ženski salon', 3),
    ('frizer', 'Pranje i frizura',        'kom',  30.00, 25, 'Ženski salon', 4),
    ('frizer', 'Bojanje kose (korijeni)', 'kom',  45.00, 25, 'Bojanje',      5),
    ('frizer', 'Bojanje kose (cijela)',   'kom',  70.00, 25, 'Bojanje',      6),
    ('frizer', 'Highlights / Farbanje',   'kom',  90.00, 25, 'Bojanje',      7),
    ('frizer', 'Keratin tretman',         'kom', 120.00, 25, 'Tretmani',     8),
    ('frizer', 'Trajni uvojci',           'kom',  65.00, 25, 'Tretmani',     9),
    ('frizer', 'Brijanje brade',          'kom',  10.00, 25, 'Muški salon', 10),
    ('frizer', 'Šišanje djeca (do 10g)',  'kom',   8.00, 25, 'Djeca',       11),
    ('frizer', 'Uklanjanje maske za kosu','kom',  15.00, 25, 'Tretmani',    12),

    # ── MEHANIČAR ──────────────────────────────────────────────────────────
    ('mehaničar', 'Dijagnostika vozila',         'kom',  30.00, 25, 'Dijagnostika', 1),
    ('mehaničar', 'Promjena ulja i filtera',      'kom',  40.00, 25, 'Servis',       2),
    ('mehaničar', 'Zamjena kočionih pločica (par)','par', 60.00, 25, 'Kočnice',      3),
    ('mehaničar', 'Zamjena diskova (par)',         'par', 80.00, 25, 'Kočnice',      4),
    ('mehaničar', 'Zamjena guma (1 kom)',          'kom',  15.00, 25, 'Gume',         5),
    ('mehaničar', 'Balansiranje kotača',           'kom',   8.00, 25, 'Gume',         6),
    ('mehaničar', 'Zamjena amortizera (par)',      'par', 120.00, 25, 'Ovjes',        7),
    ('mehaničar', 'Zamjena remena (distribucija)', 'kom', 200.00, 25, 'Motor',        8),
    ('mehaničar', 'Zamjena svjećica',              'set',  25.00, 25, 'Motor',        9),
    ('mehaničar', 'Klima punjenje/servis',         'kom',  60.00, 25, 'Klima',       10),
    ('mehaničar', 'Tehnički pregled (priprema)',   'kom',  50.00, 25, 'Pregled',     11),
    ('mehaničar', 'Sat rada mehaničara',           'h',    45.00, 25, 'Rad',         12),
    ('mehaničar', 'Zamjena baterije',              'kom',  25.00, 25, 'Elektrika',   13),
    ('mehaničar', 'Popravak ispušnog sustava',     'kom',  80.00, 25, 'Ispušni',     14),

    # ── GRAĐEVINA ──────────────────────────────────────────────────────────
    ('gradjevina', 'Sat rada radnika',             'h',    20.00, 25, 'Radna snaga',   1),
    ('gradjevina', 'Sat rada voditelja radova',    'h',    35.00, 25, 'Radna snaga',   2),
    ('gradjevina', 'Zidanje (m2)',                 'm2',   35.00, 25, 'Zidarski rad',  3),
    ('gradjevina', 'Žbukanje / Fasada (m2)',       'm2',   18.00, 25, 'Fasada',        4),
    ('gradjevina', 'Postavljanje pločica (m2)',    'm2',   22.00, 25, 'Pločice',       5),
    ('gradjevina', 'Postavljanje parketa (m2)',    'm2',   20.00, 25, 'Parket',        6),
    ('gradjevina', 'Sušenje estriha (m2)',         'm2',   12.00, 25, 'Estrih',        7),
    ('gradjevina', 'Postavljanje gipskarton (m2)', 'm2',   25.00, 25, 'Gipskarton',    8),
    ('gradjevina', 'Instalacija sanitarija',       'kom',  80.00, 25, 'Kupaonice',     9),
    ('gradjevina', 'Postavljanje kade / tuša',     'kom', 150.00, 25, 'Kupaonice',    10),
    ('gradjevina', 'Elektroinstalacija (točka)',   'kom',  45.00, 25, 'Elektrika',    11),
    ('gradjevina', 'Vodoinstalacija (točka)',      'kom',  55.00, 25, 'Voda',         12),
    ('gradjevina', 'Dostava materijala (km)',       'km',    1.50, 25, 'Transport',    13),
    ('gradjevina', 'Iznajmljivanje skele (dan)',    'dan',  15.00, 25, 'Oprema',       14),
    ('gradjevina', 'Projekt konzultacija',          'h',    60.00, 25, 'Projektiranje',15),

    # ── OPTIKA ─────────────────────────────────────────────────────────────
    ('optika', 'Pregled vida',                    'kom',  25.00, 25, 'Pregledi',     1),
    ('optika', 'Okvir dioptrijske naočale',       'kom',  80.00, 25, 'Okviri',       2),
    ('optika', 'Okvir sunčane naočale',           'kom',  60.00, 25, 'Okviri',       3),
    ('optika', 'Stakla CR39 (par)',               'par',  50.00, 25, 'Stakla',       4),
    ('optika', 'Stakla polikarbonat (par)',        'par',  70.00, 25, 'Stakla',       5),
    ('optika', 'Stakla progresivna (par)',         'par', 180.00, 25, 'Stakla',       6),
    ('optika', 'Kontaktne leće mjesečne (par)',    'par',  20.00, 25, 'Leće',         7),
    ('optika', 'Kontaktne leće dnevne (30 kom)',   'pak',  30.00, 25, 'Leće',         8),
    ('optika', 'Otopina za leće (250ml)',          'kom',   8.00, 25, 'Pribor',       9),
    ('optika', 'Popravak okvira',                  'kom',  15.00, 25, 'Servis',      10),
    ('optika', 'Zamjena nose pads',                'kom',   5.00, 25, 'Servis',      11),
    ('optika', 'Ultrazvučno čišćenje naočala',     'kom',   8.00, 25, 'Servis',      12),
    ('optika', 'Dioptrijska zaštitna stakla (par)','par', 120.00, 25, 'Stakla',      13),
]

objs = [
    ServiceTemplate(
        profile_type=pt, name=n, unit=u,
        default_price=p, tax_rate=t, category=cat, sort_order=so
    )
    for pt, n, u, p, t, cat, so in templates
]
ServiceTemplate.objects.bulk_create(objs)
print(f'Seeded {len(objs)} service templates:')
from django.db.models import Count
for row in ServiceTemplate.objects.values('profile_type').annotate(n=Count('id')):
    print(f"  {row['profile_type']}: {row['n']} usluga")
