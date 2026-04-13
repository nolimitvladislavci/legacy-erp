import json
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

# ── helpers ───────────────────────────────────────────────────────────────────

def _get_config(company):
    from .models import SynesisConfig
    cfg, _ = SynesisConfig.objects.get_or_create(company=company)
    return cfg


COUNTRY_NAMES = {
    "HR": "Hrvatska", "DE": "Njemacka", "SI": "Slovenija",
    "AT": "Austrija", "BA": "Bosna i Hercegovina", "RS": "Srbija",
    "IT": "Italija", "HU": "Madarska", "CZ": "Ceska",
}


def _country_name(code):
    return COUNTRY_NAMES.get((code or "").upper().strip(), code or "Hrvatska")


# ── settings view ─────────────────────────────────────────────────────────────

@login_required
def synesis_settings(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect("dashboard")
    cfg = _get_config(company)
    from .models import SynesisLog
    logs = SynesisLog.objects.filter(company=company).select_related("company").order_by("-synced_at")[:20]

    if request.method == "POST":
        cfg.storage_db_path = request.POST.get("storage_db_path", "").strip()
        cfg.journal_db_path = request.POST.get("journal_db_path", "").strip()
        cfg.pos_db_path = request.POST.get("pos_db_path", "").strip()
        cfg.pos_db_password = request.POST.get("pos_db_password", "").strip()
        cfg.connect_base_path      = request.POST.get("connect_base_path", "").strip() or r'C:\SynesisConnect'
        cfg.backup_retention_days  = int(request.POST.get("backup_retention_days", 30) or 30)
        cfg.auto_backup_enabled    = request.POST.get("auto_backup_enabled") == "on"
        cfg.save(update_fields=["storage_db_path", "journal_db_path", "pos_db_path", "pos_db_password",
                                 "connect_base_path", "backup_retention_days", "auto_backup_enabled", "updated_at"])
        messages.success(request, _("Konfiguracija Synesis integracije je spremljena."))
        return redirect("synesis:settings")

    return render(request, "synesis/settings.html", {"cfg": cfg, "logs": logs})


# ── regenerate token ──────────────────────────────────────────────────────────

@login_required
@require_POST
def regenerate_token(request):
    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "no company"}, status=400)
    cfg = _get_config(company)
    cfg.regenerate_token()
    messages.success(request, _("API token je regeneriran. Azurirajte sync skriptu!"))
    return redirect("synesis:settings")


# ── download sync script ──────────────────────────────────────────────────────

