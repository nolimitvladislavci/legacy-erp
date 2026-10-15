-- otpad_katalog / prodaja: život dijela od police do prodaje i povrata.
-- Pokreće se NAKON schema.sql. Idempotentno.
-- Pravilo (Ivan): dio ulazi u račun/fiskalizaciju/lanac TEK kad je prodan. Do tada je samo interni zapis.
-- Ovaj modul NIKAD ne piše u flotu: sve što flota treba ide u red `izlaz_flota` (outbox);
-- računi, fiskalizacija i DokArh se pozivaju postojećim modulima flote iz tog reda.

-- Statusi: zaliha → prodaja → isporuka → (povrat | reklamacija) → nazad na zalihu ili škart.
ALTER TABLE otpad_dio DROP CONSTRAINT IF EXISTS otpad_dio_status_check;
ALTER TABLE otpad_dio ADD CONSTRAINT otpad_dio_status_check
    CHECK (status IN ('NA_ZALIHI', 'REZERVIRAN', 'PRODAN', 'ISPORUCEN', 'POVRAT_ZATRAZEN', 'SKART'));

ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS jamstvo_mjeseci integer NOT NULL DEFAULT 12
    CHECK (jamstvo_mjeseci BETWEEN 0 AND 60);
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS kupac text;                 -- interno; NIKAD u lanac ni DokArh
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS kupac_fizicka_osoba boolean;
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS prodano_na_daljinu boolean;
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS prodajna_cijena_centi integer CHECK (prodajna_cijena_centi > 0);
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS datum_prodaje timestamptz;
ALTER TABLE otpad_dio ADD COLUMN IF NOT EXISTS povrat_do date;             -- 14 dana, samo prodaja na daljinu

-- Lanac događaja po dijelu: dopisuje se, ne mijenja. hash = sha256(prev|dio|vrsta|podaci|vrijeme).
-- `podaci` ne smije nositi osobne podatke kupca (to je ugovoreno testom).
CREATE TABLE IF NOT EXISTS dio_dogadjaj (
    id              bigserial PRIMARY KEY,
    otpad_dio_id    integer NOT NULL REFERENCES otpad_dio(id),
    vrsta           text NOT NULL CHECK (vrsta IN
                      ('PRODAJA', 'PLACANJE_KOD', 'ISPORUKA', 'POVRAT_ZATRAZEN', 'POVRAT_ZAPRIMLJEN')),
    vrijeme         text NOT NULL,                 -- ISO 8601 UTC, točno onaj niz koji je ušao u hash
    podaci          jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash       text NOT NULL,
    hash            text NOT NULL UNIQUE,
    CONSTRAINT dio_dogadjaj_hash_oblik CHECK (hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS dio_dogadjaj_dio ON dio_dogadjaj (otpad_dio_id, id);

CREATE OR REPLACE FUNCTION dio_dogadjaj_samo_dopis() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'dio_dogadjaj se samo dopisuje (% nije dopušten)', TG_OP;
END $$;

DROP TRIGGER IF EXISTS dio_dogadjaj_nepromjenjiv ON dio_dogadjaj;
CREATE TRIGGER dio_dogadjaj_nepromjenjiv BEFORE UPDATE OR DELETE ON dio_dogadjaj
    FOR EACH ROW EXECUTE FUNCTION dio_dogadjaj_samo_dopis();

-- Izlazni red prema floti (outbox). Flota ga čita; ovaj modul u flotu ne piše.
CREATE TABLE IF NOT EXISTS izlaz_flota (
    id            bigserial PRIMARY KEY,
    dogadjaj_id   bigint NOT NULL REFERENCES dio_dogadjaj(id),
    cilj          text NOT NULL CHECK (cilj IN ('RACUN', 'STORNO', 'DOKARH')),
    podaci        jsonb NOT NULL,
    stanje        text NOT NULL DEFAULT 'CEKA' CHECK (stanje IN ('CEKA', 'POSLANO', 'PAO')),
    kreirano      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS izlaz_flota_stanje ON izlaz_flota (stanje, id);

-- Uloga s najmanjim pravima za modul prodaje (lozinku postavlja administrator izvan repoa).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'otpad_prodaja') THEN
        CREATE ROLE otpad_prodaja LOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO otpad_prodaja;
GRANT SELECT ON izvor, vozilo_tip, dio, dio_broj, otpad_vozilo TO otpad_prodaja;
GRANT SELECT ON otpad_dio TO otpad_prodaja;
GRANT UPDATE (status, jamstvo_mjeseci, kupac, kupac_fizicka_osoba, prodano_na_daljinu,
              prodajna_cijena_centi, datum_prodaje, povrat_do) ON otpad_dio TO otpad_prodaja;
GRANT SELECT, INSERT ON dio_dogadjaj, izlaz_flota TO otpad_prodaja;
GRANT USAGE ON SEQUENCE dio_dogadjaj_id_seq, izlaz_flota_id_seq TO otpad_prodaja;
