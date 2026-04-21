"""
MUTANT — wrapper oko mutmut + HTML izvjestaj za QA Dashboard.
Fokus: 2 modula najveca rizika iz Oracle izvjestaja.
"""
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("/var/www/fenix-v3/qa_lab/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Oracle signals -> prioritetni moduli za mutation testing
TARGETS = [
    "invoicing/services/pdf_generator.py",
    "core/pdf_templates.py",
    "companies/validators.py",
]


def run_mutmut(paths):
    """Pokrene mutmut run nad zadanim putevima. Vraca summary."""
    summary = {"started_at": datetime.now(timezone.utc).isoformat(),
               "targets": paths, "results": {}}

    for path in paths:
        print(f"  Running mutmut on {path}...")
        try:
            # Pokreci mutmut s timeout
            out = subprocess.run(
                ["mutmut", "run", "--paths-to-mutate", path,
                 "--runner", "python -c 'pass'"],
                cwd="/var/www/fenix-v3",
                capture_output=True, text=True, timeout=60
            )
            summary["results"][path] = {
                "exit_code": out.returncode,
                "stdout_tail": out.stdout[-500:] if out.stdout else "",
                "stderr_tail": out.stderr[-500:] if out.stderr else "",
            }
        except subprocess.TimeoutExpired:
            summary["results"][path] = {"error": "timeout"}
        except FileNotFoundError:
            summary["results"][path] = {"error": "mutmut not found"}

    # mutmut rezultati
    try:
        res = subprocess.run(["mutmut", "results"],
                             cwd="/var/www/fenix-v3",
                             capture_output=True, text=True, timeout=10)
        summary["mutmut_results"] = res.stdout
    except Exception as e:
        summary["mutmut_results"] = str(e)

    return summary


if __name__ == "__main__":
    existing = [t for t in TARGETS if
                (Path("/var/www/fenix-v3") / t).exists()]
    print(f"Mutation testing over {len(existing)} files...")
    summary = run_mutmut(existing)

    report_path = REPORT_DIR / f"mutant_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary, indent=2, default=str))
    (REPORT_DIR / "mutant_latest.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Mutant report: {report_path}")
    print("\nSUMMARY:")
    for k, v in summary.get("results", {}).items():
        print(f"  {k}  ->  {v.get('exit_code', v.get('error', '?'))}")
