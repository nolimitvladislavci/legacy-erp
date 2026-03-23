# GEMINI_TASK — COMPLIANCE WATCHDOG V2 + LEGAL EXPLOIT ENGINE
# Agent: Gemini Pro 2.5
# Prioritet: VISOK — Faza 2 BORG FENIX
# Datum: 2026-03-23
# Pokreće: run_gemini_task.delay(task, max_steps=20)

## MISIJA
Ti si ComplianceWatchdog. Tvoj posao:
1. Pratiš promjene zakona u DE i HR jurisdikcijama
2. Prepoznaješ što se promijenilo i kako utječe na naše klijente
3. Tražiš LEGALNE prednosti koje klijenti ne koriste
4. Generiraš akcijske preporuke

## ZADACI

### ZADATAK A — Knowledge Core inicijalizacija
Napiši Django fixture (JSON) s popisom zakonskih izvora koje trebamo pratiti:

```python
# Struktura modela za koji pišeš fixture:
class LegalSource(models.Model):
    name = models.CharField(max_length=200)
    jurisdiction = models.CharField(choices=['DE', 'HR', 'EU'])
    url = models.URLField()
    feed_type = models.CharField(choices=['rss', 'api', 'scrape'])
    check_interval_hours = models.PositiveIntegerField()
    last_checked = models.DateTimeField(null=True)
    active = models.BooleanField(default=True)
```

Popuni sa STVARNIM URL-ovima za:
- Bundesrat (bundesrat.de — RSS)
- Bundestag (bundestag.de)
- EUR-Lex (eur-lex.europa.eu/RSSEP.xml — RSS postoji!)
- Narodne novine (nn.hr)
- FINA (fina.hr — objave)
- BMF (bundesfinanzministerium.de)

### ZADATAK B — Legal Exploit Detection
Napiši Python funkciju koja prima tekst zakona i vraća popis "legal opportunities":

```python
def find_legal_opportunities(legal_text: str, jurisdiction: str, company_profile: dict) -> list:
    """
    Vraća: [
        {
            "type": "tax_exemption" | "deduction" | "deferral" | "fund" | "threshold",
            "title": "Naziv mogućnosti",
            "description": "Što je to",
            "applicable_if": "Uvjeti primjene",
            "estimated_value_eur": 1500,
            "source": "§42 UStG",
            "risk_level": "low" | "medium" | "high",
            "action_required": "Što klijent treba napraviti"
        }
    ]
    """
```

Primjeri što tražiš (DE):
- § 19 UStG — Kleinunternehmerregelung (PDV oslobođenje do 22.000 EUR)
- § 7g EStG — Investitionsabzugsbetrag (investicijska rezerva do 200k)
- § 6b EStG — reinvesticijska rezerva kod prodaje nekretnina
- Kurzarbeitergeld — kad se može koristiti
- BAFA Bundesförderung — energetika, digitalizacija

Primjeri što tražiš (HR):
- PDV threshold (40.000 EUR)
- Olakšice za zapošljavanje (HZMO)
- EU strukturni fondovi za MSP
- Paušalni obrt vs d.o.o. analiza

### ZADATAK C — Diff Engine
Kad se zakon promijeni, generiraj strukturirani diff:

```python
class LegalChangeDiff(TypedDict):
    change_date: str
    source: str
    summary: str              # 1 rečenica
    impact_level: str         # 'immediate' | 'planning' | 'monitoring'
    affected_clients: list    # ['all', 'de_clients', 'pos_clients', etc.]
    deadline: Optional[str]   # kada se mora implementirati
    action_for_us: str        # što LIMIT Connect treba promijeniti
    action_for_client: str    # što klijent treba napraviti
```

### ZADATAK D — Napiši GEMINI_TASK_MARKET_INTEL.md
Napravi task za sebe (Gemini) kojim ćeš pratiti:
- Billomat DE (billing SaaS)
- Lexoffice (Haufe Group)
- sevDesk
- Debitoor
Što nude, što im nedostaje, gdje je naša prednost.
Spremi kao /var/www/fina-connect/GEMINI_TASK_MARKET_INTEL.md

## RESURSI
- Django app: limit_connect_ai/ (već postoji — provjeri modele)
- Celery: dostupan za scheduling
- Claude API: dostupan za sub-agenta pozive

## DONE KRITERIJ
- [ ] LegalSource fixture s min 8 izvora
- [ ] find_legal_opportunities() radi na testnom tekstu § 19 UStG
- [ ] LegalChangeDiff TypedDict implementiran
- [ ] GEMINI_TASK_MARKET_INTEL.md napisan
- [ ] Sve commitano i testirano

## NAPOMENA — ETIKA
Tražimo LEGALNE mogućnosti. Sve što pronađeš mora biti:
- Izričito navedeno u zakonu
- Primjenjivo za naše klijente (MSP, gastronomija, transport, OPG)
- Bez agresivne porezne optimizacije koja bi privukla reviziju
Ako pronađeš nešto graničnom, označi risk_level='high' i dodaj disclaimer.
