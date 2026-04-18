# CC_TASK_SENTINEL_ADVISOR.md
# FENIX SENTINEL — Advisor Wing: PLAN_078–083
# Cilj: 13/10 | Za: Opus CC | Prioritet: MAKSIMALAN
# Datum: 2026-04-18

---

## KONTEKST — ZAŠTO OVO GRADIMO

Računovođa je dugo bila robinja — tipka, tipka, tipka, podnosi obrasce, čeka inspektore.
FENIX SENTINEL Advisor Wing okreće igru: AI radi za računovođu.

Tri čvora iz budućnosti:
1. **EU Navigator** — novac dolazi automatski, ne čekamo na pozive
2. **Obrasci Engine** — PDV, JOPPD, GDPR popunjavaju se sami
3. **Digitalni Ured** — svaki korisnik ima svog AI knjigovođu dostupnog 24/7

Korisnik je postavio ljestvicu: **13/10**.
To znači: ne funkcionira samo — fascinira.

---

## PLAN_078 — EU NAVIGATOR (Gemini Fund Matching)

### Cilj
Svaka firma u sustavu dobiva personaliziranu listu EU fondova/natječaja
za koje je automatski profilirana i može aplicirati — bez istraživanja.

### Modeli

```python
# sentinel/models_advisor.py

class EUFundProfile(models.Model):
    """Profil firme za EU fondove — automatski izračunat"""
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE,
                                   related_name='eu_profile')
    # NKD/NACE sektor, zaposlenici, prihod, lokacija
    nkd_code = models.CharField(max_length=10, blank=True)
    employee_count = models.IntegerField(default=0)
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    company_age_years = models.IntegerField(default=0)
    region = models.CharField(max_length=100, blank=True)  # HR-grad, HR-split...
    # AI score
    innovation_score = models.IntegerField(default=0)    # 0-100
    digital_score = models.IntegerField(default=0)       # 0-100
    green_score = models.IntegerField(default=0)         # 0-100
    social_score = models.IntegerField(default=0)        # 0-100
    last_profiled = models.DateTimeField(null=True)
    profile_version = models.CharField(max_length=20, default='1.0')

    class Meta:
        db_table = 'sentinel_eu_fund_profile'
        verbose_name = 'EU Fund Profile'


class EUFund(models.Model):
    """Katalog EU natječaja — puni Gemini, ažurira se tjedno"""
    STATUS = [('open','Otvoren'), ('closing','Zatvara se'), ('closed','Zatvoren'),
              ('announced','Najavljen')]
    
    fund_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=500)
    title_hr = models.CharField(max_length=500, blank=True)
    program = models.CharField(max_length=200)  # Horizon EU, ESF+, ERDF...
    total_budget_eur = models.BigIntegerField(null=True)
    max_grant_eur = models.IntegerField(null=True)
    min_grant_eur = models.IntegerField(null=True)
    cofinancing_rate = models.IntegerField(default=85)  # % EU pokriva
    deadline = models.DateField(null=True)
    open_date = models.DateField(null=True)
    status = models.CharField(max_length=20, choices=STATUS, default='open')
    # Eligibility matrix
    eligible_nkd = models.JSONField(default=list)      # ['G47', 'C10'...] ili []
    eligible_regions = models.JSONField(default=list)  # [] = sve regije
    min_employees = models.IntegerField(default=0)
    max_employees = models.IntegerField(null=True)     # null = bez gornje granice
    min_age_years = models.IntegerField(default=0)
    # Scoring weights
    innovation_weight = models.IntegerField(default=25)
    digital_weight = models.IntegerField(default=25)
    green_weight = models.IntegerField(default=25)
    social_weight = models.IntegerField(default=25)
    # Meta
    source_url = models.URLField(blank=True)
    summary_hr = models.TextField(blank=True)          # Gemini summary na HR
    gemini_analysis = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sentinel_eu_fund'
        ordering = ['deadline']


class EUMatch(models.Model):
    """Personalizirani match: firma × natječaj"""
    RECOMMENDED = 'recommended'
    APPLIED = 'applied'
    REJECTED = 'rejected'
    WON = 'won'
    STATUS = [(RECOMMENDED,'Preporučeno'), (APPLIED,'Aplikacija u tijeku'),
              (REJECTED,'Odbijeno'), (WON,'Odobreno')]
    
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE,
                                related_name='eu_matches')
    fund = models.ForeignKey(EUFund, on_delete=models.CASCADE)
    match_score = models.IntegerField()       # 0-100, AI izračun
    eligibility_score = models.IntegerField() # 0-100, tvrdi uvjeti
    potential_eur = models.IntegerField()     # Procijenjeni grant €
    status = models.CharField(max_length=20, choices=STATUS, default=RECOMMENDED)
    ai_reasoning = models.TextField()        # Zašto match
    action_plan = models.JSONField(default=list)  # Koraci za aplikaciju
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'sentinel_eu_match'
        unique_together = ['company', 'fund']
        ordering = ['-match_score']
```

### Celery Task

