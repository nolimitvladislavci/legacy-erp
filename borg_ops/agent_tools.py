"""
borg_ops/agent_tools.py — Tool funkcije za agente.

Tri razine sigurnosti:
  RAZINA 1 (auto): read_file, git_diff, run_check, list_directory
  RAZINA 2 (auto+log): write_file (s backup), run_makemigrations
  RAZINA 3 (Ivan klik): request_git_commit, request_migrate, execute_*
"""

import difflib
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("agent_tools")

PROJECT_ROOT = Path("/var/www/fina-connect")
BACKUP_DIR = PROJECT_ROOT / ".agent_backups"

BLOCKED_PATHS = {".env", "settings.py", "local_settings.py", "secrets/", ".git/"}
ALLOWED_WRITE_EXTENSIONS = {".py", ".html", ".css", ".js", ".md", ".json", ".txt"}


# ── RAZINA 1 — AUTO ──────────────────────────────────────────────────────────


def read_file(path: str, max_lines: int = 500) -> dict:
    """Cita fajl. Whitelist provjera puta."""
    fpath = _resolve_path(path)
    if fpath is None:
        return {"ok": False, "error": f"Put nije dozvoljen: {path}"}
    if not fpath.exists():
        return {"ok": False, "error": f"Fajl ne postoji: {path}"}
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        truncated = len(lines) > max_lines
        if truncated:
            content = "\n".join(lines[:max_lines])
            content += f"\n# ... ({len(lines) - max_lines} linija izostavljeno)"
        return {"ok": True, "content": content, "lines": len(lines), "truncated": truncated}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def git_diff(args: str = "") -> dict:
    """Git diff trenutnih promjena."""
    cmd = ["git", "diff"] + (args.split() if args.strip() else [])
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)
    return {"ok": True, "diff": result.stdout[:5000], "stderr": result.stderr[:200]}


def run_check() -> dict:
    """manage.py check — Django konfiguracija."""
    result = subprocess.run(
        ["venv/bin/python", "manage.py", "check"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30,
    )
    return {"ok": result.returncode == 0, "output": (result.stdout + result.stderr)[:2000]}


def list_directory(path: str = ".") -> dict:
    """Lista fajlove u direktoriju."""
    fpath = _resolve_path(path)
    if fpath is None:
        return {"ok": False, "error": "Put nije dozvoljen"}
    if not fpath.is_dir():
        return {"ok": False, "error": "Nije direktorij"}
    SKIP = {"venv", "__pycache__", ".git", "node_modules", "staticfiles", ".agent_backups"}
    items = []
    for item in sorted(fpath.iterdir()):
        if item.name.startswith(".") or item.name in SKIP:
            continue
        items.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        })
    return {"ok": True, "items": items, "count": len(items)}


def git_log(n: int = 10) -> dict:
    """Zadnjih N git commitova."""
    result = subprocess.run(
        ["git", "log", "--oneline", f"-{n}"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10,
    )
    return {"ok": True, "log": result.stdout}


# ── RAZINA 2 — AUTO + LOG ─────────────────────────────────────────────────────


def write_file(path: str, content: str) -> dict:
    """
    Pise fajl. Kreira .bak backup. Vraca diff.
    Nikad ne pise .env, settings.py ili slicne osjetljive fajlove.
    """
    fpath = _resolve_path(path)
    if fpath is None:
        return {"ok": False, "error": f"Put nije dozvoljen: {path}"}
    if fpath.suffix not in ALLOWED_WRITE_EXTENSIONS:
        return {"ok": False, "error": f"Ekstenzija nije dozvoljena: {fpath.suffix}"}

    # Backup
    old_content = ""
    if fpath.exists():
        BACKUP_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(fpath, BACKUP_DIR / f"{fpath.name}.{ts}.bak")
        old_content = fpath.read_text(encoding="utf-8", errors="ignore")

    # Pisi
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content, encoding="utf-8")

    diff = _simple_diff(old_content, content, path)
    lines_added = max(0, len(content.splitlines()) - len(old_content.splitlines()))
    return {
        "ok": True,
        "path": path,
        "diff": diff,
        "lines_new": len(content.splitlines()),
        "lines_added": lines_added,
    }


