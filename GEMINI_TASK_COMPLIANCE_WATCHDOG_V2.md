# GEMINI_TASK — COMPLIANCE WATCHDOG V2 + LEGAL EXPLOIT ENGINE
# Agent: Gemini Pro 2.5
# Prioritet: VISOK — Faza 2 BORG FENIX
# Datum: 2026-03-23 | Ažurirano: 2026-03-25 — dodani pčelari, rental, EU matrix
# Pokreće: run_gemini_task.delay(task, max_steps=20)

## MISIJA
Ti si ComplianceWatchdog. Tvoj posao:
1. Pratiš promjene zakona u DE i HR jurisdikcijama
2. Prepoznaješ što se promijenilo i kako utječe na naše klijente
3. Tražiš LEGALNE prednosti koje klijenti ne koriste
4. Generiraš akcijske preporuke

**Čitaj i ovo:** EU_FONDOVI_MASTER_MATRIX.md — kompletna matrica svih skupina i EU prilike

---

## KORISNIČKE GRUPE ZA WATCHDOG (prošireno 2026-03-25)

```python
CLIENT_SEGMENTS = {
    'udruga':    ['ESF+', 'ERDF', 'CERV', 'Erasmus+', 'Zakon o udrugama', 'Zakon o volonterstvu'],
    'opg_pcela': ['APPRRR intervencije', 'Pravilnik o držanju pčela', 'EPP evidencija',
                  'Izravna plaćanja ZPP', 'plavi dizel', 'EU Reg 2021/126'],
    'rental':    ['eVisitor Zakon o turizmu', 'turistička pristojba', 'EAFRD ruralni turizam',
                  'MINT natječaji', 'Zakon o ugostiteljskoj djelatnosti', 'PDV najam'],
    'opg':       ['APPRRR', 'IPARD III', 'EAFRD', 'Zakon o poljoprivredi', 'ekološka certifikacija'],
    'msp':       ['ERDF digitalizacija', 'HAMAG-BICRO', 'HZZ subvencije', 'MINPO voucheri',
                  'PDV threshold 40k', 'Zakon o radu'],
    'pos':       ['Zakon o fiskalizaciji', 'NN promjene', 'FINA tehničke specifikacije'],
    'de_klijent':['KassenSichV', 'GoBD', '§19 UStG', '§7g EStG', 'BAFA', 'KfW', 'DSFinV-K'],
    'all_hr':    ['Zakon o radu', 'PDV', 'eRačun ViDA 2028', 'GDPR', 'Zakon o zaštiti potrošača'],
}
```

---

## ZADATAK A — Knowledge Core inicijalizacija (PROŠIRENO)

Napiši Django fixture (JSON) s popisom zakonskih izvora — MINIMALNO 20 izvora:

```python
class LegalSource(models.Model):
    name = models.CharField(max_length=200)
    jurisdiction = models.CharField(choices=['DE', 'HR', 'EU'])
    url = models.URLField()
    feed_type = models.CharField(choices=['rss', 'api', 'scrape'])
    check_interval_hours = models.PositiveIntegerField()
    client_segment = models.CharField(max_length=50, blank=True)  # NOVO
    last_checked = models.DateTimeField(null=True)
    active = models.BooleanField(default=True)
```

**Obavezni izvori (proširena lista):**

HR / EU — OPĆE:
- Narodne novine (nn.hr) — scrape — 24h
- EUR-Lex RSS (eur-lex.europa.eu/RSSEP.xml) — rss — 12h
- FINA obavijesti (fina.hr) — scrape — 24h
- eUfondovi natječaji (eufondovi.gov.hr) — scrape — 24h
- eKohezija natječaji (esf.hr/esfplus/natjecaji) — rss — 24h
- HAMAG-BICRO (hamagbicro.hr/programi-i-projekti) — scrape — 48h

HR — PČELARI (client_segment='opg_pcela'):
- APPRRR pčelarstvo (apprrr.hr/pcelarstvo-3/) — scrape — 24h
- Agroklub pčelarstvo RSS — rss — 12h
- HPS savez (pcela.hr) — scrape — 48h
- MPS pravilnici pčelarstvo — scrape — 48h

