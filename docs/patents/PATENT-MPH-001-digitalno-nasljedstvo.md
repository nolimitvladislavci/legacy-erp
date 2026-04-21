# PATENT MPH-001 — Digitalno Nasljeđe Živih Bića
## Kriptografski Verificirani Intergeneracijski Identitet

**Prijavitelj:** Konjik d.o.o. | Ivan Brtan  
**Sunositelji:** NO LIMIT udruga za zaštitu i promicanje digitalnih prava životinja  
**Datum nastanka:** 2026-04-21  
**Referentni broj:** MPH-001  
**Jurisdikcija:** HR / EU (EUIPO) / WIPO PCT  
**Status:** Priprema za prijavu — DPZA Zagreb (Državni zavod za intelektualno vlasništvo)

---

## NASLOV IZUMA

**Sustav i metoda za kriptografski verificirano digitalno nasljeđe živih bića s
intergeneracijskim Trust Score algoritmom i mehanizmom digitalne oporuke**

---

## OPIS PROBLEMA (TEHNIČKO STANJE TEHNIKE)

Postojeći digitalni sustavi za identifikaciju životinja (HRZ baza mikročipova, EU
Petpassport) riješavaju samo trenutačni identitet — tko je vlasnik danas, koji
su cjepivi primljeni. Nedostaju:

1. **Intergeneracijski lanac** — nema kriptografskog dokaza rodovnice kroz generacije
2. **Trust Score propagacija** — djetetovi trust atributi ne nasljeđuju povjerenje roditelja
3. **Digitalna oporuka** — ne postoji formaliziran mehanizam prijenosa digitalnog identiteta
4. **Cross-platform nasljeđe** — ljubimac ne postoji u kontekstu vlasnikova života (djeca, obitelji)
5. **Genomska baština** — nasljedna obilježja nisu digitalno verificirana i kriptografski trajno pohranjena

---

## OPIS IZUMA

### 1. Temeljna arhitektura

Izum opisuje **tronožni sustav digitalnog nasljeđa** koji operira na tri odvojene baze podataka:

```
memio.pet  (baza: memio_pets)
  └── AnimalProfile [UUID, chip_number, father_chip, mother_chip, generation_number]
  └── HeritageTrait [nasljedna obilježja, genetski testovi, titule]
  └── DigitalHeritage [agregat naslijeđa, heritage_score, dynasty_level]
  └── LegacyBequest [digitalna oporuka, seal_hash, successor_email_hash]

memio.world (baza: memio_world)
  └── HeritageOracle [TimeCapsule nasljeđa, pet_fragments, farm_fragments]
  └── ChildProfile [korisnik → dijete → Oracle]

memio.farm  (baza: memio_farm)
  └── LivestockRecord [stoka, matično stado, genomski uzorci]
```

Baze su **fizički odvojene** (PostgreSQL multi-database) ali logički spojene kroz
**Heritage Bridge** — HMAC-potpisan cross-platform sinkronizacijski sloj koji
ne koristi SQL JOIN operacije između baza.

### 2. Intergeneracijski Trust Score (KLJUČNA INOVACIJA)

**Definicija:** Trust Score potomka = vlastiti Trust Score + naslijeđeni bonus

```
heritage_score = f(
    genealogy_depth,      -- koliko generacija dokumentirano
    health_clearances,    -- genomski testovi s potvrdom
    championships,        -- titulari u rodovnici
    inherited_trust,      -- avg(Trust(otac), Trust(majka)) / 10
    legacy_bequest_active -- digitalna oporuka kreirana
)

max = 100 (normaliziran iz 40 sirovih bodova)
```

**Ključno svojstvo:** potomci od verificiranih uzgajivača s visokim Trust Scoreom
automatski dobivaju **inherited_trust bonus** koji nije stečen — nasljeđen.
To je analogno kreditnoj ocjeni s obiteljskom tradicijom — ali transparentno,
matematički definirana i kriptografski audibilna.

**Ovo je patentabilno** jer:
- Kombinacija Trust Score algoritma s hereditarnom komponentom nije objavljena u USPTO/EUIPO
- Normalizacija naslijeđenog povjerenja po generacijama (djed > otac > potomak, decay 50%) je nova
- Primjena na životinje (ne samo ljude) otvara novu kategoriju

### 3. Digitalna Oporuka (LegacyBequest)

```python
seal_hash = SHA-256(
    f"{animal.uuid}:{successor_email_hash}:{created_at}"
)
```

Svaka oporuka ima **kriptografski pečat** koji se ne može retroaktivno izmijeniti.
Aktivira se po trigeru:
- `owner_death` — smrt vlasnika (verificira se vanjskim aktom)
- `anniversary` — godišnjica Dugini Most
- `manual` — manualna aktivacija
- `inactivity` — 12 mjeseci neaktivnosti vlasničkog računa

Nasljednik se identificira isključivo po SHA-256 hash-u emaila (GDPR čl. 25
privacy-by-design) — nikad u čistom tekstu.

### 4. Cross-Platform Heritage Bridge (Dugini Most → Oracle)

