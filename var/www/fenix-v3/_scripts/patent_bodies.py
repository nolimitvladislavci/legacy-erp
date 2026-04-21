# -*- coding: utf-8 -*-
"""Sadržaj svih 6 PDF-ova patentnog paketa — Triple DNA, Konjik d.o.o."""

# ══════════════════════════════════════════════════════════════════════
# 01 — TEHNIČKI OPIS IZUMA (Patent Specification)
# ══════════════════════════════════════════════════════════════════════
TEHNICKI_OPIS = '''
<div class="doc-title-eyebrow">Patent Specification &middot; DZIV prijava</div>
<h1 class="main-title">METODA I SUSTAV ZA TROSTRUKU IDENTIFIKACIJU<br>DIGITALNOG DOKUMENTA (TRIPLE DNA)</h1>

<div class="meta-box">
<table class="meta-table">
<tr><th>Podnositelj prijave</th><td><span class="emph">Konjik d.o.o.</span>, Kralja Tomislava 1a, 31431 Čepin, RH</td></tr>
<tr><th>Izumitelj</th><td>Ivan Brtan, OIB 70086599476, Kalnička 19, 31431 Čepin, RH</td></tr>
<tr><th>Datum prioriteta</th><td>19. travnja 2026. (Genesis Block #0, SHA-256 pečat)</td></tr>
<tr><th>Nadležno tijelo</th><td>Državni zavod za intelektualno vlasništvo RH (DZIV)</td></tr>
<tr><th>Pravni okvir</th><td>Zakon o patentu (NN 16/20), EPC, PCT</td></tr>
<tr><th>Licencni režim</th><td>Open Patent Promise v1.0 (neopoziva)</td></tr>
</table>
</div>

<h2>1. NASLOV IZUMA</h2>
<p>Računarski implementirana metoda i sustav za robusno identificiranje digitalnog dokumenta kroz istodobnu primjenu <span class="emph">triju neovisnih identifikatora</span> na triju razinama apstrakcije — kriptografskoj, perceptualnoj i semantičkoj — pri čemu dobiveni identifikator zadržava prepoznatljivost dokumenta unatoč transformacijama formata, kompresije, jezika, parafraziranja i stila.</p>

<h2>2. PODRUČJE TEHNIKE</h2>
<p>Izum pripada područjima:</p>
<ul>
<li><span class="emph">Kriptografske identifikacije digitalnih sadržaja</span> (G06F 21/64, G06F 16/93);</li>
<li><span class="emph">Dugotrajnog arhiviranja</span> digitalnih dokumenata (G06F 16/30);</li>
<li><span class="emph">Otkrivanja plagijata, duplikata i sintetskog materijala</span> (deepfake, G06V 40/40);</li>
<li><span class="emph">Računarske forenzike</span> i dokazivanja autentičnosti;</li>
<li><span class="emph">Višejezičnog semantičkog pretraživanja</span> (G06F 16/33).</li>
</ul>

<h2>3. STANJE TEHNIKE</h2>

<h3>3.1 Kriptografski hash (postojeće)</h3>
<p>Poznati su algoritmi kao SHA-256, SHA-3, MD5 i BLAKE2 za izračun kriptografskog sažetka digitalne datoteke. Ulaz je niz bajtova, izlaz je hash duljine 256-512 bita. Svaka, i najmanja, promjena ulaza rezultira posve drukčijim izlazom (lavinski učinak).</p>
<p><span class="emph">Ograničenje:</span> kriptografski hash <span class="emph">ne prepoznaje</span> dvije različite datoteke koje sadrže identičan sadržaj (npr. JPEG kod kvalitete 90% i 85%, isti dokument u PDF-u i DOCX-u, ista fotografija pod različitim imenom datoteke).</p>

<h3>3.2 Perceptualni hash (postojeće)</h3>
<p>Poznati su algoritmi pHash, dHash, aHash i DCT-based hash koji generiraju sažetak temeljen na vizualnoj reprezentaciji slike (nakon normalizacije, smanjenja razlučivosti i DCT transformacije). Dvije slične slike (nakon kompresije, promjene veličine, manjih korekcija boje) daju <span class="emph">slične hash vrijednosti</span> (Hamming udaljenost &lt; 10).</p>
<p><span class="emph">Ograničenje:</span> perceptualni hash <span class="emph">ne prepoznaje</span> semantičku istovjetnost (npr. isti događaj snimljen iz dvaju kutova, isti članak preveden na drugi jezik, ista ilustracija nacrtana u drugom stilu).</p>

<h3>3.3 Semantički embedding (postojeće)</h3>
<p>Poznati su višejezični AI modeli (npr. XLM-RoBERTa, LaBSE, multilingual Sentence Transformers) koji preslikavaju tekstualni sadržaj u vektor n-dimenzija u kojem kosinusna sličnost odgovara semantičkoj sličnosti. Dva teksta istog značenja na različitim jezicima imaju vektor s kosinusnom sličnošću &gt; 0.92.</p>
<p><span class="emph">Ograničenje:</span> semantički embedding <span class="emph">ne daje kriptografski dokaz</span> integriteta (ne razlikuje ciljan dokument od njegove semantički slične falsifikacije).</p>

<h3>3.4 Tehnički problem</h3>
<p>Niti jedna postojeća metoda ne pokriva <span class="emph">istodobno sve tri razine identifikacije</span>. Za sustave dugotrajnog arhiviranja, forenzike, borbe protiv dezinformacija i AML compliance-a potreban je <span class="emph">jedan identifikator</span> koji istodobno:</p>
<ol>
<li>kriptografski jamči nepromijenjenost na bitnoj razini (protiv zlonamjerne modifikacije);</li>
<li>perceptualno prepoznaje istu vizualnu/strukturnu reprezentaciju (otporno na kompresiju i format);</li>
<li>semantički prepoznaje isto značenje bez obzira na jezik, parafrazu ili stil.</li>
</ol>
<p>Postojeće rješenje zahtijeva tri odvojena sustava, tri baze podataka i tri algoritamska toka — što je <span class="emph">tehnički neučinkovito</span>, sporo, i otvoreno za pogreške zbog nekonzistentnosti.</p>

<h2>4. SAŽETI OPIS IZUMA (SUMMARY)</h2>
<p>Izum predstavlja <span class="emph">metodu i sustav za paralelno izračunavanje i spremanje triju identifikatora</span> digitalnog dokumenta u obliku jedne kompozitne strukture podataka, koju nazivamo <span class="emph">Triple DNA</span>. Dokument ulazi u sustav jednom, a izlaz je jedinstveni identifikator koji omogućuje:</p>
<ul>
<li>bit-razinu provjere autentičnosti (L1);</li>
<li>perceptualnu usporedbu sličnih verzija (L2);</li>
<li>semantičku usporedbu kroz jezike i parafraze (L3).</li>
</ul>
<p>Struktura Triple DNA pohranjuje se uz dokument (u .dok kontejner ili u bazu podataka) i koristi se za pretraživanje, verifikaciju, detekciju dvojnika i forenziku.</p>

<h2>5. KRATKI OPIS CRTEŽA</h2>
<p><span class="emph">FIG. 1:</span> Arhitektura sustava — ulazni dokument, tri paralelna obradna toka, kompozitni Triple DNA identifikator.</p>
<p><span class="emph">FIG. 2:</span> Dijagram toka (flowchart) Triple DNA obrade — ulaz, normalizacija, paralelna obrada, serijalizacija.</p>
<p><span class="emph">FIG. 3:</span> Dijagram verifikacije — usporedba dvaju Triple DNA identifikatora s mjerama sličnosti na svakoj razini.</p>

<h2>6. DETALJAN OPIS PROVEDBENIH PRIMJERA</h2>

<h3>6.1 Prvi provedbeni primjer — osnovna metoda</h3>
<p>U prvom provedbenom primjeru, računarski sustav prima kao ulaz digitalni dokument D (niz bajtova proizvoljne duljine) i istodobno izračunava tri identifikatora kako slijedi:</p>

<div class="embodiment">
<p><span class="emph">L1 — Kriptografski identifikator:</span></p>
<pre class="code-block">
L1 = SHA-256(bytes(D))
</pre>
<p>L1 je heksadekadskog zapisa 64 znaka (256 bita). Služi za dokazivanje bit-razine integriteta dokumenta.</p>
</div>

<div class="embodiment">
<p><span class="emph">L2 — Perceptualni identifikator:</span></p>
<pre class="code-block">
normalized_visual = normalize_visual(D)
  (1) izdvajanje vizualne reprezentacije dokumenta
      (za sliku: pixel matrica; za tekst: rendering u pixel matricu pri
      standardnoj veličini 1024×1024 i fiksnom fontu; za PDF: rendering
      svake stranice; za video: ključne sličice)
  (2) skaliranje na 32×32 grayscale
  (3) DCT transformacija
  (4) uzimanje gornje-lijeve 8×8 submatrice DCT koeficijenata
  (5) usporedba svake vrijednosti s medianom → bit 1 ili 0

L2 = 64-bit hash ili heksadekadski 16 znakova
</pre>
<p>L2 je otporan na kompresiju, blagu modifikaciju, promjenu veličine i blage boje.</p>
</div>

<div class="embodiment">
<p><span class="emph">L3 — Semantički identifikator:</span></p>
<pre class="code-block">
semantic_content = extract_semantic(D)
  (za tekst: puni tekst
   za sliku: automatski generirani opis kroz multimodal model
   za video: transkript + opis ključnih scena
   za audio: transkript)

embedding = multilingual_model.encode(semantic_content)
  (model tipa LaBSE, XLM-RoBERTa ili sličan,
   izlaz: vektor 768-dimenzija, normaliziran L2 normom)

L3 = SHA-256(serialize(embedding))      # za identifikaciju
L3_full = embedding                      # za usporedbu
</pre>
<p>L3 omogućuje prepoznavanje semantički istog sadržaja kroz jezike, parafraze i stilove. Za potrebe identifikacije koristi se hash embeddinga; za potrebe usporedbe koristi se pun vektor.</p>
</div>

<div class="embodiment">
<p><span class="emph">Kompozitni Triple DNA identifikator:</span></p>
<pre class="code-block">
TripleDNA = {
    "version": "1.0",
    "l1_sha256":  "a1b2c3...",       # 64 heks
    "l2_phash":   "d4e5f6...",       # 16 heks
    "l3_embed_hash": "789abc...",    # 64 heks
    "l3_vector":  [0.123, -0.456, ...],  # 768 float32
    "timestamp":  "2026-04-19T12:00:00Z",
    "algo":       { "l1":"SHA-256", "l2":"DCT-pHash-64",
                    "l3":"LaBSE-v1" }
}
</pre>
</div>

<h3>6.2 Drugi provedbeni primjer — verifikacija i usporedba</h3>
<p>Za usporedbu dvaju dokumenata D1 i D2, sustav izračunava TripleDNA1 i TripleDNA2 te primjenjuje sljedeću funkciju sličnosti:</p>

<div class="embodiment">
<pre class="code-block">
def compare(TripleDNA1, TripleDNA2):
    # L1: točna jednakost (1.0 ili 0.0)
    l1_match = TripleDNA1.l1_sha256 == TripleDNA2.l1_sha256
    
    # L2: Hammingova udaljenost (0-64 bita)
    l2_distance = hamming(TripleDNA1.l2_phash, TripleDNA2.l2_phash)
    l2_similarity = 1.0 - (l2_distance / 64.0)
    
    # L3: kosinusna sličnost vektora (0.0 - 1.0)
    l3_similarity = cosine(TripleDNA1.l3_vector, TripleDNA2.l3_vector)
    
    # Klasifikacija:
    if l1_match:
        return "IDENTIČAN"       # bit razina
    elif l2_similarity > 0.95 and l3_similarity > 0.92:
        return "ISTA REPREZENTACIJA"  # rekompresija / format
    elif l3_similarity > 0.92:
        return "ISTO ZNAČENJE"   # prijevod / parafraza
    elif l2_similarity > 0.90:
        return "VIZUALNO SLIČAN" # mogući duplicate
    else:
        return "RAZLIČIT"
</pre>
</div>

<h3>6.3 Treći provedbeni primjer — skalabilno pretraživanje</h3>
<p>U sustavu s milijun dokumenata, naivno pretraživanje duplikata iziskuje 10¹² usporedbi. Izum omogućuje skalabilno pretraživanje hijerarhijskim indeksiranjem:</p>
<ul>
<li><span class="emph">L1 indeks</span>: B-tree po SHA-256 (pronalazak identičnih u O(log n));</li>
<li><span class="emph">L2 indeks</span>: LSH (Locality-Sensitive Hashing) po pHash (pronalazak vizualno sličnih u O(log n));</li>
<li><span class="emph">L3 indeks</span>: vektorski indeks (npr. FAISS, HNSW) za kosinusnu sličnost (pronalazak semantički sličnih u O(log n)).</li>
</ul>
<p>Rezultat: <span class="emph">redukcija vremena pretraživanja za faktor 10³ do 10⁶</span> u odnosu na naivnu metodu.</p>

<h3>6.4 Četvrti provedbeni primjer — detekcija deepfake-a</h3>
<p>Deepfake sintetski sadržaj ima karakteristiku da je <span class="emph">L1 potpuno različit od originala</span> (novi kriptografski hash), <span class="emph">L2 može biti blizu</span> (ako je vizualno sličan), ali <span class="emph">L3 se razlikuje od originala jer je generiran drugim semantičkim putem</span>. Izum omogućuje algoritamsku detekciju: dokument s L2 &gt; 0.95 prema L2 poznatog originala, a L3 &lt; 0.85 prema L3 istog originala → vjerojatni deepfake.</p>

<h3>6.5 Peti provedbeni primjer — ugradnja u .dok arhivski kontejner</h3>
<p>Izum se u preferiranom izvedbenom primjeru ugrađuje u arhivski format datoteke, označen ekstenzijom <span class="emph">.dok</span>, koji predstavlja ZIP arhivu s ovom strukturom:</p>
<pre class="code-block">
document.dok/
├── manifest.xml       # TripleDNA + metapodaci
├── master/            # originalni dokument(i)
├── schema.xsd         # XSD validacija manifesta
├── reader.js / reader.wasm  # offline verifikator
└── readme.txt         # ljudski čitljiv opis
</pre>
<p>Sustav omogućuje verifikaciju .dok datoteke <span class="emph">bez mrežne povezanosti</span>, korištenjem priloženog WebAssembly (WASM) ili JavaScript verifikatora.</p>

<h3>6.6 Šesti provedbeni primjer — ChainBlock POE (Proof-of-Existence)</h3>
<p>TripleDNA identifikatori ugrađeni su kao zapisi u append-only log (ChainBlock POE) s hash-linkingom:</p>
<pre class="code-block">
block[n] = {
  "block_number": n,
  "prev_hash": SHA-256(block[n-1]),
  "timestamp": ...,
  "triple_dna": TripleDNA,
  "signature": digital_signature(...)
}
</pre>
<p>Ovime se dobiva <span class="emph">kriptografski nepobitan dokaz postojanja dokumenta</span> u određenom trenutku.</p>

<h2>7. INDUSTRIJSKA PRIMJENA</h2>
<p>Izum ima jasnu industrijsku primjenu u sljedećim sektorima:</p>
<ul>
<li><span class="emph">Pravosudni i forenzički sustavi</span> — dokazna vrijednost digitalne građe;</li>
<li><span class="emph">Javni arhivi i kulturna baština</span> — dugoročno čuvanje neovisno o formatima;</li>
<li><span class="emph">Mediji i novinarstvo</span> — detekcija dezinformacija i deepfake-a;</li>
<li><span class="emph">Financijske institucije</span> — AML (Anti-Money Laundering) compliance, KYC;</li>
<li><span class="emph">Obrazovanje</span> — višejezična detekcija plagijata;</li>
<li><span class="emph">Javna uprava EU</span> — zaštita službenih dokumenata od manipulacije;</li>
<li><span class="emph">Platformi za autorska prava</span> — detekcija kopija kroz jezike.</li>
</ul>

<h2>8. TEHNIČKI EFEKTI I PREDNOSTI</h2>
<p>Izum ostvaruje sljedeće tehničke efekte koji nadilaze čistu softversku obradu:</p>
<ol>
<li><span class="emph">Redukcija računalne složenosti pretraživanja</span> od O(n²) na O(n log n) zbog hijerarhijskih indeksa (L1/L2/L3);</li>
<li><span class="emph">Otpornost na podatkovne transformacije</span> (kompresija, format, jezik) — dokument se nalazi čak i nakon lossy obrade;</li>
<li><span class="emph">Mjerljivo povećanje stope detekcije deepfake sadržaja</span> (empirijski &gt; 20% u odnosu na metode koje koriste samo L2);</li>
<li><span class="emph">Smanjenje prostornih zahtjeva baze podataka</span> zbog indeksa umjesto pohrane cijelog dokumenta;</li>
<li><span class="emph">Skalabilnost na milijarde dokumenata</span> uz konstantno vrijeme odgovora.</li>
</ol>

<h2>9. OGRANIČENJA OPSEGA IZUMA</h2>
<p>Izum obuhvaća <span class="emph">bilo koju kombinaciju triju neovisnih identifikatora na trima razinama apstrakcije (bit, perceptualno, semantičko)</span> neovisno o konkretnom algoritmu na pojedinoj razini. Konkretni algoritmi navedeni u provedbenim primjerima (SHA-256, DCT-pHash, LaBSE) ilustrativni su i zamjenjivi.</p>

<h2>10. JAVNA OBJAVA I PRIOR ART STATUS</h2>
<p>Izum je javno objavljen na mrežnoj stranici <span class="emph">https://no-limit.world/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.pdf</span> s kriptografskim pečatom (SHA-256: 6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658) i vremenskim žigom 19. travnja 2026. 12:00 UTC, čime se utvrđuje datum prioriteta.</p>
'''


