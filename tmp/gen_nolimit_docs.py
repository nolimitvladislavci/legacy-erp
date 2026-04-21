"""
NO LIMIT — Generator svih dokumenata za registraciju udruge
Statut v5, Zapisnik, 6 Odluka, Popis osnivača, Pratno obrazloženje
"""
import os, sys, django, hashlib, base64
sys.path.insert(0, '/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import weasyprint

OUT = "/var/www/fina-connect/static/udruga_no_limit"
os.makedirs(OUT, exist_ok=True)

# Pečat — mono jaje SVG embedded u data URI
with open(f"{OUT}/logos/logo_jaje_mono.svg", "rb") as f:
    LOGO_B64 = base64.b64encode(f.read()).decode()
LOGO_DATA = f"data:image/svg+xml;base64,{LOGO_B64}"

# ── ZAJEDNIČKI CSS ─────────────────────────────────────────────────
CSS = """
@page {
  margin: 22mm 20mm 28mm 22mm; size: A4;
  @bottom-center {
    content: "Udruga NO LIMIT · Kralja Tomislava 291, 31404 Vladislavci · no-limit.world · Stranica " counter(page) " / " counter(pages);
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 8pt; color: #666;
  }
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif;
  font-size: 10.5pt; color: #000; line-height: 1.55;
}
.header {
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 1.5pt solid #000; padding-bottom: 5mm; margin-bottom: 7mm;
}
.header-left { flex: 1; }
.header-left h3 { font-size: 11pt; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 1mm; }
.header-left p { font-size: 8.5pt; color: #333; line-height: 1.5; }
.header-right { min-width: 65pt; text-align: right; }
.header-right img { width: 55pt; height: auto; }

.doc-title-block { text-align: center; margin-bottom: 6mm; }
.doc-title-eyebrow {
  font-size: 8.5pt; color: #555;
  text-transform: uppercase; letter-spacing: 3px;
  margin-bottom: 3mm;
}
.doc-title {
  font-size: 17pt; font-weight: 700; letter-spacing: 0.3px;
  margin-bottom: 2mm;
}
.doc-subtitle {
  font-size: 11.5pt; font-weight: 400; color: #333;
  letter-spacing: 0.2px;
}

.legal-basis {
  font-size: 9.5pt; color: #333;
  margin-bottom: 5mm; padding: 3mm 4mm;
  background: #f5f5f5; border-left: 2pt solid #000;
}
.hr { border: none; border-top: 0.8pt solid #000; margin: 6mm 0; }
.hr-thin { border: none; border-top: 0.3pt solid #999; margin: 4mm 0; }

h1 { font-size: 13pt; font-weight: 700; margin: 6mm 0 3mm 0; letter-spacing: 0.3px; }
h2 {
  font-size: 11.5pt; font-weight: 700;
  margin: 5mm 0 2mm 0;
  color: #1a1a1a; letter-spacing: 0.2px;
  page-break-after: avoid;
}
h3 {
  font-size: 10.5pt; font-weight: 700; margin: 4mm 0 2mm 0;
  color: #1a1a1a; letter-spacing: 0.2px;
  page-break-after: avoid;
}
p { margin-bottom: 2.5mm; text-align: justify; }
ul, ol { margin: 2mm 0 3mm 6mm; }
li { margin-bottom: 1.5mm; line-height: 1.5; }

.article { margin-bottom: 5mm; page-break-inside: avoid; }
.article-title { font-weight: 700; font-size: 10.5pt; margin-bottom: 2mm; }

table { width: 100%; border-collapse: collapse; margin: 3mm 0; font-size: 9.5pt; }
table th, table td { border: 0.5pt solid #333; padding: 2mm 3mm; text-align: left; vertical-align: top; }
table th { background: #e8e8e8; font-weight: 700; }

.signature-block {
  margin-top: 12mm;
  display: flex; justify-content: space-between;
  page-break-inside: avoid;
}
.signature-block > div { width: 46%; }
.signature-block .right { text-align: right; }
.sig-line {
  border-top: 0.8pt solid #000;
  padding-top: 2mm; font-size: 9.5pt;
}
.emph { font-weight: 700; }
.note-box {
  background: #fffbea; border-left: 2pt solid #c9a84c;
  padding: 3mm 4mm; margin: 3mm 0; font-size: 9.5pt;
}
.place-date { margin: 6mm 0 4mm 0; }
"""

def html_header():
    return f'''
<div class="header">
  <div class="header-left">
    <h3>UDRUGA „NO LIMIT"</h3>
    <p>Europska udruga za digitalnu transformaciju stvarnog svijeta<br>
    Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska<br>
    no-limit.world &middot; u osnivanju (19.04.2026.)</p>
  </div>
  <div class="header-right">
    <img src="{LOGO_DATA}" alt="NO LIMIT">
  </div>
</div>
'''

def wrap(title, body, subtitle="", eyebrow=""):
    return f'''<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8">
<style>{CSS}</style></head><body>
{html_header()}
<div class="doc-title-block">
  {f'<div class="doc-title-eyebrow">{eyebrow}</div>' if eyebrow else ''}
  <div class="doc-title">{title}</div>
  {f'<div class="doc-subtitle">{subtitle}</div>' if subtitle else ''}
</div>
{body}
</body></html>'''

def make_pdf(filename, html):
    pdf = weasyprint.HTML(string=html).write_pdf()
    path = f"{OUT}/{filename}"
    with open(path, "wb") as f:
        f.write(pdf)
    return path, len(pdf)

# ══════════════════════════════════════════════════════════════════
# 1. STATUT v5 — 43 članka
# ══════════════════════════════════════════════════════════════════
STATUT_BODY = '''
<div class="legal-basis">
  Na temelju članka 13. Zakona o udrugama (Narodne novine broj 74/14, 70/17, 98/19),
  osnivači Udruge na Osnivačkoj skupštini održanoj dana 19. travnja 2026. godine u Vladislavcima,
  donijeli su ovaj Statut.
</div>

<h1>PREAMBULA</h1>

<p>Mi, osnivači Udruge „NO LIMIT", svjesni povijesnog trenutka u kojem se nalaze Europa i čovječanstvo — trenutka u kojem digitalna transformacija prelazi prag automatizacije i ulazi u eru autonomnih sustava, u kojem umjetna inteligencija postaje suautor ljudske civilizacije, u kojem se redefiniraju pojmovi vlasništva, identiteta, znanja i kulturne baštine — odlučujemo se osnovati Udrugu kao trajni instrument javnog dobra.</p>

<p>Vodimo se uvjerenjem:</p>
<p>— da digitalna transformacija ne smije biti privilegija pojedinaca ni monopol velikih korporacija, nego zajedničko nasljeđe svih građana Europske unije;</p>
<p>— da se temeljna infrastruktura digitalnog doba — formati datoteka, identifikatori, validacijski sustavi i arhivski standardi — ne smije zatvoriti unutar zidova patenata, već mora biti otvorena, slobodna i trajno zaštićena od prisvajanja;</p>
<p>— da male zemlje, lokalne zajednice i obrtnici imaju pravo na alate jednake onima koje koriste najveće svjetske organizacije;</p>
<p>— da kulturna baština i digitalna kreativnost budućih generacija zaslužuju arhiv koji nije ovisan o jednom serveru, jednoj korporaciji ili jednom političkom režimu;</p>
<p>— da digitalna transformacija mora uključiti i osobe s invaliditetom, osobe smanjene pokretljivosti i sve one koji su dosad bili isključeni iz moderne ekonomije;</p>
<p>— da je vrijeme izgraditi tehnološku infrastrukturu koju nitko ne može oduzeti, jer je javno objavljena pod licencom koja zauvijek zabranjuje patentiranje izvedenih rješenja.</p>

<p><span class="emph">A paradoksalno — i upravo zato što promičemo najsuvremeniju digitalnu tehnologiju — prepoznajemo da istinska digitalna suverenost nije moguća bez očuvanja prava građana na gotovinu kao sredstvo plaćanja.</span> Gotovina je zadnja linija privatnosti, autonomije financijskih odluka i otpornosti društva na sustavne poremećaje. Udruga će se zauzeti za hibridni model u kojem gotovina i digitalna plaćanja koegzistiraju kao europska norma. U tom nastojanju Udruga osobito prepoznaje hrvatska tehnološka rješenja koja grade mostove između gotovine i digitalnih instrumenata plaćanja.</p>

<p><span class="emph">Posebno prepoznajemo dužnost prema ljudima u nevolji</span> — žrtvama potresa, poplava, prirodnih katastrofa, starijim i bolesnim osobama bez adekvatnog stambenog zbrinjavanja, obiteljima u iznenadnoj ekonomskoj nevolji — jer digitalna transformacija nema smisla ako društvo ne može zaštititi svoje najranjivije. Izgradnja doma za čovjeka u nevolji je najstariji oblik solidarnosti i najtrajniji oblik baštine.</p>

<p>S tim uvjerenjima polažemo temeljni kamen Udruge „NO LIMIT" u Vladislavcima.</p>

<h1>I. OPĆE ODREDBE</h1>

<div class="article"><div class="article-title">Članak 1. — Naziv</div>
<p>Naziv Udruge glasi: <span class="emph">Udruga „NO LIMIT" — Europska udruga za digitalnu transformaciju stvarnog svijeta</span>. Skraćeni naziv: <span class="emph">NO LIMIT</span>.</p>
<p>Naziv na engleskom: <em>„NO LIMIT" — European Association for Digital Transformation of the Real World</em>.</p>
<p>Naziv na njemačkom: <em>„NO LIMIT" — Europäischer Verein für die digitale Transformation der realen Welt</em>.</p>
</div>

<div class="article"><div class="article-title">Članak 2. — Sjedište</div>
<p>Sjedište Udruge je na adresi: <span class="emph">Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska</span>.</p>
<p>Skupština može odlukom promijeniti adresu sjedišta unutar mjesta Vladislavci bez izmjene Statuta.</p>
</div>

<div class="article"><div class="article-title">Članak 3. — Pravna osobnost i područje djelovanja</div>
<p>Udruga je pravna osoba neprofitnog karaktera upisana u Registar udruga Republike Hrvatske. Udruga djeluje na području Republike Hrvatske, Europske unije i međunarodno.</p>
</div>

<div class="article"><div class="article-title">Članak 4. — Pečat i znak</div>
<p>Udruga ima pečat okruglog oblika, promjera 30 mm, s natpisom: <em>„Udruga NO LIMIT — Vladislavci"</em> uz središnji znak Udruge.</p>
</div>

<div class="article"><div class="article-title">Članak 5. — Zastupanje</div>
<p>Udrugu zastupa Predsjednik Udruge. U slučaju spriječenosti Predsjednika, Udrugu zastupa Tajnik Udruge uz pisanu ovlast Predsjednika. Zastupnici se upisuju u Registar udruga.</p>
</div>

<h1>II. CILJEVI I DJELATNOSTI</h1>

<div class="article"><div class="article-title">Članak 6. — Područja djelovanja</div>
<ol>
<li>Demokratska politička kultura — civilno društvo i digitalno građanstvo;</li>
<li>Obrazovanje, znanost i istraživanje — digitalna pismenost, arhivistika, etika AI;</li>
<li>Kultura i umjetnost — zaštita digitalne kulturne baštine;</li>
<li>Tehnička kultura — razvoj otvorenih tehnologija;</li>
<li>Ljudska prava — pravo na gotovinu, financijska privatnost, digitalna inkluzija osoba s invaliditetom;</li>
<li>Socijalna djelatnost — profesionalna rehabilitacija i zapošljavanje osoba s invaliditetom;</li>
<li>Humanitarna djelatnost — pomoć žrtvama prirodnih katastrofa, starijim i bolesnim osobama, obiteljima u nevolji;</li>
<li>Zaštita od prirodnih nepogoda — pripravnost, odgovor i sanacija posljedica;</li>
<li>Međunarodna suradnja.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 7. — Ciljevi Udruge</div>
<ol>
<li><span class="emph">Digitalna suverenost Europe</span> — otvoreni tehnološki standardi koji štite europske građane, mala i srednja poduzeća, javne ustanove i kulturne institucije od ovisnosti o monopolnim platformama;</li>
<li><span class="emph">Trajna zaštita kulturne i poslovne baštine</span> kroz arhivske formate, sustave validacije identiteta i mreže trajne pohrane podataka;</li>
<li><span class="emph">Promicanje Open Patent Promise</span> kao licencnog modela kojim se ključne tehnologije zauvijek štite od privatizacije;</li>
<li><span class="emph">Zaštita prava na gotovinu</span> i promicanje hibridnih rješenja koegzistencije gotovine i digitalnih plaćanja, s posebnim naglaskom na hrvatske tehnološke platforme;</li>
<li><span class="emph">Digitalna inkluzija osoba s invaliditetom</span> i osoba smanjene pokretljivosti kroz profesionalnu rehabilitaciju u profilima nove ekonomije (posebno AI-asistirano knjigovodstvo);</li>
<li><span class="emph">Stambeno zbrinjavanje osoba u nevolji</span> — zajedničkim dobrovoljnim radom i sredstvima Udruge osiguravati stambeni prostor (obnova, izgradnja, stambeni kontejneri, mobilne kuće, hitna sanacija) za žrtve prirodnih katastrofa, starije, bolesne i obitelji u iznenadnoj ekonomskoj nevolji, uz dosljedno pridržavanje propisa o gradnji i sprječavanju zloupotrebe sredstava;</li>
<li><span class="emph">Demokratizacija pristupa</span> naprednim tehnologijama (AI, blockchain) za male zajednice, obrtnike, neprofitne organizacije;</li>
<li><span class="emph">Edukacija djece i mladih</span> o digitalnoj baštini, kulturnoj pripadnosti i odgovornoj uporabi tehnologija (inicijativa PLAY.EU);</li>
<li><span class="emph">Promicanje kulture sjećanja</span> kroz sustave digitalnog arhiviranja životnih pripovijesti i baštine zajednica (memio.pet);</li>
<li><span class="emph">Suradnja s tijelima Europske unije</span> na projektima digitalne transformacije;</li>
<li><span class="emph">Izgradnja mreže ambasadora</span> s naglaskom na Hrvatsku i Njemačku kao glavna ciljana tržišta;</li>
<li><span class="emph">Promicanje financijske pismenosti i demokratizacije pristupa kapitalnim tržištima</span> za građane EU-a.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 8. — Paradoks digitalne suverenosti: zaštita prava na gotovinu</div>
<p>Udruga kao posebno načelo zastupa stajalište da istinska digitalna suverenost građana Europske unije ne može postojati bez očuvanja prava na gotovinu kao jamca privatnosti, autonomije i otpornosti društva.</p>
<p>Radi toga Udruga:</p>
<ol>
<li>zauzima se za pravo svakog građanina na plaćanje gotovinom;</li>
<li>zagovara hibridni model financijskih usluga u kojem gotovina i digitalna sredstva plaćanja postoje paralelno i ravnopravno;</li>
<li>prepoznaje i promiče hrvatske tehnološke platforme koje omogućuju polaganje gotovine na digitalne instrumente kao primjere dobre prakse;</li>
<li>inicira, sudjeluje i provodi europske istraživačke i zagovaračke projekte o koegzistenciji gotovine i digitalnih plaćanja;</li>
<li>surađuje s ECB, Europskom komisijom, nacionalnim regulatornim tijelima i civilnim društvom.</li>
</ol>
<p>Konkretne komercijalne partnere iz ovog područja Skupština utvrđuje Godišnjim programom rada.</p>
</div>

<div class="article"><div class="article-title">Članak 9. — Djelatnosti kojima se ostvaruju ciljevi</div>
<ol>
<li>organiziranje i provedba edukativnih programa, radionica, seminara i konferencija;</li>
<li>izrada, izdavanje i distribucija stručnih i edukativnih publikacija;</li>
<li>razvoj i objavljivanje tehničkih specifikacija otvorenih standarda;</li>
<li>promicanje i tehnička podrška primjeni Open Patent Promise licenci;</li>
<li>suradnja s odgojno-obrazovnim ustanovama, sveučilištima i istraživačkim centrima;</li>
<li>organiziranje znanstvenih i stručnih skupova;</li>
<li>izrada i upravljanje internetskim platformama Udruge;</li>
<li>prikupljanje, obradba i objavljivanje povijesne, kulturne i arhivske građe;</li>
<li>provedba projekata financiranih iz EU fondova, državnih, županijskih i lokalnih izvora te privatnih donacija;</li>
<li>uspostavljanje i održavanje suradnje sa srodnim udrugama u zemlji i inozemstvu;</li>
<li>zagovaranje pred europskim i nacionalnim tijelima za očuvanje prava na gotovinu i razvoj hibridnih financijskih rješenja;</li>
<li>sudjelovanje u projektima profesionalne rehabilitacije i digitalne inkluzije osoba s invaliditetom i smanjene pokretljivosti;</li>
<li>pružanje usluga (knjigovodstvenih, administrativnih, tehničkih, savjetodavnih) trećim stranama putem zaposlenika Udruge, pri čemu takve usluge ostaju pod upravom i odgovornošću Udruge (model outsourcinga usluga, ne agencijskog rada);</li>
<li>organizacija volonterskih brigada za obnovu i izgradnju stambenih objekata u humanitarnim projektima;</li>
<li>nabavka građevinskog materijala, stambenih kontejnera i mobilnih kuća za humanitarne projekte, uz dokumentiran račun i vlasnički trag;</li>
<li>suradnja s Hrvatskim Crvenim križem, Caritasom, Civilnom zaštitom, jedinicama lokalne i područne samouprave;</li>
<li>upravljanje Fondom za stambeno zbrinjavanje Udruge;</li>
<li>dodjeljivanje stipendija, nagrada i priznanja;</li>
<li>obavljanje ostalih djelatnosti koje pridonose ostvarenju ciljeva Udruge, sukladno zakonu.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 10. — Gospodarske djelatnosti</div>
<p>Udruga može obavljati gospodarske djelatnosti sukladno zakonu, pod uvjetom da su one neposredno povezane s ostvarivanjem ciljeva Udruge i da se ostvarena dobit ulaže isključivo u djelatnosti Udruge.</p>
<ol>
<li>izdavačka djelatnost;</li>
<li>organizacija seminara, konferencija i tečajeva uz naknadu;</li>
<li>izrada i prodaja edukativnih materijala;</li>
<li>usluge tehničke i savjetodavne podrške institucijama u području digitalizacije, arhivistike i hibridnih plaćanja;</li>
<li>usluge certifikacije primjene otvorenih standarda Udruge i OPP licenci;</li>
<li>edukacijski programi profesionalne rehabilitacije osoba s invaliditetom za zanimanja digitalne ekonomije (u okviru akademskog partnerstva, članak 28.);</li>
<li>pružanje stručnih usluga trećim stranama (knjigovodstvene, administrativne, IT i savjetodavne usluge) u okviru programa digitalne inkluzije i AI-asistiranih profesija.</li>
</ol>
</div>

<h1>III. ČLANSTVO</h1>

<div class="article"><div class="article-title">Članak 11. — Članovi Udruge</div>
<p>Članstvo je dobrovoljno. Svi članovi, neovisno o državljanstvu ili prebivalištu, imaju jednaka prava, obveze i odgovornosti.</p>
<p>Članovi Udruge mogu biti:</p>
<ol>
<li><span class="emph">Redovni članovi</span> — fizičke osobe starije od 14 godina i pravne osobe;</li>
<li><span class="emph">Počasni članovi</span> — osobe koje su svojim radom posebno doprinijele ostvarivanju ciljeva.</li>
</ol>
<p>Maloljetni članovi (14–18 g.) — uz pisanu suglasnost zakonskog zastupnika. Pravo odlučivanja u Skupštini imaju punoljetni članovi.</p>
</div>

<div class="article"><div class="article-title">Članak 12. — Učlanjenje</div>
<p>Pristupnica se podnosi u pisanom ili elektroničkom obliku. O redovnom članstvu odlučuje Predsjednik u roku od 30 dana. O počasnom članstvu odlučuje Skupština. Članstvo se stječe upisom u Registar članova.</p>
</div>

<div class="article"><div class="article-title">Članak 13. — Prava članova</div>
<ol>
<li>sudjelovati u radu Udruge i njezinih tijela;</li>
<li>birati i biti birani (punoljetni članovi);</li>
<li>davati prijedloge i mišljenja;</li>
<li>biti informirani o radu Udruge;</li>
<li>koristiti programe i resurse Udruge.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 14. — Članarina</div>
<ol>
<li>Fizička osoba — redovni član: <span class="emph">24 EUR godišnje</span> (2 EUR/mj);</li>
<li>Pravna osoba — redovni član: <span class="emph">120 EUR godišnje</span> (10 EUR/mj);</li>
<li>Djeca i mladi (14–18 g.): oslobođeni od članarine;</li>
<li>Počasni članovi: oslobođeni od članarine;</li>
<li>Sniženi razred (studenti, nezaposleni, umirovljenici, osobe s invaliditetom): <span class="emph">12 EUR godišnje</span>, na temelju pisanog zahtjeva.</li>
</ol>
<p>Članarina se plaća jednokratno ili u mjesečnim obrocima na TR Udruge. Skupština može prilagoditi iznose najviše jednom u 5 godina i najviše 50% u jednom prilagođenju.</p>
</div>

<div class="article"><div class="article-title">Članak 15. — Obveze članova</div>
<ol>
<li>poštivati Statut i odluke tijela Udruge;</li>
<li>djelovati u skladu s ciljevima Udruge;</li>
<li>čuvati ugled Udruge;</li>
<li>redovito plaćati članarinu.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 16. — Prestanak članstva</div>
<ol>
<li>dragovoljnim istupom;</li>
<li>neplaćanjem članarine duže od 12 mjeseci uz prethodnu opomenu;</li>
<li>isključenjem zbog grube povrede Statuta;</li>
<li>smrću ili prestankom pravne osobe.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 17. — Stegovni postupak</div>
<p>O isključenju odlučuje Predsjednik. Prigovor Skupštini u roku od 15 dana. Odluka Skupštine je konačna. Tijekom postupka članu se mora omogućiti očitovanje.</p>
</div>

<h1>IV. TIJELA UDRUGE</h1>

<div class="article"><div class="article-title">Članak 18. — Tijela Udruge</div>
<ol>
<li>Skupština;</li>
<li>Predsjednik Udruge;</li>
<li>Tajnik Udruge;</li>
<li>Blagajnik Udruge;</li>
<li>Zapisničar Udruge;</li>
<li>Likvidator Udruge.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 19. — Skupština</div>
<p>Skupština je najviše tijelo Udruge. Čine je svi punoljetni redovni članovi.</p>
<p>Skupština:</p>
<ol>
<li>donosi Statut i izmjene;</li>
<li>usvaja godišnji program rada i financijski plan;</li>
<li>usvaja godišnje financijsko izvješće;</li>
<li>bira i razrješava sve članove tijela;</li>
<li>odlučuje o prijemu u počasno članstvo;</li>
<li>odlučuje o udruživanju s drugim udrugama;</li>
<li>odlučuje o prestanku Udruge;</li>
<li>odlučuje o raspolaganju imovinom u slučaju prestanka;</li>
<li>odlučuje o strateškim partnerstvima u IP-u (čl. 26.);</li>
<li>odlučuje o plaćama i naknadama (čl. 33.);</li>
<li>odlučuje o drugim pitanjima utvrđenima Statutom.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 20. — Sjednice Skupštine</div>
<p>Redovita sjednica najmanje jedanput godišnje. Izvanredna — na zahtjev Predsjednika ili 1/3 članova.</p>
<p>Kvorum: natpolovična većina članova. Odluke natpolovičnom većinom nazočnih. Iznimka: izmjena Statuta i prestanak Udruge — 2/3 nazočnih.</p>
<p>Sjednice mogu biti elektroničke (videokonferencija) sa zapisnikom i dokazima nazočnosti.</p>
</div>

<div class="article"><div class="article-title">Članak 21. — Predsjednik</div>
<p>Mandat: <span class="emph">pet godina</span>, ponovni izbor moguć.</p>
<p>Predsjednik:</p>
<ol>
<li>zastupa Udrugu;</li>
<li>saziva i predsjedava sjednicama Skupštine;</li>
<li>provodi odluke Skupštine;</li>
<li>potpisuje akte;</li>
<li>odlučuje o tekućim poslovima između sjednica;</li>
<li>odgovara za zakonitost rada;</li>
<li>predlaže godišnji program rada i financijski plan;</li>
<li>sklapa ugovore o uslugama, sponzorstvu i partnerstvima sukladno odlukama Skupštine;</li>
<li>obavlja druge poslove utvrđene Statutom.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 22. — Tajnik</div>
<p>Mandat 5 godina. Tajnik: obavlja administrativne poslove; vodi Registar članova; pomaže Predsjedniku; zastupa Udrugu uz pisanu ovlast Predsjednika.</p>
</div>

<div class="article"><div class="article-title">Članak 23. — Blagajnik</div>
<p>Mandat 5 godina. Može imati prebivalište izvan Republike Hrvatske.</p>
<p>Blagajnik: vodi materijalno-financijsko poslovanje; priprema godišnja financijska izvješća; brine o pravilnoj uporabi sredstava; prati priljeve iz ugovora o uslugama, sponzorstva i donacija; surađuje s računovodstvenim servisom.</p>
</div>

<div class="article"><div class="article-title">Članak 24. — Zapisničar i Likvidator</div>
<p>Mandat 5 godina. Zapisničar vodi zapisnike sjednica i čuva arhivu. Likvidator zastupa Udrugu u postupku likvidacije.</p>
</div>

<h1>V. STRATEŠKA PARTNERSTVA I INTELEKTUALNO VLASNIŠTVO</h1>

<div class="article"><div class="article-title">Članak 25. — Strateški partner za intelektualno vlasništvo</div>
<p>Udruga djeluje kao tehnološki i strateški partner trgovačkog društva <span class="emph">Konjik d.o.o.</span>, Kralja Tomislava 1a, 31431 Čepin (dalje: „Nositelj IP-a"), koje je nositelj intelektualnog vlasništva tehnologija ekosustava ChainBlock — format datoteke .dok, sustav eArhivator, eValidator, mreža PLAY.EU, memio.pet, akademija memio.world i ostale tehnologije.</p>
<p>Odnos uređuje poseban Ugovor o strateškom partnerstvu koji donosi Skupština.</p>
<p>Udruga u suradnji s Nositeljem IP-a obavlja zadaće:</p>
<ol>
<li>promiče primjenu tehnologija u javnom sektoru, obrazovanju, kulturi i civilnom društvu;</li>
<li>osigurava javni nadzor nad provedbom Open Patent Promise licence;</li>
<li>surađuje s tijelima EU i nacionalnim regulatornim tijelima u standardizaciji;</li>
<li>organizira edukaciju i certifikaciju partnera;</li>
<li>zastupa interese korisnika i šire javnosti;</li>
<li>vodi javni registar tehnologija pod Open Patent Promise na platformi LIMIT Connect.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 26. — Zaštitni mehanizmi kontinuiteta tehnologije</div>
<p>Ugovor o strateškom partnerstvu obvezno sadrži odredbe o prijenosu intelektualnog vlasništva s Nositelja IP-a na Udrugu ili na drugi neprofitni subjekt kojeg imenuje Skupština, u slučaju nastupanja bilo kojeg od okidačkih događaja:</p>
<ol>
<li>Otvaranje stečaja ili likvidacije Nositelja IP-a;</li>
<li>Prodaja, pripajanje ili druga statusna promjena Nositelja IP-a subjektu koji pisano odbija prihvatiti obveze OPP licence;</li>
<li>Prestanak aktivnog razvoja i održavanja tehnologije duže od 24 mjeseca;</li>
<li>Pokušaj patentiranja izvedenih rješenja suprotno OPP licenci;</li>
<li>Pisana obavijest Nositelja IP-a o odustajanju od vlasništva;</li>
<li>Nemogućnost pravnog zastupanja Nositelja IP-a duže od 6 mjeseci.</li>
</ol>
<p>Prijenos bez naknade Udruzi. Udruga nastavlja održavati tehnologiju pod istim OPP licencnim uvjetima.</p>
<p>U slučaju prestanka Udruge, tehnologije se prenose na drugi neprofitni subjekt koji promiče OPP (Free Software Foundation Europe, Open Source Initiative ili sličan).</p>
</div>

<div class="article"><div class="article-title">Članak 27. — Open Patent Promise</div>
<p>OPP znači javnu i neopozivu obvezu nositelja IP-a da:</p>
<ol>
<li>tehnologiju stavlja besplatno na raspolaganje svim korisnicima;</li>
<li>ne podnosi tužbe radi povrede patentnih prava nad korisnicima;</li>
<li>ne dopušta drugima da patentiraju izvedena rješenja.</li>
</ol>
<p>Udruga vodi javni registar tehnologija pod OPP na mrežnim stranicama.</p>
</div>

<div class="article"><div class="article-title">Članak 28. — Partnerski projekt digitalne inkluzije (AI + Čovjek)</div>
<p>Udruga podupire i sudjeluje u strateškom projektu „AI + Čovjek — Akademija za digitalnu inkluziju", u partnerstvu s Konjik d.o.o. i obrazovnom platformom memio.world.</p>
<p>Ciljevi projekta:</p>
<ol>
<li>Profesionalna rehabilitacija osoba s invaliditetom i osoba smanjene pokretljivosti kroz online edukaciju;</li>
<li>Certifikacija nove kategorije zanimanja: AI-asistirani knjigovođa;</li>
<li>Zapošljavanje certificiranih osoba u AI-knjigovodstvenim servisima Konjika i drugih licenciranih partnera;</li>
<li>Online poslovanje bez fizičke prisutnosti, primjereno osobama smanjene pokretljivosti.</li>
</ol>
<p>Udruga u projektu: javno promicanje; razvoj obrazovnih standarda; verifikacija diploma preko memio.world; povezivanje s organizacijama osoba s invaliditetom; prijava na ESF+, InvestEU, Digital Europe Programme.</p>
<p>Projekt se provodi sukladno Europskom aktu o pristupačnosti (EU 2019/882) i UN Konvenciji o pravima osoba s invaliditetom.</p>
</div>

<div class="article"><div class="article-title">Članak 29. — Program stambenog zbrinjavanja „DOM"</div>
<p>Udruga provodi stalni program humanitarnog stambenog zbrinjavanja pod nazivom <span class="emph">„Program DOM"</span> (engl. Programme HOME, njem. Programm HEIM).</p>
<p><span class="emph">Stavak 1. Cilj:</span> osigurati adekvatni stambeni prostor osobama koje su zbog prirodne katastrofe, zdravstvenih prilika, starosti, invaliditeta ili iznenadne ekonomske nevolje ostale bez doma ili žive u uvjetima nepodobnim za život.</p>
<p><span class="emph">Stavak 2. Oblici:</span></p>
<ol>
<li>Hitna intervencija (popravak krovišta, zatvaranje otvora, grijanje);</li>
<li>Obnova postojećeg objekta korisnika;</li>
<li>Postavljanje stambenog kontejnera;</li>
<li>Postavljanje mobilne kuće;</li>
<li>Nova gradnja na zemljištu korisnika, Udruge ili partnera;</li>
<li>Prilagodba prostora osobama s invaliditetom.</li>
</ol>
<p><span class="emph">Stavak 3. Kategorije korisnika:</span> žrtve katastrofa; starije i bolesne osobe bez adekvatnog stanovanja; obitelji u iznenadnoj nevolji; osobe s invaliditetom; djeca i mladi bez stabilnog doma.</p>
<p><span class="emph">Stavak 4. Način izvođenja:</span> dobrovoljni rad volontera + sredstva Fonda za stambeno zbrinjavanje + sredstva donacija i EU fondova + stručna koordinacija. Svaki projekt ima projektni broj, dnevnik radova, popis troškova i fotodokumentaciju.</p>
<p><span class="emph">Stavak 5. Vlasništvo:</span> rezultati u pravilu postaju vlasništvo korisnika pomoći bez naknade, uz obvezu da objekt ne otuđuje 10 godina osim iznimno.</p>
<p><span class="emph">Stavak 6. Poseban TR:</span> Udruga otvara poseban transakcijski račun za Program DOM, mjesečno javno objavljuje bilancu.</p>
</div>

<h1>VI. IMOVINA, FINANCIRANJE I RAD</h1>

<div class="article"><div class="article-title">Članak 30. — Imovina</div>
<ol>
<li>novčana sredstva (članarine, donacije, sponzorstva);</li>
<li>nekretnine i pokretnine;</li>
<li>prihodi od projekata;</li>
<li>prihodi od gospodarskih djelatnosti;</li>
<li>prava intelektualnog vlasništva po čl. 26.;</li>
<li>drugi prihodi sukladno zakonu.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 31. — Financiranje</div>
<ol>
<li>članarine;</li>
<li>donacije;</li>
<li>sredstva državnog, županijskog i lokalnog proračuna;</li>
<li>sredstva EU fondova i međunarodnih izvora;</li>
<li>prihodi od ugovora o uslugama i sponzorstvima;</li>
<li>prihodi od gospodarskih djelatnosti;</li>
<li>ostali izvori.</li>
</ol>
<p>Poslovne knjige vode se sukladno propisima o neprofitnim organizacijama. Javna obavijest za priljeve iznad 1.000 EUR iz istoga izvora u roku 30 dana.</p>
</div>

<div class="article"><div class="article-title">Članak 32. — Sprječavanje zloupotrebe, pranja novca i financiranja terorizma</div>
<p>Udruga se načelno i bezuvjetno zavjetuje da neće biti zloupotrebljena za pranje novca, financiranje terorizma niti druge oblike financijske prijevare. Primjenjuje mjere koje nadilaze zakonski minimum.</p>
<p><span class="emph">Stavak 1. Zakonodavni okvir:</span> Zakon o sprječavanju pranja novca i financiranja terorizma (NN 108/17, 39/19); Direktive EU 2015/849 (AMLD4), 2018/843 (AMLD5), 2018/1673 (AMLD6); Preporuka 8 FATF-a; Zakon o humanitarnoj pomoći (NN 102/15); Zakon o financijskom poslovanju neprofitnih organizacija (NN 121/14).</p>
<p><span class="emph">Stavak 2. Ovlaštena osoba za usklađenost:</span> Tajnik Udruge. Vodi Registar velikih transakcija (&gt; 10.000 EUR); Registar donatora; provjerava identitet donatora iznad pragova; prijavljuje sumnjive transakcije.</p>
<p><span class="emph">Stavak 3. Pragovi za donacije:</span></p>
<ol>
<li>Gotovinske donacije — isključivo do 200 EUR po donatoru godišnje, uz izdavanje potvrde;</li>
<li>Ostale — putem bankovnog transfera;</li>
<li>Donacije iznad 500 EUR — verifikacija identiteta;</li>
<li>Udruga NE prihvaća donacije iz zemalja FATF crne liste, ni iz anonimnih izvora iznad 200 EUR;</li>
<li>Donacije iznad 5.000 EUR — pisana izjava o izvoru sredstava.</li>
</ol>
<p><span class="emph">Stavak 4. Pragovi za isplate:</span> &gt; 1.000 EUR dvostruki potpis (Predsjednik + Blagajnik); &gt; 10.000 EUR odluka Skupštine.</p>
<p><span class="emph">Stavak 5. Program DOM kontrole:</span> prethodna procjena potrebe od CK/Caritasa/JLS-a; evidencija korisnika; 11 godina čuvanje računa; ex-post izvješće s fotodokumentacijom; neovisni revizor za projekte &gt; 25.000 EUR.</p>
<p><span class="emph">Stavak 6. „Staklena kuća" — javna transparentnost:</span> mjesečna bilanca Programa DOM; javni popis donatora &gt; 500 EUR; javni popis korisnika pomoći (bez osobnih podataka); godišnje izvješće o usklađenosti; obvezna revizija za prihod &gt; 100.000 EUR; pravo građana na pisani upit o transakcijama &gt; 1.000 EUR (odgovor u 30 dana).</p>
<p><span class="emph">Stavak 7. Sukob interesa:</span> članovi tijela obvezno pisano prijavljuju mogući sukob interesa i isključuju se iz odlučivanja.</p>
<p><span class="emph">Stavak 8. Posljedice zloupotrebe:</span> hitno isključenje; prijava nadležnim tijelima; građanska tužba za naknadu štete.</p>
</div>

<div class="article"><div class="article-title">Članak 33. — Rad, plaće, naknade i volonterstvo</div>
<p><span class="emph">Stavak 1. Zaposlenici:</span> Udruga može zapošljavati osobe, bez ograničenja broja. Teži da neto plaće budu razmjerne prosjeku EU za kvalificirana zanimanja u istoj djelatnosti, ostvarivo u granicama financijskog plana.</p>
<p><span class="emph">Stavak 2. Obavljanje usluga za treće strane:</span> zaposlenici mogu biti angažirani za pružanje usluga trećim stranama preko Udruge (knjigovodstvene, tehničke, edukacijske). Ova djelatnost ne predstavlja agencijski rad.</p>
<p><span class="emph">Stavak 3. Osnivači i članovi tijela:</span> u načelu volonterski. Skupština može odobriti plaću uz uvjete:</p>
<ol>
<li>Financijski plan predviđa takve troškove;</li>
<li>Rad dokumentiran satnicom i izvješćem;</li>
<li>Iznos razmjeran prosjeku EU za kvalificirana zanimanja;</li>
<li>Ukupne plaće svih članova tijela ≤ 30% godišnjeg prihoda iz neinvesticijskih izvora;</li>
<li>Svi iznosi javno se objavljuju.</li>
</ol>
<p>Članovi tijela mogu istovremeno biti i zaposlenici Udruge uz pisani ugovor o radu ili o djelu.</p>
<p><span class="emph">Stavak 4. Suradnici i vanjski izvođači:</span> ugovori o djelu, uslugama i autorskim ugovorima. Naknade prema tržišnim uvjetima.</p>
<p><span class="emph">Stavak 5. Volonteri:</span> sukladno Zakonu o volonterstvu. Naknade stvarnih troškova (putovanje, smještaj, prehrana, materijal, obrazovanje). Simbolična materijalna nagrada sukladna Zakonu.</p>
</div>

<h1>VII. JAVNOST RADA</h1>

<div class="article"><div class="article-title">Članak 34. — Javnost djelovanja</div>
<p>Rad Udruge je javan. Javnost se osigurava javnošću sjednica Skupštine, objavom akata, publikacijama i komunikacijom s medijima.</p>
</div>

<div class="article"><div class="article-title">Članak 35. — Mrežna stranica</div>
<p>Udruga održava javnu mrežnu stranicu na adresi <span class="emph">no-limit.world</span> i objavljuje: Statut i opće akte; godišnje programe rada i financijska izvješća; popis tijela i naknade; Ugovor o strateškom partnerstvu s Nositeljem IP-a; registar tehnologija pod OPP; obavijesti o priljevima &gt; 1.000 EUR; obavijesti o sjednicama, projektima i događanjima.</p>
</div>

<h1>VIII. PRESTANAK UDRUGE</h1>

<div class="article"><div class="article-title">Članak 36. — Razlozi prestanka</div>
<ol>
<li>odluka Skupštine (2/3 nazočnih);</li>
<li>pripajanje, spajanje, podjela;</li>
<li>razlozi utvrđeni zakonom.</li>
</ol>
</div>

<div class="article"><div class="article-title">Članak 37. — Postupak likvidacije</div>
<p>Likvidacija sukladno Zakonu o udrugama. Likvidator zastupa Udrugu, podmiruje obveze, raspoređuje imovinu.</p>
</div>

<div class="article"><div class="article-title">Članak 38. — Sudbina imovine</div>
<p>Preostala imovina pripada drugoj udruzi, ustanovi ili zakladi sa sličnim ciljevima (u prvom redu subjektima koji promiču Open Patent Promise). Tehnologije iz čl. 26. prenose se sukladno čl. 26. Imovina se ne smije raspodijeliti članovima.</p>
</div>

<h1>IX. PRIJELAZNE I ZAVRŠNE ODREDBE</h1>

<div class="article"><div class="article-title">Članak 39. — Stupanje na snagu</div>
<p>Statut stupa na snagu danom donošenja na Osnivačkoj skupštini, a primjenjuje se od dana upisa Udruge u Registar udruga RH.</p>
</div>

<div class="article"><div class="article-title">Članak 40. — Izmjene i dopune Statuta</div>
<p>Izmjene i dopune donosi Skupština 2/3 većinom nazočnih članova.</p>
</div>

<div class="article"><div class="article-title">Članak 41. — Tumačenje Statuta</div>
<p>Tumačenje daje Skupština. Između sjednica, hitno tumačenje daje Predsjednik, uz potvrdu Skupštine na prvoj sljedećoj sjednici.</p>
</div>

<div class="place-date">
  <p>U Vladislavcima, dana 19. travnja 2026. godine.</p>
</div>

<div class="signature-block">
  <div>
    <div class="sig-line">
      <span class="emph">Predsjednik Osnivačke skupštine</span><br>
      Ivan Brtan<br>
      OIB: 70086599476
    </div>
  </div>
  <div class="right">
    <div class="sig-line">
      <span class="emph">Pečat Udruge</span><br>
      (postavlja se nakon upisa u Registar)
    </div>
  </div>
</div>
'''

# ══════════════════════════════════════════════════════════════════
# 2. ZAPISNIK OSNIVAČKE SKUPŠTINE
# ══════════════════════════════════════════════════════════════════
ZAPISNIK_BODY = '''
<p><span class="emph">Datum održavanja:</span> 19. travnja 2026. (nedjelja)<br>
<span class="emph">Vrijeme:</span> 12:00 — 14:30 sati<br>
<span class="emph">Mjesto:</span> Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska</p>

<h2>1. Nazočni</h2>
<p>Osnivačkoj skupštini nazočni su svi osnivači Udruge:</p>
<table>
<tr><th>#</th><th>Ime i prezime</th><th>OIB</th><th>Adresa</th><th>Funkcija</th></tr>
<tr><td>1.</td><td>Ivan Brtan</td><td>70086599476</td><td>Kalnička 19, 31431 Čepin</td><td>Predsjednik</td></tr>
<tr><td>2.</td><td>Ivica Kruljac</td><td>82540277049</td><td>Kralja Tomislava 291, 31404 Vladislavci</td><td>Tajnik</td></tr>
<tr><td>3.</td><td>Marija Brtan</td><td>[_______________]</td><td>[____________________________]</td><td>Zapisničar</td></tr>
<tr><td>4.</td><td>Antonio Brtan</td><td>28907401487</td><td>Grabenstrasse 29 E, 71116 Gärtringen, DE</td><td>Blagajnik</td></tr>
</table>
<p><span class="emph">Kvorum:</span> 4 od 4 osnivača nazočno (100 %). Skupština je pravovaljana.</p>

<h2>2. Dnevni red</h2>
<ol>
<li>Otvaranje Osnivačke skupštine i izbor radnih tijela;</li>
<li>Utvrđivanje namjere osnivanja Udruge;</li>
<li>Donošenje Odluke o osnivanju Udruge;</li>
<li>Donošenje Statuta Udruge;</li>
<li>Izbor osoba ovlaštenih za zastupanje Udruge;</li>
<li>Izbor članova tijela Udruge;</li>
<li>Donošenje Odluke o privremenom vizualnom identitetu;</li>
<li>Donošenje Odluke o usvajanju Programa DOM;</li>
<li>Donošenje Odluke o pokretanju postupka za upis u Registar udruga RH;</li>
<li>Ovlaštenje Predsjedniku za provedbu zaključaka;</li>
<li>Razno.</li>
</ol>

<h2>3. Tijek sjednice</h2>

<h3>Točka 1. — Otvaranje i izbor radnih tijela</h3>
<p>Osnivač Ivan Brtan otvorio je sjednicu i predložio radna tijela:</p>
<ul>
<li>Predsjedavajući: Ivan Brtan</li>
<li>Zapisničar: Marija Brtan</li>
<li>Ovjerovitelji zapisnika: Ivica Kruljac i Antonio Brtan</li>
</ul>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno.</p>

<h3>Točka 2. — Namjera osnivanja</h3>
<p>Predsjedavajući iznio je namjeru osnivanja Udruge „NO LIMIT" — Europske udruge za digitalnu transformaciju stvarnog svijeta. Posebno su istaknuti:</p>
<ol>
<li>misija očuvanja digitalne suverenosti Europe kroz Open Patent Promise;</li>
<li>strateško partnerstvo s Konjik d.o.o. (Čepin) kao nositeljem IP-a ekosustava ChainBlock;</li>
<li>zaštita prava građana na gotovinu kao sredstvo plaćanja;</li>
<li>digitalna inkluzija osoba s invaliditetom kroz akademiju memio.world;</li>
<li>humanitarno stambeno zbrinjavanje osoba u nevolji kroz Program DOM.</li>
</ol>
<p>Svi osnivači su izjavili da su upoznati s nacrtom Statuta, da ga u cijelosti podržavaju i da pristupaju osnivanju dobrovoljno.</p>

<h3>Točka 3. — Donošenje Odluke o osnivanju</h3>
<p>Donosi se Odluka o osnivanju Udruge „NO LIMIT".<br>
<span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 4. — Donošenje Statuta</h3>
<p>Nakon čitanja i rasprave po člancima, Osnivačka skupština donosi Statut Udruge „NO LIMIT" u verziji s 41 člankom i 9 poglavlja, uključujući preambulu, opće odredbe, ciljeve (čl. 6–10), članstvo (čl. 11–17), tijela s petogodišnjim mandatom (čl. 18–24), strateška partnerstva i IP (čl. 25–28), Program DOM (čl. 29), imovinu i AML mehanizme (čl. 30–33), javnost rada (čl. 34–35), prestanak (čl. 36–38), prijelazne odredbe (čl. 39–41).</p>
<p><span class="emph">Odluka:</span> Statut je prihvaćen jednoglasno (4 : 0). Statut se prilaže kao Prilog 1.</p>

<h3>Točka 5. — Izbor osobe ovlaštene za zastupanje</h3>
<p>Imenuje se <span class="emph">Ivan Brtan</span> (OIB: 70086599476), Predsjednik Udruge, kao osoba ovlaštena za zastupanje. U slučaju spriječenosti Predsjednika zastupa Tajnik Udruge uz pisanu ovlast.</p>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 6. — Izbor članova tijela Udruge</h3>
<p>Za članove tijela na mandat od 5 godina (19.04.2026. — 19.04.2031.) izabrani su:</p>
<table>
<tr><th>Funkcija</th><th>Ime i prezime</th><th>OIB</th></tr>
<tr><td>Predsjednik</td><td>Ivan Brtan</td><td>70086599476</td></tr>
<tr><td>Tajnik</td><td>Ivica Kruljac</td><td>82540277049</td></tr>
<tr><td>Zapisničar</td><td>Marija Brtan</td><td>[_______________]</td></tr>
<tr><td>Blagajnik</td><td>Antonio Brtan</td><td>28907401487</td></tr>
<tr><td>Likvidator</td><td>Ivan Brtan (privremeno)</td><td>70086599476</td></tr>
</table>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 7. — Odluka o privremenom vizualnom identitetu</h3>
<p>Donosi se Odluka kojom se utvrđuje privremeni logo i pečat te ovlašćuje Predsjednik da u roku od 90 dana od upisa u Registar odabere finalni vizualni identitet između triju pripremljenih varijanti, uz naknadnu potvrdu Skupštine.</p>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 8. — Odluka o pokretanju Programa DOM</h3>
<p>Donosi se Odluka o uspostavi i pokretanju Programa stambenog zbrinjavanja „DOM" s početkom od dana upisa Udruge u Registar. Predsjednik se zadužuje da u roku od 60 dana:</p>
<ol>
<li>otvori poseban transakcijski račun za Program DOM;</li>
<li>inicira potpisivanje Memoranduma o suradnji s Hrvatskim Crvenim križem i/ili Caritasom;</li>
<li>pripremi Protokol Programa DOM za potvrdu na prvoj redovnoj Skupštini.</li>
</ol>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 9. — Odluka o pokretanju postupka za upis</h3>
<p>Donosi se Odluka o pokretanju postupka za upis Udruge u Registar udruga RH kod Upravnog odjela za opću upravu Osječko-baranjske županije. Predsjednik se ovlašćuje da provede cjelokupan postupak.</p>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 10. — Ovlaštenje Predsjedniku</h3>
<p>Predsjednik Ivan Brtan ovlašćuje se za provedbu svih zaključaka Osnivačke skupštine, uključujući predaju zahtjeva za upis, otvaranje TR, zatraživanje OIB-a Udruge, sklapanje ugovora o strateškom partnerstvu s Konjik d.o.o., predstavljanje Udruge.</p>
<p><span class="emph">Odluka:</span> Prihvaćeno jednoglasno (4 : 0).</p>

<h3>Točka 11. — Razno</h3>
<p>Osnivači iznose podršku misiji Udruge i izjavljuju spremnost na aktivno sudjelovanje u radu.</p>

<h2>4. Završetak</h2>
<p>Predsjedavajući je u 14:30 sati zaključio sjednicu. Svi doneseni akti stupaju na snagu danom donošenja, a u odnosu na treće osobe danom upisa u Registar udruga RH.</p>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>

<div class="signature-block">
  <div>
    <div class="sig-line"><span class="emph">Predsjedavajući</span><br>Ivan Brtan</div>
    <div class="sig-line" style="margin-top:8mm"><span class="emph">Ovjerovitelj</span><br>Ivica Kruljac</div>
  </div>
  <div class="right">
    <div class="sig-line"><span class="emph">Zapisničar</span><br>Marija Brtan</div>
    <div class="sig-line" style="margin-top:8mm"><span class="emph">Ovjerovitelj</span><br>Antonio Brtan</div>
  </div>
</div>

<div class="note-box" style="margin-top:8mm">
<strong>Prilozi uz Zapisnik:</strong> 1) Statut Udruge (43 članka); 2) Odluka o osnivanju; 3) Odluka o pokretanju postupka za upis; 4) Odluka o imenovanju osoba ovlaštenih za zastupanje; 5) Odluka o privremenom vizualnom identitetu; 6) Odluka o pokretanju Programa DOM; 7) Popis osnivača; 8) Pratno obrazloženje.
</div>
'''

# ══════════════════════════════════════════════════════════════════
# 3. ODLUKE (6 dokumenata)
# ══════════════════════════════════════════════════════════════════

ODLUKA_OSNIVANJE_BODY = '''
<div class="legal-basis">
Na temelju članka 11. Zakona o udrugama (NN 74/14, 70/17, 98/19), osnivači su na Osnivačkoj skupštini održanoj <span class="emph">19. travnja 2026.</span> u Vladislavcima donijeli sljedeću
</div>

<h2>ODLUKA</h2>

<h3>I.</h3>
<p>Ovom Odlukom osniva se udruga pod nazivom:</p>
<p style="text-align:center;font-size:12pt;margin:3mm 0"><span class="emph">Udruga „NO LIMIT" — Europska udruga za digitalnu transformaciju stvarnog svijeta</span></p>
<p>Skraćeni naziv: <span class="emph">NO LIMIT</span>.</p>

<h3>II.</h3>
<p>Sjedište Udruge je na adresi <span class="emph">Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska</span>.</p>

<h3>III.</h3>
<p>Udruga se osniva na neodređeno vrijeme kao neprofitna pravna osoba radi ostvarivanja ciljeva utvrđenih Statutom Udruge koji je donesen na istoj Osnivačkoj skupštini.</p>

<h3>IV.</h3>
<p>Ciljeve i djelatnosti, unutarnje ustrojstvo, tijela, imovinu i druga pitanja od značaja za rad Udruge utvrđuje Statut.</p>

<h3>V.</h3>
<p>Ova Odluka stupa na snagu danom donošenja.</p>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>

<p><span class="emph">Osnivači:</span></p>
<ol>
<li>Ivan Brtan, OIB 70086599476 — _______________________</li>
<li>Ivica Kruljac, OIB 82540277049 — _______________________</li>
<li>Marija Brtan, OIB [_______________] — _______________________</li>
<li>Antonio Brtan, OIB 28907401487 — _______________________</li>
</ol>
'''

ODLUKA_UPIS_BODY = '''
<div class="legal-basis">
Na temelju članka 15. Zakona o udrugama, na Osnivačkoj skupštini Udruge „NO LIMIT" održanoj <span class="emph">19. travnja 2026.</span> u Vladislavcima, donesena je sljedeća
</div>

<h2>ODLUKA</h2>

<h3>I.</h3>
<p>Pokreće se postupak za upis Udruge „NO LIMIT" — Europske udruge za digitalnu transformaciju stvarnog svijeta u <span class="emph">Registar udruga Republike Hrvatske</span>, kod nadležnog tijela — <span class="emph">Upravnog odjela za opću upravu Osječko-baranjske županije</span>.</p>

<h3>II.</h3>
<p>Za provedbu ove Odluke ovlašćuje se <span class="emph">Predsjednik Udruge Ivan Brtan</span> (OIB 70086599476), koji će u ime osnivača:</p>
<ol>
<li>sastaviti i podnijeti Zahtjev za upis u Registar udruga;</li>
<li>priložiti Zahtjevu Statut Udruge, Zapisnik Osnivačke skupštine, Popis osnivača, Odluku o osnivanju, Odluku o imenovanju osoba ovlaštenih za zastupanje, preslike osobnih iskaznica osnivača i Pratno obrazloženje;</li>
<li>postupati u skladu s dobivenim uputama nadležnog tijela i poduzeti sve potrebne radnje do okončanja postupka upisa.</li>
</ol>

<h3>III.</h3>
<p>Zatražit će se i dodjela <span class="emph">OIB-a Udruge</span> od Porezne uprave po izvršenom upisu.</p>

<h3>IV.</h3>
<p>Ova Odluka stupa na snagu danom donošenja.</p>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>

<div class="signature-block">
  <div></div>
  <div class="right">
    <div class="sig-line">
      <span class="emph">Predsjedavajući Osnivačke skupštine</span><br>
      Ivan Brtan, v.r.
    </div>
  </div>
</div>
'''

ODLUKA_ZASTUPANJE_BODY = '''
<div class="legal-basis">
Na temelju članka 12. i članka 13. Zakona o udrugama i članka 5. Statuta Udruge „NO LIMIT", Osnivačka skupština na sjednici održanoj <span class="emph">19. travnja 2026.</span> donosi
</div>

<h2>ODLUKU</h2>

<h3>I.</h3>
<p>Za osobu ovlaštenu za zastupanje <span class="emph">Udruge „NO LIMIT"</span> u pravnom prometu imenuje se:</p>
<div style="background:#f5f5f5;padding:4mm;margin:3mm 0;border-left:2pt solid #000">
<p><span class="emph">IVAN BRTAN</span><br>
OIB: 70086599476<br>
Datum rođenja: 18.09.1966.<br>
Adresa: Kalnička 19, 31431 Čepin, Republika Hrvatska<br>
Funkcija: <span class="emph">Predsjednik Udruge</span><br>
Trajanje mandata: 19.04.2026. — 19.04.2031.</p>
</div>

<h3>II.</h3>
<p>U slučaju spriječenosti Predsjednika, Udrugu zastupa Tajnik Udruge uz pisanu ovlast Predsjednika. Tajnik Udruge je:</p>
<div style="background:#f5f5f5;padding:4mm;margin:3mm 0;border-left:2pt solid #000">
<p><span class="emph">IVICA KRULJAC</span><br>
OIB: 82540277049<br>
Adresa: Kralja Tomislava 291, 31404 Vladislavci, Republika Hrvatska<br>
Funkcija: <span class="emph">Tajnik Udruge</span><br>
Trajanje mandata: 19.04.2026. — 19.04.2031.</p>
</div>

<h3>III.</h3>
<p>Podaci o osobama ovlaštenima za zastupanje upisuju se u Registar udruga Republike Hrvatske.</p>

<h3>IV.</h3>
<p>Ova Odluka stupa na snagu danom donošenja.</p>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>

<div class="signature-block">
  <div></div>
  <div class="right">
    <div class="sig-line">
      <span class="emph">Predsjedavajući Osnivačke skupštine</span><br>
      Ivan Brtan, v.r.
    </div>
  </div>
</div>
'''

ODLUKA_LOGO_BODY = '''
<div class="legal-basis">
Na temelju članka 4. Statuta Udruge „NO LIMIT", Osnivačka skupština na sjednici održanoj <span class="emph">19. travnja 2026.</span> donosi
</div>

<h2>ODLUKU</h2>

<h3>I. — Privremeni logo</h3>
<p>Usvaja se privremeni logo Udruge u obliku <span class="emph">stiliziranog lebdećeg obrnutog jajeta</span> s LCD plohom i simbolom beskonačnosti (∞) kao digitalnim očima, izveden u crno-bijeloj i boja-varijanti, sukladno tehničkoj specifikaciji koja se prilaže kao sastavni dio ove Odluke.</p>

<h3>II. — Privremeni pečat</h3>
<p>Usvaja se privremeni pečat Udruge kako slijedi:</p>
<ul>
<li>oblik: okrugli;</li>
<li>promjer: 30 mm;</li>
<li>natpis po obodu: „UDRUGA NO LIMIT — VLADISLAVCI";</li>
<li>središte: privremeni logo iz točke I.;</li>
<li>boja otiska: crna.</li>
</ul>

<h3>III. — Finalizacija</h3>
<p>Predsjednik Udruge ovlašćuje se da u roku od <span class="emph">90 dana</span> od dana upisa Udruge u Registar:</p>
<ol>
<li>pregleda pripremljene tri varijante finalnog vizualnog identiteta;</li>
<li>odabere finalna rješenja loga i pečata;</li>
<li>organizira njihovu izradu i zaprimanje;</li>
<li>provede provjeru intelektualnog vlasništva (IP clearance) kod ovlaštenog odvjetnika;</li>
<li>podnese izabranu varijantu Skupštini na potvrdu na prvoj sljedećoj sjednici.</li>
</ol>

<h3>IV.</h3>
<p>Do donošenja potvrdne odluke Skupštine o finalnom vizualnom identitetu, privremeni logo i pečat upotrebljavaju se kao valjani znakovi Udruge.</p>

<h3>V.</h3>
<p>Ova Odluka stupa na snagu danom donošenja.</p>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>

<div class="signature-block">
  <div></div>
  <div class="right">
    <div class="sig-line">
      <span class="emph">Predsjedavajući Osnivačke skupštine</span><br>
      Ivan Brtan, v.r.
    </div>
  </div>
</div>
'''

ODLUKA_DOM_BODY = '''
<div class="legal-basis">
Na temelju članka 29. Statuta Udruge „NO LIMIT", Osnivačka skupština na sjednici održanoj <span class="emph">19. travnja 2026.</span> donosi
</div>

<h2>ODLUKU</h2>

<h3>I.</h3>
<p>Uspostavlja se i pokreće <span class="emph">Program stambenog zbrinjavanja „DOM"</span> kao stalni humanitarni program Udruge.</p>
<p>Program „DOM" (engl. Programme HOME, njem. Programm HEIM) provodi se za osobe koje su zbog prirodne katastrofe, zdravstvenih prilika, starosti, invaliditeta ili iznenadne ekonomske nevolje ostale bez doma ili žive u uvjetima nepodobnim za život.</p>

<h3>II.</h3>
<p>Program započinje <span class="emph">danom upisa Udruge u Registar udruga Republike Hrvatske</span>.</p>

<h3>III.</h3>
<p>Predsjednik Udruge zadužuje se da u roku od <span class="emph">60 dana</span> od upisa:</p>
<ol>
<li>otvori <span class="emph">poseban transakcijski račun</span> za Program DOM, odvojen od osnovnog poslovnog računa;</li>
<li>pokrene razgovore o sklapanju <span class="emph">Memoranduma o suradnji</span> s Hrvatskim Crvenim križem — Gradskim društvom Osijek i Caritasom Đakovačko-osječke nadbiskupije;</li>
<li>pripremi nacrt <span class="emph">Protokola Programa DOM</span> za potvrdu na prvoj redovnoj sjednici Skupštine;</li>
<li>u suradnji s Općinom Vladislavci pripremi popis prvih potencijalnih korisnika Programa u mjesnom području.</li>
</ol>

<h3>IV.</h3>
<p>Sva financijska transakcija Programa DOM odvija se preko posebnog transakcijskog računa iz točke III. 1., a javna objava mjesečnog prometa tog računa obvezna je sukladno članku 32. stavku 6. Statuta („staklena kuća" transparentnost).</p>

<h3>V.</h3>
<p>Ova Odluka stupa na snagu danom donošenja.</p>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>

<div class="signature-block">
  <div></div>
  <div class="right">
    <div class="sig-line">
      <span class="emph">Predsjedavajući Osnivačke skupštine</span><br>
      Ivan Brtan, v.r.
    </div>
  </div>
</div>
'''

# ══════════════════════════════════════════════════════════════════
# 4. POPIS OSNIVAČA
# ══════════════════════════════════════════════════════════════════
POPIS_BODY = '''
<div class="legal-basis">
Sukladno članku 11. Zakona o udrugama i članku 5. Pravilnika o sadržaju Registra udruga, Udrugu „NO LIMIT" osnivaju sljedeće osobe:
</div>

<table>
<tr>
  <th>#</th>
  <th>Ime i prezime</th>
  <th>OIB</th>
  <th>Datum rođenja</th>
  <th>Državljanstvo</th>
  <th>Adresa prebivališta</th>
  <th>Potpis</th>
</tr>
<tr>
  <td>1.</td>
  <td><span class="emph">Ivan Brtan</span></td>
  <td>70086599476</td>
  <td>18.09.1966.</td>
  <td>HRV</td>
  <td>Kalnička 19, 31431 Čepin, Hrvatska</td>
  <td>✍</td>
</tr>
<tr>
  <td>2.</td>
  <td><span class="emph">Ivica Kruljac</span></td>
  <td>82540277049</td>
  <td>[___.___.______.]</td>
  <td>HRV</td>
  <td>Kralja Tomislava 291, 31404 Vladislavci, Hrvatska</td>
  <td>✍</td>
</tr>
<tr>
  <td>3.</td>
  <td><span class="emph">Marija Brtan</span></td>
  <td>[_______________]</td>
  <td>[___.___.______.]</td>
  <td>HRV</td>
  <td>[____________________________________________________]</td>
  <td>✍</td>
</tr>
<tr>
  <td>4.</td>
  <td><span class="emph">Antonio Brtan</span></td>
  <td>28907401487</td>
  <td>12.02.2001.</td>
  <td>HRV</td>
  <td>Grabenstrasse 29 E, 71116 Gärtringen, SR Njemačka</td>
  <td>✍</td>
</tr>
</table>

<p style="margin-top:6mm">Svi osnivači izjavljuju da osnivaju Udrugu dobrovoljno, da su upoznati sa Statutom i ciljevima Udruge te da prihvaćaju sve obveze koje proizlaze iz osnivačkog akta.</p>

<div class="note-box" style="margin-top:6mm">
<strong>Napomena:</strong> Podaci za Mariju Brtan (zapisničar) dopunit će se prije predaje u Upravni odjel, nakon dostave preslike osobne iskaznice.
</div>

<div class="place-date"><p>U Vladislavcima, 19. travnja 2026.</p></div>
'''

# ══════════════════════════════════════════════════════════════════
# 5. PRATNO OBRAZLOŽENJE
# ══════════════════════════════════════════════════════════════════
PRATNO_BODY = '''
<p><span class="emph">Upravni odjel za opću upravu Osječko-baranjske županije</span><br>
Osijek<br><br>
<span class="emph">Predmet:</span> Pratno obrazloženje uz Zahtjev za upis Udruge „NO LIMIT" u Registar udruga RH<br>
<span class="emph">Predsjednik Osnivačke skupštine:</span> Ivan Brtan, OIB 70086599476<br>
<span class="emph">Datum:</span> 20. travnja 2026.</p>

<div class="hr"></div>

<p>Poštovani,</p>

<p>ovim obrazloženjem želimo unaprijed pojasniti nekoliko elemenata Statuta Udruge „NO LIMIT" koji odstupaju od uobičajene prakse, a koji su pravno utemeljeni i u skladu s važećim zakonodavstvom Republike Hrvatske i Europske unije.</p>

<h3>1. Naziv s engleskim elementom</h3>
<p>Puni naziv Udruge na hrvatskom jeziku glasi: <em>„Udruga NO LIMIT — Europska udruga za digitalnu transformaciju stvarnog svijeta"</em>. „NO LIMIT" je skraćeni naziv koji se koristi u svakodnevnoj komunikaciji, analogno skraćenim nazivima drugih upisanih udruga i klubova (npr. „NK Osijek" za „Nogometni klub Osijek"). Članak 4. stavak 2. Pravilnika o sadržaju i načinu vođenja Registra udruga RH (NN 4/15) izrijekom dopušta skraćene nazive.</p>

<h3>2. Zaštita prava na gotovinu (čl. 8. Statuta)</h3>
<p>Članak 8. Statuta zauzima stajalište o očuvanju gotovine kao sredstva plaćanja. Ovo nije politička stavka, već je u skladu s:</p>
<ul>
<li>Uredbom Vijeća (EZ) br. 974/98 o uvođenju eura, koja gotovinu definira kao zakonsko sredstvo plaćanja;</li>
<li>Mišljenjem Europske središnje banke CON/2022/40 o statusu gotovine u digitalnom dobu;</li>
<li>Zaključcima Eurogroupa iz 2023. o potrebi očuvanja dostupnosti gotovine unutar eurozone.</li>
</ul>
<p>Udruga promiče postojeća prava građana EU kroz edukaciju i zagovaranje, u skladu s Ustavom RH (čl. 35.) i Poveljom EU-a o temeljnim pravima.</p>

<h3>3. Strateško partnerstvo s trgovačkim društvom Konjik d.o.o. (čl. 25.–28. Statuta)</h3>
<p>Udruga djeluje kao tehnološki i strateški partner trgovačkog društva Konjik d.o.o. (Kralja Tomislava 1a, 31431 Čepin), koje je nositelj intelektualnog vlasništva tehnologija ekosustava ChainBlock. Ovaj model odvajanja komercijalnog nositelja IP-a i neprofitnog promotora otvorenih standarda uobičajen je u europskoj i svjetskoj praksi:</p>
<ul>
<li>Mozilla Foundation (neprofit) i Mozilla Corporation (tvrtka);</li>
<li>Linux Foundation (neprofit) i korporativni članovi (IBM, Red Hat, Oracle);</li>
<li>Apache Software Foundation (neprofit) i razvojne tvrtke pojedinih projekata.</li>
</ul>
<p>Udruga ne stječe vlastiti komercijalni patentni portfelj (čl. 28. st. 4.), već djeluje kao javni nadzornik nad provedbom Open Patent Promise licencnog modela.</p>

<h3>4. Blagajnik s prebivalištem u Njemačkoj</h3>
<p>Blagajnik Udruge Antonio Brtan ima prebivalište u Saveznoj Republici Njemačkoj. Zakon o udrugama ne traži hrvatsko prebivalište za članove tijela (izuzev zastupnika, koji ima hrvatsko prebivalište). Sloboda kretanja osoba unutar EU jamči pravo sudjelovanja u udrugama bez obzira na državu prebivališta. Članak 23. stavak 2. Statuta ovo izrijekom potvrđuje.</p>

<h3>5. Projekt digitalne inkluzije osoba s invaliditetom (čl. 28. Statuta)</h3>
<p>Udruga u partnerstvu s Konjik d.o.o. i akademijom memio.world razvija projekt profesionalne rehabilitacije osoba s invaliditetom i osoba smanjene pokretljivosti u sklopu novoga zanimanja „AI-asistirani knjigovođa". Projekt je u potpunosti u skladu s:</p>
<ul>
<li>Europskim aktom o pristupačnosti (Direktiva EU 2019/882);</li>
<li>UN-ovom Konvencijom o pravima osoba s invaliditetom (ratificirana NN 6/07);</li>
<li>Zakonom o profesionalnoj rehabilitaciji i zapošljavanju osoba s invaliditetom (NN 157/13, 152/14, 39/18);</li>
<li>Operativnim programom Učinkoviti ljudski potencijali 2021.–2027. (ESF+).</li>
</ul>
<p>Edukacijska i zagovaračka djelatnost Udruge u ovom području ne predstavlja pružanje socijalnih usluga u smislu Zakona o socijalnoj skrbi te ne zahtijeva posebnu dozvolu.</p>

<h3>6. Program DOM — stambeno zbrinjavanje (čl. 29. Statuta)</h3>
<p>Udruga provodi stalni humanitarni program stambenog zbrinjavanja „DOM" za žrtve prirodnih katastrofa, starije i bolesne osobe, obitelji u nevolji. Program je u skladu sa:</p>
<ul>
<li>Zakonom o humanitarnoj pomoći (NN 102/15);</li>
<li>Zakonom o gradnji (NN 153/13, 20/17, 39/19, 125/19);</li>
<li>Zakonom o obnovi zgrada oštećenih potresom (NN 102/20, 10/21).</li>
</ul>
<p>Udruga u čl. 32. Statuta („Sprječavanje zloupotrebe") propisuje mehanizme koji nadilaze zakonski minimum — „staklena kuća" transparentnost, javna objava donatora i priljeva, posebni TR, neovisni revizor.</p>

<h3>7. Elektroničke sjednice Skupštine (čl. 20. st. 4. Statuta)</h3>
<p>Statut dopušta održavanje sjednica Skupštine elektroničkim putem (videokonferencija), u skladu s člankom 4. Zakona o izmjenama i dopunama Zakona o udrugama (NN 73/20).</p>

<div class="hr"></div>

<p>Nadamo se da ovo obrazloženje omogućuje učinkovito procesuiranje našega zahtjeva. Za sva pitanja stojimo na raspolaganju.</p>

<p>S poštovanjem,</p>

<div class="signature-block">
  <div></div>
  <div class="right">
    <div class="sig-line">
      <span class="emph">Ivan Brtan</span><br>
      Predsjednik Osnivačke skupštine<br>
      OIB: 70086599476
    </div>
  </div>
</div>
'''

# ══════════════════════════════════════════════════════════════════
# GENERATE ALL
# ══════════════════════════════════════════════════════════════════

DOCS = [
    ("NO_LIMIT_Statut.pdf",
     "STATUT UDRUGE „NO LIMIT"",
     "Europska udruga za digitalnu transformaciju stvarnog svijeta",
     "Temeljni akt",
     STATUT_BODY),
    ("NO_LIMIT_Zapisnik_osnivacke_skupstine.pdf",
     "ZAPISNIK OSNIVAČKE SKUPŠTINE",
     "Udruga „NO LIMIT"",
     "Prvi povijesni akt",
     ZAPISNIK_BODY),
    ("NO_LIMIT_Odluka_o_osnivanju.pdf",
     "ODLUKA O OSNIVANJU",
     "Udruga „NO LIMIT"",
     "Akt o osnivanju",
     ODLUKA_OSNIVANJE_BODY),
    ("NO_LIMIT_Odluka_o_upisu.pdf",
     "ODLUKA O POKRETANJU POSTUPKA ZA UPIS",
     "u Registar udruga Republike Hrvatske",
     "Akt o upisu",
     ODLUKA_UPIS_BODY),
    ("NO_LIMIT_Odluka_o_zastupanju.pdf",
     "ODLUKA O IMENOVANJU OSOBA OVLAŠTENIH ZA ZASTUPANJE",
     "Udruga „NO LIMIT"",
     "Akt o zastupanju",
     ODLUKA_ZASTUPANJE_BODY),
    ("NO_LIMIT_Odluka_o_logu.pdf",
     "ODLUKA O PRIVREMENOM VIZUALNOM IDENTITETU",
     "Udruga „NO LIMIT"",
     "Akt o logu i pečatu",
     ODLUKA_LOGO_BODY),
    ("NO_LIMIT_Odluka_o_Programu_DOM.pdf",
     "ODLUKA O USPOSTAVI I POKRETANJU PROGRAMA DOM",
     "Humanitarni program stambenog zbrinjavanja",
     "Akt o Programu DOM",
     ODLUKA_DOM_BODY),
    ("NO_LIMIT_Popis_osnivaca.pdf",
     "POPIS OSNIVAČA",
     "Udruga „NO LIMIT"",
     "Osnivački akt",
     POPIS_BODY),
    ("NO_LIMIT_Pratno_obrazlozenje.pdf",
     "PRATNO OBRAZLOŽENJE",
     "uz Zahtjev za upis Udruge u Registar udruga RH",
     "Pratni dopis",
     PRATNO_BODY),
]

print("=== GENERIRANJE PDF DOKUMENATA ===\n")
for filename, title, subtitle, eyebrow, body in DOCS:
    html = wrap(title, body, subtitle, eyebrow)
    path, size = make_pdf(filename, html)
    print(f"  OK  {filename}  ({size//1024} KB)")

print("\n=== GOTOVO ===")
