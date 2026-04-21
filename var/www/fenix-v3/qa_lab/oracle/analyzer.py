"""
ORACLE v1 — AST-based risk analyzer za Python/Django datoteke.
Bez ML-a (nemamo 10k bugova za trening) — koristi AST + heuristike koje su
empirijski korelirane s bug-density u Django projektima.

Ulaz: Python datoteka ili diff
Izlaz: risk score 0..1 + lista konkretnih rizika + prijedlozi
"""
import ast
import subprocess
import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List


@dataclass
class RiskSignal:
    kind: str
    severity: str   # low / medium / high / critical
    line: int
    message: str
    suggestion: str


@dataclass
class FileRisk:
    path: str
    risk_score: float          # 0..1
    signals: List[RiskSignal] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# -- heuristike ----------------------------------------------------------

DANGEROUS_CALLS = {
    "eval":    ("critical", "Dinamicko izvrsavanje koda - RCE rizik"),
    "exec":    ("critical", "Dinamicko izvrsavanje koda"),
    "__import__": ("high", "Dinamicki import moze sakriti ranjivosti"),
    "pickle.loads": ("critical", "Deserializacija - RCE rizik"),
    "subprocess.call": ("high", "Subprocess bez shell=False provjere"),
    "os.system": ("critical", "Shell injection rizik"),
}

DJANGO_ANTIPATTERNS = {
    "cursor.execute": ("high", "Raw SQL - SQL injection rizik ako koristi string format"),
    "HttpResponse(request.GET": ("critical", "Reflected XSS"),
    "render(.*mark_safe": ("high", "mark_safe na user inputu - XSS"),
    "@csrf_exempt": ("medium", "CSRF zastita iskljucena"),
}


def analyze_file(path: Path) -> FileRisk:
    if not path.exists():
        return FileRisk(path=str(path), risk_score=0.0)

    source = path.read_text(encoding="utf-8", errors="replace")
    signals: List[RiskSignal] = []
    stats = {
        "loc": len(source.splitlines()),
        "has_tests": False,
        "test_file_exists": False,
        "complexity": 0,
        "num_functions": 0,
        "num_classes": 0,
        "imports": 0,
    }

    # -- AST analysis
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        signals.append(RiskSignal(
            kind="syntax_error",
            severity="critical",
            line=e.lineno or 0,
            message=f"SyntaxError: {e.msg}",
            suggestion="Ispravi sintaksnu gresku prije commita.",
        ))
        return FileRisk(path=str(path), risk_score=1.0,
                        signals=signals, stats=stats)

    for node in ast.walk(tree):
        # dangerous calls
        if isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            if call_name in DANGEROUS_CALLS:
                sev, msg = DANGEROUS_CALLS[call_name]
                signals.append(RiskSignal(
                    kind="dangerous_call", severity=sev,
                    line=getattr(node, "lineno", 0),
                    message=f"{call_name}() - {msg}",
                    suggestion=f"Razmisli da li je {call_name} neophodan."
                ))
        # complexity
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            stats["complexity"] += 1
        if isinstance(node, ast.FunctionDef):
            stats["num_functions"] += 1
        if isinstance(node, ast.ClassDef):
            stats["num_classes"] += 1
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            stats["imports"] += 1

        # bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            signals.append(RiskSignal(
                kind="bare_except", severity="medium",
                line=getattr(node, "lineno", 0),
                message="Bare except: uhvaca sve ukljucujuci KeyboardInterrupt",
                suggestion="Koristi `except Exception:` ili specificnu iznimku."
            ))

        # TODO / FIXME / HACK komentari - ne vidi ih ast, pa ih trazim zasebno

    # -- tekstualne heuristike
    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            if "FIXME" in stripped or "HACK" in stripped or "XXX" in stripped:
                signals.append(RiskSignal(
                    kind="todo_comment", severity="low", line=i,
                    message="FIXME/HACK/XXX komentar",
                    suggestion="Zavrsi ili ukloni prije produkcije."
                ))
        # hardkodirani secrets
        for key in ("password", "secret", "api_key", "token"):
            if f"{key}=" in stripped.lower() or f'"{key}":' in stripped.lower():
                # samo ako izgleda kao prava vrijednost, ne placeholder
                if "=" in stripped and any(c in stripped for c in ("'", '"')):
                    if "settings." not in stripped and "os.environ" not in stripped:
                        signals.append(RiskSignal(
                            kind="possible_secret",
                            severity="high",
                            line=i,
                            message=f"Moguci hardkodirani {key}",
                            suggestion=f"Premjesti u .env ili Django settings."
                        ))
                        break
        # CSRF exempt
        if "@csrf_exempt" in stripped:
            signals.append(RiskSignal(
                kind="csrf_exempt", severity="medium", line=i,
                message="CSRF zastita iskljucena",
                suggestion="Razmisli koristiti CSRF token umjesto exempt."
            ))

    # -- test coverage heuristic
    test_file = path.parent / f"tests" / f"test_{path.name}"
    test_file2 = path.parent / f"test_{path.name}"
    if test_file.exists() or test_file2.exists():
        stats["test_file_exists"] = True
    else:
        signals.append(RiskSignal(
            kind="no_test_file",
            severity="medium" if stats["loc"] > 50 else "low",
            line=0,
            message=f"Nema test datoteke (test_{path.name})",
            suggestion=f"Dodaj tests/test_{path.name} s barem smoke testovima."
        ))

    # -- size heuristic
    if stats["loc"] > 500:
        signals.append(RiskSignal(
            kind="large_file", severity="medium", line=0,
            message=f"Datoteka ima {stats['loc']} linija - tesko za pregled",
            suggestion="Razdvoji u vise manjih modula."
        ))

    if stats["complexity"] > 30:
        signals.append(RiskSignal(
            kind="high_complexity", severity="medium", line=0,
            message=f"Visoka cikliciana slozenost ({stats['complexity']} grana)",
            suggestion="Razmisli o refaktoriranju - extract method."
        ))

    # -- risk score formula (empirijska)
    weights = {"critical": 0.40, "high": 0.20, "medium": 0.08, "low": 0.02}
    raw = sum(weights[s.severity] for s in signals)
    # bonus ako nema testa
    if not stats["test_file_exists"] and stats["loc"] > 50:
        raw += 0.15
    risk = min(raw, 1.0)

    return FileRisk(path=str(path), risk_score=round(risk, 3),
                    signals=signals, stats=stats)


