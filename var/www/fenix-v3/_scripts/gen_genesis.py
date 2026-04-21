"""
GENESIS BLOCK #0 — Prvi dokument koji samopotvrđuje autorstvo
Triple DNA metode i ChainBlock ekosustava.

Koristi vlastitu tehnologiju (.dok, SHA-256, POE log) da dokaže sebe.
"""
import os, sys, django, hashlib, json, base64
from datetime import datetime, timezone
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit/genesis"
os.makedirs(OUT, exist_ok=True)

# Timestamp — koristimo dan osnivanja Udruge
NOW = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
NOW_STR = NOW.strftime("%Y-%m-%dT%H:%M:%S UTC")
NOW_HR = "19. travnja 2026., 12:00 UTC"

# Učitaj logo
with open("/var/www/fina-connect/static/udruga_no_limit/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO_B64 = base64.b64encode(f.read()).decode()
LOGO_DATA = f"data:image/svg+xml;base64,{LOGO_B64}"

CSS = """
@page {
  margin: 20mm 18mm 26mm 20mm; size: A4;
  @top-center {
    content: "GENESIS BLOCK #0 \\00B7 Samopotvrda autorstva \\00B7 ChainBlock \\00B7 no-limit.world";
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 7.5pt; color: #888;
    border-bottom: 0.3pt solid #ccc; padding-bottom: 2mm;
  }
  @bottom-center {
    content: "Stranica " counter(page) " / " counter(pages);
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 8pt; color: #666;
  }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; color: #000; line-height: 1.55; }

.cover {
  text-align: center; padding: 20mm 10mm;
  border: 2pt solid #000; margin-bottom: 8mm;
  background: #fafafa;
  page-break-after: always;
}
.cover .eyebrow { font-size: 9pt; letter-spacing: 4px; text-transform: uppercase; color: #444; margin-bottom: 5mm; }
.cover h1 { font-size: 22pt; font-weight: 900; letter-spacing: 0.5px; margin-bottom: 3mm; line-height: 1.25; }
.cover h2 { font-size: 13pt; font-weight: 400; color: #333; margin-bottom: 10mm; }
.cover .logo { margin: 5mm 0; }
.cover .logo img { width: 80pt; height: auto; }
.cover .meta { font-size: 9.5pt; color: #333; line-height: 1.8; margin-top: 8mm; }
.cover .hash-block {
  margin-top: 10mm; padding: 4mm; border: 0.8pt solid #000; background: white;
  font-family: monospace; font-size: 8pt; word-break: break-all; text-align: left;
}
.cover .hash-block .lbl { color: #666; font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 7.5pt; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 1mm; display: block; }

h1 { font-size: 15pt; font-weight: 700; margin: 8mm 0 4mm 0; letter-spacing: 0.3px; border-bottom: 1.5pt solid #000; padding-bottom: 2mm; }
h2 { font-size: 12pt; font-weight: 700; margin: 6mm 0 3mm 0; color: #1a1a1a; }
h3 { font-size: 11pt; font-weight: 700; margin: 4mm 0 2mm 0; color: #1a1a1a; }
p { margin-bottom: 3mm; text-align: justify; }
ul, ol { margin: 2mm 0 3mm 7mm; }
li { margin-bottom: 1.5mm; line-height: 1.55; }

.preamble {
  background: #f5f5f5; border-left: 3pt solid #000; padding: 5mm 6mm;
  margin: 4mm 0 6mm 0; font-size: 10pt; line-height: 1.6;
}
.declaration {
  border: 1pt solid #000; padding: 5mm 6mm; margin: 4mm 0;
  background: #fafafa;
}
.declaration h3 { margin-top: 0; }

.tech-spec {
  background: #f8f8f8; padding: 4mm 5mm;
  margin: 3mm 0; font-size: 9.5pt;
  border-left: 2pt solid #333;
}
.tech-spec code { font-family: monospace; background: white; padding: 1pt 3pt; border: 0.3pt solid #ddd; }

table { width: 100%; border-collapse: collapse; margin: 3mm 0; font-size: 9.5pt; }
table th, table td { border: 0.5pt solid #333; padding: 2mm 3mm; vertical-align: top; }
table th { background: #e8e8e8; font-weight: 700; text-align: left; }

.hash-box {
  font-family: monospace; background: #0a0a0a; color: #00FF88;
  padding: 3mm 4mm; font-size: 8.5pt;
  border-radius: 2pt; word-break: break-all;
  margin: 3mm 0;
}
.hash-box .lbl { color: #888; font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 7pt; text-transform: uppercase; letter-spacing: 1.5px; }

.opp-box {
  border: 2pt solid #C9A84C; background: #fffbea;
  padding: 5mm 6mm; margin: 5mm 0;
}
.opp-box h3 { color: #8B6914; margin-top: 0; }

.signature-grid {
  display: flex; justify-content: space-between; margin-top: 10mm;
  page-break-inside: avoid;
}
.signature-grid > div { width: 47%; }
.sig-box { border-top: 1pt solid #000; padding-top: 3mm; font-size: 10pt; }
.emph { font-weight: 700; }

.genesis-seal {
  border: 3pt double #000; padding: 6mm 8mm;
  margin: 8mm 0; background: #fafafa;
  text-align: center;
}
.genesis-seal .label { font-size: 8pt; letter-spacing: 4px; text-transform: uppercase; color: #555; margin-bottom: 2mm; }
.genesis-seal .value { font-family: monospace; font-size: 10pt; color: #000; font-weight: 700; }
"""

CONTENT = f"""
<div class="cover">
  <div class="eyebrow">Genesis Block #0 · ChainBlock ecosystem</div>
  <div class="logo"><img src="{LOGO_DATA}" alt="NO LIMIT"></div>
  <h1>GENESIS DOCUMENT #0</h1>
  <h2>Samopotvrda autorstva Triple DNA metode<br>
  i temeljnih tehnologija ChainBlock ekosustava</h2>

  <div class="meta">
    <strong>Izumitelj:</strong> Ivan Brtan<br>
    <strong>Nositelj intelektualnog vlasništva:</strong> Konjik d.o.o., Čepin<br>
    <strong>Strateški partner (u osnivanju):</strong> Udruga „NO LIMIT", Vladislavci<br>
    <strong>Datum i vrijeme:</strong> {NOW_HR}<br>
    <strong>Mjesto:</strong> Vladislavci, Republika Hrvatska<br>
    <strong>Pravni status:</strong> Prior art disclosure + Open Patent Promise
  </div>

  <div class="hash-block">
    <span class="lbl">Genesis Block #0 — SHA-256 placeholder (izračunava se prilikom finalizacije)</span>
    [FINAL_HASH_PLACEHOLDER]
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════ -->

<h1>I. PREAMBULA</h1>

<div class="preamble">
<p>Ovaj dokument postaje <strong>Genesis Block #0</strong> — prvi zapis u trajnom arhivskom lancu ChainBlock ekosustava. Paradoksalno, dokument <em>sam sebe potvrđuje</em> vlastitom tehnologijom koju opisuje: njegova autentičnost osigurava se Triple DNA metodom, njegova nepobitna vremenska oznaka ugrađuje se u ChainBlock append-only log, a njegova javna objava jamči globalni prior art status.</p>

<p>Ovo nije prijava patenta. Ovo je <strong>javna objava autorstva</strong> s ciljem da se spriječi svako buduće prisvajanje, monopolizacija ili patentiranje izvedenih rješenja bilo koje tehnologije opisane u ovom dokumentu. Dokument istovremeno utvrđuje <strong>Open Patent Promise</strong> licencu — neopozivu obvezu da tehnologije ostaju besplatno dostupne svakom građaninu Europske unije i svijeta, zauvijek.</p>

<p>Dokument nastaje prije službenog upisa Udruge „NO LIMIT" u Registar udruga Republike Hrvatske, kao filozofski i pravni temeljni kamen njezina postojanja.</p>
</div>

<h1>II. DEKLARACIJA AUTORSTVA</h1>

<div class="declaration">
<h3>Izumitelj</h3>
<p>
<span class="emph">IVAN BRTAN</span><br>
OIB: 70086599476<br>
Državljanstvo: Republika Hrvatska<br>
Adresa: Kalnička 19, 31431 Čepin, Republika Hrvatska
</p>

<h3>Nositelj intelektualnog vlasništva</h3>
<p>
<span class="emph">KONJIK d.o.o.</span><br>
Sjedište: Kralja Tomislava 1a, 31431 Čepin, Republika Hrvatska<br>
(trgovačko društvo, dalje: „Nositelj IP-a")
</p>

<h3>Strateški partner za javnu misiju</h3>
<p>
<span class="emph">UDRUGA „NO LIMIT"</span> — Europska udruga za digitalnu transformaciju stvarnog svijeta<br>
Sjedište: Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska<br>
Status: u osnivanju (Osnivačka skupština održana 19.04.2026., upis u Registar udruga RH slijedi)
</p>

<p style="margin-top:4mm">Ovom izjavom <strong>izumitelj Ivan Brtan</strong> potvrđuje da je samostalni autor dolje navedenih tehnologija i rješenja, te <strong>prenosi pravo intelektualnog vlasništva na Nositelja IP-a Konjik d.o.o.</strong>, uz obvezu da se sva prava podvrgnu Open Patent Promise licenci iz odjeljka V. ovog dokumenta.</p>
</div>

<h1>III. TEHNIČKA SPECIFIKACIJA — TRIPLE DNA METODA</h1>

<h2>3.1 Područje tehnike</h2>
<p>Izum pripada području <strong>kriptografske identifikacije digitalnih dokumenata</strong>, poglavito dugotrajnog arhiviranja, detekcije plagijata, otkrivanja deepfake materijala i očuvanja kulturne baštine.</p>

<h2>3.2 Tehnički problem</h2>
<p>Postojeće metode identificiranja digitalnih dokumenata oslanjaju se na jedan kriptografski hash (SHA-256, MD5), koji potpuno otkazuje u slučaju:</p>
<ul>
<li>rekompresije datoteke (npr. JPEG pri drugačijem omjeru kvalitete);</li>
<li>konverzije formata (PDF → DOCX → TXT);</li>
<li>prijevoda teksta na drugi jezik;</li>
<li>minimalne modifikacije (dodana jedna riječ, promijenjen pixel);</li>
<li>deepfake generiranja istog sadržaja drugim sredstvima.</li>
</ul>
<p>Rezultat: ne može se pratiti „isti sadržaj" kroz vrijeme, formate i jezike.</p>

<h2>3.3 Rješenje — Triple DNA identifikator</h2>
<p>Izum predstavlja metodu <strong>trostrukog paralelnog identificiranja</strong> digitalnog dokumenta, gdje se za svaki dokument istodobno izračunavaju tri neovisna identifikatora:</p>

<div class="tech-spec">
<p><span class="emph">L1 — Kriptografski sloj (Cryptographic layer):</span><br>
<code>L1 = SHA-256(binary_content_of_document)</code><br>
Identificira <strong>točnu bit-verziju</strong>. Dva jednaka L1 = identični dokumenti na razini bajta.</p>
</div>

<div class="tech-spec">
<p><span class="emph">L2 — Perceptualni sloj (Perceptual layer):</span><br>
<code>L2 = pHash(normalized_visual_representation(document))</code><br>
Koristi perceptualni hash (npr. DCT-based pHash) nad normaliziranom vizualnom reprezentacijom dokumenta (za slike: rescale + grayscale + DCT; za tekst: normalized font rendering). Omogućuje prepoznavanje <strong>vizualno sličnih verzija</strong> nakon kompresije, rescalinga, blagih modifikacija.</p>
</div>

<div class="tech-spec">
<p><span class="emph">L3 — Semantički sloj (Semantic layer):</span><br>
<code>L3 = normalize(AI_embedding(extracted_semantic_content))</code><br>
Koristi višejezični AI model za generiranje <strong>jezično neovisnog semantičkog embeddinga</strong> (vektor od n dimenzija). Kosinusna sličnost dvaju L3 identifikatora &gt; 0.92 indicira <strong>isto značenje</strong> unatoč drugačijem jeziku, parafrazama ili modificiranom stilu.</p>
</div>

<h2>3.4 Triple DNA identifikator</h2>
<p>Konačni identifikator dokumenta je struktura:</p>
<div class="tech-spec">
<code>TripleDNA = (L1 || "|" || L2 || "|" || L3_hash)</code><br>
<code>where L3_hash = SHA-256(serialize(L3_embedding))</code>
</div>

<h2>3.5 Tehnički efekt</h2>
<ul>
<li><strong>Robustnost kroz transformacije:</strong> dokument ostaje identificiran čak i nakon kompresije, konverzije formata ili prijevoda;</li>
<li><strong>Detekcija plagijata:</strong> semantički slične verzije (L3) se prepoznaju bez potrebe za ljudskim pregledom;</li>
<li><strong>Otkrivanje deepfake materijala:</strong> L2 + L3 mogu identificirati sintetski generirane dvojnike;</li>
<li><strong>Trajni arhiv:</strong> dokument se može pronaći čak i ako je izvornik izgubljen, a postoji druga verzija.</li>
</ul>

<h2>3.6 Industrijska primjena</h2>
<ul>
<li>Pravosuđe (dokazna građa);</li>
<li>Digitalni arhivi i kulturna baština (eArhivator, memio.pet, memio.world);</li>
<li>Mediji (provjera autentičnosti, borba protiv dezinformacija);</li>
<li>Financijske usluge (AML, KYC);</li>
<li>Obrazovanje (detekcija plagijata);</li>
<li>Administracija EU (zaštita javnih dokumenata).</li>
</ul>

<h1>IV. DODATNE TEHNOLOGIJE POD ISTIM AUTORSTVOM</h1>

<p>Uz Triple DNA metodu, ovom izjavom potvrđuje se autorstvo i sljedećih povezanih tehnologija razvijenih u sklopu ChainBlock ekosustava:</p>

<table>
<tr><th>Tehnologija</th><th>Kratki opis</th><th>Status</th></tr>
<tr><td><strong>.dok format</strong></td><td>Arhivski kontejner (ZIP s manifest.xml + master + schema + reader) koji ugrađuje Triple DNA identifikator i WASM verifikator za offline provjeru</td><td>Specificiran</td></tr>
<tr><td><strong>ChainBlock POE</strong></td><td>Append-only log s hash-linking za trajnu potvrdu nastanka (Proof-of-Existence) digitalnih dokumenata</td><td>Specificiran</td></tr>
<tr><td><strong>eArhivator</strong></td><td>Sustav digitalnog arhiviranja temeljen na Triple DNA + ChainBlock POE</td><td>U razvoju</td></tr>
<tr><td><strong>eValidator</strong></td><td>Javna mrežna usluga + WASM/JS offline verifikator za .dok datoteke</td><td>U razvoju</td></tr>
<tr><td><strong>PLAY.EU</strong></td><td>Mreža dječje digitalne baštine nad .dok formatom i Europeana API</td><td>Koncept</td></tr>
<tr><td><strong>memio.pet / memio.farm / memio.world</strong></td><td>Platforme kulturne i akademske baštine nad ChainBlock infrastrukturom</td><td>U razvoju</td></tr>
</table>

<h1>V. OPEN PATENT PROMISE — NEOPOZIVA OBVEZA</h1>

<div class="opp-box">
<h3>Open Patent Promise (OPP) — verzija 1.0</h3>
<p>Nositelj intelektualnog vlasništva <strong>Konjik d.o.o.</strong> ovim dokumentom <strong>javno i neopozivo obvezuje se</strong>:</p>
<ol>
<li>da će sve tehnologije iz odjeljaka III. i IV. ovog dokumenta držati <strong>besplatno na raspolaganju svakom korisniku</strong> (pojedincu, udruzi, trgovačkom društvu, javnoj ustanovi, tijelu EU-a, međunarodnoj organizaciji), bez obzira na mjesto sjedišta ili svrhu uporabe;</li>
<li>da <strong>neće podnositi tužbe radi povrede patentnih ili drugih prava intelektualnog vlasništva</strong> protiv bilo kojeg korisnika koji primjenjuje ove tehnologije u skladu s načelom otvorenosti;</li>
<li>da <strong>neće dopustiti drugima</strong> — uključujući buduće vlasnike, pravne sljednike ili licencne partnere — <strong>da patentiraju izvedena rješenja</strong> temeljena na ovdje specificiranim tehnologijama;</li>
<li>da će u slučaju statusne promjene Nositelja IP-a (stečaj, likvidacija, prodaja subjektu koji odbija OPP) <strong>prenijeti prava bez naknade</strong> na Udrugu „NO LIMIT" ili drugi neprofitni subjekt koji promiče Open Patent Promise (Free Software Foundation Europe, Open Source Initiative, ili sličan).</li>
</ol>
<p>Ova obveza je <strong>neopoziva</strong> i obvezuje sve pravne sljednike Nositelja IP-a. Kršenje ove obveze predstavlja povredu pravičnog poslovanja i temelj za sudski spor u korist korisnika tehnologije.</p>
</div>

<h1>VI. METODOLOGIJA SAMOPOTVRDE</h1>

<p>Autentičnost, vremenska točnost i nepobitnost ovog dokumenta osiguravaju se vlastitim mehanizmima ChainBlock ekosustava:</p>

<h3>6.1 Kriptografski pečat (L1)</h3>
<p>Nakon generiranja konačne PDF verzije ovog dokumenta, izračunava se SHA-256 hash cijele datoteke. Taj hash postaje primarni identifikator ovog Genesis dokumenta:</p>
<div class="hash-box">
<span class="lbl">L1 — SHA-256 (final):</span><br>
[SHA256_PLACEHOLDER]
</div>

<h3>6.2 Vremenski žig</h3>
<p>Vremenski žig ovog dokumenta utvrđuje se na:</p>
<div class="hash-box">
<span class="lbl">Timestamp (UTC):</span><br>
{NOW_STR}
</div>

<h3>6.3 Perceptualni i semantički sloj (L2, L3)</h3>
<p>L2 (pHash rendera PDF-a) i L3 (multilingualni embedding teksta) izračunavaju se u trenutku javne objave i pohranjuju se u ChainBlock POE zapisu.</p>

<h3>6.4 ChainBlock POE Genesis Block #0</h3>
<p>Ovaj dokument ulazi u ChainBlock POE append-only log kao <strong>Block #0</strong> — prvi i jedinstveni Genesis Block ekosustava. Sljedeći svaki blok u lancu referirat će svoj `prev_hash` na L1 hash ovog dokumenta.</p>

<div class="hash-box">
<span class="lbl">ChainBlock POE Genesis Entry (JSON):</span><br>
{{<br>
&nbsp;&nbsp;"block_number": 0,<br>
&nbsp;&nbsp;"prev_hash": null,<br>
&nbsp;&nbsp;"timestamp": "{NOW_STR}",<br>
&nbsp;&nbsp;"document_l1": "[SHA256_PLACEHOLDER]",<br>
&nbsp;&nbsp;"document_name": "NOLIMIT-GENESIS-0001.pdf",<br>
&nbsp;&nbsp;"author": "Ivan Brtan",<br>
&nbsp;&nbsp;"ip_holder": "Konjik d.o.o., Čepin",<br>
&nbsp;&nbsp;"license": "Open Patent Promise v1.0",<br>
&nbsp;&nbsp;"jurisdiction": "HR",<br>
&nbsp;&nbsp;"public_url": "https://no-limit.world/genesis/NOLIMIT-GENESIS-0001.pdf"<br>
}}
</div>

<h3>6.5 Javna objava kao prior art</h3>
<p>Javnom objavom ovog dokumenta i njegova SHA-256 hasha na mrežnoj stranici <strong>no-limit.world/genesis/</strong>, s vremenskim žigom 19.04.2026., postiže se:</p>
<ul>
<li><strong>Prior art status</strong> — nitko drugi nakon ovog datuma ne može prijaviti patent na iste ili vrlo slične tehnologije, jer postoji javno dokumentiran izum koji prethodi;</li>
<li><strong>Nepobitan vremenski dokaz</strong> — datum objave dokumentiran je u HTTP logovima servera, u Git repozitoriju, te kopiran u Internet Archive i WIPO PatentScope (defensive publication);</li>
<li><strong>Dokaz autorstva</strong> — kriptografski vezan SHA-256 hash + javni potpis izumitelja i Nositelja IP-a.</li>
</ul>

<h1>VII. PRAVNA OSNOVA I NADLEŽNOST</h1>

<p>Ovaj dokument i sve obveze koje iz njega proizlaze uređuju se pravom Republike Hrvatske i Europske unije. Za eventualne sporove nadležan je <strong>Općinski sud u Osijeku</strong>.</p>

<p>Relevantni pravni akti:</p>
<ul>
<li>Zakon o patentu (NN 16/20);</li>
<li>Zakon o autorskom pravu i srodnim pravima (NN 111/21);</li>
<li>Europska patentna konvencija (EPC);</li>
<li>Ugovor o suradnji u području patenata (PCT);</li>
<li>Direktiva (EU) 2019/790 o autorskom pravu na jedinstvenom digitalnom tržištu.</li>
</ul>

<h1>VIII. POTPISI I OVJERA</h1>

<p>Potpisom ovog dokumenta izumitelj, Nositelj IP-a i zastupnik strateškog partnera potvrđuju sve navedene činjenice, obveze i pravne učinke.</p>

<div class="signature-grid">
  <div>
    <div class="sig-box">
      <span class="emph">Izumitelj</span><br>
      Ivan Brtan<br>
      OIB: 70086599476<br><br>
      Datum: 19.04.2026.<br>
      Mjesto: Vladislavci<br><br>
      Potpis: _______________________
    </div>
  </div>
  <div>
    <div class="sig-box">
      <span class="emph">Nositelj IP-a — Konjik d.o.o.</span><br>
      Zakonski zastupnik: Ivan Brtan<br>
      OIB tvrtke: [__________]<br><br>
      Datum: 19.04.2026.<br>
      Mjesto: Vladislavci<br><br>
      Potpis i pečat: ________________
    </div>
  </div>
</div>

<div class="signature-grid" style="margin-top:10mm">
  <div>
    <div class="sig-box">
      <span class="emph">Udruga „NO LIMIT" (u osnivanju)</span><br>
      Predsjednik Osnivačke skupštine<br>
      Ivan Brtan, OIB 70086599476<br><br>
      Datum: 19.04.2026.<br>
      Mjesto: Vladislavci<br><br>
      Potpis: _______________________
    </div>
  </div>
  <div>
    <div class="sig-box">
      <span class="emph">Ovjerovitelj — Tajnik Udruge</span><br>
      Ivica Kruljac<br>
      OIB: 82540277049<br><br>
      Datum: 19.04.2026.<br>
      Mjesto: Vladislavci<br><br>
      Potpis: _______________________
    </div>
  </div>
</div>

<div class="genesis-seal">
  <div class="label">Genesis Block #0 — final cryptographic seal</div>
  <div class="value">[SHA256_PLACEHOLDER]</div>
  <div class="label" style="margin-top:4mm">Timestamp (UTC)</div>
  <div class="value">{NOW_STR}</div>
  <div class="label" style="margin-top:4mm">Javna objava</div>
  <div class="value">https://no-limit.world/genesis/</div>
</div>

<p style="margin-top:8mm; text-align:center; font-size:8.5pt; color:#666; font-style:italic">
— ovaj dokument rođen je 19. travnja 2026. u Vladislavcima,<br>
u istom satu u kojem je rođena Udruga koju objavljuje —
</p>
"""

HTML = f"""<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8">
<style>{CSS}</style></head><body>{CONTENT}</body></html>"""

# Render prvo s placeholderom
pdf_draft = weasyprint.HTML(string=HTML).write_pdf()

# Izračunaj SHA-256 draft-a
sha256_draft = hashlib.sha256(pdf_draft).hexdigest()
sha256_upper = sha256_draft.upper()

# Render finalni s ugrađenim hashom
final_html = HTML.replace("[SHA256_PLACEHOLDER]", sha256_upper).replace("[FINAL_HASH_PLACEHOLDER]", sha256_upper)
pdf_final = weasyprint.HTML(string=final_html).write_pdf()

# Izračunaj konačni hash (bit će drugačiji od draft-a jer smo umetnuli hash teksta unutar)
sha256_final = hashlib.sha256(pdf_final).hexdigest()
sha256_final_upper = sha256_final.upper()

# Spremi PDF
pdf_path = f"{OUT}/NOLIMIT-GENESIS-0001.pdf"
with open(pdf_path, "wb") as f:
    f.write(pdf_final)

# Spremi hash fajl
hash_path = f"{OUT}/NOLIMIT-GENESIS-0001.sha256"
with open(hash_path, "w") as f:
    f.write(f"{sha256_final}  NOLIMIT-GENESIS-0001.pdf\n")

# ChainBlock POE Genesis JSON
poe_data = {
    "block_number": 0,
    "prev_hash": None,
    "timestamp": NOW_STR,
    "timestamp_unix": int(NOW.timestamp()),
    "document": {
        "name": "NOLIMIT-GENESIS-0001.pdf",
        "size_bytes": len(pdf_final),
        "l1_sha256": sha256_final,
        "title": "Genesis Document #0 — Samopotvrda autorstva Triple DNA metode",
    },
    "author": {
        "name": "Ivan Brtan",
        "oib": "70086599476",
        "role": "izumitelj"
    },
    "ip_holder": {
        "name": "Konjik d.o.o.",
        "address": "Kralja Tomislava 1a, 31431 Čepin, Hrvatska",
        "role": "nositelj IP-a"
    },
    "strategic_partner": {
        "name": "Udruga NO LIMIT",
        "address": "Kralja Tomislava 291, 31404 Vladislavci, Hrvatska",
        "status": "u osnivanju",
        "role": "strateški partner za javnu misiju"
    },
    "license": "Open Patent Promise v1.0",
    "license_url": "https://no-limit.world/opp/",
    "jurisdiction": "HR",
    "public_url": "https://no-limit.world/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.pdf",
    "technologies": [
        "Triple DNA (L1 SHA-256 + L2 pHash + L3 AI embedding)",
        ".dok format",
        "ChainBlock POE",
        "eArhivator",
        "eValidator",
        "PLAY.EU",
        "memio.pet / memio.farm / memio.world"
    ],
    "note": "Genesis Block #0 — prvi i jedinstveni blok u ChainBlock POE lancu. Služi kao javni prior art, deklaracija autorstva, te pravna osnova za Open Patent Promise licencu."
}

poe_path = f"{OUT}/NOLIMIT-GENESIS-0001.chain.json"
with open(poe_path, "w", encoding="utf-8") as f:
    json.dump(poe_data, f, ensure_ascii=False, indent=2)

# Ispis rezultata
print("=" * 70)
print("GENESIS BLOCK #0 — STVOREN")
print("=" * 70)
print(f"PDF:       {pdf_path}  ({len(pdf_final)//1024} KB)")
print(f"SHA-256:   {sha256_final}")
print(f"Hash fajl: {hash_path}")
print(f"POE JSON:  {poe_path}")
print(f"Timestamp: {NOW_STR}")
print("=" * 70)
