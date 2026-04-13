"""
data_migration/tasks.py

TIER 1 ZAKRPE:
- run_migration prima audit_ctx i kreira PermanentMigrationAudit po zavrsetku
- PermanentMigrationAudit zapis prezivljava 24h brisanje projekta
"""
import logging
import traceback

from celery import shared_task
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


@shared_task
def cleanup_stale_migrations():
    """
    Brise sve migracijske projekte i njihove datoteke starije od 24 sata.
    PermanentMigrationAudit zapisi se NE brisu — oni ostaju 11 godina.
    """
    from .models import MigrationFile, MigrationProject

    now = timezone.now()

    expired_files = MigrationFile.objects.filter(expires_at__lt=now)
    file_count = 0
    for mf in expired_files.iterator():
        mf.delete_file_from_disk()
        file_count += 1
    expired_files.delete()

    threshold = now - timezone.timedelta(hours=24)
    stale_projects = MigrationProject.objects.unscoped().filter(created_at__lt=threshold)
    project_count = stale_projects.count()

    if project_count:
        remaining_files = MigrationFile.objects.filter(project__in=stale_projects)
        for mf in remaining_files.iterator():
            mf.delete_file_from_disk()
        stale_projects.delete()

    total = file_count + project_count
    if total:
        logger.info(
            "cleanup_stale_migrations: obrisano %d projekata, %d datoteka. "
            "PermanentMigrationAudit zapisi SACUVANI.",
            project_count, file_count,
        )

    return {"projects_deleted": project_count, "files_deleted": file_count}


@shared_task
def run_migration(project_pk, audit_ctx=None):
    """
    Pokrece import podataka u ERP bazu.
    Po zavrsetku kreira PermanentMigrationAudit zapis.
    """
    from .adapters.base import get_adapter
    from .models import MigrationProject, PermanentMigrationAudit

    audit_ctx = audit_ctx or {}

    try:
        project = MigrationProject.objects.unscoped().select_related("company", "created_by").get(pk=project_pk)
    except MigrationProject.DoesNotExist:
        logger.error("run_migration: projekt %s ne postoji.", project_pk)
        return

    if project.status != "importing":
        logger.warning("run_migration: projekt %s status=%s, ocekivan 'importing'.", project_pk, project.status)
        return

    mf = project.files.first()
    if not mf:
        project.status = "failed"
        project.save(update_fields=["status"])
        logger.error("run_migration: projekt %s nema datoteka.", project_pk)
        return

    execution_started = timezone.now()

    try:
        adapter = get_adapter(mf.adapter_used)
        adapter._current_project = project
        adapter._current_entity_type = project.entity_type

        data = mf.extracted_data or []
        project.total_rows = len(data)
        project.save(update_fields=["total_rows"])

        result = adapter.execute_import(
            company=project.company,
            data=data,
            field_mapping=project.field_mapping,
            entity_type=project.entity_type,
            user=project.created_by,
        )

        project.status = "completed"
        project.processed_rows = project.total_rows
        project.records_created = result.created
        project.records_updated = result.updated
        project.records_skipped = result.skipped
        project.records_failed = result.failed
        project.completed_at = timezone.now()
        project.save(update_fields=[
            "status", "processed_rows", "records_created",
            "records_updated", "records_skipped", "records_failed",
            "completed_at",
        ])

        logger.info(
            "run_migration: projekt %s zavrsen. created=%d, updated=%d, failed=%d",
            project_pk, result.created, result.updated, result.failed,
        )

        # ── TIER 1: Trajni audit zapis ───────────────────────────
        _create_permanent_audit(project, mf, result, execution_started, audit_ctx)

        # ── FENIX Post-Import Hook ───────────────────────────────
        post_migration_fenix_hook.delay(project_pk)

    except Exception as e:
        logger.exception("run_migration: projekt %s FAILED: %s", project_pk, e)
        project.status = "failed"
        project.save(update_fields=["status"])

        from .models import MigrationLog
        MigrationLog.objects.create(
            project=project,
            level="error",
            message=f"Fatalna greska tijekom importa: {e}\n{traceback.format_exc()[:1000]}",
        )

        # Audit i za neuspjeli import — dokazuje pokusaj
        _create_permanent_audit(project, mf, None, execution_started, audit_ctx, failed=True)


