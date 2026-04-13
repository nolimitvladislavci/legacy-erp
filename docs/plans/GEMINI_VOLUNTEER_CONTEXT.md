# Gemini Context — Volonterski modul
# Za: is_volunteer_work, grant_monetary_value, AI porezni inspektor

---

## TimeEntry model (worktime/models.py)

```python
class TimeEntry(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Skica'), ('PENDING', 'Na čekanju'),
        ('APPROVED', 'Odobreno'), ('REJECTED', 'Odbijeno'),
    ]
    TASK_TYPES = [
        ('DEVELOPMENT', 'Razvoj'), ('DESIGN', 'Dizajn'),
        ('MEETING', 'Sastanak'), ('SUPPORT', 'Podrška'),
        ('ADMIN', 'Administracija'), ('TESTING', 'Testiranje'),
        ('PLANNING', 'Planiranje'), ('TRAINING', 'Edukacija'),
        ('TRAVEL', 'Putovanje'), ('OTHER', 'Ostalo'),
    ]
    company = FK(Company)
    user = FK(User)
    project = FK(Project)
    date = DateField (indexed)
    start_time = TimeField (nullable)
    end_time = TimeField (nullable)
    duration = Decimal (hours)
    description = TextField
    task_type = CharField (choices above)
    status = CharField (DRAFT/PENDING/APPROVED/REJECTED)
    billing_amount = Decimal
    is_billed = Boolean
    is_overtime = Boolean
    invoice = FK(Invoice, nullable)
    approved_by = FK(User, nullable)
    from_timer = Boolean
    
    # Zakonski (HR NN 55/24 + DE ArbZG)
    ABSENCE_TYPES = [ANNUAL, SICK, PAID, UNPAID, HOLIDAY, PATERNITY]
    
    # NEMA: is_volunteer_work, grant_monetary_value — TO TREBA DODATI
```

## EmployeeProfile model

```python
class EmployeeProfile(models.Model):
    company = FK(Company)
    user = OneToOne(User)
    employee_id = CharField
    tax_id = CharField (OIB, 11 chars)
    hourly_rate = Decimal (default 20.00)
    overtime_rate = Decimal (default 30.00)
    phone, address, bank_account (IBAN)
    department, position
    date_hired = DateField
    weekly_hours = Decimal (default 40.00)
    daily_hours = Decimal (default 8.00)
    work_group = FK(WorkGroup)
    is_manager = Boolean
    
    # NEMA: is_volunteer, volunteer_hourly_value — TO TREBA DODATI
```

## TravelOrder model

```python
class TravelOrder(models.Model):
    STATUS = draft / approved / completed / cancelled
    TRANSPORT = car_personal / car_company / bus / train / plane / other
    
    company = FK(Company)
    employee = FK(User)
    order_number = CharField (PN-2026-0001)
    destination, purpose
    departure_date, return_date
    # ... troškovi, dnevnice, kilometraža
    
    # NEMA: is_volunteer_expense — TO TREBA DODATI za limit provjeru
```

## Payroll calculate_payslip()

```python
def calculate_payslip(payroll_run, user):
    """
    Agregira TimeEntry(status='APPROVED') za period.
    Računa bruto: sati × satnica (EmployeeProfile).
    HR: hr_calculate_net()
    DE: neto = bruto (DATEV)
    
    PROBLEM: Ne razlikuje volontere od zaposlenika!
    Ako volonter ima TimeEntry, sustav će pokušati izračunati plaću.
    """
    agg = TimeEntry.objects.filter(
        company=payroll_run.company,
        user=user, status='APPROVED',
        date__range=(period_start, period_end),
    ).aggregate(
        total_regular=Sum('regular_hours'),
        total_overtime=Sum('overtime_hours'),
        total_night=Sum('night_hours'),
    )
```

## AnomalyReport model

```python
class AnomalyReport(models.Model):
    SEVERITY = low / medium / high
    ANOMALY_TYPES = [
        GHOST_SHIFT, NO_ACTIVITY, GPS_MISMATCH,
        OVERTIME, MISSING_BREAK, DOUBLE_SHIFT,
    ]
    # NEMA: VOLUNTEER_LIMIT_EXCEEDED — TO TREBA DODATI
```

---

## Što treba implementirati za volontere

### 1. TimeEntry nova polja:
- `is_volunteer_work` = BooleanField(default=False)
- `grant_monetary_value` = Decimal (sat × EU satnica projekta)
- `grant_project_code` = CharField (EU fond referenca)

### 2. EmployeeProfile nova polja:
- `is_volunteer` = BooleanField(default=False)
- `volunteer_hourly_value` = Decimal (default 5.00 EUR za EU fondove)
- `volunteer_annual_limit` = Decimal (neoporezivi godišnji limit)

### 3. TravelOrder:
- `is_volunteer_expense` = BooleanField
- AI guard: provjeri godišnji limit prije odobrenja

### 4. Payroll exclusion:
- calculate_payslip() mora skip-ati volontere (is_volunteer=True)

### 5. AI anomaly types:
- VOLUNTEER_LIMIT_EXCEEDED — prelazak godišnjeg neoporezivog limita
- VOLUNTEER_MISSING_CONTRACT — volonter radi bez ugovora

### 6. Godišnje izvješće:
- Export za Ministarstvo rada: broj volontera, sati, dobne skupine, aktivnosti

---

## Postojeća arhitektura za kontekst

- Company.fiscal_exempt ✓ (upravo dodano)
- Company.is_nonprofit property ✓ (drugi CC dodao)
- POSReceiptItem.is_nonprofit_activity ✓ (drugi CC dodao)
- CheckoutService — mixed validation ✓ (upravo dodano)
- worktime.tracker.track() — fire-and-forget ActivityEvent logging
- AnomalyReport + nightly patrol task — Claude Haiku AI analiza
- Device Token login — unified bridge (TimeLog + WaiterShift + Cashier)
