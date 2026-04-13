"""
Management command: seed_knowledge_base
Popunjava KnowledgeArticle s 8 compliance + 4 POS + 4 invoicing + 3 general članka.

Pokretanje (pregled):
    venv/bin/python manage.py seed_knowledge_base --dry-run

Pokretanje (produkcija):
    venv/bin/python manage.py seed_knowledge_base --run

Ažuriranje postojećih (po titulu):
    venv/bin/python manage.py seed_knowledge_base --run --update

Audit: Ivan Brtan + Sonnet — 02.04.2026.
Pravna provjera: 2 korekcije (PDV kava 25%, JOPPD min 2.000 EUR)
e-Račun datum: potvrđen iz porezna.gov.hr (NN 89/25)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

ARTICLES = [
    # ── COMPLIANCE (8) ──────────────────────────────────────────────
    {
        "module": "compliance",
        "title": "ZKI i JIR: što su i zašto postoje",
        "priority": 1,
        "keywords": "zki, jir, fiskalizacija, zaštitni kod, jedinstveni identifikator, fina, cis, porezna uprava, porezna, šteka porezna, ne radi fiskalizacija, crveno, ne ispisuje jir, račun bez jir, fiskalni račun",
        "content": """ZKI (Zaštitni kod izdavatelja) i JIR (Jedinstveni identifikator računa) su dva obvezna elementa svakog fiskalnog računa prema Zakonu o fiskalizaciji (NN 133/12, 115/16, 106/18).

**ZKI** se generira lokalno na blagajni u trenutku izdavanja računa. Nastaje kao MD5 hash iz pet elemenata: OIB obveznika, datum i vrijeme, broj računa, iznos računa i oznaka operatera. Ne zahtijeva internet — uvijek se može izračunati.

**JIR** dodjeljuje FINA-in CIS (Centralni informacijski sustav) kada blagajna pošalje zahtjev za fiskalizaciju. JIR je potvrda da je Porezna uprava primila podatke o računu. Bez JIR-a račun je "u redu čekanja" za fiskalizaciju.

**Zakonski rok:** Ako CIS nije dostupan (pao internet, FINA maintenance), račun se smije izdati samo s ZKI-em. JIR se mora dostaviti u roku **48 sati** od uspostave veze (čl. 11 ZoF). Na ispisku mora pisati: *"Veza s CIS-om nije ostvarena."*

**Kazne:** Izdavanje računa bez ZKI — do 30.000 EUR. Neisporuka JIR-a u 48h — do 30.000 EUR (čl. 26 ZoF).

**LIMIT Connect:** ZKI se automatski generira pri svakom računu. JIR se dohvaća od FINA-e. Status fiskalizacije vidljiv je na svakom računu u Arhivi.""",
    },
    {
        "module": "compliance",
        "title": "Offline fiskalizacija: 48-satni zakonski rok",
        "priority": 1,
        "keywords": "offline, pao internet, nema interneta, 48h, 48 sati, bez veze, cis nedostupan, naknadna fiskalizacija, veza s cisom nije ostvarena, fina ne radi, retry, jir naknadno, šteka porezna, crven račun, internet ne radi",
        "content": """Prema čl. 11 Zakona o fiskalizaciji, obveznik smije nastaviti izdavati račune čak i kada CIS (FINA) nije dostupan. Sustav tada radi u **offline modu**.

**Što se mora napraviti:**
1. Račun se izdaje s lokalnim ZKI-em (generira se bez interneta)
2. JIR polje ostaje prazno
3. Na ispisku mora biti natpis: *"Veza s CIS-om nije ostvarena"*
4. Čim se internet obnovi → sustav **automatski šalje sve nakupljene račune** Poreznoj upravi

**Rok za naknadnu dostavu JIR-a:** 48 sati od trenutka kad je veza s CIS-om uspostavljena — ne od trenutka izdavanja računa.

**LIMIT Connect offline mod:** Sustav automatski prepoznaje gubitak interneta, sprema račune lokalno, prikazuje narančasto upozorenje na ekranu i sinkronizira se čim se veza vrati. Kasir ne mora ništa ručno raditi.