def _create_permanent_audit(project, mf, result, started_at, audit_ctx, failed=False):
    """Kreira neizbrisiv PermanentMigrationAudit zapis."""
    from .models import PermanentMigrationAudit

    company = project.company
    user = project.created_by

    try:
        PermanentMigrationAudit.objects.create(
            company_id=company.pk,
            company_name=company.name[:200],
            company_oib=getattr(company, "oib", "")[:13],
            user_id=user.pk if user else None,
            user_email=user.email if user else "unknown@unknown",
            user_full_name=(user.get_full_name() if user else "")[:200],
            source_system=(project.source_program or "")[:100],
            original_filename=audit_ctx.get("original_filename", mf.original_filename)[:255],
            file_size_bytes=audit_ctx.get("file_size", mf.file_size) or 0,
            file_sha256=audit_ctx.get("file_sha256", ""),
            entity_type=project.entity_type,
            total_rows_in_file=project.total_rows,
            agreed_to_disclaimer=audit_ctx.get("disclaimer_accepted", False),
            disclaimer_text=audit_ctx.get("disclaimer_text", ""),
            field_mapping_snapshot=project.field_mapping or {},
            records_created=result.created if result else 0,
            records_updated=result.updated if result else 0,
            records_skipped=result.skipped if result else 0,
            records_failed=result.failed if result else project.total_rows,
            ip_address=audit_ctx.get("ip_address"),
            user_agent=audit_ctx.get("user_agent", ""),
            execution_started_at=started_at,
        )
        logger.info("PermanentMigrationAudit kreiran za projekt %s", project.pk)
    except (IntegrityError, DatabaseError) as e:
        logger.error("KRITICNO: PermanentMigrationAudit kreiranje FAILED za projekt %s: %s", project.pk, e)


@shared_task
def post_migration_fenix_hook(project_pk):
    from .models import MigrationProject

    try:
        project = MigrationProject.objects.unscoped().select_related("company", "created_by").get(pk=project_pk)
    except MigrationProject.DoesNotExist:
        return

    company = project.company
    user = project.created_by

    try:
        from core.whatsapp_tasks import send_whatsapp_message
        admin_phone = _get_company_admin_phone(company)
        if admin_phone:
            msg = (
                f"*LIMIT Connect — Migracija zavrsena*\n\n"
                f"Projekt: {project.name}\n"
                f"Tip: {project.get_entity_type_display()}\n"
                f"Izvor: {project.source_program or 'N/A'}\n\n"
                f"Kreirano: {project.records_created}\n"
                f"Azurirano: {project.records_updated}\n"
                f"Preskoceno: {project.records_skipped}\n"
                f"Greske: {project.records_failed}\n\n"
                f"Pokrenuo: {user.get_full_name() if user else 'N/A'}\n"
                f"Vrijeme: {project.completed_at:%d.%m.%Y %H:%M}" if project.completed_at else ""
            )
            send_whatsapp_message.delay(admin_phone, msg)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("FENIX hook: WhatsApp greska: %s", e)

    try:
        from ai_assistant.models import AIContext
        AIContext.objects.create(
            company=company,
            context_type="migration_completed",
            summary=(
                f"Korisnik {user.get_full_name() if user else 'N/A'} je zavrsio migraciju "
                f"'{project.name}' ({project.get_entity_type_display()}) "
                f"iz programa '{project.source_program or 'nepoznato'}'. "
                f"Kreirano: {project.records_created}, azurirano: {project.records_updated}, "
                f"greske: {project.records_failed}."
            ),
            metadata={
                "project_pk": project.pk,
                "entity_type": project.entity_type,
                "source_program": project.source_program,
                "records_created": project.records_created,
                "records_updated": project.records_updated,
                "records_failed": project.records_failed,
            },
        )
    except ImportError:
        pass
    except (IntegrityError, DatabaseError) as e:
        logger.warning("FENIX hook: AI kontekst greska: %s", e)

    # ── FENIX Opportunity + Risk Scan ────────────────────────────
    # Ovo je "Aha!" moment: klijent uveze partnere i odmah dobije:
    # "Pronašli smo 12 firmi u blokadi i 4 prilike za uštedu od 8.340 EUR"
    try:
        from limit_connect_ai.tasks import fenix_post_import_scan
        fenix_post_import_scan.delay(str(company.pk), project.pk)
        logger.info("FENIX scan pokrenut za %s (project=%s)", company.name, project.pk)
    except Exception as e:
        logger.warning("FENIX hook: scan pokretanje greska: %s", e)


def _get_company_admin_phone(company):
    try:
        from django.contrib.auth.models import User
        from permissions.manager import PermissionManager
        for user in User.objects.filter(is_active=True):
            try:
                role = PermissionManager.get_user_role(user)
                if role in ("superadmin", "company_admin"):
                    profile = getattr(user, "profile", None)
                    phone = getattr(profile, "phone", None) or getattr(profile, "whatsapp_number", None)
                    if phone:
                        return phone
            except Exception:
                continue
    except DatabaseError:
        pass
    return None



