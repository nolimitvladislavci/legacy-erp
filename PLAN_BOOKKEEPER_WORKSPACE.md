# PLAN: Radno Mjesto Knjigovodstva — 10/10

## VIZIJA
Jedan ekran koji knjigovodji daje SVE: klijente, rokove, dokumente, knjiženja, porezne prijave.
Ne navigacija po 15 stranica — jedan kokpit s akcijama.

## GAP ANALIZA (trenutno vs cilj)

### POSTOJI (solidno):
- Konto modul: kontni plan, temeljnice, banka, P&L, bilanca
- Arhiva: 10+ source_type, AI bookkeeper, audit trail
- Tax reports: PDV, USt-VA, SAF-T, DATEV, EÜR, JOPPD
- Workspace model: clients M2M, workers M2M
- CompanyMembership: multi-company access
- Synesis bridge: legacy import

### NEDOSTAJE (kritično):
1. **Bookkeeper Dashboard** — nema unified pregled svih klijenata
2. **Tax Calendar** — nema rokova/deadlinea (PDV 20., JOPPD kvartal, godišnji)
3. **Client Health Score** — nema compliance scoring per client
4. **Quick Booking Stream** — nema cross-client unbooked document queue
5. **Filing Workflow** — prepare → review → file → confirm
6. **Onboarding Wizard** — dodavanje novog komitenta
7. **Workspace type 'accounting'** — dedicated bookkeeper mode

## ARHITEKTURA

### Novi fajlovi:
```
konto/
  bookkeeper_dashboard.py   — Dashboard view + context
  tax_calendar.py           — Deadline engine + calendar view
  filing_workflow.py        — Tax filing state machine
  client_health.py          — Compliance score calculator
  templates/konto/
    bookkeeper_dashboard.html
    tax_calendar.html
    filing_detail.html
    client_card.html (partial)
```

### URL-ovi:
```
/konto/workspace/                → Bookkeeper Dashboard (glavni ekran)
/konto/workspace/calendar/       → Tax Calendar (rokovi)
/konto/workspace/unbooked/       → Quick Booking Stream (svi klijenti)
/konto/workspace/client/<id>/    → Client Detail Card
/konto/workspace/filing/<id>/    → Tax Filing Detail
/konto/workspace/onboard/        → New Client Wizard
```

### Model proširenja:
```python
# konto/models.py — dodati:

class TaxFiling(models.Model):
    """Porezna prijava — lifecycle tracking."""
    company = FK(Company)
    period = FK(TaxPeriod)
    filing_type = CharField  # PDV, JOPPD, PD, USt-VA, EÜR
    status = CharField       # DRAFT → PREPARED → REVIEWED → FILED → CONFIRMED
    prepared_by = FK(User)
    reviewed_by = FK(User)
    filed_at = DateTimeField
    filing_reference = CharField  # FINA/ePU reference number
    xml_file = FileField
    pdf_file = FileField
    notes = TextField

class TaxDeadline(models.Model):
    """Zakonski rok za predaju."""
    company = FK(Company)
    filing_type = CharField
    period_year = IntegerField
    period_month = IntegerField
    deadline_date = DateField
    is_completed = BooleanField
    completed_at = DateTimeField
    days_remaining = property  # computed
```

## PRIORITET IMPLEMENTACIJE:
1. TaxDeadline + TaxFiling modeli + migracija
2. Bookkeeper Dashboard view (sve klijente, health score, unbooked count)
3. Tax Calendar view (rokovi, upcoming filings)
4. Quick Booking Stream (cross-client unbooked docs)
5. Filing workflow (prepare → file)
6. Template dizajn (responsive, dark/light)