**Alarm:** Ako internet nije dostupan duže od 36 sati, sustav šalje upozorenje jer se bliži zakonski rok. Podrška: +385 97 609 1655 (Marija)

**Kazna za prekoračenje 48h:** do 30.000 EUR.""",
    },
    {
        "module": "compliance",
        "title": "PDV stope u Hrvatskoj 2025./2026.",
        "priority": 1,
        "keywords": "pdv, porez na dodanu vrijednost, stopa, 25%, 13%, 5%, pdv kalkulator, koliki je pdv, pdv ugostiteljstvo, pdv hrana, pdv piće, pdv alkohol, nulta stopa, izvoz, pdv na usluge, koja stopa, kava pdv, kafa pdv, topli napici",
        "content": """Hrvatska primjenjuje tri PDV stope prema Zakonu o PDV-u (NN 73/13 i izmjene):

**25% — opća stopa** (sve što nije eksplicitno navedeno niže)
Primjeri: alkoholna pića, duhanski proizvodi, luksuzna dobra, elektronika, odjeća, većina usluga, **kava i svi topli napici** (espresso, cappuccino, čaj, kakao), sokovi u PET bocama za odnijeti.

**13% — snižena stopa**
Primjeri: hrana za konzumaciju na licu mjesta (ugostiteljstvo), bezalkoholna pića u ugostiteljstvu **(isključujući kavu i tople napitke koji su 25%)**, dječja hrana, jestiva ulja i masti, isporuka vode, hotelski smještaj (noćenje s doručkom), ulaznice za kulturne i sportske priredbe, bijeli šećer.

**5% — snižena stopa**
Primjeri: sve knjige (tiskane i digitalne), lijekovi na recept, medicinska oprema za dijabetes, dječje autosjedalice, kruh, mlijeko, jaja, svježe meso, riba, voće, povrće.

**Praktično za ugostiteljstvo:**
- Kava, espresso, čaj, cappuccino → **25%**
- Hrana na tanjuru (ručak, večera) → **13%**
- Bezalkoholni sok u čaši (serviran) → **13%**
- Alkohol (pivo, vino, žestoka pića) → **25%**
- Mineralna voda u boci → **13%** (servirana), **25%** (za odnijeti u PET)""",
    },
    {
        "module": "compliance",
        "title": "JOPPD obrazac: rokovi i kazne",
        "priority": 2,
        "keywords": "joppd, obrazac joppd, plaće, plaća, doprinosi, porez na dohodak, rokovi prijave, 15. u mjesecu, obračun plaća, honorar, ugovor o djelu, kazna, zaboravio joppd, kasnim s joppodom, pogreška u joppodu, eporezna",
        "content": """JOPPD (Izvješće o primicima, porezu na dohodak i prirezu te doprinosima za obvezna osiguranja) obrazac se podnosi **elektronički** putem ePorezna sustava.

**Rokovi podnošenja:**
- **Plaće zaposlenika:** do **15. u tekućem mjesecu** za prethodni mjesec
- **Honorari / ugovor o djelu / autorski honorar:** do **3. radnog dana** od isplate
- **Dividende, povlačenje sredstava:** do **3. radnog dana** od isplate
- **Isplate u naravi:** u roku 3 radna dana

**Ispravak pogreške:** Ako je JOPPD predan s greškom, može se podnijeti **ispravni obrazac** (oznaka P2) unutar roka zastare (3 godine). Kasne ispravke mogu rezultirati kamatama.

**Kazne:** Za nepodnošenje ili nepravodobno podnošenje:
- **2.000 – 200.000 EUR** za pravnu osobu
- **200 – 2.000 EUR** za odgovornu osobu
(čl. 206 Općeg poreznog zakona, EUR denominacija od 01.01.2023.)