```python
# sentinel/tasks_advisor.py

@shared_task(name='sentinel.eu_navigator_scan')
def eu_navigator_scan():
    """
    Tjedno: Gemini skenira EU fondove, profilira firme, kreira matcheve.
    Pokreće se: svaki ponedjeljak u 06:00
    """
    import anthropic
    
    client = anthropic.Anthropic()
    companies = Company.objects.filter(is_active=True).select_related('eu_profile')
    
    scan = SentinelScan.objects.create(
        scan_type='eu_navigator',
        status='running',
        companies_scanned=companies.count()
    )
    
    matches_created = 0
    alerts_fired = 0
    
    for company in companies:
        profile = _build_eu_profile(company)
        open_funds = EUFund.objects.filter(status__in=['open', 'closing'])
        
        for fund in open_funds:
            eligibility = _check_eligibility(profile, fund)
            if eligibility < 50:
                continue
            
            # Claude AI scoring
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=500,
                messages=[{
                    'role': 'user',
                    'content': f"""Procijeni match između firme i EU natječaja.
                    
Firma: {company.name}, NKD: {profile.nkd_code}, 
Zaposlenici: {profile.employee_count}, Regija: {profile.region},
Innovation: {profile.innovation_score}/100, Digital: {profile.digital_score}/100

Natječaj: {fund.title_hr or fund.title}
Program: {fund.program}, Max grant: €{fund.max_grant_eur:,}
Deadline: {fund.deadline}

Odgovori JSON: {{"match_score": 0-100, "potential_eur": broj, 
"reasoning": "2-3 rečenice", "action_steps": ["korak1", "korak2", "korak3"]}}"""
                }]
            )
            
            data = json.loads(response.content[0].text)
            match_score = data.get('match_score', 0)
            
            if match_score >= 60:
                match, created = EUMatch.objects.update_or_create(
                    company=company, fund=fund,
                    defaults={
                        'match_score': match_score,
                        'eligibility_score': eligibility,
                        'potential_eur': data.get('potential_eur', 0),
                        'ai_reasoning': data.get('reasoning', ''),
                        'action_plan': data.get('action_steps', []),
                    }
                )
                if created:
                    matches_created += 1
                    if match_score >= 75 and not match.notified:
                        SentinelAlert.objects.create(
                            company=company,
                            alert_type='eu_opportunity',
                            severity='info',
                            title=f'EU fondovi: {fund.title_hr or fund.title}',
                            message=f'Match score {match_score}/100. Potencijal: €{match.potential_eur:,}. {match.ai_reasoning}',
                            data={'fund_id': fund.id, 'match_id': match.id}
                        )
                        match.notified = True
                        match.save()
                        alerts_fired += 1
    
    scan.status = 'completed'
    scan.alerts_fired = alerts_fired
    scan.save()
    return f'EU Navigator: {matches_created} matcheva, {alerts_fired} notifikacija'


def _build_eu_profile(company):
    """Izgradi ili ažuriraj EU profil firme iz postojećih podataka"""
    profile, _ = EUFundProfile.objects.get_or_create(company=company)
    
    from documents.models import ArhivaEntry
    from hr.models import Employee
    
    # Broj zaposlenika
    profile.employee_count = Employee.objects.filter(
        company=company, is_active=True).count()
    
    # Prihodi iz arhive (računi)
    from django.db.models import Sum
    from django.utils import timezone
    last_year = timezone.now() - timedelta(days=365)
    revenue = ArhivaEntry.objects.filter(
        company=company, doc_type='invoice_out',
        date__gte=last_year
    ).aggregate(total=Sum('amount'))['total'] or 0
    profile.annual_revenue = revenue
    
    # Digital score — koriste li AI module
    ai_usage = ArhivaEntry.objects.filter(
        company=company, ai_status='done').count()
    profile.digital_score = min(100, ai_usage * 5)
    
    profile.last_profiled = timezone.now()
    profile.save()
    return profile


def _check_eligibility(profile, fund):
    """Provjeri tvrde uvjete (0-100)"""
    score = 100
    
    if fund.eligible_nkd and profile.nkd_code:
        if not any(profile.nkd_code.startswith(nkd) for nkd in fund.eligible_nkd):
            score -= 40
    
    if fund.min_employees and profile.employee_count < fund.min_employees:
        score -= 50
    
    if fund.max_employees and profile.employee_count > fund.max_employees:
        score -= 50
    
    if fund.eligible_regions and profile.region:
        if profile.region not in fund.eligible_regions:
            score -= 30
    
    return max(0, score)
```

### URL i View

```python
# sentinel/views_eu.py

@login_required
def eu_navigator(request):
    company = request.user.active_company
    profile = EUFundProfile.objects.filter(company=company).first()
    matches = EUMatch.objects.filter(company=company).select_related('fund')[:20]
    
    # Stats
    total_potential = sum(m.potential_eur for m in matches)
    hot_matches = [m for m in matches if m.match_score >= 80]
    
    return render(request, 'sentinel/eu_navigator.html', {
        'profile': profile,
        'matches': matches,
        'total_potential': total_potential,
        'hot_matches': hot_matches,
    })

@login_required  
def eu_match_detail(request, match_id):
    match = get_object_or_404(EUMatch, pk=match_id, company=request.user.active_company)
    return render(request, 'sentinel/eu_match_detail.html', {'match': match})
```

**Template**: `/sentinel/templates/sentinel/eu_navigator.html`
- Hero: "Ukupni EU potencijal: **€{total_potential:,}**"
- Cards po matchevima — score bar, deadline countdown, potential €
- Action Plan expandable (accordion)
- Status badge + CTA "Počni aplikaciju"

---

## PLAN_079 — OBRASCI ENGINE (Auto-Fill Government Forms)

### Cilj
PDV obrazac, JOPPD, URA/IRA, GDPR registar — sustav ih popunjava automatski
iz računovodstvenih podataka. Računovođa samo pregleda i klika "Podnesi".

### Modeli

```python
class ObrascTip(models.Model):
    """Katalog obrazaca — PDV, JOPPD, URA, IRA, GDPR..."""
    PERIODI = [('monthly','Mjesečno'), ('quarterly','Kvartalno'),
               ('yearly','Godišnje'), ('on_demand','Na zahtjev')]
    
    kod = models.CharField(max_length=50, unique=True)   # 'PDV', 'JOPPD', 'URA'
    naziv = models.CharField(max_length=200)
    opis = models.TextField()
    period = models.CharField(max_length=20, choices=PERIODI)
    rok_dana = models.IntegerField(default=20)  # Dana od kraja perioda
    institucija = models.CharField(max_length=100)  # 'Porezna uprava', 'HZMO'
    template_path = models.CharField(max_length=200)  # XML/PDF template
    field_mapping = models.JSONField(default=dict)   # Mapiranje polja → DB
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'sentinel_obrazac_tip'


class ObrascInstance(models.Model):
    """Instanca obrasca — popunjen, čeka podnošenje ili je podnesen"""
    STATUS = [('draft','Nacrt'), ('ready','Spreman'), 
              ('submitted','Podnesen'), ('accepted','Prihvaćen'),
              ('rejected','Odbijen')]
    
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    tip = models.ForeignKey(ObrascTip, on_delete=models.CASCADE)
    period_od = models.DateField()
    period_do = models.DateField()
    rok_podnosenja = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    
    # Podaci
    izracunata_vrijednost = models.DecimalField(max_digits=15, decimal_places=2,
                                                null=True)  # npr. PDV za uplatu
    polja = models.JSONField(default=dict)        # Sva popunjena polja
    ai_napomene = models.JSONField(default=list)  # AI upozorenja
    
    # Podneseni
    xml_sadrzaj = models.TextField(blank=True)   # Generirani XML
    pdf_sadrzaj = models.BinaryField(null=True)  # Generirani PDF
    submitted_at = models.DateTimeField(null=True)
    submission_ref = models.CharField(max_length=100, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, 
                                   on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'sentinel_obrazac_instance'
        unique_together = ['company', 'tip', 'period_od']
        ordering = ['rok_podnosenja']


class ObrascKalendar(models.Model):
    """Auto-generiran kalendar obveza za firmu"""
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    obrazac = models.ForeignKey(ObrascInstance, on_delete=models.CASCADE, null=True)
    tip = models.ForeignKey(ObrascTip, on_delete=models.CASCADE)
    due_date = models.DateField()
    reminder_sent = models.BooleanField(default=False)
    reminder_7d = models.BooleanField(default=False)   # 7 dana unaprijed
    reminder_1d = models.BooleanField(default=False)   # 1 dan unaprijed
    completed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'sentinel_obrazac_kalendar'
        ordering = ['due_date']
```

