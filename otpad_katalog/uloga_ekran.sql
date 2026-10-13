-- Jedna uloga za web ekran: stari unos (otpad_app) + tamni dio i prodaja (otpad_prodaja). Pokreće se nakon uloga_app.sql
-- i prodaja/schema_tamno.sql. Lozinku postavlja administrator izvan repoa:  ALTER ROLE otpad_ekran PASSWORD '...';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'otpad_ekran') THEN
        CREATE ROLE otpad_ekran LOGIN;
    END IF;
END $$;
GRANT otpad_app, otpad_prodaja TO otpad_ekran;
