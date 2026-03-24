# GEMINI_TASK_TAX_WIZARD_F2 — AI Motor
## Agent: Gemini | Prioritet: P0 | Tjedan: 2-3
## Preduvjet: CC_TASK_TAX_WIZARD_F1 mora biti DONE

**Čitaj prvo:** TAX_WIZARD_MASTER_PLAN.md, FENIX_STATUS.md, tax_wizard/models.py  
**Tvoj task:** Mozak sustava. Bez tebe wizard je samo kalkulator — s tobom je porezni savjetnik.

---

## MISIJA

Izgradi 2 modula:
1. `deductions.py` — rule engine za 12 HR zakonskih olakšica
2. `ai_advisor.py` — Haiku koji proaktivno pronalazi propušteni novac

---

## MODUL 1: deductions.py

### Svih 12 olakšica koje moraju biti pokrivene

```python
"""
deductions.py

Rule engine za HR zakonske olakšice (Zakon o porezu na dohodak, NN 115/16 - 144/23).
NE savjetujemo — citiramo zakon i računamo.
Svaka olakšica je zasebna klasa s:
  - check(session) → bool: ispunjava li uvjete
  - calculate(session) → Decimal: iznos olakšice
  - message(session) → str: objašnjenje za korisnika (citira zakon)
  - docs_needed → list: dokumenti za dokazivanje
"""

OLAKSICE = [
    {
        'id': 'osobni_odbitak_osnovni',
        'naziv': 'Osnovni osobni odbitak',
        'zakon': 'čl. 14. st. 1. Zakona o porezu na dohodak',
        'iznos_2025': Decimal('560.00'),  # EUR/mjes = 6.720 god
        'opis': 'Svaki porezni obveznik ima pravo na osnovni osobni odbitak 560 EUR/mjes.',
        'check': lambda s: True,  # svi imaju pravo
        'calculate': lambda s: Decimal('6720.00'),
    },
    {
        'id': 'odbitak_dijete_1',
        'naziv': 'Osobni odbitak — 1. dijete',
        'zakon': 'čl. 14. st. 2. Zakona, koeficijent 0,7',
        'iznos': lambda djeca: Decimal('560') * Decimal('0.7'),  # 392 EUR/mjes
        'check': lambda s: s.step_data.get('djeca_broj', 0) >= 1,
        'message': 'Za 1. dijete koeficijent je 0,7 × 560 = 392 EUR/mjes (4.704 EUR/god). Zahtijeva: potvrda o uzdržavanju ili podaci na PK kartici.',
        'docs_needed': ['Rodný list djeteta', 'Potvrda o školovanju (za stariju djecu)'],
    },
    {
        'id': 'odbitak_dijete_2',
        'naziv': 'Osobni odbitak — 2. dijete',
        'zakon': 'čl. 14. st. 2. koeficijent 1,0',
        'check': lambda s: s.step_data.get('djeca_broj', 0) >= 2,
        'calculate': lambda s: Decimal('560.00'),  # puni koeficijent za 2.
        'message': 'Za 2. dijete koeficijent je 1,0 × 560 = 560 EUR/mjes (6.720 EUR/god).',
    },
    {
        'id': 'odbitak_dijete_3plus',
        'naziv': 'Osobni odbitak — 3. i svako sljedeće dijete',
        'zakon': 'čl. 14. st. 2. koeficijent 2,0 (3.djete), 2,7 (4.), 3,5 (5.) itd.',
        'check': lambda s: s.step_data.get('djeca_broj', 0) >= 3,
        'calculate': 'progresivna_tablica',  # posebna funkcija
    },
    {
        'id': 'odbitak_invaliditet_vlastiti',
        'naziv': 'Osobni odbitak — invaliditet (vlastiti)',
        'zakon': 'čl. 14. st. 2. koeficijent 0,4 (do 100%), 1,5 (100%)',
        'check': lambda s: s.step_data.get('invaliditet_vlastiti', False),
        'message': 'Uz potvrdu o stupnju invalidnosti, odbitak je 0,4 do 1,5 × 560 EUR/mjes.',
        'docs_needed': ['Rješenje o invalidnosti (HZMO ili MUP)'],
    },
    {
        'id': 'odbitak_invaliditet_clana',
        'naziv': 'Osobni odbitak — invaliditet člana obitelji',
        'zakon': 'čl. 14. st. 2.',
        'check': lambda s: s.step_data.get('invaliditet_clan', False),
    },
    {
        'id': 'darovanja',
        'naziv': 'Odbitak za darovanja udrugama',
        'zakon': 'čl. 15. st. 2. Zakona — do 2% primitaka za kulturne, humanitarne, zdravstvene, sportske svrhe',
        'check': lambda s: s.step_data.get('darovanja', Decimal('0')) > 0,
        'calculate': lambda s: min(
            s.step_data.get('darovanja', Decimal('0')),
            (s.gross_income or Decimal('0')) * Decimal('0.02')
        ),
        'message': 'Možeš odbiti darovanja udrugama do 2% primitaka = {limit}€. Tvoja darovanja: {iznos}€.',
        'docs_needed': ['Potvrde udruga o primljenim darovanjima s IBAN-om'],
    },
    {
        'id': 'doprinosi_zdravstveno',
        'naziv': 'Odbitak za uplaćene doprinose za zdravstveno osiguranje',
        'zakon': 'čl. 15. st. 1. Zakona — doprinosi plaćeni u tuzemstvu',
        'check': lambda s: s.step_data.get('doprinosi_zdravstveno', Decimal('0')) > 0,
        'docs_needed': ['Potvrda HZZO o uplaćenim doprinosima'],
    },
    {
        'id': 'mladi_do_25',
        'naziv': 'Umanjenje poreza — mladi do 25 godina (100% povrat)',
        'zakon': 'čl. 43.a Zakona — porezni obveznici do 25 god.: 100% umanjenje poreza na dohodak od rada',
        'check': lambda s: s.step_data.get('dob', 2000) >= 2001,  # = do 25 god u 2025.
        'message': 'Kao osoba do 25 godina, IMATE PRAVO NA 100% POVRAT plaćenog poreza na dohodak od rada. Ovo nije greška.',
        'high_priority': True,
    },
    {
        'id': 'mladi_26_30',
        'naziv': 'Umanjenje poreza — mladi 26-30 godina (50% povrat)',
        'zakon': 'čl. 43.a Zakona — 26-30 god.: 50% umanjenje',
        'check': lambda s: 1996 <= s.step_data.get('dob', 2000) <= 2000,
        'high_priority': True,
    },
    {
        'id': 'potpomognuto_podrucje',
        'naziv': 'Umanjenje poreza — potpomognuto područje JLS I. skupine / Vukovar',
        'zakon': 'čl. 43. Zakona',
        'check': 'jls_engine.is_potpomognuto',  # posebna JLS lookup funkcija
        'message': 'Vaša JLS ({jls}) spada u potpomognuto područje. Pravo na umanjenje poreza od nesamostalnog rada.',
    },
    {
        'id': 'iseljenik_povratak',
        'naziv': 'Novo 2025: Povrat za iseljenike koji se vraćaju',
        'zakon': 'čl. 43.b Zakona (od 1.1.2025.) — boravio 2+ god. u inozemstvu, vratio se u HR',
        'check': lambda s: s.step_data.get('bio_inozemstvo', False),
        'message': 'Nova olakšica 2025. Za HR državljane koji su 2+ god. u inozemstvu i prijavili se u HR od 1.1.2025. Umanjenje razmjernog dijela porezne obveze.',
        'docs_needed': ['Potvrda o prijavi boravišta', 'Dokaz o boravku u inozemstvu'],
        'high_priority': True,  # malo tko zna za ovo
    },
]
```

