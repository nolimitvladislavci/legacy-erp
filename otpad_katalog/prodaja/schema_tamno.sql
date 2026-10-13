-- otpad_katalog / prodaja: TAMNI dio (od rođenja do stalaže) i vrata prema svjetlu (KELAVA_PLAN_K2 §1).
-- Pokreće se NAKON schema_prodaja.sql. Idempotentno.
-- Do `STAVI_U_PRODAJU` dio živi samo u ovoj bazi. U lanac flote ide jedan atom s Merkle korijenom
-- privatnog dnevnika (dio_dogadjaj), nikad sadržaj. Dnevnik je isti lanac događaja kao u prodaji (bez dupliciranja).

-- Stanja: RODEN → PREDRADNJE → NA_STALAZI → NA_ZALIHI (= "U_PRODAJI" iz plana) → PRODAN → … (kao u schema_prodaja.sql)
ALTER TABLE otpad_dio DROP CONSTRAINT IF EXISTS otpad_dio_status_check;
ALTER TABLE otpad_dio ADD CONSTRAINT otpad_dio_status_check
    CHECK (status IN ('RODEN', 'PREDRADNJE', 'NA_STALAZI', 'NA_ZALIHI', 'REZERVIRAN', 'PRODAN', 'ISPORUCEN',
                      'POVRAT_ZATRAZEN', 'SKART'));

ALTER TABLE dio_dogadjaj DROP CONSTRAINT IF EXISTS dio_dogadjaj_vrsta_check;
ALTER TABLE dio_dogadjaj ADD CONSTRAINT dio_dogadjaj_vrsta_check CHECK (vrsta IN
    ('RODEN', 'SLIKAN', 'OPRAN', 'TESTIRAN', 'PAKIRAN', 'SPREMLJEN', 'PREMJESTEN', 'STAVLJEN_U_PRODAJU', 'OBILAZAK',
     'PRODAJA', 'PLACANJE_KOD', 'ISPORUKA', 'POVRAT_ZATRAZEN', 'POVRAT_ZAPRIMLJEN'));

ALTER TABLE izlaz_flota ALTER COLUMN dogadjaj_id DROP NOT NULL;   -- tjedni atom nije vezan uz jedan događaj
ALTER TABLE izlaz_flota DROP CONSTRAINT IF EXISTS izlaz_flota_cilj_check;
ALTER TABLE izlaz_flota ADD CONSTRAINT izlaz_flota_cilj_check
    CHECK (cilj IN ('RACUN', 'STORNO', 'DOKARH', 'LANAC_SVJETLO', 'OGLAS', 'LANAC_TJEDNI'));

-- Pretinac je adresa: R03-P2-04 = regal 03, polica 2, pretinac 04. Oznaka ide na stalažu jednom i trajno.
CREATE TABLE IF NOT EXISTS pretinac (
    adresa  text PRIMARY KEY CHECK (adresa ~ '^R[0-9]{2}-P[0-9]-[0-9]{2}$'),
    opis    text
);

ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS token text UNIQUE;                -- srce koda dijela (nasumično, ne pogađa se)
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS pretinac_adresa text REFERENCES pretinac(adresa);
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS razred_jamstva text
    CHECK (razred_jamstva IN ('POTROSAC_12M', 'POTROSAC_24M', 'PRAVNA_BEZ'));

-- Slike: ovdje samo veza i otisak (sadržaj živi u ARHIVA 2030, NIKAD u Krunici). javna = izbor za webshop.
CREATE TABLE IF NOT EXISTS dio_slika (
    id            bigserial PRIMARY KEY,
    otpad_dio_id  integer NOT NULL REFERENCES otpad_dio(id),
    vrsta         text NOT NULL CHECK (vrsta IN ('DIO', 'POSLIJE_PRANJA', 'PAKET', 'POLICA')),
    sha256        text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    ref           text NOT NULL,
    javna         boolean NOT NULL DEFAULT false,
    kreirano      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (otpad_dio_id, sha256)
);
CREATE INDEX IF NOT EXISTS dio_slika_dio ON dio_slika (otpad_dio_id);

-- Stari hardver: broj s postojeće naljepnice (npr. Code 128) mapira se na token. Ništa se ne izbacuje.
CREATE TABLE IF NOT EXISTS kod_alias (
    alias   text PRIMARY KEY,
    token   text NOT NULL REFERENCES otpad_dio(token),
    vrsta   text NOT NULL DEFAULT 'CODE128'
);

GRANT SELECT ON pretinac TO otpad_prodaja;
GRANT INSERT ON otpad_dio TO otpad_prodaja;
GRANT UPDATE (token, pretinac_adresa, razred_jamstva, cijena, otpad_vozilo_id, dio_id, broj_na_dijelu)
    ON otpad_dio TO otpad_prodaja;
GRANT SELECT, INSERT ON dio_slika, kod_alias TO otpad_prodaja;
GRANT UPDATE (javna) ON dio_slika TO otpad_prodaja;
GRANT USAGE ON SEQUENCE otpad_dio_id_seq, dio_slika_id_seq TO otpad_prodaja;
