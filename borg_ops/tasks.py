"""
BORG SLA Engine — Celery tasks za detekciju SLA kršenja.

check_sla: svakih 10 min provjerava kartice koje predugo stoje u statusu.
archive_old_activity: mjesečno broji stare zapise (arhiva u v2).
"""
import logging
from celery import shared_task
from borg_ops.business_hours import sla_breached, is_business_hour
from django.utils import timezone

logger = logging.getLogger('borg.sla')

SLA_RULES = {
    'work_orders.WorkOrder': {
        'in_progress': 480,     # 8h
    },
    'burza.ProjectLead': {
        'NOVI_UPIT':        1440,   # 24h
        'INTERNA_PROCJENA': 4320,   # 72h
        'NA_BURZI':         10080,  # 7 dana
    },
    'interventions.HitnaIntervencija': {
        'NOVO':        15,    # 15 min
        'DODIJELJENO': 30,    # 30 min
        'NA_PUTU':     60,    # 1h
    },
}


@shared_task(name='borg_ops.check_sla')
def check_sla():
    """Celery beat: svakih 10 min — SLA breach detekcija."""
    from borg_ops.models import StatusTimestamp
    from django.contrib.contenttypes.models import ContentType
    from django.apps import apps

    now = timezone.now()
    breaches = []

    for model_path, rules in SLA_RULES.items():
        app_label, model_name = model_path.split('.')
        try:
            Model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        ct = ContentType.objects.get_for_model(Model)

        for status, max_minutes in rules.items():
            # Dron #2 fix: ne alarmiramo van radnog vremena (vikend/praznik)
            if not is_business_hour():
                continue

            cutoff = now - timezone.timedelta(minutes=max_minutes)
            candidates = StatusTimestamp.objects.filter(
                content_type=ct,
                status=status,
                exited_at__isnull=True,
                entered_at__lt=cutoff,
            ).select_related('user')

            for ts in candidates:
                # Računaj RADNE minute — ne ukupno proteklo vrijeme
                breached, elapsed = sla_breached(ts.entered_at, max_minutes)
                if not breached:
                    continue   # Ukupno radno vrijeme još nije premašeno

                logger.warning(
                    'SLA BREACH: %s #%s u statusu %s — %d radnih min (max %d)',
                    model_name, ts.object_id, status, elapsed, max_minutes
                )
                breaches.append({
                    'model': model_name,
                    'pk': ts.object_id,
                    'status': status,
                    'minutes': elapsed,
                    'max': max_minutes,
                })

    if breaches:
        logger.warning('SLA check: %d breach(es) detected', len(breaches))

    return {
        'checked_at': now.isoformat(),
        'breaches': len(breaches),
        'details': breaches[:20],
    }


@shared_task(name='borg_ops.archive_old_activity')
def archive_old_activity():
    """Mjesecno: broji aktivnosti starije od 90 dana (arhiva u v2)."""
    from borg_ops.models import CardActivity
    cutoff = timezone.now() - timezone.timedelta(days=90)
    count = CardActivity.objects.filter(created_at__lt=cutoff).count()
    logger.info('CardActivity: %d zapisa starijih od 90 dana', count)
    return {'old_records': count}


"""
Schema Drift Sentinel — automatska detekcija razlike između
Django modela i PostgreSQL baze.

Pokreće se: Celery beat, nedjelja 03:00
Detektira: orphan stupci u DB, stupci u modelu bez DB, tip mismatch
Alarmira: WhatsApp + log
"""
import logging
from celery import shared_task
from django.apps import apps
from django.db import connection

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
        # Skip M2M i reverse relacije — nemaju stupac u tablici
        if field.many_to_many or field.one_to_many:
            continue
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
            'SCHEMA DRIFT DETECTED: %d problema u %d tablica:\n%s',
            len(drifts), len(set(d['table'] for d in drifts)),
            '\n'.join(f'  [{d["type"]}] {d["table"]}.{d["column"]}: {d["detail"]}' for d in drifts),
        )

        # WhatsApp alarm
        try:
            from core.whatsapp import send_text
            msg = (
                f'BORG SENTINEL: Schema Drift detected!\n'
                f'{len(drifts)} problema u {len(set(d["table"] for d in drifts))} tablica.\n'
                + '\n'.join(f'[{d["type"]}] {d["table"]}.{d["column"]}' for d in drifts[:10])
            )
            send_text(phone='385976091655', message=msg, company_id='system')
        except Exception:
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
            'ORPHANED DATA DETECTED: %d relacija s siročadima:\n%s',
            len(orphans),
            '\n'.join(f'  {o["model"]}.{o["fk_field"]} → {o["target"]}: {o["count"]} orphan(a)' for o in orphans),
        )
        try:
            from core.whatsapp import send_text
            msg = (
                f'BORG SENTINEL: Orphaned Data!\n'
                + '\n'.join(f'{o["model"]}.{o["fk_field"]}: {o["count"]} siročadi' for o in orphans)
            )
            send_text(phone='385976091655', message=msg, company_id='system')
        except Exception:
            pass
    else:
        logger.info('Orphan Data Radar: sve FK relacije čiste')

    return {'orphans': orphans}
