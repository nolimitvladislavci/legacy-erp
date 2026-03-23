# GEMINI_TASK: Knowledge Graph — NKD NULL firme + confidence boost
## Agent: Gemini Pro 2.5 | Prioritet: P1 | Datum: 2026-03-23

## Kontekst
- NKD retroaktivni lookup završen: 47/86 firmi ima NKD (55%)
- 39 firmi preostaje s NKD=NULL — preopći nazivi (osobna imena, "Test", "Debug")
- Knowledge Graph confidence je niži za firme bez NKD
- `match_opportunities_for_company()` radi ali s lower precision

## Zadatak 1 — Analiza preostalih 39 firmi
```python
from companies.models import Company
no_nkd = Company.objects.filter(
    nkd_code__isnull=True
).exclude(oib__startswith='DRAFT')
for c in no_nkd:
    print(f'{c.name} | OIB: {c.oib} | active: {c.is_active if hasattr(c,"is_active") else "?"}')
```
Identificiraj koliko je aktivnih vs neaktivnih/test firmi.

## Zadatak 2 — Haiku batch inference za preostalih 39
Pozovi `_haiku_infer_nkd()` iz `partners/tasks.py` ali s nižim confidence pragom (0.5):
```python
# Za firme gdje naziv ima >= 5 znakova — pokušaj s confidence >= 0.5
# Za firme s < 5 znakova naziva (Test, Debug) → ostavi NULL, to su test firme
```
Logika: bolje pogoditi 60% nego ostaviti NULL.

## Zadatak 3 — ImpactDomain bez NKD (fallback)
Čitaj `limit_connect_ai/models_knowledge_graph.py`:
```bash
grep -n "ImpactDomain\|nkd_section\|match_opportunities" \
  /var/www/fina-connect/limit_connect_ai/models_knowledge_graph.py
```
Provjeri `match_opportunities_for_company()` — postoji li fallback kad nkd_code=NULL?
Ako ne — dodaj: "ako nema NKD, matchaj sve opportunities bez NKD filtera ali s
`confidence_score` sniženim za 30%".

## Zadatak 4 — Knowledge Graph summary za Mariju
Kreiraj management command koji generira tekstualni report:
```bash
python manage.py kg_summary
```
Output:
```
=== Knowledge Graph Summary ===
Firme: 86 ukupno | 47 s NKD (55%) | 39 bez NKD
Opportunities: 11 aktivnih
Matches: 932 ukupno
  Visoki confidence (>70%): X
  Srednji (50-70%): X
  Niski (<50%): X

Top 5 opportunities po vrijednosti:
  1. [naziv] — €X potencijal — X firmi matchano
  ...

Firme bez ijednog matcha: X
```

## Čitaj FENIX_STATUS.md i BORG_FENIX_MASTER_PLAN.md prije početka.

## Commit poruka
`KG: NKD fallback confidence, ImpactDomain bez NKD, kg_summary command`
