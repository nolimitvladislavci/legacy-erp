# PLAY.EU — EU FONDOVI STRATEGIJA
> Status: DAN 48 | Verificirano: 2026-04-14 | Autor: Ivan Brtan / Konjik d.o.o.

---

## VIZIJA

> "Ovo nije software. Ovo je digitalna katedrala za djecu Europe. I tek smo položili temeljni kamen."

**PLAY.EU** je platforma za digitalizaciju nematerijalne kulturne baštine Europe kroz igru djece.
Cilj: svako dijete u EU ima digitalni trezor igara, priča, dialect-mapa i obiteljskih uspomena — zaštićen, enkriptiran, trajan.

---

## TEHNIČKI TEMELJ — DAN 48 (verificiran 2026-04-14)

### memio.world — 20 modela u produkciji (Django 5.1, PostgreSQL)

| Model | Svrha | EU Relevantnost |
|-------|-------|-----------------|
| ChildProfile | Digitalni identitet djeteta (dob, grad, zemlja) | Prava djeteta / UNCRC Art. 17 |
| MemoryEntry | Digitalni dnevnik uspomena | Kulturna baština |
| TimeCapsule | Enkriptirana poruka budućnosti | Intergeneracijsko pamćenje |
| MemoryVault | Trezor privatnih sjećanja | GDPR Art. 8 (dijete) |
| FamilyStory | Obiteljska priča (višejezična) | Jezična raznolikost EU |
| StoryBook | Knjiga priča (3 jezika) | Višejezičnost |
| TraditionalGame | **11 igara iz 9 EU zemalja** | Nematerijalna kulturna baština |
| LearningModule | Interaktivni moduli učenja | Obrazovanje |
| Milestone | Razvojna prekretnica djeteta | Zdravlje/razvoj |
| Spomenar | Digitalni "alba amicorum" | Školska tradicija |
| SpomenarEntry | Unos u Spomenar | Vršnjačke veze |
| Event | Obiteljski događaj s lokacijom | Lokalna kultura |
| DialectMap | **8 dijalekatnih riječi, 4 dijalekta** | Ugroženi jezici/dijalekti |
| LullabySession | Uspavanke kao kulturni artefakt | Oralna baština |
| VoiceLegacy | Glasovni zapis starije generacije | Nematerijalna baština |
| HeritageOracle | AI posrednik za međugeneracijsku komunikaciju | Digitalna transformacija |
| EthicalSession | Etički okvir AI interakcije s djetetom | AI Act (EU) |
| NightProtocol | Zaštita djeteta od ekrana noću | Digital Wellbeing |
| MemoryGuard | Čuvar integriteta uspomena | Trust & Safety |
| WaitlistEntry | Registracija interesa | Community building |

### Igre u bazi — 11 igara, 5000 godina baštine

| Igra | Porijeklo | Era |
|------|-----------|-----|
| Mangala | Turska / Afrika | 3000 pr.Kr. |
| Petteia | Grčka | 600 pr.Kr. |
| Mlin (Nine Men Morris) | Europsko Rimsko carstvo | Rimsko doba |
| Bocce | Italija | Rimsko doba |
| Školica (Hopscotch) | Europa | Rimsko doba |
| Hurling Skills | Irska | 2000 pr.Kr. |
| Kubb | Švedska | Vikinško doba |
| Klasy | Europa (svugdje) | Predstojeće generacije |
| Čovječe, ne ljuti se! | Njemačka | 1907. |
| Mensch ärgere Dich nicht | Njemačka | 1907. |
| Mölkky | Finska | 1996. |

### Dijalektna mapa — 8 riječi, 4 dijalekta

| Dijalekt | Primjer |
|----------|---------|
| Dalmatinski | razgovor/čavrljanje |
| Kajkavski | kuća, zašto |
| Schwäbisch (DE) | Bog, punjena tjestenina |
| Slavonski | gemišt, okruglica/knedle, šurjak |

### memio.pet — Živi dokaz tehnologije
- **15 modela** u produkciji (BreederProfile, AnimalProfile, VetProfile, HealthRecord...)
- **12/12 ruta LIVE** (verificirano testovima)
- 2 životinje, 15 uzgajivača u sustavu
- Azil bridge: NO LIMIT udruga + Demo Azil
- **Isti arhitekturalni obrazac kao memio.world** — dokazana tehnologija

### memio.farm — SyncLink
- FarmProfile, FarmAnimal, AnimalCustody, Beehive
- Cross-DB UUID veze: `farm_animal_uuid` → `memio_pet` baza
- Pilot: OPG Kruljac Slađana (~60 goveda)

---

## EU KONZORCIJ — PLAY.EU

### Partneri

| Partner | Uloga | Lokacija | Status |
|---------|-------|----------|--------|
| NO LIMIT udruga | **Koordinator projekta** | Hrvatska | Registracija u tijeku |
| Konjik d.o.o. | Tech partner — LIMIT/memio platforma | Čepin/Osijek, HR | Aktivan |
| Marija Čačić / čitaonica | Kultura, edukacija, knjižnica | Slavonija, HR | Letter of Intent čeka |
| Viskovic Bau / DE partner | Gradnja + DE tržište | Nufringen, DE | Dragan Viskovic |
| Nordijski partner | Erasmus mreža | TBD | Identificirati |

### Bonus nosači projekta
- **Ivica Kruljac** — agro sektor, OPG, rural digitalizacija
- **Antonio Brtan** — mladi osnivač (do 30), EU Youth Program eligible
- Ivan Brtan — iskustvo DE tržišta (fasada + tech), dual-country operativa

