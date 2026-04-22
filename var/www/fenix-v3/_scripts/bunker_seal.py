#!/usr/bin/env python3
"""
bunker_seal.py — Fenix Bunker integrity pečat (TDS Layer 0)

Kreira ChainBlock blok koji zapečaćuje:
  1. SHA-256 hasheve svih kritičnih serverskih fajlova (Merkle stablo)
  2. Sve Defensive Publication pločice (KONJ-DP-...)
  3. Provjera tamper detection (usporedba s prethodnim pečatom)

Pokretanje:
  venv/bin/python _scripts/bunker_seal.py [--type daily|plates|manual]

Systemd timer: fenix-bunker.timer (04:00 daily)
"""

import os, sys, hashlib, json, argparse
from datetime import timezone as tz
from pathlib import Path

os.chdir("/var/www/fenix-v3")
sys.path.insert(0, "/var/www/fenix-v3")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.utils import timezone
from evalidator.models import (
    ChainBlockPOE, BunkerSeal, DefensivePublication,
    BUNKER_CRITICAL_PATHS,
)


ISSUER  = "Konjik d.o.o. — Bunker Integrity System"
OIB     = "0000000KONJIK"


def get_seal_type(arg: str) -> str:
    mapping = {"daily": "daily", "plates": "plates", "manual": "manual", "initial": "initial"}
    return mapping.get(arg, "daily")


def seal(seal_type: str = "daily", extra_paths: list = None, note: str = "") -> BunkerSeal:
    paths = list(BUNKER_CRITICAL_PATHS)
    if extra_paths:
        paths.extend(extra_paths)

    # 1. Skeniranje fajlova
    print(f"\n{'='*60}")
    print(f"  FENIX BUNKER SEAL — {seal_type.upper()}")
    print(f"{'='*60}")
    print(f"\n[1/5] Skeniram {len(paths)} kritičnih fajlova...")
    file_records = BunkerSeal.scan_files(paths)
    ok  = sum(1 for r in file_records if r["ok"])
    err = sum(1 for r in file_records if not r["ok"])
    for r in file_records:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} {r['path'][:55]:<55} {r.get('hash','ERROR')[:12]}...")
    print(f"\n  Fajlovi: {ok} ok, {err} greška")

    # 2. Merkle root
    print(f"\n[2/5] Računam Merkle root...")
    merkle_root = BunkerSeal.compute_merkle(file_records)
    print(f"  Merkle root: {merkle_root}")

    # 3. DP pločice
    print(f"\n[3/5] Sakupljam DP pločice...")
    dps = list(DefensivePublication.objects.order_by("dp_id").values_list("dp_id", flat=True))
    print(f"  Zapečaćene pločice ({len(dps)}): {', '.join(dps) if dps else 'nema'}")

    # 4. Prethodni pečat
    prev = BunkerSeal.objects.order_by("-sealed_at").first()
    tamper_files = []
    tamper_detected = False
    if prev:
        print(f"\n[4/5] Tamper detection (usporedba s pečatom #{prev.pk})...")
        if prev.merkle_root != merkle_root:
            # Stvori privremeni objekt za usporedbu
            tmp = BunkerSeal(files_json=file_records, prev_seal=prev)
            tamper_files = tmp.detect_tamper()
            tamper_detected = bool(tamper_files)
            if tamper_detected:
                print(f"\n  ⚠  TAMPER DETECTED! {len(tamper_files)} promijenjenih fajlova:")
                for t in tamper_files:
                    print(f"     {t['path']}")
                seal_type = "tamper_alert"
            else:
                print(f"  ✓ Merkle root promijenjen ali nema tamper fajlova (novi fajlovi?)")
        else:
            print(f"  ✓ Merkle root identičan — nema promjena")
    else:
        print(f"\n[4/5] Nema prethodnog pečata — ovo je INICIJALNI pečat")
        seal_type = "initial"

    # 5. ChainBlock blok
    print(f"\n[5/5] Kreiram ChainBlock blok...")
    now       = timezone.now()
    prev_hash = ChainBlockPOE.last_hash()
    blk_num   = ChainBlockPOE.next_block_number()

    plate_hashes_str = " | ".join(dps) if dps else "nema plocica"
    note_str = f" | {note}" if note else ""

    description = (
        f"Bunker Integrity Seal — {seal_type} | "
        f"Merkle: {merkle_root[:16]}... | "
        f"Fajlovi: {ok}/{len(paths)} ok | "
        f"Plocice: {', '.join(dps) if dps else 'nema'}{note_str}"
    )
    if tamper_detected:
        description += f" | ⚠ TAMPER: {len(tamper_files)} fajlova"

    # Documents = file records + plate records
    documents = [
        {
            "name": f"bunker_files_merkle_{now.strftime('%Y%m%d')}",
            "hash": merkle_root,
            "size": len(json.dumps(file_records)),
            "mime": "application/json",
            "url":  f"/evalidator/bunker/",
        }
    ]
    for dp_id in dps:
        documents.append({
            "name": dp_id,
            "hash": hashlib.sha256(dp_id.encode()).hexdigest(),
            "size": 0,
            "mime": "text/plain",
            "url":  f"/evalidator/dp/{dp_id}/",
        })

    block = ChainBlockPOE(
        block_number   = blk_num,
        issuer_name    = ISSUER,
        issuer_oib     = OIB,
        title          = f"Bunker Seal #{blk_num} — {seal_type} — {now.strftime('%Y-%m-%d')}",
        description    = description,
        documents_json = documents,
        prev_hash      = prev_hash,
        timestamp      = now,
        seal_token     = f"BNK-{now.strftime('%Y%m%d-%H%M%S')}-{merkle_root[:8].upper()}",
    )
    block.block_hash = block.compute_block_hash()
    block.save()

    bunker = BunkerSeal.objects.create(
        chainblock      = block,
        seal_type       = seal_type,
        files_json      = file_records,
        merkle_root     = merkle_root,
        file_count      = len(file_records),
        plates_json     = dps,
        plate_count     = len(dps),
        prev_seal       = prev,
        tamper_detected = tamper_detected,
        tamper_files_json = tamper_files,
    )

    print(f"\n{'='*60}")
    print(f"  ✅ BUNKER SEAL KREIRAN")
    print(f"{'='*60}")
    print(f"  BunkerSeal ID  : #{bunker.pk}")
    print(f"  Seal type      : {seal_type}")
    print(f"  ChainBlock     : #{block.block_number} | {block.seal_token}")
    print(f"  Merkle root    : {merkle_root}")
    print(f"  Fajlovi        : {ok}/{len(paths)}")
    print(f"  Pločice        : {len(dps)}")
    print(f"  Tamper         : {'⚠ DA' if tamper_detected else '✓ čist'}")
    print(f"  Block hash     : {block.block_hash}")
    print(f"  Verify URL     : /evalidator/verify/{block.seal_token}/")
    print(f"  Bunker URL     : /evalidator/bunker/")
    print(f"{'='*60}\n")

    return bunker


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fenix Bunker Seal")
    parser.add_argument("--type", default="daily", choices=["daily","plates","manual","initial"])
    parser.add_argument("--note", default="", help="Dodatna bilješka")
    parser.add_argument("--paths", nargs="*", help="Dodatni fajlovi za skeniranje")
    args = parser.parse_args()

    seal(seal_type=args.type, extra_paths=args.paths, note=args.note)
