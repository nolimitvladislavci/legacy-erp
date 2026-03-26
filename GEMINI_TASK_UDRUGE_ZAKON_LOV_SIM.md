# GEMINI TASK: Udruge — Zakonska analiza + POS simulacije
## Agent: Gemini 2.5 Flash | Prioritet: VISOK | Datum: 2026-03-26

## MISIJA

Dvije paralelne zadaće:

### Zadaća A: Zakonska analiza svih tipova udruga u sustavu
Analiziraj `udruge/models.py` i za svaki segment utvrdi:
1. Koji propisi pokrivaju taj tip organizacije (NN brojevi)
2. Što postoji u kodu vs. što zakon zahtijeva
3. Kritične praznine (nedostajuće evidencije koje zakon propisuje)

Fokus na ove tipove:
- **Branitelji** — Zakon NN 121/17, 156/23 + Pravilnik NN 127/21
- **Lovci** — Zakon o lovstvu + Pravilnik NN 48/22 + SLE od 05.06.2025.
- **Ribolov** — Pravilnik o športskom ribolovu NN 122/19 (je li Obrazac UL implementiran?)
- **Pčelarstvo** — AGRONET/ARKOD obveze (premije EU)
- **Rakija/destilacija** — Carinski zakon, Zakon o trošarinama
- **KUD** — Zakon o udrugama + prijavljivanje priredbi MKO
- **DVD** — Zakon o vatrogastvu NN 125/19
- **Zadruge** — Zakon o zadrugama NN 76/14 (zadruga ≠ udruga — evidencija zadrugara)

### Zadaća B: POS simulacijska skripta — popravak i izvršavanje
```bash
cat scripts/pos_sim_all.py
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from pos.models import POSReceipt
f = POSReceipt._meta.get_field('receipt_number')
print('receipt_number type:', f.__class__.__name__)
from pos.models import POSSession
print('session_number type:', POSSession._meta.get_field('session_number').__class__.__name__)
"
```

Popravi skriptu (nagazne mine: receipt_number je PositiveIntegerField, ne string) i pokreni sve 6 scenarija do kraja. Spremi rezultate u `/var/www/fina-connect/POS_SIM_REPORT_20260326.md`.

## Pristup serveru
Koristiš GeminiAgent tools:
- `read_file(path)` — čitanje fajlova
- `write_file(path, content)` — pisanje fajlova
- `run_command(cmd)` — shell komande
- `query_db(sql)` — direktni SQL upiti

## Output
1. `/var/www/fina-connect/UDRUGE_ZAKON_ANALIZA.md` — zakonska analiza svih segmenata
2. `/var/www/fina-connect/POS_SIM_REPORT_20260326.md` — rezultati POS simulacije svih 6 scenarija
3. Ako nađeš kritičnu prazninu → napiši CC_TASK za popravak u `/var/www/fina-connect/`

## Napomena
- Ne diraj produkcijske podatke — simulacija koristi is_training=True
- Ne mijenjaj models.py — samo analiza i skripta
- Zakonske reference provjeri u bazi FENIX Intelligence: `SELECT * FROM limit_connect_ai_regulatoryupdate WHERE category IN ('LABOUR','CORP','NONPROFIT') ORDER BY impact_score DESC LIMIT 10`
