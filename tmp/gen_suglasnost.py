import os, sys, django
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

HTML = """
<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<style>
  @page { margin: 22mm 20mm 22mm 22mm; size: A4; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 11pt; color: #000; line-height: 1.55; }
  h1 { font-size: 15pt; text-align: center; margin-bottom: 5mm; letter-spacing: 0.5px; }
  h2 { font-size: 11pt; text-align: center; font-weight: 400; margin-bottom: 9mm; color:#333; }
  .hline { border: none; border-top: 0.8pt solid #000; margin: 6mm 0 6mm 0; }
  .hline-thin { border: none; border-top: 0.3pt solid #888; margin: 4mm 0; }
  .block { margin-bottom: 5mm; }
  .block-title { font-weight: 700; margin-bottom: 2mm; font-size: 10.5pt; }
  p { margin-bottom: 3.5mm; text-align: justify; }
  .legal-basis { font-size: 9.5pt; color: #333; margin-bottom: 6mm; }
  .numbered { margin-left: 6mm; }
  .numbered li { margin-bottom: 2mm; }
  .signature-block {
    margin-top: 18mm;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .sig-left { width: 46%; }
  .sig-right { width: 46%; text-align: right; }
  .sig-line {
    border-top: 0.8pt solid #000;
    padding-top: 2mm;
    font-size: 9.5pt;
  }
  .footer-meta {
    margin-top: 22mm;
    padding-top: 3mm;
    border-top: 0.3pt solid #ccc;
    font-size: 8.5pt;
    color: #555;
    line-height: 1.5;
  }
  .emph { font-weight: 700; }
  .address-box {
    background: #f8fafc;
    border-left: 2.5pt solid #c9a84c;
    padding: 4mm 5mm;
    margin-bottom: 4mm;
  }
</style>
</head>
<body>

<h1>SUGLASNOST VLASNIKA NEKRETNINE</h1>
<h2>o korištenju adrese za sjedište Udruge „NO LIMIT"</h2>

<div class="legal-basis">
  Na temelju članka 13. stavka 2. Zakona o udrugama (NN 74/14, 70/17, 98/19) i članka 6. Pravilnika o sadržaju i načinu vođenja Registra udruga Republike Hrvatske (NN 4/15, 14/20), vlasnik niže navedene nekretnine daje
</div>

<hr class="hline">

<div class="block">
  <div class="block-title">I. DAVATELJ SUGLASNOSTI</div>
  <p>
    <span class="emph">Ivica Kruljac</span>, OIB: <span class="emph">[__________________]</span>,<br>
    s prebivalištem na adresi: <span class="emph">[________________________________________________]</span>,<br>
    u svojstvu <span class="emph">vlasnika nekretnine</span> iz točke II. ove Suglasnosti.
  </p>
</div>

<div class="block">
  <div class="block-title">II. NEKRETNINA</div>
  <div class="address-box">
    <strong>Kralja Tomislava 291, 31431 Vladislavci, Republika Hrvatska</strong><br>
    (kuća s poslovnim prostorom)
  </div>
  <p style="font-size:9.5pt; color:#555;">
    (Zemljišnoknjižni podaci: k.o. Vladislavci, k.č.br. [______________], z.k. uložak br. [______________] — upisuje se prije ovjere.)
  </p>
</div>

<div class="block">
  <div class="block-title">III. SVRHA SUGLASNOSTI</div>
  <p>
    Davatelj suglasnosti ovim aktom <span class="emph">dopušta</span> da se nekretnina iz točke II. koristi kao
    <span class="emph">sjedište Udruge „NO LIMIT" — Europske udruge za digitalnu transformaciju stvarnog svijeta</span>
    (u osnivanju) i da se navedena adresa upiše u Registar udruga Republike Hrvatske kao službena adresa sjedišta Udruge.
  </p>
</div>

<div class="block">
  <div class="block-title">IV. UVJETI</div>
  <ol class="numbered">
    <li>Suglasnost se daje <span class="emph">bez naknade</span> i na <span class="emph">neodređeno vrijeme</span>, do opoziva davatelja suglasnosti.</li>
    <li>Udruga se obvezuje urednim i primjerenim korištenjem prostora u skladu s njegovom namjenom i sukladno važećim propisima.</li>
    <li>Davatelj suglasnosti može suglasnost <span class="emph">jednostrano opozvati</span> pisanom izjavom s otkaznim rokom od 30 dana, u kojem je roku Udruga dužna promijeniti adresu sjedišta i obavijestiti Registar udruga.</li>
    <li>Ova Suglasnost ne predstavlja ugovor o najmu, zakupu niti drugi pravni posao s naknadom, već isključivo pravnu osnovu za upis adrese u Registar udruga.</li>
    <li>Sve troškove poslovanja Udruge snosi Udruga, a davatelj suglasnosti nije odgovoran za obveze Udruge.</li>
  </ol>
</div>

<div class="block">
  <div class="block-title">V. ZAVRŠNE ODREDBE</div>
  <p>
    Ova Suglasnost izdaje se u <span class="emph">dva (2) istovjetna primjerka</span>, od kojih se jedan prilaže uz Zahtjev za upis Udruge u Registar udruga Republike Hrvatske, a drugi zadržava davatelj suglasnosti.
  </p>
  <p>
    Suglasnost stupa na snagu danom potpisivanja i primjenjuje se od dana upisa Udruge u Registar udruga.
  </p>
</div>

<hr class="hline">

<p style="margin-top: 5mm;">
  U Vladislavcima, dana <span class="emph">19. travnja 2026. godine</span>.
</p>

<div class="signature-block">
  <div class="sig-left">
    <div class="sig-line">
      <span class="emph">Davatelj suglasnosti</span><br>
      Ivica Kruljac, vlasnik nekretnine<br>
      <span style="font-size:8.5pt; color:#666;">(vlastoručni potpis)</span>
    </div>
  </div>
  <div class="sig-right">
    <div class="sig-line">
      <span class="emph">Primatelj suglasnosti</span><br>
      Ivan Brtan, Predsjednik Udruge<br>
      <span style="font-size:8.5pt; color:#666;">(u ime Udruge u osnivanju)</span>
    </div>
  </div>
</div>

<div class="footer-meta">
  <strong>Prilozi:</strong> Preslika vlasničkog lista / izvadak iz zemljišne knjige (ako ga tijelo zatraži).<br>
  <strong>Napomena:</strong> Ovjera potpisa kod javnog bilježnika nije obvezna za upis u Registar udruga,
  ali Upravni odjel može je zatražiti u pojedinim slučajevima.
  Radi sigurnosti preporučuje se javnobilježnička ovjera potpisa davatelja suglasnosti.<br>
  <strong>Dokument br.:</strong> NO-LIMIT / SUGLASNOST-001 / 2026-04-19
</div>

</body>
</html>
"""

pdf = weasyprint.HTML(string=HTML).write_pdf()
out = "/var/www/fina-connect/static/udruga_no_limit/SUGLASNOST_Vlasnika_Ivica_Kruljac.pdf"
with open(out, "wb") as f:
    f.write(pdf)
print(f"OK: {out} ({len(pdf)//1024} KB)")