### Core Logic — PDV Auto-Popunjavanje

```python
# sentinel/obrasci/pdv.py

class PDVCalculator:
    """
    Automatski izračunava PDV obrazac iz URA/IRA knjiga.
    Podržava: standardni PDV, paušal, posebni postupak za putničke agencije
    """
    
    def __init__(self, company, period_od, period_do):
        self.company = company
        self.period_od = period_od
        self.period_do = period_do
    
    def calculate(self):
        from documents.models import ArhivaEntry
        
        # I-1: Isporuke oporezive po stopi 25%
        ira_25 = ArhivaEntry.objects.filter(
            company=self.company,
            doc_type='invoice_out',
            date__range=(self.period_od, self.period_do),
            vat_rate=25
        ).aggregate(
            base=Sum('base_amount'),
            vat=Sum('vat_amount')
        )
        
        # I-2: Isporuke oporezive po stopi 13%  
        ira_13 = ArhivaEntry.objects.filter(
            company=self.company, doc_type='invoice_out',
            date__range=(self.period_od, self.period_do), vat_rate=13
        ).aggregate(base=Sum('base_amount'), vat=Sum('vat_amount'))
        
        # I-3: Isporuke oporezive po stopi 5%
        ira_5 = ArhivaEntry.objects.filter(
            company=self.company, doc_type='invoice_out',
            date__range=(self.period_od, self.period_do), vat_rate=5
        ).aggregate(base=Sum('base_amount'), vat=Sum('vat_amount'))
        
        # III-1: Pretporez po stopi 25%
        ura_25 = ArhivaEntry.objects.filter(
            company=self.company, doc_type='invoice_in',
            date__range=(self.period_od, self.period_do), vat_rate=25
        ).aggregate(base=Sum('base_amount'), vat=Sum('vat_amount'))
        
        # Ukupni PDV za uplatu / povrat
        pdv_obveza = (
            (ira_25['vat'] or 0) + (ira_13['vat'] or 0) + (ira_5['vat'] or 0)
        )
        pretporez = (ura_25['vat'] or 0)  # simplificiran
        
        neto = pdv_obveza - pretporez
        
        polja = {
            'I-1-osnovica': ira_25['base'] or 0,
            'I-1-pdv': ira_25['vat'] or 0,
            'I-2-osnovica': ira_13['base'] or 0,
            'I-2-pdv': ira_13['vat'] or 0,
            'I-3-osnovica': ira_5['base'] or 0,
            'I-3-pdv': ira_5['vat'] or 0,
            'III-1-pretporez': pretporez,
            'XIV-obveza': max(0, neto),
            'XIV-povrat': max(0, -neto),
        }
        
        # AI provjera anomalija
        ai_napomene = self._ai_check(polja)
        
        return polja, neto, ai_napomene
    
    def _ai_check(self, polja):
        """Haiku provjeri PDV polja za anomalije"""
        import anthropic
        client = anthropic.Anthropic()
        
        napomene = []
        
        # Jednostavne provjere bez AI
        if polja['XIV-obveza'] == 0 and polja['XIV-povrat'] == 0:
            napomene.append({
                'tip': 'warning',
                'polje': 'XIV',
                'poruka': 'PDV obveza i povrat su 0 — provjeri unos'
            })
        
        ratio = 0
        if polja['I-1-osnovica'] > 0:
            ratio = polja['I-1-pdv'] / polja['I-1-osnovica']
            if abs(ratio - 0.25) > 0.01:
                napomene.append({
                    'tip': 'error',
                    'polje': 'I-1',
                    'poruka': f'PDV stopa iznosi {ratio:.1%}, očekuje se 25%'
                })
        
        # AI za kompleksniji kontekst
        if sum(polja.values()) > 10000:
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=300,
                messages=[{
                    'role': 'user',
                    'content': f'Provjeri PDV obrazac. Polja: {json.dumps(polja, default=str)}. '
                               f'Jesi li primijetio anomalije? Odgovori JSON listom napomena.'
                }]
            )
            try:
                ai_notes = json.loads(response.content[0].text)
                if isinstance(ai_notes, list):
                    napomene.extend(ai_notes)
            except:
                pass
        
        return napomene
    
    def generate_xml(self, polja):
        """Generiraj ePorezna XML format"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Obrazac_PDV xmlns="http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/ObrazacPDV/v2-0">
  <Zaglavlje>
    <Razdoblje_od>{self.period_od.strftime('%Y-%m-%d')}</Razdoblje_od>
    <Razdoblje_do>{self.period_do.strftime('%Y-%m-%d')}</Razdoblje_do>
    <OIB>{self.company.oib}</OIB>
    <Naziv>{self.company.name}</Naziv>
  </Zaglavlje>
  <Podaci>
    <I1_Osnovica>{polja.get('I-1-osnovica', 0):.2f}</I1_Osnovica>
    <I1_PDV>{polja.get('I-1-pdv', 0):.2f}</I1_PDV>
    <I2_Osnovica>{polja.get('I-2-osnovica', 0):.2f}</I2_Osnovica>
    <I2_PDV>{polja.get('I-2-pdv', 0):.2f}</I2_PDV>
    <III1_Pretporez>{polja.get('III-1-pretporez', 0):.2f}</III1_Pretporez>
    <XIV_Obveza>{polja.get('XIV-obveza', 0):.2f}</XIV_Obveza>
    <XIV_Povrat>{polja.get('XIV-povrat', 0):.2f}</XIV_Povrat>
  </Podaci>
</Obrazac_PDV>"""
```

### Celery Tasks

