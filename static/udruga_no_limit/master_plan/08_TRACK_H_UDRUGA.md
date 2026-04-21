# TRAK H — UDRUGA REGISTRACIJA

**Vlasnik**: Ivan Brtan (offline) + ljudi (Marija, Ivica, Antonio)
**File područje**: papirologija, scan dokumenata
**NE diraj**: kod (apsolutno ništa)

---

## CILJ

Udruga upisana u Registar udruga RH. OIB dodijeljen. TR otvoren. Pečat izrađen.

---

## TRENUTNO STANJE (21.04.2026.)

✅ **Završeno**:
- Statut v5 (41 članak) generiran kao PDF
- Zapisnik osnivačke skupštine generiran (datum 19.04.2026.)
- Odluka o osnivanju
- Odluka o pokretanju upisa
- Odluka o zastupanju
- Odluka o vizualnom identitetu
- Odluka o Programu DOM
- Pratno obrazloženje
- Suglasnost Ivice Kruljca o korištenju adrese (Kralja Tomislava 291, Vladislavci)
- 3 loga + EVE jaje varijante

⏳ **Nedostaje za predaju**:
- **Marijin OIB i adresa** (čekamo sliku osobne)
- Marija slika osobne za Popis osnivača
- Ivica slika osobne (potvrda OIB-a 82540277049)
- Foto-kopije osobnih iskaznica svih 4 osnivača

---

## SPRINT 1 — Marijini podaci (T1, ovaj tjedan)

### Akcija H1.1 — Marija šalje sliku osobne

Ivan ili Marija — slika prednje + stražnje strane na WhatsApp.

### Akcija H1.2 — Regeneracija dokumenata

Tarn agent (Sonnet) regenerira:
- `NOLIMIT_Popis_osnivaca.pdf` s Marijinim OIB-om i adresom
- `NOLIMIT_Zapisnik_osnivacke_skupstine.pdf` (popunjeni placeholderi)
- `NOLIMIT_Odluka_o_osnivanju.pdf`
- `NOLIMIT_Odluka_o_zastupanju.pdf`

Sve novim SHA-256 pečatom u POE.

### Akcija H1.3 — Marija ovjeri ono što treba

Ako Pravilnik traži ovjeru potpisa kod javnog bilježnika, Marija + Ivica zajedno odu (ili pojedinačno).

---

## SPRINT 2 — Predaja u Upravni odjel (T1–T2)

### Akcija H2.1 — Print svih dokumenata

Ured za sve 4 osnivača:
- Statut (3× kopija)
- Zapisnik (1× original + 2 kopije)
- 6 Odluka
- Popis osnivača
- Pratno obrazloženje
- Suglasnost vlasnika
- Foto-kopije osobnih iskaznica

### Akcija H2.2 — Predaja u Osijek

**Adresa**: Upravni odjel za opću upravu Osječko-baranjske županije, Osijek
**Tko ide**: Ivan Brtan (Predsjednik) sam ili s Marijom
**Trošak**: 0 EUR (registracija udruge je besplatna)

### Akcija H2.3 — Čekanje (do 30 dana)

Upravni odjel obrađuje. Ako sve OK → upis u Registar + dodjela registracijskog broja.

---

## SPRINT 3 — OIB + TR + Pečat (T3–T4)

### Akcija H3.1 — Zatraži OIB Udruge

Po upisu u Registar → Porezna uprava izdaje OIB.
**Rok**: 8 dana od upisa.

### Akcija H3.2 — Otvaranje TR

Banka po izboru (preporuka: PBZ ili Erste, naviše neprofit-friendly).
**Trebaju**: rješenje o upisu, OIB, Statut, osobna iskaznica zastupnika.

### Akcija H3.3 — Otvaranje **drugog** TR za Program DOM

Sukladno Statutu čl. 29 — odvojen TR za humanitarni program.

### Akcija H3.4 — Izrada pečata

Privremeni pečat → sukladno Odluci o vizualnom identitetu, do 90 dana finalni.
**Trošak**: ~30 EUR.
**Tko**: trgovina pečata u Osijeku.

---

## SPRINT 4 — Prva redovna Skupština (T8 — 60 dana nakon upisa)

### Akcija H4.1 — Pripremiti dnevni red

- Ratifikacija Pravilnika o prijateljstvu
- Ratifikacija Sponsor Agreement-a s Konjik d.o.o.
- Usvajanje godišnjeg programa rada
- Usvajanje godišnjeg financijskog plana
- Imenovanje računovodstvenog servisa

### Akcija H4.2 — Saziv Skupštine

15 dana unaprijed, pisani poziv svim 4 članovima.

### Akcija H4.3 — Zapisnik + Objava odluka

- Sve odluke u POE log
- Javno na `https://no-limit.world/skupstina/2026-06/`

---

## SLJEDEĆA AKCIJA

→ **H1.1**: Ivan, šalji sliku Marijine osobne na WhatsApp.

## ZADNJA IZMJENA

| Datum | Tko | Što | Sljedeći korak |
|---|---|---|---|
| 21.04.2026. | Opus design | Plan napisan | Marija šalje sliku osobne |

## DEPENDENCIES

- **Čeka**: Marijina slika OI (blokira sve dalje)
- **Blokira**: E (Marketing — bez upisa nema legitimacije za sastanke), F (Pilot — pilot s bilježnikom traži upisanu Udrugu)

## VAŽNO

**Bez Udruge upisane**, NO LIMIT je samo Konjikov projekt. **S Udrugom upisanom**, dobivamo:
- Pravnu osobnost
- Mogućnost EU fondova
- Trust Anchor legitimaciju
- ChainBlock POE povjerenje
- OPP javni registar autoritet
