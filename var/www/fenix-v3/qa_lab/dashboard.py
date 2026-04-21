"""
QA DASHBOARD — jedan Django view /qa/ koji prikazuje:
  Oracle (AST risk) + Time Machine (smoke journeys) + Mutant (mutation tests) + Bunker probe.
Staff-only.
"""
import json
from pathlib import Path
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

REPORTS = Path("/var/www/fenix-v3/qa_lab/reports")


def _read_json(name):
    p = REPORTS / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


HTML = """
<!DOCTYPE html><html lang="hr"><head><meta charset="utf-8">
<title>QA Lab - Fenix V3</title><style>
:root{--bg:#0a0f1d;--card:#0f172a;--gold:#c9a84c;--red:#dc2626;--green:#16a34a;--ylw:#f59e0b;--text:#e2e8f0;--muted:#94a3b8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:'Segoe UI',Arial;padding:20px}
h1{color:var(--gold);font-size:22pt;margin-bottom:4px}h1 span{color:var(--muted);font-size:12pt;font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;margin-top:16px}
.card{background:var(--card);border:1px solid #1e3a5f;border-radius:10px;padding:18px}
.card h2{color:var(--gold);font-size:13pt;margin:0 0 10px 0;display:flex;align-items:center;gap:8px;border-bottom:1px solid #1e3a5f;padding-bottom:8px}
.card h2 .badge{font-size:9pt;padding:2px 8px;border-radius:10px;background:rgba(201,168,76,.15);color:var(--gold);font-weight:700;letter-spacing:.5px}
.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:0.5px solid #1e3a5f;font-size:10pt}
.row:last-child{border:0}.row .k{color:var(--muted)}.row .v{font-weight:600}
.v.red{color:var(--red)}.v.green{color:var(--green)}.v.ylw{color:var(--ylw)}
table{width:100%;border-collapse:collapse;font-size:9.5pt;margin-top:8px}
table td,table th{padding:4px 6px;border-bottom:0.5px solid #1e3a5f;text-align:left}
table th{color:var(--muted);font-weight:500}
.score{font-size:18pt;font-weight:800;padding:6px 10px;border-radius:6px;display:inline-block}
.score.hi{background:var(--red);color:white}.score.mid{background:var(--ylw);color:#111}.score.lo{background:var(--green);color:white}
.tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:8pt;margin-right:4px}
.tag.critical{background:var(--red);color:white}.tag.high{background:#b45309;color:white}.tag.medium{background:#92650a;color:white}.tag.low{background:#555;color:white}
.footer{margin-top:24px;color:var(--muted);font-size:9pt;text-align:center}
</style></head><body>
<h1>Fenix V3 - QA Lab <span>ORACLE - TIME MACHINE - MUTANT - BUNKER</span></h1>
<div class="grid">
{CARDS}
</div>
<div class="footer">Ažurirano: {NOW} UTC &middot; svi izvještaji u /var/www/fenix-v3/qa_lab/reports/</div>
</body></html>
"""


@login_required
@require_GET
def dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponse("Access denied", status=403)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    cards = []

    # ORACLE
    oracle = _read_json("oracle_latest.json") or []
    cards.append(_render_oracle(oracle))

    # TIME MACHINE
    tm = _read_json("time_machine_latest.json")
    cards.append(_render_time_machine(tm))

    # MUTANT
    mut = _read_json("mutant_latest.json")
    cards.append(_render_mutant(mut))

    # BUNKER
    cards.append(_render_bunker())

    html = HTML.replace("{CARDS}", "\n".join(cards)).replace("{NOW}", now)
    return HttpResponse(html)


def _render_oracle(results):
    if not results:
        return '<div class="card"><h2>ORACLE<span class="badge">AST risk</span></h2><p>Nema izvještaja. Pokreni: <code>venv/bin/python qa_lab/oracle/analyzer.py</code></p></div>'

    top = sorted(results, key=lambda r: r.get("risk_score", 0), reverse=True)[:7]
    rows = []
    for r in top:
        score = r.get("risk_score", 0)
        cls = "hi" if score > 0.6 else ("mid" if score > 0.3 else "lo")
        path = r.get("path", "").replace("/var/www/fenix-v3/", "")
        rows.append(f'<tr><td><code>{path}</code></td>'
                    f'<td style="text-align:right"><span class="score {cls}">{score:.2f}</span></td>'
                    f'<td style="text-align:right">{len(r.get("signals",[]))}</td></tr>')
    rows_html = "".join(rows)
    max_score = max((r.get("risk_score", 0) for r in results), default=0)
    files = len(results)
    return f'''<div class="card">
<h2>ORACLE<span class="badge">AST risk</span></h2>
<div class="row"><span class="k">Analiziranih datoteka</span><span class="v">{files}</span></div>
<div class="row"><span class="k">Max risk score</span><span class="v {"red" if max_score>0.6 else "ylw" if max_score>0.3 else "green"}">{max_score:.2f}</span></div>
<table><tr><th>File</th><th style="text-align:right">Risk</th><th style="text-align:right">Signals</th></tr>{rows_html}</table>
</div>'''


