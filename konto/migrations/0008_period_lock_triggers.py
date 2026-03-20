from django.db import migrations


FORWARD_SQL = """
-- Function for JournalEntry (date field: date, type: DateField)
CREATE OR REPLACE FUNCTION check_period_lock_journal()
RETURNS TRIGGER AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM konto_accountingperiod
    WHERE company_id = NEW.company_id
      AND is_locked = TRUE
      AND year = EXTRACT(YEAR FROM NEW.date)::INTEGER
      AND month = EXTRACT(MONTH FROM NEW.date)::INTEGER
  ) THEN
    RAISE EXCEPTION 'Razdoblje %/% je zaključano. Knjiženje nije dozvoljeno.',
      LPAD(EXTRACT(MONTH FROM NEW.date)::TEXT, 2, '0'),
      EXTRACT(YEAR FROM NEW.date)::TEXT;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_period_lock_journal
BEFORE INSERT OR UPDATE ON konto_journalentry
FOR EACH ROW EXECUTE FUNCTION check_period_lock_journal();

-- Function for Invoice (date field: date_issued, type: DateTimeField)
CREATE OR REPLACE FUNCTION check_period_lock_invoice()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.date_issued IS NOT NULL AND EXISTS (
    SELECT 1 FROM konto_accountingperiod
    WHERE company_id = NEW.company_id
      AND is_locked = TRUE
      AND year = EXTRACT(YEAR FROM NEW.date_issued)::INTEGER
      AND month = EXTRACT(MONTH FROM NEW.date_issued)::INTEGER
  ) THEN
    RAISE EXCEPTION 'Razdoblje %/% je zaključano. Izdavanje računa nije dozvoljeno.',
      LPAD(EXTRACT(MONTH FROM NEW.date_issued)::TEXT, 2, '0'),
      EXTRACT(YEAR FROM NEW.date_issued)::TEXT;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_period_lock_invoice
BEFORE INSERT OR UPDATE ON invoicing_invoice
FOR EACH ROW EXECUTE FUNCTION check_period_lock_invoice();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_period_lock_journal ON konto_journalentry;
DROP TRIGGER IF EXISTS trg_period_lock_invoice ON invoicing_invoice;
DROP FUNCTION IF EXISTS check_period_lock_journal();
DROP FUNCTION IF EXISTS check_period_lock_invoice();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('konto', '0007_accountingperiod'),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]
