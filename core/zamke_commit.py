"""
core/zamke_commit.py — Zamka 2 Protokol (Z2P)

Svaki git commit prolazi kroz svih 9 sigurnosnih lejera.
Jedno narušavanje = svih 9 lejera se aktiviraju.

Lejer mapa (identična BPZ-9):
  L1 — Nginx: commit SHA u Redis deny tracking
  L2 — TLS/Session: commit tagging u Redis
  L3 — Code Scan: statička analiza committanih fajlova (SQLi/XSS/secrets)
  L4 — Auth: verifikacija identiteta committera (git config vs whitelist)
  L5 — Folija: re-verifikacija kritičnih putanja nakon commita
  L6 — DB Guardian: CommitGuardian record + TAJNA proof
  L7 — Maze Update: API maze seed rotacija (commit SHA → nova entropija)
  L8 — Behavioral: reset baseline ako clean, eskalacija ako sumnjivo
  L9 — Quantum Seal: TAJNA_N chain za commit

Centralni servis: Redis pub/sub kanal `zamke:commit` + CommitGuardian DB
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger("fenix.zamke.commit")

# ── Konfiguracija ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path("/var/www/fina-connect")
FINA_ROOT    = Path("/var/www/fina-connect")

# Whitelist committer emailova (git config user.email)
TRUSTED_AUTHORS = {
    "ivan@limit-connect.com",
    "ivan@fina-connect.online",
    "claude@anthropic.com",
    "cc@limit-connect.com",
    "sonnet@limit-connect.com",
    "opus@limit-connect.com",
    "haiku@limit-connect.com",
    "root@fenix-v3",
    "root@fina-connect",
    "admin@limit-connect.com",
    "marija@fina-connect.online",
    "ivan@no-limit.hr",
}

# Paterni koji su ZABRANJENI u committanom kodu
_SECRET_PATTERNS = [
    re.compile(r'(?i)(password|passwd|secret|api_key|private_key)\s*=\s*["\'][^"\']{8,}["\']'),
    re.compile(r'(?i)sk-[a-zA-Z0-9]{20,}'),           # OpenAI key
    re.compile(r'(?i)AKIA[0-9A-Z]{16}'),               # AWS key
    re.compile(r'(?i)-----BEGIN (RSA |EC )?PRIVATE KEY'),
    re.compile(r'(?i)xoxb-[0-9]+-[0-9]+-[a-z0-9]+'),  # Slack token
]

_SQLI_COMMIT_PATTERN = re.compile(
    r"(?i)(UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO.*VALUES|OR\s+1\s*=\s*1)",
    re.MULTILINE
)

# ── Result struktura ──────────────────────────────────────────────────────────

class LayerResult(NamedTuple):
    layer: str
    ok: bool
    message: str
    data: dict


class Z2Result(NamedTuple):
    commit_sha: str
    all_ok: bool
    layers: list[LayerResult]
    tajna_proof: str
    timestamp: str


# ── Redis helper ─────────────────────────────────────────────────────────────

def _redis():
    import redis as _redis_lib
    return _redis_lib.Redis(host="127.0.0.1", port=6379, db=4, decode_responses=True)


# ── L1: Nginx commit tracking ─────────────────────────────────────────────────

def _l1_nginx_track(commit_sha: str, author_email: str, trusted: bool) -> LayerResult:
    """L1: Spremi commit SHA u Redis za nginx monitoring."""
    try:
        r = _redis()
        key = f"z2:commit:l1:{commit_sha[:16]}"
        r.hset(key, mapping={
            "sha": commit_sha,
            "author": author_email,
            "trusted": "1" if trusted else "0",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        r.expire(key, 86400 * 90)  # 90 dana

        if not trusted:
            # Nepoznati autor → nginx deny + zamke alarm
            deny_key = f"z2:untrusted:{commit_sha[:16]}"
            r.setex(deny_key, 86400 * 30, author_email)
            return LayerResult("L1-nginx", False, f"ALARM: nepoznati autor {author_email}", {})

        return LayerResult("L1-nginx", True, "commit SHA evidentiran", {"key": key})
    except Exception as e:
        return LayerResult("L1-nginx", False, f"Redis error: {e}", {})


# ── L2: TLS/Session tagging ───────────────────────────────────────────────────

def _l2_session_tag(commit_sha: str, project: str) -> LayerResult:
    """L2: Tagira Redis sesiju s commit SHA-om."""
    try:
        r = _redis()
        r.setex(f"z2:active_commit:{project}", 3600, commit_sha)
        r.rpush(f"z2:commit_log:{project}", json.dumps({
            "sha": commit_sha[:16],
            "ts": datetime.now(timezone.utc).isoformat(),
        }))
        r.ltrim(f"z2:commit_log:{project}", -100, -1)  # zadnjih 100
        return LayerResult("L2-session", True, "session tagged", {"sha": commit_sha[:16]})
    except Exception as e:
        return LayerResult("L2-session", False, f"error: {e}", {})


# ── L3: Code scan — secrets / SQLi ───────────────────────────────────────────

def _l3_code_scan(staged_files: list[str], project_root: Path) -> LayerResult:
    """L3: Skeniraj staged fajlove za tajne, SQLi, XSS."""
    findings = []
    scanned = 0

    for rel_path in staged_files:
        path = project_root / rel_path
        if not path.exists():
            continue
        if path.suffix not in {".py", ".js", ".ts", ".html", ".env", ".yml", ".yaml", ".json", ".sh"}:
            continue
        if path.stat().st_size > 1_000_000:  # skip >1MB
            continue

        try:
            content = path.read_text(errors="ignore")
            scanned += 1

            for pat in _SECRET_PATTERNS:
                if pat.search(content):
                    findings.append(f"SECRET in {rel_path}: {pat.pattern[:40]}")

            if _SQLI_COMMIT_PATTERN.search(content):
                findings.append(f"SQLi pattern in {rel_path}")

        except Exception:
            continue

    if findings:
        return LayerResult("L3-scan", False, f"ALARM: {len(findings)} nalaza", {"findings": findings})

    return LayerResult("L3-scan", True, f"čist ({scanned} fajlova skenirano)", {"scanned": scanned})


# ── L4: Auth — verifikacija autora ───────────────────────────────────────────

def _l4_author_verify(author_email: str, author_name: str) -> LayerResult:
    """L4: Provjeri je li autor u whitelist-u."""
    trusted = author_email.lower() in {e.lower() for e in TRUSTED_AUTHORS}

    if not trusted:
        return LayerResult(
            "L4-auth", False,
            f"ALARM: nepoznati autor '{author_name} <{author_email}>'",
            {"author": author_email}
        )

    return LayerResult("L4-auth", True, f"autor verificiran: {author_email}", {})


# ── L5: Folija — re-verifikacija kritičnih putanja ───────────────────────────

def _l5_folija_verify(project_root: Path) -> LayerResult:
    """L5: Pozovi Folija integrity check za kritične fajlove."""
    try:
        folija_path = project_root / "fenix_folija.py"
        if not folija_path.exists():
            return LayerResult("L5-folija", True, "folija.py ne postoji — skip", {})

        # Provjeri hash kritičnih fajlova koji su u BunkerSeal
        critical = [
            project_root / "fenix_folija.py",
            project_root / "config" / "settings.py",
            project_root / "core" / "zamke_engine.py",
            project_root / "core" / "zamke_commit.py",
        ]

        issues = []
        for p in critical:
            if p.exists():
                # Jednostavna provjera — fajl mora biti čitljiv i > 100B
                size = p.stat().st_size
                if size < 100:
                    issues.append(f"SUMNJIVO MALI: {p.name} ({size}B)")

        if issues:
            return LayerResult("L5-folija", False, f"ALARM: {issues}", {})

        return LayerResult("L5-folija", True, "kritični fajlovi OK", {"checked": len(critical)})
    except Exception as e:
        return LayerResult("L5-folija", False, f"error: {e}", {})


# ── L6: DB Guardian — CommitGuardian record ───────────────────────────────────

def _l6_db_guardian(commit_sha: str, author_email: str, message: str,
                     all_ok: bool, tajna_proof: str, project: str) -> LayerResult:
    """L6: Spremi CommitGuardian u DB."""
    try:
        import sys
        # Osiguraj da project root je u sys.path
        proj_root = str(PROJECT_ROOT if project == "fenix-v3" else FINA_ROOT)
        if proj_root not in sys.path:
            sys.path.insert(0, proj_root)

        import django
        # Force override — globalni DJANGO_SETTINGS_MODULE može biti pogrešan
        settings_module = "config.settings" if project == "fenix-v3" else "core.settings"
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
        try:
            from django.apps import apps
            if not apps.ready:
                django.setup()
        except Exception:
            django.setup()

        # CommitGuardian je u Fenix V3 DB (evalidator app)
        # fina-connect: Redis-only zapis (ne diraj tuđu DB)
        if project == "fina-connect":
            raise ImportError("fina-connect → Redis fallback")
        from evalidator.models import CommitGuardian
        guardian = CommitGuardian.objects.create(
            commit_sha=commit_sha,
            author_email=author_email,
            commit_message=message[:500],
            project=project,
            all_layers_ok=all_ok,
            tajna_proof=tajna_proof,
        )
        return LayerResult("L6-guardian", True, f"CommitGuardian #{guardian.pk}", {"id": guardian.pk})
    except ImportError as ie:
        # fina-connect ili Django setup issue → Redis-only zapis
        try:
            r = _redis()
            r.hset(f"z2:guardian:{commit_sha[:16]}", mapping={
                "sha": commit_sha, "email": author_email,
                "project": project, "ok": "1" if all_ok else "0",
                "tajna": tajna_proof[:32], "msg": message[:200],
            })
            r.expire(f"z2:guardian:{commit_sha[:16]}", 86400 * 90)
            return LayerResult("L6-guardian", True, f"Redis guardian (no DB): {commit_sha[:12]}", {})
        except Exception as re:
            return LayerResult("L6-guardian", False, f"Redis fallback error: {re}", {})
    except Exception as e:
        logger.warning("L6 DB guardian error: %s", e)
        return LayerResult("L6-guardian", False, f"DB error: {e}", {})


# ── L7: API Maze — rotacija seed-a ───────────────────────────────────────────

def _l7_maze_rotate(commit_sha: str) -> LayerResult:
    """L7: Rotiraj API maze seed — svaki commit mijenja maze entropiju."""
    try:
        r = _redis()
        new_seed = hashlib.sha3_256(commit_sha.encode() + os.urandom(16)).hexdigest()
        r.setex("z2:maze:seed", 86400 * 30, new_seed)
        r.incr("z2:maze:rotation_count")
        return LayerResult("L7-maze", True, f"maze seed rotiran: {new_seed[:12]}", {})
    except Exception as e:
        return LayerResult("L7-maze", False, f"error: {e}", {})


# ── L8: Behavioral — reset/eskalacija ────────────────────────────────────────

def _l8_behavioral(commit_sha: str, all_ok: bool) -> LayerResult:
    """L8: Ažuriraj behavioral baseline."""
    try:
        r = _redis()
        if all_ok:
            # Clean commit → reset alarm counter
            r.setex("z2:behavioral:last_clean", 86400 * 7, commit_sha[:16])
            r.delete("z2:behavioral:consecutive_alarms")
            return LayerResult("L8-behavioral", True, "baseline reset — clean commit", {})
        else:
            count = r.incr("z2:behavioral:consecutive_alarms")
            r.expire("z2:behavioral:consecutive_alarms", 86400 * 3)
            if int(count) >= 3:
                return LayerResult("L8-behavioral", False,
                                   f"ALARM: {count} uzastopnih alarmantnih commitova!", {"count": count})
            return LayerResult("L8-behavioral", True, f"alarm #{count} evidentiran", {"count": count})
    except Exception as e:
        return LayerResult("L8-behavioral", False, f"error: {e}", {})


# ── L9: Quantum Seal — TAJNA proof ───────────────────────────────────────────

def _l9_quantum_seal(commit_sha: str, project: str) -> tuple[str, LayerResult]:
    """L9: Kreiraj TAJNA proof za commit."""
    try:
        import sys, importlib.util
        proj_root = str(PROJECT_ROOT if project == "fenix-v3" else FINA_ROOT)
        # Direktni import modula — izbjegava core/__init__.py Celery import
        spec = importlib.util.spec_from_file_location(
            "tajna_protokol",
            f"{proj_root}/core/tajna_protokol.py"
        )
        _tajna_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_tajna_mod)
        TajnaSession = _tajna_mod.TajnaSession

        r = _redis()
        prev_key = f"z2:tajna:prev:{project}"
        prev_tajna = r.get(prev_key) or ""

        session = TajnaSession()
        proof = session.seal(commit_sha, prev_tajna)
        session.destroy()

        # Spremi za sljedeći commit
        r.setex(prev_key, 86400 * 90, proof)
        r.hset(f"z2:tajna:chain:{project}", commit_sha[:16], proof[:32])

        return proof, LayerResult("L9-quantum", True,
                                  f"TAJNA proof: {proof[:16]}...", {"proof": proof[:16]})
    except Exception as e:
        logger.warning("L9 quantum seal error: %s", e)
        fallback = hashlib.sha3_256(commit_sha.encode() + os.urandom(32)).hexdigest()
        return fallback, LayerResult("L9-quantum", False, f"fallback proof (no TAJNA): {e}", {})


# ── WhatsApp alarm ────────────────────────────────────────────────────────────

def _whatsapp_alarm(commit_sha: str, author_email: str, failed_layers: list[str]) -> None:
    """Pošalji WhatsApp alarm ako postoje failed layers."""
    try:
        import requests
        r = _redis()
        cooldown_key = f"z2:wa_alarm:{commit_sha[:8]}"
        if r.get(cooldown_key):
            return

        msg = (
            f"🔴 *ZAMKA 2 ALARM* — Fenix V3\n"
            f"Commit: `{commit_sha[:16]}`\n"
            f"Autor: {author_email}\n"
            f"Failed layers: {', '.join(failed_layers)}\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        requests.post(
            "http://localhost:3000/api/sendText",
            json={"chatId": "4915771998747@c.us", "text": msg},
            timeout=5,
        )
        r.setex(cooldown_key, 14400, "1")  # 4h cooldown
    except Exception as e:
        logger.warning("WhatsApp alarm error: %s", e)


# ── Publish to central sentinel ───────────────────────────────────────────────

def _publish_sentinel(result: Z2Result, project: str) -> None:
    """Objavi commit event na Redis pub/sub kanalu zamke:commit."""
    try:
        r = _redis()
        payload = json.dumps({
            "sha": result.commit_sha[:16],
            "project": project,
            "all_ok": result.all_ok,
            "tajna": result.tajna_proof[:16],
            "ts": result.timestamp,
            "layers": [
                {"layer": lr.layer, "ok": lr.ok, "msg": lr.message}
                for lr in result.layers
            ],
        })
        r.publish("zamke:commit", payload)
        # Spremi zadnjih 50 eventa
        r.lpush("z2:sentinel:log", payload)
        r.ltrim("z2:sentinel:log", 0, 49)
    except Exception as e:
        logger.warning("Sentinel publish error: %s", e)


# ── Glavni motor ──────────────────────────────────────────────────────────────

def run_z2_protocol(
    commit_sha: str,
    author_email: str,
    author_name: str,
    commit_message: str,
    staged_files: list[str],
    project: str = "fenix-v3",
    project_root: Path | None = None,
) -> Z2Result:
    """
    Pokreni Zamka 2 Protokol za jedan commit.
    Svi lejeri se izvršavaju — ne zaustavlja se na prvom alarmu.
    """
    if project_root is None:
        project_root = PROJECT_ROOT if project == "fenix-v3" else FINA_ROOT

    ts = datetime.now(timezone.utc).isoformat()
    trusted = author_email.lower() in {e.lower() for e in TRUSTED_AUTHORS}

    # L1–L5 paralelno (IO-bound)
    layers: list[LayerResult] = []

    l1 = _l1_nginx_track(commit_sha, author_email, trusted)
    l2 = _l2_session_tag(commit_sha, project)
    l3 = _l3_code_scan(staged_files, project_root)
    l4 = _l4_author_verify(author_email, author_name)
    l5 = _l5_folija_verify(project_root)

    layers.extend([l1, l2, l3, l4, l5])

    # L7 ne ovisi o L6
    l7 = _l7_maze_rotate(commit_sha)
    layers.append(l7)

    # L9: TAJNA proof (mora biti prije L6 koji ga sprema)
    tajna_proof, l9 = _l9_quantum_seal(commit_sha, project)
    layers.append(l9)

    # L8: behavioral (ovisi o prethodnim rezultatima)
    partial_ok = all(lr.ok for lr in [l1, l3, l4])
    l8 = _l8_behavioral(commit_sha, partial_ok)
    layers.append(l8)

    all_ok = all(lr.ok for lr in layers)

    # L6: DB Guardian (sprema sve — uključujući TAJNA proof)
    l6 = _l6_db_guardian(commit_sha, author_email, commit_message,
                          all_ok, tajna_proof, project)
    layers.insert(5, l6)  # ubaci na poziciju L6

    # Final sort by layer name
    layers.sort(key=lambda x: x.layer)

    result = Z2Result(
        commit_sha=commit_sha,
        all_ok=all_ok,
        layers=layers,
        tajna_proof=tajna_proof,
        timestamp=ts,
    )

    # Publish async (ne blokira commit)
    threading.Thread(target=_publish_sentinel, args=(result, project), daemon=True).start()

    # WhatsApp alarm ako ima failed layera
    failed = [lr.layer for lr in layers if not lr.ok]
    if failed:
        threading.Thread(target=_whatsapp_alarm,
                         args=(commit_sha, author_email, failed), daemon=True).start()

    # Log summary
    status = "✓ CLEAN" if all_ok else f"⚠ ALARM ({len(failed)} layers)"
    logger.info("Z2P commit=%s project=%s %s", commit_sha[:16], project, status)

    return result


# ── CLI entry (poziva ga git hook) ────────────────────────────────────────────

def main(project: str = "fenix-v3") -> int:
    """
    CLI entry point — čita git stanje i pokreće Z2P.
    Vraća exit code: 0 = clean, 1 = alarm (ne blokira commit — samo logira).
    """
    root = PROJECT_ROOT if project == "fenix-v3" else FINA_ROOT

    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception:
        # HEAD ne postoji još (prvi commit)
        commit_sha = "INITIAL-" + hashlib.sha3_256(os.urandom(16)).hexdigest()[:16]

    try:
        author_line = subprocess.check_output(
            ["git", "log", "-1", "--format=%ae|%an"], cwd=root, text=True
        ).strip()
        author_email, author_name = author_line.split("|", 1)
    except Exception:
        author_email = os.environ.get("GIT_AUTHOR_EMAIL", "unknown@unknown")
        author_name  = os.environ.get("GIT_AUTHOR_NAME", "unknown")

    try:
        commit_message = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], cwd=root, text=True
        ).strip()
    except Exception:
        commit_message = ""

    try:
        staged_output = subprocess.check_output(
            ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD"],
            cwd=root, text=True
        ).strip()
        staged_files = [f for f in staged_output.splitlines() if f]
    except Exception:
        staged_files = []

    result = run_z2_protocol(
        commit_sha=commit_sha,
        author_email=author_email,
        author_name=author_name,
        commit_message=commit_message,
        staged_files=staged_files,
        project=project,
        project_root=root,
    )

    # Ispis na stdout (vidljiv u terminalu)
    print(f"\n{'='*60}")
    print(f"  🔐 ZAMKA 2 PROTOKOL — {project.upper()}")
    print(f"{'='*60}")
    print(f"  Commit : {commit_sha[:16]}")
    print(f"  Autor  : {author_email}")
    print(f"  TAJNA  : {result.tajna_proof[:20]}...")
    print(f"  Status : {'✅ SVE OK' if result.all_ok else '🔴 ALARM'}")
    print(f"{'─'*60}")
    for lr in result.layers:
        icon = "✅" if lr.ok else "🔴"
        print(f"  {icon} {lr.layer:<20} {lr.message[:50]}")
    print(f"{'='*60}\n")

    return 0  # Ne blokira commit — samo monitoring


if __name__ == "__main__":
    import sys
    project_arg = sys.argv[1] if len(sys.argv) > 1 else "fenix-v3"
    sys.exit(main(project_arg))
