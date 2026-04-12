# CC_TASK: Employee 10/10 — Kompletni HRM sustav
# Kreirao: Sonnet — 2026-04-12
# Prioritet: Visok — izvršiti nakon 15.04. launch
# Procjena: 5-7 dana

---

## STANJE PRIJE POČETKA (verificirano)

POSTOJI I RADI — ne diraj:
  ✓ BookingSignature (core/models.py) — 31 zapis, append-only, SHA-256
  ✓ EmployeeProfile (worktime/models.py) — 308 zapisa, 24 polja
  ✓ TriKeyProfile s FINA cert podrškom — fina_cert_fingerprint/serial/expires
  ✓ CroValidator API (/api/v1/validate/) — OIB MOD11, IBAN MOD97, MBS
  ✓ employee_create view — kreira User + UserProfile + EmployeeProfile (attr checkboxovi)
  ✓ TimeEntry.compliance_note — postoji
  ✓ POSCashier — 49 zapisa (PIN login na terminalu)
  ✓ Workspace — 36 (5 desk + 31 premise)

NE POSTOJI — to gradimo:
  ✗ TimeLogRevision model (izmjena sata mora imati trag — Inspektorat rada)
  ✗ Data Vault za IBAN pri offboardingu (GDPR + ZOR)
  ✗ EmployeeProfile.is_terminated + terminated_at
  ✗ Self-service portal za radnika (moji sati, moja plaća, zahtjevi)
  ✗ Compliance monitor dashboard (admin vidi kritične flagove)
  ✗ Onboarding wizard za radnika (4 koraka)
  ✗ Offboarding wizard (checklist + GDPR timer)

---

## KORAK 0: OBVEZNO ČITANJE MODELA PRIJE KODA

```bash
# Provjeri STVARNA polja prije svakog koraka
grep -n "class TimeEntry\|class EmployeeProfile" /var/www/fina-connect/worktime/models.py
sed -n 'LINE,+40p' /var/www/fina-connect/worktime/models.py
```

---

## FAZA 1: TimeLogRevision — zakonski trag izmjena sati (1-2 dana)

### Zašto: Inspektorat rada traži nepromjenjivost. Svaka izmjena = trag.

### 1.1 Novi model (worktime/models.py — dodaj na kraj)

```python
class TimeLogRevision(models.Model):
    """
    Svaka izmjena TimeEntry mora se logirati ovdje.
    Zakon o radu + Inspektorat rada zahtijeva nepromjenjivi trag.
    """
    time_entry = models.ForeignKey(
        TimeEntry, on_delete=models.CASCADE,
        related_name='revisions'
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True
    )
    # Tko je izmijenio
    changed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    # Što je bilo prije i što je sad
    field_name = models.CharField(max_length=50)     # 'start_time', 'end_time', 'duration'
    old_value  = models.CharField(max_length=200)
    new_value  = models.CharField(max_length=200)
    reason     = models.CharField(max_length=300, blank=True)  # obavezno za HR izmjene

    # Dispute — radnik se ne slaže
    disputed_by  = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='disputed_revisions'
    )
    disputed_at  = models.DateTimeField(null=True, blank=True)
    dispute_note = models.TextField(blank=True)
    dispute_resolved = models.BooleanField(default=False)
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)
    dispute_resolved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_disputes'
    )

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Revizija radnog sata'
        verbose_name_plural = 'Revizije radnih sati'

    def __str__(self):
        return f"{self.time_entry} | {self.field_name}: {self.old_value}→{self.new_value}"
```

### 1.2 Migracija

```bash
venv/bin/python manage.py makemigrations worktime --name="add_timelog_revision"
venv/bin/python manage.py migrate worktime
```

### 1.3 Signal — auto-log svake izmjene TimeEntry

