"""
Pre-Flight Migration Check — blokira deployment ako postoje
neregistrirane promjene u modelima.

Usage:
  python manage.py preflight_check
  
Exit codes:
  0 = sve OK
  1 = neregistrirane migracije
  2 = schema drift detektiran
"""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-flight check: migracije + schema drift'

    def handle(self, *args, **options):
        errors = 0

        # 1. Neregistrirane migracije
        self.stdout.write('\n[1/3] Checking for unregistered migrations...')
        out = StringIO()
        try:
            call_command('makemigrations', '--check', '--dry-run', stdout=out, stderr=out)
            self.stdout.write(self.style.SUCCESS('  OK — no pending migrations'))
        except SystemExit as e:
            if e.code:
                self.stdout.write(self.style.ERROR(
                    '  FAIL — unregistered model changes detected!\n'
                    '  Run: python manage.py makemigrations'
                ))
                errors += 1
            else:
                self.stdout.write(self.style.SUCCESS('  OK — no pending migrations'))

        # 2. Unapplied migracije
        self.stdout.write('\n[2/3] Checking for unapplied migrations...')
        out = StringIO()
        try:
            call_command('migrate', '--check', stdout=out, stderr=out)
            self.stdout.write(self.style.SUCCESS('  OK — all migrations applied'))
        except SystemExit as e:
            if e.code:
                self.stdout.write(self.style.ERROR(
                    '  FAIL — unapplied migrations exist!\n'
                    '  Run: python manage.py migrate'
                ))
                errors += 1
            else:
                self.stdout.write(self.style.SUCCESS('  OK — all migrations applied'))

        # 3. Schema drift (quick check — top 10 tablica)
        self.stdout.write('\n[3/3] Quick schema drift check...')
        from django.apps import apps

        from borg_ops.tasks import _get_db_columns, _get_model_columns

        drift_count = 0
        for model in list(apps.get_models())[:50]:
            table = model._meta.db_table
            try:
                db_cols = _get_db_columns(table)
                model_cols = _get_model_columns(model)

                orphans = set(db_cols.keys()) - set(model_cols.keys()) - {'id'}
                missing = set(model_cols.keys()) - set(db_cols.keys())

                if orphans:
                    self.stdout.write(self.style.WARNING(
                        f'  DRIFT: {table} has {len(orphans)} orphan DB column(s): {", ".join(orphans)}'
                    ))
                    drift_count += len(orphans)
                if missing:
                    self.stdout.write(self.style.ERROR(
                        f'  DRIFT: {table} missing {len(missing)} DB column(s): {", ".join(missing)}'
                    ))
                    drift_count += len(missing)
            except TypeError:
                pass

        if drift_count:
            self.stdout.write(self.style.WARNING(f'  {drift_count} schema drift(s) detected'))
        else:
            self.stdout.write(self.style.SUCCESS('  OK — no schema drift'))

        # Summary
        self.stdout.write('')
        if errors:
            self.stdout.write(self.style.ERROR(f'PRE-FLIGHT FAILED: {errors} blocker(s)'))
            raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS('PRE-FLIGHT PASSED — safe to deploy'))