HR — RENTAL / TURIZAM (client_segment='rental'):
- MINT natječaji (mint.hr/natjecaji) — scrape — 24h
- HTZ vijesti (htz.hr) — rss — 24h
- eVisitor promjene (evisitor.mint.hr) — scrape — 48h
- APPRRR ruralni razvoj (apprrr.hr/ruralni-razvoj) — scrape — 48h

HR — UDRUGE (client_segment='udruga'):
- Ured za udruge (udruge.gov.hr/vijesti) — rss — 24h
- ESF+ natječaji (esf.hr/esfplus/natjecaji) — rss — 12h
- Ministarstvo rada (mrosp.gov.hr/natjecaji) — scrape — 24h

DE (client_segment='de_klijent'):
- Bundesrat RSS (bundesrat.de) — rss — 12h
- BMF Pressemitteilungen — rss — 24h
- BAFA aktuell — scrape — 24h
- KfW Presse — rss — 48h

---

## ZADATAK B — Legal Exploit Detection (PROŠIRENO)

Napiši Python funkciju `find_legal_opportunities()` — proširiti za sve segmente:

```python
def find_legal_opportunities(legal_text: str, jurisdiction: str, company_profile: dict) -> list:
    """
    Vraća: [{"type", "title", "description", "applicable_if", "estimated_value_eur",
              "source", "risk_level", "action_required", "segment": ["rental", "opg_pcela"...]}]
    """
```

**Prilike koje OBAVEZNO tražiš:**

PČELARI (segment='opg_pcela'):
- APPRRR intervencija 55.1.b.01 — oprema min. 30 košnica (100% refundacija)
- APPRRR 55.1.b.02 — suzbijanje varoze (100% refundacija, svi pčelari)
- "Plavi dizel" — povrat trošarine na gorivo
- Izravna plaćanja po košnici (Jedinstveni zahtjev)
- Ekološki bonus — dodatni % za eko-certificirane
- R1 račun vezan uz subvenciju — APPRRR traži specifikaciju

RENTAL / TURIZAM (segment='rental'):
- PDV oslobođenje za iznajmljivače fizičke osobe < 40k EUR
- Paušalni porez na dohodak od iznajmljivanja (po krevetu/godišnje)
- EAFRD M06 — investicija u ruralni smještaj do 200k EUR
- LEADER/LAG fondovi — 5-50k EUR za ruralni turizam
- HTZ poticaji za rekonstrukciju i kategorizaciju

UDRUGE (segment='udruga'):
- Volonterski sati kao EU in-kind (do 50% sufinanciranja, EU FR čl. 190)
- CERV program (Citizens, Equality, Rights) — do 500k EUR
- Erasmus+ KA2 — 50-150k EUR za edukacijske projekte
- ESF+ — 100k-2M EUR za socijalne projekte

MSP (segment='msp'):
- ERDF digitalizacija (NPU) — do 100k EUR
- MINPO digitalni voucheri — do 25k EUR
- HZZ subvencija zapošljavanja — 70-100% bruto 12 mj
- HAMAG-BICRO povoljni zajmovi

DE (segment='de_klijent'):
- § 19 UStG Kleinunternehmerregelung (PDV < 25k EUR)
- § 7g EStG Investitionsabzugsbetrag (200k EUR rezerva)
- BAFA BEG — energetska sanacija do 70% troška
- KfW kredit — 1-2% kamate za energetiku/digitalizaciju

---

## ZADATAK C — Diff Engine (nepromijenjen)

```python
class LegalChangeDiff(TypedDict):
    change_date: str
    source: str
    summary: str
    impact_level: str         # 'immediate' | 'planning' | 'monitoring'
    affected_clients: list    # koristiti CLIENT_SEGMENTS ključeve
    deadline: Optional[str]
    action_for_us: str
    action_for_client: str
```