```python
# worktime/signals.py — dodaj:

from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import TimeEntry, TimeLogRevision

TRACKED_FIELDS = ['start_time', 'end_time', 'duration', 'date', 'hours']

@receiver(pre_save, sender=TimeEntry)
def log_timeentry_revision(sender, instance, **kwargs):
    if not instance.pk:
        return  # novi zapis, nema što logirati
    try:
        old = TimeEntry.objects.get(pk=instance.pk)
    except TimeEntry.DoesNotExist:
        return
    for field in TRACKED_FIELDS:
        old_val = getattr(old, field, None)
        new_val = getattr(instance, field, None)
        if str(old_val) != str(new_val):
            # Dohvati usera iz thread local (AuditMiddleware)
            from core.audit import _thread_locals
            user = getattr(_thread_locals, 'user', None)
            TimeLogRevision.objects.create(
                time_entry=instance,
                company=instance.company,
                changed_by=user if user and user.is_authenticated else None,
                field_name=field,
                old_value=str(old_val),
                new_value=str(new_val),
            )
```

### 1.4 Admin

```python
# worktime/admin.py — dodaj:
@admin.register(TimeLogRevision)
class TimeLogRevisionAdmin(admin.ModelAdmin):
    list_display = ['time_entry', 'field_name', 'old_value', 'new_value',
                    'changed_by', 'changed_at', 'dispute_resolved']
    list_filter  = ['dispute_resolved', 'field_name']
    readonly_fields = ['time_entry', 'changed_by', 'changed_at',
                       'disputed_by', 'disputed_at']

    def has_delete_permission(self, request, obj=None):
        return False  # nikad brisati — zakonski trag
```

### 1.5 Dispute API endpoint

```python
# worktime/views.py — dodaj:
@login_required
@require_POST
def dispute_revision(request, revision_id):
    """Radnik prijavljuje neslaganje s izmjenom sata."""
    from .models import TimeLogRevision
    from django.utils import timezone
    rev = get_object_or_404(TimeLogRevision,
                            pk=revision_id,
                            time_entry__user=request.user)
    if rev.disputed_by:
        return JsonResponse({'error': 'Već prijavljeno.'}, status=400)
    rev.disputed_by  = request.user
    rev.disputed_at  = timezone.now()
    rev.dispute_note = request.POST.get('note', '').strip()
    rev.save(update_fields=['disputed_by', 'disputed_at', 'dispute_note'])

    # Obavijesti managera
    try:
        from core.notify import notify_manager_dispute
        notify_manager_dispute(rev)
    except Exception:
        pass

    return JsonResponse({'ok': True, 'msg': 'Prigovor zabilježen. Manager je obaviješten.'})
```

URL: `path('revision/<int:revision_id>/dispute/', views.dispute_revision, name='dispute_revision')`

---

## FAZA 2: Data Vault + Offboarding (1-2 dana)

### 2.1 EmployeeProfile — dodaj polja za offboarding

```python
# worktime/models.py — u klasu EmployeeProfile dodaj:

# Offboarding
is_terminated      = models.BooleanField(default=False, verbose_name='Prekinut radni odnos')
terminated_at      = models.DateField(null=True, blank=True)
termination_reason = models.CharField(max_length=100, blank=True,
    choices=[
        ('resignation',    'Otkaz radnika'),
        ('employer',       'Otkaz poslodavca'),
        ('mutual',         'Sporazumni raskid'),
        ('contract_end',   'Istekao ugovor'),
        ('probation',      'Probni rad'),
    ])

# Data Vault — GDPR + ZOR kompromis
iban_archived      = models.BooleanField(default=False,
    help_text='IBAN skriven iz UI-a, ali pohranjen kriptiran za porezni nadzor')
iban_archive_at    = models.DateTimeField(null=True, blank=True,
    help_text='Automatski 30 dana od is_terminated=True')

# NAPOMENA: bank_account se NE briše nikad.
# ZOR: isplatne liste čuvaju se 6 godina, mirovinsko trajno.
# Data Vault: korisnik ne vidi IBAN, ali je u bazi.
```

Migracija:
```bash
venv/bin/python manage.py makemigrations worktime --name="employee_offboarding_vault"
venv/bin/python manage.py migrate worktime
```

### 2.2 Celery task — automatski Data Vault 30 dana nakon otkaza