**LIMIT Connect:** JOPPD se automatski priprema iz modula Radna snaga → Obračun plaća. Nakon odobrenja obračuna, sustav generira XML datoteku za upload u ePorezna.""",
    },
    {
        "module": "compliance",
        "title": "e-Račun (Fiskalizacija 2.0): obveze od 2026. i 2027.",
        "priority": 1,
        "keywords": "eracun, e-racun, elektronički račun, b2b, xml račun, ubl, fina eracun, obaveza eracuna, kada kreće eracun, en16931, digitalni račun, fiskalizacija 2.0, pdv obveznik, posrednik, kpd, cius-hr, b2c transakcijski račun",
        "content": """Zakon o fiskalizaciji (NN 89/25) uvodi Fiskalizaciju 2.0 — obveznu razmjenu elektroničkih računa.

**Tko mora i od kada:**

**Od 1. siječnja 2026. — PDV obveznici:**
- Moraju izdavati I zaprimati eRačune za sve B2B transakcije u Hrvatskoj
- Papirnati i PDF računi više nisu pravno valjani za B2B
- Uz to: svi transakcijski (bezgotovinski) B2C računi moraju se fiskalizirati od 1.1.2026.

**Od 1. siječnja 2026. — svi ostali (paušalisti, OPG, obrtu bez PDV-a):**
- Moraju **zaprimati** eRačune od PDV obveznika
- Mogu koristiti besplatnu aplikaciju **MikroeRačun** (ePorezna)

**Od 1. siječnja 2027. — svi ostali:**
- Moraju i **izdavati** eRačune

**Format:** UBL XML 2.1, usklađen s europskim standardom **EN 16931** + hrvatska proširenja (CIUS-HR). Svaka stavka mora imati KPD 2025 klasifikacijsku šifru (6 znamenki).

**Dostava:** Putem certificiranog informacijskog posrednika (FINA, Moj-eRačun, drugi registrirani). LIMIT Connect koristi FINA kanal.

**Što se NE mijenja:**
- Računi fizičkim osobama (B2C gotovina/kartica) → ostaje Fiskalizacija 1.0, ZKI/JIR
- Inozemni kupci → obični račun (nije eRačun)

**LIMIT Connect:** OutboundPipeline automatski generira UBL XML, primjenjuje XAdES-BES digitalni potpis i šalje kroz FINA e-Račun sustav.""",
    },
    {
        "module": "compliance",
        "title": "Blagajnički maksimum: limit gotovinskih plaćanja između poduzetnika",
        "priority": 2,
        "keywords": "blagajnički maximum, gotovina, gotovinska plaćanja, limit gotovine, 15000 eur, pranje novca, cash, koliko gotovine smije, gotovinski promet, b2b gotovina, zakon gotovina, limit cash, isplata gotovinom",
        "content": """Prema Zakonu o sprječavanju pranja novca i financiranja terorizma (NN 108/17, izmjena NN 55/22), **gotovinska plaćanja između pravnih osoba i obrtnika** ograničena su.

**Limit: 15.000 EUR** po transakciji (ili nizu povezanih transakcija) između poslovnih subjekata.

Iznos iznad limita mora se platiti bezgotovinskim putem (virman, kartica, transakcijski račun).

**Ovo se NE odnosi na:**
- Naplate od fizičkih osoba (gosti, kupci) — tamo nema gornjeg limita za gotovinu
- Blagajnu prodajnog mjesta (POS) — nema zakonskog maksimuma koliko gotovine smije biti u blagajni

**Praktično:** Ako dobavljač dođe po gotovinski plaćanje fakture — iznos iznad 15.000 EUR mora ići na račun, ne u ruke.

**Kazna:** 10.000 – 1.000.000 EUR za pravnu osobu; 1.000 – 10.000 EUR za fizičku osobu.""",
    },
    {
        "module": "compliance",
        "title": "GDPR za ugostitelje i male poduzetnike",
        "priority": 2,
        "keywords": "gdpr, zaštita podataka, osobni podaci, kamera, videonadzor, pravo na zaborav, privola, newsletter, email marketing, cookies, pohrana podataka gostiju, brisanje podataka, gdpr kazna, azop, osobni podaci gostiju",
        "content": """GDPR (Opća uredba o zaštiti podataka, EU 2016/679) obvezuje sve koji obrađuju osobne podatke građana EU-a.

