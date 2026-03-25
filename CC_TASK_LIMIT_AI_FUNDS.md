# CC_TASK_LIMIT_AI_FUNDS — EU Fondovi workflow (Faza 2)
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-25

**Čitaj prvo:** FENIX_STATUS.md, EU_FONDOVI_MASTER_MATRIX.md,
LIMIT_CONNECT_AI_PLAN.md (Faza 2), limit_connect_ai/models.py

---

## Kontekst

Svaka korisnička grupa ima specifične EU/državne prilike:
- Pčelari → APPRRR intervencije (100% refundacija opreme)
- Rental → EAFRD ruralni turizam, MINT natječaji
- Udruge → ESF+, CERV, Erasmus+
- OPG → IPARD III, EAFRD, izravna plaćanja
- MSP → ERDF digitalizacija, HAMAG-BICRO, HZZ
- DE klijenti → BAFA, KfW, § 7g EStG

Cilj: Korisnik ne traži fondove. LIMIT Connect ih nalazi i priprema prijavu.

---

## ZADATAK 1 — Provjeri i proširi FundOpportunity model

Fajl: `intelligence/models.py` — pronađi FundOpportunity, provjeri polja:

```python
# Dodaj ako ne postoje:
class FundOpportunity(models.Model):
    # ... (provjeri što već postoji)

    # NOVA POLJA ako nedostaju:
    client_segments = models.JSONField(
        default=list,
        verbose_name='Relevantni segmenti',
        help_text='["opg_pcela", "rental", "udruga", "msp", "de_klijent", "opg"]'
    )
    jurisdiction = models.CharField(
        max_length=5, choices=[('HR','HR'),('EU','EU'),('DE','DE')],
        default='HR'
    )
    fund_body = models.CharField(
        max_length=200, blank=True,
        verbose_name='Tijelo (APPRRR, eKohezija, BAFA...)'
    )
    max_amount_eur = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Maksimalni iznos (EUR)'
    )
    refund_percent = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='% povrata (npr. 100 za APPRRR)'
    )
    min_requirement = models.TextField(
        blank=True,
        verbose_name='Minimalni uvjeti',
        help_text='npr. "min. 30 košnica, ažurirani EPP"'
    )
    application_url = models.URLField(blank=True)
    source_url = models.URLField(blank=True, verbose_name='Izvor informacija')
    is_recurring = models.BooleanField(
        default=False,
        verbose_name='Ponavljajući natječaj',
        help_text='True za godišnje APPRRR intervencije'
    )
```

Migracija: `venv/bin/python manage.py makemigrations intelligence`

---

## ZADATAK 2 — FundApplicationDraft workflow

Provjeri postoji li model u `limit_connect_ai/models.py`.
Ako ne postoji, kreiraj:

```python
class FundApplicationDraft(models.Model):
    STATUS_CHOICES = [
        ('draft',           'Nacrt'),
        ('review_pending',  'Čeka review'),
        ('approved',        'Odobreno za slanje'),
        ('submitted',       'Predano'),
        ('rejected',        'Odbijeno'),
        ('funded',          'Odobreno financiranje'),
    ]

    company           = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                           related_name='fund_drafts')
    opportunity       = models.ForeignKey('intelligence.FundOpportunity',
                                           on_delete=models.CASCADE, null=True, blank=True)
    title             = models.CharField(max_length=200)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    eligibility_score = models.PositiveSmallIntegerField(default=0,
                                                          help_text='0-100, AI procjena')
    eligibility_notes = models.TextField(blank=True)
    # Predpopunjena polja iz Company podataka
    draft_content     = models.JSONField(default=dict,
                                          help_text='Predpopunjena aplikacijska polja')
    # Dokumenti koji se trebaju priložiti
    required_docs     = models.JSONField(default=list,
                                          help_text='Popis potrebnih dokumenata')
    # Veze na R1 račune (za APPRRR)
    linked_invoices   = models.ManyToManyField('invoicing.Invoice', blank=True,
                                                related_name='fund_applications')
    amount_requested  = models.DecimalField(max_digits=12, decimal_places=2,
                                             null=True, blank=True)
    amount_approved   = models.DecimalField(max_digits=12, decimal_places=2,
                                             null=True, blank=True)
    deadline          = models.DateField(null=True, blank=True)
    submitted_at      = models.DateTimeField(null=True, blank=True)
    reviewed_by       = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                           on_delete=models.SET_NULL)
    notes             = models.TextField(blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'EU/Državna aplikacija'
        verbose_name_plural = 'EU/Državne aplikacije'

    def __str__(self):
        return f'{self.company.name} — {self.title} ({self.get_status_display()})'
```

