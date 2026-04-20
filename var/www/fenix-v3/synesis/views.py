"""
synesis/views.py — Synesis integracija views.
Adaptirano za Fenix V3 TenantView pattern.
"""

import json
import os
import tempfile
import time

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from core.base_view import TenantView


COUNTRY_NAMES = {
    "HR": "Hrvatska",
    "DE": "Njemacka",
    "SI": "Slovenija",
    "AT": "Austrija",
    "BA": "Bosna i Hercegovina",
    "RS": "Srbija",
    "IT": "Italija",
    "HU": "Madarska",
}


def _country_name(code):
    return COUNTRY_NAMES.get((code or "").upper().strip(), code or "Hrvatska")


def _get_config(company):
    from .models import SynesisConfig

    cfg, _ = SynesisConfig.objects.get_or_create(company=company)
    return cfg


# ── settings view ─────────────────────────────────────────────────────────────


class SynesisSettingsView(TenantView):
    template_name = "synesis/settings.html"
    page_title = "Synesis integracija"

    def get(self, request):
        cfg = _get_config(self.company)
        from .models import SynesisLog

        logs = SynesisLog.objects.filter(company=self.company).order_by("-synced_at")[:20]
        return self.render(request, {"cfg": cfg, "logs": logs})

    def post(self, request):
        cfg = _get_config(self.company)
        cfg.storage_db_path = request.POST.get("storage_db_path", "").strip()
        cfg.journal_db_path = request.POST.get("journal_db_path", "").strip()
        cfg.pos_db_path = request.POST.get("pos_db_path", "").strip()
        cfg.pos_db_password = request.POST.get("pos_db_password", "").strip()
        cfg.connect_base_path = request.POST.get("connect_base_path", "").strip() or r"C:\SynesisConnect"
        cfg.backup_retention_days = int(request.POST.get("backup_retention_days", 30) or 30)
        cfg.auto_backup_enabled = request.POST.get("auto_backup_enabled") == "on"
        cfg.save(
            update_fields=[
                "storage_db_path",
                "journal_db_path",
                "pos_db_path",
                "pos_db_password",
                "connect_base_path",
                "backup_retention_days",
                "auto_backup_enabled",
                "updated_at",
            ]
        )
        messages.success(request, _("Konfiguracija Synesis integracije je spremljena."))
        return redirect("synesis:settings")


# ── regenerate token ──────────────────────────────────────────────────────────


class RegenerateTokenView(TenantView):
    def post(self, request):
        cfg = _get_config(self.company)
        cfg.regenerate_token()
        messages.success(request, _("API token je regeneriran. Ažurirajte sync skriptu!"))
        return redirect("synesis:settings")


# ── download sync script ──────────────────────────────────────────────────────


