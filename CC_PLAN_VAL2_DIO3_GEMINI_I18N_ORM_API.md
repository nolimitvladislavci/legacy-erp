# VAL 2 — DIO 3: I18N 100% + ORM DEEP + API DOCS (GEMINI/SONNET)
> Tri paralelna toka: prijevodi, performance, dokumentacija

## CILJ A: i18n 100% coverage svih 5 jezika (1,453 praznih → 0)
## CILJ B: ORM optimization 10% → 40%+ (synesis, delivery, registration prioritet)
## CILJ C: OpenAPI full coverage (15 → 100+ annotations)

---

## A. I18N COMPLETION (1,453 praznih → 0)

### Trenutno stanje:
```
DE: 205 praznih (97.0% coverage)
EN: 104 praznih (98.5% coverage)
HR: 403 praznih (94.1% coverage)
EL: 389 praznih (94.3% coverage)
TR: 352 praznih (94.8% coverage)
```

### Pristup:
1. Extraktuj sve prazne msgstr iz svakog .po fajla
2. Koristi DeepL API (već integriran) za batch prijevod
3. Review i unos u .po fajlove
4. `python manage.py compilemessages`

### Prioritet:
1. **HR** (403) — matični jezik, mora biti 100%
2. **DE** (205) — ključno tržište
3. **EN** (104) — internacionalni
4. **EL** (389) — grčko tržište
5. **TR** (352) — tursko tržište

### Skripta za batch:
```python
# scripts/fill_translations.py
# Za svaki prazan msgstr:
# 1. Uzmi msgid (engleski/hrvatski original)
# 2. Prevedi DeepL-om na ciljni jezik
# 3. Upiši u .po fajl
# 4. Compilemessages
```

---

## B. ORM DEEP OPTIMIZATION

### Najgori appovi (ORM pozivi : optimizacije):
```
synesis/   179 : 4  = 2%  — KRITIČNO
worktime/  316 : 20 = 6%
invoicing/ 291 : 18 = 6%
appointments/ 139 : 9 = 6%
registration/ 125 : 8 = 6%
companies/ 113 : 10 = 9%
```

### Za svaki app:
1. Otvori views.py
2. Nađi svaki queryset bez select_related/prefetch_related
3. Pogledaj template — koji FK se dereferenciraju?
4. Dodaj odgovarajući select_related/prefetch_related
5. Za list views: dodaj .only() za subset polja
6. Za dashboard: koristi annotate/aggregate umjesto Python petlji
7. count()>0 → exists()

### Dodatno: django-debug-toolbar info
```python
# Dodaj u settings (DEBUG only):
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
```

---

## C. API DOCUMENTATION (OpenAPI/Swagger)

### Trenutno: 15 drf_spectacular referenci
### Cilj: Svaki DRF ViewSet/APIView ima @extend_schema

### Koraci:
1. Pronađi sve DRF ViewSet/APIView klase
2. Dodaj @extend_schema dekoratore s:
   - description
   - request/response serializers
   - tags (po modulu)
3. Konfiguriraj spectacular za auto-schema

### URL za docs:
```python
# core/urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
urlpatterns += [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
```

## NE DIRATI:
- Modele / abstract klase (DIO 1)
- Exception handling (DIO 2)
- csrf_exempt (DIO 2)

## METRIKA USPJEHA
- Empty translations: 1,453 → 0
- select_related/prefetch: 964 → 1,500+
- OpenAPI annotations: 15 → 100+
- API docs accessible at /api/docs/