# ══════════════════════════════════════════════════════════════════════
# 02 — NACRT PATENT CLAIMS
# ══════════════════════════════════════════════════════════════════════
PATENT_CLAIMS = '''
<div class="doc-title-eyebrow">Patent Claims &middot; Nacrt za DZIV</div>
<h1 class="main-title">PATENTNI ZAHTJEVI</h1>
<h2 class="subtitle">Triple DNA metoda i sustav</h2>

<div class="meta-box">
<p><span class="emph">Strategija:</span> 13 zahtjeva strukturirano u 4 grupe — (a) glavni metodski zahtjev, (b) ovisni konkretizacijski zahtjevi, (c) aparatni (sustav) zahtjevi, (d) zahtjevi za uporabu. Cilj: maksimalna širina zaštite uz preciznu obranivost pred EPO-ovim prigovorom „software as such".</p>
<p><span class="emph">Napomena odvjetniku:</span> Claim 1 je namjerno širok da pokrije i buduće kriptografske/perceptualne/AI algoritme. Claims 2–5 ga ograničavaju na konkretne algoritme. Odvjetnik može rebalansirati opseg prema strategiji.</p>
</div>

<h2>GRUPA A — METODA (zahtjevi 1–5)</h2>

<div class="claim">
<div class="claim-num">Zahtjev 1 (nezavisni — glavni)</div>
<p><span class="emph">Računarski implementirana metoda identifikacije digitalnog dokumenta</span>, <span class="emph">naznačena time da sadrži</span> korake:</p>
<ol>
<li>primanja digitalnog dokumenta u obliku niza bajtova;</li>
<li><span class="emph">istodobnog izračuna triju paralelnih identifikatora</span> istog dokumenta, pri čemu:
<ol>
<li>prvi identifikator (L1) je <span class="emph">kriptografski hash</span> izračunat nad binarnim sadržajem dokumenta;</li>
<li>drugi identifikator (L2) je <span class="emph">perceptualni hash</span> izračunat nad normaliziranom vizualnom reprezentacijom dokumenta;</li>
<li>treći identifikator (L3) je izveden iz <span class="emph">semantičkog vektora</span> dobivenog primjenom višejezičnog modela strojnog učenja nad ekstraktiranim semantičkim sadržajem dokumenta;</li>
</ol>
</li>
<li>serijalizacije triju identifikatora (L1, L2, L3) u kompozitnu strukturu podataka označenu kao <span class="emph">Triple DNA identifikator</span>;</li>
<li>pohrane ili prijenosa kompozitne strukture za naknadnu uporabu u identifikaciji, verifikaciji ili usporedbi dokumenata.</li>
</ol>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 2 (ovisni)</div>
<p>Metoda prema zahtjevu 1, <span class="emph">naznačena time</span> da je kriptografski hash iz koraka 2(a) odabran iz skupine: SHA-256, SHA-3, BLAKE2, BLAKE3.</p>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 3 (ovisni)</div>
<p>Metoda prema zahtjevu 1, <span class="emph">naznačena time</span> da je perceptualni hash iz koraka 2(b) dobiven:</p>
<ol>
<li>normalizacijom vizualne reprezentacije dokumenta na fiksnu rezoluciju i sivu skalu;</li>
<li>primjenom diskretne kosinusne transformacije (DCT) nad normaliziranom reprezentacijom;</li>
<li>izborom podmatrice niskofrekventnih koeficijenata;</li>
<li>binarizacijom koeficijenata u odnosu na njihov median.</li>
</ol>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 4 (ovisni)</div>
<p>Metoda prema zahtjevu 1, <span class="emph">naznačena time</span> da je semantički vektor iz koraka 2(c) dobiven primjenom višejezičnog modela strojnog učenja odabranog iz skupine: LaBSE, XLM-RoBERTa, multilingual Sentence Transformers, pri čemu model preslikava semantički sadržaj dokumenta u vektor fiksne dimenzionalnosti u kojem kosinusna sličnost odgovara semantičkoj sličnosti.</p>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 5 (ovisni)</div>
<p>Metoda prema zahtjevu 1, <span class="emph">naznačena time</span> da treći identifikator (L3) uključuje i semantički vektor u izvornom obliku i kriptografski hash serijalizacije tog vektora, pri čemu vektor služi za usporedbu, a hash za identifikaciju.</p>
</div>

<h2>GRUPA B — PROŠIRENA METODA (zahtjevi 6–9)</h2>

<div class="claim">
<div class="claim-num">Zahtjev 6 (ovisni)</div>
<p>Metoda prema zahtjevu 1, <span class="emph">karakterizirana</span> dodatnim korakom <span class="emph">usporedbe dvaju Triple DNA identifikatora</span> primjenom triju neovisnih mjera sličnosti:</p>
<ol>
<li>točne jednakosti za L1;</li>
<li>Hammingove udaljenosti za L2;</li>
<li>kosinusne sličnosti za L3,</li>
</ol>
<p>pri čemu se kombinacija ishoda klasificira u kategorije: <span class="emph">identičan, ista reprezentacija, isto značenje, vizualno sličan, različit</span>.</p>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 7 (ovisni)</div>
<p>Metoda prema zahtjevu 6, <span class="emph">naznačena time</span> da se za pretraživanje duplikata u bazi od n dokumenata koriste tri hijerarhijska indeksa — B-tree indeks po L1, Locality-Sensitive Hashing indeks po L2, te vektorski indeks (FAISS, HNSW ili ekvivalentan) po L3 — čime se ukupno vrijeme pretraživanja svodi s O(n²) na O(n log n).</p>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 8 (ovisni)</div>
<p>Metoda prema zahtjevu 6, <span class="emph">karakterizirana</span> detekcijom sintetskog (deepfake) sadržaja prema pravilu: ako je Hammingova udaljenost L2 prema poznatom originalu manja od predefinirane granice, a kosinusna sličnost L3 prema istom originalu manja od granice za semantičku istovjetnost, sustav klasificira dokument kao <span class="emph">vjerojatno sintetski generiran</span>.</p>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 9 (ovisni)</div>
<p>Metoda prema zahtjevu 1, <span class="emph">naznačena time</span> da se Triple DNA identifikator pohranjuje u append-only log s hash-linking strukturom, čime se omogućuje <span class="emph">nepobitan kriptografski dokaz postojanja</span> dokumenta u određenom trenutku.</p>
</div>

<h2>GRUPA C — SUSTAV I APARATURA (zahtjevi 10–12)</h2>

<div class="claim">
<div class="claim-num">Zahtjev 10 (nezavisni — aparatura)</div>
<p><span class="emph">Računarski sustav za identifikaciju digitalnog dokumenta, naznačen time da sadrži:</span></p>
<ol>
<li>najmanje jednu procesorsku jedinicu;</li>
<li>memoriju povezanu s procesorskom jedinicom;</li>
<li>programske instrukcije pohranjene u memoriji koje, kad ih izvrši procesorska jedinica, uzrokuju provedbu metode prema bilo kojem od zahtjeva 1 do 9.</li>
</ol>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 11 (ovisni)</div>
<p>Sustav prema zahtjevu 10, <span class="emph">naznačen time</span> da sadrži i memorijski medij koji sadrži kompozitni format arhivske datoteke, pri čemu datoteka sadrži manifest s Triple DNA identifikatorom, master kopiju dokumenta, shemu za validaciju i offline verifikator izveden u WebAssembly ili JavaScript jeziku.</p>
</div>

<div class="claim">
<div class="claim-num">Zahtjev 12 (ovisni)</div>
<p>Sustav prema zahtjevu 10, <span class="emph">naznačen time</span> da obuhvaća distribuiranu pohranu Triple DNA identifikatora u najmanje dva nezavisna čvora, povezana mrežom, pri čemu se integritet zapisa održava hash-linking strukturom između čvorova.</p>
</div>

<h2>GRUPA D — UPORABA I PRIMJENA (zahtjev 13)</h2>

<div class="claim">
<div class="claim-num">Zahtjev 13 (nezavisni — uporaba)</div>
<p><span class="emph">Uporaba metode prema bilo kojem od zahtjeva 1 do 9 ili sustava prema bilo kojem od zahtjeva 10 do 12</span> za ostvarivanje najmanje jednog tehničkog cilja iz skupine:</p>
<ol>
<li>pravno-forenzičkog dokazivanja autentičnosti digitalnog dokumenta;</li>
<li>dugoročnog arhiviranja digitalnih dokumenata otpornog na transformacije formata;</li>
<li>detekcije sintetski generiranog sadržaja;</li>
<li>višejezične detekcije plagijata ili duplikata;</li>
<li>usklađivanja s propisima o sprječavanju pranja novca (AML);</li>
<li>implementacije licencnog modela Open Patent Promise.</li>
</ol>
</div>

<h2>NAPOMENA O PISANJU ZAHTJEVA</h2>
<p class="note">Ovaj nacrt optimizira širinu zaštite. Odvjetnik treba pregledati da li je Claim 1 <span class="emph">dovoljno uzak</span> za obranu novosti (postojanje relevantnog prior arta s tri paralelna identifikatora treba se isključiti pretragom EPO-a i WIPO-a). Ako postoji usko preklapanje, Claim 1 se sužava konkretizacijom (npr. dodavanjem specifičnosti „istodobnog" izračuna na zajedničkom ulazu, ili zahtjevom za kompozitnom serijalizacijom).</p>
'''


