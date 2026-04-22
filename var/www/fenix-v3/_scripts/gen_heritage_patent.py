#!/usr/bin/env python3
"""
Konjik d.o.o. — KONJ-DP-2026-002
Digitalno Nasljeđe Živih Bića — Intergeneracijski Trust Score i Digitalna Oporuka

Registrira prior art u Konjik DefensivePublication sustav (ChainBlock),
generira PDF dokument WeasyPrint-om i zapisuje u static/udruga_no_limit/patent/.
"""
import os, sys, hashlib, secrets, json
from datetime import datetime

sys.path.insert(0, '/var/www/fenix-v3')
os.chdir('/var/www/fenix-v3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()

from django.utils import timezone
from evalidator.models import DefensivePublication, MerkleLeaf, ChainBlockPOE
import weasyprint

# ─── KONSTANTE ────────────────────────────────────────────────────────────────
DP_ID      = "KONJ-DP-2026-002"
DATUM      = "21. travnja 2026."
DATUM_ISO  = "2026-04-21"
OUT_DIR    = "/var/www/fina-connect/static/udruga_no_limit/patent"
OUT_PDF    = os.path.join(OUT_DIR, "KONJ-DP-2026-002-digitalno-nasljedstvo.pdf")

os.makedirs(OUT_DIR, exist_ok=True)

# ─── 12 OTKRIVENIH TVRDNJI (leaves 0-11) ──────────────────────────────────────
REVEALED_CLAIMS = [
    # Ključni algoritmički doprinosi
    "[H01] IntergeneracijskiTrustScore — 8-dimenzionalni normalizirani scoring sustav (0-15) za procjenu genetske i zdravstvene vrijednosti živih bića temeljen na generacijskoj dubini, poznatim prvacima, zdravstvenim potvrdama, HeritageTrait verifikacijama i nasljeđenom trustu",
    "[H02] DigitalnaOporuka (LegacyBequest) — kriptografski pečatirani digitalni testament za živa bića sa SHA-256 seal_hashom oblika SHA256(animal_id:successor_email_hash:created_at), triggerima (smrt vlasnika, godišnjica, neaktivnost 12mj) i revokabilnim statusnim lancem",
    "[H03] DuguniMost-HeritageOracle signal — automatski cross-platform sync koji se okida kad animal.status=uginulo: signal → sync_dugini_most_to_oracles() → HeritageOracle.pet_fragments memorijalni fragment (memio.pet ↔ memio.world most)",
    "[H04] HeritageTrait verifikacijski lanac — taksonomski tip osobina (genetic_test, health_clearance, championship, talent, temperament, longevity) s inheritable bitom koji propagira score kroz generacije putem parent→child chip lookup mehanizma",
    "[H05] DinastijaRazina klasifikacijski algoritam — trostupanjska klasifikacija (Početnik: 0-3, Linija: 4-7, Dinastija: 8+) bazirana na generation_depth i known_champions; svaki stupanj nosi vizualni identitet (boja + ikona) za javni showcase",
    "[H06] QR-verifikacija genealoškog identiteta — permanentni QR kod generiran na zahtjev (PNG, cache 1h) koji kodira kanonski URL /pas/{chip}/naslijede/ kao jedinstven digitalni pečat rodovnice, printabilan na potvrde i dokumente",
    "[H07] HeritageBridge cross-platform protokol — jednosmjerni sync API (add_pet_fragment_to_oracle) koji upisuje memorial fragmente u HeritageOracle.pet_fragments JSONField na memio.world bez direktne FK veze između baza; lookup po chip_or_tag identifikatoru",
    "[H08] SealHash kriptografski dokaz nasljednog zahtjeva — deterministički SHA-256 fingerprint koji veže identitet životinje, hash nasljednika i timestamp u jedan nepromjenjivi zapis, verifikabilan bez otkrivanja email adrese nasljednika",
    "[H09] Rekurzivno genealoško stablo (dubina 3) — API koji vraća JSON tree strukturu do 3 generacijske razine koristeći father_chip/mother_chip pointere; svaki čvor nosi ime, chip, heritage_score i dynasty_level za vizualizaciju u frontendu",
    "[H10] HeritageShowcase javni registar — javno dostupan (bez autentikacije) filtriran prikaz DigitalHeritage zapisa s heritage_score≥5 sortiranih opadajuće; svaki unos sadrži mini QR (48px) za instant verifikaciju",
    "[H11] CrossSpecies unified Heritage standard — jedan model (DigitalHeritage, HeritageTrait, LegacyBequest) koji pokriva pse, mačke, konje i ostale registrirane vrste bez species-specific granjanja; proširiv na memio.farm, memio.world, memio.global",
    "[H12] PrivatnostNasljeđa protokol — pohranjivanje successor_email_hash (SHA-256 email adrese nasljednika) umjesto plain-text kontakta, omogućava verifikaciju nasljednog prava bez otkrivanja osobnih podataka trećim stranama",
]

ABSTRACT = """
Sustav i metoda za digitalno nasljeđe živih bića koji kombinira intergeneracijski
kriptografski trust score, verifikabilni genealoški zapis i digitalni testament
(oporuku) pečaćen SHA-256 seal_hash algoritmom. Sustav implementira 8-dimenzionalni
normalizirani scoring (0-15) temeljen na generacijskoj dubini, genetskim testovima,
zdravstvenim potvrdama, titulama i nasljeđenom trustu. Digitalna oporuka (LegacyBequest)
omogućava vlasnicima živih bića definiranje nasljednika uz kriptografsku zaštitu
identiteta putem hash-a email adrese. Sustav je cross-platform dizajniran (memio.pet,
memio.world) s jednosmjernim sync protokolom (HeritageBridge) koji upisuje memorijalne
fragmente u HeritageOracle po signalu statusne promjene životinje.
""".strip()

# ─────────────────────────────────────────────────────────────────────────────
# CSS za PDF
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
@page {
  margin: 22mm 18mm 26mm 20mm; size: A4;
  @top-right { content: "PRIOR ART · Konjik d.o.o. · KONJ-DP-2026-002";
    font-family:'DejaVu Sans',Arial,sans-serif; font-size:7.5pt; color:#888; }
  @bottom-center {
    content: counter(page) " / " counter(pages) "  —  KONJ-DP-2026-002  —  limit-connect.com/konjik/";
    font-family:'DejaVu Sans',Arial,sans-serif; font-size:8pt; color:#666; }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'DejaVu Sans',Arial,sans-serif; font-size:10.5pt; color:#000; line-height:1.6; }
h1 { font-size:14pt; font-weight:700; margin:8mm 0 3mm; border-bottom:1.5pt solid #000; padding-bottom:2mm; }
h2 { font-size:11.5pt; font-weight:700; margin:6mm 0 2mm; color:#1a1a1a; }
h3 { font-size:10.5pt; font-weight:700; margin:4mm 0 2mm; color:#1a1a1a; }
p { margin-bottom:2.5mm; text-align:justify; }
ul,ol { margin:2mm 0 3mm 7mm; }
li { margin-bottom:1.5mm; }
.cover { text-align:center; padding:30mm 0 20mm; border-bottom:2pt solid #C9A84C; margin-bottom:15mm; }
.cover .eyebrow { font-size:8pt; letter-spacing:3px; text-transform:uppercase; color:#666; margin-bottom:5mm; }
.cover .title { font-size:20pt; font-weight:700; line-height:1.2; margin-bottom:4mm; }
.cover .subtitle { font-size:13pt; color:#333; margin-bottom:8mm; }
.meta { background:#f5f5f5; border-left:2pt solid #C9A84C; padding:4mm 5mm; margin:4mm 0 8mm; font-size:9.5pt; }
.meta table { width:100%; border-collapse:collapse; }
.meta td { padding:1.5mm 2mm; vertical-align:top; }
.meta td:first-child { font-weight:700; width:32%; color:#333; }
.claim { border:0.5pt solid #333; padding:3mm 4mm; margin:3mm 0; background:#fafafa; page-break-inside:avoid; }
.claim-num { font-weight:700; color:#C9A84C; margin-bottom:2mm; font-size:10pt;
  border-bottom:0.3pt solid #C9A84C; padding-bottom:1mm; }
.code { background:#f0f0f0; padding:3mm; font-family:monospace; font-size:8pt;
  border-left:2pt solid #C9A84C; margin:2mm 0; white-space:pre-wrap; }
.phase-box { background:#f8f8f8; border:0.5pt solid #ccc; border-radius:2pt;
  padding:3mm 4mm; margin:2mm 0; }
.phase-title { font-weight:700; color:#1a1a1a; margin-bottom:1mm; }
.gold { color:#C9A84C; font-weight:700; }
.chainblock-seal { background:#f0fff4; border:1pt solid #2d7a4f; padding:4mm; margin:8mm 0 0;
  font-size:9pt; text-align:center; }
table.data { width:100%; border-collapse:collapse; margin:3mm 0; font-size:9pt; }
table.data th { background:#e8e8e8; font-weight:700; padding:2mm 3mm;
  border:0.4pt solid #333; text-align:left; }
table.data td { padding:2mm 3mm; border:0.4pt solid #ccc; vertical-align:top; }
.merkle-row { font-family:monospace; font-size:7.5pt; color:#555; }
.status-r { color:#2d7a4f; font-weight:700; }
.status-b { color:#999; }
"""


def build_html(dp, block, leaves_data, merkle_root):
    # Grupiraj revealed leaves u tablicu
    revealed_rows = ""
    for idx, status, lhash, salt, content in leaves_data:
        if status == "revealed":
            label = content[:8] if content else f"[H{idx+1:02d}]"
            desc  = content[10:90] + "..." if len(content) > 100 else content[10:]
            revealed_rows += f"""
<tr>
  <td class="merkle-row">{idx+1:02d}</td>
  <td><span class="status-r">REVEALED</span></td>
  <td><strong>{label}</strong> {desc}</td>
  <td class="merkle-row">{lhash[:16]}...</td>
</tr>"""
        else:
            revealed_rows += f"""
<tr>
  <td class="merkle-row">{idx+1:02d}</td>
  <td><span class="status-b">blank</span></td>
  <td><em>rezervirano</em></td>
  <td class="merkle-row">{lhash[:16]}...</td>
</tr>"""

    claims_html = ""
    for i, claim in enumerate(REVEALED_CLAIMS, 1):
        tag  = claim[:6]   # [H01]
        body = claim[7:]   # tekst iza taga
        claims_html += f"""
<div class="claim">
  <div class="claim-num">Tvrdnja {i:02d} {tag}</div>
  <p>{body}</p>
</div>"""

    seal_token = block.seal_token if block else DP_ID
    block_num  = block.block_number if block else "?"
    block_hash = block.block_hash[:32] if block else "?"

    return f"""<!DOCTYPE html><html lang="hr"><head><meta charset="UTF-8"></head><body>

<!-- ══ NASLOVNA ══ -->
<div class="cover">
  <div class="eyebrow">Defensive Publication · Konjik d.o.o. · Prior Art Registry</div>
  <div class="title">DIGITALNO NASLJEDSTVO ZIVIH BICA</div>
  <div class="subtitle">Intergeneracijski Trust Score i Digitalna Oporuka<br>
  temeljena na kriptografskom seal-hash mehanizmu i cross-platform Heritage Bridge protokolu</div>
  <div style="font-size:9pt;color:#666;">Referenca: {DP_ID} &nbsp;·&nbsp; Prioritetni datum: {DATUM}</div>
</div>

<div class="meta"><table>
<tr><td>Podnositelj</td><td><strong>Konjik d.o.o.</strong>, Kralja Tomislava 1a, 31431 Cepin, Republika Hrvatska</td></tr>
<tr><td>Izumitelji</td><td>Ivan Brtan (OIB: 70086599476) · Marija Brtan · Antonio Brtan</td></tr>
<tr><td>Prioritetni datum</td><td>{DATUM} (ChainBlock pecat, limit-connect.com)</td></tr>
<tr><td>Prethodni DP</td><td>KONJ-DP-2026-001 — QBP-32 / TDS (preduvjetna infrastruktura)</td></tr>
<tr><td>IPC klasifikacija</td><td>G06F 21/64; H04L 9/32; G16H 10/60; H04L 9/00; G06F 16/903</td></tr>
<tr><td>ChainBlock</td><td>Block #{block_num} · Seal: {seal_token}</td></tr>
<tr><td>Merkle root</td><td class="merkle-row">{merkle_root[:32]}...</td></tr>
<tr><td>Licencni rezim</td><td>Open Patent Promise v1.1 — besplatno za akademsku i neprofitnu uporabu</td></tr>
</table></div>

<h1>1. NASLOV IZUMA</h1>
<p><strong>Sustav i metoda za digitalno nasljedstvo zivih bica koji implementira
intergeneracijski kriptografski trust score (8 dimenzija, normaliziran 0-15),
genealosko stablo s rekurzivnim parent chip lookup mehanizmom (dubina 3),
kriptografski pečatirani digitalni testament (LegacyBequest) s SHA-256 seal_hash
algoritmom i cross-platform Heritage Bridge protokol za sinkronizaciju memorijalnih
fragmenata izmedju neovisnih platformi.</strong></p>

<h1>2. PODRUCJE TEHNIKE</h1>
<ul>
<li>Kriptografski pečati i verifikabilnost podataka — IPC G06F 21/64</li>
<li>Zero-Knowledge hash protokoli za zastitu osobnih podataka — IPC H04L 9/32</li>
<li>Zdravstvene informacijske platforme za ne-humane vrste — IPC G16H 10/60</li>
<li>Cross-platform sinkronizacija distribuiranih baza podataka — IPC H04L 9/00</li>
<li>Semanticki web i linked-data genealoski zapisi — IPC G06F 16/903</li>
</ul>

<h1>3. STANJE TEHNIKE I RAZLIKOVNOST</h1>

<h2>3.1 Postojeca rjesenja</h2>
<p><strong>(a) Klasicni rodovnici (FCI, HKS, AKC):</strong> Papirnati ili digitalni PDF
dokumenti bez kriptografske verifikacije. Podaci su centralizirani, podlozni falsifikatu,
bez intergeneracijskog scoringa i bez automatske sinkronizacije pri promjeni statusa zivotinje.</p>
<p><strong>(b) Blockchain-based pet records (PetChain, Companion):</strong>
Upisuju hash dokumenta na javni blockchain, ali bez domenske semantike (score, genealogija),
bez privatnosti nasljednika i bez cross-platform Heritage Bridge koncepta.</p>
<p><strong>(c) Digitalni testamenti (Willful, SafeWill):</strong> Napravljeni iskljucivo za
ljude. Ne postoji ekvivalent za ziva bica koji kriptografski vezuje identitet zivotinje,
hash nasljednika i timestamp u jedan verifikabilan zapis.</p>
<p><strong>(d) AI scoring za kucne ljubimce:</strong> Postoje aplikacije za procjenu
zdravlja (FitBark, Whistle), ali bez genealoske dimenzije, bez intergeneracijskog
propagiranja trusts i bez Merkle-zasnovanog prior art mehanizma.</p>

<h2>3.2 Razlikovnost ovog izuma</h2>
<p>KONJ-DP-2026-002 donosi cetiri neovisna tehnicka doprinosa koji zajedno cine
kohezivni sustav nedostupan u dosadanjoj literaturi i praksi:</p>
<ol>
<li><strong>Intergeneracijski normalizirani trust score</strong> koji propagira nasljedne
vrijednosti (genetski testovi, titule, longevity) kroz genealosko stablo bez direktnih
FK veza - iskljucivo putem chip identifikatora</li>
<li><strong>SHA-256 seal_hash digitalna oporuka</strong> koja stiti identitet nasljednika
(hash umjesto plain-text email), verifikabilna bez otkrivanja osobnih podataka</li>
<li><strong>DuguniMost-HeritageOracle signal protokol</strong> — automatski okidan
cross-platform sync koji reagira na promjenu statusnog polja (uginulo) i upisuje
memorijalne fragmente na necentraliziranu platformu (memio.world)</li>
<li><strong>CrossSpecies unified Heritage standard</strong> — jedinstven model
primjenjiv na pse, macke, konje i ostale vrste bez species-specific granjanja logike</li>
</ol>

<h1>4. OPIS IZUMA — 12 KOMPONENTI</h1>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H01 — IntergeneracijskiTrustScore</div>
<p>Osam-dimenzionalni normalizirani scoring sustav (max raw = 40 pts, normalized 0-15):
generation_depth (max 5), known_champions (max 5), health_clearances (max 5),
genetic_test_count (max 5), longevity_records (max 5), championship_titles (max 5),
inherited_trust iz parent-a (max 5), heirloom_documents (max 5).
Normalizacija: score = int(raw * 15 / 40). Score se racuna na zahtjev i cacheira u
DigitalHeritage.heritage_score JSON polju.</p>
<div class="code">def calculate_heritage_score(animal):
    raw = 0
    raw += min(animal.digital_heritage.generation_depth, 5)
    raw += min(animal.digital_heritage.known_champions * 2, 5)
    raw += min(animal.heritage_traits.filter(
        trait_type='health_clearance', result='pass').count() * 2, 5)
    # ... (ostale dimenzije)
    normalized = int(raw * 15 / 40)
    return normalized, raw, breakdown</div>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H02 — LegacyBequest digitalna oporuka</div>
<p>Model s poljima: animal (FK), successor_email_hash (SHA-256 email-a nasljednika),
trigger (owner_death | anniversary | manual | inactivity_12m), status (draft | active |
triggered | completed | revoked), seal_hash = SHA256(animal.id:successor_email_hash:created_at).
Seal hash je deterministicki fingerprint koji dokazuje postojanje nasljednog zahtjeva
na tocno odredjeni datum bez otkrivanja identiteta nasljednika.</p>
<div class="code">seal_hash = hashlib.sha256(
    f"{{animal.id}}:{{successor_email_hash}}:{{created_at.isoformat()}}".encode()
).hexdigest()</div>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H03 — DuguniMost-HeritageOracle signal</div>
<p>Django post_save signal na AnimalProfile koji se aktivira iskljucivo kad nova
vrijednost status polja = 'uginulo'. Signal poziva sync_dugini_most_to_oracles(animal)
koji pronalazi sve ChildProfile (memio.world) vezane za vlasnika putem user FK-a i
upisuje memorijalni fragment u HeritageOracle.pet_fragments JSONField (append, ne replace).
Fragmenti su strukturirani objekti: {chip_or_tag, animal_name, species, event_date,
is_memorial, added_at}.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H04 — HeritageTrait verifikacijski lanac</div>
<p>Svaka HeritageTrait instanca ima is_inheritable boolean. Kod racunanja heritage_score
za potomka, sustav lookup-a father_chip i mother_chip u AnimalProfile tablici i zbrajaju
se inherited traits iz oba roditelja (is_inheritable=True). Ovo kreira propagacijski
lanac kroz generacije bez rekurzivnih upita — samo parent-level lookup.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H05 — DinastijaRazina</div>
<p>Trostupanjska klasifikacija: Pocetnik (generation_depth=0, known_champions=0,
boja=#6b7280, ikona=🌱), Linija (generation_depth>=2 ili known_champions>=1,
boja=#7c3aed, ikona=⚜️), Dinastija (generation_depth>=4 ili known_champions>=3,
boja=#C9A84C, ikona=👑). Implementirano kao @property na DigitalHeritage modelu.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H06 — QR verifikacija genealoskog identiteta</div>
<p>HTTP endpoint /pas/{chip}/naslijede/qr/ generira PNG QR kod koji kodira kanonski URL
/pas/{chip}/naslijede/. Odgovor je PNG image/png s Cache-Control: max-age=3600.
Koristena biblioteka: qrcode[pil]. QR je dostupan bez autentikacije, printabilan na
rodovnicu, veterinarski certifikat ili plemensku potvrdu.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H07 — HeritageBridge cross-platform protokol</div>
<p>add_pet_fragment_to_oracle(child, chip_or_tag, animal_name, ...) - funkcija koja
provjerava postoji li HeritageOracle za child (get_or_create), ucitava pet_fragments
JSONField i appenda novi fragment bez brisanja postojecih. Identifikator fragmenta je
chip_or_tag; duplikati se zamjenjuju (update ako chip_or_tag vec postoji). Nema direktne
FK veze izmedju memio_pets i memio_world baza.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H08 — SealHash kriptografski dokaz</div>
<p>SHA-256 fingerprint koji veže tri elementa u nepromjenjivi zapis:
(1) UUID identifikator zivotinje, (2) SHA-256 hash email adrese nasljednika (double-hash
za privatnost), (3) ISO timestamp kreiranja zapisa. Seal hash se racuna pri kreiranju
LegacyBequest i sprema u bazu. Verifikacija: ponovi izracun i usporedi s pohranenim
hashom — ne zahtijeva pristup email adresi nasljednika.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H09 — Rekurzivno genealosko stablo (dubina 3)</div>
<p>API endpoint /api/heritage/{chip}/ vraca JSON tree do dubine 3 generacije.
Za svaki cvor: ime, chip, heritage_score, dynasty_level, father_chip, mother_chip,
children_chips. Rekurzija je ogranicena na depth=3 i max 100 ukupnih cvorova.
Nema vanjskih JOIN-ova — svaka razina je zasebni queryset lookup po chip-u.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H10 — HeritageShowcase javni registar</div>
<p>Endpoint /naslijede/ prikazuje DigitalHeritage.objects.filter(heritage_score__gte=5)
.select_related('animal').order_by('-heritage_score'). Svaka kartica sadrži:
fotografiju zivotinje, dynasty badge, heritage_score pill, broj titula i clearancea,
mini QR 48x48px (img src="/pas/{chip}/naslijede/qr/"). Bez autentikacije.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H11 — CrossSpecies unified Heritage standard</div>
<p>Modeli DigitalHeritage, HeritageTrait i LegacyBequest ne sadrze species-specific
polja. Sve instance AnimalProfile (bez obzira na species) mogu imati heritage zapis.
trait_type choices pokrivaju sve vrste: genetic_test, health_clearance, championship,
talent, temperament, longevity, other. Ovo omogucuje primjenu na memio.farm (stoka),
memio.world (opce) i buduce vertikale.</p>
</div>

<div class="phase-box">
<div class="phase-title">KOMPONENTA H12 — PrivatnostNasljedja protokol</div>
<p>Successor identitet se nikad ne pohranjuje u plain-textu. Polje LegacyBequest.
successor_email_hash = SHA-256(email). Sustav moze verificirati nasljedni zahtjev
(korisnik unese email → izracuna SHA-256 → usporedi s pohranenim hashom) bez
pohrane email-a. Seal hash dodatno kriptografski veže hash nasljednika uz identitet
zivotinje i datum — lanac je verifikabilan bez ikakvih osobnih podataka.</p>
</div>

<h1>5. PATENTNOPRAVNE TVRDNJE (CLAIMS)</h1>

{claims_html}

<h1>6. MERKLE STABLO — 32 LISTA</h1>
<p>Publikacija je pečatena Merkle stablom od 32 lista (12 otkrivenih + 20 rezerviranih
za buduce proširenje). Svaki list: SHA-256(content || salt).</p>
<table class="data">
<tr><th>#</th><th>Status</th><th>Sadrzaj (skraceno)</th><th>Hash (16 hex)</th></tr>
{revealed_rows}
</table>
<p><strong>Merkle root:</strong> <span class="merkle-row">{merkle_root}</span></p>
<p><strong>Merkle depth:</strong> 5</p>

<h1>7. CHAINBLOCK PEČAT</h1>
<div class="chainblock-seal">
  <strong>ChainBlock Proof of Existence — Block #{block_num}</strong><br>
  Seal token: {seal_token}<br>
  Block hash: <span class="merkle-row">{block_hash}...</span><br>
  Vremenski pecat: {DATUM} (limit-connect.com/konjik/)<br><br>
  Ovaj prior art dokument je kriptografski zapecacen u Konjik ChainBlock lancu.<br>
  Verifikacija: limit-connect.com/hr/chainblock/verify/{seal_token}/
</div>

<h1>8. IZJAVA O OPEN PATENT PROMISE</h1>
<p>Konjik d.o.o. ovime objavljuje da se odrice prava tuzbe za povredu patenta prema
svakome tko koristi, kopira, modificira ili distribuira ovu inovaciju u akademske,
edukacijske, neprofitne ili osobne svrhe, pod uvjetom da ne koristi inovaciju za
direktno komercijalno natjecanje s Konjik d.o.o. ili njenim licenciranim partnerima.</p>
<p>Komercijalna upotreba zahtijeva licencni ugovor s Konjik d.o.o. Kontakt:
ivan.brtan@konjik.hr</p>

<h1>9. REFERENCE</h1>
<ul>
<li>KONJ-DP-2026-001 — QBP-32 / TDS (preduvjetna kriptografska infrastruktura)</li>
<li>FENIX_ZAKON.md — Konjik pravni okvir za DefensivePublication sustav</li>
<li>Django signals dokumentacija — https://docs.djangoproject.com/en/5.0/topics/signals/</li>
<li>FCI rodovnicki standardi — https://www.fci.be/en/Pedigrees/</li>
<li>SHA-256 FIPS 180-4 — National Institute of Standards and Technology, 2015</li>
<li>Merkle, R.C. (1988). A Digital Signature Based on a Conventional Encryption Function.</li>
</ul>

</body></html>"""


def main():
    print(f"\n{'='*60}")
    print(f"  Konjik d.o.o. — {DP_ID}")
    print(f"  Digitalno Nasljedstvo Zivih Bica")
    print(f"{'='*60}\n")

    # Provjeri ne postoji li već
    if DefensivePublication.objects.filter(dp_id=DP_ID).exists():
        print(f"[!] {DP_ID} vec postoji u bazi. Brisem i regeneriram...")
        old = DefensivePublication.objects.get(dp_id=DP_ID)
        old.leaves.all().delete()
        old.delete()

    # ─── Generiraj Merkle leaves ──────────────────────────────────────────────
    print(f"[1/5] Generiram {len(REVEALED_CLAIMS)} revealed + {32 - len(REVEALED_CLAIMS)} blank Merkle lista...")
    leaves_data = []
    for i in range(32):
        salt = secrets.token_hex(32)
        if i < len(REVEALED_CLAIMS):
            content = REVEALED_CLAIMS[i]
            status  = "revealed"
        else:
            content = ""
            status  = "blank"
        lhash = hashlib.sha256(f"{content}{salt}".encode()).hexdigest()
        leaves_data.append((i, status, lhash, salt, content))

    # ─── Izračunaj Merkle root ────────────────────────────────────────────────
    print("[2/5] Racunam Merkle root...")
    level = [ld[2] for ld in leaves_data]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256((level[i] + level[i+1]).encode()).hexdigest()
            for i in range(0, len(level), 2)
        ]
    merkle_root = level[0]
    print(f"    Merkle root: {merkle_root[:32]}...")

    # ─── TAI64N timestamp ────────────────────────────────────────────────────
    tai64n = format(int(timezone.now().timestamp()) + (2**62) * 4, 'x')

    # ─── Kreiraj ChainBlock ───────────────────────────────────────────────────
    print("[3/5] Kreiram ChainBlock blok...")
    doc_hash = hashlib.sha256(f"{DP_ID}{merkle_root}{ABSTRACT}".encode()).hexdigest()
    block = ChainBlockPOE(
        block_number=ChainBlockPOE.next_block_number(),
        seal_token=DP_ID,
        issuer_name="Konjik d.o.o.",
        issuer_oib="0000000KONJIK",
        title="Digitalno Nasljedstvo Zivih Bica — Intergeneracijski Trust Score i Digitalna Oporuka",
        description=f"{DP_ID}: {ABSTRACT[:300]}",
        documents_json=[{
            "name": DP_ID,
            "hash": doc_hash,
            "size": len(ABSTRACT),
            "mime": "text/plain",
            "url": f"https://limit-connect.com/hr/chainblock/verify/{DP_ID}/",
        }],
        prev_hash=ChainBlockPOE.last_hash(),
        timestamp=timezone.now(),
    )
    block.block_hash = block.compute_block_hash()
    block.save()
    print(f"    Block #{block.block_number} · Hash: {block.block_hash[:32]}...")
    print(f"    Integrity check: {block.verify_integrity()}")

    # ─── Kreiraj DefensivePublication ─────────────────────────────────────────
    print("[4/5] Kreiram DefensivePublication i MerkleLeaf zapise...")
    dp = DefensivePublication.objects.create(
        dp_id=DP_ID,
        status="partial",
        title="Digitalno Nasljedstvo Zivih Bica — Intergeneracijski Trust Score i Digitalna Oporuka",
        abstract=ABSTRACT,
        inventors_json=[
            {"name": "Ivan Brtan",    "oib": "70086599476", "role": "primary"},
            {"name": "Marija Brtan",  "role": "co-inventor"},
            {"name": "Antonio Brtan", "role": "co-inventor"},
        ],
        ipc_class="G06F21/64; H04L9/32; G16H10/60; H04L9/00; G06F16/903",
        merkle_root=merkle_root,
        merkle_depth=5,
        tai64n=tai64n,
        puf_paper_id=f"KONJ-PAPER-2026-002-A",
        chainblock=block,
    )
    for idx, status, lhash, salt, content in leaves_data:
        MerkleLeaf.objects.create(
            publication=dp,
            index=idx,
            status=status,
            leaf_hash=lhash,
            salt=salt,
            content=content,
            revealed_at=timezone.now() if status == "revealed" else None,
        )

    # Verifikacija Merkle integriteta
    assert dp.verify_merkle(), "GREŠKA: Merkle verifikacija nije prošla!"
    print(f"    Merkle verifikacija: OK")
    print(f"    Listova: {dp.leaves.count()} (revealed: {dp.leaves.filter(status='revealed').count()})")

    # ─── Generiraj PDF ────────────────────────────────────────────────────────
    print(f"[5/5] Generiram PDF: {OUT_PDF}")
    html_content = build_html(dp, block, leaves_data, merkle_root)
    full_html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><style>{CSS}</style></head><body>"
    # Zamijeni body tag u build_html rezultatu (već ima DOCTYPE)
    html_for_weasy = html_content.replace(
        "<!DOCTYPE html><html lang=\"hr\"><head><meta charset=\"UTF-8\"></head><body>",
        f"<!DOCTYPE html><html lang=\"hr\"><head><meta charset=\"UTF-8\"><style>{CSS}</style></head><body>"
    )
    wp = weasyprint.HTML(string=html_for_weasy)
    wp.write_pdf(OUT_PDF)
    size_kb = os.path.getsize(OUT_PDF) // 1024
    print(f"    PDF size: {size_kb} KB")

    # ─── Finalni izvještaj ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ZAPECACENO: {DP_ID}")
    print(f"  ChainBlock:   Block #{block.block_number}")
    print(f"  Seal token:   {block.seal_token}")
    print(f"  Block hash:   {block.block_hash[:40]}...")
    print(f"  Merkle root:  {merkle_root[:40]}...")
    print(f"  TAI64N:       {tai64n}")
    print(f"  PDF:          {OUT_PDF}")
    print(f"  Integrity:    {block.verify_integrity()} / Merkle: {dp.verify_merkle()}")
    print(f"\n  Prioritetni datum: {DATUM}")
    print(f"  Svi Big Tech patenti na Digital Heritage sustav su BLOKIRANI.")
    print(f"{'='*60}\n")

    return dp, block


if __name__ == "__main__":
    main()