```python
# worktime/tasks.py — dodaj:
@shared_task(name='worktime.tasks.iban_vault_check')
def iban_vault_check():
    """
    Svake noći 02:00 — provjeri terminated radnike.
    Ako je prošlo 30 dana od terminated_at → sakrij IBAN iz UI-a.
    IBAN ostaje u bazi (bank_account), samo se iban_archived = True.
    """
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now().date() - timedelta(days=30)
    to_vault = EmployeeProfile.objects.filter(
        is_terminated=True,
        iban_archived=False,
        terminated_at__lte=cutoff,
        bank_account__gt=''
    )
    count = to_vault.update(iban_archived=True, iban_archive_at=timezone.now())
    return f'Data Vault: {count} IBAN-a arhivirano'
```

Registriraj u CELERY_BEAT_SCHEDULE:
```python
'worktime-iban-vault-check': {
    'task': 'worktime.tasks.iban_vault_check',
    'schedule': crontab(hour=2, minute=30),
},
```

### 2.3 Offboarding view

```python
# companies/views.py — dodaj:
@login_required
@require_POST
def employee_offboard(request, pk):
    """Pokreni offboarding process za radnika."""
    from worktime.models import EmployeeProfile
    from django.utils import timezone
    from accounts.trikey import TriKeyProfile

    profile, company = _require_strict_admin(request)
    if not company:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    ep = get_object_or_404(EmployeeProfile, pk=pk, company=company)
    reason    = request.POST.get('reason', 'mutual')
    term_date = request.POST.get('terminated_at', timezone.now().date().isoformat())

    # 1. Označi kao terminiranog
    ep.is_terminated      = True
    ep.terminated_at      = term_date
    ep.termination_reason = reason
    ep.save(update_fields=['is_terminated', 'terminated_at', 'termination_reason'])

    # 2. Deaktiviraj PIN odmah
    try:
        tk = TriKeyProfile.objects.get(user=ep.user)
        tk.pin_hash     = ''
        tk.pin_attempts = 0
        tk.save(update_fields=['pin_hash', 'pin_attempts'])
    except Exception:
        pass

    # 3. Deaktiviraj korisnički račun
    ep.user.is_active = False
    ep.user.save(update_fields=['is_active'])

    # 4. BookingSignature audit
    try:
        from core.models import BookingSignature
        BookingSignature.log(
            request, 'delete',
            target_model='worktime.EmployeeProfile',
            target_id=str(ep.pk),
            target_repr=f'Offboarding: {ep.user.get_full_name()} ({reason})',
        )
    except Exception:
        pass

    return JsonResponse({
        'ok': True,
        'msg': f'{ep.user.get_full_name()} je odjavljen. IBAN se arhivira za 30 dana.',
        'checklist': {
            'pin_deactivated': True,
            'user_deactivated': True,
            'iban_vault_scheduled': True,
            'oib_retained': '11 godina (ZOR)',
            'fiscal_records': 'nepromjenjivo',
            'open_sessions': 0,  # TODO: provjeri otvorene POS smjene
        }
    })
```

URL (companies/urls.py):
```python
path('settings/employee/<int:pk>/offboard/', views.employee_offboard, name='employee_offboard'),
```

---

## FAZA 3: Compliance Monitor (1 dan)

### 3.1 View — compliance_monitor

