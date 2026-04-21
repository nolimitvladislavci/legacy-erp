"""
NO LIMIT / Konjik d.o.o. — Patent paket za odvjetnika
Triple DNA metoda, 6 PDF-ova spremnih za DZIV prijavu
"""
import os, sys, django, base64
sys.path.insert(0, '/var/www/fenix-v3')
sys.path.insert(0, '/var/www/fenix-v3/_scripts')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit/patent"
os.makedirs(OUT, exist_ok=True)

with open("/var/www/fina-connect/static/udruga_no_limit/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO_B64 = base64.b64encode(f.read()).decode()
LOGO_DATA = f"data:image/svg+xml;base64,{LOGO_B64}"

CSS = """
@page {
  margin: 22mm 18mm 26mm 20mm; size: A4;
  @top-right {
    content: "KONFIDENCIJALNO · Konjik d.o.o. · DZIV patent paket";
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 7.5pt; color: #888;
  }
  @bottom-center {
    content: counter(page) " / " counter(pages) "  —  Triple DNA patent paket  —  no-limit.world/patent";
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 8pt; color: #666;
  }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; color: #000; line-height: 1.55; }

.header { display:flex; justify-content:space-between; align-items:flex-start;
  border-bottom:1.5pt solid #000; padding-bottom:5mm; margin-bottom:7mm; }
.header-left { flex:1; }
.header-left h3 { font-size:11pt; font-weight:700; letter-spacing:0.5px; }
.header-left p { font-size:8.5pt; color:#333; line-height:1.5; }
.header-right { min-width:55pt; text-align:right; }
.header-right img { width:46pt; height:auto; }

.doc-title-eyebrow { font-size:8.5pt; color:#555; text-transform:uppercase;
  letter-spacing:3px; margin-bottom:2mm; }
.main-title { font-size:17pt; font-weight:700; letter-spacing:0.3px;
  margin-bottom:3mm; line-height:1.3; }
.subtitle { font-size:12pt; font-weight:400; color:#333; margin-bottom:6mm; }

h1 { font-size:13pt; font-weight:700; margin:7mm 0 3mm 0; letter-spacing:0.3px;
  padding-bottom:2mm; border-bottom:0.5pt solid #555; }
h2 { font-size:11.5pt; font-weight:700; margin:5mm 0 2mm 0; color:#1a1a1a; }
h3 { font-size:10.5pt; font-weight:700; margin:4mm 0 2mm 0; color:#1a1a1a; }
p { margin-bottom:2.5mm; text-align:justify; }
ul, ol { margin:2mm 0 3mm 7mm; }
li { margin-bottom:1.5mm; line-height:1.55; }

.meta-box { background:#f5f5f5; border-left:2pt solid #000; padding:3mm 4mm;
  margin-bottom:5mm; font-size:9.5pt; }
.meta-box p { margin-bottom:1mm; }

.meta-table, .data-table, .cost-table, .legend-table { width:100%;
  border-collapse:collapse; margin:3mm 0; font-size:9.5pt; }
.meta-table th, .data-table th, .cost-table th, .legend-table th {
  background:#e8e8e8; font-weight:700; text-align:left;
  padding:2mm 3mm; border:0.4pt solid #333; vertical-align:top; width:30%; }
.meta-table td, .data-table td, .cost-table td, .legend-table td {
  padding:2mm 3mm; border:0.4pt solid #333; vertical-align:top; }

.embodiment { background:#fafafa; border-left:2pt solid #555; padding:3mm 4mm;
  margin:3mm 0; font-size:9.5pt; page-break-inside:avoid; }
.code-block, pre.code-block { background:#f0f0f0; padding:3mm; font-family:monospace;
  font-size:8.5pt; border-left:2pt solid #C9A84C; margin:2mm 0; white-space:pre-wrap;
  border-radius:2pt; }

.claim { border:0.5pt solid #333; padding:3mm 4mm; margin:3mm 0; background:#fafafa;
  page-break-inside:avoid; }
.claim-num { font-weight:700; font-size:10pt; color:#C9A84C; margin-bottom:2mm;
  padding-bottom:1mm; border-bottom:0.3pt solid #C9A84C; }

.abstract-box { border:1pt solid #333; padding:4mm 5mm; background:#fafafa;
  font-size:10pt; line-height:1.7; margin:3mm 0; }

.note-box { background:#fffbea; border-left:2pt solid #C9A84C;
  padding:3mm 4mm; margin:3mm 0; font-size:9.5pt; }

.done-box { background:#f0fdf4; border-left:2pt solid #16a34a;
  padding:3mm 4mm; margin:3mm 0; font-size:9.5pt; }
.todo-box { background:#fff7ed; border-left:2pt solid #f59e0b;
  padding:3mm 4mm; margin:3mm 0; font-size:9.5pt; }

.fig-box { border:0.8pt solid #333; padding:5mm; background:#fff;
  margin:3mm 0 2mm 0; page-break-inside:avoid; }
.fig-caption { font-style:italic; color:#555; font-size:9pt;
  text-align:center; margin-bottom:2mm; }

.emph { font-weight:700; }
.note { font-style:italic; color:#555; font-size:9.5pt; }
"""

def header():
    return f'''<div class="header">
  <div class="header-left">
    <h3>PATENT PAKET — Triple DNA</h3>
    <p>Podnositelj: Konjik d.o.o., Kralja Tomislava 1a, 31431 Čepin, RH<br>
    Izumitelj: Ivan Brtan, OIB 70086599476<br>
    Prior art: Genesis Block #0, 19.04.2026. 12:00 UTC<br>
    Javni paket: no-limit.world/static/udruga_no_limit/patent/</p>
  </div>
  <div class="header-right">
    <img src="{LOGO_DATA}" alt="NO LIMIT">
  </div>
</div>'''

def make_pdf(filename, body_html):
    html = f'''<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8">
<style>{CSS}</style></head><body>{header()}{body_html}</body></html>'''
    pdf = weasyprint.HTML(string=html).write_pdf()
    path = f"{OUT}/{filename}"
    with open(path, "wb") as f:
        f.write(pdf)
    return path, len(pdf)

from patent_bodies import (TEHNICKI_OPIS, PATENT_CLAIMS, PATENT_SAZETAK,
    FORMALNI_OBRAZAC, SHEME, UPUTE_ODVJETNIKU)

DOCS = [
    ("PATENT-01_Tehnicki_opis.pdf",      TEHNICKI_OPIS),
    ("PATENT-02_Nacrt_claims.pdf",       PATENT_CLAIMS),
    ("PATENT-03_Sazetak.pdf",            PATENT_SAZETAK),
    ("PATENT-04_Formalni_obrazac.pdf",   FORMALNI_OBRAZAC),
    ("PATENT-05_Sheme.pdf",              SHEME),
    ("PATENT-06_Upute_odvjetniku.pdf",   UPUTE_ODVJETNIKU),
]

print("=" * 70)
print("PATENT PAKET — Triple DNA — generiranje")
print("=" * 70)
for fname, body in DOCS:
    path, size = make_pdf(fname, body)
    print(f"  OK  {fname}  ({size//1024} KB)")
print("=" * 70)
print(f"Svi dokumenti: {OUT}/")
print(f"Javni URL: https://no-limit.world/static/udruga_no_limit/patent/")