### scan_all funkcija

```python
def scan_all(session) -> dict:
    """
    Pokretač za sve olakšice.
    Vraća: {'found': [lista], 'total_savings': Decimal, 'high_priority': [lista]}
    """
    found = []
    total_savings = Decimal('0')
    high_priority = []
    
    for olaksica in OLAKSICE:
        check_fn = olaksica.get('check')
        if callable(check_fn) and check_fn(session):
            calc_fn = olaksica.get('calculate')
            savings = calc_fn(session) if callable(calc_fn) else None
            
            entry = {
                'id': olaksica['id'],
                'naziv': olaksica['naziv'],
                'zakon': olaksica.get('zakon', ''),
                'message': olaksica.get('message', '').format(
                    iznos=session.step_data.get(olaksica['id'], 0),
                    limit=(session.gross_income or 0) * Decimal('0.02'),
                    jls=session.jls_code,
                ),
                'savings': savings,
                'docs_needed': olaksica.get('docs_needed', []),
                'high_priority': olaksica.get('high_priority', False),
            }
            found.append(entry)
            if savings:
                total_savings += savings
            if olaksica.get('high_priority'):
                high_priority.append(entry)
    
    return {
        'found': found,
        'count': len(found),
        'total_savings': total_savings,
        'high_priority': high_priority,
    }
```