def run_makemigrations(app: str) -> dict:
    """Generira migracije (NE aplicira)."""
    result = subprocess.run(
        ["venv/bin/python", "manage.py", "makemigrations", app, "--no-input"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60,
    )
    return {"ok": result.returncode == 0, "output": (result.stdout + result.stderr)[:2000]}


def run_tests(app: str = "") -> dict:
    """manage.py test za jedan app."""
    cmd = ["venv/bin/python", "manage.py", "test", "--no-input"]
    if app:
        cmd.append(app)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    return {
        "ok": result.returncode == 0,
        "output": (result.stdout + result.stderr)[-2000:],
    }


# ── RAZINA 3 — IVAN MORA KLIKNUTI ────────────────────────────────────────────


def request_git_commit(msg: str) -> dict:
    """
    NE commitira. Vraca approval_needed=True.
    Agent dobiva signal → WebSocket salje ask_ivan event Ivanu.
    """
    stat = subprocess.run(
        ["git", "diff", "--stat"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--stat"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
    )
    diff_info = (stat.stdout + staged.stdout).strip() or "Nema promjena u working tree-u"
    return {
        "ok": True,
        "approval_needed": True,
        "action": "git_commit",
        "commit_msg": msg,
        "diff_stat": diff_info,
        "prompt": (
            f"Agent je spreman za commit.\n\n"
            f"Promjene:\n```\n{diff_info}\n```\n\n"
            f"Commit poruka: `{msg}`\n\nOdobravaš?"
        ),
    }


def execute_git_commit(msg: str) -> dict:
    """Commitira — SAMO poziva se iz continue_after_approval() nakon Ivanovog OK."""
    subprocess.run(["git", "add", "-A"], cwd=PROJECT_ROOT, timeout=10)
    r = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30,
    )
    if r.returncode == 0:
        h = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        return {"ok": True, "commit": h.stdout.strip()}
    return {"ok": False, "error": r.stderr[:500]}


def request_migrate(app: str = "") -> dict:
    """Trazi odobrenje za migrate."""
    return {
        "ok": True,
        "approval_needed": True,
        "action": "migrate",
        "app": app,
        "prompt": (
            f"Agent trazi pokretanje migracije"
            f"{' za app: ' + app if app else ' (sve pending)'}"
            f". Odobri?"
        ),
    }


def execute_migrate(app: str = "") -> dict:
    """Migrira — SAMO nakon Ivanovog odobrenja."""
    cmd = ["venv/bin/python", "manage.py", "migrate"]
    if app:
        cmd.append(app)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    return {"ok": result.returncode == 0, "output": (result.stdout + result.stderr)[:2000]}


# ── ANTHROPIC TOOL DEFINITIONS ───────────────────────────────────────────────

HAIKU_TOOLS = [
    {
        "name": "read_file",
        "description": "Cita sadrzaj Python/HTML/MD fajla iz projekta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relativni put od project root (npr. documents/views.py)"
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Max linija za citanje (default 500)"
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Pise ili mijenja fajl. Automatski kreira backup. "
            "Vraca diff. Koristi za kod, template, config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "Relativni put fajla"},
                "content": {"type": "string", "description": "Kompletan novi sadrzaj fajla"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_check",
        "description": "Pokrace manage.py check — provjeri Django konfiguraciju.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "git_diff",
        "description": "Pokaze git diff trenutnih promjena.",
        "input_schema": {
            "type": "object",
            "properties": {
                "args": {"type": "string", "description": "Opcionalni argumenti (npr. HEAD~1)"}
            },
        },
    },
    {
        "name": "git_log",
        "description": "Zadnjih N git commitova.",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Broj commitova (default 10)"}
            },
        },
    },
    {
        "name": "list_directory",
        "description": "Lista fajlove u direktoriju projekta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relativni put direktorija (default .)"}
            },
        },
    },
    {
        "name": "run_makemigrations",
        "description": "Generira Django migracije za app (NE aplicira ih).",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Ime Django appa"}
            },
            "required": ["app"],
        },
    },
    {
        "name": "request_git_commit",
        "description": (
            "Trazi Ivanovo odobrenje za git commit. "
            "NE commitira odmah — ceka potvrdu. "
            "Koristiti nakon sto su sve promjene gotove."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "msg": {"type": "string", "description": "Commit poruka"}
            },
            "required": ["msg"],
        },
    },
]

# DeepSeek i Gemini nemaju write_file po defaultu
DEEPSEEK_TOOLS = [t for t in HAIKU_TOOLS if t["name"] not in ("write_file", "run_makemigrations")]
GEMINI_TOOLS   = [t for t in HAIKU_TOOLS if t["name"] in ("read_file", "list_directory", "git_log")]

# Mapa ime → funkcija (za _execute_tool u tasks_agent)
TOOL_FUNCTION_MAP = {
    "read_file":          read_file,
    "write_file":         write_file,
    "run_check":          lambda **_: run_check(),
    "git_diff":           git_diff,
    "git_log":            git_log,
    "list_directory":     list_directory,
    "run_makemigrations": run_makemigrations,
    "run_tests":          run_tests,
    "request_git_commit": request_git_commit,
    "request_migrate":    request_migrate,
    "execute_git_commit": execute_git_commit,
    "execute_migrate":    execute_migrate,
}

TOOL_LOG_TYPE_MAP = {
    "read_file": "read_file", "list_directory": "read_file",
    "git_log": "git_op", "git_diff": "git_op",
    "write_file": "write_file",
    "run_check": "exec_cmd", "run_makemigrations": "exec_cmd", "run_tests": "exec_cmd",
    "request_git_commit": "git_op", "execute_git_commit": "git_op",
    "request_migrate": "exec_cmd", "execute_migrate": "exec_cmd",
}


# ── POMOCNE ──────────────────────────────────────────────────────────────────

def _resolve_path(path: str):
    """Sigurnosna provjera — path mora biti unutar PROJECT_ROOT."""
    try:
        resolved = (PROJECT_ROOT / path).resolve()
        if not str(resolved).startswith(str(PROJECT_ROOT)):
            return None
        rel = str(resolved).replace(str(PROJECT_ROOT) + "/", "")
        for blocked in BLOCKED_PATHS:
            if blocked in rel:
                return None
        return resolved
    except Exception:
        return None


def _simple_diff(old: str, new: str, filename: str) -> str:
    """Human-readable unified diff, max 200 linija."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{filename}", tofile=f"b/{filename}", n=3
        )
    )
    return "".join(diff[:200])