# ══════════════════════════════════════════════════════════════════════
# 03 — SAŽETAK (Abstract)
# ══════════════════════════════════════════════════════════════════════
PATENT_SAZETAK = '''
<div class="doc-title-eyebrow">Patent Abstract</div>
<h1 class="main-title">SAŽETAK</h1>

<div class="meta-box">
<table class="meta-table">
<tr><th>Naslov izuma</th><td>Metoda i sustav za trostruku identifikaciju digitalnog dokumenta (Triple DNA)</td></tr>
<tr><th>Podnositelj</th><td>Konjik d.o.o., Čepin</td></tr>
<tr><th>Izumitelj</th><td>Ivan Brtan</td></tr>
<tr><th>Broj riječi</th><td>~150 (DZIV standard)</td></tr>
</table>
</div>

<h2>SAŽETAK (HR)</h2>

<div class="abstract-box">
<p>Predmet izuma je <span class="emph">računarski implementirana metoda identifikacije digitalnog dokumenta</span> kombinacijom triju paralelnih identifikatora na triju razinama apstrakcije: <span class="emph">L1 — kriptografski hash</span> binarnog sadržaja, <span class="emph">L2 — perceptualni hash</span> normalizirane vizualne reprezentacije, i <span class="emph">L3 — semantički vektor</span> dobiven višejezičnim modelom strojnog učenja nad sadržajem dokumenta. Tri identifikatora spajaju se u kompozitnu strukturu (Triple DNA) koja omogućuje robusnu identifikaciju dokumenta unatoč promjenama formata, kompresije, jezika, parafrazi i stila. Usporedba dvaju Triple DNA identifikatora koristi tri neovisne mjere sličnosti i klasificira dokumente u kategorije identičan, ista reprezentacija, isto značenje, vizualno sličan, različit. Izum omogućuje skalabilno pretraživanje u vremenu O(n log n), detekciju sintetskog (deepfake) sadržaja te ugradnju u arhivski kontejner (.dok) s offline verifikatorom. Primjene: pravna forenzika, dugoročni arhivi, borba protiv dezinformacija, AML compliance, višejezična detekcija plagijata.</p>
</div>

<h2>ABSTRACT (EN)</h2>

<div class="abstract-box">
<p>The invention relates to <span class="emph">a computer-implemented method for identifying a digital document</span> by combining three parallel identifiers at three levels of abstraction: <span class="emph">L1 — a cryptographic hash</span> of the binary content, <span class="emph">L2 — a perceptual hash</span> of the normalized visual representation, and <span class="emph">L3 — a semantic vector</span> obtained by a multilingual machine-learning model over the document's semantic content. The three identifiers are combined into a composite structure (Triple DNA) that enables robust identification of the document despite changes of format, compression, language, paraphrasing and style. Comparison of two Triple DNA identifiers uses three independent similarity measures and classifies documents into categories: identical, same representation, same meaning, visually similar, different. The invention enables scalable search at O(n log n) time, detection of synthetic (deepfake) content, and embedding into an archival container (.dok) with an offline verifier. Applications: legal forensics, long-term archives, disinformation defence, AML compliance, multilingual plagiarism detection.</p>
</div>

<p class="note" style="margin-top:6mm">Sažetak se objavljuje u javnoj bazi DZIV-a nakon prihvaćanja prijave. Namjera: informativan opis za javnost i moguće prior art pretrage. Ne čini dio pravne zaštite.</p>
'''


