# LEGAL_PARAMS_MASTER.md
# Zakonski parametri HR + DE (2011–2026+)
# Zabetonirano: 2026-03-27 | Autor: Sonnet (istraživanje + web search)
# OBAVEZNO za sve AI agente, CC Code, Gemini, Haiku
# JEDINA ISTINA o propisima — ažurirati samo uz izvor i datum

---

## PRAVILO KORIŠTENJA

```python
def get_legal_params(date, country='HR') -> dict:
    """
    Uvijek pozivaj s KONKRETNIM datumom dokumenta.
    Nikad ne primjenjuj parametre iz 2026 na dokument iz 2018.
    """
```

**Svaka compliance provjera mora uključiti:**
1. `document_date` — točan datum dokumenta
2. `country` — HR ili DE
3. `is_production` — `synesis_id IS NULL AND year >= 2026`

---

## ═══════════════════════════════════════════════
## HRVATSKA (HR) — KRONOLOŠKI ZAKONSKI OKVIR
## ═══════════════════════════════════════════════

### VALUTA

| Period | Valuta | Napomena |
|--------|--------|----------|
| Pre-01.01.2023. | HRK (kuna) | Zakonsko sredstvo plaćanja |
| 01.01.2023. – 14.01.2023. | HRK + EUR | Dvojni optjecaj (14 dana) |
| 15.01.2023. → | EUR | Jedino zakonsko sredstvo plaćanja |

**Fiksni tečaj konverzije (Uredba Vijeća EU 2022/1208 od 12.07.2022.):**
`1 EUR = 7,53450 HRK` (nepromjenjivo zauvijek)

**Zakon o uvođenju eura: NN 57/22, 88/22**
- Stupio na snagu: 15.07.2022.
- Obvezno dvojno iskazivanje cijena: 05.09.2022. – 31.12.2023.
- HRK faktura pre-2023 = LEGALNA, ne greška
- Iznosi u ugovorima u HRK se automatski tretiraju kao EUR po fiksnom tečaju

```python
# Compliance check za valutu
def check_currency(invoice_date, currency):
    year = invoice_date.year
    if year < 2023:
        if currency == 'HRK':
            return True, None      # Legalno — kuna je bila valuta
        if currency == 'EUR':
            return True, None      # EUR bio moguć u ugovorima
    elif year == 2023:
        return True, None          # Prijelazna godina — oboje OK
    else:  # 2024+
        if currency != 'EUR':
            return False, f'Valuta {currency} nije legalna od 2023 — samo EUR'
    return True, None
```

---

### HR PDV STOPE — KOMPLETNA POVIJEST

**Zakon o PDV-u: NN 73/13 (temeljni, od 01.07.2013.)**
**Izmjene: NN 99/13, 148/13, 153/13, 143/14, 115/16, 106/18, 121/19, 138/20, 39/22, 113/22, 114/23, 152/24**

#### Opća stopa PDV-a

| Period | Opća stopa | NN broj |
|--------|-----------|---------|
| Pre-01.07.2013. | 25% | Stari zakon |
| 01.07.2013. → | **25%** | NN 73/13 |
| 01.01.2020. → | Planirano 24%, **ALI ZADRŽANO 25%** | NN 121/19 — zadržana 25% |
| 2020. → danas | **25%** | Nepromijenjeno |

> **Važno:** Zakon NN 115/16 bio je planirao smanjenje na 24% od 01.01.2020., ali je to NN 121/19 zadržao na 25%.

#### Snižena stopa 13%

| Period | Što se oporezuje stopom 13% | NN |
|--------|---------------------------|-----|
| 01.07.2013. – 31.12.2013. | 10% bila stopa (nije 13!) | NN 73/13 |
| 01.01.2014. → | Stopa povećana s 10% na **13%** | NN 148/13 |
| 2014. → 31.03.2022. | 13%: novine, hotelski smještaj, restoran usluge*, kinoulaznice, kinofilmovi, groblje, pogrebnici, sport ulaznice, sporeni... | NN 115/16 |
| 01.01.2020. → | 13%: Priprema i usluživanje hrane u ugostiteljskim objektima (restorani!) | NN 121/19 |
| 01.04.2022. → | 13%: Restorani **SMANJENO NA 5%** (vidi niže) | NN 39/22 |
| 01.01.2024. → | 13%: OPET povećano na 13% za restorane | NN 114/23 |
| 01.10.2022. → | 13%: Prirodni plin, grijanje, drvo (privremeno) | NN 113/22 |

