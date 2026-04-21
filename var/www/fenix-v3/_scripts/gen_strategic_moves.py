"""
NO LIMIT — 3 strateška poteza protiv Big Tech-a
Obrambena dopuna Future 3 strategije
"""
import os, sys, django, base64, re
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit/future"
os.makedirs(OUT, exist_ok=True)

with open("/var/www/fina-connect/static/udruga_no_limit/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO = base64.b64encode(f.read()).decode()

HTML = f'''<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8"><style>
@page {{
  margin: 22mm 18mm 28mm 20mm; size: A4;
  @top-center {{ content: "NO LIMIT - Strategic Moves - 3 poteza protiv Big Tech"; font-size: 7.5pt; color: #888; }}
  @bottom-center {{ content: counter(page) " / " counter(pages) "  no-limit.world"; font-size: 8pt; color: #666; }}
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; color: #000; line-height: 1.6; }}

.cover {{ text-align:center; padding:25mm 8mm; border:2pt solid #000;
  margin-bottom:8mm; background:linear-gradient(135deg,#0a0f1d 0%,#1a1a2e 100%);
  color:white; page-break-after:always; }}
.cover .eyebrow {{ font-size:9pt; letter-spacing:5px; text-transform:uppercase;
  color:#C9A84C; margin-bottom:5mm; }}
.cover img {{ width:60pt; height:auto; margin:3mm 0; filter:invert(1); }}
.cover h1 {{ font-size:28pt; font-weight:900; letter-spacing:0.5px;
  margin:3mm 0; line-height:1.2; color:white; }}
.cover h2 {{ font-size:14pt; font-weight:400; color:#cbd5e1; margin-bottom:12mm; }}
.cover .triad {{ display:flex; justify-content:space-around; gap:6mm; margin-top:12mm; }}
.cover .triad .cell {{ flex:1; padding:5mm; border:1pt solid #C9A84C; background:rgba(255,255,255,0.05); }}
.cover .triad .cell .num {{ font-size:32pt; font-weight:900; color:#C9A84C; }}
.cover .triad .cell .title {{ font-size:11pt; font-weight:700; margin:2mm 0; color:white; }}
.cover .triad .cell .tag {{ font-size:8pt; color:#94a3b8; }}
.cover .meta {{ font-size:9pt; color:#94a3b8; margin-top:12mm; line-height:1.8; }}

h1 {{ font-size:18pt; font-weight:700; margin:8mm 0 4mm 0; letter-spacing:0.3px;
  border-bottom:2pt solid #dc2626; padding-bottom:2mm; }}
h1 .num {{ color:#dc2626; font-size:32pt; vertical-align:-4pt; margin-right:3mm; }}
h2 {{ font-size:12pt; font-weight:700; margin:5mm 0 2mm 0; }}
h3 {{ font-size:11pt; font-weight:700; margin:4mm 0 2mm 0; }}
p {{ margin-bottom:3mm; text-align:justify; }}
ul, ol {{ margin:2mm 0 3mm 7mm; }}
li {{ margin-bottom:1.5mm; line-height:1.55; }}

.box {{ border-left:2.5pt solid #dc2626; padding:4mm 5mm; margin:4mm 0; background:#fef2f2; }}
.box.blue {{ border-color:#1e3a5f; background:#eff6ff; }}
.box.green {{ border-color:#16a34a; background:#f0fdf4; }}
.box.dark {{ border-color:#C9A84C; background:#0f172a; color:white; }}
.box.dark h3 {{ color:#C9A84C; }}

.code {{ background:#f4f4f4; padding:3mm; font-family:monospace; font-size:9pt;
  border-left:2pt solid #555; margin:2mm 0; white-space:pre-wrap; }}

table.tbl {{ width:100%; border-collapse:collapse; margin:3mm 0; font-size:9.5pt; }}
table.tbl th, table.tbl td {{ border:0.5pt solid #333; padding:2mm 3mm;
  text-align:left; vertical-align:top; }}
table.tbl th {{ background:#dc2626; color:white; }}
table.tbl tr:nth-child(even) {{ background:#f5f5f5; }}

.emph {{ font-weight:700; }}
.wau {{ background:#0f172a; color:#C9A84C; padding:4mm 5mm; margin:4mm 0;
  border-radius:3pt; font-size:10.5pt; font-style:italic; }}
.wau .lbl {{ font-size:8pt; letter-spacing:3px; text-transform:uppercase;
  color:#dc2626; margin-bottom:1mm; font-style:normal; }}

.dialog {{ background:#f8f8f8; border-left:2pt solid #555; padding:4mm 5mm; margin:4mm 0; font-size:10pt; }}
.dialog .speaker {{ font-weight:700; color:#0f172a; }}
</style></head><body>

<div class="cover">
  <div class="eyebrow">Strategic Moves - Defensive Playbook</div>
  <img src="data:image/svg+xml;base64,{LOGO}" alt="NO LIMIT">
  <h1>TRI POTEZA<br>PROTIV BIG TECH-a</h1>
  <h2>Obrambena strategija za trajnu neranjivost ekosustava<br>institucionalni moat - ugovorni otrov - vlasnicki balans</h2>

  <div class="triad">
    <div class="cell">
      <div class="num">1</div>
      <div class="title">Trust Anchor</div>
      <div class="tag">institucionalni moat</div>
    </div>
    <div class="cell">
      <div class="num">2</div>
      <div class="title">Poison Pill</div>
      <div class="tag">otrov za akviziciju</div>
    </div>
    <div class="cell">
      <div class="num">3</div>
      <div class="title">Open Standard Foundation</div>
      <div class="tag">zaklada koja ih drzi za ruke</div>
    </div>
  </div>

  <div class="meta">
    Dopuna Future 3 strategije<br>
    Future 3 = ofenzivno (davanje - branjenje - pustanje)<br>
    Strategic Moves = obrambeno (sidro - otrov - vlast)<br>
    Zajedno = kompletan NO LIMIT Strategic Playbook
  </div>
</div>

<h1>UVOD - zasto tri obrambena poteza</h1>
<p>Future 3 strategije (Backscratch + Prior Art Engine + DAO Ownership Flip) su <span class="emph">evolucijske</span>
- grade mrezu polako i sigurno. Ovo su tri <span class="emph">obrambena poteza</span> namjenjena trenutku
kad Big Tech (Google, Microsoft, Meta, Amazon, ili njihovi pravni partneri) pokusa:</p>
<ul>
<li>kupiti Konjik d.o.o. i povuci OPP,</li>
<li>kopirati tehnologiju i nametnuti svoj standard,</li>
<li>lobirati kod EU institucija da se nas standard odbaci.</li>
</ul>

<p>Svaki potez rjesava jedan od ta tri napada. <span class="emph">Ne trebas ih implementirati istodobno</span> - dolaze prirodno kako ekosustav raste. Ali kad dodje trenutak, nemas vremena ih izmisliti - moraju biti <span class="emph">vec pripremljeni</span>.</p>

<div class="wau">
  <div class="lbl">Filozofski okvir</div>
  Big Tech ima kod, novac i ljudstvo. Ono sto nemaju:
  <strong>legitimitet zajednice</strong>. Ti poteza ne grade bolji proizvod -
  oni grade <strong>nedodirljiv moat</strong> kroz pravo, drustvo i zakon.
</div>

<h1><span class="num">1</span>TRUST ANCHOR</h1>
<h2>Sidro povjerenja koje ne mogu kopirati</h2>

<p>Big Tech moze kopirati tvoj kod, algoritam, arhitekturu. Ono sto ne mogu kopirati jest
<span class="emph">tvoj reputacijski kapital kod gradjana i institucija</span>.</p>

<h2>Potez</h2>

<div class="box blue">
<p>Ne gradis API za Google. Gradis API za:</p>
<ul>
<li><span class="emph">Hrvatske javne biljeznike</span> (integracija u notarijatske informacijske sustave);</li>
<li><span class="emph">Sudove</span> (eSpis integracija, prihvacanje kao dokazno sredstvo u sudskim postupcima);</li>
<li><span class="emph">Arhiviste</span> (Drzavni arhiv, zupanijski arhivi, arhivski standard);</li>
<li><span class="emph">Medije</span> (HINA, novinske agencije, urednicke kuhinje);</li>
<li><span class="emph">Banke</span> (HNB, PBZ, ZABA za AML compliance);</li>
<li><span class="emph">Javnu upravu</span> (e-Gradjanin, e-Porez, e-Mirovinsko).</li>
</ul>
</div>

<p>Kad tvoja tehnologija postane <span class="emph">sluzbena metoda</span> za provjeru autentičnosti
dokumenata u Hrvatskoj, Google moze imati 1000 puta brzi algoritam - ali sud ce prihvatiti
<span class="emph">tvoj potpis</span>, a ne njihov.</p>

<h2>Tehnicka implementacija - Trust Registry</h2>

<div class="code">class TrustRegistry:
    # Registar povjerenja - tko smije potpisivati dokumente

    def __init__(self):
        # Ovo se ne mijenja bez sudske odluke ili izmjene zakona
        self.authorized_signers = [
            "Javni biljeznik Zagreb - Ured Ivana Horvata",
            "Visoki upravni sud RH",
            "Hrvatska narodna banka",
            "Drzavni arhiv u Zagrebu",
            "HINA - Hrvatska novinska agencija",
            "..."
        ]

    def verify_signature(self, document_hash, signature, signer):
        if signer not in self.authorized_signers:
            return {{
                "valid": False,
                "reason": "Potpisnik nije ovlasten prema Zakonu o elektronickim dokumentima"
            }}
        return self.crypto_verify(document_hash, signature)</div>

<h2>UI za institucije</h2>

<div class="code">+-------------------------------------------------------------+
| NO LIMIT Trust Registry                                     |
+-------------------------------------------------------------+
| Ovlasteni potpisnici (clanak 5. Zakona o e-dokumentima):    |
|                                                             |
| [v] Javni biljeznik Zagreb (potpisuje ~150 dok./dan)        |
| [v] Visoki upravni sud RH                                   |
| [v] Hrvatska narodna banka                                  |
| [v] Drzavni arhiv u Zagrebu                                 |
|                                                             |
| Zadnjih 30 dana:                                            |
|   12.847 potpisanih dokumenata                              |
|   0 osporenih potpisa                                       |
|                                                             |
| [Prijavi zlouporabu]  [Zatrazi ukljucenje u registar]       |
+-------------------------------------------------------------+</div>

<h2>Zasto Big Tech ne moze kopirati</h2>
<p>Jer zahtijeva <span class="emph">sudske odluke i zakonske okvire</span>. Google moze imati najbolji algoritam
na svijetu, ali sud ce uvijek priznati potpis javnog biljeznika prije Googleovog "trust scorea".</p>

<div class="wau">
  <div class="lbl">Wau efekt</div>
  Tvoj moat nije tehnologija - tvoj moat je <strong>zakon</strong>.
  A zakon se ne kopira jednim sprint-om - zakon se gradi godinama u ludom kontekstu hrvatskog drzavnog aparata.
  Kad ga jednom imas, Big Tech pristaje ili gubi.
</div>

<h2>Sto radis sutra</h2>
<table class="tbl">
<tr><th>Dan</th><th>Zadatak</th><th>Output</th></tr>
<tr><td>1</td><td>Sastanak s javnim biljeznikom (Osijek)</td><td>Pismo namjere za integraciju Triple DNA</td></tr>
<tr><td>2</td><td>Konzultacije s Pravnim fakultetom</td><td>Analiza Trust Anchor modela za RH pravo</td></tr>
<tr><td>3</td><td>HNB kontakt - AML tim</td><td>Prezentacija eValidator za AML compliance</td></tr>
<tr><td>4</td><td>Drzavni arhiv - Pregled digitalnog arhivskog standarda</td><td>Pismo suradnje</td></tr>
</table>

<p><span class="emph">Trosak:</span> 0 EUR (samo tvoje vrijeme + kave). <span class="emph">Efekt:</span>
pocinjes graditi institucionalni moat koji Big Tech ne moze preskociti.</p>

<h1><span class="num">2</span>POISON PILL</h1>
<h2>Otrovna pilula za akviziciju</h2>

<p>Ako te Big Tech ikada pokusa kupiti, cijena akvizicije ukljucuje <span class="emph">obvezu da OPP
ostane na snazi 100 godina</span>. Ne mogu reci "ne". Jer ako kazu "ne", ti ne prodajes.
A ako ne prodaju, tehnologija ostaje tvoja i nastavlja rasti.</p>

<h2>Pravna konstrukcija</h2>

<div class="box dark">
<h3>Clanak 12. Ugovora o prijenosu patenta (Sponsor Agreement)</h3>

<p><span class="emph">12.1.</span> Stjecatelj (u daljnjem tekstu: Google, Microsoft, ili drugi pravni sljednik)
prihvaca da je Patent (Triple DNA i sve izvedenice) <span class="emph">trajno opterecen OPP licencom</span>
u korist Udruge NO LIMIT na razdoblje od <span class="emph">100 (sto) godina od datuma prijenosa</span>.</p>

<p><span class="emph">12.2.</span> Ova se odredba ne moze izmijeniti niti staviti izvan snage bez pismene suglasnosti
Udruge NO LIMIT i <span class="emph">2/3 vecine registriranih korisnika OPP mreze</span>.</p>

<p><span class="emph">12.3.</span> U slucaju krsenja ove odredbe, Ugovor o prijenosu patenta postaje
<span class="emph">nistavan ex tunc</span> (od pocetka), a Patent se automatski vraca u vlasnistvo
Konjik d.o.o. ili njegovog pravnog sljednika. Stjecatelj nema pravo na povrat sredstava.</p>

<p><span class="emph">12.4.</span> Stjecatelj se obvezuje da ce u roku od 30 dana od potpisa ovog Ugovora
upisati OPP teret u sve patentne registre (DZIV, EPO, USPTO) u kojima je patent aktivan.</p>

<p><span class="emph">12.5.</span> Udruga NO LIMIT ima pravo nadzora nad provedbom ove klauzule kroz
godisnji audit i javnu objavu statusa patenta na no-limit.world.</p>
</div>

<h2>Otrovna pilula u akciji - dijalog</h2>

<div class="dialog">
<p><span class="speaker">Google:</span> "Zelimo kupiti Konjik za 50 milijuna eura."</p>
<p><span class="speaker">Konjik:</span> "Super. Potpisite da OPP ostaje na snazi 100 godina."</p>
<p><span class="speaker">Google:</span> "To je predugo. Dajte 10 godina."</p>
<p><span class="speaker">Konjik:</span> "Ne. 100 godina ili nista."</p>
<p><span class="speaker">Google (za stolom):</span> "Ako ne kupimo, tehnologija postaje standard u EU. Ako kupimo, vezani smo 100 godina da je dajemo besplatno..."</p>
<p><span class="speaker">Google (naglas):</span> "Potpisujemo."</p>
<p><span class="speaker">Razlog:</span> gubitak 50M EUR akvizicije manji je od gubitka EU trzista.</p>
</div>

<h2>Zasto ovo funkcionira</h2>
<p>Jer Big Tech <span class="emph">ne kupuje tehnologiju - kupuje trziste</span>. Ako je tvoje trziste
(institucije iz Poteza #1) uvjetovano OPP-om, oni nemaju izbora.</p>

<div class="wau">
  <div class="lbl">Wau efekt</div>
  Ne prodajes im tehnologiju. Prodajes im <strong>ulaznicu na trziste koje si stvorio</strong>.
  Ulaznica placa 50M EUR i dolazi s ljubavnom opaskom: "Poštujete OPP sto godina ili se ugovor poništava."
</div>

<h1><span class="num">3</span>OPEN STANDARD FOUNDATION (ZOS)</h1>
<h2>Zaklada koja ih drzi za ruke</h2>

<p>Ne drzis patent u Konjiku. Prenosis ga u <span class="emph">neprofitnu zakladu</span> (Zaklada za otvorene
standarde, ZOS) koju vodi konzorcij od 5 ravnopravnih clanova - ukljucujuci Google.</p>

<h2>Pravna arhitektura</h2>

<div class="box green">
<h3>Upravni odbor ZOS-a (5 clanova, 1 glas svaki)</h3>
<ol>
<li><span class="emph">NO LIMIT Udruga</span> - <span class="emph">pravo veta na promjenu OPP-a</span></li>
<li><span class="emph">Pravni fakultet Zagreb</span> - garant usklađenosti sa zakonom i akademska nezavisnost</li>
<li><span class="emph">Hrvatska obrtnicka komora (HOK)</span> - glas malih poduzetnika</li>
<li><span class="emph">Google LLC</span> - glas Big Tech-a (ali s 1/5 tezine, nije dominantan)</li>
<li><span class="emph">Microsoft Corp</span> (ili Meta, ili IBM) - balans unutar Big Tech-a</li>
</ol>
<p><span class="emph">+ Europska komisija</span> kao promatrac (bez prava glasa)</p>
</div>

<h2>Sto ZOS radi</h2>
<ul>
<li>Drzi patent Triple DNA i sve izvedenice;</li>
<li>Licencira ga svima pod OPP uvjetima (nikad monopolno);</li>
<li>Bilo tko moze postati <span class="emph">Certified Implementer</span> (placa 1000 EUR/god za branding + kvalitetne pecate);</li>
<li>Prihod od certifikacije ide u razvoj open-source alata (EurekaLayer, eValidator core, PLAY.EU);</li>
<li>Godisnje javno izvjesce o koristenju (tko, koliko, gdje);</li>
<li>Upravni odbor se sastaje 4x godisnje; promatrac EK dobiva zapisnike.</li>
</ul>

<h2>Zasto Google pristaje na ovo</h2>

<p>Jer im je <span class="emph">bolje biti za stolom nego na jelovniku</span>. Ako ne udju u zakladu,
zaklada ce donijeti standard bez njih - i oni ce ga morati implementirati. Ako udju, imaju priliku
oblikovati standard (ali ne i ukinuti OPP).</p>

<p>To je jedini nacin da ih <span class="emph">drzis blizu, ali ne i na vlasti</span>.</p>

<div class="wau">
  <div class="lbl">Wau efekt</div>
  Google glasanjem (1 od 5) doprinosi evoluciji standarda - i time ga legitimira.
  Svaki put kad Google glasa, on ojacava standard koji mu je namijenio ogranicenje.
  Parados koji radi u nasu korist.
</div>

<h2>Pravna jurisdikcija</h2>

<table class="tbl">
<tr><th>Jurisdikcija</th><th>Prednost</th><th>Manje</th></tr>
<tr><td><span class="emph">Malta</span></td><td>EU clanica, low corporate tax, foundation law razvijen</td><td>Udaljenost od HR-a</td></tr>
<tr><td><span class="emph">Svicarska</span></td><td>Najjaca tradicija foundation law-a (Wikipedia Switzerland Foundation)</td><td>Nije EU, komplicira EU integraciju</td></tr>
<tr><td><span class="emph">Lihtenstajn</span></td><td>Stabilan, blizu HR-a, foundation law izvrstan</td><td>Mala ekonomska tezina</td></tr>
<tr><td><span class="emph">Nizozemska (Stichting)</span></td><td>EU, prestizno, nizi trosak, jak precedent</td><td>Savjetodavna pomoc skupa</td></tr>
</table>

<p><span class="emph">Moja preporuka:</span> <span class="emph">Nizozemska Stichting</span>
(Wikipedia Foundation, Mozilla Foundation, Linux Foundation imaju slicne strukture).</p>

<h1>STRATEGIC PLAYBOOK - kompletna slika</h1>

<table class="tbl">
<tr><th>Tim/Sloj</th><th>Future 3 (ofenzivno)</th><th>Strategic Moves (obrambeno)</th></tr>
<tr><td>Pravno</td><td>License Backscratch (recipr. klauzula)</td><td>Poison Pill (akvizicija = 100 god OPP)</td></tr>
<tr><td>Institucionalno</td><td>DAO Ownership Flip (decentralizacija)</td><td>Open Standard Foundation (ZOS zaklada)</td></tr>
<tr><td>Drustveno</td><td>Prior Art Engine (zajednicki lov)</td><td>Trust Anchor (institucijski moat)</td></tr>
</table>

<p>Dvije runde x 3 poteza = <span class="emph">6-clanih strategija koje rade zajedno</span>. Nikakav pojedinacni napad Big Tech-a nije dovoljan - svaki potez ima uparenu obranu.</p>

<h2>Redoslijed primjene (prioritet)</h2>

<table class="tbl">
<tr><th>Faza</th><th>Future 3</th><th>Strategic Moves</th><th>Horizont</th></tr>
<tr><td><span class="emph">SADA</span></td><td>#3 Backscratch (OPP v1.1)</td><td>#1 Trust Anchor (prvi sastanci)</td><td>0-3 mj</td></tr>
<tr><td>Srednje</td><td>#2 Prior Art Engine (razvoj)</td><td>#2 Poison Pill (OPP v1.2 + Sponsor Agreement)</td><td>3-12 mj</td></tr>
<tr><td>Dugorocno</td><td>#1 DAO Ownership Flip (prijenos)</td><td>#3 ZOS zaklada (osnivanje)</td><td>12-24 mj</td></tr>
</table>

<h1>ZAKLJUCAK</h1>

<p>Future 3 i Strategic Moves nisu konkurentske strategije - one su <span class="emph">dvije strane iste medalje</span>:</p>

<ul>
<li>Future 3 te gradi <span class="emph">prema gore</span> (mreza raste, tehnologija se usavrsava);</li>
<li>Strategic Moves te brani <span class="emph">od gore</span> (Big Tech ne moze prodrijeti u ono sto si izgradio).</li>
</ul>

<p>Zajedno, one cine <span class="emph">kompletan NO LIMIT Strategic Playbook</span> - obrambeno-ofenzivni
instrument koji nadzivljava svoje autore, svoje institucije, svoje konkurente.</p>

<p style="text-align:center;margin-top:10mm;font-style:italic;color:#555">
- Big Tech misli na sljedeci kvartal. NO LIMIT misli na sljedece stoljece. -<br>
- Sto ti misli se dulje, to manje znaci kvartal. -
</p>

</body></html>'''

# Ukloni emojis i posebne znakove
emoji_pattern = re.compile("[\U0001F300-\U0001F9FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001FA70-\U0001FAFF]+", flags=re.UNICODE)
HTML_CLEAN = emoji_pattern.sub("", HTML)

pdf = weasyprint.HTML(string=HTML_CLEAN).write_pdf()
path = f"{OUT}/NOLIMIT-STRATEGIC-MOVES-01.pdf"
open(path, "wb").write(pdf)
print(f"OK: {path} ({len(pdf)//1024} KB)")