**Videonadzor:** Snimke se smiju čuvati **maksimalno 30 dana** (AZOP smjernice), osim kod incidenta. Obvezan vidljivi natpis.

**Podaci o rezervacijama:** Ime, kontakt, datum — mogu se čuvati radi poslovnih evidencija do **11 godina** (ZOR). Marketinška obrada zahtijeva privolu.

**Email / WhatsApp marketing:** Bez eksplicitne privole (opt-in) zabranjeno.

**Pravo na brisanje:** Gost može zatražiti brisanje podataka. **Iznimka:** fiskalizacijski zapisi i računovodstveni podaci čuvaju se 11 godina bez obzira na zahtjev.

**LIMIT Connect:** GDPR dashboard dostupan na /gdpr/dashboard/. Arhiva primjenjuje 11-godišnji retention za fiskalizacijske dokumente automatski.

**Kazne:** Do 20.000.000 EUR ili 4% godišnjeg prihoda (veće od toga).""",
    },
    {
        "module": "compliance",
        "title": "Storno računa: kada i kako",
        "priority": 2,
        "keywords": "storno, storniranje, pogreška na računu, krivi iznos, krivi pdv, otkazati račun, poništiti račun, ispraviti račun, storno fiskalizacija, s račun, storno zki jir, refund, povrat, reklamacija, negativni račun",
        "content": """Storno račun (oznaka **S**) izdaje se kada treba poništiti već fiskalizirani račun. Nema zakonskog roka — može se napraviti u bilo koje vrijeme.

**Kada se radi storno:**
- Pogrešno unesena cijena ili PDV stopa
- Pogrešan artikl
- Kupac vraća robu
- Duplikat računa

**Postupak u LIMIT Connect:**
1. Pronađi originalni račun u Arhivi
2. Klikni "Storno" → sustav kreira novi račun tipa **S** koji referira na originalni (po broju)
3. Storno prolazi fiskalizaciju (dobiva vlastiti ZKI i JIR)
4. Iznos je negativan (= zrcalna slika originalnog)

**PDV ispravak:** Ako je izdan R1 (B2B) račun s PDV-om, storno omogućava ispravak PDV-a u tekućem obračunskom razdoblju ili u roku 3 godine (čl. 33 ZPDV).

**Blagajnički utjecaj:** Storno smanjuje dnevni promet u Z-izvještaju. Gotovinski povrat kupcu mora biti evidentiran kao isplata iz blagajne.

**Nije dozvoljeno:** Brisanje računa umjesto storniranja. Svaki izdan fiskalni račun mora imati vidljiv zapis — zakonska obveza čuvanja 11 godina.""",
    },
    # ── POS (5) ──────────────────────────────────────────────────────
    {
        "module": "pos",
        "title": "Z-izvještaj i zatvaranje smjene",
        "priority": 1,
        "keywords": "z-izvještaj, z report, zatvaranje smjene, zaključak smjene, dnevni promet, prebrojati blagajnu, gotovina na kraju dana, smjena, kasir, z ispis, z dokument",
        "content": """Z-izvještaj je dnevni zaključak blagajne koji se radi na kraju radnog dana ili smjene.

**Što sadrži Z-izvještaj:**
- Ukupni promet (gotovina + kartica + ostalo)
- Broj izdanih računa
- PDV po stopama (5%, 13%, 25%)
- Polog i podizanja gotovine
- Stanja po kasirima (ako više kasira)

**Postupak u LIMIT Connect:**
1. Klikni gumb **Z** (gornji desni kut POS-a)
2. Unesi prebrojanu gotovinu
3. Sustav izračuna razliku (višak/manjak)
4. Potvrdi → smjena se zatvara, Z-izvještaj se generira kao PDF

**Zakonska obveza:** Prema ZoF, dnevni izvještaj mora biti pohranjen. LIMIT Connect automatski arhivira sve Z-izvještaje.