> **Ključna promjena:** Restorani/ugostiteljstvo:
> - Pre-2020: 25%
> - 01.01.2020 – 31.03.2022: 13% (NN 121/19)
> - 01.04.2022 – 31.12.2023: 5% (NN 39/22, COVID rasterećenje)
> - 01.01.2024 → : **13%** (NN 114/23 — povratak)

#### Snižena stopa 5%

| Period | Što se oporezuje stopom 5% | NN |
|--------|--------------------------|-----|
| 01.07.2013. → | Kruh, mlijeko, knjige, lijekovi, medicinska oprema, kino-ulaznice | NN 73/13 |
| 01.01.2017. → | Proširenje: znanstvene revije i sl. | NN 115/16 |
| 01.04.2022. → | **VELIKA PROMJENA:** Meso, riba, povrće, voće, jaja, ulja, masnoće, dječja hrana, gnojiva, pesticidi, hrana za životinje, sadnice, sjemenje, ulaznice za koncerte/sport/kulturu | NN 39/22 |
| 01.04.2022 – 31.03.2023. | Prirodni plin (privremeno) | NN 39/22 |
| 01.04.2022. → | Restorani/ugostiteljstvo (vidi gore) | NN 39/22 |
| 01.01.2024 – 31.03.2025. | Produljeno: prirodni plin, grijanje, ogrjevno drvo, peleti | NN 35/24 |

#### Stopa 0%

| Period | Što | NN |
|--------|-----|----|
| 01.10.2022. → | Solarne ploče (ugradnja na stambene objekte i javne zgrade) | NN 113/22 |
| 01.01.2023. → | Solarne ploče (prodaja) — TRAJNO | NN 113/22 |

#### PDV prag za registraciju

| Period | Prag (godišnji promet) | Valuta |
|--------|----------------------|--------|
| 2013. – 2022. | 300.000 HRK | HRK |
| 2023. → | **40.000 EUR** (= 301.380 HRK) | EUR |
| (planirano) | **60.000 EUR** | EUR |

> NN 152/24 planira povećanje praga na 60.000 EUR — pratiti!

```python
# HR PDV stopa lookup
HR_PDV_RULES = {
    # Format: (date_from, date_to, category) -> rate
    # Opća stopa
    'standard': [
        ('2013-07-01', None, 25.0),
    ],
    # Ugostiteljstvo/restorani
    'restaurant': [
        ('2013-07-01', '2019-12-31', 25.0),
        ('2020-01-01', '2022-03-31', 13.0),  # NN 121/19
        ('2022-04-01', '2023-12-31', 5.0),   # NN 39/22 COVID rasterećenje
        ('2024-01-01', None,         13.0),  # NN 114/23
    ],
    # Hrana (prehrambeni sektor)
    'food_basic': [
        ('2013-07-01', '2022-03-31', 5.0),   # Kruh, mlijeko
        ('2022-04-01', None,         5.0),   # Prošireno na meso, voće, povrće...
    ],
    'food_processed': [
        ('2013-07-01', '2022-03-31', 25.0),  # Prerađena hrana
        ('2022-04-01', None,         5.0),   # Smanjeno NN 39/22
    ],
    # Plin/grijanje
    'natural_gas': [
        ('2013-07-01', '2022-03-31', 25.0),
        ('2022-04-01', '2023-03-31', 5.0),   # Privremeno NN 39/22
        ('2022-10-01', '2023-03-31', 5.0),   # Grijanje iz toplinskih stanica NN 113/22
        ('2023-04-01', '2025-03-31', 13.0),  # Produljeno na 13% NN 113/22 → NN 35/24
        ('2025-04-01', None,         25.0),  # Natrag na 25%
    ],
    # Solarne ploče
    'solar_panels': [
        ('2022-10-01', None, 0.0),           # Nulta stopa NN 113/22
    ],
    # Sport/kultura/koncerti
    'culture_tickets': [
        ('2013-07-01', '2022-03-31', 13.0),
        ('2022-04-01', None,         5.0),   # NN 39/22
    ],
}
```