---

## MODUL 2: ai_advisor.py

### Zadatak

Haiku model (ne Sonnet — ovo mora biti brzo i jeftino) generira **proaktivne poruke** u wizardu.

```python
"""
ai_advisor.py

Haiku-powered proaktivni porezni savjetnik.
PRAVILO: Nikad ne savjetujemo. Citiramo zakon i prikazujemo matematiku.
Korisnik donosi zaključak sam.
"""
import anthropic

def generate_step_hint(session, step_id: str, prefill_value=None) -> str:
    """
    Generira kontekstualni hint za određeni korak wizarda.
    Poziva se AJAX-om nakon učitavanja svakog koraka.
    """
    client = anthropic.Anthropic()
    
    context = f"""
    Porezni wizard za HR. Korisnik: {session.taxpayer_type}, 
    godina: {session.tax_year}, JLS stopa: {session.jls_rate}%.
    Korak: {step_id}.
    {"Predpopunjeni podatak: " + str(prefill_value) + "€" if prefill_value else ""}
    Pronađene olakšice: {len(session.deductions_found)} 
    """
    
    prompt = f"""
    {context}
    
    Generiraj JEDNU kratku proaktivnu poruku (max 2 rečenice, HR jezik) za ovaj korak wizarda.
    Pravila:
    - Citiraj zakon ako je relevantno
    - Pokaži matematiku: "X€ × Y% = Z€"
    - Nikad ne kaži "Preporučujem" ili "Trebali biste"
    - Budi konkretan — korisnik nema strpljenja za opće fraze
    - Ako ima predpopunjen podatak, potvrdi ga: "Vidim X€ iz tvojih faktura."
    """
    
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def generate_savings_summary(session) -> str:
    """
    Generira sažetak pronađenih ušteda — prikazuje se na kraju wizarda.
    Ovo je najvažnija poruka u cijelom wizardu.
    """
    client = anthropic.Anthropic()
    
    deductions = session.deductions_found
    high_priority = [d for d in deductions if d.get('high_priority')]
    total = session.calculated_return or 0
    
    prompt = f"""
    HR porezni wizard. Generiraj sažetak ušteda (HR jezik, max 4 rečenice).
    
    Pronađene olakšice: {len(deductions)}
    Visoko prioritetne (malo tko zna): {[d['naziv'] for d in high_priority]}
    Ukupna moguća ušteda/povrat: {total}€
    Porezni obveznik: {session.taxpayer_type}
    
    Budi konkretan. Navedi svaku visoko prioritetnu olakšicu. 
    Završi s: "Ove podatke treba unijeti u ePoreznu do [rok]."
    Nikad ne kaži "Preporučujem" — samo prikaži što zakon kaže.
    """
    
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def generate_jls_comparison(session) -> dict:
    """
    Prikazuje JLS poreznu stopu korisnika vs. prosjek županije i HR prosjek.
    NE savjetuje promjenu. Samo prikazuje podatke.
    """
    from .jls_engine import get_jls_rate, get_county_average
    
    user_rate = session.jls_rate or get_jls_rate(session.jls_code)
    county_avg = get_county_average(session.jls_code)
    hr_avg = Decimal('12.5')  # HR prosjek 2025
    
    gross = session.gross_income or Decimal('0')
    
    return {
        'tvoja_stopa': user_rate,
        'prosjek_zupanije': county_avg,
        'hr_prosjek': hr_avg,
        'razlika_vs_prosjek': user_rate - hr_avg,
        'iznos_razlike_eur': gross * (user_rate - hr_avg) / 100,
        'napomena': f'Vaša JLS ({session.jls_code}) ima stopu {user_rate}%. HR prosjek je {hr_avg}%.'
    }
```

