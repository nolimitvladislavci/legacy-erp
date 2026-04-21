"""OPP v1.1 — Open Patent Promise s ugrađenim čl. 27 (Reciprocitet)"""
import os, sys, django, base64
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit/opp"
os.makedirs(OUT, exist_ok=True)

with open("/var/www/fina-connect/static/udruga_no_limit/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO = base64.b64encode(f.read()).decode()

HTML = f'''<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8"><style>
@page {{ margin: 22mm 20mm; size: A4; @bottom-center {{ content: "OPP v1.1 - no-limit.world - " counter(page) "/" counter(pages); font-size:8pt; color:#666; }} }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; color: #000; line-height: 1.6; }}
.header {{ display:flex; justify-content:space-between; border-bottom:1.5pt solid #000; padding-bottom:5mm; margin-bottom:7mm; }}
.header img {{ width:50pt; }}
.header h2 {{ font-size:11pt; }}
.header p {{ font-size:9pt; color:#333; }}
.cover {{ text-align:center; margin-bottom:8mm; }}
.cover h1 {{ font-size:22pt; font-weight:900; letter-spacing:0.5px; margin-bottom:3mm; }}
.cover h2 {{ font-size:12pt; font-weight:400; color:#333; margin-bottom:5mm; }}
.version {{ display:inline-block; padding:4pt 12pt; background:#0f172a; color:#C9A84C; border-radius:3pt; font-weight:700; }}
h1 {{ font-size:13pt; margin:6mm 0 3mm 0; padding-bottom:2mm; border-bottom:1pt solid #C9A84C; }}
h2 {{ font-size:11pt; margin:4mm 0 2mm 0; }}
p {{ margin-bottom:3mm; text-align:justify; }}
ol, ul {{ margin-left:6mm; margin-bottom:3mm; }}
li {{ margin-bottom:1.5mm; }}
.article {{ background:#fafafa; border-left:3pt solid #0f172a; padding:4mm 5mm; margin:4mm 0; }}
.article.key {{ border-left-color:#C9A84C; background:#fffbea; }}
.article h3 {{ color:#0f172a; font-size:11pt; margin-bottom:2mm; }}
.emph {{ font-weight:700; }}
.signature {{ margin-top:10mm; display:flex; justify-content:space-between; }}
.sig-box {{ width:46%; border-top:1pt solid #000; padding-top:2mm; font-size:9.5pt; }}
</style></head><body>

<div class="header">
  <div>
    <h2>OPEN PATENT PROMISE v1.1</h2>
    <p>Licencni režim ChainBlock ekosustava &middot; Konjik d.o.o. + Udruga NO LIMIT</p>
  </div>
  <img src="data:image/svg+xml;base64,{LOGO}" alt="NL">
</div>

<div class="cover">
  <h1>OPEN PATENT PROMISE</h1>
  <h2>Neopoziva licenca Konjik d.o.o. za sve korisnike — s ugrađenim reciprocitetom</h2>
  <span class="version">v1.1 · 20. travnja 2026.</span>
</div>

<h1>PREAMBULA</h1>
<p>Ova OPP licenca (Open Patent Promise, v1.1) predstavlja <span class="emph">javnu i neopozivu obvezu</span> 
trgovačkog društva <span class="emph">Konjik d.o.o.</span> (Kralja Tomislava 1a, 31431 Čepin, Hrvatska) 
prema svim korisnicima digitalnih tehnologija ekosustava ChainBlock — uključujući Triple DNA metodu, 
format datoteke .dok, eArhivator, eValidator, ChainBlock POE, PLAY.EU, memio.pet, memio.farm, memio.world, 
te sve izvedene tehnologije.</p>

<p>Verzija 1.1 nadopunjuje originalnu OPP v1.0 (objavljenu u Genesis Block #0 dana 19.04.2026.) 
novim <span class="emph">Člankom 27. — Reciprocitet</span> (License Backscratch), 
koji stvara mrežni efekt davanja bez troška.</p>

<h1>I. TEMELJNE ODREDBE (članci 1–26 preneseni iz v1.0)</h1>

<div class="article">
<h3>Članak 1. — Besplatno korištenje</h3>
<p>Konjik d.o.o. kao nositelj intelektualnog vlasništva obvezuje se da će sve tehnologije 
ChainBlock ekosustava <span class="emph">besplatno staviti na raspolaganje</span> svakom korisniku 
(fizičkoj osobi, pravnoj osobi, udruzi, javnoj ustanovi, tijelu EU-a, međunarodnoj organizaciji), 
bez obzira na mjesto sjedišta, svrhu uporabe, veličinu organizacije ili financijsku sposobnost.</p>
</div>

<div class="article">
<h3>Članak 2. — Zabrana tužbi</h3>
<p>Konjik d.o.o. <span class="emph">neopozivo se odriče</span> prava podnošenja tužbi radi povrede 
patentnih, autorskih ili drugih prava intelektualnog vlasništva nad korisnicima koji primjenjuju 
ove tehnologije u skladu s načelom otvorenosti i misijom javnog dobra.</p>
</div>

<div class="article">
<h3>Članak 3. — Zabrana patentiranja izvedenica</h3>
<p>Konjik d.o.o. <span class="emph">neće dopustiti drugima</span> — uključujući buduće vlasnike, 
pravne sljednike ili licencne partnere — da patentiraju izvedena rješenja temeljena na ovdje 
obuhvaćenim tehnologijama. Svaki pokušaj takvog patentiranja Konjik će aktivno osporavati pred 
nadležnim tijelima.</p>
</div>

<div class="article">
<h3>Članak 4. — Prijenos u slučaju gašenja</h3>
<p>U slučaju statusne promjene Konjik d.o.o. (stečaj, likvidacija, prodaja subjektu koji odbija OPP), 
prava iz ovih tehnologija <span class="emph">automatski se prenose bez naknade</span> na 
Udrugu NO LIMIT ili na drugi neprofitni subjekt koji promiče Open Patent Promise 
(Free Software Foundation Europe, Open Source Initiative, ili sličan), o čemu odlučuje tijelo Udruge.</p>
</div>

<p style="font-style:italic;color:#666;margin:4mm 0">Članci 5.–26. zadržavaju se iz v1.0 bez izmjena (dostupno u Genesis Block #0).</p>

<h1>II. NOVI ČLANAK v1.1</h1>

<div class="article key">
<h3>Članak 27. — Reciprocitet (License Backscratch)</h3>

<p><span class="emph">Stavak 1.</span> Ako Korisnik ove OPP licence (fizička ili pravna osoba) 
stekne ili ikada u budućnosti stekne patent ili drugo registrirano pravo intelektualnog vlasništva 
koje pokriva tehnologiju primjenjivu za:</p>
<ol type="a">
<li>digitalnu identifikaciju dokumenata;</li>
<li>perceptivno ili semantičko pretraživanje sadržaja;</li>
<li>verifikaciju autentičnosti bez centralnog autoriteta;</li>
<li>arhivske sustave za digitalne dokumente;</li>
<li>algoritme protiv dezinformacija, deepfake-a ili plagijata;</li>
<li>kriptografske sustave za dokazivanje postojanja (Proof-of-Existence);</li>
</ol>

<p><span class="emph">Stavak 2.</span> Korisnik ovim prihvaćanjem OPP v1.1 licence 
<span class="emph">daje Udruzi NO LIMIT, svim njezinim članovima, Konjik d.o.o. i svim 
ostalim korisnicima OPP mreže doživotnu, besplatnu, neopozivu, svjetsku licencu</span> 
za korištenje takvog patenta ili prava, u svrhe koje nisu u suprotnosti s misijom otvorenih 
standarda i javnog dobra.</p>

<p><span class="emph">Stavak 3.</span> Licenca iz stavka 2. primjenjuje se <span class="emph">retroaktivno</span> 
na sve patente i prava koje Korisnik prijavi ili stekne u bilo kojem trenutku <span class="emph">nakon</span> 
prihvaćanja ove OPP v1.1 licence.</p>

<p><span class="emph">Stavak 4.</span> Licenca iz stavka 2. obuhvaća pravo na:</p>
<ol>
<li>korištenje patentirane tehnologije u vlastitim proizvodima Udruge i njezinih članova;</li>
<li>sublicenciranje drugim korisnicima OPP mreže u istim nekomercijalnim uvjetima;</li>
<li>uključivanje u otvorene standarde koje Udruga razvija ili podržava;</li>
<li>korištenje u obrazovne, istraživačke i humanitarne svrhe bez ikakvih ograničenja.</li>
</ol>

<p><span class="emph">Stavak 5.</span> Korisnik zadržava pravo komercijalne eksploatacije 
vlastitih patenata prema trećim osobama koje nisu dio OPP mreže. Reciprocitet se 
<span class="emph">primjenjuje samo unutar OPP mreže</span>.</p>

<p><span class="emph">Stavak 6.</span> Udruga NO LIMIT vodi javni registar Korisnika OPP mreže 
na svojim mrežnim stranicama. Registar obuhvaća datum prihvaćanja i popis patenata 
koji ulaze u OPP mrežu temeljem ovog članka.</p>

<p><span class="emph">Stavak 7.</span> Odricanje od OPP v1.1 licence ne oslobađa Korisnika 
obveza iz ovog članka u odnosu na patente koje je već prijavio u razdoblju dok je bio 
korisnik OPP-a.</p>
</div>

<h1>III. MEHANIZAM PRIHVAĆANJA</h1>

<p>Korisnik prihvaća OPP v1.1 jednim od sljedećih načina:</p>
<ol>
<li>Preuzimanjem bilo koje tehnologije iz ChainBlock ekosustava (implicitno prihvaćanje);</li>
<li>Pisanim potpisom ovog dokumenta i dostavom Udruzi;</li>
<li>Registracijom u javnom registru OPP mreže na <span class="emph">no-limit.world/opp/registar</span>;</li>
<li>Ugradnjom OPP klauzule u vlastite licence, ugovore ili statute.</li>
</ol>

<h1>IV. PRAVNA OSNOVA I NADLEŽNOST</h1>

<p>Ova licenca uređuje se pravom Republike Hrvatske i Europske unije. Za eventualne sporove nadležan je 
<span class="emph">Općinski sud u Osijeku</span>. Relevantni akti:</p>
<ul>
<li>Zakon o patentu (NN 16/20);</li>
<li>Zakon o obveznim odnosima (NN 35/05, 41/08, 125/11, 78/15, 29/18, 126/21);</li>
<li>Uredba (EU) 2017/1001 o žigu Europske unije;</li>
<li>Direktiva (EU) 2019/790 o autorskom pravu na jedinstvenom digitalnom tržištu.</li>
</ul>

<h1>V. ODNOS PREMA v1.0</h1>

<p>OPP v1.1 ne opoziva OPP v1.0. Postojeći korisnici OPP v1.0 zadržavaju sva prava stečena 
tom verzijom. OPP v1.1 predstavlja <span class="emph">dobrovoljnu nadogradnju</span>, 
koju korisnici mogu prihvatiti u bilo kojem trenutku. Novi korisnici (od dana objave v1.1) 
automatski prihvaćaju v1.1 osim ako izričito naznače drukčije.</p>

<h1>VI. POTPIS I OVJERA</h1>

<p style="margin-top:5mm">Dana 20. travnja 2026., u Vladislavcima, Republika Hrvatska.</p>

<div class="signature">
  <div class="sig-box">
    <span class="emph">Konjik d.o.o.</span><br>
    Zastupnik: Ivan Brtan<br>
    OIB: 70086599476<br><br>
    Potpis i pe&#269;at:
  </div>
  <div class="sig-box" style="text-align:right">
    <span class="emph">Udruga NO LIMIT (u osnivanju)</span><br>
    Predsjednik: Ivan Brtan<br>
    OIB: 70086599476<br><br>
    Potpis:
  </div>
</div>

<p style="margin-top:8mm;font-size:8.5pt;color:#666;text-align:center;font-style:italic">
Kriptografski pe&#269;at dokumenta: izra&#269;unava se nakon finalizacije i pohranjuje u ChainBlock POE kao Block #1<br>
Javna objava: https://no-limit.world/static/udruga_no_limit/opp/NOLIMIT-OPP-v1.1.pdf
</p>

</body></html>'''

pdf = weasyprint.HTML(string=HTML).write_pdf()
path = f"{OUT}/NOLIMIT-OPP-v1.1.pdf"
open(path, "wb").write(pdf)
print(f"OK: {path} ({len(pdf)//1024} KB)")