**AFFECTED_CLIENTS_MATRIX (koristiti kao referencu):**
```python
{
    'pcela_epp_rok':          ['opg_pcela'],           # rujan-prosinac
    'apprrr_intervencija':    ['opg_pcela'],            # godišnje
    'apprrr_ruralni':         ['opg', 'rental', 'opg_pcela'],
    'evisitor_promjena':      ['rental'],               # instant
    'turisticka_pristojba':   ['rental'],
    'eafrd_natjecaj':         ['opg', 'rental', 'opg_pcela'],
    'esf_natjecaj':           ['udruga', 'msp'],
    'cerv_natjecaj':          ['udruga'],
    'erdf_digitalizacija':    ['msp', 'de_klijent'],
    'hamag_kredit':           ['msp'],
    'bafa_promjena':          ['de_klijent'],
    'kassenSichV':            ['de_klijent', 'pos'],
    'pdv_threshold_hr':       ['all_hr'],
    'fiskalizacija_hr':       ['all_hr'],
    'zakon_o_radu':           ['all_hr'],
    'eu_vida_eracun_2028':    ['all'],
}
```

---

## ZADATAK D — GEMINI_TASK_MARKET_INTEL.md (nepromijenjen)

Napravi task kojim ćeš pratiti:
- Billomat DE, Lexoffice (Haufe), sevDesk, Debitoor
- Komparativna analiza: što nude, što im nedostaje, gdje je naša prednost
- Posebno: pokrivaju li pčelare / rental / EU fondove integraciju?
Spremi kao /var/www/fina-connect/GEMINI_TASK_MARKET_INTEL.md

**Hint za traženje prednosti:**
- Nijedan od konkurenata NEMA: EPP Prilog 3 PDF, APPRRR subvenciju integrirani,
  eVisitor direktnu integraciju, ili EU in-kind volonterski timesheet
- Ovo su naše asimetrične prednosti — dokumentiraj ih

---

## ZADATAK E (NOVO) — Fund Opportunity Scanner

Jednom tjedno (ponedjeljak 06:00), skeniraj sve izvore i generiraj:

```python
def weekly_fund_scan(company_id: int) -> list:
    """
    Za svaku kompaniju: pretraži LegalSource izvore,
    pronađi aktivne natječaje, procijeni prihvatljivost.
    """
    # 1. Dohvati company profil (djelatnost, veličina, lokacija, plan)
    # 2. Za svaki relevantni izvor iz CLIENT_SEGMENTS:
    #    - Scrapiraj aktivne natječaje/pozive
    #    - Procijeni eligibilitet (0-100 score)
    # 3. Za natječaje score >= 60:
    #    - Kreiraj FundOpportunity (intelligence app)
    #    - Pošalji WhatsApp/email alert
    # 4. Logira u AIReportLog
```

Format WhatsApp alertа:
```
🏛️ *EU/Državna prilika za vaš OPG*
Fond: APPRRR 55.1.b.01 — Oprema za pčelarstvo
Maksimalni iznos: [X] EUR (100% refundacija)
Rok: [datum]
Procjena prihvatljivosti: 85%
Uvjet: R1 računi za opremu, min. 30 košnica, ažurirani EPP

Za više: [link na FundApplicationDraft]
```

---

## RESURSI
- Django app: limit_connect_ai/ (provjeri modele)
- Referentni fajl: EU_FONDOVI_MASTER_MATRIX.md (NOVO — kompletan pregled)
- Celery: dostupan za scheduling
- Claude API: dostupan za sub-agenta

## DONE KRITERIJ
- [ ] LegalSource fixture s min 20 izvora (uključuje pčelare, rental, udruge, DE)
- [ ] CLIENT_SEGMENTS dict implementiran u modelu ili konstanti
- [ ] find_legal_opportunities() pokriva sve 5 segmenata
- [ ] AFFECTED_CLIENTS_MATRIX implementiran u LegalChangeDiff
- [ ] weekly_fund_scan() implementiran kao Celery task
- [ ] GEMINI_TASK_MARKET_INTEL.md napisan (s konkurentskom analizom EU fondova)
- [ ] Sve commitano i testirano

## NAPOMENA — ETIKA (nepromijenjena)
Tražimo LEGALNE mogućnosti. Izričito navedene u zakonu.
Primjenjivo za naše klijente. Bez agresivne porezne optimizacije.
risk_level='high' + disclaimer za granične slučajeve.
