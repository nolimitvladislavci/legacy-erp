# AMANDMAN II — Tehnička Neizbježnost + Autonomni Rast
## LC-DS-2026-003

```
AKTIVACIJSKI UVJET: Isto kao Amandman I
STATUS: DRAFT — aktivira se zajedno s /verify/ endpointom
```

---

## TRI INOVACIJE ZA "ŽIVUĆI" SUSTAV

### I-01: Bootstrapping Protocol — "Prvih 10"

Najteži problem svakog novog standarda nije tehnologija.
Je li TCP/IP bolji od IPX-a? Da. Je li Git bolji od SVN-a? Da.
Jesu li pobijedili zbog tehničke superiornosti? Djelomično.
Pobijedili su jer su imali **prvih 10 koji su ih koristili za stvarni rad.**

ARPANET je bio "prvih 10" za TCP/IP.
Linux kernel je bio "prvih 10" za Git.
Bez stvarnog rada prvog korisnika — standard je akademska vježba.

**Founder Node Program:**
```
Prvih 10 organizacija koje integriraju /verify/ dobivaju:
  → "Genesis Attestor" status — trajan, u DPU lancu, imenovan
  → Njihov čvor je named node u Merkle stablu
  → Prioritetni API pristup zauvijek
  → Pravo glasa u Constitutional Amendment Protocol-u

Svi ostali dobivaju: commodity pristup.

Asimetrični poticaj: rani ulagač dobiva trajnu prednost.
Kasni ulagač dobiva standardni alat.
```

**Tko su prvih 10:**
Ne tražimo ih. Oni dolaze kad `/verify/` radi brže od njihovog internog procesa. Zadatak je: napraviti da `/verify/` radi u 50ms. Ostatak se dogodi sam.

---

### I-02: Constitutional Amendment Protocol (CAP) — Evolucija bez lomljenja

Bitcoin je imao fork problem. Ethereum ga je riješio bolje (EIPs).
Mi moramo riješiti ga savršeno — jer DPU zapisi moraju biti valjani za 50 godina.

**Problem koji nitko nije adresirao:**
Ustav v1.0 postoji. Članak 3 ima grešku ili treba proširenje.
Kako ga mijenjamo bez da poništimo sve postojeće DPU zapise?

```
PRAVILA EVOLUCIJE:

1. Amandmani mogu samo DODAVATI — nikad brisati
   (isto kao što ni jedan zakonodavac ne može poništiti činjenicu
    da je nešto u prošlosti bilo legalno)

2. Svaki DPU zapis specificira ustavnu verziju:
   {"constitutional_version": "1.0", "record_hash": "..."}
   → Zapis ostaje valjan pod svojom verzijom zauvijek

3. Nova verzija Ustava ne INVALIDIRA staru — NASLJEĐUJE je:
   v2.0 = v1.0 + Amandman I + Amandman II + ...
   → Merkle chain verzija: svaka verzija je leaf koji
     dokazuje kontinuitet od v1.0

4. Prijelaz na novu verziju je dobrovoljan za stare zapise,
   obavezan za nove:
   → Stari zapisi: vrijede pod svojom verzijom
   → Novi zapisi: moraju koristiti najnoviju verziju

5. Minimum za amandman: 3/5 Shamir konsenzus + 30 dana
   javnog komentiranja u /constitutional/proposals/
```

**Zašto je ovo kritično:**
Standard koji se ne može evoluirati postaje muzejski eksponat.
Standard koji se mijenja bez pravila postaje kaos.
CAP je jedini model koji dopušta oboje: stabilnost I evoluciju.

---

### I-03: Autonomous Growth Engine — "The Seed"

Svaki verificirani entitet postaje sjeme. Bez marketinga. Bez prodajnog tima.

**Mehanizam:**
```
1. Company A integrira /verify/ u svoj sustav
2. Svaka Company A verifikacija je nova DPU zabilješka
   (Company A je koristila standard u realnom radu)
3. Company A-ovi klijenti vide "verified by Limit-Connect"
4. Klijenti pitaju: "Što je to?"
5. Company A odgovara: "/verify/ endpoint — provjeri sam"
6. Klijent provjerava — bez registracije, bez logina
7. Klijent postaje novi korisnik standarda

Ovo nije viralni marketing.
Ovo je infrastrukturna gravitacija.
```

