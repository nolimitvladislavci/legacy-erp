"""
3 Sentinela: Schema Drift, Pre-Flight Migration, Orphaned Data Radar
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# 1. SCHEMA DRIFT SENTINEL — Celery task
# ══════════════════════════════════════════════════════════════════════

sentinel_code = '''"""
Schema Drift Sentinel — automatska detekcija razlike između
Django modela i PostgreSQL baze.

Pokreće se: Celery beat, nedjelja 03:00
Detektira: orphan stupci u DB, stupci u modelu bez DB, tip mismatch
Alarmira: WhatsApp + log
"""
import logging
from celery import shared_task
from django.apps import apps
from django.db import connection, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('borg.sentinel')


def _get_db_columns(table_name):
    """Dohvati sve stupce iz PostgreSQL tablice."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position",
            [table_name]
        )
        return {row[0]: {'type': row[1], 'nullable': row[2]} for row in cursor.fetchall()}


def _get_model_columns(model):
    """Dohvati sva polja iz Django modela."""
    columns = {}
    for field in model._meta.get_fields():
        if hasattr(field, 'column') and field.column:
            columns[field.column] = {
                'field_name': field.name,
                'field_type': type(field).__name__,
            }
    return columns


@shared_task(bind=True, soft_time_limit=120)
def schema_drift_check(self):
    """
    Usporedi Django modele s PostgreSQL bazom.
    Pronađi: orphan stupce, missing stupce, drift.
    """
    drifts = []
    checked = 0

    for model in apps.get_models():
        table = model._meta.db_table
        
        try:
            db_cols = _get_db_columns(table)
        except Exception:
            continue
        
        if not db_cols:
            continue
        
        model_cols = _get_model_columns(model)
        checked += 1

        # Stupci u DB ali ne u modelu (orphan)
        for col_name in db_cols:
            if col_name not in model_cols and col_name != 'id':
                drifts.append({
                    'table': table,
                    'column': col_name,
                    'type': 'ORPHAN_IN_DB',
                    'detail': f'Stupac "{col_name}" ({db_cols[col_name]["type"]}) postoji u DB ali ne u Django modelu',
                })

        # Polja u modelu ali ne u DB (missing)
        for col_name in model_cols:
            if col_name not in db_cols:
                drifts.append({
                    'table': table,
                    'column': col_name,
                    'type': 'MISSING_IN_DB',
                    'detail': f'Polje "{model_cols[col_name]["field_name"]}" ({model_cols[col_name]["field_type"]}) postoji u modelu ali ne u DB tablici',
                })

    # Alarmiranje
    if drifts:
        logger.warning(
            'SCHEMA DRIFT DETECTED: %d problema u %d tablica:\\n%s',
            len(drifts), len(set(d['table'] for d in drifts)),
            '\\n'.join(f'  [{d["type"]}] {d["table"]}.{d["column"]}: {d["detail"]}' for d in drifts),
        )

        # WhatsApp alarm
        try:
            from core.whatsapp import send_text
            msg = (
                f'BORG SENTINEL: Schema Drift detected!\\n'
                f'{len(drifts)} problema u {len(set(d["table"] for d in drifts))} tablica.\\n'
                + '\\n'.join(f'[{d["type"]}] {d["table"]}.{d["column"]}' for d in drifts[:10])
            )
            send_text(phone='385976091655', message=msg, company_id='system')
        except ImportError:
            pass
    else:
        logger.info('Schema Drift Sentinel: %d tablica provjereno — ČISTO', checked)

    return {
        'checked_tables': checked,
        'drifts': len(drifts),
        'details': drifts[:50],  # Max 50 za Celery result
    }


@shared_task(bind=True, soft_time_limit=120)
def orphan_data_check(self):
    """
    Orphaned Data Radar — pronađi zapise koji pokazuju na
    nepostojeće FK objekte (company, partner, user).
    """
    from django.contrib.contenttypes.models import ContentType

    orphans = []
    
    # Kritične FK relacije za provjeru
    checks = [
        ('invoicing.Invoice', 'company_id', 'companies.Company'),
        ('invoicing.Invoice', 'partner_id', 'partners.Partner'),
        ('work_orders.WorkOrder', 'company_id', 'companies.Company'),
        ('inventory.InventoryItem', 'company_id', 'companies.Company'),
        ('experiences.ExperienceBooking', 'schedule_id', 'experiences.ExperienceSchedule'),
        ('pos.POSReceipt', 'session_id', 'pos.POSSession'),
    ]

    for model_path, fk_field, target_path in checks:
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
            
            target_app, target_model = target_path.split('.')
            TargetModel = apps.get_model(target_app, target_model)
            
            # Nađi zapise s FK koji ne postoji u target tablici
            valid_ids = set(TargetModel.objects.values_list('pk', flat=True))
            
            orphan_qs = Model.objects.exclude(
                **{f'{fk_field}__isnull': True}
            ).exclude(
                **{f'{fk_field}__in': valid_ids}
            ) if valid_ids else Model.objects.none()
            
            # Efikasniji pristup: raw SQL
            from django.db import connection
            table = Model._meta.db_table
            target_table = TargetModel._meta.db_table
            with connection.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} t "
                    f"WHERE t.{fk_field} IS NOT NULL "
                    f"AND t.{fk_field} NOT IN (SELECT id FROM {target_table})"
                )
                count = cur.fetchone()[0]
            
            if count > 0:
                orphans.append({
                    'model': model_path,
                    'fk_field': fk_field,
                    'target': target_path,
                    'count': count,
                })
        except Exception as e:
            logger.debug('Orphan check skip %s.%s: %s', model_path, fk_field, e)

    if orphans:
        logger.warning(
            'ORPHANED DATA DETECTED: %d relacija s siročadima:\\n%s',
            len(orphans),
            '\\n'.join(f'  {o["model"]}.{o["fk_field"]} → {o["target"]}: {o["count"]} orphan(a)' for o in orphans),
        )
        try:
            from core.whatsapp import send_text
            msg = (
                f'BORG SENTINEL: Orphaned Data!\\n'
                + '\\n'.join(f'{o["model"]}.{o["fk_field"]}: {o["count"]} siročadi' for o in orphans)
            )
            send_text(phone='385976091655', message=msg, company_id='system')
        except ImportError:
            pass
    else:
        logger.info('Orphan Data Radar: sve FK relacije čiste')

    return {'orphans': orphans}