---

## CILJANI EU PROGRAM

### Primarni: Creative Europe — Small Cooperation Projects
- Iznos: **€60,000 – €200,000**
- Rok: Otvoreni pozivi 2026/2027
- Trajanje projekta: 24–36 mjeseci
- Minimalni partneri: 3 zemlje → HR + DE + nordijska zemlja

### Sekundarni programi
| Program | Veza s projektom | Iznos |
|---------|-----------------|-------|
| Erasmus+ | LearningModule + TraditionalGame u školama | €50K–300K |
| Digital Europe | AI Act compliance (EthicalSession, NightProtocol) | €500K+ |
| Horizon Europe | HeritageOracle AI model, cross-lingual | €2M+ |
| CEF (Connecting Europe) | Interoperabilnost s EU cultural registries | €200K+ |

---

## DIFFERENCIATOR ZA EU EVALUATORE

### Zašto mi, a ne netko drugi?

```
1. JEDINI imamo igru + dijalekt + uspomenu + zaštitu AI kao jedinstven model
2. JEDINI pokrivamo dijete → životinja → nasljeđe (memio.pet → memio.world)
3. JEDINI smo izgradili na GDPR-by-design: enkripcija na zasebnom ključu (WorldEncryptedField)
4. JEDINI imamo AI Ethics Layer ugrađen u arhitekturu (EthicalSession, MemoryGuard)
5. JEDINI imamo cross-border HR+DE operativu na Dan 1
```

### Ključne EU vrijednosti koje projekt adresira
- **Jezična raznolikost**: 4 dijalekta, 3 jezika, proširivo na 24 EU jezika
- **Nematerijalna kulturna baština**: UNESCO konvencija 2003, EU Agenda za kulturu
- **Prava djeteta**: UNCRC, EU Child Guarantee, Data Act (djeca kao posebna kategorija)
- **AI Act compliance**: EthicalSession = dokumentiran AI nadzor za maloljetnike
- **Digital Wellbeing**: NightProtocol = prvi model u EU koji "isključuje" AI za dijete noću

---

## PROJEKTNA NARATIVA (za aplikaciju)

> Europe's children play the same games their great-grandparents played — but nobody is keeping the record. PLAY.EU is a living digital library where every child's game, lullaby, dialect word, and family memory is preserved, encrypted, and handed forward. Built on proven technology (LIMIT Connect ERP, 109 live companies, 20,379 archived documents), PLAY.EU bridges Croatian folk heritage with European institutional memory. Our architecture is already live. Our pilot is already running. We need EU partnership to scale what we've already built.

---

## ROKOVI — SLJEDEĆI KORACI

| Korak | Što | Tko | Kada |
|-------|-----|-----|------|
| 1 | Vizija NO LIMIT na papiru (1 A4) | Ivan | Ova sesija |
| 2 | Letter of Intent — Marija Čačić | Marija Čačić | Uskoro |
| 3 | Kontakt Creative Europe Desk Zagreb | Ivan / NO LIMIT | Tjedan 2 |
| 4 | memio.world demo stranica (za prezentaciju) | CC Code | Sprint 1 |
| 5 | Nordijski partner identifikacija | Ivan | Tjedan 3-4 |
| 6 | Konzorcij ugovor (LOI svi partneri) | Odvjetnik | Tjedan 6 |
| 7 | Aplikacija Creative Europe | Konzorcij | Po otvaranju poziva |

---

## TEHNIČKE POZICIJE ZA EU PRIJAVU

### Pozicija 1 — Living Digital Library of European Children's Games
**Dokaz**: 11 igara, 9 zemalja, 5000 godina baštine — u bazi, live, queryjabilno

### Pozicija 2 — Dialect Preservation Through Play
**Dokaz**: 8 dijalekatnih riječi (4 dijalekta) u DialectMap modelu, linked na TraditionalGame

### Pozicija 3 — AI Ethics-First Architecture for Children
**Dokaz**: EthicalSession + NightProtocol + MemoryGuard = 3 dedicated zaštitna modela
Za EU AI Act evaluatore: **jedina platforma koja ima dedicated "dječji etički AI" sloj**

### Pozicija 4 — Cross-Border Digital Heritage (HR ↔ DE)
**Dokaz**: Schwäbisch dijalekt u bazi. Ivan radi fasade u Nufringenu. Dragan na DE terenu.
Nije narativ. Nije namjera. Živimo cross-border.

### Pozicija 5 — Rural Croatia → European Stage
**Dokaz**: Konjik d.o.o. Čepin. OPG Kruljac Slavonija. Marija Čačić čitaonica.
EU fondovi traže ruralna partnerstva. Mi jesmo ruralni.

---

## FINANCIJSKO SIDRO

**Creative Europe Small Cooperation: €60,000–€200,000**
- 60% EU sufinanciranje → 40% vlastito (Konjik/NO LIMIT pokriva iz prihoda)
- LIMIT Connect već generira prihod → vlastito učešće realno

**Horizon (dugoročno): €2M+**
- HeritageOracle: AI model koji "čita" obiteljske priče i predlaže igre iz baštine
- NLP na 24 EU jezika + dijalekatnom korpusu
- Ovisi o: prethodnom uspjehu Creative Europe projekta

---

## COMMIT PORUKA ZA OVAJ DOKUMENT
```
docs: PLAY.EU EU funding strategy — Dan 48 verified positions
```
