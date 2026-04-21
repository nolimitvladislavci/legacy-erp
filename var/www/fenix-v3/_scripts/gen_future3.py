"""
NO LIMIT — Tri stvari iz budućnosti (Patent strategija)
Trajni dokument koji opisuje vizionarske nadogradnje Patent + OPP modela
"""
import os, sys, django, base64
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit/future"
os.makedirs(OUT, exist_ok=True)

with open("/var/www/fina-connect/static/udruga_no_limit/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO_B64 = base64.b64encode(f.read()).decode()
LOGO_DATA = f"data:image/svg+xml;base64,{LOGO_B64}"

HTML = f"""<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8"><style>
@page {{
  margin: 22mm 18mm 28mm 20mm; size: A4;
  @top-center {{
    content: "NO LIMIT · Future Roadmap · Tri stvari iz budućnosti";
    font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 7.5pt; color: #888;
  }}
  @bottom-center {{
    content: counter(page) " / " counter(pages) "  —  no-limit.world/#future3";
    font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 8pt; color: #666;
  }}
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; color: #000; line-height: 1.6; }}
.cover {{ text-align:center; padding:25mm 8mm; border:2pt solid #000;
  margin-bottom:8mm; background:linear-gradient(135deg,#fafafa 0%,#e8e8e8 100%);
  page-break-after:always; }}
.cover .eyebrow {{ font-size:9pt; letter-spacing:5px; text-transform:uppercase;
  color:#444; margin-bottom:5mm; }}
.cover img {{ width:60pt; height:auto; margin:3mm 0; }}
.cover h1 {{ font-size:26pt; font-weight:900; letter-spacing:0.5px;
  margin:3mm 0; line-height:1.2; }}
.cover h2 {{ font-size:14pt; font-weight:400; color:#333; margin-bottom:10mm; }}
.cover .triad {{ display:flex; justify-content:space-around; gap:6mm; margin-top:12mm; }}
.cover .triad .cell {{ flex:1; padding:5mm; border:1pt solid #000; background:white; }}
.cover .triad .cell .num {{ font-size:30pt; font-weight:900; color:#C9A84C; }}
.cover .triad .cell .title {{ font-size:11pt; font-weight:700; margin:2mm 0; }}
.cover .triad .cell .tag {{ font-size:8pt; color:#666; }}
.cover .meta {{ font-size:9pt; color:#666; margin-top:12mm; line-height:1.8; }}

h1 {{ font-size:18pt; font-weight:700; margin:8mm 0 4mm 0; letter-spacing:0.3px;
  border-bottom:2pt solid #C9A84C; padding-bottom:2mm; }}
h1 .num {{ color:#C9A84C; font-size:28pt; vertical-align:-3pt; margin-right:3mm; }}
h2 {{ font-size:12pt; font-weight:700; margin:5mm 0 2mm 0; }}
h3 {{ font-size:11pt; font-weight:700; margin:4mm 0 2mm 0; }}
p {{ margin-bottom:3mm; text-align:justify; }}
ul, ol {{ margin:2mm 0 3mm 7mm; }}
li {{ margin-bottom:1.5mm; line-height:1.55; }}

.box {{ border-left:2.5pt solid #C9A84C; padding:4mm 5mm; margin:4mm 0; background:#fffbea; }}
.box.red {{ border-color:#dc2626; background:#fef2f2; }}
.box.green {{ border-color:#16a34a; background:#f0fdf4; }}
.box.blue {{ border-color:#1e3a5f; background:#eff6ff; }}

.code {{ background:#f4f4f4; padding:3mm; font-family:monospace; font-size:9pt;
  border-left:2pt solid #555; margin:2mm 0; white-space:pre-wrap; }}

.flow {{ display:flex; gap:3mm; margin:4mm 0; font-size:9.5pt; }}
.flow .step {{ flex:1; background:#fafafa; border:1pt solid #aaa; border-radius:3pt; padding:3mm; }}
.flow .step .lbl {{ font-size:8pt; color:#666; text-transform:uppercase; letter-spacing:1px; }}
.flow .step .val {{ font-weight:700; margin-top:1mm; }}
.arrow {{ display:flex; align-items:center; font-size:14pt; color:#C9A84C; }}

table.tbl {{ width:100%; border-collapse:collapse; margin:3mm 0; font-size:9.5pt; }}
table.tbl th, table.tbl td {{ border:0.5pt solid #333; padding:2mm 3mm;
  text-align:left; vertical-align:top; }}
table.tbl th {{ background:#0f172a; color:white; }}
table.tbl tr:nth-child(even) {{ background:#f5f5f5; }}

.emph {{ font-weight:700; }}
.wau {{ background:#0f172a; color:#C9A84C; padding:4mm 5mm; margin:4mm 0;
  border-radius:3pt; font-size:10.5pt; font-style:italic; }}
.wau .lbl {{ font-size:8pt; letter-spacing:3px; text-transform:uppercase;
  color:#94a3b8; margin-bottom:1mm; }}

.priority-banner {{ background:#16a34a; color:white; padding:3mm 5mm; margin:4mm 0;
  border-radius:3pt; font-weight:700; }}
</style></head><body>

<!-- ══ NASLOVNICA ══ -->
<div class="cover">
  <div class="eyebrow">Future Roadmap · ChainBlock ecosystem</div>
  <img src="{LOGO_DATA}" alt="NO LIMIT">
  <h1>TRI STVARI<br>IZ BUDUĆNOSTI</h1>
  <h2>Vizionarska nadogradnja Patent + OPP modela<br>filozofija · pravna arhitektura · mrežni efekt</h2>

  <div class="triad">
    <div class="cell">
      <div class="num">1</div>
      <div class="title">DAO Ownership Flip</div>
      <div class="tag">pravna arhitektura · 12–18 mj</div>
    </div>
    <div class="cell">
      <div class="num">2</div>
      <div class="title">Collective Prior Art Engine</div>
      <div class="tag">sigurnost · 6 mj</div>
    </div>
    <div class="cell">
      <div class="num">3</div>
      <div class="title">License Backscratch</div>
      <div class="tag">mrežni efekt · 3 mj (SADA)</div>
    </div>
  </div>

  <div class="meta">
    Podnositelj ideja: vanjski AI savjetnik (20.04.2026.) · Mapirano na feedback_future3_rule<br>
    Vlasnik strategije: Udruga NO LIMIT + Konjik d.o.o. (strateški partner)<br>
    Status: roadmap — ratifikacija na prvoj redovnoj sjednici Skupštine Udruge
  </div>
</div>

<!-- ══ UVOD ══ -->
<h1>UVOD — zašto 3 stvari iz budućnosti</h1>
<p>Pravilo ekosustava: u svaki sprint ugrađuju se <span class="emph">tri stvari iz budućnosti</span> — 
<span class="emph">jedna tehnologija</span>, <span class="emph">jedna sigurnost</span>, 
<span class="emph">jedan mrežni efekt</span>. Ovaj dokument preslikava to pravilo na 
patent/OPP sloj ChainBlock ekosustava.</p>

<p>Cilj nije „imati patent". Cilj je <span class="emph">učiniti tehnologiju trajno nepristupačnom za monopolizaciju</span> —
čak i pod uvjetima koje danas ne možemo predvidjeti (preuzimanje tvrtke, politička promjena, 
novi patenski rat, pojava patent trolova). Tri predložene strategije adresiraju tri sloja te obrane.</p>

<div class="wau">
  <div class="lbl">Filozofski okvir</div>
  Patent je ključ. OPP su vrata. Ako želimo da vrata ostanu otvorena zauvijek,
  <strong>moramo ili baciti ključ</strong> (DAO Flip), <strong>ili imati vojsku čuvara</strong> (Prior Art Engine),
  <strong>ili učiniti davanje atraktivnijim od uzimanja</strong> (Backscratch).
</div>

<!-- ══ #1 DAO OWNERSHIP FLIP ══ -->
<h1><span class="num">1</span>DAO Ownership Flip</h1>
<h2>Vlasništvo koje nestaje</h2>

<p>Konjik d.o.o. dobrovoljno prenosi vlasništvo nad Triple DNA patentom na decentraliziranu 
organizaciju (DAO) koju vodi Udruga NO LIMIT. Patent ostaje <span class="emph">aktivan</span> 
(štiti od trolova), ali vlasništvo postaje <span class="emph">tokenizirano i neprodavo</span>.</p>

<h2>Mehanizam — tri kruga prijenosa</h2>

<div class="box blue">
<h3>Krug 1 (2026.) — Konjik → Udruga</h3>
<ul>
<li>Konjik d.o.o. sklapa <span class="emph">Ugovor o darovanju patenta</span> s Udrugom NO LIMIT;</li>
<li>Uvjet u ugovoru: <span class="emph">zauvijek besplatna licenca za OPP</span>;</li>
<li>Javno objavljeno + potpisano + upisano u Registar patenata RH (DZIV);</li>
<li>Pravni temelj: čl. 62 Zakona o patentu RH (prijenos patenta).</li>
</ul>
</div>

<div class="box blue">
<h3>Krug 2 (2027.) — Udruga → Zaklada</h3>
<ul>
<li>Udruga osniva <span class="emph">neprofitnu zakladu</span> (Malta, Švicarska ili Lihtenštajn — jurisdikcije s jasnim foundation law okvirom);</li>
<li>Zaklada drži patent; DAO (na Ethereum/Solana) upravlja licencnim odlukama;</li>
<li>100.000 tokena se dijeli besplatno svakom tko doprinese ekosustavu (kod, dokumentacija, prijevod, edukacija);</li>
<li>Nitko ne može imati više od 1% tokena (osim Udruge koja ima 5% kao čuvar protiv 51% napada).</li>
</ul>
</div>

<div class="box blue">
<h3>Krug 3 (2028.) — Puna decentralizacija</h3>
<ul>
<li>OPP uvjeti postaju <span class="emph">neizmjenjivi</span> (smart contract zaključan);</li>
<li>Patent je u javnoj dobroj, <span class="emph">nepristupačan za tužbe</span> i prodaju;</li>
<li>Konjik, Udruga i svaki pojedinačni nositelj tokena gube ekskluzivu — <span class="emph">svi postaju samo korisnici</span>.</li>
</ul>
</div>

<h2>Pravna posljedica</h2>
<p>Prvi patent u Hrvatskoj koji je <span class="emph">dobrovoljno izgubljen u javno dobro</span>. 
Konkurenti ne mogu kupiti Konjik da bi dobili patent jer ga Konjik više ne posjeduje. 
Politička promjena ne može ga povući jer nije u rukama jedne pravne osobe. Čak i gašenje 
Udruge ne ugrožava patent jer je u zakladi izvan EU jurisdikcije (ali u pravnoj sigurnosti). </p>

<div class="wau">
  <div class="lbl">Wau efekt</div>
  Triple DNA postaje trajno <strong>nepristupačan</strong> — poput Bitcoin-a kad je Satoshi nestao.
  Tehnologija nadživljava sve svoje autore i vlasnike.
</div>

<!-- ══ #2 COLLECTIVE PRIOR ART ENGINE ══ -->
<h1><span class="num">2</span>Collective Prior Art Engine</h1>
<h2>Zajednička obrana od patent trolova</h2>

<p>Umjesto da NO LIMIT sam (ili uz skupe odvjetnike) prikuplja prior art za obranu od patent trolova,
<span class="emph">crowdsourcing</span> obrane: svaki građanin može prijaviti sumnjivi patent i 
<span class="emph">zaraditi nagradu</span> ako se patent dokaže nevažećim.</p>

<h2>Arhitektura</h2>

<div class="code">class CollectivePriorArt:
    """Wikipedia za patente — ali s nagradama."""

    def submit_suspicious_patent(self, patent_nr, submitted_by):
        # 1. Provjera je li već u bazi
        # 2. Automatska pretraga: Google Patents, EPO Espacenet,
        #    WIPO PatentScope, GitHub public commits, arXiv papers
        # 3. Ako se nađe prior art → ljudska verifikacija (3 stručnjaka)
        # 4. Ako je validan → šalji Opposition / Observation EPO/USPTO
        # 5. Ako opozicija uspije → nagrada 10% vrijednosti patenta

    def bounty_calculation(self, patent_nr):
        # Procjena: koliko bi NO LIMIT koštalo da ga licencira?
        # Tipično: 5.000 – 50.000 EUR po patentu
        # Nagrada: 500 – 5.000 EUR po uspješno oborenom patentu</div>

<h2>UI za prijavitelje</h2>

<div class="code">┌─────────────────────────────────────────────────────────────┐
│ 🛡  Prijavi sumnjivi patent                                  │
├─────────────────────────────────────────────────────────────┤
│ Broj patenta:  [ EPO-2026-123456                      ]     │
│                                                             │
│ Zašto misliš da je nevažeći?                                │
│ [ Ova tehnologija je bila u GitHub repozitoriju 2024.  ]    │
│                                                             │
│ 📎 Priloži dokaz:  [ Odaberi datoteku ]                     │
│                                                             │
│ ─────────────────────────────────────────                   │
│   Nagrada ako uspije:  ~1.200 EUR                           │
│ ─────────────────────────────────────────                   │
│                                                             │
│ [ 📤 Prijavi ]    [ 🔍 Prvo pretraži bazu ]                 │
└─────────────────────────────────────────────────────────────┘</div>

<h2>Ekonomija</h2>
<table class="tbl">
<tr><th>Faza</th><th>Tko plaća</th><th>Tko dobiva</th></tr>
<tr><td>Pretraga</td><td>Udruga (automatsko)</td><td>Prijavitelj (dokaz sprema)</td></tr>
<tr><td>Opozicija pred EPO</td><td>Udruga (350–700 EUR)</td><td>Zajednica (trajna obrana)</td></tr>
<tr><td>Uspjeh opozicije</td><td>—</td><td>Prijavitelj: 500–5.000 EUR; Udruga: PR + prestige</td></tr>
</table>

<div class="wau">
  <div class="lbl">Wau efekt</div>
  Patent trolovi više nisu sigurni. Svaki njihov patent može biti srušen od strane
  <strong>bilo koga na svijetu</strong> koji želi zaraditi 1.200 EUR. NO LIMIT postaje
  <strong>Interpol za patente</strong> — ne radi sam, aktivira zajednicu.
</div>

<!-- ══ #3 LICENSE BACKSCRATCH ══ -->
<h1><span class="num">3</span>License Backscratch</h1>
<h2>Dajem ti, ti meni — mrežni efekt kao alternativa donacijama</h2>

<div class="priority-banner">
  ⚡ PRIORITET #3 — najlakši za implementaciju, odmah. Trošak: 0 EUR. Horizont: 3 mjeseca.
</div>

<p>Umjesto da Udruga traži donacije ili članarine, uvodi <span class="emph">recipročnu licencu</span>:
<em>„Ti koristiš naš Triple DNA besplatno. Ako ti ikada patentiraš nešto korisno za nas — 
mi koristimo tvoje besplatno."</em></p>

<h2>Pravna klauzula — Čl. 27 OPP v1.1 (Reciprocitet)</h2>

<div class="box green">
<p><span class="emph">Članak 27. — Reciprocitet</span></p>
<p>Ako Korisnik (pravna ili fizička osoba) ikada stekne patent koji pokriva tehnologiju 
koja se može primijeniti za:</p>
<ol type="a">
<li>digitalnu identifikaciju dokumenata;</li>
<li>perceptivno ili semantičko pretraživanje sadržaja;</li>
<li>verifikaciju autentičnosti bez centralnog autoriteta,</li>
</ol>
<p>Korisnik ovim pristajanjem na OPP licencu <span class="emph">daje Udruzi NO LIMIT 
i svim njezinim članovima doživotnu, besplatnu, neopozivu licencu</span> za korištenje 
tog patenta u nekomercijalne svrhe.</p>
<p>Ova odredba primjenjuje se retroaktivno na sve patente koje Korisnik prijavi 
nakon prihvaćanja OPP v1.1 licence.</p>
</div>

<h2>Mrežni efekt — projekcija</h2>
<table class="tbl">
<tr><th>Godina</th><th>Korisnici OPP-a</th><th>Novi patenti u mreži</th><th>Vrijednost mreže (EUR)</th></tr>
<tr><td>2026</td><td>50</td><td>0</td><td>0</td></tr>
<tr><td>2027</td><td>200</td><td>5</td><td>75.000</td></tr>
<tr><td>2028</td><td>500</td><td>50</td><td>750.000</td></tr>
<tr><td>2029</td><td>1.500</td><td>200</td><td>3.000.000</td></tr>
<tr><td>2030</td><td>5.000</td><td>500</td><td>7.500.000+</td></tr>
</table>

<p style="color:#666;font-size:9pt">Pretpostavke: 10% korisnika generira barem jedan povezan patent u svom radu; 
prosječna licencna vrijednost po patentu u nekomercijalnoj upotrebi: 15.000 EUR/god.</p>

<h2>UI prikaz korisniku (ilustracija)</h2>

<div class="code">┌─────────────────────────────────────────────────────────────┐
│ 🤝 Tvoj patentni portfelj prema NO LIMIT-u                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Ti koristiš:                                                │
│   Triple DNA (Konjik d.o.o.)  — vrijednost:         0 €    │
│                                                             │
│ NO LIMIT koristi tvoje:                                     │
│   • AI Detektor plagijata (tvoj patent 2027)                │
│     vrijednost:                          ~15.000 €/god.    │
│                                                             │
│ BILANCA:  Ti si u plusu      15.000 €/god.  🎉              │
│                                                             │
│ [ 📊 Svi patenti u mreži ]  [ 🤝 Pozovi partnera ]          │
└─────────────────────────────────────────────────────────────┘</div>

<div class="wau">
  <div class="lbl">Wau efekt</div>
  Patentni sustav koji <strong>nagrađuje davanje, ne uzimanje</strong>.
  Što više daš, to više dobiješ natrag. Kapitalizam naopako — ali funkcionira
  jer je temeljen na trajnim zakonskim obvezama, ne na povjerenju.
</div>

<!-- ══ ROADMAP ══ -->
<h1>ROADMAP — kako početi sutra</h1>

<table class="tbl">
<tr><th>#</th><th>Koncept</th><th>Ključna inovacija</th><th>Trošak</th><th>Horizont</th></tr>
<tr><td>3</td><td><span class="emph">License Backscratch</span></td><td>Reciprocitet umjesto donacija</td><td>0 EUR (2h pravnik)</td><td>3 mjeseca</td></tr>
<tr><td>2</td><td>Collective Prior Art Engine</td><td>Rušenje trolova uz nagradu</td><td>~15.000 EUR razvoj</td><td>6 mjeseci</td></tr>
<tr><td>1</td><td>DAO Ownership Flip</td><td>Patent koji nije ničije vlasništvo</td><td>~50.000 EUR (zaklada + tokenomika)</td><td>12–18 mjeseci</td></tr>
</table>

<h2>Akcije PRIJE kraja svibnja 2026. (Prioritet #3)</h2>
<ol>
<li>Pripremiti <span class="emph">OPP v1.1 licencu</span> s čl. 27 (Reciprocitet) — dovršeno danas;</li>
<li>Objaviti OPP v1.1 na <code>no-limit.world/opp/</code> s SHA-256 pečatom;</li>
<li>Ratifikacija na prvoj redovnoj sjednici Skupštine Udruge;</li>
<li>Pozvati prvih 10 partnera (LIMIT Connect, Viskovic Bau, memio.world, PLAY.EU i 6 ostalih) da potpišu;</li>
<li>Javna objava s listom prvih potpisnika.</li>
</ol>

<h2>Akcije do kraja 2026. (Prioritet #2)</h2>
<ol>
<li>Razvoj Python servisa <code>prior_art_engine</code> na LIMIT Connect infrastrukturi;</li>
<li>Integracija s Google Patents API, EPO Open Data, WIPO PatentScope;</li>
<li>Pilot s 3 sumnjivih patenata (test case);</li>
<li>Otvaranje javne baze na <code>no-limit.world/defender/</code>;</li>
<li>Partnerstvo s FSF Europe i OIN (Open Invention Network).</li>
</ol>

<h2>Akcije 2027-2028 (Prioritet #1)</h2>
<ol>
<li>Pravna analiza jurisdikcija za zakladu (Malta / CH / LI);</li>
<li>Tokenomika i smart contract design (audit razina „bank-grade");</li>
<li>Testnet deployment + peer review (6 mj);</li>
<li>Mainnet + Krug 1 prijenos;</li>
<li>Krug 2 + Krug 3 u kasnijim fazama.</li>
</ol>

<!-- ══ MAPIRANJE NA PRAVILO ══ -->
<h1>MAPIRANJE NA PRAVILO „TRI STVARI"</h1>

<table class="tbl">
<tr><th>Stvar iz pravila</th><th>Ovaj sprint — Patent sloj</th></tr>
<tr><td><span class="emph">Tehnologija</span></td><td>Collective Prior Art Engine (Python servis + baza)</td></tr>
<tr><td><span class="emph">Sigurnost</span></td><td>DAO Ownership Flip (patent izvan domašaja pojedinačnog aktera)</td></tr>
<tr><td><span class="emph">Mrežni efekt</span></td><td>License Backscratch (svaki korisnik širi mrežu bez troška)</td></tr>
</table>

<div class="box">
<p>Tri strategije nisu međusobno isključujuće — naprotiv, <span class="emph">jačaju jedna drugu</span>:</p>
<ul>
<li>Backscratch (kratkoročno) širi mrežu korisnika → daje masu za Prior Art Engine;</li>
<li>Prior Art Engine (srednjoročno) štiti mrežu od trolova → daje povjerenje za DAO Flip;</li>
<li>DAO Flip (dugoročno) trajno zaključava sve što je postignuto — <span class="emph">nepobitno</span>.</li>
</ul>
</div>

<!-- ══ KRAJ ══ -->
<h1>ZAKLJUČAK</h1>

<p>Tri stvari iz budućnosti ne predstavljaju tri projekta nego <span class="emph">jedan 
kontinuirani filozofski luk</span>: od <span class="emph">davanja</span> (Backscratch), 
preko <span class="emph">branjenja</span> (Prior Art Engine), do <span class="emph">puštanja</span> 
(DAO Flip). Luk koji od privatnog vlasništva vodi do trajnog javnog dobra — ne naglim 
oduzimanjem, nego sporim dozrijevanjem.</p>

<p>Najveća pobjeda NO LIMIT-a bit će ako za 5 godina nitko više ne treba NO LIMIT — 
jer su sve tehnologije u javnom dobru, svi trolovi bez sredstava, a mreža korisnika 
sama održava otvorenost. Tada Udruga može s mirom prestati postojati — svoju misiju 
je izvršila.</p>

<p style="text-align:center;margin-top:10mm;font-style:italic;color:#555">
— Tri stvari iz budućnosti nisu obećanje.<br>
Tri stvari iz budućnosti su uputstvo za put.<br>
Prva se primjenjuje danas. —
</p>

</body></html>"""

pdf = weasyprint.HTML(string=HTML).write_pdf()
path = f"{OUT}/NOLIMIT-FUTURE3-01.pdf"
with open(path, "wb") as f:
    f.write(pdf)

print(f"OK: {path} ({len(pdf)//1024} KB)")
