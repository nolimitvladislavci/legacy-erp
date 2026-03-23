"""
data_migration/views.py

Strict state machine flow:
    upload → mapping → preview → execute → result

Pravila:
- Svaki view provjerava project.status i redirecta na ispravan korak
- mapping_view dozvoljava draft I mapped (korisnik se moze vratiti)
- AJAX endpointi vracaju JSON
- Partial save mapiranja (ne gubi se rad)
"""
import json
import logging
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.company_utils import get_user_company

from .adapters.base import detect_adapter, get_adapter, get_all_adapters
from .models import MigrationFile, MigrationLog, MigrationProject

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────

# Dozvoljeni statusi po viewu + redirect destinacija za krivi status
_STATE_RULES = {
    "mapping":  {"allowed": {"draft", "mapped"},    "fallback": "data_migration:upload"},
    "preview":  {"allowed": {"mapped"},             "fallback": "data_migration:mapping"},
    "execute":  {"allowed": {"preview"},            "fallback": "data_migration:preview"},
    "result":   {"allowed": {"completed", "failed"}, "fallback": None},
}


def _get_project(request, pk):
    """Dohvaca projekt uz company scope provjeru."""
    company = get_user_company(request)
    return get_object_or_404(
        MigrationProject.objects.unscoped().filter(company=company),
        pk=pk,
    )


def _check_state(request, project, view_name):
    """
    Provjerava je li projekt u dozvoljenom statusu za dani view.
    Vraca None ako je OK, ili HttpResponseRedirect ako treba redirectat.
    """
    rules = _STATE_RULES.get(view_name)
    if not rules:
        return None
    if project.status in rules["allowed"]:
        return None

    # Odredi kuda redirectat na temelju aktualnog statusa
    status_to_view = {
        "draft":     "data_migration:mapping",
        "mapped":    "data_migration:mapping",
        "preview":   "data_migration:preview",
        "importing": "data_migration:status",
        "completed": "data_migration:result",
        "failed":    "data_migration:result",
    }
    target = status_to_view.get(project.status, rules["fallback"])
    if target and ":" in target:
        return redirect(target, pk=project.pk)
    return redirect("data_migration:dashboard")


def _get_primary_file(project):
    """Vraca prvu (glavnu) datoteku projekta."""
    return project.files.first()


def _detect_format_from_ext(filename):
    """Detektira format iz ekstenzije."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    format_map = {
        "csv": "csv", "xlsx": "xlsx", "xls": "xls",
        "json": "json", "xml": "xml", "mdb": "mdb",
    }
    return format_map.get(ext, "other")


# ── Dashboard ─────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Lista svih migracijskih projekata za tvrtku."""
    company = get_user_company(request)
    projects = MigrationProject.objects.filter(company=company)
    return render(request, "data_migration/dashboard.html", {
        "projects": projects,
        "adapters": get_all_adapters(),
    })


# ── Step 1: Upload ────────────────────────────────────────────────

@login_required
def upload_view(request):
    """Upload datoteke + kreiranje projekta."""
    company = get_user_company(request)

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return render(request, "data_migration/upload.html", {
                "error": "Odaberite datoteku za uvoz.",
            })

        name = request.POST.get("name", "").strip()
        if not name:
            name = f"Import — {uploaded_file.name}"

        entity_type = request.POST.get("entity_type", "partners")
        source_program = request.POST.get("source_program", "").strip()

        # Kreiraj projekt
        project = MigrationProject.objects.create(
            company=company,
            name=name[:200],
            source_program=source_program[:100],
            entity_type=entity_type,
            status="draft",
            created_by=request.user,
        )

        # Detektiraj format
        file_format = _detect_format_from_ext(uploaded_file.name)

        # Spremi datoteku
        mf = MigrationFile(
            project=project,
            original_filename=uploaded_file.name[:255],
            file_format=file_format,
        )
        mf.file.save(uploaded_file.name, uploaded_file, save=False)
        mf.save()

        # chmod 600 na uploadanu datoteku
        try:
            file_path = mf.file.path
            os.chmod(file_path, 0o600)
        except (OSError, NotImplementedError):
            pass

        # Detektiraj adapter i ekstrahiraj podatke
        try:
            file_path = mf.file.path
            adapter = detect_adapter(file_path, file_format)
            if not adapter:
                project.delete()
                return render(request, "data_migration/upload.html", {
                    "error": f"Format '{file_format}' nije podrzani. Podrzani: CSV, Excel (XLSX/XLS).",
                })

            raw_data = adapter.extract_raw_data(file_path)
            columns = adapter.get_detected_columns(raw_data)

            mf.adapter_used = adapter.name
            mf.extracted_data = raw_data
            mf.row_count = len(raw_data)
            mf.detected_columns = columns
            mf.save(update_fields=[
                "adapter_used", "extracted_data", "row_count", "detected_columns",
            ])

            # Postavi total_rows na projektu
            project.total_rows = len(raw_data)
            project.save(update_fields=["total_rows"])

        except ValueError as e:
            project.delete()
            return render(request, "data_migration/upload.html", {
                "error": str(e),
            })
        except Exception as e:
            logger.exception("Greska pri parsiranju datoteke: %s", e)
            project.delete()
            return render(request, "data_migration/upload.html", {
                "error": f"Greska pri citanju datoteke: {e}",
            })

        return redirect("data_migration:mapping", pk=project.pk)

    return render(request, "data_migration/upload.html")