---

### HR FISKALIZACIJA — KOMPLETNA POVIJEST

#### Verzija 1.0 — Zakon NN 133/12

| Datum | Event |
|-------|-------|
| 03.12.2012. | Zakon objavljen NN 133/12 |
| 01.01.2013. | Stupanje na snagu — 1. krug obveznika |
| 01.07.2013. | **Svi obveznici** — gotovinski promet |
| 01.01.2013. | ZKI (Zaštitni kod izdavatelja) + JIR (Jedinstveni identifikator računa) |

**Obvezni elementi računa v1.0:**
- OIB obveznika
- Datum i vrijeme
- Broj računa
- PDV status
- Iznos po stopama
- Način plaćanja
- OIB operatera
- ZKI
- JIR (po potvrdi Porezne uprave)

**Tko NE ide na fiskalizaciju (trajno izuzeti):**
- Iznajmljivanje nekretnina fizičkih osoba
- Prodaja na tržnicama
- Djelatnosti u susjednoj pomoći (kućanstvo)
- Prijevoz putnika autobusima na osnovi ugovora s javnim prijevoznikom
- Posredovanje u prodaji karata (kino, kazalište, sport)
- Kladionice (poseban sustav)
- Bankarski poslovi i osiguranje
- Zdravstvene usluge fizičkih osoba

#### Izmjena NN 115/16 — na snazi 01.01.2017. (dio od 01.07.2017.)

- Izmjene u sadržaju računa
- Proširenje obveznika

#### Izmjena NN 106/18

- Tehničke izmjene

#### Izmjena NN 121/19

- Daljnje izmjene

#### Izmjena NN 138/20 — na snazi 01.04.2020. (dio od 01.01.2021.)

| Datum | Što je novo |
|-------|------------|
| 01.04.2020. | **QR kod** postaje obvezni element svakog računa |
| 01.04.2020. | Fiskalizacija pratećih dokumenata (predračuni, otpremnice) — oznaka "OVO NIJE FISKALIZIRANI RAČUN" |
| 01.01.2021. | **Novi elementi** na računu |

#### Izmjena NN 114/23 — na snazi 01.01.2024.

| Datum | Što je novo |
|-------|------------|
| 01.01.2024. | **Napojnice** se fiskaliziraju uz račun |

---

#### Verzija 2.0 (NOVI ZAKON) — NN 89/25

| Datum | Što |
|-------|-----|
| 11.06.2025. | Zakon donesen od Sabora |
| **01.09.2025.** | **Novi Zakon o fiskalizaciji (NN 89/25) stupa na snagu** |
| 01.09.2025. | **Stari zakon NN 133/12 (sve izmjene) PRESTAJE VAŽITI** |
| **01.01.2026.** | **eRačun obveza**: Fiskalizacija bezgotovinskih računa + eRačun B2B |

**Što je novo u NN 89/25:**
- eRačun je definiran zakonom (EU norma EN 16931-1:2017)
- Fiskalizacija se proširuje na bezgotovinske račune (od 01.01.2026.)
- AMS (Adresar metapodatkovnih servisa) — Porezna uprava
- Napojnice proširene (kartice, mobile)
- QR kod zadržan
- Knjiga računa — ovjera putem ePorezna (od 01.01.2026.)
- Z-izvještaji ostaju (zakonska osnova za dnevni promet)