@login_required
def download_script(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect("synesis:settings")
    cfg = _get_config(company)
    script = _build_script(cfg, company)
    response = HttpResponse(script, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="synesis_sync.py"'
    return response


def _build_script(cfg, company):
    """
    Generira Windows sync skriptu s potpunom izolacijom MDB fajlova.

    FOLDER ARHITEKTURA na Windows računalu:
      C:\\Synesis\\FIRMA\\           ← ORIGINALI — nikad ne pisemo direktno
          Storage.mdb
          Journal.mdb

      C:\\SynesisConnect\\FIRMA\\    ← CONNECT RADNI FOLDER
          backup\\                  ← automatski backup prije svake operacije
              Storage_2026-03-11_08-30.mdb
              Storage_2026-03-11_08-30.mdb.sha256
          work\\                    ← radna kopija za sav R/W rad
              Storage_work.mdb
              Journal_work.mdb
          export\\                  ← JSON export iz ERP-a
              export_2026-03-11_08-30.json
          connect_log.txt          ← log svakog sync-a

    TOK UVOZA  (Synesis → ERP):
      Original → backup/ → work kopija → čitaj SQL → POST na API

    TOK IZVOZA (ERP → Synesis):
      GET export queue → work kopija → upiši u work → provjeri integritet
      → zamijeni original work kopijom → potvrdi ERP-u
    """
    slug = company.name.replace(' ', '_').replace('.', '').replace(',', '')[:20]
    connect_base = r"C:SynesisConnect"
    retention    = 30

    L = []
    def a(s=''): L.append(s)

    # ── Header ──────────────────────────────────────────────────────────
    a('#!/usr/bin/env python3')
    a('# -*- coding: utf-8 -*-')
    a('"""')
    a(f'synesis_sync.py — {company.name}')
    a(f'Generirano: {timezone.now().strftime("%d.%m.%Y %H:%M")}')
    a('')
    a('Instalacija: pip install pyodbc requests')
    a('Pokretanje:')
    a('  python synesis_sync.py              # sve (backup+uvoz+izvoz)')
    a('  python synesis_sync.py import       # samo uvoz Synesis -> ERP')
    a('  python synesis_sync.py export       # samo izvoz ERP -> Synesis')
    a('  python synesis_sync.py backup       # samo backup')
    a('  python synesis_sync.py status       # provjeri stanje')
    a('  python synesis_sync.py partners     # samo partneri')
    a('  python synesis_sync.py items        # samo artikli')
    a('  python synesis_sync.py pos          # samo POS kasa')
    a('"""')
    a('import sys, os, shutil, json, datetime, decimal, time, hashlib, logging')
    a('import pyodbc, requests')
    a()

    # ── Konfiguracija ────────────────────────────────────────────────────
    a('# =====================================================================')
    a('# KONFIGURACIJA')
    a('# =====================================================================')
    a()
    a('# --- ORIGINALNI SYNESIS FAJLOVI (SAMO ZA CITANJE / BACKUP) ---')
    a(f'STORAGE_ORIGINAL = r"{cfg.storage_db_path or r"C:\Synesis\FIRMA\Storage.mdb"}"')
    a(f'JOURNAL_ORIGINAL = r"{cfg.journal_db_path or r"C:\Synesis\FIRMA\Journal.mdb"}"')
    pos_db  = cfg.pos_db_path or ''
    pos_pwd = cfg.pos_db_password or ''
    a(f'POS_ORIGINAL     = r"{pos_db}"')
    a(f'POS_PWD          = "{pos_pwd}"')
    a()
    a('# --- CONNECT RADNI FOLDERI (automatski se kreiraju) ---')
    a(f'CONNECT_BASE  = r"{connect_base}"')
    a(f'FIRMA_SLUG    = "{slug}"')
    a('CONNECT_DIR   = os.path.join(CONNECT_BASE, FIRMA_SLUG)')
    a('BACKUP_DIR    = os.path.join(CONNECT_DIR, "backup")')
    a('WORK_DIR      = os.path.join(CONNECT_DIR, "work")')
    a('EXPORT_DIR    = os.path.join(CONNECT_DIR, "export")')
    a('LOG_FILE      = os.path.join(CONNECT_DIR, "connect_log.txt")')
    a()
    a('# --- RADNE KOPIJE (cijeli R/W ide ovdje) ---')
    a('STORAGE_WORK  = os.path.join(WORK_DIR, "Storage_work.mdb")')
    a('JOURNAL_WORK  = os.path.join(WORK_DIR, "Journal_work.mdb")')
    a()
    a('# --- API ---')
    a('API_URL       = "https://viskovic-group.de/api/synesis/import/"')
    a(f'API_TOKEN     = "{cfg.api_token}"')
    a(f'EXPORT_URL    = "https://viskovic-group.de/api/synesis/export/{cfg.api_token}/"')
    a(f'CONFIRM_URL   = "https://viskovic-group.de/api/synesis/export/{cfg.api_token}/confirm/"')
    a('BATCH_SIZE    = 200')
    a(f'BACKUP_DAYS   = {retention}')
    a('DRIVER        = "Microsoft Access Driver (*.mdb, *.accdb)"')
    a()

    # ── Logger ───────────────────────────────────────────────────────────
    a('# =====================================================================')
    a('# LOGGER')
    a('# =====================================================================')
    a('def _setup_log():')
    a('    os.makedirs(CONNECT_DIR, exist_ok=True)')
    a('    fmt = "%(asctime)s [%(levelname)s] %(message)s"')
    a('    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[')
    a('        logging.FileHandler(LOG_FILE, encoding="utf-8"),')
    a('        logging.StreamHandler(sys.stdout),')
    a('    ])')
    a('    return logging.getLogger("synesis")')
    a('log = _setup_log()')
    a()

    # ── Helper funkcije ──────────────────────────────────────────────────
    a('def json_serial(o):')
    a('    if isinstance(o, datetime.datetime): return o.strftime("%Y-%m-%d %H:%M:%S")')
    a('    if isinstance(o, datetime.date):     return o.strftime("%Y-%m-%d")')
    a('    if isinstance(o, decimal.Decimal):   return float(o)')
    a('    return str(o)')
    a()
    a('def safe(v):')
    a('    if v is None: return None')
    a('    if isinstance(v, float) and v == int(v): return int(v)')
    a('    s = str(v).strip(); return s if s else None')
    a()
    a('def file_hash(path):')
    a('    h = hashlib.sha256()')
    a('    with open(path, "rb") as f:')
    a('        for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)')
    a('    return h.hexdigest()')
    a()
    a('def ensure_dirs():')
    a('    for d in [CONNECT_DIR, BACKUP_DIR, WORK_DIR, EXPORT_DIR]:')
    a('        os.makedirs(d, exist_ok=True)')
    a()
    a('def send_batch(sync_type, data):')
    a('    hdrs = {"Content-Type": "application/json", "Authorization": f"Token {API_TOKEN}"}')
    a('    pl   = json.dumps({"type": sync_type, "data": data}, default=json_serial, ensure_ascii=False)')
    a('    try:')
    a('        r = requests.post(API_URL, data=pl.encode("utf-8"), headers=hdrs, timeout=120)')
    a('        return r.json()')
    a('    except Exception as e:')
    a('        log.error(f"API greska ({sync_type}): {e}"); return {"error": str(e)}')
    a()

    # ── BACKUP ───────────────────────────────────────────────────────────
    a('# =====================================================================')
    a('# BACKUP — uvijek prvi korak, nikad se ne preskace')
    a('# =====================================================================')
    a('def make_backup(src, label):')
    a('    if not os.path.exists(src):')
    a('        log.warning(f"  Original ne postoji: {src}"); return None')
    a('    ts  = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")')
    a('    dst = os.path.join(BACKUP_DIR, f"{label}_{ts}.mdb")')
    a('    try:')
    a('        shutil.copy2(src, dst)')
    a('        h = file_hash(dst)')
    a('        with open(dst + ".sha256", "w") as f: f.write(h)')
    a('        log.info(f"  Backup: {dst}")')
    a('        log.info(f"  SHA256: {h[:16]}...")')
    a('        return dst')
    a('    except Exception as e:')
    a('        log.error(f"  BACKUP NIJE USPIO: {e}"); return None')
    a()
    a('def cleanup_backups():')
    a('    cutoff = datetime.datetime.now() - datetime.timedelta(days=BACKUP_DAYS)')
    a('    rm = 0')
    a('    if not os.path.isdir(BACKUP_DIR): return')
    a('    for fn in os.listdir(BACKUP_DIR):')
    a('        fp = os.path.join(BACKUP_DIR, fn)')
    a('        if os.path.isfile(fp) and datetime.datetime.fromtimestamp(os.path.getmtime(fp)) < cutoff:')
    a('            os.remove(fp); rm += 1')
    a('    if rm: log.info(f"  Obrisano starih backupa: {rm}")')
    a()
    a('def do_backup():')
    a('    log.info("\\n=== BACKUP ===")')
    a('    r = make_backup(STORAGE_ORIGINAL, "Storage")')
    a('    make_backup(JOURNAL_ORIGINAL, "Journal")')
    a('    if POS_ORIGINAL: make_backup(POS_ORIGINAL, "POS")')
    a('    if r is None and os.path.exists(STORAGE_ORIGINAL):')
    a('        log.error("KRITICNO: Storage backup nije uspio. Sync prekinut.")')
    a('        sys.exit(1)')
    a('    cleanup_backups()')
    a()

    # ── WORK KOPIJA ──────────────────────────────────────────────────────
    a('# =====================================================================')
    a('# RADNA KOPIJA — sav R/W rad ovdje, nikad u originalu')
    a('# =====================================================================')
    a('def make_work_copy():')
    a('    log.info("\\n--- Kreiranje radne kopije ---")')
    a('    if os.path.exists(STORAGE_ORIGINAL):')
    a('        shutil.copy2(STORAGE_ORIGINAL, STORAGE_WORK)')
    a('        log.info(f"  Storage work: {STORAGE_WORK}")')
    a('    if os.path.exists(JOURNAL_ORIGINAL):')
    a('        shutil.copy2(JOURNAL_ORIGINAL, JOURNAL_WORK)')
    a('        log.info(f"  Journal work: {JOURNAL_WORK}")')
    a()
    a('def conn_s(): return pyodbc.connect(f"DRIVER={{{DRIVER}}};DBQ={STORAGE_WORK};")')
    a('def conn_j(): return pyodbc.connect(f"DRIVER={{{DRIVER}}};DBQ={JOURNAL_WORK};")')
    a()

    # ── UVOZ Synesis → ERP ───────────────────────────────────────────────
    a('# =====================================================================')
    a('# UVOZ: Synesis -> ERP')
    a('# =====================================================================')
    a('def sync_partners():')
    a('    log.info("\\n[PARTNERI] Synesis -> ERP")')
    a('    c = conn_s(); cur = c.cursor()')
    a('    cur.execute("""')
    a('        SELECT PARTNER_ID, PARTNER_NAME, PARTNER_VATNUMBER, PARTNER_STREET,')
    a('               CITY_NAME, CITY_ZIPCODE, PARTNER_EMAIL, PARTNER_PHONE,')
    a('               PARTNER_MOBILE, PARTNER_WEB, INT_COUNTRYID,')
    a('               PARTNER_DISCOUNTRATE, PARTNER_PAYMENTDAYS, PARTNER_TYPE')
    a('        FROM PARTNERS WHERE PARTNER_NAME IS NOT NULL ORDER BY PARTNER_ID')
    a('    """)')
    a('    cols = [d[0] for d in cur.description]')
    a('    rows = [dict(zip(cols, [safe(v) for v in row])) for row in cur.fetchall()]')
    a('    c.close()')
    a('    log.info(f"  Pronasao: {len(rows)} partnera")')
    a('    cr=up=er=0')
    a('    for i in range(0, len(rows), BATCH_SIZE):')
    a('        res = send_batch("partners", rows[i:i+BATCH_SIZE])')
    a('        cr+=res.get("created",0); up+=res.get("updated",0); er+=res.get("errors",0)')
    a('    log.info(f"  Kreirano:{cr} Azurirano:{up} Greske:{er}")')
    a()
    a('def sync_items():')
    a('    log.info("\\n[ARTIKLI] Synesis -> ERP")')
    a('    c = conn_s(); cur = c.cursor()')
    a('    cur.execute("""')
    a('        SELECT ITEM_ID, ITEM_NAME, ITEM_MEASURE, ITEM_BARCODE,')
    a('               ITEM_NETPRICE, VAT_RATE, ITEM_PRICE,')
    a('               ITEMGROUP_NAME, ITEM_TYPE, NKPID, ITEM_REMARK')
    a('        FROM ITEMS WHERE ITEM_NAME IS NOT NULL ORDER BY ITEM_ID')
    a('    """)')
    a('    cols = [d[0] for d in cur.description]')
    a('    rows = [dict(zip(cols, [safe(v) for v in row])) for row in cur.fetchall()]')
    a('    c.close()')
    a('    log.info(f"  Pronasao: {len(rows)} artikala")')
    a('    cr=up=er=0')
    a('    for i in range(0, len(rows), BATCH_SIZE):')
    a('        res = send_batch("items", rows[i:i+BATCH_SIZE])')
    a('        cr+=res.get("created",0); up+=res.get("updated",0); er+=res.get("errors",0)')
    a('    log.info(f"  Kreirano:{cr} Azurirano:{up} Greske:{er}")')
    a()
    a('def sync_pos():')
    a('    if not POS_ORIGINAL: return')
    a('    log.info("\\n[POS KASA] Synesis -> ERP")')
    a('    pos_work = os.path.join(WORK_DIR, "POS_work.mdb")')
    a('    shutil.copy2(POS_ORIGINAL, pos_work)')
    a('    cs = f"DRIVER={{{DRIVER}}};DBQ={pos_work};PWD={POS_PWD};" if POS_PWD else f"DRIVER={{{DRIVER}}};DBQ={pos_work};"')
    a('    conn = pyodbc.connect(cs); cur = conn.cursor()')
    a('    pos_name = "Kasa"')
    a('    try:')
    a('        cur.execute("SELECT ValueString FROM Settings WHERE [Key]=\'POSName\'")')
    a('        r = cur.fetchone()')
    a('        if r: pos_name = r[0] or "Kasa"')
    a('    except: pass')
    a('    cutoff = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")')
    a('    rows = []')
    a('    try:')
    a('        cur.execute(')
    a('            "SELECT Receipt_ID, Receipt_Date, Receipt_Ammount, Receipt_VATAmmout,"')
    a('            " Receipt_PaymentType, Receipt_ZKI, Receipt_JIR, Receipt_Customer"')
    a('            " FROM Receipts WHERE Receipt_Date >= ? ORDER BY Receipt_Date", cutoff)')
    a('        cols = [d[0] for d in cur.description]')
    a('        rows = [dict(zip(cols, [safe(v) for v in r])) for r in cur.fetchall()]')
    a('    except Exception as ex: log.warning(f"  POS upozorenje: {ex}")')
    a('    conn.close()')
    a('    try: os.remove(pos_work)')
    a('    except: pass')
    a('    log.info(f"  Pronasao: {len(rows)} POS bonova")')
    a('    if rows:')
    a('        res = send_batch("pos", {"pos_name": pos_name, "receipts": rows, "totals": []})')
    a('        log.info(f"  Prihod danas:{res.get(\'revenue_today\',0)} tjedan:{res.get(\'revenue_week\',0)} mj:{res.get(\'revenue_month\',0)}")')
    a()

    # ── IZVOZ ERP → Synesis ─────────────────────────────────────────────
    a('# =====================================================================')
    a('# IZVOZ: ERP -> Synesis (s backup zastltom, pise samo u work kopiju)')
    a('# =====================================================================')
    a('def fetch_export():')
    a('    log.info("\\n[IZVOZ] Provjera ERP export queue...")')
    a('    try:')
    a('        r = requests.get(EXPORT_URL, timeout=30)')
    a('        data = r.json()')
    a('        n = len(data.get("items",[])) + len(data.get("partners",[])) + len(data.get("pkv",[])) + len(data.get("calculations",[]))')
    a('        log.info(f"  Pronasao {n} zapisa za izvoz")')
    a('        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")')
    a('        with open(os.path.join(EXPORT_DIR, f"export_{ts}.json"), "w", encoding="utf-8") as f:')
    a('            json.dump(data, f, default=json_serial, ensure_ascii=False, indent=2)')
    a('        return data')
    a('    except Exception as e:')
    a('        log.error(f"  Greska pri dohvatu exporta: {e}")')
    a('        return {}')
    a()
    a('def write_to_work(data):')
    a('    """Pise ERP promjene u WORK kopiju — nikad u original."""')
    a('    items    = data.get("items", [])')
    a('    partners = data.get("partners", [])')
    a('    pkv_list = data.get("pkv", [])')
    a('    calcs    = data.get("calculations", [])')
    a('    if not any([items, partners, pkv_list, calcs]):')
    a('        log.info("  Nema podataka za izvoz iz ERP-a."); return True, []')
    a('    log.info(f"\\n--- Pisanje u WORK kopiju ({len(items)} artikala, {len(partners)} partnera, {len(pkv_list)} PKV, {len(calcs)} kalkulacija) ---")')
    a('    confirmed_ids = []')
    a('    ok = er = 0')
    a()
    a('    # Artikli')
    a('    if items:')
    a('        c = conn_s(); cur = c.cursor()')
    a('        for item in items:')
    a('            try:')
    a('                act = item.get("action","update"); fld = item.get("fields",{}); sid = item.get("synesis_id",""); qid = item.get("queue_id")')
    a('                if act == "update" and sid:')
    a('                    sets = ", ".join(f"{k}=?" for k in fld)')
    a('                    cur.execute(f"UPDATE ITEMS SET {sets} WHERE ITEM_ID=?", list(fld.values())+[int(sid)])')
    a('                    log.info(f"  UPDATE ITEMS #{sid}: {list(fld.keys())}")')
    a('                elif act == "insert":')
    a('                    cols = ", ".join(fld.keys()); phs = ", ".join(["?"]*len(fld))')
    a('                    cur.execute(f"INSERT INTO ITEMS ({cols}) VALUES ({phs})", list(fld.values()))')
    a('                    log.info(f"  INSERT ITEMS: {fld.get(\'ITEM_NAME\',\'?\')}")')
    a('                confirmed_ids.append(qid); ok+=1')
    a('            except Exception as e: log.warning(f"  GRESKA artikl: {e}"); er+=1')
    a('        c.commit(); c.close()')
    a()
    a('    # Partneri')
    a('    if partners:')
    a('        c = conn_s(); cur = c.cursor()')
    a('        for p in partners:')
    a('            try:')
    a('                act = p.get("action","update"); fld = p.get("fields",{}); sid = p.get("synesis_id",""); qid = p.get("queue_id")')
    a('                if act == "update" and sid:')
    a('                    sets = ", ".join(f"{k}=?" for k in fld)')
    a('                    cur.execute(f"UPDATE PARTNERS SET {sets} WHERE PARTNER_ID=?", list(fld.values())+[int(sid)])')
    a('                    log.info(f"  UPDATE PARTNERS #{sid}")')
    a('                elif act == "insert":')
    a('                    cols = ", ".join(fld.keys()); phs = ", ".join(["?"]*len(fld))')
    a('                    cur.execute(f"INSERT INTO PARTNERS ({cols}) VALUES ({phs})", list(fld.values()))')
    a('                    log.info(f"  INSERT PARTNERS: {fld.get(\'PARTNER_NAME\',\'?\')}")')
    a('                confirmed_ids.append(qid); ok+=1')
    a('            except Exception as e: log.warning(f"  GRESKA partner: {e}"); er+=1')
    a('        c.commit(); c.close()')
    a()
    a('    # PKV primke')
    a('    if pkv_list:')
    a('        cs = conn_s(); cj = conn_j()')
    a('        curs = cs.cursor(); curj = cj.cursor()')
    a('        curs.execute("SELECT MAX(TRANCODE) FROM RETAIL")')
    a('        next_tc = int(curs.fetchone()[0] or 0) + 1')
    a('        for pkv in pkv_list:')
    a('            try:')
    a('                fld=pkv.get("fields",{}); qid=pkv.get("queue_id")')
    a('                erp_id=(fld.get("erp_tranid") or f"ERPPKV-{fld.get(\'calculation_id\',qid)}")[:50]')
    a('                curs.execute("SELECT DIN,TRANCODE FROM RETAIL WHERE REMARK=? AND TRANID=\'PKVINPUT\'",[erp_id])')
    a('                ex=curs.fetchone()')
    a('                td=datetime.datetime.now()')
    a('                desc=(fld.get("DESCRIPTION") or "")[:30]; vendor=(fld.get("VENDOR_NAME") or "")[:50]')
    a('                docnum=(fld.get("DOCUMENT_NUMBER") or "")[:15]')
    a('                rid=int(fld.get("RETAIL_ID",1)); net=float(fld.get("ITEM_TOTALPURCHASEVALUE",0)); mpc=float(fld.get("RET_TOTALINPUT",0))')
    a('                if ex:')
    a('                    curs.execute("UPDATE RETAIL SET DESCRIPTION=?,VENDOR_NAME=?,DOCUMENT_NUMBER=?,DOCUMENT_DATE=?,ITEM_TOTALPURCHASEVALUE=?,RET_TOTALINPUT=? WHERE DIN=?",[desc,vendor,docnum,td,net,mpc,ex[0]])')
    a('                    log.info(f"  UPDATE PKV RETAIL DIN={ex[0]}")')
    a('                else:')
    a('                    curs.execute("INSERT INTO RETAIL (PRIORITY,TRANCODE,RETAIL_ID,TRANDATE,FOND,DESCRIPTION,VENDOR_NAME,DOCUMENT_NUMBER,DOCUMENT_DATE,ITEM_TOTALPURCHASEVALUE,RET_TOTALINPUT,CONID,SE_CONTROLLER,SE_PKVPRINTTYPE,SE_RETPRINTDISCOUNT,SE_RETPRINTPROFITRATE,SE_RETPRINTPROFIT,SE_JUMPMARGIN,SE_RETAILPRICE,SE_RETAILACCOUNT,SE_RETAILVATACCOUNT,SE_RETAILVAT10ACCOUNT,SE_RETAILVAT5ACCOUNT,SE_RETAILPROFITACCOUNT,SE_RETNONINVOICED,SE_PACKRETACCOUNT,REMARK,TRANID,TRANVERSION,CHECKED) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[2,next_tc,rid,td,1,desc,vendor,docnum,td,net,mpc,"1","1",1,1,1,1,1,1,"66001","664","664","664","668","6500","6500",erp_id,"PKVINPUT","1.00",False])')
    a('                    try:')
    a('                        curj.execute("INSERT INTO Journal (DOCUMENT,DOCUMENT_ID,DOCUMENT_NUMBER,DOCUMENT_KEY,DOCUMENT_PRIORITY,DOCUMENT_CREATED,DOCUMENT_PARTNER,DOCUMENT_DATE,DOCUMENT_AMMOUNT,DOCUMENT_DESCRIPTION,ITEMS_RECORDS,DOCUMENT_INVALID,CHECKED,MEMOPRINT,MEMOALARM,EXPORTED) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",["RETAIL",str(next_tc),next_tc,f"RETAIL|{next_tc}",1,td,vendor,td,mpc,f"PKV iz ERP-a: {desc}"[:50],1,False,False,False,False,False])')
    a('                    except Exception as jex: log.warning(f"  UPOZ PKV Journal: {jex}")')
    a('                    log.info(f"  INSERT PKV #{next_tc}: {desc} nab={net:.2f} MPC={mpc:.2f}")')
    a('                    next_tc+=1')
    a('                confirmed_ids.append(qid); ok+=1')
    a('            except Exception as e: log.warning(f"  GRESKA PKV: {e}"); er+=1')
    a('        cs.commit(); cj.commit(); cs.close(); cj.close()')
    a()
    a('    # Kalkulacije/ponude')
    a('    if calcs:')
    a('        cs = conn_s(); cj = conn_j()')
    a('        curs = cs.cursor(); curj = cj.cursor()')
    a('        curs.execute("SELECT MAX(OFFER_NUMBER) FROM OFFERS")')
    a('        next_on = int(curs.fetchone()[0] or 0) + 1')
    a('        for calc in calcs:')
    a('            try:')
    a('                fld=calc.get("fields",{}); qid=calc.get("queue_id"); act=calc.get("action","insert"); sid=calc.get("synesis_id","")')
    a('                pname=fld.get("project_name","Kalkulacija"); cname=(fld.get("client_name","") or "")[:50]')
    a('                net=float(fld.get("offer_total_net",0)); gross=float(fld.get("offer_total_vat",0))')
    a('                vat=round(gross-net,2); vpct=int(fld.get("vat_percent",25))')
    a('                remark=f"ERP kalk #{fld.get(\'calculation_id\',\'\')} | {pname}"[:50]')
    a('                od=datetime.datetime.now()')
    a('                tranid=f"ERP-{fld.get(\'calculation_id\',qid)}"')
    a('                vb25=net if vpct==25 else 0; v25=vat if vpct==25 else 0')
    a('                vb10=net if vpct==10 else 0; v10=vat if vpct==10 else 0')
    a('                vb5 =net if vpct==5  else 0; v5 =vat if vpct==5  else 0')
    a('                if act=="update" and sid:')
    a('                    curs.execute("UPDATE OFFERS SET CUSTOMER_NAME=?,INVOICETOTAL=?,VAT_BASE25=?,VAT_25=?,VAT_BASE10=?,VAT_10=?,VAT_BASE5=?,VAT_5=?,VAT_INVOICEAMMOUNT=?,VAT_INVOICENETAMMOUNT=?,VAT_NETINVOICE=?,VAT_BASE=?,VAT_AMMOUNT=?,REMARK=? WHERE DIN=?",[cname,gross,vb25,v25,vb10,v10,vb5,v5,gross,net,net,net,vat,remark,int(sid)])')
    a('                else:')
    a('                    curs.execute("SELECT DIN,OFFER_NUMBER FROM OFFERS WHERE TRANID=?",[tranid])')
    a('                    ex=curs.fetchone()')
    a('                    if ex:')
    a('                        curs.execute("UPDATE OFFERS SET CUSTOMER_NAME=?,INVOICETOTAL=?,VAT_BASE25=?,VAT_25=?,VAT_BASE10=?,VAT_10=?,VAT_BASE5=?,VAT_5=?,VAT_INVOICEAMMOUNT=?,VAT_INVOICENETAMMOUNT=?,VAT_NETINVOICE=?,VAT_BASE=?,VAT_AMMOUNT=?,REMARK=? WHERE DIN=?",[cname,gross,vb25,v25,vb10,v10,vb5,v5,gross,net,net,net,vat,remark,ex[0]])')
    a('                    else:')
    a('                        curs.execute("INSERT INTO OFFERS (PRIORITY,OFFER_NUMBER,OFFER_DATE,CUSTOMER_ID,CUSTOMER_NAME,INVOICETOTAL,VAT_BASE25,VAT_25,VAT_BASE10,VAT_10,VAT_BASE5,VAT_5,VAT_INVOICEAMMOUNT,VAT_INVOICENETAMMOUNT,VAT_NETINVOICE,VAT_BASE,VAT_AMMOUNT,REST_AMMOUNT,REMARK,OFFER_VALIDDAYS,OFFER_VALIDDATE,TRANID,TRANVERSION,CHECKED) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[1,next_on,od,0,cname,gross,vb25,v25,vb10,v10,vb5,v5,gross,net,net,net,vat,gross,remark,30,od+datetime.timedelta(days=30),tranid,"1.0",False])')
    a('                        try:')
    a('                            curj.execute("INSERT INTO Journal (DOCUMENT,DOCUMENT_ID,DOCUMENT_NUMBER,DOCUMENT_KEY,DOCUMENT_PRIORITY,DOCUMENT_CREATED,DOCUMENT_PARTNER,DOCUMENT_DATE,DOCUMENT_AMMOUNT,DOCUMENT_DESCRIPTION,ITEMS_RECORDS,DOCUMENT_INVALID,CHECKED,MEMOPRINT,MEMOALARM,EXPORTED) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",["OFFERS",str(next_on),next_on,f"OFFERS|{next_on}",1,od,cname,od,gross,f"Ponuda iz ERP-a: {pname}"[:50],0,False,False,False,False,False])')
    a('                        except Exception as jex: log.warning(f"  UPOZ Journal: {jex}")')
    a('                        next_on+=1')
    a('                confirmed_ids.append(qid); ok+=1')
    a('            except Exception as e: log.warning(f"  GRESKA kalk: {e}"); er+=1')
    a('        cs.commit(); cj.commit(); cs.close(); cj.close()')
    a()
    a('    log.info(f"  Upisano u work: {ok} | Greske: {er}")')
    a('    return er == 0, confirmed_ids')
    a()
    a('def apply_work_to_original(confirmed_ids):')
    a('    """')
    a('    Zadnji korak: zamijeni original work kopijom.')
    a('    Ako ne uspije, original ostaje netaknut.')
    a('    """')
    a('    log.info("\\n--- Primjena work kopije na original ---")')
    a('    emg = STORAGE_WORK + ".emg"')
    a('    try:')
    a('        shutil.copy2(STORAGE_ORIGINAL, emg)  # emergency backup')
    a('        shutil.copy2(STORAGE_WORK, STORAGE_ORIGINAL)')
    a('        # Provjeri da original radi')
    a('        c = pyodbc.connect(f"DRIVER={{{DRIVER}}};DBQ={STORAGE_ORIGINAL};")')
    a('        c.cursor().execute("SELECT COUNT(*) FROM ITEMS"); c.close()')
    a('        os.remove(emg)')
    a('        log.info("  Original uspjesno azuriran.")')
    a('        # Potvrdi ERP-u')
    a('        try:')
    a('            requests.post(CONFIRM_URL, json={"confirmed_ids": confirmed_ids}, headers={"Content-Type":"application/json"}, timeout=30)')
    a('            log.info(f"  ERP potvrden o {len(confirmed_ids)} zapisa.")')
    a('        except Exception as ce: log.warning(f"  Potvrda ERP nije uspjela: {ce}")')
    a('        return True')
    a('    except Exception as e:')
    a('        log.error(f"  KRITICNO: Zamjena originala nije uspjela: {e}")')
    a('        if os.path.exists(emg):')
    a('            try: shutil.copy2(emg, STORAGE_ORIGINAL); log.info("  Original restauriran.")')
    a('            except Exception as e2: log.error(f"  RUCNO KOPIRAJ: {emg} -> {STORAGE_ORIGINAL}\\n  Greska: {e2}")')
    a('        return False')
    a()
    a('def sync_from_erp():')
    a('    """Izvoz ERP -> Synesis. Sve operacije idu kroz work kopiju."""')
    a('    data = fetch_export()')
    a('    total = sum(len(data.get(k,[])) for k in ["items","partners","pkv","calculations"])')
    a('    if total == 0:')
    a('        log.info("  Nema promjena iz ERP-a."); return')
    a('    make_work_copy()')
    a('    ok, confirmed = write_to_work(data)')
    a('    if ok:')
    a('        apply_work_to_original(confirmed)')
    a('    else:')
    a('        log.error("  Izvoz nije primjenjen zbog gresaka u pisanju.")')
    a()

    # ── STATUS ───────────────────────────────────────────────────────────
    a('def check_status():')
    a('    log.info("\\n=== STATUS ===")')
    a('    for name, path in [("Storage original", STORAGE_ORIGINAL), ("Journal original", JOURNAL_ORIGINAL)]:')
    a('        ex = os.path.exists(path)')
    a('        sz = os.path.getsize(path)//1024 if ex else 0')
    a('        log.info(f"  {name}: {\'OK \'+str(sz)+\'KB\' if ex else \'NE POSTOJI\'}")')
    a('    nbu = len([f for f in os.listdir(BACKUP_DIR) if f.endswith(".mdb")]) if os.path.isdir(BACKUP_DIR) else 0')
    a('    log.info(f"  Backup fajlova: {nbu} (cuvamo {BACKUP_DAYS} dana)")')
    a('    log.info(f"  Connect folder: {CONNECT_DIR}")')
    a()

    # ── MAIN ─────────────────────────────────────────────────────────────
    a('if __name__ == "__main__":')
    a('    mode = sys.argv[1] if len(sys.argv) > 1 else "all"')
    a('    ensure_dirs()')
    a('    t0 = time.time()')
    a('    log.info(f"\\n{\'=\'*60}")')
    a(f'    log.info("LIMIT Connect Synesis Sync — {company.name}")')
    a('    log.info(f"Nacin: {mode} | {datetime.datetime.now().strftime(\'%d.%m.%Y %H:%M\')}")')
    a('    log.info(f"{\'=\'*60}")')
    a('    if   mode == "status":  check_status()')
    a('    elif mode == "backup":  do_backup()')
    a('    elif mode == "partners": do_backup(); make_work_copy(); sync_partners()')
    a('    elif mode == "items":   do_backup(); make_work_copy(); sync_items()')
    a('    elif mode == "pos":     do_backup(); make_work_copy(); sync_pos()')
    a('    elif mode == "import":  do_backup(); make_work_copy(); sync_partners(); sync_items(); sync_pos()')
    a('    elif mode == "export":  do_backup(); sync_from_erp()')
    a('    else:  # all')
    a('        do_backup()')
    a('        make_work_copy()')
    a('        sync_partners()')
    a('        sync_items()')
    a('        sync_pos()')
    a('        sync_from_erp()')
    a('    log.info(f"\\nGOTOVO za {time.time()-t0:.1f}s")')

    return '\n'.join(L) + '\n'

# ── import API ─────────────────────────────────────────────────────────────────

# CSRF exempt: token-authenticated API endpoint
@csrf_exempt
def synesis_import_api(request):
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
    elif sync_type == "pkv_probe":
        result = _import_pkv_probe(company, data)
    elif sync_type == "schema_probe":
        result = _import_schema_probe(company, data)
    elif sync_type == "invoices":
        created, updated, errors = _import_invoices(request, company, data if isinstance(data, list) else data.get("invoices", []))
        result = {"created": created, "updated": updated, "errors": errors}
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
    elif sync_type == "pos":
        pass  # _import_pos updates cfg directly

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



def _import_pos(company, data):
    """Process POS receipts data - updates summary stats in SynesisConfig."""
    import datetime

    from django.utils import timezone

    receipts = data.get("receipts", [])
    pos_name = data.get("pos_name", "Kasa")

    now = timezone.now()
    today = now.date()
    week_ago  = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)
    revenue_today = revenue_week = revenue_month = 0.0

    for r in receipts:
        try:
            amt = float(r.get("Receipt_Ammount") or 0)
            date_str = str(r.get("Receipt_Date") or "")[:10]
            try:
                receipt_date = datetime.date.fromisoformat(date_str)
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
        cfg.pos_revenue_today  = round(revenue_today,  2)
        cfg.pos_revenue_week   = round(revenue_week,   2)
        cfg.pos_revenue_month  = round(revenue_month,  2)
        cfg.last_sync_pos = now
        cfg.save(update_fields=[
            "pos_name", "pos_receipts_total",
            "pos_revenue_today", "pos_revenue_week", "pos_revenue_month",
            "last_sync_pos", "updated_at",
        ])
    except ObjectDoesNotExist as exc:
        return {"error": str(exc), "received": len(receipts)}

    return {
        "received": len(receipts),
        "revenue_today":  round(revenue_today,  2),
        "revenue_week":   round(revenue_week,   2),
        "revenue_month":  round(revenue_month,  2),
        "pos_name": pos_name,
    }

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
                _, was_created = Partner.objects.update_or_create(
                    company=company, oib=oib, defaults=defaults)
            else:
                # No OIB — lookup by name, skip oib in unique key
                defaults["oib"] = ""
                try:
                    obj = Partner.objects.get(company=company, name=name)
                    for k, v in defaults.items():
                        setattr(obj, k, v)
                    obj.save()
                    was_created = False
                except Partner.DoesNotExist:
                    # Generate a placeholder oib to satisfy unique constraint
                    defaults["oib"] = f"SYN-{row.get('PARTNER_ID', '').strip() or name[:8]}"
                    obj = Partner.objects.create(company=company, name=name, **{k: v for k, v in defaults.items() if k != 'name'})
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
    return {"created": created, "updated": updated, "errors": errors,
            "total_in_db": total, "error_detail": "\n".join(error_msgs[:10])}


def _import_items(company, data):
    from companies.models import TaxRate
    from inventory.models import InventoryItem

    vat_map = {int(tr.rate): tr for tr in TaxRate.objects.all()}

    created = updated = errors = 0
    error_msgs = []

    for row in data:
        try:
            name = (row.get("ITEM_NAME") or "").strip()
            if not name:
                continue
            synesis_id = str(row.get("ITEM_ID") or "").strip()
            sku = "SYN-" + synesis_id if synesis_id else ""
            unit = (row.get("ITEM_MEASURE") or "kom").strip().lower()
            barcode = (row.get("ITEM_BARCODE") or "").strip()
            vat_num = int(row.get("VAT_RATE") or 25)
            if vat_num == 10:
                vat_num = 13
            tax_rate_obj = vat_map.get(vat_num) or vat_map.get(25)
            unit_price = float(row.get("ITEM_NETPRICE") or 0)
            gross_price = float(row.get("ITEM_PRICE") or 0)
            category = (row.get("ITEMGROUP_NAME") or "").strip()
            description = (row.get("ITEM_REMARK") or "").strip()

            if not sku:
                errors += 1
                continue
            defaults = {
                "name": name,
                "unit": unit,
                "barcode": barcode,
                "unit_price": gross_price or unit_price,
                "purchase_price": unit_price,
                "tax_rate": tax_rate_obj,
                "description": (category + " - " if category else "") + description,
            }
            _, was_created = InventoryItem.objects.update_or_create(
                company=company, sku=sku, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1
        except (ValueError, TypeError) as exc:
            errors += 1
            error_msgs.append(str(exc)[:200])

    total = InventoryItem.objects.filter(company=company).count()
    return {"created": created, "updated": updated, "errors": errors,
            "total_in_db": total, "error_detail": "\n".join(error_msgs[:10])}


# Extra views to append to synesis/views.py

# ── public script download (token in URL) ─────────────────────────────────────

def download_script_public(request, token):
    """No login required — token in URL authenticates the request."""
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

@login_required
def download_setup_bat(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect("synesis:settings")
    cfg = _get_config(company)
    bat = _build_setup_bat(cfg, company)
    response = HttpResponse(bat, content_type="text/plain; charset=windows-1250")
    response["Content-Disposition"] = 'attachment; filename="synesis_setup.bat"'
    return response


def _build_setup_bat(cfg, company):
    token = cfg.api_token
    script_url = "https://viskovic-group.de/api/synesis/script/{}/".format(token)
    company_name = company.name.replace('"', '')
    lines = [
        "@echo off",
        "chcp 65001 > nul",
        "setlocal",
        "",
        "echo ============================================",
        'echo  LIMIT Connect - Synesis automatska sync',
        'echo  Tvrtka: {}'.format(company_name),
        "echo ============================================",
        "echo.",
        "",
        ":: Provjeri Python",
        'set "PYTHON="',
        'where python > nul 2>&1',
        'if not errorlevel 1 set "PYTHON=python"',
        'if not defined PYTHON (',
        '    where py > nul 2>&1',
        '    if not errorlevel 1 set "PYTHON=py"',
        ')',
        'if not defined PYTHON (',
        '    echo [GRESKA] Python nije pronaDen!',
        '    echo.',
        '    echo Instalirajte Python s: https://www.python.org/downloads/',
        '    echo Kod instalacije OBAVEZNO oznacite "Add Python to PATH"',
        '    echo Zatim pokrenite ovaj setup ponovo.',
        '    echo.',
        '    pause',
        '    exit /b 1',
        ')',
        'echo [OK] Python pronaDen',
        "echo.",
        "",
        ":: Instaliraj pakete",
        'echo [1/4] Instalacija potrebnih paketa (pyodbc, requests)...',
        '%PYTHON% -m pip install pyodbc requests --quiet --upgrade',
        'if errorlevel 1 (',
        '    echo [GRESKA] Instalacija paketa neuspjesna!',
        '    pause',
        '    exit /b 1',
        ')',
        'echo [OK] Paketi instalirani',
        "echo.",
        "",
        ":: Preuzmi sync skriptu",
        'echo [2/4] Preuzimanje sync skripte s portala...',
        'set "SYNC_SCRIPT=%~dp0synesis_sync.py"',
        'curl -s -f -o "%SYNC_SCRIPT%" "{}"'.format(script_url),
        'if errorlevel 1 (',
        '    echo [GRESKA] Preuzimanje skripte neuspjesno!',
        '    echo Provjerite internetsku vezu i pokusajte ponovo.',
        '    pause',
        '    exit /b 1',
        ')',
        'echo [OK] Skripta preuzeta',
        "echo.",
        "",
        ":: Kreiraj Scheduled Task (svaki dan u 02:00)",
        'echo [3/4] Postavljanje automatske sinkronizacije...',
        'schtasks /create /tn "FinaConnect-SynesisSync" /tr "\\"%PYTHON%\\" \\"%SYNC_SCRIPT%\\"" /sc daily /st 02:00 /f > nul 2>&1',
        'if errorlevel 1 (',
        '    echo [UPOZORENJE] Nije moguce kreirati automatski zadatak.',
        '    echo Pokrenite setup kao Administrator.',
        ') else (',
        '    echo [OK] Automatska sinkronizacija: svaki dan u 02:00',
        ')',
        "echo.",
        "",
        ":: Prva sinkronizacija",
        'echo [4/4] Pokrecemo prvu sinkronizaciju...',
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


# ── schema probe download ──────────────────────────────────────────────────────

@login_required
def download_schema_probe(request):
    """Download synesis_schema_probe.py — run on Windows to send us INVOICES schema."""
    import os
    probe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'synesis_schema_probe.py')
    try:
        with open(probe_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return HttpResponse("Skripta nije pronađena.", status=404)
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="synesis_schema_probe.py"'
    return response


# ── schema probe receiver (handles type=schema_probe in import API) ────────────

def _import_schema_probe(company, data):
    """
    Receive schema from Windows probe script.
    Saves to /tmp/synesis_schema_{company_id}.json for developer inspection.
    """
    import json as _json
    out_path = f'/tmp/synesis_schema_{company.pk}.json'
    payload = data[0] if data else {}
    with open(out_path, 'w', encoding='utf-8') as f:
        _json.dump(payload, f, indent=2, ensure_ascii=False)
    tables = payload.get('tables', [])
    schema = payload.get('schema', {})
    # Log key tables
    inv_tables = [t for t in tables if 'INV' in t.upper() or 'PONUD' in t.upper()]
    return {
        'received': len(tables),
        'created': 0,
        'updated': 0,
        'errors': 0,
        'invoice_tables': inv_tables,
        'saved_to': out_path,
        'total_in_db': 0,
    }


def _import_pkv_probe(company, data):
    """Receive PKV probe data — save to /tmp for developer inspection."""
    import json as _json
    out_path = f'/tmp/synesis_pkv_probe_{company.pk}.json'
    payload = data[0] if data else {}
    with open(out_path, 'w', encoding='utf-8') as f:
        _json.dump(payload, f, indent=2, ensure_ascii=False)
    transcodes = payload.get('trancode_retail', [])
    retail_ids = payload.get('retail_ids', [])
    return {
        'received': 1,
        'created': 0,
        'updated': 0,
        'errors': 0,
        'trancode_retail': transcodes,
        'retail_ids': retail_ids,
        'saved_to': out_path,
        'total_in_db': 0,
    }


@login_required
def download_pkv_probe(request):
    """Download synesis_read_pkv.py — čita PKV logiku iz Storage.mdb."""
    import os
    probe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'synesis_read_pkv.py')
    try:
        with open(probe_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return HttpResponse("Skripta nije pronađena.", status=404)
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="synesis_read_pkv.py"'
    return response


def _import_invoices(request, company, data_list):
    """Import faktura iz Synesis MDB (Storage.mdb INVOICES/INVOICEPO tablice)."""
    import hashlib
    from decimal import Decimal, InvalidOperation

    from django.utils import timezone

    from invoicing.models import Invoice, InvoiceItem
    from partners.models import Partner

    created = updated = errors = 0
    year = None

    for row in data_list:
        try:
            # Identifikacija
            synesis_id = str(row.get('TRANCODE', row.get('DIN', ''))).strip()
            year = row.get('_synesis_year', None)
            if not synesis_id:
                errors += 1
                continue

            # Duplikat provjera
            existing = Invoice.objects.filter(
                company=company,
                synesis_id=synesis_id,
                synesis_year=year,
            ).first()

            # Hash za integritet
            hash_input = f"{synesis_id}|{year}|{row.get('TRANDATE','')}|{row.get('CUSTOMER_NAME','')}|{row.get('INVOICE_TOTAL', 0)}"
            archive_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

            # Parse datuma
            date_str = str(row.get('TRANDATE', '')).strip()
            if date_str and date_str != 'None':
                from django.utils.dateparse import parse_date, parse_datetime
                date_issued = parse_datetime(date_str) or parse_date(date_str)
                if not date_issued:
                    # Fallback: Synesis US format MM/DD/YY HH:MM:SS
                    from datetime import datetime as _dt
                    for fmt in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%y", "%d.%m.%Y", "%Y-%m-%d"):
                        try:
                            date_issued = timezone.make_aware(_dt.strptime(date_str, fmt))
                            break
                        except ValueError:
                            continue
                if date_issued and not hasattr(date_issued, 'hour'):
                    from datetime import datetime as dt
                    date_issued = timezone.make_aware(dt.combine(date_issued, dt.min.time()))
                elif date_issued and timezone.is_naive(date_issued):
                    date_issued = timezone.make_aware(date_issued)
            else:
                date_issued = timezone.now()

            due_str = str(row.get('INVOICE_DUEDATE', '')).strip()
            date_due = None
            if due_str and due_str != 'None':
                from django.utils.dateparse import parse_date
                date_due = parse_date(due_str[:10]) if len(due_str) >= 10 else None
                if not date_due:
                    from datetime import datetime as _dt2
                    for fmt2 in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%y", "%d.%m.%Y"):
                        try:
                            date_due = _dt2.strptime(due_str, fmt2).date()
                            break
                        except ValueError:
                            continue

            # Partner
            partner_name = str(row.get('CUSTOMER_NAME', row.get('RET_CUSTOMERNAME', ''))).strip()
            partner_oib = str(row.get('PARTNER_VATNUMBER', row.get('RET_CUSTOMERVATNUMBER', ''))).strip()
            partner = None
            if partner_oib:
                partner = Partner.objects.filter(company=company, oib=partner_oib).first()
            if not partner and partner_name:
                partner = Partner.objects.filter(company=company, name__icontains=partner_name[:30]).first()

            # Iznosi
            def safe_dec(v):
                if v is None:
                    return Decimal('0')
                try:
                    return Decimal(str(v).replace(',', '.'))
                except (InvalidOperation, ValueError):
                    return Decimal('0')

            total = safe_dec(row.get('INVOICE_TOTAL', row.get('TOTAL', 0)))
            tax_amount = safe_dec(row.get('INVOICE_TAX', row.get('TAXAMOUNT', 0)))
            subtotal = total - tax_amount if total > tax_amount else total

            # Broj racuna
            invoice_number = str(row.get('INVOICE_NUMBER', '')).strip()
            if not invoice_number:
                invoice_number = f"SYN-{year or '0'}-{synesis_id}"

            # Protection date (11 years from issue)
            protection_date = None
            if date_issued:
                d = date_issued if hasattr(date_issued, 'date') else date_issued
                base = d.date() if hasattr(d, 'date') else d
                protection_date = base.replace(year=base.year + 11)

            if existing:
                if existing.archive_hash != archive_hash:
                    existing.archive_hash = archive_hash
                    existing.save(update_fields=['archive_hash'])
                    updated += 1
                continue

            # Ensure unique number
            base_number = invoice_number
            counter = 1
            while Invoice.objects.filter(number=invoice_number).exists():
                invoice_number = f"{base_number}-{counter}"
                counter += 1

            inv = Invoice.objects.create(
                company=company,
                number=invoice_number,
                doctype='R',
                country='HR',
                date_issued=date_issued,
                date_due=date_due,
                client_name=partner_name,
                client_address=str(row.get('PARTNER_STREET', '')).strip(),
                client_city=str(row.get('CITY_NAME', '')).strip(),
                client_oib=partner_oib,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total=total,
                status='PAID',
                source='synesis',
                synesis_id=synesis_id,
                synesis_year=year,
                archive_hash=archive_hash,
                is_locked=True,
                deletion_protected_until=protection_date,
                partner=partner,
                note=f'Uvezeno iz Synesis arhive ({year})',
                # Fiskalizacija
                jir=str(row.get('FIS_JIR', '')).strip() or None,
                zki=str(row.get('FIS_ZKI', '')).strip() or None,
                is_fiscalized=bool(row.get('FIS_JIR')),
            )

            # Import stavki ako postoje (TINVOICES/TINVOICEPO tablice)
            items_data = row.get('_items', [])
            for idx, item_row in enumerate(items_data):
                item_name = str(item_row.get('ITEM_NAME', item_row.get('DESCRIPTION', f'Stavka {idx+1}'))).strip()
                qty = safe_dec(item_row.get('ITEM_QTY', item_row.get('QTY', 1)))
                price = safe_dec(item_row.get('ITEM_PRICE', item_row.get('PRICE', 0)))
                item_tax = safe_dec(item_row.get('VAT_RATE', 25))
                item_total = qty * price
                InvoiceItem.objects.create(
                    invoice=inv,
                    description=item_name,
                    quantity=qty,
                    unit=str(item_row.get('ITEM_MEASURE', 'kom')).strip() or 'kom',
                    unit_price=price,
                    total_price=item_total,
                    tax_rate=item_tax,
                )

            created += 1

        except (ValueError, TypeError):
            errors += 1
            import traceback
            traceback.print_exc()

    # Update config
    # Update year config
    from .models import SynesisConfig, SynesisYearConfig
    cfg = SynesisConfig.objects.filter(company=company).select_related("company").first()
    if cfg:
        year = timezone.now().year
        yc, _ = SynesisYearConfig.objects.get_or_create(config=cfg, year=year)
        yc.last_sync_invoices = timezone.now()
        yc.invoices_total = Invoice.objects.filter(company=company, source='synesis', synesis_year=year).count()
        yc.save(update_fields=['last_sync_invoices', 'invoices_total'])

    return created, updated, errors






def _import_employees(company, rows):
    """Import employees from Synesis EMPLOYEES table into EmployeeProfile."""
    from django.contrib.auth import get_user_model

    from worktime.models import EmployeeProfile
    User = get_user_model()

    created = updated = errors = 0

    for row in rows:
        try:
            name = (row.get('STUFF_NAME') or '').strip()
            if not name:
                continue
            oib = (row.get('STUFF_OIB') or '').strip()
            position = (row.get('STUFF_POSITION') or '').strip()
            city = (row.get('STUFF_CITY') or '').strip()
            street = (row.get('STUFF_STREET') or '').strip()
            email = (row.get('STUFF_MAIL') or '').strip()
            iban = (row.get('STUFF_IBAN') or '').strip()
            bank_name = (row.get('BANKNAME') or '').strip()

            # Parse salary
            try:
                salary = float(row.get('STUFF_SALARY') or 0)
            except (ValueError, TypeError):
                salary = 0

            # Lookup by OIB or name
            existing = None
            if oib:
                existing = EmployeeProfile.objects.filter(company=company, tax_id=oib).first()
            if not existing:
                existing = EmployeeProfile.objects.filter(
                    company=company, user__first_name__icontains=name.split()[0][:10]
                ).first() if ' ' in name else None

            if existing:
                # Update
                existing.position = position or existing.position
                existing.address = f'{street}, {city}'.strip(', ') or existing.address
                existing.bank_account = iban or existing.bank_account
                existing.tax_id = oib or existing.tax_id
                existing.save()
                updated += 1
            else:
                # Create a stub user
                parts = name.split(None, 1)
                last_name = parts[0].title() if parts else name.title()
                first_name = parts[1].title() if len(parts) > 1 else ''

                username = f'syn_{oib or name[:8].lower().replace(" ", "_")}'
                username = username[:30]

                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': email or '',
                        'is_active': False,  # Synesis import, not a real login
                    }
                )

                EmployeeProfile.objects.create(
                    company=company,
                    user=user,
                    tax_id=oib,
                    position=position,
                    address=f'{street}, {city}'.strip(', '),
                    bank_account=iban,
                    phone='',
                    hourly_rate=round(salary / 160, 2) if salary else 0,
                )
                created += 1

        except (ValueError, TypeError):
            errors += 1

    return {'created': created, 'updated': updated, 'errors': errors}


def _import_retail(company, retail_rows, tretail_rows):
    """Import primke (goods receipts) from Synesis RETAIL/TRETAIL tables."""
    from datetime import datetime as _dt
    from decimal import Decimal, InvalidOperation

    from django.utils import timezone

    from inventory.models import GoodsReceipt, GoodsReceiptItem, InventoryItem
    from partners.models import Partner

    created = updated = errors = 0

    # Build line items lookup by DIN
    from collections import defaultdict
    lines_by_din = defaultdict(list)
    for lr in tretail_rows:
        din = lr.get('DIN', '').strip()
        if din:
            lines_by_din[din].append(lr)

    def safe_dec(v):
        if v is None:
            return Decimal('0')
        try:
            return Decimal(str(v).replace(',', '.').strip())
        except (InvalidOperation, ValueError):
            return Decimal('0')

    def parse_synesis_date(ds):
        ds = str(ds or '').strip()
        if not ds or ds == 'None':
            return None
        for fmt in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%y", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return _dt.strptime(ds, fmt).date()
            except ValueError:
                continue
        return None

    for row in retail_rows:
        try:
            din = row.get('DIN', '').strip()
            if not din:
                continue

            doc_number = str(row.get('DOCUMENT_NUMBER', '')).strip()
            trancode = str(row.get('TRANCODE', '')).strip()
            receipt_number = doc_number or f"PKV-{trancode}"

            # Skip if already imported (by receipt_number + company)
            existing = GoodsReceipt.objects.filter(
                company=company,
                receipt_number=receipt_number,
            ).first()
            if existing:
                updated += 1
                continue

            # Parse date
            date = parse_synesis_date(row.get('TRANDATE', ''))
            if not date:
                date = parse_synesis_date(row.get('DOCUMENT_DATE', ''))
            if not date:
                date = timezone.now().date()

            # Find supplier
            vendor_name = str(row.get('VENDOR_NAME', '')).strip()
            vendor_oib = str(row.get('PARTNER_VATNUMBER', '')).strip()
            supplier = None
            if vendor_oib:
                supplier = Partner.objects.filter(company=company, oib=vendor_oib).first()
            if not supplier and vendor_name:
                supplier = Partner.objects.filter(company=company, name__icontains=vendor_name[:30]).first()

            total_purchase = safe_dec(row.get('ITEM_TOTALPURCHASEVALUE', 0))
            total_retail = safe_dec(row.get('RET_TOTALINPUT', 0))

            receipt = GoodsReceipt.objects.create(
                company=company,
                receipt_number=receipt_number,
                supplier=supplier,
                date=date,
                document_number=doc_number,
                status='confirmed',
                notes=f'Synesis import (DIN:{din})',
                total_purchase=total_purchase,
                total_selling=total_retail,
                receipt_type='purchase',
                linked_invoice_number=doc_number,
            )

            # Import line items
            items = lines_by_din.get(din, [])
            for item_row in items:
                item_name = str(item_row.get('ITEM_NAME', '')).strip()
                if not item_name:
                    continue

                item_id = str(item_row.get('ITEM_ID', '')).strip()
                sku = f"SYN-{item_id}" if item_id else None

                inv_item = None
                if sku:
                    inv_item = InventoryItem.objects.filter(company=company, sku=sku).first()

                qty = safe_dec(item_row.get('ITEM_QTY', 0))
                if qty == 0:
                    # TRETAIL uses ITEM_OUTPUT for qty sometimes
                    qty = abs(safe_dec(item_row.get('ITEM_OUTPUT', 0)))
                if qty == 0:
                    qty = Decimal('1')

                purchase_price = safe_dec(item_row.get('ITEM_PURCHASEPRICE',
                                          item_row.get('ITEM_NEWNETPRICE', 0)))
                selling_net = safe_dec(item_row.get('ITEM_NEWPRICE',
                                       item_row.get('ITEM_NEWNETPRICE', 0)))
                margin = safe_dec(item_row.get('ITEM_MARGIN',
                                   item_row.get('ITEM_PROFITRATE', 0)))

                GoodsReceiptItem.objects.create(
                    receipt=receipt,
                    inventory_item=inv_item,
                    quantity=qty,
                    purchase_price_unit=purchase_price,
                    cost_price_unit=purchase_price,
                    margin_percent=margin,
                    selling_price_net=selling_net,
                    tax_rate=Decimal('25'),
                    selling_price_gross=round(selling_net * Decimal('1.25'), 2),
                    total_purchase_price=round(purchase_price * qty, 2),
                    total_selling_gross=round(selling_net * Decimal('1.25') * qty, 2),
                )

            created += 1

        except (ValueError, TypeError):
            errors += 1
            import traceback
            traceback.print_exc()

    return {'created': created, 'updated': updated, 'errors': errors}


# ═══════════════════════════════════════════════════
#  SYNESIS MDB ONLINE IMPORT
# ═══════════════════════════════════════════════════
import os
import tempfile

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt


@login_required
def mdb_upload(request):
    """Upload Storage.mdb or Synesis JSON for online analysis and import."""
    from core.company_utils import get_user_company
    company = get_user_company(request)

    if request.method == 'POST' and request.FILES.get('mdb_file'):
        mdb_file = request.FILES['mdb_file']
        fname = mdb_file.name.lower()

        # Save to temp
        tmp_dir = os.path.join(tempfile.gettempdir(), 'synesis_uploads')
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f'{company.pk}_{mdb_file.name}')

        with open(tmp_path, 'wb') as f:
            for chunk in mdb_file.chunks():
                f.write(chunk)

        # Detect file type
        if fname.endswith('.json'):
            request.session['synesis_file_type'] = 'json'
        else:
            request.session['synesis_file_type'] = 'mdb'

        request.session['synesis_mdb_path'] = tmp_path
        request.session['synesis_mdb_name'] = mdb_file.name

        return redirect('synesis:mdb_preview')

    return render(request, 'synesis/mdb_upload.html')


@login_required
def mdb_preview(request):
    """Preview MDB contents before import."""
    from core.company_utils import get_user_company

    from . import mdb_service

    company = get_user_company(request)
    mdb_path = request.session.get('synesis_mdb_path')
    mdb_name = request.session.get('synesis_mdb_name', 'Storage.mdb')

    if not mdb_path or not os.path.exists(mdb_path):
        return redirect('synesis:mdb_upload')

    file_type = request.session.get('synesis_file_type', 'mdb')

    if file_type == 'json':
        summary = mdb_service.json_summary(mdb_path)
        partners = mdb_service.json_partners_preview(mdb_path)
        items = mdb_service.json_items_preview(mdb_path)
        invoices = []
    else:
        summary = mdb_service.read_mdb_summary(mdb_path)
        partners = mdb_service.read_partners(mdb_path)
        items = mdb_service.read_items(mdb_path)
        invoices = mdb_service.read_invoices(mdb_path)

    return render(request, 'synesis/mdb_preview.html', {
        'mdb_name': mdb_name,
        'file_type': file_type,
        'summary': summary,
        'partners': partners[:50],
        'partners_total': len(partners),
        'items': items[:50],
        'items_total': len(items),
        'invoices': invoices[:30],
        'invoices_total': len(invoices),
    })


@login_required
def mdb_import_execute(request):
    """Execute the actual import into ERP."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from core.company_utils import get_user_company

    from . import mdb_service

    company = get_user_company(request)
    mdb_path = request.session.get('synesis_mdb_path')

    if not mdb_path or not os.path.exists(mdb_path):
        return JsonResponse({'error': 'MDB file not found. Please upload again.'}, status=400)

    import_type = request.POST.get('type', 'partners')
    file_type = request.session.get('synesis_file_type', 'mdb')
    results = {}

    try:
        if file_type == 'json':
            # JSON import — uses existing _import_* functions
            results = mdb_service.import_json_to_erp(mdb_path, company)
        elif import_type == 'partners':
            results = mdb_service.import_partners_to_erp(mdb_path, company)
        elif import_type == 'items':
            results = mdb_service.import_items_to_erp(mdb_path, company)
        elif import_type == 'all':
            r1 = mdb_service.import_partners_to_erp(mdb_path, company)
            r2 = mdb_service.import_items_to_erp(mdb_path, company)
            results = {
                'partners': r1,
                'items': r2,
            }
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    # Verification summary
    from inventory.models import InventoryItem
    from partners.models import Partner
    results['verification'] = {
        'total_partners': Partner.objects.filter(company=company).count(),
        'total_items': InventoryItem.objects.filter(company=company).count(),
    }

    return JsonResponse({'status': 'success', 'results': results})


SYNESIS_ARHIVA_BASE = '/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis'
SYNESIS_ACTIVE_BASE = '/var/www/fina-connect/synesis/KONJIK'

def _scan_synesis_knjige():
    import csv
    import io
    import os
    import re
    import subprocess
    def _get_s(mdb):
        try:
            r = subprocess.run(['mdb-export', mdb, 'Settings'], capture_output=True, text=True, timeout=10)
            d = {}
            for row in csv.DictReader(io.StringIO(r.stdout)):
                k = (row.get('Key') or '').strip().strip('"')
                v = (row.get('ValueString') or '').strip().strip('"')
                if k: d[k] = v
            return d
        except (ValueError, AttributeError):
            return {}
    def _name_from_dir(d):
        n = re.sub(r'\s*\d{4}.*$', '', d).strip()
        return n.title() if n == n.upper() else n
    knjige = []
    active = f"{SYNESIS_ACTIVE_BASE}/Storage.mdb"
    if os.path.exists(active):
        s = _get_s(active)
        naz = s.get('eRacunUserName','Konjik d.o.o.')
        if naz == naz.upper(): naz = naz.title()
        knjige.append({'naziv': naz, 'oib': s.get('eRacunUserOIB','').strip(),
                       'dir': 'KONJIK', 'godina': '2025', 'aktivna': True,
                       'size_kb': round(os.path.getsize(active)/1024)})
    if os.path.exists(SYNESIS_ARHIVA_BASE):
        for d in sorted(os.listdir(SYNESIS_ARHIVA_BASE)):
            mdb = f"{SYNESIS_ARHIVA_BASE}/{d}/Storage.mdb"
            if not os.path.exists(mdb): continue
            s = _get_s(mdb)
            naz = (s.get('eRacunUserName') or '').strip() or _name_from_dir(d)
            if naz == naz.upper(): naz = naz.title()
            oib = (s.get('eRacunUserOIB') or s.get('RSOIB') or '').strip()
            god = re.search(r'\d{4}', d)
            knjige.append({'naziv': naz, 'oib': oib, 'dir': d,
                           'godina': god.group() if god else '?', 'aktivna': False,
                           'size_kb': round(os.path.getsize(mdb)/1024)})
    return knjige



from django.contrib.auth.decorators import login_required


@login_required
def synesis_knjige(request):
    """Popis svih Synesis knjiga (MDB fajlova) na serveru."""
    from companies.models import Company
    knjige = _scan_synesis_knjige()
    # Označi koje firme već postoje u LIMIT Connect (prema OIB-u)
    svi_oib = {
        c.oib: c for c in Company.objects.exclude(oib='').only('name','oib','id')
    }
    for k in knjige:
        c = svi_oib.get(k['oib'])
        k['u_sustavu'] = bool(c)
        k['limit_naziv'] = c.name if c else None
        k['limit_id'] = str(c.id) if c else None
    return render(request, 'synesis/knjige.html', {
        'knjige': knjige,
        'ukupno': len(knjige),
        'u_sustavu': sum(1 for k in knjige if k['u_sustavu']),
        'aktivnih': sum(1 for k in knjige if k['aktivna']),
    })