def _render_time_machine(tm):
    if not tm:
        return '<div class="card"><h2>TIME MACHINE<span class="badge">smoke</span></h2><p>Nema izvještaja. Pokreni: <code>venv/bin/python qa_lab/time_machine/smoke_runner.py</code></p></div>'
    s = tm.get("summary", {})
    passed = s.get("passed", 0); total = s.get("total", 0); crit = s.get("critical_failed", 0)
    rb_color = "green" if crit == 0 else "red"
    rows = []
    for j in tm.get("journeys", []):
        ok = j.get("passed")
        color = "green" if ok else "red"
        crit_tag = '<span class="tag critical">CRITICAL</span>' if j.get("critical") else ""
        rows.append(f'<tr><td><code>{j.get("name")}</code> {crit_tag}</td>'
                    f'<td style="text-align:right">{j.get("duration_ms")}ms</td>'
                    f'<td style="text-align:right"><span class="v {color}">{"OK" if ok else "FAIL"}</span></td></tr>')
    return f'''<div class="card">
<h2>TIME MACHINE<span class="badge">smoke</span></h2>
<div class="row"><span class="k">Prolazi</span><span class="v {"green" if passed==total else "ylw"}">{passed}/{total}</span></div>
<div class="row"><span class="k">Kritičnih falova</span><span class="v {rb_color}">{crit}</span></div>
<div class="row"><span class="k">Auto-rollback</span><span class="v {rb_color}">{"SPREMNO" if crit==0 else "TRIGGERS"}</span></div>
<table><tr><th>Journey</th><th style="text-align:right">Trajanje</th><th style="text-align:right">Status</th></tr>{"".join(rows)}</table>
</div>'''


def _render_mutant(mut):
    if not mut:
        return '<div class="card"><h2>MUTANT<span class="badge">mutation</span></h2><p>Nema izvještaja. Pokreni: <code>venv/bin/python qa_lab/mutant/runner.py</code></p></div>'
    targets = mut.get("targets", [])
    results = mut.get("results", {})
    rows = []
    for t, r in results.items():
        code = r.get("exit_code", r.get("error", "?"))
        ok = (code == 0 or code == 2)  # mutmut: 2 = survived mutants
        color = "ylw" if code == 2 else ("green" if ok else "red")
        rows.append(f'<tr><td><code>{t}</code></td>'
                    f'<td style="text-align:right"><span class="v {color}">{code}</span></td></tr>')
    last = mut.get("started_at", "")
    return f'''<div class="card">
<h2>MUTANT<span class="badge">mutation</span></h2>
<div class="row"><span class="k">Targeta</span><span class="v">{len(targets)}</span></div>
<div class="row"><span class="k">Zadnje pokretanje</span><span class="v">{last[:19] if last else "-"}</span></div>
<table><tr><th>File</th><th style="text-align:right">Exit</th></tr>{"".join(rows)}</table>
<p style="font-size:8.5pt;color:#94a3b8;margin-top:8px">mutmut exit 0 = svi mutanti ubijeni, 2 = neki preživjeli</p>
</div>'''


def _render_bunker():
    # Nađi najnoviji bunker report
    bunkers = sorted(REPORTS.glob("bunker_*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not bunkers:
        return '<div class="card"><h2>BUNKER<span class="badge">login probe</span></h2><p>Nema izvještaja.</p></div>'
    data = json.loads(bunkers[0].read_text())
    t = data.get("timings", {})
    errs = len(data.get("errors", []))
    goto = t.get("goto_ms", 0)
    http = t.get("http_status")
    color = "green" if http == 200 and errs == 0 else "red"
    target_url = data.get('target', {}).get('url', '')
    return f'''<div class="card">
<h2>BUNKER<span class="badge">login probe</span></h2>
<div class="row"><span class="k">Target</span><span class="v" style="font-size:9pt">{target_url}</span></div>
<div class="row"><span class="k">HTTP status</span><span class="v {color}">{http}</span></div>
<div class="row"><span class="k">goto</span><span class="v">{goto}ms</span></div>
<div class="row"><span class="k">WebAuthn dostupan</span><span class="v">{t.get("webauthn_available_ms","-")}ms</span></div>
<div class="row"><span class="k">Email input vidljiv</span><span class="v {"green" if t.get("has_email_input") else "red"}">{t.get("has_email_input")}</span></div>
<div class="row"><span class="k">Bunker element na stranici</span><span class="v {"green" if t.get("has_bunker_element") else "red"}">{t.get("has_bunker_element")}</span></div>
<div class="row"><span class="k">JS greška</span><span class="v {"green" if errs==0 else "red"}">{errs}</span></div>
</div>'''