**Z-izvještaj ne briše podatke** — samo zatvara tekuću smjenu. Svi računi ostaju vidljivi u Arhivi.""",
    },
    {
        "module": "pos",
        "title": "Gratis i popust na POS-u",
        "priority": 3,
        "keywords": "gratis, popust, besplatno, discount, sniženje, akcija, kupon, posto popusta, gratis artikl, promo, poklon, besplatan artikl na blagajni",
        "content": """POS u LIMIT Connect podržava dvije vrste umanjenja cijene: **gratis** (0 EUR) i **popust** (%).

**Gratis artikl:**
- Dodaj artikl u košaricu
- Klikni na njega → unesi cijenu 0,00
- Fiskalizira se s iznosom 0 EUR (zakonski ispravno)

**Postotni popust:**
- Dodaj artikle u košaricu
- Klikni ikonu % → unesi postotak
- Primjenjuje se na cijelu košaricu ili samo na odabrani artikl

**Napomena za PDV:** Gratis artikl i dalje ima PDV stopu u sistemu — za internu evidenciju. Na računu se ispisuje cijena 0,00 EUR.

**Kupon / voucher:** Klikni gumb 🎫 u košarici → unesi kod vaučera → iznos se odbija od ukupnog.""",
    },
    {
        "module": "pos",
        "title": "PIN kasir: promjena blagajnika bez odjave",
        "priority": 3,
        "keywords": "pin, kasir, blagajnik, promjena kasira, odjava kasira, pin kod, prijava blagajnik, tko je na blagajni, pin blagajna",
        "content": """LIMIT Connect POS podržava brzu promjenu kasira putem PIN-a — bez odjave iz sustava.

**Promjena kasira:**
1. Klikni na ime trenutnog kasira (gornji lijevi kut POS-a)
2. Unesi PIN novog kasira (4 znamenke)
3. Blagajna se prebacuje na novog kasira

**Postavljanje PIN-a:** Administrator → Korisnici → odaberi zaposlenika → Postavi POS PIN.

**Zašto je ovo važno zakonski:** Svaki račun mora imati oznaku operatera (kasira) koji ga je izdao — to je zakonski zahtjev fiskalizacije (ZoF čl. 9). PIN sustav osigurava da je pravi kasir evidentiran na svakom računu.""",
    },
    {
        "module": "pos",
        "title": "Revolut i kartično plaćanje na POS-u",
        "priority": 3,
        "keywords": "revolut, kartica, plaćanje karticom, terminal, visa, mastercard, card payment, bezgotovinsko, pos kartica, revolut plaćanje",
        "content": """LIMIT Connect POS podržava gotovinu, karticu i Revolut kao načine plaćanja.

**Revolut:**
1. U košarici klikni gumb **REVOLUT** (ljubičasti)
2. Otvara se QR kod ili link za plaćanje
3. Kupac skenira QR mobitelom i plaća
4. Blagajna automatski bilježi plaćanje

**Kartica (vanjski terminal):**
1. Klikni **KARTICA**
2. Naplatni iznos se prikazuje kupcu
3. Provuci karticu na fizičkom terminalu
4. Potvrdi u POS-u

**Mješovito plaćanje** (dio gotovina, dio kartica): klikni Napredno → unesi iznos za gotovinu → ostatak ide na karticu.

**Napomena:** Kartično i Revolut plaćanje fiskalizira se isto kao gotovina — svaki račun dobiva ZKI i JIR.""",
    },
    {
        "module": "pos",
        "title": "Napojnica (tiping) — fiskalizacija od 2026.",
        "priority": 2,
        "keywords": "napojnica, tip, tiping, bakšiš, napojnice fiskalizacija, porez na napojnicu, kako fiskalizirati napojnicu, zakon napojnice 2026",
        "content": """Od 1. siječnja 2026. (Fiskalizacija 2.0), napojnice koje se plaćaju karticom ili transakcijskim putem **moraju se fiskalizirati**.

**Gotovinska napojnica:** I dalje nije obvezno fiskalizirati — konobar prima gotovinom, ne evidentira se.

**Kartična napojnica:** Ako gost na POS terminalu doda napojnicu pri plaćanju karticom, ona se mora fiskalizirati kao posebna stavka na računu ili kao poseban račun.

