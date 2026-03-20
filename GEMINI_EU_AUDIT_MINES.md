# Gemini EU Audit — 3 Nagazne Mine
## Za implementaciju u LIMIT Connect

---

## Trenutno stanje (već implementirano od drugog CC):

### EmployeeProfile (worktime/models.py):
```python
is_volunteer = BooleanField(default=False)
volunteer_hourly_value = Decimal(default=5.00)  # EU satnica
volunteer_annual_limit = Decimal(default=238.90)  # Neoporezivi godišnji limit
volunteer_contract_date = DateField(nullable)

@property
def is_volunteer_active(self):
    return self.is_volunteer and self.volunteer_contract_date is not None
```

### TimeEntry:
```python
is_volunteer_work = BooleanField(default=False)
grant_monetary_value = Decimal  # Automatski: sati × volunteer_hourly_value
grant_project_code = CharField  # EU fond referenca
```

### VolunteerTaxGuard (worktime/services/volunteer_guard.py):
```python
class VolunteerTaxGuard:
    @classmethod
    def check_expense(cls, travel_order):
        """Provjerava godišnji limit neoporezive isplate za volontera."""
        # Zbraja sve completed TravelOrder za tekuću godinu
        # Uspoređuje s profile.volunteer_annual_limit
        # Ako prelazi → BLOKADA + AnomalyReport
        return (bool, str)
```

### Project model:
```python
code = CharField(max_length=20, unique=True)  # npr. "ESF-2026-001"
name = CharField(max_length=200)
hourly_rate = Decimal(default=25.00)
budget_hours = Decimal(nullable)  # Budžet u satima
is_billable = BooleanField(default=True)
members = M2M(User)

# NEMA: is_eu_funded, eu_grant_reference, max_monthly_hours
```

---

## 3 NAGAZNE MINE — Što nedostaje:

### MINA 1: Double-Dipping detekcija
**Problem**: Volonter radi na Projektu A od 08:00-12:00 i netko mu upiše Projekt B od 11:00-15:00 → EU revizor automatski detektira preklapanje → projekt odbijen, novac vrati.

**Rješenje**: Prije generiranja EU timesheeta (i pri save() TimeEntry):
```python
# Pseudokod — provjera preklapanja
conflicting = TimeEntry.objects.filter(
    user=entry.user,
    date=entry.date,
    start_time__lt=entry.end_time,
    end_time__gt=entry.start_time,
).exclude(pk=entry.pk)
if conflicting.exists():
    raise ValidationError('DOUBLE_DIPPING: Preklapanje s %s' % conflicting.first())
```

**Status**: NE POSTOJI — treba implementirati

---

### MINA 2: Mjesečni fond sati limit (Pravilo 100%)
**Problem**: Osoba ne smije prijaviti više od mjesečnog fonda sati (~160-176h ovisno o mjesecu). EU revizor zbroji SVE projekte za osobu u mjesecu → ako prelazi fond → reject.

**Rješenje**: Prije exporta EU timesheeta:
```python
# Zbroji SVE TimeEntry za korisnika u mjesecu (svi projekti)
total_month = TimeEntry.objects.filter(
    user=user, date__year=year, date__month=month, status='APPROVED'
).aggregate(Sum('duration'))['duration__sum'] or 0

MAX_MONTHLY = 176  # ili izračunati iz radnih dana × 8h
if total_month > MAX_MONTHLY:
    # Blokiraj export, označi crvenom
    raise ValidationError('Mjesečni fond prekoračen: %sh / %sh' % (total_month, MAX_MONTHLY))
```

**Status**: NE POSTOJI — treba implementirati

---

### MINA 3: EU Potpisni blok (Audit Trail)
**Problem**: EU Timesheet bez potpisnog bloka s timestampom odobrenja je bezvrijedan papir.

**Rješenje**: PDF generator mora sadržavati:
```
────────────────────────────────────────────────
Potpis volontera: ___________________________
Ime: Ivan Horvat | OIB: 12345678901
Datum potpisa: __.__.2026.

Potpis voditelja projekta: ___________________________
Ime: Marija Kovačević | Pozicija: Voditelj projekta
Datum odobrenja: 15.03.2026. 14:32:15 (iz sustava — approved_at)

Izjavljujem pod kaznenom i materijalnom odgovornošću
da su navedeni sati stvarno odrađeni na navedenom projektu.

Generirano: 19.03.2026. 22:45:00 | LIMIT Connect v2026.03
Referenca: ESF-2026-001 | Period: 01.03.-31.03.2026.
────────────────────────────────────────────────
```

**Status**: NE POSTOJI — treba implementirati

---

## Preporuka za implementaciju:

### Prioritet 1: Double-Dipping (TimeEntry.clean() + signal)
- Dodati u TimeEntry.clean() metodu
- Poziva se automatski pri save()
- Blokira preklapanje PRIJE upisa u bazu

### Prioritet 2: Mjesečni fond (EU Timesheet Generator)
- Provjera pri generiranju PDF-a
- Flag na TimeEntry: `monthly_cap_exceeded = BooleanField`
- Crvena oznaka u sustavu

### Prioritet 3: Potpisni blok (PDF template)
- Dodati u xhtml2pdf template
- `approved_by`, `approved_at` već postoje na TimeEntry
- Klauzula o odgovornosti hardkodirana u template

### Project model — nova polja:
```python
is_eu_funded = BooleanField(default=False)
eu_grant_reference = CharField(max_length=50, blank=True)  # npr. "ESF.5.2.1."
eu_max_monthly_hours = DecimalField(default=176)  # mjesečni fond
eu_volunteer_hourly_rate = DecimalField(default=8.00)  # satnica za in-kind
```
