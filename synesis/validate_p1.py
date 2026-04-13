#!/usr/bin/env python3
"""
Synesis P1 Validation: MDB INVOICES/URAEU count vs LC Invoice count per company.
Also checks TINVOICES line items.
"""

import csv
import io
import os
import subprocess
import sys

import django

os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"
sys.path.insert(0, "/var/www/fina-connect")
django.setup()

from companies.models import Company
from invoicing.models import Invoice

MDB_CHARSET = "cp1250"
ARCHIVE_DIRS = [
    "/var/www/fina-connect/synesis/KONJIK_ARHIVA/Synesis/",
    "/var/www/fina-connect/Korpa/",
    "/var/www/fina-connect/Uvjek_Frisko/Synesis/",
]


def mdb_count(mdb_path, table):
    """Count rows in MDB table."""
    env = os.environ.copy()
    env["MDB_JET3_CHARSET"] = MDB_CHARSET
    try:
        r = subprocess.run(["mdb-export", mdb_path, table], capture_output=True, text=True, timeout=30, env=env)
        if r.returncode != 0:
            return -1
        rows = list(csv.DictReader(io.StringIO(r.stdout)))
        return len(rows)
    except TypeError:
        return -1


def find_mdbs():
    """Find all Storage.mdb files and extract client name."""
    mdbs = []
    for base_dir in ARCHIVE_DIRS:
        if not os.path.isdir(base_dir):
            continue
        for entry in sorted(os.listdir(base_dir)):
            fp = os.path.join(base_dir, entry)
            if not os.path.isdir(fp):
                continue
            storage = os.path.join(fp, "Storage.mdb")
            if os.path.exists(storage):
                # Extract client name (remove year suffix)
                import re

                match = re.match(r"^(.+?)\s+\d{4}", entry)
                client = match.group(1).strip() if match else entry
                mdbs.append({"client": client, "folder": entry, "mdb": storage})
    return mdbs


# --- MAIN ---
mdbs = find_mdbs()
print(f"Found {len(mdbs)} MDB folders")
print(
    f"{'Client':<35} {'MDB_IRA':>8} {'LC_IRA':>7} {'MDB_URA':>8} {'LC_URA':>7} {'MDB_TINV':>9} {'LC_Items':>8} {'Status'}"
)
print("=" * 120)

total_mdb_ira = 0
total_lc_ira = 0
total_mdb_ura = 0
total_lc_ura = 0
missing_ira = []
missing_ura = []
ok = 0
issues = 0

for m in mdbs:
    client = m["client"]
    mdb = m["mdb"]

    # MDB counts
    inv_count = mdb_count(mdb, "INVOICES")
    ura_count = mdb_count(mdb, "URAEU")
    tinv_count = mdb_count(mdb, "TINVOICES")

    # Find matching LC company
    from django.db.models import Q

    companies = Company.objects.filter(
        Q(name__icontains=client[:20]) | Q(name__icontains=client.split()[0] if client.split() else client)
    )

    lc_ira = 0
    lc_ura = 0
    lc_items = 0
    status = ""

    if companies.exists():
        for co in companies:
            lc_ira += Invoice.objects.filter(company=co, number__startswith="SYN-IRA-").count()
            lc_ura += Invoice.objects.filter(company=co, number__startswith="SYN-URA-").count()
    else:
        status = "NO_MATCH"

    if inv_count > 0 and lc_ira == 0:
        missing_ira.append(client)
        status += " MISS_IRA"
    if ura_count > 0 and lc_ura == 0:
        missing_ura.append(client)
        status += " MISS_URA"

    if inv_count > 0:
        total_mdb_ira += inv_count
    if lc_ira > 0:
        total_lc_ira += lc_ira
    if ura_count > 0:
        total_mdb_ura += ura_count
    if lc_ura > 0:
        total_lc_ura += lc_ura

    if not status:
        ira_ok = inv_count <= 0 or abs(inv_count - lc_ira) / max(inv_count, 1) < 0.1
        ura_ok = ura_count <= 0 or abs(ura_count - lc_ura) / max(ura_count, 1) < 0.1
        if ira_ok and ura_ok:
            status = "OK"
            ok += 1
        else:
            status = "DIFF"
            issues += 1
    else:
        issues += 1

    inv_s = str(inv_count) if inv_count >= 0 else "-"
    ura_s = str(ura_count) if ura_count >= 0 else "-"
    tinv_s = str(tinv_count) if tinv_count >= 0 else "-"

    print(f"{client:<35} {inv_s:>8} {lc_ira:>7} {ura_s:>8} {lc_ura:>7} {tinv_s:>9} {'':>8} {status}")

print("=" * 120)
print(f"TOTALS: MDB_IRA={total_mdb_ira}, LC_IRA={total_lc_ira}, MDB_URA={total_mdb_ura}, LC_URA={total_lc_ura}")
print(f"OK: {ok}, Issues: {issues}")
print(f"Missing IRA ({len(missing_ira)}): {missing_ira[:20]}")
print(f"Missing URA ({len(missing_ura)}): {missing_ura[:20]}")