**LIMIT Connect:** Na POS-u, pri kartičnom plaćanju, prikazuje se polje za unos napojnice. Iznos se automatski dodaje na račun i fiskalizira.

**PDV na napojnicu:** Napojnica je prihod zaposlenika — ne podliježe PDV-u. Na računu se iskazuje zasebno, bez PDV-a.""",
    },
    # ── INVOICING (4) ────────────────────────────────────────────────
    {
        "module": "invoicing",
        "title": "Vrste računa: R, R1, A, S, FA, OTP",
        "priority": 1,
        "keywords": "vrste računa, r račun, r1 račun, avansni račun, storno, otpremnica, fa račun, b2b, b2c, pdv na računu, gotovinski račun, transakcijski račun, koji tip računa",
        "content": """LIMIT Connect podržava sve zakonski propisane vrste računovodstvenih dokumenata:

**R** — Gotovinski/kartični račun (B2C)
Račun krajnjem potrošaču (fizičkoj osobi). Fiskalizira se kroz ZoF 1.0, sadrži ZKI i JIR. PDV se obračunava ali ne prikazuje zasebno (osim ako kupac zatraži R1).

**R1** — Račun s iskazanim PDV-om (B2B)
Račun poslovnom kupcu (pravnoj osobi ili obrtniku). Sadrži OIB kupca, PDV prikazan zasebno po stopama. Kupac može odbiti PDV kao pretporez.

**A** — Avansni (predujamni) račun
Izdaje se pri primanju predujma. Mora se stornirati pri isporuci i kreirati konačni R1.

**S** — Storno
Poništava prethodno izdan račun. Sadrži referencu na originalni račun. Fiskalizira se s negativnim iznosom.

**FA** — Faktura (bez fiskalizacije)
Za usluge koje se naplaćuju virmanom, bez blagajničke naplate. Ne fiskalizira se kroz ZoF (nije gotovinska naplata).

**OTP** — Otpremnica
Dokument koji prati robu pri isporuci. Nema PDV-a — to dolazi na R1 pri naplati.

**Kako odabrati:** Fizička osoba plaća gotovinom/karticom → **R**. Firma plaća virmanom → **FA**. Firma plaća gotovinom → **R1**.""",
    },
    {
        "module": "invoicing",
        "title": "Avansni račun: tijek od predujma do konačnog računa",
        "priority": 2,
        "keywords": "avansni, predujam, avans, uplata unaprijed, avansni račun, konačni račun, storno avansa, pdv avans, avansni r1, depozit",
        "content": """Avansni račun (tip A) se izdaje kada kupac plati dio ili cijeli iznos prije isporuke robe ili usluge.

**Tijek dokumenta:**
1. Kupac uplati predujam → kreiraj **Avansni račun (A)**
2. PDV se obračunava i iskazuje već u avansnom računu
3. Pri isporuci → kreiraj **R1 konačni račun** s punim iznosom
4. R1 mora referencirati avansni: u napomeni navedi broj avansnog računa
5. Ako je avans bio jednaka finalnom iznosu → iznos na R1 je 0 EUR (plaćeno avansno)

**PDV pravilo:** PDV se plaća u trenutku primitka predujma — ne čeka isporuku (čl. 31 ZPDV).

**LIMIT Connect:** Odaberi tip "A" pri kreiranju računa → unesi iznos predujma → sustav automatski prati odnos avans/konačni račun u modulu Dugovanja.""",
    },
    {
        "module": "invoicing",
        "title": "Slanje e-Računa kroz LIMIT Connect",
        "priority": 1,
        "keywords": "slanje eracuna, posrednik, fina eracun, xml, ubl, kako poslati eracun, eracun poslovnom kupcu, moj-eracun, informacijski posrednik, kpd šifra, klasifikacija, eracun greška",
        "content": """LIMIT Connect automatski generira i šalje eRačune PDV obveznicima putem FINA kanala.

**Postupak:**
1. Kreiraj FA ili R1 račun (tip B2B)
2. Unesi OIB primatelja — sustav dohvaća naziv i adresu iz registra
3. Provjeri KPD šifre na stavkama (6-znamenkasta oznaka iz KPD 2025)
4. Klikni "Pošalji eRačun"
5. Sustav generira UBL XML → potpisuje XAdES-BES certifikatom → šalje FINA-i

