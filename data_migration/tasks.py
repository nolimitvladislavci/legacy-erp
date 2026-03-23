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
    except Exception as e:
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
    except Exception as e:
        logger.warning("FENIX hook: AI kontekst greska: %s", e)


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
    except Exception:
        pass
    return None