```python
# Fiskalizacija lookup
def get_fiscal_version(date):
    if date < '2013-01-01':
        return None, 'Pre-fiskalizacija — nije obavezno'
    elif date < '2013-07-01':
        return '1.0', 'Fiskalizacija 1.0 (1. krug)'
    elif date < '2020-04-01':
        return '1.0', 'Fiskalizacija 1.0 — ZKI + JIR'
    elif date < '2021-01-01':
        return '1.1', 'Fiskalizacija 1.1 — + QR kod + prateći dokumenti'
    elif date < '2024-01-01':
        return '1.2', 'Fiskalizacija 1.2 — + novi elementi'
    elif date < '2025-09-01':
        return '1.3', 'Fiskalizacija 1.3 — + napojnice'
    elif date < '2026-01-01':
        return '2.0', 'Fiskalizacija 2.0 (NN 89/25) — novi zakon, gotovinski'
    else:
        return '2.0+', 'Fiskalizacija 2.0+ — + bezgotovinski + eRačun'

def requires_zki_jir(date):
    """ZKI/JIR su obavezni za gotovinske račune od 01.01.2013."""
    return date >= '2013-01-01'

def requires_qr(date):
    """QR kod obavezan od 01.04.2020."""
    return date >= '2020-04-01'
```

**COMPLIANCE PRAVILO — Historijski dokumenti:**
- Pre-2013: Nema ZKI/JIR = NORMALNO (nije postojalo)
- 2013–2020 bez QR koda = NORMALNO (QR nije bio obavezan)
- 2020+ bez QR koda = UPOZORENJE
- 2023+ HRK valuta = UPOZORENJE (trebalo bi biti EUR)

---

### HR eRACUN

| Datum | Obveza | Krug |
|-------|--------|------|
| 01.12.2018. | eRačun B2G — centralna tijela državne uprave | B2G (obveza primanja) |
| 01.07.2019. | eRačun B2G — lokalna samouprava | B2G (obveza primanja) |
| 01.12.2020. | eRačun B2G — sve JLP | B2G (puno) |
| 01.07.2023. | eRačun B2G — javna nabava | B2G proširenje |
| **01.01.2026.** | **eRačun B2B — svi porezni obveznici** | **B2B (NN 89/25)** |

**Format: HR eRačun** = UBL 2.1 ili UN/CEFACT CII, usklađen s EN 16931

---

## ═══════════════════════════════════════════════
## NJEMAČKA (DE) — KRONOLOŠKI ZAKONSKI OKVIR  
## ═══════════════════════════════════════════════

### DE MwSt (Mehrwertsteuer / Umsatzsteuer)

**Zakon: UStG (Umsatzsteuergesetz)**
**Relevantni paragraf za stope: §12 UStG**

#### Opća stopa (Regelsteuersatz)

| Period | Stopa | Napomena |
|--------|-------|----------|
| 2007. – 30.06.2020. | **19%** | Stabilna |
| **01.07.2020. – 31.12.2020.** | **16%** | **COVID konjunkturpaket** (130 mrd EUR paket) |
| **01.01.2021. →** | **19%** | Povratak na normalnu stopu |

> **KRITIČNO za compliance:** Dokument s MwSt 16% datiran između 01.07.2020. i 31.12.2020. = LEGALAN. Ne tretirati kao grešku!

#### Snižena stopa (ermäßigter Steuersatz)

| Period | Stopa | Napomena |
|--------|-------|----------|
| 2007. – 30.06.2020. | **7%** | Hrana, knjige, transport... |
| **01.07.2020. – 31.12.2020.** | **5%** | **COVID** smanjenje |
| **01.01.2021. →** | **7%** | Povratak |

#### Gastronomija (Speisen in Restaurants)

| Period | MwSt | Napomena |
|--------|------|----------|
| Pre-2020. | 19% | Standardna stopa za konzumaciju u restoranu |
| 01.07.2020. – 31.12.2020. | 5% | COVID paket |
| 01.01.2021. – 31.12.2023. | **7%** | Produženo rasterećenje za gastronomiju |
| **01.01.2024. →** | **19%** | **Povratak na punu stopu** — nije produženo! |

> Gastronomija "takeln für daheim" (za van) i dalje 7%.

#### Posebni slučajevi