**Status praćenja:** Svaki eRačun ima status: U_REDU / GREŠKA / NA_ČEKANJU / DOSTAVLJENO. Vidljivo u Arhivi → eRačuni.

**Česte greške:**
- "Nevažeći OIB" → provjeri OIB primatelja u porezna.gov.hr
- "KPD šifra nedostaje" → dodaj KPD šifru na stavku u Skladištu
- "Certifikat istekao" → kontaktiraj FINA-u za obnovu

**Bez PDV certifikata:** Ako nisi PDV obveznik, eRačun šalješ kroz MikroeRačun (aplikacija ePorezna) — LIMIT Connect generira XML koji možeš uploadati.""",
    },
    {
        "module": "invoicing",
        "title": "Faktura vs. fiskalni račun: kada što koristiti",
        "priority": 2,
        "keywords": "faktura, fiskalni račun, kad trebam fiskalnu blagajnu, virman, kada fiskalizirati, bezgotovinska naplata, račun za firmu, r1 gotovina, razlika faktura račun",
        "content": """Česta zabluda: "firmama šaljem fakturu, ne trebam fiskalnu blagajnu."

**Pravilo je jednostavno:**

| Tko plaća | Kako plaća | Dokument | Fiskalizacija |
|-----------|-----------|----------|---------------|
| Fizička osoba | Gotovina ili kartica | R (blagajnički) | DA — ZKI+JIR |
| Fizička osoba | Virman / transakcija | R (od 2026.) | DA — Fisk. 2.0 |
| Firma | Gotovina ili kartica | R1 (blagajnički) | DA — ZKI+JIR |
| Firma | Virman | FA (faktura/eRačun) | NE (Fisk. 1.0), DA od 2026. (Fisk. 2.0) |

**Od 1.1.2026. nova pravila:** Svi transakcijski (bezgotovinski) računi fizičkim osobama moraju se fiskalizirati — više nema iznimke za virman B2C.

**Praktično:** Ugostitelj koji iznajmljuje sobe — gostima koji plaćaju karticom ili gotovinom → fiskalni R. Agenciji koja plaća virmanom → eRačun (FA/R1 u UBL XML formatu).""",
    },
    # ── GENERAL (3) ──────────────────────────────────────────────────
    {
        "module": "general",
        "title": "Što je LIMIT Connect i kako početi",
        "priority": 1,
        "keywords": "limit connect, erp, blagajna, fiskalizacija, što je limit connect, kako koristiti, početi, registracija, prvi koraci, onboarding, help, pomoc, upute",
        "content": """LIMIT Connect je sve-u-jednom ERP i POS sustav za male i srednje poduzetnike u Hrvatskoj i EU.

**Što sustav uključuje:**
- 🧾 POS blagajna s automatskom fiskalizacijom (ZKI/JIR)
- 📄 Fakturiranje i e-Račun (Fiskalizacija 2.0)
- 📦 Skladište i zalihe
- 👥 Radni sati i evidencija zaposlenika
- 📊 Financijsko izvještavanje
- 🤝 Udruge (DVD, KUD, ribari, pčelari, vatrogasci...)
- 🐾 Golubarstvo i OPG modul

**Brzi start:**
1. Registriraj tvrtku (OIB + naziv)
2. Postavi POS terminal i kasire
3. Unesi artikle u Skladište (s PDV stopama)
4. Otvori smjenu i počni naplaćivati

**Podrška:** +385 97 609 1655 (Marija) | fina.connect.online@gmail.com""",
    },
    {
        "module": "general",
        "title": "Česti problemi i rješenja",
        "priority": 2,
        "keywords": "problem, greška, ne radi, error, 500, blagajna ne radi, ne mogu se prijaviti, zaboravio lozinku, ne ispisuje račun, sporо, tech support, podrška",
        "content": """**POS ne fiskalizira / crveni ekran:**
