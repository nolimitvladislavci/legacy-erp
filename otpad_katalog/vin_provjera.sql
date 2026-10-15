-- Tvrda provjera VIN-a u bazi (sloj 1 + 5): 17 znakova, A–Z bez I/O/Q i 0–9, jedinstven.
-- Pokreće se nakon schema.sql. Idempotentno. Kontrolnu znamenku i ostale slojeve provjerava vin.py.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'otpad_vozilo_vin_znakovi') THEN
        ALTER TABLE otpad_vozilo
            ADD CONSTRAINT otpad_vozilo_vin_znakovi CHECK (vin IS NULL OR vin ~ '^[A-HJ-NPR-Z0-9]{17}$');
    END IF;
END $$;