| Period | Što | Stopa |
|--------|-----|-------|
| 01.01.2023. → | Solarne ploče (PV sustavi ≤30 kWp) | **0%** |
| 01.01.2025. → | Kunstgegenstände (umjetnina, kolekcionarski predmeti) | **7%** |
| 01.01.2025. → | Paušalni poljoprivrednici | **7,8%** (bio 9%) |

#### Kleinunternehmer (Mali poduzetnici §19 UStG)

| Period | Godišnji limit (prethodna god.) | Running limit (tekuća god.) |
|--------|-------------------------------|-----------------------------|
| 2019. | 17.500 EUR | 50.000 EUR |
| 01.01.2020. → 31.12.2024. | **22.500 EUR** | 50.000 EUR |
| **01.01.2025. →** | **25.000 EUR** | 100.000 EUR |

> Kleinunternehmer ne naplaćuju MwSt. Na računu MORA pisati: "Kein Ausweis von Umsatzsteuer gemäß §19 UStG".

---

### DE E-RECHNUNG (Elektronische Rechnung)

**Zakon: Wachstumschancengesetz (27.03.2024., BGBl I 2024 Nr. 108)**
**Izmjena §14 UStG**

| Datum | Obveza |
|-------|--------|
| **01.01.2025.** | **EMPFANGSPFLICHT**: Sva poduzeća moraju PRIMATI e-račune. Minimalno: e-mail sandučić. |
| **01.01.2025.** | AUSSTELLUNGSPFLICHT: E-račun može biti poslan (nisu svi moraju) |
| 01.01.2025. – 31.12.2026. | Prijelazno: PDF/papir dozvoljen uz suglasnost primatelja |
| 01.01.2025. – 31.12.2027. | Mala poduzeća (prethodni prihod ≤ 800.000 EUR) — mogu slati PDF/papir |
| **01.01.2028.** | **SVA PODUZEĆA** moraju slati e-račune za interne B2B |

**Izuzeća od AUSSTELLUNGSPFLICHT:**
- Kleinunternehmer (§19 UStG) — ne moraju SLATI, ali moraju PRIMATI
- Kleinbetragsrechnungen (iznos ≤ 250 EUR bruto §33 UStDV)
- Prijevozne karte (§34 UStDV)
- Usluge za nepoduzetnike (B2C)

**Prihvaćeni formati:**
- XRechnung (XML, CEN EN 16931)
- ZUGFeRD ≥ 2.0.1 (PDF/A-3 + XML, hibrid; ne MINIMUM i BASIC-WL profili)
- Factur-X (kompatibilan s EN 16931)
- Vlastiti format ako je interoperabilan s EN 16931

**Arhiviranje: 10 godina (§14b UStG + §147 AO)**

```python
# DE e-Rechnung compliance
def de_erechnung_check(invoice_date, is_b2b, is_kleinunternehmer, amount, prev_year_revenue=None):
    year = invoice_date.year
    
    if year < 2025:
        return False, 'Pre-2025: e-Rechnung nije bila obvezna'
    
    if not is_b2b:
        return False, 'B2C: e-Rechnung nije obvezna'
    
    if amount and amount <= 250:
        return False, 'Kleinbetragsrechnung ≤250 EUR: izuzeto'
    
    # Empfangspflicht (primanje) — svi od 2025
    # Ausstellungspflicht (slanje):
    if is_kleinunternehmer:
        if year < 2028:
            return False, 'Kleinunternehmer: oslobođen od slanja do 2027'
    
    if prev_year_revenue and prev_year_revenue <= 800000:
        if year <= 2027:
            return False, f'Prihod ≤800k EUR: prijelazna odredba do 2027'
    
    if year >= 2025:
        return True, 'E-Rechnung obvezna (B2B DE)'
    
    return False, 'Nije obvezno'
```

---

### DE DSFinV-K (Kassensicherungsverordnung)

**KassenSichV: na snazi od 01.01.2020.**
**DSFinV-K: format za podatke fiskalnih blagajni**