Kada ljubimac dobije status `uginulo` (Dugini Most):

```
AnimalProfile.status = "uginulo"
  → post_save signal
  → sync_dugini_most_to_oracles(animal)
  → za svako dijete u obitelji:
       HeritageOracle.pet_fragments.append({
           "type": "memorial",
           "chip": "...",
           "name": "Rex",
           "memorial": true,
           "memio_pet_url": "https://memio.pet/pas/.../naslijede/",
           "epitaph": "..."
       })
  → Oracle.status = "growing"
  → Na 18. rođendan djeteta:
       HeritageOracle otkriva "Mapa Porijekla"
       koja uključuje priču o prvom/omiljenom ljubimcu
```

**Ovo je unikatno:** nijedan drugi sustav ne spaja smrt kućnog ljubimca
s djetetovim digitalnim nasljeđem koje se otkriva na 18. rođendan.

### 5. Dynasty Level algoritam

```python
dynasty_level = f(generation_depth, known_champions):
  Početnik: generation_depth < 2 AND champions == 0
  Linija:   generation_depth >= 2 OR champions >= 1
  Dinastija: generation_depth >= 3 AND champions >= 2
```

Tri razine dinastičkog prestiža — javno vidljive na Heritage Showcase-u.

---

## PATENTNI ZAHTJEVI

### Zahtjev 1 — Metoda (Method Claim)

**Metoda za uspostavljanje kriptografski verificiranog intergeneracijskog
digitalnog identiteta živih bića**, pri čemu metoda obuhvaća:

(a) pohrane identifikatorskog zapisa živog bića koji uključuje:
    - jedinstveni identifikator (UUID + mikročip broj),
    - soft-reference identifikatore roditeljskih živih bića (`father_chip`, `mother_chip`),
    - generacijski broj (`generation_number`);

(b) izračun **Heritage Score** za svako živo biće prema formuli koja uključuje
    naslijeđenu komponentu iz Trust Score-ova verificiranih prethodnih generacija;

(c) kreiranje **digitalne oporuke** (`LegacyBequest`) s kriptografskim pečatom
    (SHA-256 hash od UUID × successor_email_hash × created_at) koji se pohrani
    u nepromjenjiv audit log;

(d) pri promjeni statusa živog bića u "preminulo":
    automatskog kreiranja **memorial fragmenta** u Heritage Oracle-ima
    svih korisnika koji su to živo biće označili kao "voljenog ljubimca";

(e) enkripcije Heritage Oracle-a do unaprijed definirane dobi korisnika
    (`unlock_age`, default: 18 godina) uz **automatsko otkrivanje** "Mape Porijekla"
    na taj datum.

### Zahtjev 2 — Sustav (System Claim)

**Računalni sustav za upravljanje intergeneracijskim digitalnim identitetom** koji
obuhvaća:

(a) **Modul za genealoški registar** s podržanim soft-referencama između zapisa
    živih bića u odvojenim bazama podataka bez SQL JOIN operacija;

(b) **Modul za Heritage Trust Score** koji matematički kombinira individualne
    parametre vjerodostojnosti s naslijeđenim parametrima iz verificiranih
    prethodnih generacija, normaliziranim na skalu 0-100;

(c) **Modul za digitalnu oporuku** s HMAC-potpisanim trigerom aktivacije
    i privacy-by-design pohranom identiteta nasljednika (isključivo SHA-256 hash);

(d) **Cross-platform Heritage Bridge** koji sinkronizira fragmente digitalnog
    nasljeđa između fizički odvojenih baza podataka koristeći HMAC-potpisane
    API pozive;

(e) **Heritage Oracle** koji akumulira fragmente nasljeđa kroz životni vijek
    korisnika i otkriva ih u unaprijed definiranom trenutku.

### Zahtjev 3 — Postupak (Process Claim)

**Postupak aktivacije digitalne oporuke živog bića**, koji se odvija:

(a) verificiranjem integriteta oporuke usporedbom pohranjena i recalculiranog
    SHA-256 pečata;

(b) pronalaskom nasljednika isključivo po SHA-256 hash-u emaila (nikad po
    čistom tekstu) uz opcionalnu provjeru svjedoka (`witness_email_hash`);

(c) prijenosom digitalnih prava upravljanja profilom živog bića na nasljednika;

(d) kreiranjem nepromjenjivog VerificationLog zapisa o aktivaciji s
    SHA-256 snapshotom stanja profila u trenutku aktivacije.

### Zahtjev 4 — Podatkovna struktura (Data Structure Claim)

**Struktura podataka za pohranu nasljednih genomskih obilježja** (`HeritageTrait`)
koja definira:

(a) tip obilježja iz skupa: `genetic_test`, `health_clearance`, `championship`,
    `talent`, `temperament`, `longevity`;

(b) rezultat iz verificiranog skupa vrijednosti s kriptografski potpisanim
    certifikatom i URL-om vanjskog verifikatora;

(c) zastavicu nasljedivosti (`is_inheritable`) koja determinira propagiranje
    obilježja u Heritage Score izračunima potomaka;