# ── Step 2: Mapping ───────────────────────────────────────────────

@login_required
def mapping_view(request, pk):
    """Mapiranje kolona iz datoteke u ERP polja."""
    project = _get_project(request, pk)
    redir = _check_state(request, project, "mapping")
    if redir:
        return redir

    mf = _get_primary_file(project)
    if not mf:
        return redirect("data_migration:upload")

    adapter = get_adapter(mf.adapter_used)
    schema = adapter.get_mapping_schema(project.entity_type)
    detected_columns = mf.detected_columns or []

    # Sample redovi za preview (prvih 5)
    raw_samples = mf.extracted_data[:5] if mf.extracted_data else []

    # Pretvori u dict: {kolona: "primjer vrijednosti iz prvog reda"}
    sample_values = {}
    for col in detected_columns:
        for row in raw_samples:
            val = row.get(col, "")
            if val:
                sample_values[col] = str(val)[:50]
                break
        else:
            sample_values[col] = ""

    # Pretvori sample redove u liste za tablicu
    sample_table = []
    for row in raw_samples:
        sample_table.append([str(row.get(col, ""))[:50] for col in detected_columns])

    # Auto-match: ako detektirana kolona ima isto ime kao ERP polje
    auto_mapping = {}
    if not project.field_mapping:
        schema_labels = {f["label"].lower(): f["key"] for f in schema}
        schema_keys = {f["key"].lower(): f["key"] for f in schema}
        for col in detected_columns:
            col_lower = col.lower().strip()
            if col_lower in schema_keys:
                auto_mapping[col] = schema_keys[col_lower]
            elif col_lower in schema_labels:
                auto_mapping[col] = schema_labels[col_lower]

    return render(request, "data_migration/mapping.html", {
        "project": project,
        "mf": mf,
        "schema": schema,
        "detected_columns": detected_columns,
        "sample_values": sample_values,
        "sample_table": sample_table,
        "existing_mapping": project.field_mapping or auto_mapping,
    })


@login_required
@require_POST
def mapping_save_api(request, pk):
    """AJAX: sprema mapiranje (partial ili finalno)."""
    project = _get_project(request, pk)
    if project.status not in ("draft", "mapped"):
        return JsonResponse({"ok": False, "error": "Projekt nije u stanju za mapiranje."}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "Neispravan JSON."}, status=400)

    mapping = body.get("mapping", {})
    is_final = body.get("is_final", False)

    # Uvijek spremi (partial save)
    project.field_mapping = mapping
    project.save(update_fields=["field_mapping", "updated_at"])

    if is_final:
        mf = _get_primary_file(project)
        if not mf:
            return JsonResponse({"ok": False, "error": "Nema uploadane datoteke."}, status=400)

        adapter = get_adapter(mf.adapter_used)
        errors = adapter.validate_mapping(mapping, project.entity_type)
        if errors:
            return JsonResponse({"ok": False, "errors": errors}, status=400)

        project.status = "mapped"
        project.save(update_fields=["status", "updated_at"])

    return JsonResponse({"ok": True, "status": project.status})