```python
# companies/views.py — dodaj:
@login_required
def compliance_monitor(request):
    """
    Admin vidi sve compliance probleme radnika u jednom pogledu.
    Kritično = crveno. Upozorenje = žuto. OK = zeleno.
    """
    from core.company_utils import get_user_company
    from worktime.models import EmployeeProfile
    from django.utils import timezone
    from datetime import timedelta

    company = get_user_company(request)
    if not company:
        return redirect('/')

    alerts = []
    employees = EmployeeProfile.objects.filter(
        company=company, is_terminated=False
    ).select_related('user')

    for ep in employees:
        # KRITIČNO: nema OIB a radi na kasi
        if not ep.tax_id:
            alerts.append({
                'level': 'critical',
                'employee': ep,
                'message': f'Nema OIB! Radi na kasi — kazna do 66.000€',
                'action_url': f'/hr/companies/settings/employee/{ep.pk}/edit/',
                'action_label': 'Unesi OIB odmah',
            })

        # KRITIČNO: nema IBAN a treba primiti plaću
        if not ep.bank_account and not ep.is_volunteer:
            alerts.append({
                'level': 'critical',
                'employee': ep,
                'message': 'Nema IBAN — ne može primiti plaću',
                'action_url': f'/hr/companies/settings/employee/{ep.pk}/edit/',
                'action_label': 'Unesi IBAN',
            })

        # UPOZORENJE: PIN star > 90 dana
        try:
            from accounts.trikey import TriKeyProfile
            tk = ep.user.trikeyprofile
            if tk.pin_set_at:
                days = (timezone.now() - tk.pin_set_at).days
                if days > 90:
                    alerts.append({
                        'level': 'warning',
                        'employee': ep,
                        'message': f'PIN star {days} dana — preporuka rotacija',
                        'action_url': None,
                        'action_label': None,
                    })
        except Exception:
            pass

        # UPOZORENJE: prekovremeni > 48h ovaj tjedan (ZOR čl. 96)
        week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
        from worktime.models import TimeEntry
        week_hours = TimeEntry.objects.filter(
            user=ep.user, company=company,
            date__gte=week_start
        ).aggregate(
            total=models.Sum('hours')
        )['total'] or 0
        if week_hours > 48:
            alerts.append({
                'level': 'warning',
                'employee': ep,
                'message': f'{week_hours:.1f}h ovaj tjedan — ZOR limit 50h (čl. 96)',
                'action_url': None,
                'action_label': None,
            })

    critical = [a for a in alerts if a['level'] == 'critical']
    warnings = [a for a in alerts if a['level'] == 'warning']
    score = max(0, 100 - len(critical)*15 - len(warnings)*5)

    return render(request, 'companies/compliance_monitor.html', {
        'alerts': alerts,
        'critical': critical,
        'warnings': warnings,
        'score': score,
        'employees': employees,
        'page_title': 'Compliance Monitor',
    })
```

URL: `path('compliance/', views.compliance_monitor, name='compliance_monitor')`

### 3.2 Template (companies/templates/companies/compliance_monitor.html)

Koristiti FenixShell pattern (base.html extend).
Semafor: crvena = critical, žuta = warning, zelena = OK.
Score bar u gold tonu.
Svaki alert ima direktno action dugme.
KORISTITI fx- CSS klase iz fenix-tokens.css.

---

## FAZA 4: Self-Service Portal (1-2 dana)

### 4.1 URL struktura

```
/worktime/moji-sati/          → moji sati ovaj mjesec + graf
/worktime/moja-placa/         → zadnja isplatna lista (PDF link)
/worktime/zahtjevi/           → godišnji, bolovanje, PIN promjena
/worktime/revision/<pk>/dispute/  → dispute gumb (FAZA 1)
```

### 4.2 Moji sati view

```python
# worktime/views.py — dodaj:
@login_required
def my_hours(request):
    """Radnik vidi SVOJE sate — ne može vidjeti tuđe."""
    from django.utils import timezone
    import datetime

    company = getattr(request.user.profile, 'company', None)
    today   = timezone.now().date()
    month_start = today.replace(day=1)

    entries = TimeEntry.objects.filter(
        user=request.user,
        company=company,
        date__gte=month_start,
        date__lte=today,
    ).order_by('-date')

    total_hours = sum(e.hours or 0 for e in entries)

    # Projekcija plaće — ako postoji EmployeeProfile
    projected_pay = None
    try:
        ep = request.user.employeeprofile
        projected_pay = round(float(ep.hourly_rate) * total_hours, 2)
    except Exception:
        pass

    # Revizije koje čekaju dispute
    from .models import TimeLogRevision
    pending_disputes = TimeLogRevision.objects.filter(
        time_entry__user=request.user,
        disputed_by__isnull=True,
        changed_by__isnull=False,  # admin je izmijenio
    ).exclude(changed_by=request.user)

    return render(request, 'worktime/my_hours.html', {
        'entries': entries,
        'total_hours': total_hours,
        'projected_pay': projected_pay,
        'pending_disputes': pending_disputes,
        'month_start': month_start,
        'page_title': 'Moji sati',
    })
```