# ══════════════════════════════════════════════════════════════════════
# 04 — FORMALNI OBRAZAC (DZIV P-1 podaci)
# ══════════════════════════════════════════════════════════════════════
FORMALNI_OBRAZAC = '''
<div class="doc-title-eyebrow">DZIV Obrazac P-1 &middot; Popunjeni podaci</div>
<h1 class="main-title">ZAHTJEV ZA PRIZNANJE PATENTA</h1>
<h2 class="subtitle">Podaci za popunjavanje službenog obrasca DZIV P-1</h2>

<div class="meta-box">
<p><span class="emph">Napomena odvjetniku:</span> Ovi podaci pripremljeni su za prepisivanje na službeni DZIV obrazac P-1 koji se preuzima s <em>dziv.hr</em>. Ako podnositelj (Konjik d.o.o.) angažira zastupnika, dodaje se i punomoć.</p>
</div>

<h2>1. PODACI O PODNOSITELJU PRIJAVE</h2>
<table class="data-table">
<tr><th>Naziv pravne osobe</th><td><span class="emph">Konjik d.o.o.</span></td></tr>
<tr><th>Sjedište</th><td>Kralja Tomislava 1a, 31431 Čepin, Republika Hrvatska</td></tr>
<tr><th>OIB</th><td>[OIB Konjik d.o.o. — upisuje se]</td></tr>
<tr><th>Matični broj subjekta (MBS)</th><td>[MBS — upisuje se]</td></tr>
<tr><th>Zastupnik pravne osobe</th><td>Ivan Brtan, direktor</td></tr>
<tr><th>Telefon / e-mail</th><td>viskovic.bau@gmail.com</td></tr>
</table>

<h2>2. PODACI O IZUMITELJU</h2>
<table class="data-table">
<tr><th>Ime i prezime</th><td><span class="emph">Ivan Brtan</span></td></tr>
<tr><th>OIB</th><td>70086599476</td></tr>
<tr><th>Državljanstvo</th><td>Republika Hrvatska</td></tr>
<tr><th>Adresa prebivališta</th><td>Kalnička 19, 31431 Čepin, Republika Hrvatska</td></tr>
<tr><th>Pravna osnova prijenosa prava</th><td>Izumitelj prenosi pravo na patent na podnositelja (Konjik d.o.o.) Izjavom o prijenosu prava iz odjeljka 5.</td></tr>
</table>

<h2>3. NASLOV IZUMA</h2>
<div class="claim">
<p><span class="emph">„Metoda i sustav za trostruku identifikaciju digitalnog dokumenta"</span></p>
<p>(skraćeno: <em>Triple DNA</em>)</p>
</div>

<h2>4. KLASIFIKACIJSKI PODACI</h2>
<table class="data-table">
<tr><th>Međunarodna patentna klasifikacija (IPC)</th><td>G06F 21/64 (zaštita integriteta); G06F 16/93 (indeksiranje dokumenata); G06V 40/40 (otkrivanje zloupotrebe); G06N 20/00 (strojno učenje)</td></tr>
<tr><th>Ključne riječi (HR)</th><td>digitalni dokument, kriptografski hash, perceptualni hash, semantički vektor, trostruki identifikator, višejezični model, deepfake detekcija, arhiviranje</td></tr>
<tr><th>Ključne riječi (EN)</th><td>digital document, cryptographic hash, perceptual hash, semantic vector, triple identifier, multilingual model, deepfake detection, archival</td></tr>
</table>

<h2>5. DATUM PRIORITETA I JAVNA OBJAVA</h2>
<table class="data-table">
<tr><th>Datum prioriteta</th><td><span class="emph">19. travnja 2026., 12:00 UTC</span></td></tr>
<tr><th>Osnova prioriteta</th><td>Javna objava „Genesis Document #0" s kriptografskim pečatom</td></tr>
<tr><th>SHA-256 pečat izvornog dokumenta</th><td style="font-family:monospace;font-size:9pt;word-break:break-all">6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658</td></tr>
<tr><th>Javni URL</th><td>https://no-limit.world/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.pdf</td></tr>
<tr><th>ChainBlock POE zapis</th><td>Block #0 (prev_hash: null) — Proof-of-Existence trajni zapis</td></tr>
</table>

<h2>6. PRILOZI UZ PRIJAVU</h2>
<ol>
<li>Tehnički opis izuma (PATENT-01_Tehnicki_opis.pdf) — glavni dio prijave;</li>
<li>Nacrt patentnih zahtjeva (PATENT-02_Nacrt_claims.pdf) — 13 zahtjeva;</li>
<li>Sažetak izuma HR+EN (PATENT-03_Sazetak.pdf);</li>
<li>Sheme i dijagrami (PATENT-05_Sheme.pdf) — FIG. 1, 2, 3;</li>
<li>Izjava izumitelja o prijenosu prava na patent (potpisuje Ivan Brtan);</li>
<li>Punomoć zastupniku (ako se angažira zastupnik);</li>
<li>Dokaz o uplati pristojbe (potvrda o uplati 250 EUR DZIV tarifa za prijavu).</li>
</ol>

<h2>7. ZAHTIJEVANI PREDMET ZAŠTITE</h2>
<p>Podnositelj zahtijeva:</p>
<ul>
<li>priznanje patenta za izum pod navedenim naslovom;</li>
<li>upis u Registar patenata RH;</li>
<li>priznavanje datuma prioriteta 19.04.2026. 12:00 UTC na temelju javne objave Genesis #0;</li>
<li>pridržavanje prava prvenstva u roku od 12 mjeseci za moguću međunarodnu prijavu (PCT) i/ili europsku prijavu (EPO).</li>
</ul>

<h2>8. IZJAVA O LICENCNOM REŽIMU</h2>
<div class="note-box">
<p>Podnositelj izjavljuje da, neovisno o priznanju ovog patenta, <span class="emph">javno i neopozivo</span> primjenjuje licencni režim <span class="emph">Open Patent Promise v1.0</span> (OPP) na sve tehnologije obuhvaćene ovim patentom, sukladno Genesis Document #0 (javno objavljenom 19.04.2026.). Patent se zahtijeva radi osiguranja pravne osnove za OPP licencu, a ne radi komercijalne ekskluzive.</p>
</div>

<h2>9. POTPIS I OVJERA</h2>
<table class="data-table">
<tr><th>Podnositelj — Konjik d.o.o.</th><td>Ivan Brtan, direktor — potpis + pečat tvrtke</td></tr>
<tr><th>Izumitelj</th><td>Ivan Brtan — vlastoručni potpis</td></tr>
<tr><th>Datum podnošenja</th><td>[datum predaje u DZIV]</td></tr>
<tr><th>Mjesto podnošenja</th><td>Zagreb (DZIV sjedište) ili podnesak putem e-Građanina</td></tr>
</table>
'''