def _get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        parts = []
        cur = node.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def get_changed_files() -> List[Path]:
    # vraca datoteke koje je git izmijenio u zadnjih N commita (staged + unstaged)
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"], cwd="/var/www/fenix-v3",
            stderr=subprocess.DEVNULL
        ).decode()
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd="/var/www/fenix-v3",
            stderr=subprocess.DEVNULL
        ).decode()
    except Exception:
        return []
    files = set((out + staged).splitlines())
    return [Path("/var/www/fenix-v3") / f for f in files
            if f.endswith(".py") and "migrations" not in f]


def analyze_project(paths=None, limit=None):
    root = Path("/var/www/fenix-v3")
    if paths:
        files = [root / p for p in paths if str(p).endswith(".py")]
    else:
        files = list(root.glob("*/*.py"))
        files = [f for f in files if
                 "venv" not in f.parts and
                 "migrations" not in f.parts and
                 "_scripts" not in f.parts and
                 "qa_lab" not in f.parts]
    if limit:
        files = files[:limit]

    results = []
    for f in files:
        try:
            results.append(analyze_file(f))
        except Exception as e:
            print(f"  ERR {f}: {e}", file=sys.stderr)
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--changed":
        files = get_changed_files()
        print(f"Analyzing {len(files)} changed files...")
        results = [analyze_file(f) for f in files]
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        results = analyze_project(limit=200)
    else:
        # default: analyze accounts + invoicing (najvazniji moduli)
        results = analyze_project(
            paths=["accounts/views.py", "accounts/bunker_models.py",
                   "accounts/webauthn_views.py", "accounts/stepup_view.py",
                   "invoicing/views.py"]
        )

    # sort po risk score desc
    results.sort(key=lambda r: r.risk_score, reverse=True)

    print("=" * 78)
    print(f"{'RISK':>6} {'LOC':>5} {'SIGNALS':>8}  FILE")
    print("-" * 78)
    for r in results[:50]:
        path_short = r.path.replace("/var/www/fenix-v3/", "")
        print(f"{r.risk_score:>6.2f} {r.stats.get('loc',0):>5} "
              f"{len(r.signals):>8}  {path_short}")

    # high-risk details
    print()
    print("HIGH RISK DETAILS:")
    for r in results[:5]:
        if r.risk_score < 0.3:
            break
        print(f"\n  [{r.risk_score:.2f}] {r.path.replace('/var/www/fenix-v3/','')}")
        for s in r.signals[:5]:
            print(f"    L{s.line:<4} {s.severity:>8}  {s.message}")

    # save json
    out_path = Path("/var/www/fenix-v3/qa_lab/reports/oracle_latest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        [asdict(r) for r in results], indent=2, default=str))
    print(f"\nJSON: {out_path}")
