-- Uloga za web ekran s NAJMANJIM potrebnim pravima (bez DELETE, bez DDL).
-- Lozinku postavlja administrator izvan repoa:  ALTER ROLE otpad_app PASSWORD '...';
-- Pokreće se nakon schema.sql. Idempotentno.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'otpad_app') THEN
        CREATE ROLE otpad_app LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO otpad_app;
GRANT SELECT ON izvor, vozilo_tip TO otpad_app;
GRANT SELECT, INSERT ON dio, dio_broj, dio_vozilo, otpad_vozilo, otpad_dio TO otpad_app;
GRANT USAGE ON SEQUENCE dio_id_seq, dio_broj_id_seq, otpad_vozilo_id_seq, otpad_dio_id_seq TO otpad_app;