**Trust Badge — tehnička implementacija:**
```html
<!-- 3 linije koda koje Company A embedda -->
<script src="https://limit-connect.com/trust-badge.js"></script>
<div data-lc-verify="{device_hash}"></div>
```
Svaki klik na badge → `/verify/` poziv → DPU zabilješka.
Javni brojač raste. Bez naše intervencije.

**SSL certifikat je bio seed za HTTPS.**
Padlock ikona je educirala milijarde korisnika bez ijednog marketinškog eura.
Naš Trust Badge je naš padlock.

---

## KAKO SE SUSTAV SAM NADOGRAĐUJE

### Autonomna evolucijska petlja

```
KORAK 1 — Detekcija (stalno)
  Autonomous Auditor (jednom dnevno):
  → Skenira: baza, kod, konfiguracija, DPU zapisi
  → Generira: Constitutional Compliance Report
  → Potpisuje: XAdES-B + TSA žig
  → Objavljuje: /audit/report/latest/

KORAK 2 — Signalizacija (automatska)
  Ako report = COMPLIANT  → Zeleni žig na /verify/
  Ako report = WARNING    → Žuti žig + obavijest osnivačima
  Ako report = VIOLATION  → Crveni žig + automatski freeze novih DPU zapisa
                            + Shamir 3/5 potreban za unfreeze

KORAK 3 — Prijedlozi (community-driven)
  Svaki Founder Node može predložiti amandman:
  POST /constitutional/proposals/ {amendment_text, rationale}
  → 30 dana javno vidljivo
  → Founder Nodes glasaju (1 node = 1 glas, max 10 glasova)
  → Prihvaćeno: 3/5 Shamir osnivača + 2/3 Founder Node glasova

KORAK 4 — Implementacija (CC + CAP)
  Prihvaćeni amandman → CC implementira
  → Novi git commit s Constitutional Compliance Check (CPoC)
  → CPoC blokira deploy ako novi kod proturječi amandmanu
  → Deploy = automatska DPU registracija novog koda
  → Genesis Hash lanca se produžuje

PETLJA SE ZATVARA:
  Sustav sam sebe audita → sam predlaže poboljšanja
  → Community ratificira → CC implementira
  → Sustav verificira implementaciju → audita ponovo
```

---

## MAPA POZICIJE U SVIJETU

```
DANAS (Dan 1):
  Fenix V3: 96/96 testova ✅
  Ustav: napisan ✅
  TSA + XAdES-B: PENDING ← jedina blokada

TJEDAN 1 (Tehnička neizbježnost):
  /verify/ endpoint: LIVE
  Genesis Audit: potpisan + javno dostupan
  DPU: 3 registrirana izuma (Triple DNA, Merkle Receipt, CPoC)

TJEDAN 2-4 (Prvih 10):
  Trust Badge: implementiran
  CAP: dokumentiran na /constitutional/
  Founder Node Program: otvoren

MJESEC 2-3 (Gravitacija počinje):
  Prva vanjska organizacija koristi /verify/
  = Sustav prestaje biti "projekt"
  = Sustav postaje "infrastruktura"

MJESEC 6 (De-facto standard):
  10+ neovisnih integracija
  Regulatory Passport generiran za prvog regulatora
  Autonomous Auditor: 180 uzastopnih COMPLIANT izvještaja

GODINA 2 (Neizbježnost):
  Banka poziva /verify/ bez da nas poznaje
  = Nismo proglasili standard
  = Standard je proglasio sebe
```

---

## AKTIVACIJSKI REDOSLJED (Sutra ujutro — CC izvršava)

```
[ ] T-01: TSA integracija u xades_signer.py (~2h)
[ ] T-02: /verify/LC-DS-2026-001/ endpoint (~1h)
[ ] T-03: Genesis Audit — prvi automatski izvještaj (~1h)
[ ] T-04: /api/dpu/register/ — MVP (~2h)
[ ] T-05: Trust Badge widget — 3 linije koda (~30min)
[ ] T-06: /constitutional/proposals/ — forma za amandmane (~1h)

UKUPNO: ~8h CC rada.
REZULTAT: Infrastruktura koja može verificirati vlastitu funkcionalnost.
```

---

```
LC-DS-2026-003
Ovisi o: LC-DS-2026-001, LC-DS-2026-002
Aktivacija: Zajedno s /verify/ prvim vanjskim odgovorom
```