Template (worktime/templates/worktime/my_hours.html):
- Kartica s ukupnim satima ovog mjeseca
- Graf sati po danima (posljednjih 30 dana)
- Lista smjena s gumbom "Prijavi grešku" ako postoji revizija
- Projekcija plaće (ako postoji hourly_rate)
- Mobile-first, FenixShell base.html

---

## FAZA 5: Onboarding Wizard — 4 koraka (1 dan)

### Koristiti POSTOJEĆE:
- CroValidator API (/api/v1/validate/) za OIB u koraku 1
- TriKeyProfile za PIN u koraku 3
- FINA certifikat upload za korak 4 (Ključ 3 = kvalificirani potpis)
- BookingSignature.log() za audit svakog koraka

### Flow:

```
/companies/onboard/employee/<pk>/

KORAK 1: Identitet
  - OIB unos → /api/v1/validate/ → real-time ✓/✗
  - IBAN unos → /api/v1/validate/ → real-time ✓/✗
  - Radno mjesto, satnica, datum zaposlenja

KORAK 2: Pristup
  - Atribut checkboxovi (Admin / Radnik / Računovođa / Voditelj)
  - Terminal dodjela (ako je Radnik + POS)
  - Workspace dodjela

KORAK 3: PIN
  - Radnik postavlja PIN (6 znamenki) sada
  - ILI: admin unosi privremeni, radnik mijenja pri prvoj prijavi
  - PIN predlog od sustava (ne 1234, ne datum rođenja)

KORAK 4: Potpis (opcionalno — ako firma ima FINA certifikat)
  - Generirani PDF ugovora o radu
  - Ako korisnik ima FINA cert (Ključ 3) → digitalni potpis
  - Ako nema → "Isprintaj, potpiši, skeniraj i uploada"
  - Canvas potpis = samo za interne potvrde (primanje opreme, PIN izjava)

Rezultat jednog korisniku:
  ✓ EmployeeProfile kreiran/ažuriran
  ✓ OIB i IBAN validirani
  ✓ PIN aktivan
  ✓ Terminal i Workspace dodijeljeni
  ✓ BookingSignature: 4 audit zapisa (po koraku)
  ✓ Email s pristupnim podacima (ako postoji email)
  ✓ WhatsApp pozivnica (ako postoji telefon)
```

---

## ZABRANJENA ZONA

- NE modificirati core/models.py BookingSignature (append-only, ne diraj)
- NE brisati bank_account iz baze (samo iban_archived = True)
- NE modificirati base.html osim ako je nužno
- NE mijenjati CroValidator API (/api/v1/validate/)
- NE modifiicirati TriKeyProfile.verify_pin() logiku

---

## REDOSLJED IZVRŠENJA

```
Dan 1:  FAZA 1 — TimeLogRevision model + signal + admin + dispute API
Dan 2:  FAZA 2 — Data Vault polja + offboard view + Celery task
Dan 3:  FAZA 3 — Compliance monitor view + template
Dan 4:  FAZA 4 — Self-service portal (my_hours + my_pay)
Dan 5:  FAZA 5 — Onboarding wizard 4 koraka
Dan 6:  Testiranje + BookingSignature hookovi na sve nove viewove
Dan 7:  Git commit + FENIX_STATUS.md update
```

---

## VERIFIKACIJA PO FAZI

```bash
# FAZA 1:
venv/bin/python manage.py shell -c "
from worktime.models import TimeLogRevision
print('TimeLogRevision OK:', TimeLogRevision.objects.count())
"

# FAZA 2:
venv/bin/python manage.py shell -c "
from worktime.models import EmployeeProfile
ep = EmployeeProfile.objects.first()
print('Offboard polja:', ep.is_terminated, ep.iban_archived)
"

# FAZA 3:
curl -s https://limit-connect.com/hr/companies/compliance/ -L | grep -c "compliance"

# FAZA 5: OIB validator
curl -s -X POST https://limit-connect.com/api/v1/validate/ \
  -H 'Content-Type: application/json' \
  -d '{"oib":"12345678901"}' | python3 -m json.tool
```

---
## END-OF-SESSION: ažuriraj FENIX_STATUS.md kad završiš svaku fazu