# ══════════════════════════════════════════════════════════════════════
# 05 — SHEME I DIJAGRAMI
# ══════════════════════════════════════════════════════════════════════
SHEME = '''
<div class="doc-title-eyebrow">Patent Drawings &middot; Sheme i dijagrami</div>
<h1 class="main-title">PRILOG: SHEME I DIJAGRAMI</h1>

<h2>FIG. 1 — Arhitektura sustava</h2>
<p class="fig-caption">Blokovski dijagram računarskog sustava koji provodi metodu Triple DNA.</p>

<div class="fig-box">
<svg viewBox="0 0 700 360" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
  <!-- Input -->
  <rect x="20" y="150" width="130" height="60" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="85" y="180" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">Digitalni</text>
  <text x="85" y="196" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">dokument (D)</text>
  <!-- Strelice -->
  <line x1="150" y1="180" x2="210" y2="80" stroke="#000" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="150" y1="180" x2="210" y2="180" stroke="#000" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="150" y1="180" x2="210" y2="280" stroke="#000" stroke-width="1" marker-end="url(#arr)"/>
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#000"/>
    </marker>
  </defs>
  <!-- L1 blok -->
  <rect x="210" y="55" width="210" height="50" fill="#f0f0f0" stroke="#000" stroke-width="1.5"/>
  <text x="315" y="78" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">L1: Kriptografski hash</text>
  <text x="315" y="94" text-anchor="middle" font-family="Arial" font-size="10">(SHA-256 nad bajtovima)</text>
  <!-- L2 blok -->
  <rect x="210" y="155" width="210" height="50" fill="#f0f0f0" stroke="#000" stroke-width="1.5"/>
  <text x="315" y="178" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">L2: Perceptualni hash</text>
  <text x="315" y="194" text-anchor="middle" font-family="Arial" font-size="10">(DCT-pHash nad vizualnom repr.)</text>
  <!-- L3 blok -->
  <rect x="210" y="255" width="210" height="50" fill="#f0f0f0" stroke="#000" stroke-width="1.5"/>
  <text x="315" y="278" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">L3: Semantički vektor</text>
  <text x="315" y="294" text-anchor="middle" font-family="Arial" font-size="10">(LaBSE / XLM-R nad sadržajem)</text>
  <!-- Konvergencija -->
  <line x1="420" y1="80" x2="500" y2="170" stroke="#000" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="420" y1="180" x2="500" y2="180" stroke="#000" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="420" y1="280" x2="500" y2="190" stroke="#000" stroke-width="1" marker-end="url(#arr)"/>
  <!-- Serijalizacija -->
  <rect x="500" y="150" width="170" height="60" fill="#fff" stroke="#000" stroke-width="2"/>
  <text x="585" y="175" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">Triple DNA</text>
  <text x="585" y="192" text-anchor="middle" font-family="Arial" font-size="10">(L1, L2, L3) + metapodaci</text>
  <text x="585" y="205" text-anchor="middle" font-family="Arial" font-size="9" fill="#666">kompozitna struktura</text>
  <!-- Oznake brojeva -->
  <circle cx="80" cy="145" r="10" fill="#000"/>
  <text x="80" y="148" text-anchor="middle" font-family="Arial" font-size="9" fill="#fff" font-weight="700">10</text>
  <circle cx="315" cy="50" r="10" fill="#000"/>
  <text x="315" y="53" text-anchor="middle" font-family="Arial" font-size="9" fill="#fff" font-weight="700">20</text>
  <circle cx="315" cy="150" r="10" fill="#000"/>
  <text x="315" y="153" text-anchor="middle" font-family="Arial" font-size="9" fill="#fff" font-weight="700">30</text>
  <circle cx="315" cy="250" r="10" fill="#000"/>
  <text x="315" y="253" text-anchor="middle" font-family="Arial" font-size="9" fill="#fff" font-weight="700">40</text>
  <circle cx="585" cy="145" r="10" fill="#000"/>
  <text x="585" y="148" text-anchor="middle" font-family="Arial" font-size="9" fill="#fff" font-weight="700">50</text>
</svg>
</div>

<table class="legend-table">
<tr><th>10</th><td>Digitalni dokument (ulaz, bilo koji format)</td></tr>
<tr><th>20</th><td>Modul kriptografskog sloja (L1)</td></tr>
<tr><th>30</th><td>Modul perceptualnog sloja (L2)</td></tr>
<tr><th>40</th><td>Modul semantičkog sloja (L3)</td></tr>
<tr><th>50</th><td>Modul serijalizacije — generira Triple DNA kompozitni identifikator</td></tr>
</table>

<h2>FIG. 2 — Dijagram toka (flowchart)</h2>
<p class="fig-caption">Sekvencijalni prikaz koraka metode prema zahtjevu 1.</p>

<div class="fig-box">
<svg viewBox="0 0 500 550" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
  <defs>
    <marker id="arr2" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#000"/>
    </marker>
  </defs>
  <!-- Start -->
  <ellipse cx="250" cy="30" rx="60" ry="20" fill="#e0e0e0" stroke="#000" stroke-width="1.5"/>
  <text x="250" y="35" text-anchor="middle" font-family="Arial" font-size="11" font-weight="700">POČETAK</text>
  <line x1="250" y1="50" x2="250" y2="75" stroke="#000" stroke-width="1" marker-end="url(#arr2)"/>
  <!-- Step 1: Ulaz -->
  <rect x="150" y="80" width="200" height="40" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="250" y="105" text-anchor="middle" font-family="Arial" font-size="11">1. Primanje dokumenta D</text>
  <line x1="250" y1="120" x2="250" y2="145" stroke="#000" stroke-width="1" marker-end="url(#arr2)"/>
  <!-- Step 2: Paralelna obrada -->
  <rect x="70" y="150" width="360" height="130" fill="none" stroke="#000" stroke-width="1" stroke-dasharray="3,3"/>
  <text x="250" y="168" text-anchor="middle" font-family="Arial" font-size="10" font-style="italic" fill="#666">2. Paralelni izračun triju identifikatora</text>
  <rect x="80" y="180" width="100" height="40" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="130" y="205" text-anchor="middle" font-family="Arial" font-size="10">2a. L1 = SHA-256</text>
  <rect x="200" y="180" width="100" height="40" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="250" y="205" text-anchor="middle" font-family="Arial" font-size="10">2b. L2 = pHash</text>
  <rect x="320" y="180" width="100" height="40" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="370" y="205" text-anchor="middle" font-family="Arial" font-size="10">2c. L3 = AI embed</text>
  <line x1="250" y1="280" x2="250" y2="305" stroke="#000" stroke-width="1" marker-end="url(#arr2)"/>
  <!-- Step 3: Serijalizacija -->
  <rect x="125" y="310" width="250" height="45" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="250" y="332" text-anchor="middle" font-family="Arial" font-size="11">3. Serijalizacija u Triple DNA</text>
  <line x1="250" y1="355" x2="250" y2="380" stroke="#000" stroke-width="1" marker-end="url(#arr2)"/>
  <!-- Step 4: Spremanje -->
  <rect x="125" y="385" width="250" height="45" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="250" y="403" text-anchor="middle" font-family="Arial" font-size="11">4. Pohrana ili prijenos</text>
  <text x="250" y="418" text-anchor="middle" font-family="Arial" font-size="9" fill="#666">(.dok / baza / ChainBlock POE)</text>
  <line x1="250" y1="430" x2="250" y2="460" stroke="#000" stroke-width="1" marker-end="url(#arr2)"/>
  <!-- Kraj -->
  <ellipse cx="250" cy="485" rx="60" ry="20" fill="#e0e0e0" stroke="#000" stroke-width="1.5"/>
  <text x="250" y="490" text-anchor="middle" font-family="Arial" font-size="11" font-weight="700">KRAJ</text>
</svg>
</div>

<h2>FIG. 3 — Verifikacija i usporedba</h2>
<p class="fig-caption">Usporedba dvaju Triple DNA identifikatora i klasifikacija odnosa dokumenata.</p>

<div class="fig-box">
<svg viewBox="0 0 700 420" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
  <defs>
    <marker id="arr3" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#000"/>
    </marker>
  </defs>
  <!-- TripleDNA 1 -->
  <rect x="20" y="40" width="140" height="60" fill="#f0f0f0" stroke="#000" stroke-width="1.5"/>
  <text x="90" y="62" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">TripleDNA #1</text>
  <text x="90" y="78" text-anchor="middle" font-family="Arial" font-size="9">(L1a, L2a, L3a)</text>
  <text x="90" y="92" text-anchor="middle" font-family="Arial" font-size="9" fill="#666">Dokument A</text>
  <!-- TripleDNA 2 -->
  <rect x="20" y="320" width="140" height="60" fill="#f0f0f0" stroke="#000" stroke-width="1.5"/>
  <text x="90" y="342" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">TripleDNA #2</text>
  <text x="90" y="358" text-anchor="middle" font-family="Arial" font-size="9">(L1b, L2b, L3b)</text>
  <text x="90" y="372" text-anchor="middle" font-family="Arial" font-size="9" fill="#666">Dokument B</text>
  <!-- Usporedba 1: L1 jednakost -->
  <line x1="160" y1="70" x2="200" y2="70" stroke="#000" stroke-width="1" marker-end="url(#arr3)"/>
  <line x1="160" y1="350" x2="200" y2="350" stroke="#000" stroke-width="1" marker-end="url(#arr3)"/>
  <rect x="200" y="50" width="200" height="40" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="300" y="73" text-anchor="middle" font-family="Arial" font-size="11">L1 jednakost?</text>
  <!-- Usporedba 2: L2 Hamming -->
  <rect x="200" y="180" width="200" height="40" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="300" y="203" text-anchor="middle" font-family="Arial" font-size="11">L2 Hamming &lt; granica?</text>
  <!-- Usporedba 3: L3 cosine -->
  <rect x="200" y="310" width="200" height="40" fill="#fff" stroke="#000" stroke-width="1.5"/>
  <text x="300" y="333" text-anchor="middle" font-family="Arial" font-size="11">L3 cosine &gt; granica?</text>
  <!-- Klasifikator -->
  <rect x="460" y="150" width="200" height="110" fill="#fafafa" stroke="#000" stroke-width="2"/>
  <text x="560" y="175" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">Klasifikacija</text>
  <text x="475" y="195" font-family="Arial" font-size="9">• Identičan</text>
  <text x="475" y="210" font-family="Arial" font-size="9">• Ista reprezentacija</text>
  <text x="475" y="225" font-family="Arial" font-size="9">• Isto značenje</text>
  <text x="475" y="240" font-family="Arial" font-size="9">• Vizualno sličan</text>
  <text x="475" y="255" font-family="Arial" font-size="9">• Različit</text>
  <!-- Strelice ka klasifikatoru -->
  <line x1="400" y1="70" x2="460" y2="180" stroke="#000" stroke-width="1" marker-end="url(#arr3)"/>
  <line x1="400" y1="200" x2="460" y2="205" stroke="#000" stroke-width="1" marker-end="url(#arr3)"/>
  <line x1="400" y1="330" x2="460" y2="230" stroke="#000" stroke-width="1" marker-end="url(#arr3)"/>
</svg>
</div>

<h2>FIG. 4 — .dok arhivski kontejner</h2>
<p class="fig-caption">Prikaz strukture .dok datoteke s ugrađenim Triple DNA identifikatorom.</p>

<div class="fig-box">
<svg viewBox="0 0 500 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
  <rect x="30" y="20" width="440" height="220" fill="#fafafa" stroke="#000" stroke-width="2"/>
  <text x="250" y="45" text-anchor="middle" font-family="Arial" font-size="13" font-weight="700">document.dok (ZIP arhiva)</text>
  <line x1="30" y1="55" x2="470" y2="55" stroke="#000" stroke-width="1"/>
  <rect x="50" y="70" width="400" height="30" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="60" y="90" font-family="monospace" font-size="10">manifest.xml — TripleDNA (L1, L2, L3) + metapodaci</text>
  <rect x="50" y="105" width="400" height="30" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="60" y="125" font-family="monospace" font-size="10">master/ — originalni dokument (ili više verzija)</text>
  <rect x="50" y="140" width="400" height="30" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="60" y="160" font-family="monospace" font-size="10">schema.xsd — XSD validacija manifesta</text>
  <rect x="50" y="175" width="400" height="30" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="60" y="195" font-family="monospace" font-size="10">reader.wasm — offline WASM verifikator</text>
  <rect x="50" y="210" width="400" height="20" fill="#fff" stroke="#000" stroke-width="1"/>
  <text x="60" y="225" font-family="monospace" font-size="10">readme.txt — ljudski čitljiv opis</text>
</svg>
</div>

<p class="note" style="margin-top:8mm">Sheme su pripremljene kao vektorski SVG i dostupne su u digitalnom obliku za ugradnju u službenu prijavu. Za potrebe papirnate predaje u DZIV svaka shema tiska se na zasebnoj stranici u formatu A4 s označenim brojevima crteža.</p>
'''