| Datum | Obveza |
|-------|--------|
| 01.01.2020. | KassenSichV — sve blagajne moraju imati TSE (technische Sicherheitseinrichtung) |
| 01.01.2020. | DSFinV-K export format obavezan za reviziju |
| 01.01.2023. | Tagesabschluss (Z-Bericht) obavezan, čuvanje 10 godina |

**Z-Bericht (Tagesabschluss) DE — obavezan:**
- Svaki radni dan
- Sadrži: Gesamtumsatz, MwSt po stopama, broj transakcija, Kassensturz
- Čuvanje: 10 godina (GoBD)
- Format: DSFinV-K kompatibilan

---

### DE Pflichtangaben auf Rechnung (§14 Abs.4 UStG)

Obavezne stavke na svakom DE računu:

1. Vollständiger Name und Anschrift beider Parteien
2. Steuernummer ODER USt-IdNr. Ausstellers
3. Ausstellungsdatum
4. Fortlaufende Rechnungsnummer
5. Menge und Art der Lieferung / Leistung
6. **Zeitpunkt der Lieferung/Leistung (Leistungsdatum)** — čak i ako = datum računa (paušalni navod: "Leistungsdatum entspricht Rechnungsdatum" je OK)
7. Entgelt (neto iznos)
8. MwSt Steuersatz + Steuerbetrag
9. Bruttobetrag
10. Hinweis auf Steuerbefreiung (ako oslobođen)

> Nedostaje Leistungsdatum = račun nije valjan za Vorsteuerabzug!

---

## ═══════════════════════════════════════════════
## COMPLIANCE MATRICA — KADA PROVJERI ŠTO
## ═══════════════════════════════════════════════

```python
COMPLIANCE_MATRIX = {
    # HR dokumenti
    'HR_pre_2013': {
        'check_fiscal': False,       # Nije postojala
        'check_pdv': True,           # 25% standardna
        'check_currency': False,     # HRK normalno
        'check_eracun': False,
    },
    'HR_2013_2020': {
        'check_fiscal': True,        # ZKI + JIR (od 01.07.2013.)
        'check_qr': False,           # QR još nije bio obavezan
        'check_pdv': True,
        'check_currency': False,     # HRK normalno
        'check_eracun': False,
        'pdv_notes': '13% za restorane od 01.01.2020.',
    },
    'HR_2020_2022': {
        'check_fiscal': True,        # ZKI + JIR + QR (od 01.04.2020.)
        'check_qr': True,
        'check_pdv': True,
        'check_currency': False,     # HRK normalno pre-2023
        'check_eracun': False,
        'pdv_notes': 'Restorani 13% (2020-2022-03)',
    },
    'HR_2022_2023': {
        'check_fiscal': True,
        'check_qr': True,
        'check_pdv': True,
        'check_currency': 'both',    # 2023: prijelazna godina HRK/EUR
        'check_eracun': False,
        'pdv_notes': 'VELIKA promjena 01.04.2022: meso/voće/povrće 5%, restorani 5%',
    },
    'HR_2023_2025': {
        'check_fiscal': True,        # ZKI + JIR + QR + napojnice (2024)
        'check_pdv': True,
        'check_currency': 'eur',     # Samo EUR
        'check_eracun': 'b2g',       # Samo B2G
        'pdv_notes': 'Restorani od 01.01.2024. opet 13%',
    },
    'HR_2025_09_plus': {
        'check_fiscal': True,        # Novi zakon NN 89/25
        'check_pdv': True,
        'check_currency': 'eur',
        'check_eracun': 'b2g',       # B2B od 01.01.2026.
        'law': 'NN 89/25',
    },
    'HR_2026_plus': {  # PRODUKCIJA — naši pravi klijenti
        'check_fiscal': True,        # NN 89/25
        'check_pdv': True,
        'check_currency': 'eur',
        'check_eracun': 'b2b',       # B2B eRačun obveza
        'is_production': True,       # JEDINO OVO JE NAŠA PRODUKCIJA
        'law': 'NN 89/25 + ZO PDV',
    },
    
    # DE dokumenti
    'DE_pre_2020': {
        'check_mwst': True,          # 19%/7% stabilno
        'check_erechnung': False,
        'check_dsfinvk': False,
        'mwst_standard': 19, 'mwst_reduced': 7,
    },
    'DE_2020_07_12': {
        'check_mwst': True,
        'mwst_standard': 16,         # COVID! 16% je LEGALNO
        'mwst_reduced': 5,           # COVID! 5% je LEGALNO
        'check_erechnung': False,
        'covid_period': True,        # Obavezno označiti
    },
    'DE_2021_2023': {
        'check_mwst': True,
        'mwst_standard': 19, 'mwst_reduced': 7,
        'check_erechnung': False,
        'restaurant_note': 'Gastronomija 7% do 31.12.2023.',
    },
    'DE_2024': {
        'check_mwst': True,
        'mwst_standard': 19, 'mwst_reduced': 7,
        'check_erechnung': False,    # Još nije obveza slanja
        'check_erechnung_receive': True,  # ALI primanje od 01.01.2025
        'restaurant_note': 'Gastronomija od 01.01.2024. OPET 19%!',
    },
    'DE_2025_plus': {
        'check_mwst': True,
        'mwst_standard': 19, 'mwst_reduced': 7,
        'check_erechnung': True,     # Primanje OBVEZNO. Slanje uz prijelazne odredbe.
        'kleinunternehmer_limit': 25000,
        'solar_panels': 0,           # 0% za solarne ploče
    },
}
```

