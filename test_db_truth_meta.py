import os
import sys

sys.path.append('/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.db import connection

print("="*70)
print(" FINA-CONNECT CHAOS MONKEY - META TEST (POSTGRESQL INTROSPEKCIJA)")
print("="*70)

def verify_database_constraints():
    with connection.cursor() as cursor:
        # 1. Provjera fizičkih UNIQUE ograničenja
        cursor.execute("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'konto_journalentry' AND contype = 'u';
        """)
        unique_constraints = cursor.fetchall()

        print("\n[1] FIZIČKI UNIQUE CONSTRAINTS NA TABLICI 'konto_journalentry':")
        if unique_constraints:
            for name, definition in unique_constraints:
                print(f" ✅ Dokaz pronađen: {name} -> {definition}")
        else:
            print(" 🚨 FATALNO: Baza nema pojma o 'unique_together'.")
            print("    -> Migracija nije prošla ili je Django štiti samo u memoriji.")

        # 2. Provjera fizičkih CHECK ograničenja (Matematika)
        cursor.execute("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'konto_ledgerline' AND contype = 'c';
        """)
        check_constraints = cursor.fetchall()

        print("\n[2] FIZIČKI CHECK CONSTRAINTS NA TABLICI 'konto_ledgerline':")
        if check_constraints:
            for name, definition in check_constraints:
                print(f" ✅ Dokaz pronađen: {name} -> {definition}")
        else:
            print(" 🚨 FATALNO: Nema CHECK ograničenja za iznose.")

        # 3. Provjera PostgreSQL Triggera (Matematički balans cijele temeljnice)
        cursor.execute("""
            SELECT tgname, pg_get_triggerdef(pg_trigger.oid)
            FROM pg_trigger
            JOIN pg_class ON pg_trigger.tgrelid = pg_class.oid
            WHERE relname = 'konto_ledgerline' AND tgisinternal = false;
        """)
        triggers = cursor.fetchall()

        print("\n[3] POSTGRESQL TRIGGERS ZA VALIDACIJU BALANSA (Duguje = Potražuje):")
        if triggers:
            for t in triggers:
                print(f" ✅ Dokaz pronađen (Trigger): {t[0]}")
        else:
            print(" 🚨 FATALNO: Baza nema SQL Trigger koji zbraja Duguje i Potražuje!")
            print("    -> Bilo koji alat koji pristupa bazi direktno može upisati razliku.")
            print("    -> Python 'clean()' metoda je trenutno jedina, vrlo krhka linija obrane.")

if __name__ == "__main__":
    verify_database_constraints()
    print("="*70)