# ── Step 3: Preview ───────────────────────────────────────────────

@login_required
def preview_view(request, pk):
    """Preview transformiranih podataka prije importa."""
    project = _get_project(request, pk)
    redir = _check_state(request, project, "preview")
    if redir:
        return redir

    mf = _get_primary_file(project)
    if not mf:
        return redirect("data_migration:upload")

    adapter = get_adapter(mf.adapter_used)

    # Transformiraj prvih 50 redova
    preview_slice = mf.extracted_data[:50] if mf.extracted_data else []
    mapped_preview = adapter.apply_mapping(preview_slice, project.field_mapping)

    # Spremi preview i postavi status
    project.preview_data = mapped_preview
    project.status = "preview"
    project.save(update_fields=["preview_data", "status", "updated_at"])

    # Shema za prikaz zaglavlja tablice — samo mapirana polja
    schema = adapter.get_mapping_schema(project.entity_type)
    mapped_fields = [f for f in schema if f["key"] in project.field_mapping.values()]

    # Pretvori preview dict-ove u liste za Django template iteraciju
    field_keys = [f["key"] for f in mapped_fields]
    preview_table = []
    for row in mapped_preview:
        preview_table.append([str(row.get(k, ""))[:80] for k in field_keys])

    return render(request, "data_migration/preview.html", {
        "project": project,
        "mf": mf,
        "preview_table": preview_table,
        "mapped_fields": mapped_fields,
        "total_rows": mf.row_count,
    })


# ── Step 4: Execute ───────────────────────────────────────────────

@login_required
@require_POST
def execute_api(request, pk):
    """AJAX: pokrece Celery task za import."""
    project = _get_project(request, pk)
    if project.status != "preview":
        return JsonResponse(
            {"ok": False, "error": "Projekt nije u stanju za pokretanje importa."},
            status=400,
        )

    # Postavi status na importing
    project.status = "importing"
    project.processed_rows = 0
    project.records_created = 0
    project.records_updated = 0
    project.records_skipped = 0
    project.records_failed = 0
    project.save(update_fields=[
        "status", "processed_rows", "records_created",
        "records_updated", "records_skipped", "records_failed", "updated_at",
    ])

    # Pokreni Celery task
    from .tasks import run_migration
    run_migration.delay(project.pk)

    return JsonResponse({"ok": True, "status": "importing"})


@login_required
@require_GET
def status_api(request, pk):
    """AJAX polling: vraca trenutni status importa."""
    project = _get_project(request, pk)
    data = {
        "status": project.status,
        "processed_rows": project.processed_rows,
        "total_rows": project.total_rows,
        "progress_percent": project.progress_percent,
        "records_created": project.records_created,
        "records_updated": project.records_updated,
        "records_skipped": project.records_skipped,
        "records_failed": project.records_failed,
    }
    if project.status in ("completed", "failed"):
        data["redirect_url"] = f"/data-migration/{project.pk}/result/"
    return JsonResponse(data)


# ── Step 5: Result ────────────────────────────────────────────────

@login_required
def result_view(request, pk):
    """Rezultat importa sa statistikom i logovima."""
    project = _get_project(request, pk)
    redir = _check_state(request, project, "result")
    if redir:
        return redir

    logs = project.logs.all()

    # Filter po levelu
    level_filter = request.GET.get("level", "")
    if level_filter in ("info", "warning", "error"):
        logs = logs.filter(level=level_filter)

    log_counts = {
        "info": project.logs.filter(level="info").count(),
        "warning": project.logs.filter(level="warning").count(),
        "error": project.logs.filter(level="error").count(),
    }

    return render(request, "data_migration/result.html", {
        "project": project,
        "logs": logs[:500],  # max 500 logova na stranici
        "level_filter": level_filter,
        "log_counts": log_counts,
    })


# ── Delete ────────────────────────────────────────────────────────

@login_required
@require_POST
def delete_project(request, pk):
    """Brise projekt i sve povezane datoteke."""
    project = _get_project(request, pk)

    # Fizicki brisi datoteke s diska
    for mf in project.files.all():
        mf.delete_file_from_disk()

    project.delete()
    return redirect("data_migration:dashboard")
