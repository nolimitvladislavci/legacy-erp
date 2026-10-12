-- PROBNI PODACI za testiranje. Brojevi (prefiks TST) su IZMIŠLJENI, ne postoje u stvarnosti.
-- Ne pokretati na produkciji. Zahtijeva schema.sql, pretraga.sql i uvezeni vozilo_tip.
-- Idempotentno.

INSERT INTO izvor (naziv, napomena)
VALUES ('PROBNI PODACI', 'Izmišljeni brojevi s prefiksom TST, samo za testiranje')
ON CONFLICT (naziv) DO NOTHING;

CREATE TEMP TABLE _probni (
    naziv_hr text, naziv_de text, kategorija text, broj text,
    marka text, model text, generacija text
);

INSERT INTO _probni VALUES
 ('Alternator',        'Lichtmaschine',       'Elektrika',   'TST 100 001 A', 'Ford', 'Focus',  'Mk III'),
 ('Anlaser',           'Anlasser',            'Elektrika',   'TST 100 002 A', 'Ford', 'Focus',  'Mk III'),
 ('Far lijevi',        'Scheinwerfer links',  'Svjetla',     'TST 100 003 B', 'Ford', 'Focus',  'Mk III'),
 ('Far desni',         'Scheinwerfer rechts', 'Svjetla',     'TST 100 004 B', 'Ford', 'Focus',  'Mk III'),
 ('Odbojnik prednji',  'Stoßstange vorn',     'Karoserija',  'TST 100 005 C', 'Ford', 'Focus',  'Mk III'),
 ('Vrata prednja lijeva','Tür vorn links',    'Karoserija',  'TST 100 006 C', 'Ford', 'Focus',  'Mk III'),
 ('Retrovizor desni',  'Außenspiegel rechts', 'Karoserija',  'TST 100 007 C', 'Ford', 'Focus',  'Mk III'),
 ('Računalo motora',   'Motorsteuergerät',    'Elektronika', 'TST 100 008 D', 'Ford', 'Focus',  'Mk III'),
 ('Mjenjač 5 brzina',  'Getriebe 5-Gang',     'Pogon',       'TST 100 009 D', 'Ford', 'Focus',  'Mk III'),
 ('Turbo',             'Turbolader',          'Motor',       'TST 100 010 E', 'Ford', 'Focus',  'Mk III'),
 ('ABS pumpa',         'ABS-Hydraulikblock',  'Kočnice',     'TST 100 011 E', 'Ford', 'Focus',  'Mk II'),
 ('Kompresor klime',   'Klimakompressor',     'Klima',       'TST 100 012 F', 'Ford', 'Focus',  'Mk II'),
 ('Hladnjak vode',     'Wasserkühler',        'Hlađenje',    'TST 100 013 F', 'Ford', 'Focus',  'Mk II'),
 ('Servo pumpa',       'Servopumpe',          'Upravljanje', 'TST 100 014 G', 'Ford', 'Focus',  'Mk II'),
 ('Amortizer prednji', 'Stoßdämpfer vorn',    'Ovjes',       'TST 100 015 G', 'Ford', 'Focus',  'Mk II'),
 ('Brizgaljka',        'Einspritzdüse',       'Motor',       'TST 100 016 H', 'Ford', 'Fiesta', 'Mk VII'),
 ('Spojka',            'Kupplung',            'Pogon',       'TST 100 017 H', 'Ford', 'Fiesta', 'Mk VII'),
 ('Maska',             'Kühlergrill',         'Karoserija',  'TST 100 018 H', 'Ford', 'Fiesta', 'Mk VII'),
 ('Haube motora',      'Motorhaube',          'Karoserija',  'TST 100 019 J', 'Ford', 'Fiesta', 'Mk VII'),
 ('Sjedalo vozača',    'Fahrersitz',          'Unutrašnjost','TST 100 020 J', 'Ford', 'Fiesta', 'Mk VII');

DO $$
DECLARE
    r record; did integer; iz integer;
BEGIN
    SELECT id INTO iz FROM izvor WHERE naziv = 'PROBNI PODACI';
    FOR r IN SELECT * FROM _probni LOOP
        IF EXISTS (SELECT 1 FROM dio_broj WHERE broj_norm = norm_broj(r.broj)) THEN
            CONTINUE;
        END IF;
        INSERT INTO dio (naziv_hr, naziv_de, kategorija)
        VALUES (r.naziv_hr, r.naziv_de, r.kategorija) RETURNING id INTO did;
        INSERT INTO dio_broj (dio_id, broj, broj_norm, vrsta, proizvodjac, izvor_id)
        VALUES (did, r.broj, norm_broj(r.broj), 'OEM', 'PROBNI', iz);
        INSERT INTO dio_vozilo (dio_id, vozilo_tip_id, izvor_id)
        SELECT did, v.id, iz FROM vozilo_tip v
        WHERE v.marka = r.marka AND v.model = r.model AND v.generacija = r.generacija;
    END LOOP;

    -- broj proizvođača za alternator (drugi broj istog dijela)
    INSERT INTO dio_broj (dio_id, broj, broj_norm, vrsta, proizvodjac, izvor_id)
    SELECT b.dio_id, 'TSTX 986 000 001', norm_broj('TSTX 986 000 001'), 'PROIZVODJAC', 'PROBNI', iz
    FROM dio_broj b WHERE b.broj_norm = norm_broj('TST 100 001 A')
    ON CONFLICT DO NOTHING;

    -- računalo motora stane i na Focus Mk II (dio na dva tipa vozila)
    INSERT INTO dio_vozilo (dio_id, vozilo_tip_id, izvor_id)
    SELECT b.dio_id, v.id, iz
    FROM dio_broj b, vozilo_tip v
    WHERE b.broj_norm = norm_broj('TST 100 008 D')
      AND v.marka = 'Ford' AND v.model = 'Focus' AND v.generacija = 'Mk II'
    ON CONFLICT DO NOTHING;
END $$;

-- jedan auto na otpadu i tri skinuta dijela
INSERT INTO otpad_vozilo (vin, vozilo_tip_id, km, datum_dolaska, napomena)
SELECT 'TESTVIN0000000001', v.id, 187000, DATE '2026-10-01', 'probni auto'
FROM vozilo_tip v
WHERE v.marka = 'Ford' AND v.model = 'Focus' AND v.generacija = 'Mk III'
ON CONFLICT (vin) DO NOTHING;

INSERT INTO otpad_dio (dio_id, otpad_vozilo_id, broj_na_dijelu, polica, stanje, cijena, status)
SELECT b.dio_id, ov.id, x.na_dijelu, x.polica, x.stanje, x.cijena, x.status
FROM (VALUES
    ('TST 100 001 A', 'tst-100-001-a', 'A-01-3', 'B', 45.00, 'NA_ZALIHI'),
    ('TST 100 002 A', 'TST100002A',    'A-01-4', 'A', 38.00, 'NA_ZALIHI'),
    ('TST 100 003 B', 'TST 100 003 B', 'B-02-1', 'C', 60.00, 'PRODAN')
) AS x(broj, na_dijelu, polica, stanje, cijena, status)
JOIN dio_broj b ON b.broj_norm = norm_broj(x.broj)
JOIN otpad_vozilo ov ON ov.vin = 'TESTVIN0000000001'
WHERE NOT EXISTS (SELECT 1 FROM otpad_dio o
                  WHERE o.dio_id = b.dio_id AND o.otpad_vozilo_id = ov.id);
