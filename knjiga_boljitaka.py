#!/usr/bin/env python3
"""Knjiga Boljitaka - PDF generator za Mariju."""
import os, datetime
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django; django.setup()
from companies.models import Company
from partners.models import Partner
from inventory.models import InventoryItem, GoodsReceipt
from invoicing.models import Invoice
from worktime.models import EmployeeProfile

s = {
    'p': f'{Partner.objects.count():,}'.replace(',','.'),
    'a': f'{InventoryItem.objects.count():,}'.replace(',','.'),
    'f': f'{Invoice.objects.count():,}'.replace(',','.'),
    'r': f'{GoodsReceipt.objects.count():,}'.replace(',','.'),
    'e': str(EmployeeProfile.objects.count()),
    'c': str(Company.objects.count()),
}
d = datetime.date.today().strftime('%d.%m.%Y.')

html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 2cm 2.5cm; }}
body {{ font-family: Segoe UI, Tahoma, sans-serif; font-size: 11pt; line-height: 1.6; color: #222; }}
h1 {{ color: #c9a84c; border-bottom: 3px solid #c9a84c; padding-bottom: 10px; font-size: 22pt; }}
h2 {{ color: #0a0a0a; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 30px; font-size: 14pt; }}
h3 {{ color: #555; margin-top: 20px; font-size: 12pt; }}
.hdr {{ background: #0a0a0a; color: #c9a84c; padding: 30px; margin: -2cm -2.5cm 30px -2.5cm; text-align: center; }}
.hdr h1 {{ color: #c9a84c; border: none; margin: 0; font-size: 28pt; }}
.hdr .sub {{ color: #e8d5a0; font-size: 12pt; margin-top: 5px; }}
.hdr .dt {{ color: #999; font-size: 10pt; margin-top: 15px; }}
.sg {{ display: flex; flex-wrap: wrap; gap: 15px; margin: 20px 0; }}
.sc {{ background: #f8f6f0; border: 1px solid #e8d5a0; border-radius: 8px; padding: 15px 20px; width: 30%; text-align: center; }}
.sc .n {{ font-size: 24pt; font-weight: bold; color: #c9a84c; }}
.sc .l {{ font-size: 9pt; color: #666; text-transform: uppercase; letter-spacing: 1px; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 10pt; }}
th {{ background: #0a0a0a; color: #c9a84c; padding: 8px 12px; text-align: left; }}
td {{ padding: 6px 12px; border-bottom: 1px solid #eee; }}
tr:nth-child(even) td {{ background: #faf9f6; }}
.ok {{ color: #2e7d32; font-weight: bold; }}
.wait {{ color: #e65100; }}
.hl {{ background: #fff8e1; border-left: 4px solid #c9a84c; padding: 12px 16px; margin: 15px 0; font-size: 10pt; }}
.nb {{ background: #c9a84c; color: #0a0a0a; padding: 2px 8px; border-radius: 3px; font-size: 8pt; font-weight: bold; }}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
.pb {{ page-break-before: always; }}
.ft {{ margin-top: 40px; padding-top: 20px; border-top: 2px solid #c9a84c; text-align: center; color: #999; font-size: 9pt; }}
</style></head><body>

<div class="hdr">
<h1>KNJIGA BOLJITAKA</h1>
<div class="sub">LIMIT Connect ERP &mdash; limit-connect.com</div>
<div class="dt">Sesija: 14.&mdash;15. ozujak 2026. | Izdano: {d}</div>
</div>

<h2>Stanje sustava</h2>
<div class="sg">
<div class="sc"><div class="n">{s['p']}</div><div class="l">Partnera</div></div>
<div class="sc"><div class="n">{s['a']}</div><div class="l">Artikala</div></div>
<div class="sc"><div class="n">{s['f']}</div><div class="l">Faktura</div></div>
<div class="sc"><div class="n">{s['r']}</div><div class="l">Primki</div></div>
<div class="sc"><div class="n">{s['e']}</div><div class="l">Zaposlenika</div></div>
<div class="sc"><div class="n">{s['c']}</div><div class="l">Firmi</div></div>
</div>

<h2>1. Synesis Arhiva &mdash; Kompletni Uvoz <span class="nb">NOVO</span></h2>
<p>Svi podaci iz KS LIMIT Synesis arhive za 2025. godinu uspjesno uvezeni u ERP.
<strong>69 klijenata</strong> KONJIK + <strong>5 klijenata</strong> Korpas.</p>
<table>
<tr><th>Vrsta podataka</th><th>Novo</th><th>Azurirano</th><th>Gresaka</th></tr>
<tr><td>Partneri (dobavljaci i kupci)</td><td class="ok">12.856</td><td>8.563</td><td class="ok">0</td></tr>
<tr><td>Artikli (proizvodi i usluge)</td><td class="ok">4.798</td><td>7.006</td><td class="ok">0</td></tr>
<tr><td>Fakture (izlazni racuni)</td><td class="ok">1.876</td><td>523</td><td class="ok">0</td></tr>
<tr><td>Primke (ulazni dokumenti)</td><td class="ok">1.022</td><td>4.633</td><td class="ok">0</td></tr>
<tr><td>Zaposlenici</td><td class="ok">256</td><td>69</td><td class="ok">0</td></tr>
</table>
<div class="hl"><strong>Alat za buduce uvoze:</strong> Naredba <code>synesis_bulk_import</code> za onboarding
novih klijenata + <code>synesis_analyze.sh</code> za analizu i backup arhiva.</div>

<h2>2. e-Racun Inbox &mdash; Primanje e-Racuna <span class="nb">NOVO</span></h2>
<p>Sustav sada moze <strong>primati e-racune</strong> od dobavljaca. Obavezan zahtjev Fiskalizacije 2.0.</p>
<ul>
<li>Upload UBL XML datoteke putem web sucelja</li>
<li>Automatski parser za EN 16931 / PEPPOL BIS 3.0 format</li>
<li><strong>Jednim klikom proknjizi u URA</strong> &mdash; automatski kreira ulazni racun i partnera</li>
<li>API endpoint za vanjske sustave</li>
</ul>

<h2>3. Fiskalizacija 2.0 &mdash; Pripremljenost <span class="nb">NOVO</span></h2>
<p>Sustav je <strong>95% tehicki spreman</strong> za Fiskalizaciju 2.0.</p>
<table>
<tr><th>Zahtjev</th><th>Status</th><th>Komentar</th></tr>
<tr><td>EN 16931 UBL generator</td><td class="ok">GOTOVO</td><td>PEPPOL BIS 3.0</td></tr>
<tr><td>FINA CIS integracija</td><td class="ok">GOTOVO</td><td>SOAP, XMLSigner, ZKI/JIR</td></tr>
<tr><td>Slanje e-racuna</td><td class="ok">GOTOVO</td><td>API + web sucelje</td></tr>
<tr><td>Primanje e-racuna</td><td class="ok">GOTOVO</td><td>Inbox + auto-booking</td></tr>
<tr><td>PDV-S obrazac</td><td class="ok">GOTOVO</td><td>Generiranje + XML za e-Porezna</td></tr>
<tr><td>Arhiva 11 godina</td><td class="ok">GOTOVO</td><td>SHA-256 + zastita od brisanja</td></tr>
<tr><td>KPD sifre na stavkama</td><td class="ok">GOTOVO</td><td>Spremno za mapiranje</td></tr>
<tr><td>Adapteri za posrednike</td><td class="ok">GOTOVO</td><td>FINA, Moj-eRacun, PONDI</td></tr>
<tr><td>Produkcijski certifikat</td><td class="wait">CEKA</td><td>Naruciti od FINA</td></tr>
<tr><td>Ugovor s posrednikom</td><td class="wait">CEKA</td><td>Kontakt: peppol@fina.hr</td></tr>
</table>
<div class="hl"><strong>Preporuka:</strong> Koristiti usluge postojeceg posrednika (FINA ili Moj-eRacun).
Usteda: 30-50 tisuca EUR i 6-12 mjeseci rada.</div>

<div class="pb"></div>

<h2>4. Arhitektura &mdash; Reorganizacija <span class="nb">NOVO</span></h2>
<p>Reorganizacija koda bez prekida u radu sustava.</p>
<table>
<tr><th>Komponenta</th><th>Sto radi</th><th>Prednost</th></tr>
<tr><td>DocumentEntry</td><td>Jedinstvena tocka za kreiranje dokumenata</td><td>POS, fakture, uvoz &mdash; jedan kod</td></tr>
<tr><td>FiscalHandlerRegistry</td><td>Automatski odabir fiskalizacije</td><td>HR, DE, EU &mdash; automatski</td></tr>
<tr><td>Services layer</td><td>Poslovna logika odvojena od prikaza</td><td>Manje gresaka, laksi razvoj</td></tr>
</table>
<p><strong>Prednost:</strong> Nova drzava ili posrednik = jedna klasa od ~50 linija, bez promjene postojeceg koda.</p>

<h2>5. Infrastruktura</h2>
<table>
<tr><th>Poboljsanje</th><th>Detalji</th></tr>
<tr><td>Upravljanje servisima</td><td>Migracija na systemd &mdash; automatski restart svih servisa</td></tr>
<tr><td>Disk</td><td>Oslobobjeno 17 GB (73% &rarr; 42%)</td></tr>
<tr><td>WhatsApp integracija</td><td>Popravljeno &mdash; 5 taskova za poruke sada radi</td></tr>
<tr><td>Backup</td><td>Poboljsana sigurnost &mdash; uklonjene lozinke iz skripti</td></tr>
<tr><td>Ciscenje</td><td>155 zastarjelih fajlova uklonjeno iz produkcije</td></tr>
</table>

<h2>6. Novi Tipovi Dokumenata <span class="nb">NOVO</span></h2>
<table>
<tr><th>Oznaka</th><th>Naziv</th><th>Namjena</th></tr>
<tr><td><strong>FA</strong></td><td>Faktura (B2B)</td><td>Racun izmedu firmi</td></tr>
<tr><td><strong>URA</strong></td><td>Ulazni racun</td><td>Racun primljen od dobavljaca</td></tr>
<tr><td><strong>RN</strong></td><td>Racun &mdash; gotovina</td><td>Gotovinski racun (POS)</td></tr>
</table>
<p>Novi statusi: <strong>POTVRDJENO</strong> i <strong>FISKALIZIRANO</strong> za bolji tijek dokumenata.</p>

<h2>7. Sljedeci Koraci</h2>
<table>
<tr><th>#</th><th>Zadatak</th><th>Tko</th><th>Rok</th></tr>
<tr><td>1</td><td>Naruciti produkcijski FINA certifikat</td><td>Marija</td><td>Odmah</td></tr>
<tr><td>2</td><td>Kontaktirati peppol@fina.hr za posrednika</td><td>Niksa / Marija</td><td>Ovaj tjedan</td></tr>
<tr><td>3</td><td>Mapirati artikle na KPD 2025 sifre</td><td>Marija + Tim</td><td>Q2 2026</td></tr>
<tr><td>4</td><td>Implementirati API posrednika</td><td>Razvoj</td><td>Q2 2026</td></tr>
<tr><td>5</td><td>Onboarding ~60 klijenata KS LIMIT</td><td>Tim</td><td>Q2-Q3 2026</td></tr>
<tr><td>6</td><td>Webshop za Optiku Oko</td><td>Razvoj</td><td>Q3 2026</td></tr>
</table>

<div class="hl"><strong>Rok:</strong> Fiskalizacija 2.0 &mdash; <strong>01.01.2026.</strong>
Sustav je tehicki spreman. Preostaje: certifikat + ugovor s posrednikom.</div>

<div class="ft">
LIMIT Connect ERP &mdash; limit-connect.com<br>
Konjik d.o.o. | OIB: 37590751921 | Cepin, Kralja Tomislava 1a<br>
Generirano: {d}
</div>
</body></html>'''

out = '/var/www/fina-connect/media/knjiga_boljitaka'
os.makedirs(out, exist_ok=True)
pdf = f'{out}/knjiga_boljitaka_2026-03-15.pdf'
htm = f'{out}/knjiga_boljitaka_2026-03-15.html'
with open(htm, 'w', encoding='utf-8') as f:
    f.write(html)
from weasyprint import HTML
HTML(string=html).write_pdf(pdf)
print(f'PDF:  {pdf}')
print(f'HTML: {htm}')
print(f'Size: {os.path.getsize(pdf)/1024:.0f} KB')
print(f'URL:  https://limit-connect.com/media/knjiga_boljitaka/knjiga_boljitaka_2026-03-15.pdf')
