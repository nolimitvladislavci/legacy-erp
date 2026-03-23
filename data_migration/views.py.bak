"""
data_migration/views.py

State Machine views za migraciju podataka.
Striktno preusmjeravanje — korisnik NE MOŽE preskakati korake.

Flow: upload → mapping → preview → execute (AJAX)
"""
import logging
import os
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .adapters.base import detect_adapter, get_adapter
from .models import MigrationFile, MigrationLog, MigrationProject

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.json', '.xml'}


@login_required
def project_list(request):
    """Lista migracijskih projekata za tvrtku."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('core:dashboard')

    projects = MigrationProject.objects.filter(
        company=company,
    ).order_by('-created_at')[:50]

    return render(request, 'data_migration/project_list.html', {
        'projects': projects,
        'company': company,
    })


@login_required
def upload_migration_file(request):
    """Korak 1: Upload datoteke i kreiranje DRAFT projekta."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, 'Molimo odaberite datoteku.')
            return render(request, 'data_migration/upload.html', {'company': company})

        # Validacija
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(request, f'Format {ext} nije podržan. Dozvoljeni: {", ".join(ALLOWED_EXTENSIONS)}')
            return render(request, 'data_migration/upload.html', {'company': company})

        if uploaded.size > MAX_FILE_SIZE:
            messages.error(request, f'Datoteka prevelika ({uploaded.size // 1024 // 1024} MB). Max: 50 MB.')
            return render(request, 'data_migration/upload.html', {'company': company})

        # Entity type
        entity_type = request.POST.get('entity_type', 'mixed')
        source_program = request.POST.get('source_program', '')
        project_name = request.POST.get('name', '') or f'Import {uploaded.name}'

        # Kreiraj projekt
        project = MigrationProject.objects.create(
            company=company,
            name=project_name[:200],
            source_program=source_program[:100],
            entity_type=entity_type,
            status='draft',
            created_by=request.user,
        )

        # Format detekcija
        format_map = {
            '.csv': 'csv', '.xlsx': 'xlsx', '.xls': 'xls',
            '.json': 'json', '.xml': 'xml',
        }

        migration_file = MigrationFile.objects.create(
            project=project,
            file=uploaded,
            original_filename=uploaded.name[:255],
            file_format=format_map.get(ext, 'other'),
            file_size=uploaded.size,
        )

        # Auto-detect adapter i extract
        try:
            adapter = detect_adapter(migration_file.file.path, migration_file.file_format)
            if adapter:
                migration_file.adapter_used = adapter.name
                raw_data = adapter.extract_raw_data(migration_file.file.path)
                migration_file.detected_columns = adapter.get_detected_columns(raw_data)
                migration_file.row_count = len(raw_data)
                # Spremi samo prvih 200 redova u extracted_data (za preview)
                migration_file.extracted_data = raw_data[:200]
                migration_file.save(update_fields=[
                    'adapter_used', 'detected_columns', 'row_count', 'extracted_data',
                ])

                MigrationLog.objects.create(
                    project=project, level='info',
                    message=f'Datoteka učitana: {uploaded.name} ({len(raw_data)} redova, '
                            f'{len(migration_file.detected_columns)} kolona, adapter: {adapter.name})',
                )
            else:
                MigrationLog.objects.create(
                    project=project, level='warning',
                    message=f'Nije pronađen adapter za {uploaded.name} — ručno mapiranje potrebno.',
                )
        except Exception as e:
            logger.error('Extract error for %s: %s', uploaded.name, e)
            MigrationLog.objects.create(
                project=project, level='error',
                message=f'Greška pri čitanju datoteke: {str(e)[:200]}',
            )

        return redirect('data_migration:mapping', project_id=project.pk)

    return render(request, 'data_migration/upload.html', {'company': company})


@login_required
def mapping_view(request, project_id):
    """Korak 2: Povezivanje CSV kolona s ERP poljima."""
    company = get_user_company(request)
    project = get_object_or_404(MigrationProject, pk=project_id, company=company)

    # State Machine — samo draft ili mapped mogu mapirati
    if project.status not in ('draft', 'mapped'):
        return redirect('data_migration:preview', project_id=project.pk)

    migration_file = project.files.first()
    if not migration_file:
        messages.error(request, 'Nema uploadane datoteke.')
        return redirect('data_migration:upload')

    # Dohvati adapter
    adapter_name = migration_file.adapter_used or 'csv_generic'
    try:
        adapter = get_adapter(adapter_name)
    except KeyError:
        adapter = get_adapter('csv_generic')

    schema = adapter.get_mapping_schema(project.entity_type)
    detected_columns = migration_file.detected_columns or []
    sample_data = (migration_file.extracted_data or [])[:5]

    if request.method == 'POST':
        # Spremi mapiranje
        mapping = {}
        for col in detected_columns:
            erp_field = request.POST.get(f'map_{col}', '')
            if erp_field:
                mapping[col] = erp_field

        project.field_mapping = mapping
        project.save(update_fields=['field_mapping'])

        # Validacija mapiranja
        errors = adapter.validate_mapping(mapping, project.entity_type)
        if errors:
            for err in errors:
                messages.warning(request, err)
            return render(request, 'data_migration/mapping.html', {
                'project': project,
                'schema': schema,
                'detected_columns': detected_columns,
                'sample_data': sample_data,
                'current_mapping': mapping,
                'company': company,
            })

        # Generiraj preview
        raw_data = migration_file.extracted_data or []
        mapped_preview = adapter.apply_mapping(raw_data[:50], mapping)
        project.preview_data = mapped_preview
        project.status = 'mapped'
        project.save(update_fields=['status', 'preview_data'])

        MigrationLog.objects.create(
            project=project, level='info',
            message=f'Mapiranje spremljeno: {len(mapping)} polja.',
        )

        return redirect('data_migration:preview', project_id=project.pk)

    return render(request, 'data_migration/mapping.html', {
        'project': project,
        'schema': schema,
        'detected_columns': detected_columns,
        'sample_data': sample_data,
        'current_mapping': project.field_mapping or {},
        'company': company,
    })