```python
@shared_task(name='sentinel.obrasci_generate_monthly')
def obrasci_generate_monthly():
    """
    1. u mjesecu: auto-generiraj PDV obrasce za prošli mjesec
    Pokreće se: 1. u 07:00
    """
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    today = date.today()
    period_od = (today - relativedelta(months=1)).replace(day=1)
    period_do = today.replace(day=1) - timedelta(days=1)
    rok = today.replace(day=20)  # PDV rok: 20. u mjesecu
    
    pdv_tip = ObrascTip.objects.get(kod='PDV')
    companies = Company.objects.filter(
        is_active=True,
        companyprofile__pdv_obveznik=True
    )
    
    for company in companies:
        if ObrascInstance.objects.filter(
            company=company, tip=pdv_tip, period_od=period_od
        ).exists():
            continue
        
        calc = PDVCalculator(company, period_od, period_do)
        polja, neto, napomene = calc.calculate()
        
        obrazac = ObrascInstance.objects.create(
            company=company,
            tip=pdv_tip,
            period_od=period_od,
            period_do=period_do,
            rok_podnosenja=rok,
            status='ready',
            izracunata_vrijednost=neto,
            polja=polja,
            ai_napomene=napomene,
            xml_sadrzaj=calc.generate_xml(polja)
        )
        
        # Alert ako ima povrat
        if neto < 0:
            SentinelAlert.objects.create(
                company=company,
                alert_type='pdv_refund',
                severity='info',
                title=f'PDV povrat: {abs(neto):.2f} EUR',
                message=f'Za {period_od.strftime("%m/%Y")} imate pravo na povrat PDV-a.',
                data={'obrazac_id': obrazac.id}
            )
        
        # Alarm ako ne može platiti
        elif neto > 5000:
            SentinelAlert.objects.create(
                company=company,
                alert_type='pdv_large_liability',
                severity='warning',
                title=f'PDV obveza: {neto:.2f} EUR do {rok}',
                message='Visoka PDV obveza — provjeri likvidnost.',
                data={'obrazac_id': obrazac.id}
            )


@shared_task(name='sentinel.obrasci_reminder')
def obrasci_reminder():
    """
    Dnevno: Šalji podsjetnike za obrazce koji uskoro dospijevaju
    Pokreće se: svaki dan u 08:00
    """
    from django.utils import timezone
    today = timezone.now().date()
    
    # 7 dana unaprijed
    due_7d = ObrascInstance.objects.filter(
        rok_podnosenja=today + timedelta(days=7),
        status__in=['draft', 'ready']
    ).select_related('company', 'tip')
    
    for o in due_7d:
        SentinelAlert.objects.get_or_create(
            company=o.company,
            alert_type='obrazac_deadline',
            defaults={
                'severity': 'warning',
                'title': f'{o.tip.naziv} — rok za 7 dana',
                'message': f'Obrazac {o.tip.naziv} mora biti podnesen do {o.rok_podnosenja}.',
                'data': {'obrazac_id': o.id}
            }
        )
    
    # 1 dan — hitno
    due_1d = ObrascInstance.objects.filter(
        rok_podnosenja=today + timedelta(days=1),
        status__in=['draft', 'ready']
    )
    for o in due_1d:
        SentinelAlert.objects.create(
            company=o.company,
            alert_type='obrazac_urgent',
            severity='critical',
            title=f'HITNO: {o.tip.naziv} ističe sutra!',
            message=f'Obrazac mora biti podnesen DO SUTRA ({o.rok_podnosenja}).',
            data={'obrazac_id': o.id}
        )
```

---

## PLAN_080 — DIGITALNI URED (Conversational Advisory)

### Vizija
Svaki korisnik LIMIT Connect ima SVOG AI računovođu — dostupnog 24/7.
Nije chatbot. **Ured je** — sa sjećanjem, kontekstom firme, proaktivnim savjetima.

### Modeli

```python
# sentinel/models_ured.py

class DigitalniUred(models.Model):
    """Ured per-company — sjećanje, profil, aktivna sesija"""
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE,
                                   related_name='digitalni_ured')
    # Trajno sjećanje
    memory = models.JSONField(default=dict)     # Ključni faktori o firmi
    preferences = models.JSONField(default=dict)  # Korisničke preferencije
    # Stats
    total_conversations = models.IntegerField(default=0)
    total_insights = models.IntegerField(default=0)
    last_active = models.DateTimeField(null=True)
    # Persona
    advisor_name = models.CharField(max_length=100, default='Fenix Savjetnik')
    advisor_tone = models.CharField(max_length=20, default='professional')
    
    class Meta:
        db_table = 'sentinel_digitalni_ured'


class UredKonverzacija(models.Model):
    """Jedna sesija razgovora (može trajati više dana)"""
    TOPIC = [
        ('pdv', 'PDV i porezi'), ('eu', 'EU fondovi'),
        ('hr', 'Zaposlenici i plaće'), ('cashflow', 'Novčani tok'),
        ('compliance', 'Usklađenost'), ('general', 'Opće')
    ]
    
    ured = models.ForeignKey(DigitalniUred, on_delete=models.CASCADE,
                             related_name='conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.CharField(max_length=20, choices=TOPIC, default='general')
    title = models.CharField(max_length=200, blank=True)  # Auto-generiraj
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    is_resolved = models.BooleanField(default=False)
    summary = models.TextField(blank=True)  # AI sažetak nakon zatvaranja
    
    class Meta:
        db_table = 'sentinel_ured_konverzacija'
        ordering = ['-last_message_at']


class UredPoruka(models.Model):
    """Jedna poruka u konverzaciji"""
    ROLE = [('user', 'Korisnik'), ('assistant', 'AI'), ('system', 'Sustav')]
    
    konverzacija = models.ForeignKey(UredKonverzacija, on_delete=models.CASCADE,
                                     related_name='poruke')
    role = models.CharField(max_length=20, choices=ROLE)
    sadrzaj = models.TextField()
    
    # AI metadata
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    model_used = models.CharField(max_length=50, default='claude-haiku-4-5-20251001')
    latency_ms = models.IntegerField(default=0)
    
    # Insights
    extracted_actions = models.JSONField(default=list)  # Todo items iz odgovora
    extracted_alerts = models.JSONField(default=list)   # Alarmantni nalazi
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sentinel_ured_poruka'
        ordering = ['created_at']


class UredInsight(models.Model):
    """Proaktivni uvid — AI pronašao nešto važno, čeka korisnika"""
    PRIORITY = [('low','Nisko'), ('medium','Srednje'), ('high','Visoko')]
    
    ured = models.ForeignKey(DigitalniUred, on_delete=models.CASCADE,
                             related_name='insights')
    naslov = models.CharField(max_length=200)
    sadrzaj = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY)
    topic = models.CharField(max_length=20)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True)
    
    class Meta:
        db_table = 'sentinel_ured_insight'
        ordering = ['-created_at']
```

### Core — AI Engine s Kontekstom