→ Provjeri internet vezu. Sustav nastavlja raditi offline (ZKI bez JIR-a). JIR dolazi kad se veza obnovi (rok 48h).

**Ne mogu se prijaviti:**
→ Provjeri caps lock. Ako zaboravljena lozinka: klikni "Zaboravio/la lozinku" na login stranici → kod stiže na email.

**Račun ne ispisuje:**
→ Provjeri je li pisač povezan. Za termalni pisač: provjeri USB/Bluetooth vezu. Za PDF ispis: klikni ikonu PDF na računu.

**Artikl nema PDV stopu:**
→ Idi u Skladište → pronađi artikl → uredi → postavi PDV stopu.

**"Greška 500" ili bijeli ekran:**
→ Osviježi stranicu (F5). Ako traje: kontaktiraj podršku s opisom što si radio.

**Podrška:** +385 97 609 1655 (Marija, radnim danom 8-16h)""",
    },
    {
        "module": "general",
        "title": "Arhiviranje dokumenata: koliko dugo čuvati",
        "priority": 3,
        "keywords": "arhiva, čuvanje dokumenata, zakon o računovodstvu, zor, 11 godina, rok čuvanja, brisanje, gdpr arhiva, fiskalni zapisi, stari računi",
        "content": """**Zakon o računovodstvu (ZOR) propisuje:**

- Fiskalni računi, temeljnice, knjige ulaznih/izlaznih računa → **11 godina**
- Platne liste i JOPPD → **11 godina**
- Ugovori s radnicima → **6 godina od prestanka radnog odnosa**
- Opća korespondencija → **2 godine** (preporuka, nije zakonski minimum)

**GDPR vs. ZOR:** Korisnik može tražiti brisanje osobnih podataka (GDPR čl. 17), ali fiskalizacijski i računovodstveni podaci **ne smiju se brisati** — ZOR ima prednost.

**LIMIT Connect Arhiva** automatski primjenjuje ove rokove. Dokumenti stariji od 11 godina označavaju se za pregled i eventualno arhiviranje van sustava.

**Nikad ne brišite:** fiskalne račune, Z-izvještaje, temeljnice, platne liste — to su zakonski zaštićeni podaci.""",
    },
]


class Command(BaseCommand):
    help = "Seed KnowledgeArticle s compliance, POS, invoicing i general člancima."

    def add_arguments(self, parser):
        parser.add_argument("--run", action="store_true", help="Stvarno upiši u bazu")
        parser.add_argument("--dry-run", action="store_true", help="Samo prikaži što bi se upisalo")
        parser.add_argument("--update", action="store_true", help="Ažuriraj postojeće (po titulu)")

    def handle(self, *args, **options):
        from ai_assistant.models import KnowledgeArticle

        if not options["run"] and not options["dry_run"]:
            self.stdout.write("Koristi --dry-run za pregled ili --run za upis.")
            return

        created = updated = skipped = 0

        for art in ARTICLES:
            title = art["title"]
            exists = KnowledgeArticle.objects.filter(title=title).first()

            if options["dry_run"]:
                status = "UPDATE" if (exists and options["update"]) else ("SKIP" if exists else "CREATE")
                self.stdout.write(f"  [{status}] [{art['module']}] {title}")
                continue

            if exists and not options["update"]:
                skipped += 1
                continue

            with transaction.atomic():
                obj, created_now = KnowledgeArticle.objects.update_or_create(
                    title=title,
                    defaults={
                        "module": art["module"],
                        "content": art["content"],
                        "keywords": art["keywords"],
                        "priority": art["priority"],
                        "is_active": True,
                    },
                )
                if created_now:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"  CREATED [{art['module']}] {title}"))
                else:
                    updated += 1
                    self.stdout.write(f"  UPDATED [{art['module']}] {title}")

        if options["run"]:
            self.stdout.write(
                self.style.SUCCESS(f"\nGotovo: {created} kreirano, {updated} ažurirano, {skipped} preskočeno.")
            )
            total = KnowledgeArticle.objects.filter(is_active=True).count()
            self.stdout.write(f"Ukupno aktivnih KnowledgeArticle: {total}")
