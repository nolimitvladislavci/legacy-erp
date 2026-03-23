"""
data_migration/tasks.py

Celery taskovi:
1. cleanup_stale_migrations — svaki sat brise stare projekte (24h)
2. run_migration — asinhroni import s inkrementalnim progress updateom
"""
import logging
import traceback

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def cleanup_stale_migrations():
    """
    Brise sve migracijske projekte i njihove datoteke starije od 24 sata,
    bez obzira na status. LIMIT Connect nije arhiva.
    """
    from .models import MigrationFile, MigrationProject

    now = timezone.now()

    # 1. Brisi sve istekle datoteke (expires_at < now)
    expired_files = MigrationFile.objects.filter(expires_at__lt=now)
    file_count = 0
    for mf in expired_files.iterator():
        mf.delete_file_from_disk()
        file_count += 1
    expired_files.delete()

    # 2. Brisi projekte starije od 24h (kaskadno brise Files i Logs)
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
            "cleanup_stale_migrations: obrisano %d projekata, %d datoteka.",
            project_count, file_count,
        )

    return {"projects_deleted": project_count, "files_deleted": file_count}


@shared_task
def run_migration(project_pk):
    """
    Pokrece import podataka u ERP bazu.

    Inkrementalno azurira project.processed_rows svakih 100 redova
    tako da frontend polling moze prikazati stvarni napredak.
    """
    from .adapters.base import get_adapter
    from .models import MigrationProject

    try:
        project = MigrationProject.objects.unscoped().get(pk=project_pk)
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

    try:
        adapter = get_adapter(mf.adapter_used)

        # Postavi kontekst za logging unutar adaptera
        adapter._current_project = project
        adapter._current_entity_type = project.entity_type

        # Postavi total_rows
        data = mf.extracted_data or []
        project.total_rows = len(data)
        project.save(update_fields=["total_rows"])

        # Pokreni import — adapter interno azurira progress svakih 100 redova
        result = adapter.execute_import(
            company=project.company,
            data=data,
            field_mapping=project.field_mapping,
            entity_type=project.entity_type,
            user=project.created_by,
        )

        # Finalni update
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

        # ── FENIX Auto-Activation: scan olakšica + bonitet ──────────
        try:
            from limit_connect_ai.tasks import fenix_post_import_scan
            fenix_post_import_scan.delay(str(project.company_id), str(project.pk))
            logger.info("[FENIX] Post-import scan triggered za company=%s", project.company_id)
        except Exception as fenix_err:
            logger.warning("[FENIX] Post-import trigger failed: %s", fenix_err)

    except Exception as e:
        logger.exception("run_migration: projekt %s FAILED: %s", project_pk, e)
        project.status = "failed"
        project.save(update_fields=["status"])

        # Zapisi error u MigrationLog
        from .models import MigrationLog
        MigrationLog.objects.create(
            project=project,
            level="error",
            message=f"Fatalna greska tijekom importa: {e}\n{traceback.format_exc()[:1000]}",
        )
