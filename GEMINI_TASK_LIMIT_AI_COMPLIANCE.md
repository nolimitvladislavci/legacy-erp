# GEMINI_TASK_LIMIT_AI_COMPLIANCE
# Izvršava: Gemini autonomni agent
# Koordinira: Sonnet
# Prioritet: SREDNJI (Faza 2 — kreće nakon Faze 1)
# Datum: 2026-03-21

## OBAVEZNO PRIJE POČETKA
1. Pročitaj FENIX_STATUS.md
2. Pročitaj LIMIT_CONNECT_AI_PLAN.md — Faza 2, sekcija 2.2 i 2.3
3. Provjeri je li Faza 1 završena (limit_connect_ai app mora postojati)
4. Pročitaj limit_connect_ai/models.py (ComplianceWatchItem)

## CILJ
Implementirati ComplianceWatchdog — AI koji autonomno prati zakonske promjene
i kreira ComplianceWatchItem za svaku kompaniju kad detektira promjenu.

## ZADATAK

### 1. Provjeri postojeće
- Pročitaj intelligence/tasks.py (intelligence_nightly_patrol)
- Pročitaj intelligence/models.py
- Razumij kako patrol već radi — proširujemo, ne dupličiramo

### 2. Zakonski izvori po tipu klijenta
Definiraj u `limit_connect_ai/compliance_sources.py`:

```python
COMPLIANCE_SOURCES = {
    'HR': [
        {'name': 'Narodne novine', 'url': 'https://narodne-novine.nn.hr/rss.aspx', 'type': 'rss'},
        {'name': 'FINA obavijesti', 'url': 'https://www.fina.hr/rss', 'type': 'rss'},
        {'name': 'ePorezi novosti', 'url': 'https://e-porezna.porezna-uprava.hr/', 'type': 'scrape'},
    ],
    'DE': [
        {'name': 'Bundesgesetzblatt', 'url': 'https://www.bgbl.de/', 'type': 'scrape'},
        {'name': 'BMF Schreiben', 'url': 'https://www.bundesfinanzministerium.de/rss', 'type': 'rss'},
    ],
    'EU': [
        {'name': 'EUR-Lex', 'url': 'https://eur-lex.europa.eu/oj/direct-access.html', 'type': 'scrape'},
    ],
    'NPF': [  # udruge
        {'name': 'Registar udruga', 'url': 'https://registri.uprava.hr/rss', 'type': 'rss'},
    ],
}
```

### 3. compliance_watchdog Celery task
```python
@shared_task
def compliance_check_all():
    """Ponedjeljak 08:00 — provjeri zakonske promjene za sve aktivne klijente."""
    for mission in AIAgentMission.objects.filter(
        is_active=True, mission_type='compliance_watch'
    ):
        check_compliance_for_company.delay(mission.company_id)

@shared_task
def check_compliance_for_company(company_id):
    """
    1. Dohvati relevantne izvore za kompaniju (HR/DE/EU/NPF)
    2. Scrappe/RSS — dohvati novosti zadnjih 7 dana
    3. Pošalji Gemini Flash za analizu relevantnosti
    4. Ako releventno za ovu kompaniju → kreira ComplianceWatchItem
    5. Šalje WhatsApp upozorenje (instant, bez odobrenja)
    """
```

### 4. Gemini evaluacija relevantnosti
Za svaki zakonski članak koji nađeš:
- Pošalji Gemini Flash prompt: "Je li ova zakonska promjena relevantna za [djelatnost]? Što treba napraviti? Koji je rok?"
- Ako relevantno: kreira ComplianceWatchItem s:
  - law_reference
  - description
  - deadline (izvuci iz teksta)
  - ai_notes (što konkretno napraviti)
  - status = 'action_needed'

### 5. WhatsApp notifikacija (instant)
Format (iz PLANA):
```
⚠️ *Zakonska promjena — LIMIT Connect*
[Naziv zakona]
Relevantno za: [tvoja djelatnost]
Rok: [datum ili "nije određen"]
Što napraviti: [AI sažetak]
Detalji u sustavu: limit-connect.com/ai/compliance/
```

### 6. Integracija s intelligence patrol
Proširi `intelligence/tasks.py::intelligence_nightly_patrol` da poziva
`check_compliance_for_company` za kompanije koje imaju compliance_watch misiju.
NE dupliziraj logiku — delegiraj.

### 7. Na kraju OBAVEZNO:
- Testiraj s jednim ComplianceWatchItem ručno (Konjik d.o.o.)
- Provjeri da WhatsApp format izgleda ispravno (ne šalji zapravo)
- git commit s porukom "limit_connect_ai Faza 2: ComplianceWatchdog"
- Upiši DONE u FENIX_STATUS.md
- Napiši Sonnet što si napravio i što možda nedostaje

## NAPOMENE
- RSS je jednostavniji od scrapinga — počni s RSS izvorima
- Ako izvor nema RSS, koristi requests + BeautifulSoup (već u venv?)
- Rate limit! Ne scrappe isti izvor više od 1x/24h — koristi cache
- Gemini Flash je tvoj model za evaluaciju — koristiš ga interno
- Kad nisi siguran je li relevantno — bolje javi nego ne javi

## GOTOVO KAD:
- [ ] compliance_sources.py definiran
- [ ] check_compliance_for_company task radi bez errora
- [ ] Kreira ComplianceWatchItem za testni slučaj
- [ ] WhatsApp format ispravan (log, ne stvarno slanje)
- [ ] git commit napravljen