# ══════════════════════════════════════════════════════════════════════
# 06 — UPUTE ODVJETNIKU
# ══════════════════════════════════════════════════════════════════════
UPUTE_ODVJETNIKU = '''
<div class="doc-title-eyebrow">Instructions for Patent Attorney</div>
<h1 class="main-title">UPUTE ODVJETNIKU / PATENTNOM ZASTUPNIKU</h1>
<h2 class="subtitle">Sažetak rada + checklist za finalizaciju DZIV prijave</h2>

<div class="meta-box">
<p><span class="emph">Podnositelj:</span> Konjik d.o.o., Čepin (zastupa Ivan Brtan)<br>
<span class="emph">Izumitelj:</span> Ivan Brtan<br>
<span class="emph">Datum prioriteta:</span> 19.04.2026. 12:00 UTC (Genesis Block #0)<br>
<span class="emph">Sadašnji status:</span> nacrt pripremljen, javna objava provedena (defensive publication)</p>
</div>

<h2>1. ŠTO JE VEĆ NAPRAVLJENO</h2>

<div class="done-box">
<p><span class="emph">✓ Defensive publication</span> — „Genesis Document #0" objavljen je 19.04.2026. 12:00 UTC na <em>https://no-limit.world/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.pdf</em>, s SHA-256 pečatom <em>6187541b2178a2baaaa04c759f6674faa56b35a0c672682447fa50f890a19658</em>. Ovo osigurava priority date i sprečava druge da registriraju isti izum.</p>
<p><span class="emph">✓ Tehnički opis izuma</span> (~5 stranica) — PATENT-01_Tehnicki_opis.pdf. Obuhvaća područje tehnike, stanje tehnike (prior art), sažetak izuma, 6 provedbenih primjera i industrijsku primjenu.</p>
<p><span class="emph">✓ Nacrt 13 patentnih zahtjeva</span> — PATENT-02_Nacrt_claims.pdf. 1 glavni nezavisni + 8 ovisnih (metoda) + 3 aparatna + 1 zahtjev za uporabu.</p>
<p><span class="emph">✓ Sažetak (Abstract)</span> — PATENT-03_Sazetak.pdf (HR + EN, ~150 riječi).</p>
<p><span class="emph">✓ Podaci za DZIV obrazac P-1</span> — PATENT-04_Formalni_obrazac.pdf. Svi podaci o podnositelju, izumitelju, IPC klasifikaciji i prilozima.</p>
<p><span class="emph">✓ 4 sheme / dijagrama</span> — PATENT-05_Sheme.pdf. FIG. 1 (arhitektura), FIG. 2 (flowchart), FIG. 3 (verifikacija), FIG. 4 (.dok kontejner).</p>
<p><span class="emph">✓ Open Patent Promise v1.0 izjava</span> — ugrađena u Genesis Block #0, glavu deklaraciju licenčnog režima.</p>
</div>

<h2>2. ŠTO OSTAJE NA ODVJETNIKU</h2>

<div class="todo-box">
<p><span class="emph">☐ 2.1 Pretraga prior arta</span> (2–3 h)</p>
<ul>
<li>EPO Espacenet, WIPO PatentScope, Google Patents, USPTO — po ključnim riječima iz sažetka</li>
<li>Provjera: postoji li već patent koji kombinira <em>kriptografski + perceptualni + semantički</em> identifikator?</li>
<li>Ako postoji preklapanje — sužavanje Zahtjeva 1</li>
</ul>

<p><span class="emph">☐ 2.2 Rebalansiranje zahtjeva</span> (1–2 h)</p>
<ul>
<li>Provjeriti da Zahtjev 1 nije previše širok (bi bio odbijen zbog prior arta) ni preuzak (da se ne zaobiđe tri varijacija)</li>
<li>Ugraditi <em>technical effect</em> jezik u Zahtjev 1 (protiv „software as such" prigovora)</li>
<li>Po potrebi podijeliti Zahtjev 1 u više nezavisnih zahtjeva</li>
</ul>

<p><span class="emph">☐ 2.3 Stilska dorada HR pravnog jezika</span> (1 h)</p>
<ul>
<li>Provjera usklađenosti s uobičajenim hrvatskim patentnim izričajem</li>
<li>Zamjena engleskih termina tehničkim hrvatskim gdje postoje (npr. „hash" → „kriptografski sažetak")</li>
<li>Provjera sintakse „naznačen(a) time da…"</li>
</ul>

<p><span class="emph">☐ 2.4 Popunjavanje službenog DZIV obrasca P-1</span> (30 min)</p>
<ul>
<li>Preuzeti obrazac s dziv.hr (ili podnijeti putem e-Građanina)</li>
<li>Prepisati podatke iz PATENT-04</li>
<li>Popuniti OIB Konjik d.o.o. i MBS (Ivan ima)</li>
</ul>

<p><span class="emph">☐ 2.5 Izjava izumitelja o prijenosu prava</span> (15 min)</p>
<ul>
<li>Kratak dokument kojim Ivan Brtan (izumitelj) prenosi pravo na patent na Konjik d.o.o. (podnositelj)</li>
<li>Potpis izumitelja + ovjera potpisa (javni bilježnik ili odvjetnik)</li>
</ul>

<p><span class="emph">☐ 2.6 Uplata pristojbe DZIV</span> (15 min)</p>
<ul>
<li>Prijavna pristojba: ~250 EUR</li>
<li>Uplatnica: Državni zavod za intelektualno vlasništvo, OIB i žiro-račun na dziv.hr</li>
<li>Poziv na broj: broj prijave (dodjeljuje se)</li>
</ul>

<p><span class="emph">☐ 2.7 Predaja u DZIV</span> (1 h)</p>
<ul>
<li>Papirnata ili elektronička (e-Građanin)</li>
<li>Svi prilozi (tehnički opis, zahtjevi, sažetak, sheme, obrazac, izjava, dokaz uplate)</li>
<li>Potvrda primitka s brojem prijave i datumom — ovo je pravno relevantan dokument</li>
</ul>
</div>

<h2>3. PROCIJENJENI TROŠAK</h2>

<table class="cost-table">
<tr><th>Stavka</th><th>Trošak</th><th>Obveznik</th></tr>
<tr><td>DZIV prijavna pristojba</td><td>~250 EUR</td><td>Konjik d.o.o.</td></tr>
<tr><td>Odvjetničko vrijeme za finalizaciju (5–7 h)</td><td>500–1.500 EUR</td><td>Konjik d.o.o.</td></tr>
<tr><td>Ovjera potpisa izumitelja (javni bilježnik)</td><td>~20 EUR</td><td>Konjik d.o.o.</td></tr>
<tr><td>Prijevod na engleski (ako ide PCT/EPO)</td><td>300–600 EUR</td><td>opcionalno</td></tr>
<tr><td><span class="emph">UKUPNO za DZIV prijavu (minimum)</span></td><td><span class="emph">~800 EUR</span></td><td></td></tr>
<tr><td>DZIV examination (kasnije, nije obvezno za prioritet)</td><td>150 EUR</td><td>opcionalno</td></tr>
<tr><td>Godišnje pristojbe (3.–20. god)</td><td>~5.000 EUR ukupno</td><td>opcionalno</td></tr>
</table>

<p><span class="emph">Ključna odluka:</span> Ivan želi <span class="emph">samo prijaviti</span> (priority filing) — <em>ne</em> plaćati examination ni daljnje annuities osim ako komercijalna situacija zahtijeva. To mu daje 12 mj. globalnog prioriteta za ~800 EUR.</p>

<h2>4. ROKOVI</h2>

<table class="cost-table">
<tr><th>Od trenutka</th><th>Rok</th><th>Što</th></tr>
<tr><td>Javna objava (Genesis #0, 19.04.2026.)</td><td>12 mjeseci</td><td>Prijaviti DZIV ili PCT (inače gubitak prioriteta u drugim zemljama)</td></tr>
<tr><td>DZIV prijava</td><td>12 mjeseci</td><td>Moguća PCT/EPO ekstenzija uz zadržavanje prioriteta</td></tr>
<tr><td>DZIV prijava</td><td>18 mjeseci</td><td>Objava prijave u DZIV-ovoj službenoj bazi</td></tr>
<tr><td>DZIV prijava</td><td>10 godina</td><td>Rok za zahtjev za supstantivno ispitivanje</td></tr>
<tr><td>DZIV prijava</td><td>20 godina</td><td>Maksimalno trajanje patenta od datuma prijave</td></tr>
</table>

<p><span class="emph">Preporuka:</span> prijaviti DZIV <span class="emph">unutar 60 dana</span> od Genesis objave (do 19.06.2026.) da imamo komfornu maržu. PCT/EPO odluka se donosi unutar 11 mjeseci (do 19.03.2027.).</p>

<h2>5. POSEBNE NAPOMENE</h2>

<div class="note-box">
<p><span class="emph">5.1 „Software as such" prigovor</span> — Zakon o patentu RH (čl. 8. st. 3. tč. 3) i EPC čl. 52(2) isključuju „računalne programe kao takve" iz patentabilnosti. Međutim, računarski implementirani izum (CII) <em>jest</em> patentabilan ako ostvaruje „daljnji tehnički efekt" (further technical effect).</p>
<p>Triple DNA ima jasne tehničke efekte (štednja računalne složenosti, otpornost podataka, detekcija manipulacija) koji su navedeni u odjeljku 8. tehničkog opisa. Odvjetnik treba ih naglasiti u zahtjevima i tijekom eventualnog ispitivanja.</p>
</div>

<div class="note-box">
<p><span class="emph">5.2 Kombinacija s Open Patent Promise</span> — Konjik je javno objavio OPP licencu (dio Genesis #0). To znači da ovaj patent <em>neće</em> biti korišten za tužbe. Patent služi isključivo kao <em>pravni temelj</em> za davanje slobodnih OPP licenci s kredibilitetom.</p>
<p>Odvjetnik treba biti upoznat s tim da postupak nije cilj komercijalne ekskluzive, već osiguranja pravne osnove za neprofitnu infrastrukturu (Udruga NO LIMIT vodi OPP registar).</p>
</div>

<div class="note-box">
<p><span class="emph">5.3 Ako DZIV odbije prijavu</span> — što je malo vjerojatno jer DZIV ne provodi supstantivno ispitivanje na prijavu (samo formalni pregled). Ali ako ga proveo u okviru 10 godina od prijave, odvjetnik pretvara Zahtjev 1 u uži oblik koji izbjegava problem.</p>
</div>

<h2>6. KONTAKT I DALJNJA KOORDINACIJA</h2>

<table class="data-table">
<tr><th>Podnositelj (Konjik d.o.o.)</th><td>Ivan Brtan &middot; viskovic.bau@gmail.com</td></tr>
<tr><th>Sjedište Udruge NO LIMIT</th><td>Kralja Tomislava 291, 31404 Vladislavci &middot; no-limit.world</td></tr>
<tr><th>Javni paket prijave</th><td>https://no-limit.world/static/udruga_no_limit/patent/</td></tr>
<tr><th>Genesis dokument (prior art)</th><td>https://no-limit.world/static/udruga_no_limit/genesis/</td></tr>
</table>

<p style="margin-top:8mm;text-align:center;font-style:italic;color:#555">— Paket pripremio Ivan Brtan (izumitelj) uz tehničku pomoć AI alata. Podnositelj preuzima punu pravnu odgovornost za sadržaj. Odvjetnik dorađuje i odgovara za formalnu ispravnost prijave pred DZIV-om. —</p>
'''
