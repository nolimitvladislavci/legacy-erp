"""
Generira jedan PDF koji agregira Master Plan (00) + svih 8 traka (01-08).
"""
import os, sys, django, base64, re
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit/master_plan"

with open("/var/www/fina-connect/static/udruga_no_limit/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO = base64.b64encode(f.read()).decode()

# Convert markdown to HTML (simple)
def md_to_html(md_text):
    html = md_text
    # Headers
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # Code blocks (```...```)
    html = re.sub(r'```(?:\w+)?\n(.+?)\n```', lambda m: f'<pre>{m.group(1)}</pre>', html, flags=re.DOTALL)
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    # Tables (simple)
    lines = html.split('\n')
    out_lines = []
    in_table = False
    for line in lines:
        if line.startswith('|') and '|' in line[1:]:
            if not in_table:
                out_lines.append('<table class="md">')
                in_table = True
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(c.replace('-', '').replace(':', '').strip() == '' for c in cells):
                continue  # separator row
            tag = 'th' if not any('---' in c for c in cells) and len(out_lines) > 0 and out_lines[-1] == '<table class="md">' else 'td'
            tag = 'th' if not any('---' in c for c in cells) and out_lines[-1] == '<table class="md">' else 'td'
            row = ''.join(f'<{tag}>{c}</{tag}>' for c in cells)
            out_lines.append(f'<tr>{row}</tr>')
        else:
            if in_table:
                out_lines.append('</table>')
                in_table = False
            out_lines.append(line)
    if in_table:
        out_lines.append('</table>')
    html = '\n'.join(out_lines)
    # Lists (basic)
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    # Paragraphs
    html = re.sub(r'\n\n', '</p><p>', html)
    html = '<p>' + html + '</p>'
    return html


CSS = """
@page { margin: 18mm 16mm 22mm 18mm; size: A4;
  @top-right { content: "NO LIMIT - MASTER PLAN v1.0"; font-size: 7.5pt; color: #888; }
  @bottom-center { content: counter(page) " / " counter(pages) "  no-limit.world/master-plan"; font-size: 8pt; color: #666; }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9pt; color: #000; line-height: 1.45; }
.cover { text-align:center; padding:25mm 8mm; border:2pt solid #000;
  margin-bottom:8mm; background:linear-gradient(135deg,#0a0f1d 0%,#1a1a2e 100%);
  color:white; page-break-after:always; }
.cover .eyebrow { font-size:9pt; letter-spacing:5px; text-transform:uppercase; color:#C9A84C; margin-bottom:5mm; }
.cover img { width:60pt; filter:invert(1); }
.cover h1 { font-size:30pt; font-weight:900; margin:5mm 0; color:white; }
.cover h2 { font-size:13pt; font-weight:400; color:#cbd5e1; margin-bottom:10mm; }
.cover .meta { font-size:9pt; color:#94a3b8; margin-top:10mm; line-height:1.8; }
h1 { font-size:16pt; font-weight:700; margin:8mm 0 3mm 0; color:#0f172a;
  border-bottom:2pt solid #C9A84C; padding-bottom:2mm; page-break-before:always; }
h1:first-of-type { page-break-before:avoid; }
h2 { font-size:11pt; font-weight:700; margin:5mm 0 2mm 0; color:#1e3a5f; }
h3 { font-size:10pt; font-weight:700; margin:4mm 0 2mm 0; color:#334155; }
p { margin-bottom:2mm; text-align:justify; }
ul, ol { margin:1mm 0 2mm 5mm; }
li { margin-bottom:1mm; }
strong { color:#0f172a; }
code { background:#f0f0f0; padding:1pt 3pt; font-family:monospace; font-size:8pt; border-radius:2pt; }
pre { background:#f4f4f4; padding:3mm; font-family:monospace; font-size:7.5pt;
  border-left:2pt solid #C9A84C; margin:2mm 0; white-space:pre-wrap; overflow-x:auto; }
table.md { width:100%; border-collapse:collapse; margin:3mm 0; font-size:8.5pt; }
table.md td, table.md th { border:0.4pt solid #555; padding:1.5mm 2mm; text-align:left; vertical-align:top; }
table.md th { background:#0f172a; color:white; font-weight:700; }
table.md tr:nth-child(even) { background:#fafafa; }
.toc { padding:10mm; background:#fafafa; border:1pt solid #ccc; margin-bottom:8mm; page-break-after:always; }
.toc h2 { color:#0f172a; border-bottom:1pt solid #C9A84C; padding-bottom:2mm; }
.toc ol { font-size:11pt; line-height:2; }
"""


# Glavni template
HTML_HEADER = f'''<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8">
<style>{CSS}</style></head><body>
<div class="cover">
  <div class="eyebrow">Master Plan v1.0</div>
  <img src="data:image/svg+xml;base64,{LOGO}" alt="NO LIMIT">
  <h1>NO LIMIT<br>MASTER PLAN</h1>
  <h2>8 paralelnih traka, agent-isolated<br>Sve sto je danas u glavi - sad je trajno na disku</h2>
  <div class="meta">
    Datum kreiranja: 21. travnja 2026.<br>
    Predsjednik: Ivan Brtan<br>
    Generiran: Opus 4.7 + Ivan Brtan<br>
    Javni URL: https://no-limit.world/static/udruga_no_limit/master_plan/<br><br>
    Pravilo: bilo koji buduci agent moze preuzeti rad
  </div>
</div>

<div class="toc">
<h2>SADRZAJ</h2>
<ol>
<li>Master Plan - sazetak i faze</li>
<li>Trak A - Backend / Database</li>
<li>Trak B - Frontend / UI (UCS + POS Command Mode)</li>
<li>Trak C - AI / Resolver / Intent</li>
<li>Trak D - Patent + Pravno</li>
<li>Trak E - Marketing / Outreach</li>
<li>Trak F - Pilot + Operativno</li>
<li>Trak G - QA / DevOps</li>
<li>Trak H - Udruga registracija</li>
</ol>
</div>
'''

# Učitaj sve trake
files = [
    "00_MASTER_PLAN.md",
    "01_TRACK_A_BACKEND.md",
    "02_TRACK_B_FRONTEND.md",
    "03_TRACK_C_AI.md",
    "04_TRACK_D_PATENT.md",
    "05_TRACK_E_MARKETING.md",
    "06_TRACK_F_PILOT.md",
    "07_TRACK_G_QA.md",
    "08_TRACK_H_UDRUGA.md",
]

body_parts = []
for f in files:
    with open(f"{OUT}/{f}") as fp:
        body_parts.append(md_to_html(fp.read()))

html = HTML_HEADER + "\n".join(body_parts) + "</body></html>"

# Ukloni emojis koji ne rade s DejaVu fontom
emoji_pattern = re.compile("[\U0001F300-\U0001F9FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001FA70-\U0001FAFF]+", flags=re.UNICODE)
html = emoji_pattern.sub("", html)

pdf = weasyprint.HTML(string=html).write_pdf()
out_path = f"{OUT}/NOLIMIT-MASTER-PLAN-v1.pdf"
with open(out_path, "wb") as f:
    f.write(pdf)
print(f"OK: {out_path} ({len(pdf)//1024} KB)")