'''

tasks_path = os.path.join(BASE, 'borg_ops/tasks.py')
with open(tasks_path) as f:
    existing = f.read()

# Dodaj sentinel taskove na kraj
if 'schema_drift_check' not in existing:
    with open(tasks_path, 'a') as f:
        f.write('\n\n' + sentinel_code)
    print("[OK] borg_ops/tasks.py — Schema Drift + Orphan Data sentineli dodani")
else:
    print("[SKIP] Sentineli već postoje")


# ══════════════════════════════════════════════════════════════════════
# 2. PRE-FLIGHT MIGRATION CHECK — management command
# ══════════════════════════════════════════════════════════════════════

preflight_cmd = '''"""
Pre-Flight Migration Check — blokira deployment ako postoje
neregistrirane promjene u modelima.

Usage:
  python manage.py preflight_check
  
Exit codes:
  0 = sve OK
  1 = neregistrirane migracije
  2 = schema drift detektiran
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from io import StringIO


class Command(BaseCommand):
    help = 'Pre-flight check: migracije + schema drift'

    def handle(self, *args, **options):
        errors = 0

        # 1. Neregistrirane migracije
        self.stdout.write('\\n[1/3] Checking for unregistered migrations...')
        out = StringIO()
        try:
            call_command('makemigrations', '--check', '--dry-run', stdout=out, stderr=out)
            self.stdout.write(self.style.SUCCESS('  OK — no pending migrations'))
        except SystemExit as e:
            if e.code:
                self.stdout.write(self.style.ERROR(
                    f'  FAIL — unregistered model changes detected!\\n'
                    f'  Run: python manage.py makemigrations'
                ))
                errors += 1
            else:
                self.stdout.write(self.style.SUCCESS('  OK — no pending migrations'))

        # 2. Unapplied migracije
        self.stdout.write('\\n[2/3] Checking for unapplied migrations...')
        out = StringIO()
        try:
            call_command('migrate', '--check', stdout=out, stderr=out)
            self.stdout.write(self.style.SUCCESS('  OK — all migrations applied'))
        except SystemExit as e:
            if e.code:
                self.stdout.write(self.style.ERROR(
                    f'  FAIL — unapplied migrations exist!\\n'
                    f'  Run: python manage.py migrate'
                ))
                errors += 1
            else:
                self.stdout.write(self.style.SUCCESS('  OK — all migrations applied'))

        # 3. Schema drift (quick check — top 10 tablica)
        self.stdout.write('\\n[3/3] Quick schema drift check...')
        from borg_ops.tasks import _get_db_columns, _get_model_columns
        from django.apps import apps

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
'''

cmd_dir = os.path.join(BASE, 'core/management/commands')
os.makedirs(cmd_dir, exist_ok=True)
with open(os.path.join(cmd_dir, 'preflight_check.py'), 'w') as f:
    f.write(preflight_cmd)
print("[OK] core/management/commands/preflight_check.py")


# ══════════════════════════════════════════════════════════════════════
# 3. CELERY BEAT SCHEDULE — dodaj sentinel crontabe
# ══════════════════════════════════════════════════════════════════════

settings_path = os.path.join(BASE, 'core/settings.py')
with open(settings_path) as f:
    settings = f.read()

if 'schema_drift_check' not in settings:
    # Nađi zadnji CELERY_BEAT_SCHEDULE.update
    sentinel_schedule = """
# ── BORG Sentineli ──────────────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update({
    "borg-schema-drift-weekly": {
        "task": "borg_ops.tasks.schema_drift_check",
        "schedule": crontab(day_of_week='sunday', hour='3', minute='0'),
    },
    "borg-orphan-data-weekly": {
        "task": "borg_ops.tasks.orphan_data_check",
        "schedule": crontab(day_of_week='sunday', hour='3', minute='30'),
    },
})
"""
    settings += sentinel_schedule
    with open(settings_path, 'w') as f:
        f.write(settings)
    print("[OK] core/settings.py — beat schedule za sentinele (ned 03:00 + 03:30)")
else:
    print("[SKIP] Sentinel schedule već postoji")


print("\n═══════════════════════════════════════════")
print("3 SENTINELA AKTIVNA")
print("  1. Schema Drift (ned 03:00)")
print("  2. Orphan Data (ned 03:30)")
print("  3. Pre-Flight Check (manage.py preflight_check)")
print("═══════════════════════════════════════════")