---

## ZADATAK 3 — AI Eligibility Check

Fajl: `limit_connect_ai/fund_checker.py` (novi fajl):

```python
"""
AI Eligibility Checker — procjenjuje prihvatljivost tvrtke za EU/državni fond.
Lokalna heuristika + Haiku fallback.
"""
from decimal import Decimal


SEGMENT_RULES = {
    'opg_pcela': {
        'checks': [
            lambda co: hasattr(co, 'apiaries') and co.apiaries.filter(aktivan=True).exists(),
            lambda co: sum(a.broj_kosnica for a in co.apiaries.filter(aktivan=True)) > 0,
        ],
        'bonus_30_hives': lambda co: sum(
            a.broj_kosnica for a in co.apiaries.filter(aktivan=True)
        ) >= 30,
    },
    'rental': {
        'checks': [
            lambda co: co.business_type in ['opg', 'obrt', 'doo'],
        ],
    },
    'udruga': {
        'checks': [
            lambda co: co.business_type in ['udruga', 'zadruga', 'ustanova'],
        ],
    },
}


def check_eligibility(company, opportunity) -> dict:
    """
    Lokalna procjena — bez AI za poznate uvjete.
    Vraća: {score: 0-100, notes: str, auto_create_draft: bool}
    """
    score = 50  # Base score
    notes = []
    segment = opportunity.client_segments[0] if opportunity.client_segments else 'msp'

    # Provjeri registraciju
    if company.oib:
        score += 10
        notes.append('✓ OIB registriran')
    else:
        notes.append('✗ Nedostaje OIB')
        score -= 20

    # Provjeri segment
    if segment == 'opg_pcela':
        try:
            apiaries = company.apiaries.filter(aktivan=True)
            total_hives = sum(a.broj_kosnica for a in apiaries)
            if total_hives >= 30:
                score += 30
                notes.append(f'✓ {total_hives} košnica (min. 30 ispunjeno)')
            elif total_hives > 0:
                score += 10
                notes.append(f'⚠ {total_hives} košnica (potrebno 30 za opremu)')
            else:
                notes.append('✗ Nema evidentiranih košnica')
                score -= 30
        except Exception:
            notes.append('? Košnice nisu evidentirane u sustavu')

    elif segment == 'udruga':
        if company.business_type in ['udruga', 'zadruga']:
            score += 30
            notes.append(f'✓ Poslovni tip: {company.business_type}')
        else:
            score -= 20
            notes.append('✗ Nije udruga/zadruga')

    elif segment == 'rental':
        # Provjeri eVisitor/Rental modul
        if hasattr(company, 'pos_terminals'):
            score += 15
            notes.append('✓ Aktivan u sustavu')

    # Rokovi
    from django.utils import timezone
    if opportunity.deadline:
        days_left = (opportunity.deadline - timezone.now().date()).days
        if days_left < 0:
            score = 0
            notes.append('✗ Rok je prošao')
        elif days_left < 7:
            notes.append(f'⚠ Samo {days_left} dana do roka!')
        else:
            notes.append(f'✓ Rok: {opportunity.deadline} ({days_left} dana)')

    score = max(0, min(100, score))

    return {
        'score': score,
        'notes': '\n'.join(notes),
        'auto_create_draft': score >= 60,
    }
```

---

## ZADATAK 4 — Views i URL-ovi

Fajl: `limit_connect_ai/fund_views.py` (ili dodaj u views.py):