---

## ═══════════════════════════════════════════════
## PODACI U BAZI — KLASIFIKACIJA
## ═══════════════════════════════════════════════

```python
# Distribucija dokumenata po godini i statusu
DATABASE_CLASSIFICATION = {
    2011: {'source': 'synesis', 'count': 6,     'is_production': False, 'currency': 'EUR'},
    2012: {'source': 'synesis', 'count': 13,    'is_production': False, 'currency': 'EUR'},
    2013: {'source': 'synesis', 'count': 15,    'is_production': False, 'currency': 'EUR'},
    2014: {'source': 'synesis', 'count': 32,    'is_production': False, 'currency': 'EUR'},
    2015: {'source': 'synesis', 'count': 17,    'is_production': False, 'currency': 'EUR'},
    2016: {'source': 'synesis', 'count': 11,    'is_production': False, 'currency': 'EUR'},
    2017: {'source': 'synesis', 'count': 21,    'is_production': False, 'currency': 'EUR'},
    2018: {'source': 'synesis', 'count': 106,   'is_production': False, 'currency': 'EUR'},
    2019: {'source': 'synesis', 'count': 68,    'is_production': False, 'currency': 'EUR'},
    2020: {'source': 'synesis', 'count': 103,   'is_production': False, 'currency': 'EUR'},
    2021: {'source': 'synesis', 'count': 103,   'is_production': False, 'currency': 'EUR'},
    2022: {'source': 'synesis', 'count': 166,   'is_production': False, 'currency': 'EUR'},
    2023: {'source': 'synesis', 'count': 292,   'is_production': False, 'currency': 'EUR'},
    2024: {'source': 'synesis', 'count': 2756,  'is_production': False, 'currency': 'EUR'},
    2025: {'source': 'synesis', 'count': 11383, 'is_production': False, 'currency': 'EUR'},
    2026: {'source': 'manual',  'count': 236,   'is_production': True,  'currency': 'EUR'},
    # POS posebno:
    'pos_2026': {'source': 'pos', 'count': 251, 'is_production': True,  'currency': 'EUR'},
}

# Napomena: Svi Synesis dokumenti su u EUR bez obzira na godinu
# (Synesis je već preračunao HRK u EUR pri uvozu)
# Ovo znači da check_currency za historijske dokumente nije relevantan

PRODUCTION_FILTER_SQL = """
    synesis_id IS NULL
    AND EXTRACT(year FROM date_issued) >= 2026
"""

PRODUCTION_FILTER_DJANGO = {
    'synesis_id__isnull': True,
    'date_issued__year__gte': 2026,
}
```

---