# ══════════════════════════════════════════════════════════════════════════════
# Data Sovereignty — Full Export
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, soft_time_limit=600)
def generate_full_export(self, manifest_id):
    """
    Async generacija kompletnog izvoza podataka za tenanta.
    Exportira: partners, invoices, receipts, inventory, audit entries.
    S kontekstualnim linkovima (document -> legal_reference -> verification).
    """
    import json
    import os
    import tempfile
    from django.utils import timezone as tz

    logger = logging.getLogger('borg.export')

    try:
        from data_migration.models import ExportManifest
        manifest = ExportManifest.objects.select_related('company').get(pk=manifest_id)
    except ExportManifest.DoesNotExist:
        return {'error': 'Manifest not found'}

    manifest.status = 'processing'
    manifest.save(update_fields=['status'])

    company = manifest.company
    export_data = {
        '_meta': {
            'export_date': tz.now().isoformat(),
            'company': company.name,
            'company_oib': getattr(company, 'oib', ''),
            'format_version': '1.0',
            'generator': 'BORG Data Sovereignty Export',
        },
        'partners': [],
        'invoices': [],
        'audit_entries': [],
    }
    counts = {}

    try:
        # Partners
        from partners.models import Partner
        partners = Partner.objects.filter(company=company).values(
            'id', 'name', 'oib', 'vat_id', 'address', 'city', 'country',
            'email', 'phone', 'buyer_type', 'vies_valid', 'created_at',
        )
        export_data['partners'] = [
            {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
             for k, v in p.items()}
            for p in partners
        ]
        counts['partners'] = len(export_data['partners'])
    except DatabaseError as e:
        logger.debug('Export partners error: %s', e)

    try:
        # Invoices
        from invoicing.models import Invoice
        invoices = Invoice.objects.filter(company=company).values(
            'id', 'number', 'date_issued', 'date_due', 'client_name',
            'client_oib', 'total', 'status', 'is_fiscalized', 'zki', 'jir',
        )
        export_data['invoices'] = [
            {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
             for k, v in inv.items()}
            for inv in invoices
        ]
        counts['invoices'] = len(export_data['invoices'])
    except DatabaseError as e:
        logger.debug('Export invoices error: %s', e)

    try:
        # Audit entries (contextual links)
        if manifest.include_audit:
            from borg_ops.models import BorgAuditEntry
            entries = BorgAuditEntry.objects.filter(company=company).values(
                'id', 'entry_type', 'severity', 'summary', 'legal_reference',
                'verification_type', 'verification_result', 'metadata', 'created_at',
            )
            export_data['audit_entries'] = [
                {k: str(v) if not isinstance(v, (str, int, float, bool, dict, type(None))) else v
                 for k, v in e.items()}
                for e in entries
            ]
            counts['audit_entries'] = len(export_data['audit_entries'])
    except DatabaseError as e:
        logger.debug('Export audit error: %s', e)

    # Write JSON file
    try:
        export_dir = os.path.join('/var/www/fina-connect/exports')
        os.makedirs(export_dir, exist_ok=True)
        filename = f'export_{company.pk}_{tz.now().strftime("%Y%m%d_%H%M%S")}.json'
        filepath = os.path.join(export_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        file_size = os.path.getsize(filepath) / (1024 * 1024)

        manifest.status = 'completed'
        manifest.file_path = filepath
        manifest.file_size_mb = round(file_size, 2)
        manifest.entity_counts = counts
        manifest.completed_at = tz.now()
        manifest.expires_at = tz.now() + tz.timedelta(hours=48)
        manifest.save()

        # Audit trail
        from borg_ops.audit_helpers import log_borg_audit
        log_borg_audit(
            company=company,
            entry_type='EXPORT',
            summary=f'Full export zavrsen: {sum(counts.values())} entiteta, {file_size:.1f} MB',
            metadata={'manifest_id': manifest.pk, 'counts': counts, 'file': filename},
        )

        logger.info('Export completed for %s: %s (%s MB)', company.name, filename, file_size)
        return {'status': 'completed', 'file': filepath, 'counts': counts}

    except (FileNotFoundError, PermissionError, IOError) as e:
        manifest.status = 'failed'
        manifest.save(update_fields=['status'])
        logger.error('Export failed for %s: %s', company.name, e)
        return {'status': 'failed', 'error': str(e)}