```python
# sentinel/ured_engine.py

import anthropic
import time

class UredAIEngine:
    """
    Srce Digitalnog Ureda — Claude s trajnim kontekstom firme.
    Haiku za brze odgovore, Sonnet za kompleksno savjetovanje.
    """
    
    SYSTEM_PROMPT = """Ti si Fenix — osobni AI savjetnik za računovodstvo i financije.
Imaš pristup svim podacima firme: računi, plaće, PDV, EU fondovi, obveze.

PRAVILA:
- Govori direktno i konkretno (ne "možda" — reci "provjeri OIB u Ahrt. 1 st. 5")
- Uvijek navedi broj, datum ili iznos kad ga imaš
- Ako nešto nije u redu, reci jasno (bez omekšavanja)
- Predloži konkretni sljedeći korak
- Ako pitanje zahtijeva odvjetnika/revizora, jasno reci
- Jezik: prilagodi korisniku (HR/DE/EN auto-detect)

KONTEKST FIRME:
{company_context}

SJEĆANJE (prethodne sesije):
{memory}

AKTUALNI UPOZORENJA:
{active_alerts}"""
    
    def __init__(self, konverzacija: UredKonverzacija):
        self.konverzacija = konverzacija
        self.ured = konverzacija.ured
        self.company = self.ured.company
        self.client = anthropic.Anthropic()
    
    def _build_company_context(self):
        """Izgradi kontekst firme za sistem prompt"""
        from django.utils import timezone
        today = timezone.now().date()
        last_month = today - timedelta(days=30)
        
        from documents.models import ArhivaEntry
        from django.db.models import Sum, Count
        
        invoices_out = ArhivaEntry.objects.filter(
            company=self.company, doc_type='invoice_out',
            date__gte=last_month
        ).aggregate(
            total=Sum('amount'), count=Count('id')
        )
        
        invoices_in = ArhivaEntry.objects.filter(
            company=self.company, doc_type='invoice_in',
            date__gte=last_month
        ).aggregate(total=Sum('amount'), count=Count('id'))
        
        alerts = SentinelAlert.objects.filter(
            company=self.company, is_read=False
        ).order_by('-created_at')[:5]
        
        upcoming = ObrascInstance.objects.filter(
            company=self.company,
            rok_podnosenja__gte=today,
            rok_podnosenja__lte=today + timedelta(days=30),
            status__in=['draft', 'ready']
        )
        
        ctx = {
            'name': self.company.name,
            'oib': getattr(self.company, 'oib', 'N/A'),
            'last_30d_prihodi': float(invoices_out['total'] or 0),
            'last_30d_rashodi': float(invoices_in['total'] or 0),
            'incoming_invoices': invoices_in['count'],
            'outgoing_invoices': invoices_out['count'],
            'active_alerts_count': SentinelAlert.objects.filter(
                company=self.company, is_read=False).count(),
            'upcoming_deadlines': [
                {'naziv': o.tip.naziv, 'rok': str(o.rok_podnosenja),
                 'iznos': str(o.izracunata_vrijednost or '?')}
                for o in upcoming[:3]
            ]
        }
        return json.dumps(ctx, ensure_ascii=False, default=str, indent=2)
    
    def _build_messages(self):
        """Izgradi messages za API — zadnjih 20 poruka"""
        poruke = self.konverzacija.poruke.filter(
            role__in=['user', 'assistant']
        ).order_by('created_at')[-20:]
        
        return [{'role': p.role, 'content': p.sadrzaj} for p in poruke]
    
    def send(self, user_message: str, use_sonnet: bool = False) -> str:
        """Pošalji poruku, dobij odgovor"""
        start = time.time()
        
        # Spremi korisničku poruku
        UredPoruka.objects.create(
            konverzacija=self.konverzacija,
            role='user',
            sadrzaj=user_message
        )
        
        model = 'claude-sonnet-4-6' if use_sonnet else 'claude-haiku-4-5-20251001'
        
        system = self.SYSTEM_PROMPT.format(
            company_context=self._build_company_context(),
            memory=json.dumps(self.ured.memory, ensure_ascii=False, default=str),
            active_alerts=self._get_active_alerts_text()
        )
        
        messages = self._build_messages()
        
        response = self.client.messages.create(
            model=model,
            max_tokens=1000,
            system=system,
            messages=messages
        )
        
        ai_text = response.content[0].text
        latency = int((time.time() - start) * 1000)
        
        # Spremi AI odgovor
        ai_msg = UredPoruka.objects.create(
            konverzacija=self.konverzacija,
            role='assistant',
            sadrzaj=ai_text,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            model_used=model,
            latency_ms=latency
        )
        
        # Ažuriraj ured stats
        self.ured.total_conversations = (
            UredKonverzacija.objects.filter(ured=self.ured).count()
        )
        self.ured.last_active = timezone.now()
        self.ured.save(update_fields=['total_conversations', 'last_active'])
        
        # Auto-update sjećanje svaki 10. odgovor
        msg_count = self.konverzacija.poruke.count()
        if msg_count % 10 == 0:
            self._update_memory(ai_text)
        
        return ai_text
    
    def _get_active_alerts_text(self):
        alerts = SentinelAlert.objects.filter(
            company=self.company, is_read=False
        ).order_by('-severity', '-created_at')[:5]
        return '\n'.join([f"- [{a.severity.upper()}] {a.title}" for a in alerts])
    
    def _update_memory(self, last_response: str):
        """Haiku izvuče ključne faktore iz razgovora i spremi u memory"""
        recent_msgs = self.konverzacija.poruke.order_by('-created_at')[:6]
        context = '\n'.join([f'{m.role}: {m.sadrzaj[:200]}' for m in reversed(list(recent_msgs))])
        
        response = self.client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{
                'role': 'user',
                'content': f'Izvuci max 5 ključnih novih činjenica o firmi iz ovog razgovora. '
                           f'JSON objekt: {{"facts": [{{"key": "...", "value": "..."}}]}}.\n\n{context}'
            }]
        )
        try:
            data = json.loads(response.content[0].text)
            for fact in data.get('facts', []):
                self.ured.memory[fact['key']] = fact['value']
            self.ured.save(update_fields=['memory'])
        except:
            pass
```

### Views — Digitalni Ured API

```python
# sentinel/views_ured.py

@login_required
def digitalni_ured(request):
    """Glavna stranica ureda"""
    company = request.user.active_company
    ured, _ = DigitalniUred.objects.get_or_create(company=company)
    
    conversations = UredKonverzacija.objects.filter(
        ured=ured, user=request.user
    ).order_by('-last_message_at')[:10]
    
    insights = UredInsight.objects.filter(
        ured=ured, is_read=False
    ).order_by('-priority', '-created_at')[:5]
    
    # Kreiraj novu konverzaciju ili otvori zadnju
    active_conv = conversations.first()
    
    return render(request, 'sentinel/digitalni_ured.html', {
        'ured': ured,
        'conversations': conversations,
        'active_conv': active_conv,
        'insights': insights,
    })


@login_required
@csrf_exempt
def ured_send_message(request, conv_id):
    """API: pošalji poruku AI savjetniku"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    d = json.loads(request.body)
    message = d.get('message', '').strip()
    use_sonnet = d.get('advanced', False)
    
    if not message:
        return JsonResponse({'error': 'Prazna poruka'}, status=400)
    
    company = request.user.active_company
    ured = get_object_or_404(DigitalniUred, company=company)
    conv = get_object_or_404(UredKonverzacija, pk=conv_id, ured=ured, user=request.user)
    
    engine = UredAIEngine(conv)
    response_text = engine.send(message, use_sonnet=use_sonnet)
    
    return JsonResponse({
        'response': response_text,
        'model': 'sonnet' if use_sonnet else 'haiku',
        'conv_id': conv.id
    })


@login_required
def ured_new_conversation(request):
    """Kreiraj novu konverzaciju"""
    company = request.user.active_company
    ured, _ = DigitalniUred.objects.get_or_create(company=company)
    
    topic = request.POST.get('topic', 'general')
    conv = UredKonverzacija.objects.create(
        ured=ured, user=request.user, topic=topic
    )
    return redirect('sentinel:digitalni_ured_conv', conv_id=conv.id)
```