class DownloadScriptView(TenantView):
    def get(self, request):
        cfg = _get_config(self.company)
        script = _build_script(cfg, self.company)
        response = HttpResponse(script, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="synesis_sync.py"'
        return response


# ── public token-based script download ───────────────────────────────────────


def download_script_public(request, token):
    """No login required — API token in URL authenticates."""
    from .models import SynesisConfig

    try:
        cfg = SynesisConfig.objects.select_related("company").get(api_token=token, is_active=True)
    except SynesisConfig.DoesNotExist:
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Invalid token")
    script = _build_script(cfg, cfg.company)
    response = HttpResponse(script, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="synesis_sync.py"'
    return response


# ── download setup BAT ────────────────────────────────────────────────────────


class DownloadSetupView(TenantView):
    def get(self, request):
        cfg = _get_config(self.company)
        bat = _build_setup_bat(cfg, self.company)
        response = HttpResponse(bat, content_type="text/plain; charset=windows-1250")
        response["Content-Disposition"] = 'attachment; filename="synesis_setup.bat"'
        return response


def _build_setup_bat(cfg, company):
    token = cfg.api_token
    script_url = "https://limit-connect.com/hr/synesis/script/{}/".format(token)
    company_name = company.name.replace('"', "")
    lines = [
        "@echo off",
        "chcp 65001 > nul",
        "setlocal",
        "",
        "echo ============================================",
        "echo  Fenix V3 - Synesis automatska sync",
        "echo  Tvrtka: {}".format(company_name),
        "echo ============================================",
        "echo.",
        "",
        ":: Provjeri Python",
        'set "PYTHON="',
        "where python > nul 2>&1",
        'if not errorlevel 1 set "PYTHON=python"',
        "if not defined PYTHON (",
        "    where py > nul 2>&1",
        '    if not errorlevel 1 set "PYTHON=py"',
        ")",
        "if not defined PYTHON (",
        "    echo [GRESKA] Python nije pronaDen!",
        "    echo.",
        "    echo Instalirajte Python s: https://www.python.org/downloads/",
        '    echo Kod instalacije OBAVEZNO oznacite "Add Python to PATH"',
        "    echo Zatim pokrenite ovaj setup ponovo.",
        "    echo.",
        "    pause",
        "    exit /b 1",
        ")",
        "echo [OK] Python pronaDen",
        "echo.",
        "",
        ":: Instaliraj pakete",
        "echo [1/4] Instalacija potrebnih paketa (pyodbc, requests)...",
        "%PYTHON% -m pip install pyodbc requests --quiet --upgrade",
        "if errorlevel 1 (",
        "    echo [GRESKA] Instalacija paketa neuspjesna!",
        "    pause",
        "    exit /b 1",
        ")",
        "echo [OK] Paketi instalirani",
        "echo.",
        "",
        ":: Preuzmi sync skriptu",
        "echo [2/4] Preuzimanje sync skripte s portala...",
        'set "SYNC_SCRIPT=%~dp0synesis_sync.py"',
        'curl -s -f -o "%SYNC_SCRIPT%" "{}"'.format(script_url),
        "if errorlevel 1 (",
        "    echo [GRESKA] Preuzimanje skripte neuspjesno!",
        "    pause",
        "    exit /b 1",
        ")",
        "echo [OK] Skripta preuzeta",
        "echo.",
        "",
        ":: Kreiraj Scheduled Task (svaki dan u 02:00)",
        "echo [3/4] Postavljanje automatske sinkronizacije...",
        'schtasks /create /tn "FenixV3-SynesisSync" /tr "\\"%PYTHON%\\" \\"%SYNC_SCRIPT%\\"" /sc daily /st 02:00 /f > nul 2>&1',
        "if errorlevel 1 (",
        "    echo [UPOZORENJE] Nije moguce kreirati automatski zadatak.",
        "    echo Pokrenite setup kao Administrator.",
        ") else (",
        "    echo [OK] Automatska sinkronizacija: svaki dan u 02:00",
        ")",
        "echo.",
        "",
        ":: Prva sinkronizacija",
        "echo [4/4] Pokrecemo prvu sinkronizaciju...",
        "echo.",
        '%PYTHON% "%SYNC_SCRIPT%"',
        "echo.",
        "echo ============================================",
        "echo  Gotovo! Sinkronizacija je postavljena.",
        "echo  Pokrece se automatski svaki dan u 02:00.",
        "echo ============================================",
        "echo.",
        "pause",
    ]
    return "\r\n".join(lines) + "\r\n"


def _build_script(cfg, company):
    """Generira Windows sync skriptu za klijenta."""
    slug = company.name.replace(" ", "_").replace(".", "").replace(",", "")[:20]
    connect_base = r"C:\SynesisConnect"
    retention = cfg.backup_retention_days or 30

    L = []

    def a(s=""):
        L.append(s)

    a("#!/usr/bin/env python3")
    a("# -*- coding: utf-8 -*-")
    a('"""')
    a(f"synesis_sync.py — {company.name}")
    a(f"Generirano: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
    a("")
    a("Instalacija: pip install pyodbc requests")
    a("Pokretanje:")
    a("  python synesis_sync.py              # sve")
    a("  python synesis_sync.py import       # samo uvoz Synesis -> ERP")
    a("  python synesis_sync.py export       # samo izvoz ERP -> Synesis")
    a("  python synesis_sync.py backup       # samo backup")
    a("  python synesis_sync.py status       # provjeri stanje")
    a("  python synesis_sync.py partners     # samo partneri")
    a("  python synesis_sync.py items        # samo artikli")
    a('"""')
    a("import sys, os, shutil, json, datetime, decimal, time, hashlib, logging")
    a("import pyodbc, requests")
    a()
    a("# =====================================================================")
    a("# KONFIGURACIJA")
    a("# =====================================================================")
    a()
    a(f'STORAGE_ORIGINAL = r"{cfg.storage_db_path or r"C:\Synesis\FIRMA\Storage.mdb"}"')
    a(f'JOURNAL_ORIGINAL = r"{cfg.journal_db_path or r"C:\Synesis\FIRMA\Journal.mdb"}"')
    a(f'POS_ORIGINAL     = r"{cfg.pos_db_path or ""}"')
    a(f'POS_PWD          = "{cfg.pos_db_password or ""}"')
    a()
    a(f'CONNECT_BASE  = r"{connect_base}"')
    a(f'FIRMA_SLUG    = "{slug}"')
    a("CONNECT_DIR   = os.path.join(CONNECT_BASE, FIRMA_SLUG)")
    a('BACKUP_DIR    = os.path.join(CONNECT_DIR, "backup")')
    a('WORK_DIR      = os.path.join(CONNECT_DIR, "work")')
    a('EXPORT_DIR    = os.path.join(CONNECT_DIR, "export")')
    a('LOG_FILE      = os.path.join(CONNECT_DIR, "connect_log.txt")')
    a()
    a('STORAGE_WORK  = os.path.join(WORK_DIR, "Storage_work.mdb")')
    a('JOURNAL_WORK  = os.path.join(WORK_DIR, "Journal_work.mdb")')
    a()
    a('API_URL       = "https://limit-connect.com/api/synesis/import/"')
    a(f'API_TOKEN     = "{cfg.api_token}"')
    a(f'EXPORT_URL    = "https://limit-connect.com/api/synesis/export/{cfg.api_token}/"')
    a(f'CONFIRM_URL   = "https://limit-connect.com/api/synesis/export/{cfg.api_token}/confirm/"')
    a("BATCH_SIZE    = 200")
    a(f"BACKUP_DAYS   = {retention}")
    a('DRIVER        = "Microsoft Access Driver (*.mdb, *.accdb)"')
    a()
    a("def _setup_log():")
    a("    os.makedirs(CONNECT_DIR, exist_ok=True)")
    a('    fmt = "%(asctime)s [%(levelname)s] %(message)s"')
    a("    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[")
    a('        logging.FileHandler(LOG_FILE, encoding="utf-8"),')
    a("        logging.StreamHandler(sys.stdout),")
    a("    ])")
    a()
    a("_setup_log()")
    a("log = logging.getLogger()")
    a()
    a("def safe(v):")
    a("    if isinstance(v, (bytes, bytearray)): return v.decode('cp1250', errors='replace')")
    a("    if isinstance(v, decimal.Decimal): return float(v)")
    a("    if isinstance(v, datetime.datetime): return v.strftime('%Y-%m-%d %H:%M:%S')")
    a("    if isinstance(v, datetime.date): return v.strftime('%Y-%m-%d')")
    a("    return v")
    a()
    a("def json_serial(o):")
    a("    if isinstance(o, (datetime.datetime, datetime.date)): return o.isoformat()")
    a("    if isinstance(o, decimal.Decimal): return float(o)")
    a("    return str(o)")
    a()
    a("def send_batch(type_, data):")
    a('    headers = {"Authorization": f"Token {API_TOKEN}", "Content-Type": "application/json"}')
    a("    try:")
    a(
        '        r = requests.post(API_URL, headers=headers, json={"type": type_, "data": data if isinstance(data, list) else [data]}, timeout=60)'
    )
    a("        return r.json()")
    a("    except Exception as e: log.error(f'  Greska slanja: {e}'); return {}")
    a()
    a("def ensure_dirs():")
    a("    for d in [BACKUP_DIR, WORK_DIR, EXPORT_DIR]:")
    a("        os.makedirs(d, exist_ok=True)")
    a()
    a("def do_backup():")
    a('    log.info("\\n--- Backup originalnih fajlova ---")')
    a("    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')")
    a("    for src, name in [(STORAGE_ORIGINAL, 'Storage'), (JOURNAL_ORIGINAL, 'Journal')]:")
    a("        if not os.path.exists(src): continue")
    a("        dst = os.path.join(BACKUP_DIR, f'{name}_{ts}.mdb')")
    a("        shutil.copy2(src, dst)")
    a("        log.info(f'  Backup: {dst}')")
    a("    # Brisanje starih backupa")
    a("    cutoff = datetime.datetime.now() - datetime.timedelta(days=BACKUP_DAYS)")
    a("    for f in os.listdir(BACKUP_DIR):")
    a("        fp = os.path.join(BACKUP_DIR, f)")
    a("        if os.path.getmtime(fp) < cutoff.timestamp():")
    a("            os.remove(fp); log.info(f'  Obrisan stari backup: {f}')")
    a()
    a("def make_work_copy():")
    a('    log.info("\\n--- Kreiranje radne kopije ---")')
    a("    if os.path.exists(STORAGE_ORIGINAL): shutil.copy2(STORAGE_ORIGINAL, STORAGE_WORK)")
    a("    if os.path.exists(JOURNAL_ORIGINAL): shutil.copy2(JOURNAL_ORIGINAL, JOURNAL_WORK)")
    a()
    a(f'def conn_s(): return pyodbc.connect(f"DRIVER={{{chr(123)}DRIVER{chr(125)}}};DBQ={{STORAGE_WORK}};")')
    a(f'def conn_j(): return pyodbc.connect(f"DRIVER={{{chr(123)}DRIVER{chr(125)}}};DBQ={{JOURNAL_WORK}};")')
    a()
    a("def sync_partners():")
    a('    log.info("\\n[PARTNERI] Synesis -> ERP")')
    a("    c = conn_s(); cur = c.cursor()")
    a('    cur.execute("""')
    a("        SELECT PARTNER_ID, PARTNER_NAME, PARTNER_VATNUMBER, PARTNER_STREET,")
    a("               CITY_NAME, CITY_ZIPCODE, PARTNER_EMAIL, PARTNER_PHONE,")
    a("               PARTNER_MOBILE, PARTNER_WEB, INT_COUNTRYID,")
    a("               PARTNER_DISCOUNTRATE, PARTNER_PAYMENTDAYS, PARTNER_TYPE")
    a("        FROM PARTNERS WHERE PARTNER_NAME IS NOT NULL ORDER BY PARTNER_ID")
    a('    """)')
    a("    cols = [d[0] for d in cur.description]")
    a("    rows = [dict(zip(cols, [safe(v) for v in row])) for row in cur.fetchall()]")
    a("    c.close()")
    a('    log.info(f"  Pronasao: {len(rows)} partnera")')
    a("    cr=up=er=0")
    a("    for i in range(0, len(rows), BATCH_SIZE):")
    a('        res = send_batch("partners", rows[i:i+BATCH_SIZE])')
    a('        cr+=res.get("created",0); up+=res.get("updated",0); er+=res.get("errors",0)')
    a('    log.info(f"  Kreirano:{cr} Azurirano:{up} Greske:{er}")')
    a()
    a("def sync_items():")
    a('    log.info("\\n[ARTIKLI] Synesis -> ERP")')
    a("    c = conn_s(); cur = c.cursor()")
    a('    cur.execute("""')
    a("        SELECT ITEM_ID, ITEM_NAME, ITEM_MEASURE, ITEM_BARCODE,")
    a("               ITEM_NETPRICE, VAT_RATE, ITEM_PRICE,")
    a("               ITEMGROUP_NAME, ITEM_TYPE, NKPID, ITEM_REMARK")
    a("        FROM ITEMS WHERE ITEM_NAME IS NOT NULL ORDER BY ITEM_ID")
    a('    """)')
    a("    cols = [d[0] for d in cur.description]")
    a("    rows = [dict(zip(cols, [safe(v) for v in row])) for row in cur.fetchall()]")
    a("    c.close()")
    a('    log.info(f"  Pronasao: {len(rows)} artikala")')
    a("    cr=up=er=0")
    a("    for i in range(0, len(rows), BATCH_SIZE):")
    a('        res = send_batch("items", rows[i:i+BATCH_SIZE])')
    a('        cr+=res.get("created",0); up+=res.get("updated",0); er+=res.get("errors",0)')
    a('    log.info(f"  Kreirano:{cr} Azurirano:{up} Greske:{er}")')
    a()
    a("def sync_from_erp():")
    a('    log.info("\\n[IZVOZ] Provjera ERP export queue...")')
    a("    try:")
    a("        r = requests.get(EXPORT_URL, timeout=30)")
    a("        data = r.json()")
    a("    except Exception as e: log.error(f'  Greska: {e}'); return")
    a("    n = len(data.get('items',[])) + len(data.get('partners',[]))")
    a('    log.info(f"  Pronasao {n} zapisa za izvoz")')
    a()
    a('if __name__ == "__main__":')
    a('    mode = sys.argv[1] if len(sys.argv) > 1 else "all"')
    a("    ensure_dirs()")
    a("    t0 = time.time()")
    a(f'    log.info(f"FENIX V3 Synesis Sync — {company.name}")')
    a("    log.info(f\"Nacin: {mode} | {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\")")
    a('    if   mode == "status": pass')
    a('    elif mode == "backup":  do_backup()')
    a('    elif mode == "partners": do_backup(); make_work_copy(); sync_partners()')
    a('    elif mode == "items":   do_backup(); make_work_copy(); sync_items()')
    a('    elif mode == "import":  do_backup(); make_work_copy(); sync_partners(); sync_items()')
    a('    elif mode == "export":  do_backup(); sync_from_erp()')
    a("    else:")
    a("        do_backup(); make_work_copy(); sync_partners(); sync_items(); sync_from_erp()")
    a('    log.info(f"\\nGOTOVO za {time.time()-t0:.1f}s")')
    a()

    return "\n".join(L) + "\n"


# ── import API ─────────────────────────────────────────────────────────────────


@csrf_exempt
def synesis_import_api(request):
    """POST /api/synesis/import/ — Token-authenticated API endpoint za sync skriptu."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Token "):
        return JsonResponse({"error": "Missing token"}, status=401)
    token = auth[6:].strip()

    from .models import SynesisConfig, SynesisLog

    try:
        cfg = SynesisConfig.objects.select_related("company").get(api_token=token, is_active=True)
    except SynesisConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=401)

    company = cfg.company
    t_start = time.time()

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    sync_type = body.get("type")
    data = body.get("data", [])
    if not sync_type or not isinstance(data, list):
        return JsonResponse({"error": "Missing type or data"}, status=400)

    if sync_type == "partners":
        result = _import_partners(company, data)
    elif sync_type == "items":
        result = _import_items(company, data)
    elif sync_type == "pos":
        result = _import_pos(company, data)
    elif sync_type == "invoices":
        created, updated, errors = _import_invoices(request, company, data)
        result = {"created": created, "updated": updated, "errors": errors}
    elif sync_type == "schema_probe":
        result = _import_schema_probe(company, data)
    elif sync_type == "pkv_probe":
        result = _import_pkv_probe(company, data)
    else:
        return JsonResponse({"error": "Unknown type: " + sync_type}, status=400)

    duration = round(time.time() - t_start, 2)
    now = timezone.now()

    if sync_type == "partners":
        cfg.last_sync_partners = now
        cfg.partners_total = result.get("total_in_db", cfg.partners_total)
        cfg.save(update_fields=["last_sync_partners", "partners_total", "updated_at"])
    elif sync_type == "items":
        cfg.last_sync_items = now
        cfg.items_total = result.get("total_in_db", cfg.items_total)
        cfg.save(update_fields=["last_sync_items", "items_total", "updated_at"])

    SynesisLog.objects.create(
        company=company,
        sync_type=sync_type,
        records_received=len(data),
        records_created=result.get("created", 0),
        records_updated=result.get("updated", 0),
        errors=result.get("errors", 0),
        error_detail=result.get("error_detail", ""),
        duration_seconds=duration,
        client_ip=request.META.get("REMOTE_ADDR"),
    )

    return JsonResponse({**result, "duration": duration})


# ── export API ────────────────────────────────────────────────────────────────


@csrf_exempt
def synesis_export_api(request, token):
    """GET /api/synesis/export/{token}/ — Vraća pending promjene za Synesis."""
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    from .models import SynesisConfig, SynesisExportQueue

    try:
        cfg = SynesisConfig.objects.select_related("company").get(api_token=token, is_active=True)
    except SynesisConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=401)

    company = cfg.company
    items_export = _export_items(company)
    partners_export = _export_partners(company)

    SynesisExportQueue.objects.filter(company=company, is_exported=False).update(
        is_exported=True, exported_at=timezone.now()
    )

    return JsonResponse(
        {
            "items": items_export,
            "partners": partners_export,
            "timestamp": timezone.now().isoformat(),
            "total": len(items_export) + len(partners_export),
        }
    )


@csrf_exempt
def synesis_export_confirm(request, token):
    """POST /api/synesis/export/{token}/confirm/ — Potvrda uspješnog pisanja u MDB."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    from .models import SynesisConfig, SynesisExportQueue

    try:
        cfg = SynesisConfig.objects.select_related("company").get(api_token=token, is_active=True)
    except SynesisConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=401)

    try:
        body = json.loads(request.body)
        confirmed = body.get("confirmed_ids", [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    count = SynesisExportQueue.objects.filter(company=cfg.company, pk__in=confirmed).update(
        is_confirmed=True, confirmed_at=timezone.now()
    )

    return JsonResponse({"confirmed": count})


def _export_items(company):
    from .models import SynesisExportQueue

    pending = SynesisExportQueue.objects.filter(company=company, export_type="item", is_exported=False).order_by(
        "created_at"
    )
    results = []
    for q in pending:
        entry = {"queue_id": q.pk, "action": q.action, "fields": q.payload}
        if q.synesis_id:
            entry["synesis_id"] = q.synesis_id
        results.append(entry)
    return results


def _export_partners(company):
    from .models import SynesisExportQueue

    pending = SynesisExportQueue.objects.filter(company=company, export_type="partner", is_exported=False).order_by(
        "created_at"
    )
    results = []
    for q in pending:
        entry = {"queue_id": q.pk, "action": q.action, "fields": q.payload}
        if q.synesis_id:
            entry["synesis_id"] = q.synesis_id
        results.append(entry)
    return results


# ── import helpers ────────────────────────────────────────────────────────────


def _import_partners(company, data):
    from partners.models import Partner

    created = updated = errors = 0
    error_msgs = []

    for row in data:
        try:
            name = (row.get("PARTNER_NAME") or "").strip()
            if not name:
                continue
            oib = (row.get("PARTNER_VATNUMBER") or "").strip()
            ptype_raw = str(row.get("PARTNER_TYPE") or "1")
            ptype = "supplier" if ptype_raw == "1" else "client"
            country = _country_name((row.get("INT_COUNTRYID") or "HR"))
            phone = ((row.get("PARTNER_PHONE") or "") or (row.get("PARTNER_MOBILE") or "")).strip()
            zip_code = (row.get("CITY_ZIPCODE") or "").strip()
            if zip_code == "0":
                zip_code = ""
            defaults = {
                "name": name,
                "address": (row.get("PARTNER_STREET") or "").strip(),
                "city": (row.get("CITY_NAME") or "").strip().title(),
                "zip_code": zip_code,
                "email": (row.get("PARTNER_EMAIL") or "").strip(),
                "phone": phone,
                "web": (row.get("PARTNER_WEB") or "").strip(),
                "country": country,
                "partner_type": ptype,
                "payment_term": int(row.get("PARTNER_PAYMENTDAYS") or 0),
                "discount_percent": float(row.get("PARTNER_DISCOUNTRATE") or 0),
            }
            if oib:
                defaults["oib"] = oib
                obj, was_created = Partner.objects.update_or_create(company=company, oib=oib, defaults=defaults)
            else:
                defaults["oib"] = ""
                try:
                    obj = Partner.objects.get(company=company, name=name, oib="")
                    for k, v in defaults.items():
                        setattr(obj, k, v)
                    obj.save()
                    was_created = False
                except Partner.DoesNotExist:
                    syn_id = str(row.get("PARTNER_ID", "")).strip()
                    defaults["oib"] = f"SYN-{syn_id or name[:8]}"
                    obj = Partner.objects.create(company=company, **defaults)
                    was_created = True
                except Partner.MultipleObjectsReturned:
                    was_created = False

            if was_created:
                created += 1
            else:
                updated += 1
        except ObjectDoesNotExist as exc:
            errors += 1
            error_msgs.append(str(exc)[:200])

    total = Partner.objects.filter(company=company).count()
    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_in_db": total,
        "error_detail": "\n".join(error_msgs[:10]),
    }


def _import_items(company, data):
    from inventory.models import InventoryItem

    created = updated = errors = 0
    error_msgs = []

    for row in data:
        try:
            name = (row.get("ITEM_NAME") or "").strip()
            if not name:
                continue
            synesis_id = str(row.get("ITEM_ID") or "").strip()
            sku = "SYN-" + synesis_id if synesis_id else ""
            if not sku:
                errors += 1
                continue
            unit = (row.get("ITEM_MEASURE") or "kom").strip().lower()
            barcode = (row.get("ITEM_BARCODE") or "").strip()
            vat_num = float(row.get("VAT_RATE") or 25)
            if vat_num == 10:
                vat_num = 13
            unit_price = float(row.get("ITEM_PRICE") or 0)
            purchase_price = float(row.get("ITEM_NETPRICE") or 0)
            category = (row.get("ITEMGROUP_NAME") or "").strip()
            description = (row.get("ITEM_REMARK") or "").strip()

            defaults = {
                "name": name,
                "unit": unit,
                "barcode": barcode,
                "unit_price": unit_price or purchase_price,
                "purchase_price": purchase_price,
                "tax_rate": vat_num,
                "description": (category + " - " if category else "") + description,
            }
            _, was_created = InventoryItem.objects.update_or_create(company=company, sku=sku, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1
        except (ValueError, TypeError) as exc:
            errors += 1
            error_msgs.append(str(exc)[:200])

    total = InventoryItem.objects.filter(company=company).count()
    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_in_db": total,
        "error_detail": "\n".join(error_msgs[:10]),
    }


def _import_pos(company, data):
    import datetime as _dt

    receipts = data.get("receipts", []) if isinstance(data, dict) else []
    pos_name = data.get("pos_name", "Kasa") if isinstance(data, dict) else "Kasa"

    now = timezone.now()
    today = now.date()
    week_ago = today - _dt.timedelta(days=7)
    month_ago = today - _dt.timedelta(days=30)
    revenue_today = revenue_week = revenue_month = 0.0

    for r in receipts:
        try:
            amt = float(r.get("Receipt_Ammount") or 0)
            date_str = str(r.get("Receipt_Date") or "")[:10]
            try:
                receipt_date = _dt.date.fromisoformat(date_str)
            except (ValueError, KeyError):
                receipt_date = None
            if receipt_date:
                if receipt_date == today:
                    revenue_today += amt
                if receipt_date >= week_ago:
                    revenue_week += amt
                if receipt_date >= month_ago:
                    revenue_month += amt
        except (ValueError, TypeError):
            pass

    from .models import SynesisConfig

    try:
        cfg = SynesisConfig.objects.get(company=company)
        cfg.pos_name = pos_name or cfg.pos_name
        cfg.pos_receipts_total = len(receipts)
        cfg.pos_revenue_today = round(revenue_today, 2)
        cfg.pos_revenue_week = round(revenue_week, 2)
        cfg.pos_revenue_month = round(revenue_month, 2)
        cfg.last_sync_pos = now
        cfg.save(
            update_fields=[
                "pos_name",
                "pos_receipts_total",
                "pos_revenue_today",
                "pos_revenue_week",
                "pos_revenue_month",
                "last_sync_pos",
                "updated_at",
            ]
        )
    except ObjectDoesNotExist as exc:
        return {"error": str(exc), "received": len(receipts)}

    return {
        "received": len(receipts),
        "revenue_today": round(revenue_today, 2),
        "revenue_week": round(revenue_week, 2),
        "revenue_month": round(revenue_month, 2),
        "pos_name": pos_name,
    }


def _import_invoices(request, company, data_list):
    """Import faktura iz Synesis u fenix-v3 Invoice model."""
    import hashlib
    from decimal import Decimal, InvalidOperation

    from invoicing.models import Invoice, InvoiceItem
    from partners.models import Partner

    created = updated = errors = 0
    year = None

    for row in data_list:
        try:
            synesis_id = str(row.get("TRANCODE", row.get("DIN", ""))).strip()
            if not synesis_id:
                continue

            archive_hash = hashlib.md5(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()

            # Datum
            date_str = str(row.get("INVOICE_DATE", row.get("TRANDATE", ""))).strip()
            date_issued = None
            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    import datetime as _dt

                    date_issued = _dt.datetime.strptime(date_str[:10], fmt).date()
                    year = date_issued.year
                    break
                except (ValueError, TypeError):
                    continue
            if not date_issued:
                import datetime as _dt

                date_issued = _dt.date.today()

            # Skip if exists
            existing = Invoice.objects.filter(company=company, synesis_id=synesis_id).first()

            # Partner lookup
            partner_oib = str(row.get("PARTNER_VATNUMBER", "")).strip()
            partner_name = str(row.get("PARTNER_NAME", "")).strip()
            partner = None
            if partner_oib:
                partner = Partner.objects.filter(company=company, oib=partner_oib).first()
            if not partner and partner_name:
                partner = Partner.objects.filter(company=company, name__icontains=partner_name[:30]).first()

            def safe_dec(v):
                if v is None:
                    return Decimal("0")
                try:
                    return Decimal(str(v).replace(",", "."))
                except (InvalidOperation, ValueError):
                    return Decimal("0")

            total = safe_dec(row.get("INVOICE_TOTAL", row.get("TOTAL", 0)))
            tax_amount = safe_dec(row.get("INVOICE_TAX", row.get("TAXAMOUNT", 0)))
            subtotal = total - tax_amount if total > tax_amount else total

            invoice_number = str(row.get("INVOICE_NUMBER", "")).strip()
            if not invoice_number:
                invoice_number = f"SYN-{year or '0'}-{synesis_id}"

            if existing:
                if existing.synesis_hash != archive_hash:
                    existing.synesis_hash = archive_hash
                    existing.save(update_fields=["synesis_hash"])
                    updated += 1
                continue

            # Deduplicate invoice number
            base_number = invoice_number
            counter = 1
            while Invoice.objects.filter(company=company, number=invoice_number).exists():
                invoice_number = f"{base_number}-{counter}"
                counter += 1

            inv = Invoice.objects.create(
                company=company,
                number=invoice_number,
                doc_type=Invoice.DocType.INVOICE,
                issue_date=date_issued,
                buyer_name=partner_name,
                buyer_address=str(row.get("PARTNER_STREET", "")).strip(),
                buyer_city=str(row.get("CITY_NAME", "")).strip(),
                buyer_oib=partner_oib,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total=total,
                status=Invoice.Status.PAID,
                source="synesis",
                synesis_id=synesis_id,
                synesis_year=year,
                synesis_hash=archive_hash,
                is_locked=True,
                jir=str(row.get("FIS_JIR", "")).strip() or "",
                zki=str(row.get("FIS_ZKI", "")).strip() or "",
                note=f"Uvezeno iz Synesis arhive ({year})",
            )

            # Import line items
            for idx, item_row in enumerate(row.get("_items", [])):
                item_name = str(item_row.get("ITEM_NAME", item_row.get("DESCRIPTION", f"Stavka {idx + 1}"))).strip()
                qty = safe_dec(item_row.get("ITEM_QTY", item_row.get("QTY", 1)))
                price = safe_dec(item_row.get("ITEM_PRICE", item_row.get("PRICE", 0)))
                item_total = qty * price
                InvoiceItem.objects.create(
                    invoice=inv,
                    description=item_name,
                    quantity=qty,
                    unit=str(item_row.get("ITEM_MEASURE", "kom")).strip() or "kom",
                    unit_price=price,
                    total_price=item_total,
                    tax_rate=safe_dec(item_row.get("VAT_RATE", 25)),
                )

            created += 1

        except (ValueError, TypeError):
            errors += 1
            import traceback

            traceback.print_exc()

    # Update year config
    from .models import SynesisConfig, SynesisYearConfig

    cfg = SynesisConfig.objects.filter(company=company).first()
    if cfg and year:
        yc, _ = SynesisYearConfig.objects.get_or_create(config=cfg, year=year)
        yc.last_sync_invoices = timezone.now()
        yc.invoices_total = Invoice.objects.filter(company=company, source="synesis", synesis_year=year).count()
        yc.save(update_fields=["last_sync_invoices", "invoices_total"])

    return created, updated, errors


def _import_schema_probe(company, data):
    import json as _json

    out_path = f"/tmp/synesis_schema_{company.pk}.json"
    payload = data[0] if data else {}
    with open(out_path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, indent=2, ensure_ascii=False)
    tables = payload.get("tables", [])
    inv_tables = [t for t in tables if "INV" in t.upper()]
    return {
        "received": len(tables),
        "created": 0,
        "updated": 0,
        "errors": 0,
        "invoice_tables": inv_tables,
        "saved_to": out_path,
        "total_in_db": 0,
    }


def _import_pkv_probe(company, data):
    import json as _json

    out_path = f"/tmp/synesis_pkv_probe_{company.pk}.json"
    payload = data[0] if data else {}
    with open(out_path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, indent=2, ensure_ascii=False)
    return {
        "received": 1,
        "created": 0,
        "updated": 0,
        "errors": 0,
        "saved_to": out_path,
        "total_in_db": 0,
    }


# ── MDB online upload / preview / import ──────────────────────────────────────


class MdbUploadView(TenantView):
    template_name = "synesis/mdb_upload.html"
    page_title = "Synesis Online Import"

    def get(self, request):
        return self.render(request, {})

    def post(self, request):
        if not request.FILES.get("mdb_file"):
            return self.render(request, {"error": "Odaberite datoteku."})

        mdb_file = request.FILES["mdb_file"]
        fname = mdb_file.name.lower()

        tmp_dir = os.path.join(tempfile.gettempdir(), "synesis_uploads")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"{self.company.pk}_{mdb_file.name}")

        with open(tmp_path, "wb") as f:
            for chunk in mdb_file.chunks():
                f.write(chunk)

        request.session["synesis_file_type"] = "json" if fname.endswith(".json") else "mdb"
        request.session["synesis_mdb_path"] = tmp_path
        request.session["synesis_mdb_name"] = mdb_file.name

        return redirect("synesis:mdb_preview")


class MdbPreviewView(TenantView):
    template_name = "synesis/mdb_preview.html"
    page_title = "Pregled MDB sadržaja"

    def get(self, request):
        from . import mdb_service

        mdb_path = request.session.get("synesis_mdb_path")
        mdb_name = request.session.get("synesis_mdb_name", "Storage.mdb")

        if not mdb_path or not os.path.exists(mdb_path):
            return redirect("synesis:mdb_upload")

        file_type = request.session.get("synesis_file_type", "mdb")

        if file_type == "json":
            summary = mdb_service.json_summary(mdb_path)
            partners = mdb_service.json_partners_preview(mdb_path)
            items = mdb_service.json_items_preview(mdb_path)
            invoices = []
        else:
            summary = mdb_service.read_mdb_summary(mdb_path)
            partners = mdb_service.read_partners(mdb_path)
            items = mdb_service.read_items(mdb_path)
            invoices = mdb_service.read_invoices(mdb_path)

        return self.render(
            request,
            {
                "mdb_name": mdb_name,
                "file_type": file_type,
                "summary": summary,
                "partners": partners[:50],
                "partners_total": len(partners),
                "items": items[:50],
                "items_total": len(items),
                "invoices": invoices[:30],
                "invoices_total": len(invoices),
            },
        )


class MdbImportExecuteView(TenantView):
    def post(self, request):
        from . import mdb_service

        mdb_path = request.session.get("synesis_mdb_path")
        if not mdb_path or not os.path.exists(mdb_path):
            return self.json_error("MDB file not found. Please upload again.", status=400)

        import_type = request.POST.get("type", "partners")
        file_type = request.session.get("synesis_file_type", "mdb")
        results = {}

        try:
            if file_type == "json":
                results = mdb_service.import_json_to_erp(mdb_path, self.company)
            elif import_type == "partners":
                results = mdb_service.import_partners_to_erp(mdb_path, self.company)
            elif import_type == "items":
                results = mdb_service.import_items_to_erp(mdb_path, self.company)
            elif import_type == "all":
                r1 = mdb_service.import_partners_to_erp(mdb_path, self.company)
                r2 = mdb_service.import_items_to_erp(mdb_path, self.company)
                results = {"partners": r1, "items": r2}
        except Exception as e:
            return self.json_error(str(e), status=500)

        from inventory.models import InventoryItem
        from partners.models import Partner

        results["verification"] = {
            "total_partners": Partner.objects.filter(company=self.company).count(),
            "total_items": InventoryItem.objects.filter(company=self.company).count(),
        }
        return self.json_ok({"status": "success", "results": results})
