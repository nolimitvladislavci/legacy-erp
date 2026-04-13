# VAL 2 — DIO 1: ABSTRACT MODELI + CODE DEDUPLICATION (OPUS)
> Najzahtjevniji — zahtijeva razumijevanje svih 625 tablica i pattern extraction

## CILJ
Kreirati 10+ abstract base modela i eliminirati code duplication across 85 appova.
Smanjiti ukupni Python LoC za 10-15% bez gubitka funkcionalnosti.

## SCOPE

### Faza 1: Analiza dupliciranih polja across modela
Pregledati SVE models.py i identificirati polja koja se ponavljaju u 5+ modela:
- `company = ForeignKey(Company)` — gotovo svaki model
- `created_at = DateTimeField(auto_now_add=True)`
- `updated_at = DateTimeField(auto_now=True)`
- `created_by = ForeignKey(User)`
- `is_active = BooleanField(default=True)`
- `notes/description = TextField(blank=True)`
- `status = CharField(choices=...)`
- `amount/total = DecimalField`

### Faza 2: Kreiranje abstract modela u core/
```python
# core/base_models.py

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class CompanyOwnedModel(TimestampedModel):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    class Meta:
        abstract = True

class UserTrackedModel(CompanyOwnedModel):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    class Meta:
        abstract = True

class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        abstract = True
    def soft_delete(self):
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=['is_active', 'deactivated_at'])

class AuditableModel(UserTrackedModel, SoftDeleteModel):
    """Full audit trail: company + user + timestamps + soft delete."""
    class Meta:
        abstract = True
```

### Faza 3: Refactoring top 10 najvećih models.py
Po prioritetu (linije koda):
1. udruge/models.py — 3,062 linija (splitati u 3-4 fajla)
2. pos/models.py — 1,849 linija
3. delivery/models.py — 1,666 linija
4. inventory/models.py — 1,469 linija
5. companies/models.py — 1,161 linija
6. tax_wizard/models.py — 960 linija
7. marketplace/models.py — 918 linija
8. worktime/models.py — 917 linija
9. experiences/models.py — 890 linija
10. documents/models.py — 784 linija

### Faza 4: Common manager/queryset patterns
```python
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class CompanyScopedManager(ActiveManager):
    def for_company(self, company):
        return self.get_queryset().filter(company=company)
```

## PRAVILA
- NEMA schema promjena — abstract modeli ne generiraju migracije
- Svaka promjena mora proći `python manage.py makemigrations --check` (no new migrations)
- Svaka promjena mora proći `python manage.py check`
- NE DIRATI: views, templates, URLs, signals — samo models.py

## NE DIRATI (scope drugih timova):
- Preostale broad catches (DIO 2)
- csrf_exempt (DIO 2)
- ORM optimizacije u viewsima (DIO 3)

## METRIKA USPJEHA
- Abstract modeli: 2 → 10+
- Duplicate field definitions: -30%
- udruge/models.py: 3,062 → <1,500 (split + abstract)
- 0 novih migracija
- Django check: 0 issues
