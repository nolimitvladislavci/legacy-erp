"""
NO LIMIT — Generator svih dokumenata za registraciju udruge
Statut v5, Zapisnik, 6 Odluka, Popis osnivača, Pratno obrazloženje
"""

import os, sys, django, base64

sys.path.insert(0, "/var/www/fenix-v3")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit"
os.makedirs(OUT, exist_ok=True)

with open(f"{OUT}/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO_B64 = base64.b64encode(f.read()).decode()
LOGO_DATA = f"data:image/svg+xml;base64,{LOGO_B64}"

CSS = """
@page {
  margin: 22mm 20mm 28mm 22mm; size: A4;
  @bottom-center {
    content: "Udruga NO LIMIT \\00B7 Kralja Tomislava 291, 31404 Vladislavci \\00B7 no-limit.world \\00B7 Stranica " counter(page) " / " counter(pages);
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 8pt; color: #666;
  }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; color: #000; line-height: 1.55; }
.header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1.5pt solid #000; padding-bottom: 5mm; margin-bottom: 7mm; }
.header-left { flex: 1; }
.header-left h3 { font-size: 11pt; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 1mm; }
.header-left p { font-size: 8.5pt; color: #333; line-height: 1.5; }
.header-right { min-width: 65pt; text-align: right; }
.header-right img { width: 55pt; height: auto; }
.doc-title-block { text-align: center; margin-bottom: 6mm; }
.doc-title-eyebrow { font-size: 8.5pt; color: #555; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 3mm; }
.doc-title { font-size: 17pt; font-weight: 700; letter-spacing: 0.3px; margin-bottom: 2mm; }
.doc-subtitle { font-size: 11.5pt; font-weight: 400; color: #333; letter-spacing: 0.2px; }
.legal-basis { font-size: 9.5pt; color: #333; margin-bottom: 5mm; padding: 3mm 4mm; background: #f5f5f5; border-left: 2pt solid #000; }
.hr { border: none; border-top: 0.8pt solid #000; margin: 6mm 0; }
.hr-thin { border: none; border-top: 0.3pt solid #999; margin: 4mm 0; }
h1 { font-size: 13pt; font-weight: 700; margin: 6mm 0 3mm 0; letter-spacing: 0.3px; }
h2 { font-size: 11.5pt; font-weight: 700; margin: 5mm 0 2mm 0; color: #1a1a1a; page-break-after: avoid; }
h3 { font-size: 10.5pt; font-weight: 700; margin: 4mm 0 2mm 0; color: #1a1a1a; page-break-after: avoid; }
p { margin-bottom: 2.5mm; text-align: justify; }
ul, ol { margin: 2mm 0 3mm 6mm; }
li { margin-bottom: 1.5mm; line-height: 1.5; }
.article { margin-bottom: 5mm; page-break-inside: avoid; }
.article-title { font-weight: 700; font-size: 10.5pt; margin-bottom: 2mm; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0; font-size: 9.5pt; }
table th, table td { border: 0.5pt solid #333; padding: 2mm 3mm; text-align: left; vertical-align: top; }
table th { background: #e8e8e8; font-weight: 700; }
.signature-block { margin-top: 12mm; display: flex; justify-content: space-between; page-break-inside: avoid; }
.signature-block > div { width: 46%; }
.signature-block .right { text-align: right; }
.sig-line { border-top: 0.8pt solid #000; padding-top: 2mm; font-size: 9.5pt; }
.emph { font-weight: 700; }
.note-box { background: #fffbea; border-left: 2pt solid #c9a84c; padding: 3mm 4mm; margin: 3mm 0; font-size: 9.5pt; }
.place-date { margin: 6mm 0 4mm 0; }
"""


def header():
    return f'''<div class="header">
  <div class="header-left">
    <h3>UDRUGA „NO LIMIT"</h3>
    <p>Europska udruga za digitalnu transformaciju stvarnog svijeta<br>
    Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska<br>
    no-limit.world &middot; u osnivanju (19.04.2026.)</p>
  </div>
  <div class="header-right">
    <img src="{LOGO_DATA}" alt="NO LIMIT">
  </div>
</div>'''


def wrap(title, body, subtitle="", eyebrow=""):
    return f"""<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8">
<style>{CSS}</style></head><body>
{header()}
<div class="doc-title-block">
  {f'<div class="doc-title-eyebrow">{eyebrow}</div>' if eyebrow else ""}
  <div class="doc-title">{title}</div>
  {f'<div class="doc-subtitle">{subtitle}</div>' if subtitle else ""}
</div>
{body}
</body></html>"""


def make_pdf(filename, html):
    pdf = weasyprint.HTML(string=html).write_pdf()
    path = f"{OUT}/{filename}"
    with open(path, "wb") as f:
        f.write(pdf)
    return path, len(pdf)


# Sav sadržaj kao varijable
sys.path.insert(0, "/var/www/fenix-v3/_scripts")
from nolimit_bodies import (
    STATUT_BODY,
    ZAPISNIK_BODY,
    ODLUKA_OSNIVANJE_BODY,
    ODLUKA_UPIS_BODY,
    ODLUKA_ZASTUPANJE_BODY,
    ODLUKA_LOGO_BODY,
    ODLUKA_DOM_BODY,
    POPIS_BODY,
    PRATNO_BODY,
)

DOCS = [
    (
        "NO_LIMIT_Statut.pdf",
        "STATUT UDRUGE „NO LIMIT\u201d",
        "Europska udruga za digitalnu transformaciju stvarnog svijeta",
        "Temeljni akt",
        STATUT_BODY,
    ),
    (
        "NO_LIMIT_Zapisnik_osnivacke_skupstine.pdf",
        "ZAPISNIK OSNIVAČKE SKUPŠTINE",
        "Udruga „NO LIMIT\u201d",
        "Prvi povijesni akt",
        ZAPISNIK_BODY,
    ),
    (
        "NO_LIMIT_Odluka_o_osnivanju.pdf",
        "ODLUKA O OSNIVANJU",
        "Udruga „NO LIMIT\u201d",
        "Akt o osnivanju",
        ODLUKA_OSNIVANJE_BODY,
    ),
    (
        "NO_LIMIT_Odluka_o_upisu.pdf",
        "ODLUKA O POKRETANJU POSTUPKA ZA UPIS",
        "u Registar udruga Republike Hrvatske",
        "Akt o upisu",
        ODLUKA_UPIS_BODY,
    ),
    (
        "NO_LIMIT_Odluka_o_zastupanju.pdf",
        "ODLUKA O IMENOVANJU OSOBA OVLAŠTENIH ZA ZASTUPANJE",
        "Udruga „NO LIMIT\u201d",
        "Akt o zastupanju",
        ODLUKA_ZASTUPANJE_BODY,
    ),
    (
        "NO_LIMIT_Odluka_o_logu.pdf",
        "ODLUKA O PRIVREMENOM VIZUALNOM IDENTITETU",
        "Udruga „NO LIMIT\u201d",
        "Akt o logu i pečatu",
        ODLUKA_LOGO_BODY,
    ),
    (
        "NO_LIMIT_Odluka_o_Programu_DOM.pdf",
        "ODLUKA O USPOSTAVI I POKRETANJU PROGRAMA DOM",
        "Humanitarni program stambenog zbrinjavanja",
        "Akt o Programu DOM",
        ODLUKA_DOM_BODY,
    ),
    ("NO_LIMIT_Popis_osnivaca.pdf", "POPIS OSNIVAČA", "Udruga „NO LIMIT\u201d", "Osnivački akt", POPIS_BODY),
    (
        "NO_LIMIT_Pratno_obrazlozenje.pdf",
        "PRATNO OBRAZLOŽENJE",
        "uz Zahtjev za upis Udruge u Registar udruga RH",
        "Pratni dopis",
        PRATNO_BODY,
    ),
]

print("=== GENERIRANJE ===")
for filename, title, subtitle, eyebrow, body in DOCS:
    html = wrap(title, body, subtitle, eyebrow)
    path, size = make_pdf(filename, html)
    print(f"OK {filename} ({size // 1024} KB)")
print("DONE")