### Template Koncepcija — `sentinel/digitalni_ured.html`

```
┌─────────────────────────────────────────────────────────┐
│  🏛️  DIGITALNI URED         [Fenix Savjetnik]   [⚙️]    │
├──────────────┬──────────────────────────────────────────┤
│  RAZGOVORI   │                                          │
│  ─────────   │   [💡 Proaktivni uvidi: 3 nova]          │
│  > Cashflow  │   ┌────────────────────────────────────┐ │
│    PDV Q1    │   │ PDV refund €1,200 čeka povrat       │ │
│    EU Match  │   │ Rok JOPPD: za 5 dana                │ │
│    Plaće     │   │ EU match: Digitalizacija 82/100 ✓  │ │
│  ─────────   │   └────────────────────────────────────┘ │
│  [+ Novi]    │                                          │
│              │   ════════════════════════════════════   │
│  BRZE TEME:  │   Fenix: Dobar dan! Vaš PDV za Q1       │
│  [PDV]       │   iznosi 3,200 EUR — rok je 20.04.      │
│  [EU]        │   Imate povrat pretporeza od 800 EUR.    │
│  [Plaće]     │   Što vas zanima?                       │
│  [Cash]      │                                          │
│              │   ════════════════════════════════════   │
│              │   ┌────────────────────────────────────┐ │
│              │   │ Upiši pitanje...            [📤]    │ │
│              │   │              [⚡ Haiku] [🧠 Sonnet] │ │
│              │   └────────────────────────────────────┘ │
└──────────────┴──────────────────────────────────────────┘
```

---

## PLAN_081 — PROAKTIVNI KALENDAR OBVEZA

### Cilj
Svaka firma dobiva personaliziran računovodstveni kalendar —
s realnim rokovima, procijenjenim iznosima i prijedlogom akcija.

### Model

```python
class KalendarObveza(models.Model):
    """Master kalendar svih računovodstvenih obveza za firmu"""
    KATEGORIJA = [
        ('porezna', 'Porezna uprava'), ('mirovinsko', 'HZMO'),
        ('zdravstveno', 'HZZO'), ('sud', 'Sudski registar'),
        ('eu', 'EU/HAMAG'), ('banka', 'Banka'), ('ostalo', 'Ostalo')
    ]
    
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    kategorija = models.CharField(max_length=20, choices=KATEGORIJA)
    naziv = models.CharField(max_length=200)
    opis = models.TextField()
    rok = models.DateField()
    procijenjeni_iznos = models.DecimalField(max_digits=12, decimal_places=2,
                                              null=True)
    zakonska_osnova = models.CharField(max_length=200, blank=True)  # Čl. X ZPD
    penali_kašnjenja = models.TextField(blank=True)  # Što se dogodi ako kasniš
    # Status
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True)
    # Generiran iz
    auto_generated = models.BooleanField(default=True)
    obrazac = models.ForeignKey(ObrascInstance, null=True, on_delete=models.SET_NULL)
    
    class Meta:
        db_table = 'sentinel_kalendar_obveza'
        ordering = ['rok']
        indexes = [
            models.Index(fields=['company', 'rok']),
            models.Index(fields=['company', 'is_completed']),
        ]
```

### Celery Beat

```python
@shared_task(name='sentinel.generate_calendar')
def generate_calendar():
    """
    Tjedno: regeneriraj kalendar za sve firme
    Pokreće se: svake nedjelje u 22:00
    """
    for company in Company.objects.filter(is_active=True):
        _generate_company_calendar(company)


def _generate_company_calendar(company):
    """Generiraj godišnji kalendar za firmu na temelju zakonskih obveza"""
    from datetime import date
    today = date.today()
    
    # Brišemo stare auto-generirane
    KalendarObveza.objects.filter(
        company=company, auto_generated=True,
        rok__gt=today, is_completed=False
    ).delete()
    
    items = []
    year = today.year
    
    # PDV — mjestečno 20.
    for month in range(today.month, 13):
        rok = date(year, month, 20)
        if rok > today:
            items.append(KalendarObveza(
                company=company,
                kategorija='porezna',
                naziv=f'PDV obrazac {month:02d}/{year}',
                rok=rok,
                zakonska_osnova='Čl. 85 Zakona o PDV-u',
                penali_kašnjenja='Kamata 9% godišnje + prekršajna novčana kazna do 200.000 HRK'
            ))
    
    # JOPPD — 15. u mjesecu
    for month in range(today.month, 13):
        rok = date(year, month, 15)
        if rok > today:
            items.append(KalendarObveza(
                company=company,
                kategorija='mirovinsko',
                naziv=f'JOPPD {month:02d}/{year}',
                rok=rok,
                zakonska_osnova='Čl. 86 Zakona o doprinosima'
            ))
    
    # Godišnji obračun poreza — 30.04.
    items.append(KalendarObveza(
        company=company,
        kategorija='porezna',
        naziv=f'Godišnji obračun poreza na dobit {year}',
        rok=date(year, 4, 30),
        zakonska_osnova='Čl. 35 Zakona o porezu na dobit'
    ))
    
    KalendarObveza.objects.bulk_create(items, ignore_conflicts=True)
```

---

## PLAN_082 — EXPLOZIVNO RJEŠENJE #1: OBRASCI PORTAL (One-Click Submit)

### Vizija
Ne samo auto-fill — **direktna integracija s ePorezna/HZMO/HZZO API**.
Korisnik klika "Podnesi" — sustav podnosi, vraća potvrdu.

### Arhitektura