@login_required
def preview_view(request, project_id):
    """Korak 3: Pregled mapiranih podataka prije importa."""
    company = get_user_company(request)
    project = get_object_or_404(MigrationProject, pk=project_id, company=company)

    # State Machine
    if project.status == 'draft':
        return redirect('data_migration:mapping', project_id=project.pk)
    if project.status == 'completed':
        messages.info(request, 'Ovaj import je već završen.')
        return redirect('data_migration:project_list')

    preview_data = project.preview_data or []
    migration_file = project.files.first()

    return render(request, 'data_migration/preview.html', {
        'project': project,
        'preview_data': preview_data[:50],
        'total_rows': migration_file.row_count if migration_file else len(preview_data),
        'company': company,
    })


@login_required
@require_POST
def execute_import(request, project_id):
    """Korak 4: Stvarni uvoz. AJAX — vraća JSON."""
    company = get_user_company(request)
    project = get_object_or_404(MigrationProject, pk=project_id, company=company)

    if project.status not in ('mapped', 'preview'):
        return JsonResponse({
            'success': False,
            'message': 'Projekt nije spreman za import.',
        }, status=400)

    project.status = 'importing'
    project.save(update_fields=['status'])

    migration_file = project.files.first()
    if not migration_file:
        project.status = 'failed'
        project.save(update_fields=['status'])
        return JsonResponse({
            'success': False, 'message': 'Nema datoteke za import.',
        }, status=400)

    try:
        # Dohvati adapter
        adapter_name = migration_file.adapter_used or 'csv_generic'
        try:
            adapter = get_adapter(adapter_name)
        except KeyError:
            adapter = get_adapter('csv_generic')

        # Puni extract (ne samo 200 redova iz previewa)
        raw_data = adapter.extract_raw_data(migration_file.file.path)
        mapped_data = adapter.apply_mapping(raw_data, project.field_mapping)

        result = adapter.execute_import(
            company=company,
            data=mapped_data,
            field_mapping=project.field_mapping,
            entity_type=project.entity_type,
            user=request.user,
        )

        project.records_created = result.created
        project.records_updated = result.updated
        project.records_skipped = result.skipped
        project.records_failed = result.failed
        project.status = 'completed'
        project.completed_at = timezone.now()
        project.save(update_fields=[
            'records_created', 'records_updated', 'records_skipped',
            'records_failed', 'status', 'completed_at',
        ])

        # Spremi greške u log
        for err in result.errors[:100]:
            MigrationLog.objects.create(
                project=project,
                level='error',
                row_number=err.get('row'),
                field_name=err.get('field', ''),
                message=err.get('message', ''),
                original_value=err.get('value', ''),
            )

        MigrationLog.objects.create(
            project=project, level='info',
            message=(
                f'Import završen: {result.created} kreirano, {result.updated} ažurirano, '
                f'{result.skipped} preskočeno, {result.failed} neuspjelo.'
            ),
        )

        return JsonResponse({
            'success': True,
            'message': (
                f'Import završen! {result.created} kreirano, '
                f'{result.updated} ažurirano, {result.skipped} preskočeno.'
            ),
            'created': result.created,
            'updated': result.updated,
            'skipped': result.skipped,
            'failed': result.failed,
            'redirect_url': '/data-migration/',
        })

    except Exception as e:
        logger.error('Import execution error: %s', e, exc_info=True)
        project.status = 'failed'
        project.save(update_fields=['status'])
        MigrationLog.objects.create(
            project=project, level='error',
            message=f'Kritična greška: {str(e)[:300]}',
        )
        return JsonResponse({
            'success': False,
            'message': f'Greška pri importu: {str(e)[:200]}',
        }, status=500)


@login_required
def import_status(request, project_id):
    """API za polling statusa importa."""
    company = get_user_company(request)
    project = get_object_or_404(MigrationProject, pk=project_id, company=company)

    logs = list(project.logs.order_by('-created_at')[:10].values(
        'level', 'message', 'row_number', 'created_at',
    ))

    return JsonResponse({
        'status': project.status,
        'status_display': project.get_status_display(),
        'created': project.records_created,
        'updated': project.records_updated,
        'skipped': project.records_skipped,
        'failed': project.records_failed,
        'logs': logs,
    })
