-- otpad_katalog: interna baza kataloških brojeva za auto otpad (bez slika).
-- PostgreSQL. Idempotentno: može se pokrenuti više puta.
-- Pravilo: broj se uvijek pretražuje preko broj_norm (velika slova, bez razmaka i crtica).

CREATE OR REPLACE FUNCTION norm_broj(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT upper(regexp_replace(coalesce(t, ''), '[^0-9A-Za-z]', '', 'g'))
$$;

-- "Citroën" -> "citroen", "Škoda" -> "skoda"; bez ekstenzije unaccent.
CREATE OR REPLACE FUNCTION bez_dijakritika(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT translate(lower(coalesce(t, '')),
                   'čćžšđäöüßéèêëàáâíìîóòôúùûñç',
                   'cczsdaouseeeeaaaiiiooouuunc')
$$;

CREATE TABLE IF NOT EXISTS izvor (
    id        serial PRIMARY KEY,
    naziv     text NOT NULL UNIQUE,
    verzija   text,
    licenca   text,
    napomena  text
);

-- Tip vozila = marka + model + generacija s godištima.
CREATE TABLE IF NOT EXISTS vozilo_tip (
    id          serial PRIMARY KEY,
    marka       text NOT NULL,
    model       text NOT NULL,
    generacija  text NOT NULL DEFAULT '',
    godina_od   integer NOT NULL,
    godina_do   integer,                 -- NULL = još u proizvodnji
    motor_kod   text,
    kw          integer,
    ccm         integer,
    gorivo      text,
    izvor_id    integer REFERENCES izvor(id),
    CONSTRAINT vozilo_tip_godine CHECK (godina_do IS NULL OR godina_do >= godina_od),
    CONSTRAINT vozilo_tip_jedinstven UNIQUE (marka, model, generacija, godina_od)
);
CREATE INDEX IF NOT EXISTS vozilo_tip_marka_model ON vozilo_tip (marka, model);

CREATE TABLE IF NOT EXISTS dio (
    id          serial PRIMARY KEY,
    naziv_hr    text NOT NULL,
    naziv_de    text,
    kategorija  text
);

-- Jedan dio može imati više brojeva: OEM, kataloški, proizvođača, interni.
CREATE TABLE IF NOT EXISTS dio_broj (
    id           serial PRIMARY KEY,
    dio_id       integer NOT NULL REFERENCES dio(id) ON DELETE CASCADE,
    broj         text NOT NULL,                       -- kako je napisan
    broj_norm    text NOT NULL,                       -- za pretragu
    vrsta        text NOT NULL CHECK (vrsta IN ('OEM', 'KATALOSKI', 'PROIZVODJAC', 'INTERNI')),
    proizvodjac  text,
    izvor_id     integer REFERENCES izvor(id),
    CONSTRAINT dio_broj_norm_je_norm CHECK (broj_norm = norm_broj(broj)),
    CONSTRAINT dio_broj_nije_prazan CHECK (broj_norm <> ''),
    CONSTRAINT dio_broj_jedinstven UNIQUE (dio_id, broj_norm, vrsta)
);
CREATE INDEX IF NOT EXISTS dio_broj_norm ON dio_broj (broj_norm);

-- Na koje tipove vozila dio stane.
CREATE TABLE IF NOT EXISTS dio_vozilo (
    dio_id          integer NOT NULL REFERENCES dio(id) ON DELETE CASCADE,
    vozilo_tip_id   integer NOT NULL REFERENCES vozilo_tip(id) ON DELETE CASCADE,
    napomena        text,
    izvor_id        integer REFERENCES izvor(id),
    PRIMARY KEY (dio_id, vozilo_tip_id)
);

-- Vaši auti na otpadu.
CREATE TABLE IF NOT EXISTS otpad_vozilo (
    id              serial PRIMARY KEY,
    vin             text UNIQUE,
    vozilo_tip_id   integer REFERENCES vozilo_tip(id),
    km              integer,
    datum_dolaska   date,
    napomena        text,
    CONSTRAINT otpad_vozilo_vin CHECK (vin IS NULL OR length(vin) = 17)
);

-- Vaši skinuti dijelovi na zalihi.
CREATE TABLE IF NOT EXISTS otpad_dio (
    id                 serial PRIMARY KEY,
    dio_id             integer REFERENCES dio(id),
    otpad_vozilo_id    integer REFERENCES otpad_vozilo(id),
    broj_na_dijelu     text,              -- što je stvarno otisnuto na dijelu
    broj_norm          text GENERATED ALWAYS AS (norm_broj(broj_na_dijelu)) STORED,
    polica             text,
    stanje             text CHECK (stanje IN ('A', 'B', 'C', 'D')),
    cijena             numeric(10, 2),
    status             text NOT NULL DEFAULT 'NA_ZALIHI'
                       CHECK (status IN ('NA_ZALIHI', 'REZERVIRAN', 'PRODAN')),
    kreirano           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS otpad_dio_broj_norm ON otpad_dio (broj_norm);
CREATE INDEX IF NOT EXISTS otpad_dio_status ON otpad_dio (status);