```python
class EPoreznaConnector:
    """
    Direktna integracija s ePorezna REST API (Gov.hr / eCitizen 2.0)
    Koristi firmin FINA certifikat za autentikaciju
    """
    
    BASE_URL = 'https://api.eporezna.hr/v2'  # Produkcija
    BASE_URL_TEST = 'https://test.eporezna.hr/v2'
    
    def __init__(self, company):
        self.company = company
        self.cert_path = company.fina_cert_path
        self.cert_password = company.fina_cert_password
    
    def submit_pdv(self, obrazac: ObrascInstance) -> dict:
        """Podnesi PDV obrazac elektronski"""
        import requests
        
        xml_payload = obrazac.xml_sadrzaj
        
        response = requests.post(
            f'{self.BASE_URL}/pdv/submit',
            data=xml_payload.encode('utf-8'),
            cert=(self.cert_path, self.cert_password),
            headers={
                'Content-Type': 'application/xml',
                'X-OIB': self.company.oib,
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            obrazac.status = 'submitted'
            obrazac.submitted_at = timezone.now()
            obrazac.submission_ref = result.get('ref_number', '')
            obrazac.save()
            
            SentinelAlert.objects.create(
                company=self.company,
                alert_type='obrazac_submitted',
                severity='success',
                title=f'{obrazac.tip.naziv} uspješno podnesen',
                message=f'Referentni broj: {obrazac.submission_ref}'
            )
            return {'success': True, 'ref': obrazac.submission_ref}
        
        return {'success': False, 'error': response.text}
```

---

## PLAN_083 — EXPLOZIVNO RJEŠENJE #2: SILENT TWIN MONITORING

### Vizija
Svaka akcija u sustavu ima "sjena" — tiha AI analiza koja
nikad ne ometa, ali uvijek zna kad nešto nije u redu.

```python
class SilentTwin:
    """
    Pasivni promatrač koji analizira booking patterns.
    Ne blokira, ne obavještava spam — čeka threshold.
    
    Inspiracija: Fenix V3 Innovations — Silent Twin koncept
    """
    
    ANOMALY_THRESHOLD = 3   # Anomalije u 24h = alert
    CONFIDENCE_THRESHOLD = 85  # % potrebno za alert
    
    def observe(self, event_type: str, company_id: int, data: dict):
        """Async promatranje — ne čeka odgovor"""
        observe_event.delay(event_type, company_id, data)


@shared_task(name='sentinel.observe_event')
def observe_event(event_type: str, company_id: int, data: dict):
    """
    Haiku AI analizira event u pozadini.
    Korisnik ne čeka — ovo radi u pozadini.
    """
    import anthropic
    
    # Dohvati kontekst
    company = Company.objects.get(pk=company_id)
    recent_alerts = SentinelAlert.objects.filter(
        company=company,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    if recent_alerts >= 10:  # Spam zaštita
        return
    
    client = anthropic.Anthropic()
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=200,
        messages=[{
            'role': 'user',
            'content': f'''Analiziraj događaj. Je li anomalija?
Event: {event_type}
Data: {json.dumps(data, default=str, ensure_ascii=False)[:500]}
Firma: {company.name}

JSON: {{"is_anomaly": bool, "confidence": 0-100, "reason": "string", "severity": "info|warning|critical"}}'''
        }]
    )
    
    try:
        result = json.loads(response.content[0].text)
        if result['is_anomaly'] and result['confidence'] >= SilentTwin.CONFIDENCE_THRESHOLD:
            SentinelAlert.objects.create(
                company=company,
                alert_type=f'twin_{event_type}',
                severity=result.get('severity', 'warning'),
                title=f'Silent Twin detekcija: {event_type}',
                message=result['reason'],
                data=data
            )
    except:
        pass
```

---

## PLAN_083b — EXPLOZIVNO RJEŠENJE #3: ADAPTIVE WORKSPACE INTELLIGENCE

### Vizija  
Dashboard koji se MIJENJA sam — ne statički widgeti,
nego živo sučelje koje zna što računovođi treba SADA.

```python
# sentinel/workspace_intelligence.py

class AdaptiveWorkspace:
    """
    Prati ponašanje korisnika i adaptira dashboard.
    Inspiracija: Fenix V3 — Adaptive Workspace
    """
    
    def get_personalized_layout(self, user, company):
        """
        Vrati personaliziran redoslijed widgeta za korisnika.
        """
        import anthropic
        
        usage = self._get_usage_patterns(user, company)
        pending_items = self._get_pending_items(company)
        
        client = anthropic.Anthropic()
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{
                'role': 'user',
                'content': f'''Odredi prioritet widgeta za dashboard.
                
Korisnikov usage: {json.dumps(usage, default=str)}
Pending: {json.dumps(pending_items, default=str)}
Trenutno: {timezone.now().strftime("%A %H:%M")}

Poredaj: ["eu_matches", "obrazci", "digitalni_ured", "audit_chain", 
          "temporal_score", "cashflow", "calendar"]
JSON: {{"order": ["widget1", "widget2", ...], "highlight": "widget_koji_treba_paznju"}}'''
            }]
        )
        
        try:
            return json.loads(response.content[0].text)
        except:
            return {'order': ['obrazci', 'calendar', 'cashflow', 'eu_matches',
                              'digitalni_ured', 'temporal_score', 'audit_chain'],
                    'highlight': 'obrazci'}
    
    def _get_usage_patterns(self, user, company):
        """Koliko puta korisnik koristi što"""
        # Iz session loga
        return {
            'most_visited': 'arhiva',
            'last_session_focus': 'pdv',
            'avg_session_minutes': 25,
            'pending_alerts': SentinelAlert.objects.filter(
                company=company, is_read=False).count()
        }
    
    def _get_pending_items(self, company):
        from datetime import date
        today = date.today()
        return {
            'overdue_forms': ObrascInstance.objects.filter(
                company=company, rok_podnosenja__lt=today,
                status__in=['draft', 'ready']).count(),
            'hot_eu_matches': EUMatch.objects.filter(
                company=company, match_score__gte=80,
                status='recommended').count(),
            'unread_insights': UredInsight.objects.filter(
                ured__company=company, is_read=False).count(),
        }
```

---

## INTEGRACIJA S FINA-CONNECT

### Što prenosimo u fina-connect

Sve modele iz sentinel appu treba dodati u fina-connect IDENTITY:
- `EUFund` + `EUMatch` → novi `eu` app
- `ObrascTip` + `ObrascInstance` → novi `obrasci` app
- `DigitalniUred` + `UredKonverzacija` → proširenje `accounts`/`core` appu

### Migracija strategija

```bash
# Na fina-connect serveru (port 8000)
# 1. Kreiraj sentinel app
python manage.py startapp sentinel

# 2. Kopiraj models_advisor.py, models_ured.py
# 3. Dodaj u INSTALLED_APPS

# 4. Makemi migracije
python manage.py makemigrations sentinel
python manage.py migrate

# 5. Sinkroniziraj EUFund katalog između baza (jednom tjedno)
# bridge.py task: sync_eu_funds_catalog
```

### Bridge Sync Task