## ═══════════════════════════════════════════════
## ZAKONSKI REFERENTNI IZVOR
## ═══════════════════════════════════════════════

### HR Reference

| Zakon | NN broj | Na snazi | Sadržaj |
|-------|---------|----------|---------|
| Zakon o fiskalizaciji u prometu gotovinom | 133/12 | 01.01.2013. | Osnova v1.0 |
| ZoF izmjena | 115/16 | 01.01.2017. | Izmjene |
| ZoF izmjena | 106/18 | 2018. | Izmjene |
| ZoF izmjena | 121/19 | 2019. | Izmjene |
| ZoF izmjena (QR kod) | 138/20 | 01.04.2020. (QR), 01.01.2021. | QR + prateći dok. |
| ZoF izmjena (napojnice) | 114/23 | 01.01.2024. | Napojnice |
| **NOVI Zakon o fiskalizaciji** | **89/25** | **01.09.2025.** | **v2.0 + eRačun** |
| Zakon o PDV-u | 73/13 | 01.07.2013. | Temeljni |
| ZoPDV izmjena | 115/16 | 01.01.2017. | Preraspodijela stopa |
| ZoPDV izmjena | 121/19 | 2019. | Zadržano 25% (bio plan 24%) |
| ZoPDV izmjena | 39/22 | **01.04.2022.** | **PDV 5% na hranu, restorani 5%** |
| ZoPDV izmjena | 113/22 | 01.10.2022. | Plin/grijanje 5%, solarke 0% |
| ZoPDV izmjena | 114/23 | 01.01.2024. | Restorani natrag 13% |
| ZoPDV izmjena | 35/24 | 01.04.2024. | Produljenje plin/grijanje |
| ZoPDV izmjena | 152/24 | 01.01.2025. | PDV prag 60k EUR (planirano) |
| Zakon o uvođenju eura | 57/22, 88/22 | 01.01.2023. | 1 EUR = 7,53450 HRK |

### DE Reference

| Zakon/Propis | Na snazi | Sadržaj |
|-------------|----------|---------|
| UStG §12 (COVID izmjena) | 01.07.2020. – 31.12.2020. | MwSt 16%/5% |
| UStG §12 (vraćeno) | 01.01.2021. | MwSt 19%/7% |
| UStG §12 Gastronomie | 01.01.2024. | Gastronomija opet 19% |
| KassenSichV | 01.01.2020. | TSE obveza za blagajne |
| DSFinV-K | 01.01.2020. | Format fiskalnih podataka |
| Wachstumschancengesetz | 01.01.2025. | E-Rechnung B2B + nova KU granica |
| §19 UStG (nova KU granica) | 01.01.2025. | 25.000 EUR / 100.000 EUR |
| JStG 2024 | 01.01.2025. | Umet. predm. 7%, paušalni polj. 7,8% |

---

## ZAKLJUČAK — FILTER ZA SVE AI AGENTE

```python
def is_compliant_check_required(invoice) -> tuple[bool, str, dict]:
    """
    Jedina funkcija koja govori treba li provjeru i s kojim parametrima.
    
    Returns:
        (should_check, reason, params_dict)
    """
    # 1. Synesis uvoz — nikad provjeravaj
    if invoice.synesis_id:
        return False, 'Synesis uvoz — historijski podaci', {}
    
    # 2. Staro (pre-2026 manual unos) — samo osnovna provjera, ne svi propisi
    year = invoice.date_issued.year if hasattr(invoice.date_issued, 'year') else 2000
    country = getattr(invoice, 'country', 'HR') or 'HR'
    
    if year < 2026 and country == 'HR':
        return False, f'HR dokument iz {year} — propisi toga doba, ne 2026 compliance', {}
    
    if year < 2025 and country == 'DE':
        return False, f'DE dokument iz {year} — propisi toga doba, e-Rechnung nije bio obavezan', {}
    
    # 3. Produkcija — provjeri s točnim parametrima
    params = get_legal_params(invoice.date_issued, country)
    return True, 'Produkcijski dokument — compliance provjera', params
```