---

## KORAK 3: jls_engine.py

Trebaj kreirati lookup tablicu za **574 JLS u HR** s njihovim poreznim stopama.

```python
"""
jls_engine.py

Lookup za 574 JLS (jedinica lokalne samouprave) u HR.
Podaci: porezne stope po JLS za 2025. godinu.
Izvor: Ministarstvo financija, NN odluke JLS.

Zbog veličine, podaci su u fixtures/jls_stope_2025.json
"""

import json, os
from decimal import Decimal
from functools import lru_cache

JLS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'jls_stope_2025.json')

@lru_cache(maxsize=1)
def _load_jls_data():
    with open(JLS_DATA_PATH) as f:
        return json.load(f)

def get_jls_rate(jls_code: str) -> Decimal:
    data = _load_jls_data()
    jls = data.get(jls_code, {})
    return Decimal(str(jls.get('stopa_niza', '20.0')))

def is_potpomognuto(session) -> bool:
    data = _load_jls_data()
    jls = data.get(session.jls_code, {})
    return jls.get('potpomognuto', False) or jls.get('vukovar', False)

def get_county_average(jls_code: str) -> Decimal:
    data = _load_jls_data()
    # Pronađi županiju ovog JLS-a i izračunaj prosjek
    jls = data.get(jls_code, {})
    county = jls.get('zupanija_code', '')
    rates = [Decimal(str(v['stopa_niza'])) for v in data.values() 
             if v.get('zupanija_code') == county and 'stopa_niza' in v]
    return sum(rates) / len(rates) if rates else Decimal('15.0')
```

### JLS fixtures — format

Kreiraj `tax_wizard/fixtures/jls_stope_2025.json` s podacima:

```json
{
  "HR010101": {
    "naziv": "Grad Zagreb",
    "zupanija_code": "HR01",
    "stopa_niza": 23.6,
    "stopa_visa": 30.0,
    "potpomognuto": false,
    "vukovar": false
  },
  "HR020101": {
    "naziv": "Grad Osijek",
    "zupanija_code": "HR02",
    "stopa_niza": 10.0,
    "stopa_visa": 15.0,
    "potpomognuto": false,
    "vukovar": false
  }
  // ... svih 574 JLS
}
```

**Za punjenje JLS podataka:** Web scrape ili PDF parse iz NN-a. Ako nemaš podatke, stavi 50 najvećih gradova i označi `"placeholder": true` za ostatak.

---

## TESTOVI koje moraš napisati

1. `test_olaksica_mladi_100_posto` — dob 2003, potvrdi da je high_priority i 100% povrat
2. `test_olaksica_iseljenik_nova_2025` — bio_inozemstvo=True, potvrdi da je high_priority
3. `test_scan_all_obrtnik_2_djece` — 2 djece, provjeri ukupnu uštedu
4. `test_jls_zagreb_vs_osijek` — Zagreb 23.6% vs Osijek 10% — razlika na 50k prihoda = 6.800€
5. `test_ai_advisor_returns_string` — mock Haiku, provjeri da vraća ne-prazni string

---

## DONE kriterij

```python
from tax_wizard.deductions import scan_all
from tax_wizard.models import TaxWizardSession
s = TaxWizardSession(taxpayer_type='zaposleni', tax_year=2025)
s.step_data = {'djeca_broj': 2, 'dob': 2003, 'bio_inozemstvo': True}
result = scan_all(s)
assert result['count'] >= 4  # mladi + 2 djece + iseljenik
assert len(result['high_priority']) >= 2
print(f"GEMINI F2 DONE: {result['count']} olakšica, {result['total_savings']}€ ušteda")
```