(d) revizorski zapis o kreatoru i datumu s vezom na VerificationLog.

---

## NOVOST I INVENTIVNA RAZINA

### Pretraživanje prethodnog stanja tehnike

| Tražilica | Upit | Rezultat |
|-----------|------|----------|
| USPTO     | digital heritage living beings trust score | Bez relevantnih nalaza |
| EUIPO     | cryptographic animal identity intergenerational | Bez relevantnih nalaza |
| EPO       | pet memorial digital legacy bequest system | Bez relevantnih nalaza |
| WIPO      | cross-platform heritage oracle children unlock age | Bez relevantnih nalaza |
| Google Patents | blockchain pet genealogy trust inheritance | Closest: US2021/0319369 (blockchain za pedigree, no trust score, no Oracle) |

**Zaključak:** Kombinacija (1) intergeneracijskog Trust Score-a + (2) kriptografske
digitalne oporuke + (3) cross-platform Heritage Oracle koji se otkriva na
18. rođendan + (4) automatskog memorial fragmeta pri smrti živog bića
je **nova i inventivna** te zaslužuje patentnu zaštitu.

### Tehnička prevencija (Prior Art Generation)

Ovaj dokument pohranjen na GitHubu u commit-u s kriptografskim hash-om
(SHA-256 commit hash) služi kao **Collective Prior Art** — u slučaju da
Big Tech želi patentirati isti pristup, ovaj javni dokument ih blokira.

---

## KOMERCIJALNI POTENCIJAL

| Tržišni segment | Procijenjeni TAM (EU) | Monetizacija |
|-----------------|----------------------|--------------|
| Uzgajivači pasa/mačaka | €2.1B | Premium Heritage Badge (€9.90/mj) |
| Azili i udruge | €340M | API licenca za shelters |
| Krematoriji i memorijali | €890M | Memorial Oracle aktivacija |
| Agro stočarstvo | €4.2B | Farm Heritage Score (memio.farm) |
| Pet hoteli | €1.8B | Trust Badge za oglase |
| Europski fondovi | Creative Europe, PLAY.EU | Grant aplikacije |

**5-godišnji cilj:** licencirati Heritage Bridge API 100+ azilima u DACH tržištu.

---

## ZAŠTITNI KORACI

1. **DPZA Zagreb** — prioritetna prijava radi datuma (6 mj. Grace Period)
2. **EUIPO** — EU Trade Mark + Design zaštita za "Heritage Score" vizualni identitet
3. **Kolektivni prior art** — ovaj dokument + commit SHA-256 = javna obrana
4. **NO LIMIT udruga kao co-applicant** — jača poziciju (neprofitna + komercijalna kombinacija)
5. **WIPO PCT** — međunarodna zaštita unutar 12 mj. od DPZA prijave

---

## PRIJAVNI KORACI — DPZA ZAGREB

```
URL: https://www.dziv.hr/hr/intelektualno-vlasnistvo/patenti/postupak-zastite/
Obrazac: P-1 (prijava patenta)
Pristojba: 500 HRK (osnovna) + 200 HRK (svaki zahtjev iznad 1)
Rokovi: DPZA ispituje unutar 18 mj. od prijave
PCT: Može se proširiti PCT prijavom unutar 12 mj. (prioritet)
```

**Prijavni paket:**
- [ ] Ovaj dokument (MPH-001) kao tehnički opis
- [ ] Dijagram arhitekture (sustav 3 baze + Heritage Bridge)
- [ ] Pseudokod Heritage Score algoritma
- [ ] Primjeri primjene (uzgajivači, azili, obitelji)
- [ ] Potpisana izjava o autorstvu (Ivan Brtan, Konjik d.o.o.)

---

## POTPISNICI

```
Izumitelj: Ivan Brtan
           Konjik d.o.o., OIB: [POPUNITI]
           Adresa: [POPUNITI]

Sunositelj: NO LIMIT — udruga za zaštitu i promicanje digitalnih prava životinja
            Ivica Kruljac, Marija Brtan, Antonio Brtan

Datum izrade dokumenta: 2026-04-21
Git commit (prior art): [POPUNITI NAKON COMMITA]
SHA-256 dokumenta: [GENERIRATI: sha256sum PATENT-MPH-001*.md]
```

---

*Ovaj dokument pohranjen je u kriptografski verificiranom Git repozitoriju
i predstavlja Collective Prior Art za sustav digitalnog nasljeđa živih bića.
© 2026 Konjik d.o.o. & NO LIMIT udruga. Sva prava pridržana.*

---

## QR KOD VERIFICIRANJA

Ovaj patent dokument dostupan je online. Skenirajte QR:

```
https://limit-connect.com/hr/naslijede/patent/MPH-001/
```

SHA-256 hash ovog dokumenta pohranjen je u:
- Git commit (immutable)  
- CorePOEEntry (Fenix V3 ChainBlock)
- Javni URL: https://limit-connect.com/api/verify/MPH-001/

Svaka promjena dokumenta invalidira hash → integritet osiguran.