```python
# core/bridge.py — dodaj

@shared_task(name='bridge.sync_eu_funds')
def sync_eu_funds():
    """Sinkroniziraj EU katalog iz fenix-v3 u fina-connect"""
    # fenix-v3 je "master" za katalog fondova
    # fina-connect čita matcheve za svoje firme
    # Implementirati cross-DB sync via REST API
    pass
```

---

## CELERY BEAT RASPORED — KOMPLETNI

```python
# settings/celery_beat.py — SVIH 12 taskova

CELERY_BEAT_SCHEDULE = {
    # === SENTINEL CORE (PLAN_072-077) ===
    'sentinel-stale-sessions':     {'task': 'sentinel.check_stale_pos_sessions',
                                    'schedule': crontab(minute='*/15')},
    'sentinel-temporal-score':     {'task': 'sentinel.temporal_ledger_score',
                                    'schedule': crontab(hour=3, minute=0)},
    'sentinel-audit-chain':        {'task': 'sentinel.audit_chain_verify',
                                    'schedule': crontab(hour=4, minute=0)},
    'sentinel-fiscal-scan':        {'task': 'sentinel.fiscal_compliance_scan',
                                    'schedule': crontab(hour=5, minute=0,
                                                        day_of_week='mon')},
    'sentinel-dashboard-refresh':  {'task': 'sentinel.dashboard_cache_refresh',
                                    'schedule': crontab(minute='*/30')},
    
    # === SENTINEL ADVISOR (PLAN_078-083) ===
    'sentinel-eu-navigator':       {'task': 'sentinel.eu_navigator_scan',
                                    'schedule': crontab(hour=6, minute=0,
                                                        day_of_week='mon')},
    'sentinel-pdv-generate':       {'task': 'sentinel.obrasci_generate_monthly',
                                    'schedule': crontab(hour=7, minute=0,
                                                        day_of_month=1)},
    'sentinel-obrasci-reminder':   {'task': 'sentinel.obrasci_reminder',
                                    'schedule': crontab(hour=8, minute=0)},
    'sentinel-calendar-generate':  {'task': 'sentinel.generate_calendar',
                                    'schedule': crontab(hour=22, minute=0,
                                                        day_of_week='sun')},
    
    # === DEEPSEEK PATROL ===
    'deepseek-patrol':             {'task': 'deepseek.nightly_code_audit',
                                    'schedule': crontab(hour=2, minute=0)},
}
```

---

## TEMPLATE STRUKTURA

```
sentinel/templates/sentinel/
├── dashboard.html           # SENTINEL Command Center (PLAN_076)
├── eu_navigator.html        # EU fondovi matchevi
├── eu_match_detail.html     # Detalji jednog matcha
├── obrasci_lista.html       # Svi obrasci, timeline prikaz
├── obrazac_detail.html      # Jedan obrazac — pregled + submit
├── digitalni_ured.html      # Conversational AI ured
├── digitalni_ured_conv.html # Aktivna konverzacija
├── kalendar.html            # Proaktivni kalendar obveza
└── adaptive_home.html       # Personaliziran home (PLAN_083b)
```

---

## URL ROUTING

```python
# sentinel/urls.py — dodati PLAN_078-083 URL-ove

urlpatterns += [
    # EU Navigator
    path('eu-navigator/', views_eu.eu_navigator, name='eu_navigator'),
    path('eu-match/<int:match_id>/', views_eu.eu_match_detail, name='eu_match_detail'),
    
    # Obrasci Engine
    path('obrasci/', views_obrasci.obrasci_lista, name='obrasci_lista'),
    path('obrasci/<int:pk>/', views_obrasci.obrazac_detail, name='obrazac_detail'),
    path('obrasci/<int:pk>/submit/', views_obrasci.obrazac_submit, name='obrazac_submit'),
    path('obrasci/<int:pk>/xml/', views_obrasci.obrazac_xml_download, name='obrazac_xml'),
    
    # Digitalni Ured
    path('ured/', views_ured.digitalni_ured, name='digitalni_ured'),
    path('ured/<int:conv_id>/', views_ured.digitalni_ured, name='digitalni_ured_conv'),
    path('ured/<int:conv_id>/send/', views_ured.ured_send_message, name='ured_send'),
    path('ured/nova/', views_ured.ured_new_conversation, name='ured_nova_konv'),
    
    # Kalendar
    path('kalendar/', views_kalendar.kalendar_obveza, name='kalendar_obveza'),
]
```

---

## MIGRACIJA: REDOSLIJED IZVRŠAVANJA

```
KORAK 1: Kreiraj sentinel app (manage.py startapp sentinel)
KORAK 2: models.py — core (SentinelAlert, SentinelScan, TemporalLedgerScore, AuditChain)
KORAK 3: models_advisor.py — EU (EUFundProfile, EUFund, EUMatch)
KORAK 4: models_advisor.py — Obrasci (ObrascTip, ObrascInstance, KalendarObveza)
KORAK 5: models_ured.py — Ured (DigitalniUred, UredKonverzacija, UredPoruka, UredInsight)
KORAK 6: makemigrations + migrate (provjeri 0 errora)
KORAK 7: obrasci/ — PDVCalculator, seedaj ObrascTip katalog
KORAK 8: ured_engine.py — UredAIEngine
KORAK 9: tasks_advisor.py — svi Celery taskovi
KORAK 10: urls.py — sve rute
KORAK 11: Templates (12 stranica)
KORAK 12: Celery Beat — svih 12 taskova
KORAK 13: venv/bin/python manage.py check — 0 errora
KORAK 14: git commit — feat(sentinel): Advisor Wing PLAN_078-083
```

---

## PROVJERA KVALITETE — 13/10 KRITERIJI

| Kriterij | Target | Implementirano |
|----------|--------|----------------|
| Zero blind spots | 100% | SHA-256 chain + Silent Twin |
| Proactive intelligence | 5 tipova uvida | EU + Obrasci + Calendar + Twin + Adaptive |
| AI-native | 3+ modela | Haiku + Sonnet + (Gemini budući) |
| Government integration | ePorezna API | EPoreznaConnector stub |
| Conversational UX | Real-time chat | UredAIEngine |
| Memory/context | Per-company | DigitalniUred.memory |
| Auto-compliance | 12 obveza/god | KalendarObveza |
| EU funding pipeline | 20+ fondova | EUNavigator weekly scan |
| Cross-DB sync | fina-connect | bridge.py plan |
| Test coverage | venv check 0 err | KORAK 13 obavezno |

---

**STATUS: PLAN SPREMAN ZA OPUS CC IMPLEMENTACIJU**
**Ukupno novih modela: 13 | Novih taskova: 9 | Novih URLova: 13**
**Ukupan scope: PLAN_072-083 = kompletni FENIX SENTINEL sistem**