```python
@login_required
def fund_opportunities(request):
    """Lista EU/državnih prilike relevantnih za tvrtku."""
    company = request.user.profile.company

    # Odredi segment
    segment_map = {
        'udruga': 'udruga', 'zadruga': 'udruga',
        'opg': 'opg', 'sopg': 'opg',
    }
    segment = segment_map.get(company.business_type, 'msp')

    # Provjeri je li pčelar
    if hasattr(company, 'apiaries') and company.apiaries.filter(aktivan=True).exists():
        segment = 'opg_pcela'

    # Provjeri je li rental
    if hasattr(company, 'rental_properties'):
        segment = 'rental'

    from intelligence.models import FundOpportunity
    from django.utils import timezone

    opportunities = FundOpportunity.objects.filter(
        active=True,
        client_segments__contains=segment,
    ).order_by('deadline', '-max_amount_eur')[:20]

    from limit_connect_ai.models import FundApplicationDraft
    my_drafts = FundApplicationDraft.objects.filter(company=company).order_by('-created_at')[:5]

    return render(request, 'limit_connect_ai/fund_opportunities.html', {
        'opportunities': opportunities,
        'my_drafts':    my_drafts,
        'segment':      segment,
        'company':      company,
    })


@login_required
def fund_draft_create(request, opportunity_id):
    """Kreiraj FundApplicationDraft s predpopunjenim podacima."""
    from intelligence.models import FundOpportunity
    from limit_connect_ai.fund_checker import check_eligibility
    from limit_connect_ai.models import FundApplicationDraft

    company     = request.user.profile.company
    opportunity = get_object_or_404(FundOpportunity, pk=opportunity_id)
    eligibility = check_eligibility(company, opportunity)

    # Predpopuni iz Company podataka
    draft_content = {
        'naziv_prijavitelja': company.name,
        'oib':                company.oib,
        'adresa':             getattr(company, 'address', ''),
        'iban':               getattr(company, 'iban', ''),
        'kontakt_email':      getattr(company, 'email', ''),
        'opis_projekta':      f'[AI draft - {opportunity.title}]',
    }

    # Pronađi relevantne R1 račune (za APPRRR)
    linked_invoices = []
    if 'opg_pcela' in (opportunity.client_segments or []):
        from invoicing.models import Invoice
        linked_invoices = list(
            Invoice.objects.filter(
                company=company,
                status__in=['sent', 'paid'],
            ).order_by('-date_issued')[:20].values_list('id', flat=True)
        )

    draft = FundApplicationDraft.objects.create(
        company=company,
        opportunity=opportunity,
        title=f'{opportunity.title} — {company.name}',
        eligibility_score=eligibility['score'],
        eligibility_notes=eligibility['notes'],
        draft_content=draft_content,
        deadline=opportunity.deadline,
        required_docs=getattr(opportunity, 'required_docs', []),
    )
    if linked_invoices:
        draft.linked_invoices.set(linked_invoices)

    return redirect('limit_connect_ai:fund_draft_detail', pk=draft.pk)
```

URL-ovi (dodaj u `limit_connect_ai/urls.py`):
```python
path('funds/',                           fund_views.fund_opportunities,   name='fund_opportunities'),
path('funds/draft/<int:opportunity_id>/',fund_views.fund_draft_create,    name='fund_draft_create'),
path('funds/draft/<int:pk>/detail/',     fund_views.fund_draft_detail,    name='fund_draft_detail'),
```

---

## ZADATAK 5 — Cockpit widget "EU Prilike"

U dashboard template (ili cockpit view context), dodaj:

```python
from intelligence.models import FundOpportunity
from django.utils import timezone

context['fund_alerts'] = FundOpportunity.objects.filter(
    active=True,
    deadline__gte=timezone.now().date(),
    client_segments__contains=detected_segment,
).order_by('deadline')[:3]
```

Template snippet:
```html
{% if fund_alerts %}
<div class="stat-card mb-3">
  <div class="d-flex align-items-center gap-2 mb-2">
    <span style="font-size:1.2rem">🏛️</span>
    <strong>EU / Državne prilike</strong>
    <span class="badge bg-warning text-dark ms-auto">{{ fund_alerts|length }} aktivno</span>
  </div>
  {% for fund in fund_alerts %}
  <div class="d-flex justify-content-between align-items-center py-1
              border-bottom border-secondary" style="font-size:.83rem">
    <div>
      <div class="text-white">{{ fund.title|truncatechars:45 }}</div>
      <div class="text-muted small">{{ fund.fund_body }} · max {{ fund.max_amount_eur|floatformat:0 }} EUR</div>
    </div>
    <a href="{% url 'limit_connect_ai:fund_draft_create' fund.pk %}"
       class="btn btn-sm btn-outline-warning ms-2">Prijavi →</a>
  </div>
  {% endfor %}
</div>
{% endif %}
```

---

## ZADATAK 6 — Seed podaci: inicijalni FundOpportunity zapisi

Management command: `limit_connect_ai/management/commands/seed_fund_opportunities.py`

Unesi minimalno 10 konkretnih prilika:

```python
INITIAL_FUNDS = [
    {
        'title': 'APPRRR 55.1.b.01 — Nabava opreme za pčelarstvo',
        'jurisdiction': 'HR',
        'fund_body': 'APPRRR',
        'client_segments': ['opg_pcela'],
        'max_amount_eur': None,  # 100% prihvatljivog troška
        'refund_percent': 100,
        'min_requirement': 'Minimalno 30 košnica. Ažurirana EPP evidencija. R1 račun za opremu.',
        'is_recurring': True,
        'application_url': 'https://www.apprrr.hr/pcelarstvo-3/',
    },
    {
        'title': 'APPRRR 55.1.b.02 — Suzbijanje varoze i bolesti',
        'jurisdiction': 'HR',
        'fund_body': 'APPRRR',
        'client_segments': ['opg_pcela'],
        'refund_percent': 100,
        'min_requirement': 'Svi pčelari u EPP evidenciji.',
        'is_recurring': True,
    },
    {
        'title': 'ESF+ — Socijalno uključivanje i aktivno starenje',
        'jurisdiction': 'EU',
        'fund_body': 'MROSP / eKohezija',
        'client_segments': ['udruga'],
        'max_amount_eur': Decimal('500000'),
        'application_url': 'https://esf.hr/esfplus/natjecaji/natjecaji/',
    },
    {
        'title': 'EAFRD M06 — Razvoj malih poljoprivrednih gospodarstava',
        'jurisdiction': 'EU',
        'fund_body': 'APPRRR / IPARD III',
        'client_segments': ['opg', 'opg_pcela', 'rental'],
        'max_amount_eur': Decimal('200000'),
        'refund_percent': 50,
    },
    {
        'title': 'ERDF — Digitalizacija MSP (NPU)',
        'jurisdiction': 'EU',
        'fund_body': 'MINPO / eUfondovi',
        'client_segments': ['msp'],
        'max_amount_eur': Decimal('100000'),
        'application_url': 'https://eufondovi.gov.hr',
    },
    {
        'title': 'BAFA BEG — Energetska obnova poslovnih zgrada',
        'jurisdiction': 'DE',
        'fund_body': 'BAFA',
        'client_segments': ['de_klijent'],
        'max_amount_eur': None,  # do 70% troška
        'refund_percent': 70,
        'application_url': 'https://www.bafa.de',
    },
    {
        'title': 'CERV — Vrijednosti i prava EU',
        'jurisdiction': 'EU',
        'fund_body': 'Europska komisija',
        'client_segments': ['udruga'],
        'max_amount_eur': Decimal('300000'),
    },
    {
        'title': 'HTZ — Razvoj turističkih kapaciteta',
        'jurisdiction': 'HR',
        'fund_body': 'HTZ / MINTS',
        'client_segments': ['rental'],
        'max_amount_eur': Decimal('50000'),
        'application_url': 'https://www.mint.hr/natjecaji',
    },
    {
        'title': 'HZZ — Subvencija zapošljavanja (mjere aktivne politike)',
        'jurisdiction': 'HR',
        'fund_body': 'HZZ',
        'client_segments': ['msp', 'udruga'],
        'max_amount_eur': None,  # 70-100% bruto plaće do 12 mj
        'refund_percent': 85,
        'is_recurring': True,
    },
    {
        'title': 'APPRRR — "Plavi dizel" povrat trošarine',
        'jurisdiction': 'HR',
        'fund_body': 'APPRRR',
        'client_segments': ['opg', 'opg_pcela'],
        'is_recurring': True,
        'min_requirement': 'Upisan u EPP evidenciju. Vozilo registrirano za OPG.',
    },
]
```

---

## ZADATAK 7 — Admin

```python
@admin.register(FundApplicationDraft)
class FundApplicationDraftAdmin(admin.ModelAdmin):
    list_display = ['company', 'title', 'status', 'eligibility_score',
                    'amount_requested', 'deadline', 'created_at']
    list_filter  = ['status', 'opportunity__jurisdiction']
    search_fields = ['company__name', 'title']
    readonly_fields = ['eligibility_score', 'eligibility_notes', 'draft_content', 'created_at']
    actions = ['mark_submitted', 'mark_approved']
```

---

## DONE kriterij

- [ ] FundOpportunity model s novim poljima (client_segments, jurisdiction, fund_body, etc.)
- [ ] FundApplicationDraft model + migracija
- [ ] `fund_checker.py` — check_eligibility() radi za opg_pcela, udruga, rental, msp
- [ ] Views: fund_opportunities, fund_draft_create, fund_draft_detail
- [ ] Cockpit widget "EU Prilike" — pokazuje 3 relevantna fonda s rokom
- [ ] seed_fund_opportunities command — 10 inicijalnih zapisa
- [ ] Admin registriran
- [ ] Commit: "feat(ai): EU/Fund opportunities workflow — eligibility check, draft, cockpit widget"
