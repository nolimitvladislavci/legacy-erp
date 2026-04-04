# CC_TASK_CLAIM_YOUR_BUSINESS.md
# Za: CC Code
# Datum: 2026-03-30
# Rok: 15.04.2026. — NEMA POMAKA
# Prioritet: P0 — BLOCKER za 71 firmu s pravim podacima
#
# DIJAGNOZA (provjereno u bazi danas):
# - 71 firma (Konjik umbrella) ima prave podatke (fakture, journals, partneri)
# - 0 od 71 ima korisnika koji može se prijaviti
# - 0 emailova u bazi za te firme
# - Kad vlasnik pokuša registraciju s OIB-om: "Firma u sustavu — kontaktirajte podršku" → DEAD END
# - OIB unique constraint fail ako proba kreirati novu firmu → ERROR 500
# - Marija ih može vidjeti ali nema UI za dodavanje korisnika firmi
#
# REZULTAT KOJI TREBA: Svaki od 71 vlasnika može se prijaviti do 15.04.
# i vidjeti SVOJE podatke (fakture iz prošle godine, partnere, stanje konta).
#
# OVO JE "OBLAČENJE ODIJELA" — platform postaje upotrebljiva za stvarne klijente.

---

## ARHITEKTURA RJEŠENJA

Tri ulaza u isti rezultat:

```
Ulaz A: Vlasnik sam → /pocni/?oib=12345678901
   OIB lookup → firma postoji → "Tražite pristup" → Marija odobri → login

Ulaz B: Marija inicira → /posrednik/invite/[firma_id]/
   Generira magic invite link → šalje WhatsApp/email vlasnicima
   Vlasnik klikne → registracija s pre-filled podacima → automatski link

Ulaz C: Bulk invite → management command
   Script za svih 71 firmi → kreira invite tokene → sprema za Mariju da pošalje
```

Sva tri ulaza završavaju na **istom mjestu**: novi User + UserProfile vezan na POSTOJEĆU firmu,
s PRISTUPOM SVIM POSTOJEĆIM PODACIMA te firme.

---

## KORAK 1 — Model: CompanyClaimRequest

```python
# Dodati u companies/models.py ili registration/models.py

class CompanyClaimRequest(models.Model):
    """
    Zahtjev za pristup firmi koja već postoji u sustavu.
    
    Scenarij: vlasnik "Sa-Ni Mont" pokušava se registrirati,
    OIB lookup pronađe firmu, umjesto DEAD END → kreira ClaimRequest.
    Marija (ili superadmin) odobrava → kreira se user + membership.
    """
    STATUS = [
        ('pending',  'Čeka odobrenje'),
        ('approved', 'Odobreno'),
        ('rejected', 'Odbijeno'),
        ('expired',  'Isteklo (7 dana bez odgovora)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='claim_requests'
    )
    
    # Podaci vlasnika koji traži pristup
    email = models.EmailField()
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    
    # Verifikacija identiteta
    oib_confirmed = models.BooleanField(default=False)
    role_claimed = models.CharField(max_length=50, default='company_admin',
        help_text='Koja uloga se traži: company_admin, accountant, worker')
    
    # Token za email verifikaciju
    verify_token = models.CharField(max_length=64, unique=True, 
        default=lambda: secrets.token_urlsafe(32))
    token_expires = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    reviewed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_claims'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=300, blank=True)
    
    # Rezultat
    created_user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_from_claim'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label = 'registration'
        db_table = 'company_claim_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['email', 'status']),
        ]

    def __str__(self):
        return f'{self.email} → {self.company.name} [{self.status}]'

    @property
    def is_token_valid(self):
        from django.utils import timezone
        return self.status == 'pending' and timezone.now() < self.token_expires

    def approve(self, reviewed_by):
        """
        Odobri zahtjev: kreira korisnika i veže ga na firmu.
        Vraća (user, password) za slanje vlasniku.
        """
        from django.contrib.auth.models import User
        from accounts.models import UserProfile, CompanyMembership
        from django.utils import timezone
        import secrets
        
        # Kreira user
        base_un = self.email.split('@')[0].lower().replace('.', '_')[:25]
        username = base_un
        i = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_un}{i}'; i += 1
        
        temp_password = secrets.token_urlsafe(12)
        user = User.objects.create_user(
            username=username,
            email=self.email,
            password=temp_password,
            first_name=self.first_name,
            last_name=self.last_name,
        )
        
        # UserProfile vezan na POSTOJEĆU firmu
        UserProfile.objects.create(
            user=user,
            company=self.company,
            role=self.role_claimed,
            email_verified=True,  # Email je verificiran kroz claim process
        )
        
        # CompanyMembership
        CompanyMembership.objects.get_or_create(
            user=user, company=self.company,
            defaults={'role': self.role_claimed, 'is_active': True, 'is_default': True}
        )
        
        # RBAC UserRole
        try:
            from permissions.models import Role, UserRole
            role = Role.objects.get(role_type=self.role_claimed)
            UserRole.objects.get_or_create(
                user=user, role=role, company=self.company,
                defaults={'is_primary': True}
            )
        except Exception:
            pass
        
        # Ažuriraj claim
        self.status = 'approved'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.created_user = user
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'created_user'])
        
        return user, temp_password
```

**Migracija:**
```bash
venv/bin/python manage.py makemigrations registration --name company_claim_request
venv/bin/python manage.py migrate
```

---

## KORAK 2 — Ulaz A: "Claim Your Business" u SmartEntry

Modificiraj `/api/auth/detect-email/` i dodaj OIB check u SmartEntry.

Modificiraj `registration/views.py` — `api_oib_lookup` (linija 1065):

```python
# STARO (linija ~1075):
if company:
    return JsonResponse({
        'found': True,
        'source': 'internal',
        'message': 'Tvrtka je vec u sustavu — kontaktirajte podrsku za pristup.',
        'existing': True,
    })

# NOVO:
if company:
    # Provjeri ima li firma aktivnih korisnika
    from accounts.models import UserProfile
    has_owner = UserProfile.objects.filter(company=company).exists()
    
    return JsonResponse({
        'found': True,
        'source': 'internal',
        'name': company.name,
        'address': company.address or '',
        'city': getattr(company, 'city', '') or '',
        'existing': True,
        'has_owner': has_owner,
        # Ključna razlika:
        'can_claim': not has_owner,  # Može tražiti pristup ako nema vlasnika
        'claim_url': f'/firma/preuzmi/{company.id}/',
        'message': (
            'Ova firma već ima administratora u sustavu. Kontaktirajte podršku.'
            if has_owner else
            'Ova firma je u sustavu. Možete zatražiti pristup vlastitim podacima.'
        ),
    })
```

Dodati novi view `claim_company_form` i `submit_claim`:

```python
def claim_company_form(request, company_id):
    """
    GET /firma/preuzmi/<company_id>/
    Forma za traženje pristupa firmi koja postoji bez vlasnika.
    """
    from companies.models import Company
    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        raise Http404
    
    # Provjeri nema li već aktivnih usera
    from accounts.models import UserProfile
    if UserProfile.objects.filter(company=company).exists():
        messages.warning(request, 'Ova firma već ima aktivnog administratora.')
        return redirect('home')
    
    # Provjeri nema li pending claim zahtjeva
    pending = CompanyClaimRequest.objects.filter(
        company=company, status='pending'
    ).exists()
    
    return render(request, 'registration/claim_company.html', {
        'company': company,
        'pending': pending,
    })


def submit_claim(request, company_id):
    """
    POST /firma/preuzmi/<company_id>/submit/
    Kreira ClaimRequest i šalje WhatsApp obavijest Mariji.
    """
    from companies.models import Company
    from django.utils import timezone
    
    company = get_object_or_404(Company, id=company_id)
    
    # Provjeri nije li već preuzeto
    from accounts.models import UserProfile
    if UserProfile.objects.filter(company=company).exists():
        return JsonResponse({'error': 'Firma već ima administratora.'}, status=400)
    
    email = request.POST.get('email', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    
    if not email or not first_name:
        messages.error(request, 'Email i ime su obavezni.')
        return redirect('claim_company', company_id=company_id)
    
    # Provjeri duplicate
    if CompanyClaimRequest.objects.filter(email=email, company=company, status='pending').exists():
        messages.info(request, 'Vaš zahtjev je već poslan. Čekajte odobrenje.')
        return redirect('claim_company', company_id=company_id)
    
    claim = CompanyClaimRequest.objects.create(
        company=company,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        oib_confirmed=True,
        token_expires=timezone.now() + timezone.timedelta(days=7),
        ip_address=request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR'),
    )
    
    # WhatsApp Mariji
    try:
        from core.whatsapp import send_text
        approve_url = f'https://limit-connect.com/firma/odobri/{claim.id}/'
        send_text(
            phone='+4915771998747',  # Ivan/Marija
            message=(
                f'📋 ZAHTJEV ZA PRISTUP FIRMI\n'
                f'Firma: {company.name}\n'
                f'OIB: {company.oib}\n'
                f'Kontakt: {first_name} {last_name} | {email} | {phone}\n'
                f'\n✅ Odobri: {approve_url}'
            )
        )
    except Exception:
        pass
    
    messages.success(request, 
        f'Zahtjev je poslan! Administrator će vas kontaktirati u roku 24 sata. '
        f'Login podaci bit će poslani na {email}.'
    )
    return redirect('claim_success')
```

---

## KORAK 3 — Ulaz B: Marija inicira invite (posrednički flow)

Dodati u `registration/views.py` ili `companies/views.py`:

```python
@login_required
def send_company_invite(request, company_id):
    """
    POST /posrednik/invite/<company_id>/
    Marija generira magic invite link za firmu i šalje ga vlasniku.
    Dostupno: superadmin i company_admin Konjik umbrelle.
    """
    from companies.models import Company
    from django.utils import timezone
    
    company = get_object_or_404(Company, id=company_id)
    
    # Provjeri ovlasti - samo Konjik admin
    if not request.user.is_superuser:
        user_company = request.user.profile.company
        if company.umbrella_parent != user_company and company != user_company:
            return HttpResponseForbidden()
    
    # Generiraj claim request s invite tokenem
    claim = CompanyClaimRequest.objects.create(
        company=company,
        email=request.POST.get('email', ''),
        first_name=request.POST.get('first_name', ''),
        last_name=request.POST.get('last_name', ''),
        phone=request.POST.get('phone', ''),
        oib_confirmed=True,
        role_claimed='company_admin',
        token_expires=timezone.now() + timezone.timedelta(days=30),
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    invite_url = f'https://limit-connect.com/firma/aktiviraj/{claim.verify_token}/'
    
    # Pošalji WhatsApp ako ima broj
    phone = request.POST.get('phone', '')
    if phone:
        try:
            from core.whatsapp import send_text
            send_text(
                phone=phone,
                message=(
                    f'Pozdrav! Vaša firma *{company.name}* je u LIMIT Connect sustavu.\n\n'
                    f'Aktivirajte pristup vlastitim podacima ovdje:\n'
                    f'{invite_url}\n\n'
                    f'Link vrijedi 30 dana.'
                )
            )
        except Exception:
            pass
    
    return JsonResponse({
        'ok': True,
        'invite_url': invite_url,
        'claim_id': str(claim.id),
    })


def activate_via_invite(request, token):
    """
    GET/POST /firma/aktiviraj/<token>/
    Vlasnik klikne link → forma za postavljanje lozinke → pristup firmi.
    """
    claim = get_object_or_404(CompanyClaimRequest, verify_token=token)
    
    if not claim.is_token_valid:
        messages.error(request, 'Link je istekao ili nevažeći.')
        return redirect('home')
    
    if request.method == 'POST':
        password = request.POST.get('password1', '')
        if len(password) < 8:
            messages.error(request, 'Lozinka mora imati najmanje 8 znakova.')
            return render(request, 'registration/activate_invite.html', {'claim': claim})
        
        # Postavi lozinku i odobri
        from django.contrib.auth.models import User
        from django.contrib.auth import login
        
        user, _ = claim.approve(reviewed_by=None)
        user.set_password(password)
        user.save()
        
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Dobrodošli! Pristupili ste firmi {claim.company.name}.')
        return redirect('dashboard')
    
    return render(request, 'registration/activate_invite.html', {
        'claim': claim,
        'company': claim.company,
    })
```

---

## KORAK 4 — Ulaz C: Approve UI + Bulk invite script

### 4a. Approve view (Marija odobrava zahtjev)

```python
@login_required
def approve_claim(request, claim_id):
    """
    GET /firma/odobri/<claim_id>/
    Marija klika link iz WhatsAppa → vidi detalje → odobrava/odbija.
    """
    from registration.models import CompanyClaimRequest
    
    claim = get_object_or_404(CompanyClaimRequest, id=claim_id, status='pending')
    
    if not (request.user.is_superuser or 
            request.user.profile.company == claim.company.umbrella_parent):
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            user, temp_password = claim.approve(reviewed_by=request.user)
            
            # Pošalji login podatke vlasniku
            try:
                from core.email_tasks import send_email_task
                from django.conf import settings
                send_email_task.delay(
                    f'Pristup LIMIT Connect — {claim.company.name}',
                    f'Poštovani {claim.first_name},\n\n'
                    f'Vaš pristup firmi {claim.company.name} je odobren.\n\n'
                    f'Prijava: https://limit-connect.com/hr/login/\n'
                    f'Korisničko ime: {user.username}\n'
                    f'Privremena lozinka: {temp_password}\n\n'
                    f'Molimo promijenite lozinku pri prvoj prijavi.',
                    settings.DEFAULT_FROM_EMAIL,
                    [claim.email],
                )
            except Exception:
                pass
            
            messages.success(request, 
                f'Odobreno! {claim.first_name} može se prijaviti. '
                f'Login podaci poslani na {claim.email}.')
            return redirect('pending_claims')
        
        elif action == 'reject':
            claim.status = 'rejected'
            claim.reviewed_by = request.user
            claim.reject_reason = request.POST.get('reason', '')
            claim.save()
            messages.warning(request, 'Zahtjev odbijen.')
            return redirect('pending_claims')
    
    return render(request, 'registration/approve_claim.html', {'claim': claim})


@login_required  
def pending_claims(request):
    """
    GET /firma/zahtjevi/
    Marija vidi sve pending zahtjeve za odobrenje.
    """
    from registration.models import CompanyClaimRequest
    claims = CompanyClaimRequest.objects.filter(status='pending').select_related('company')
    return render(request, 'registration/pending_claims.html', {'claims': claims})
```

### 4b. Bulk invite management command

```python
# Kreiraj: management/commands/bulk_invite_ghost_firms.py
"""
Bulk invite za sve ghost firme u umbrelli.
Kreira invite tokene, sprema CSV za Mariju da pošalje WhatsApp/email.

Koristi:
    venv/bin/python manage.py bulk_invite_ghost_firms --umbrella "Konjik d.o.o."
    venv/bin/python manage.py bulk_invite_ghost_firms --umbrella "Konjik d.o.o." --dry-run
"""
from django.core.management.base import BaseCommand
from companies.models import Company
from accounts.models import UserProfile
from registration.models import CompanyClaimRequest
from django.utils import timezone
import csv
import sys

class Command(BaseCommand):
    help = 'Bulk invite za ghost firme u umbrelli'

    def add_arguments(self, parser):
        parser.add_argument('--umbrella', type=str, required=True)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        umbrella = Company.objects.filter(name__icontains=options['umbrella']).first()
        if not umbrella:
            self.stderr.write(f'Umbrella firma nije pronađena: {options["umbrella"]}')
            return

        children = Company.objects.filter(
            umbrella_parent=umbrella
        ).filter(
            userprofile__isnull=True
        ).distinct()

        self.stdout.write(f'Ghost firme u {umbrella.name}: {children.count()}')

        if options['dry_run']:
            for c in children:
                self.stdout.write(f'  {c.name} | OIB: {c.oib}')
            return

        # Kreiraj invite tokene i CSV
        writer = csv.writer(sys.stdout)
        writer.writerow(['Firma', 'OIB', 'Invite URL', 'WhatsApp poruka'])

        created = 0
        for firm in children:
            # Skip ako već ima pending claim
            if CompanyClaimRequest.objects.filter(company=firm, status='pending').exists():
                continue

            claim = CompanyClaimRequest.objects.create(
                company=firm,
                email=f'vlasnik@{firm.oib}.noreply',  # Placeholder dok ne dobijemo email
                first_name='Vlasnik',
                oib_confirmed=True,
                role_claimed='company_admin',
                token_expires=timezone.now() + timezone.timedelta(days=30),
            )

            invite_url = f'https://limit-connect.com/firma/aktiviraj/{claim.verify_token}/'
            wa_msg = (
                f'Pozdrav! Vaša firma *{firm.name}* je u LIMIT Connect sustavu.\n'
                f'Aktivirajte pristup: {invite_url}'
            )
            writer.writerow([firm.name, firm.oib, invite_url, wa_msg])
            created += 1

        self.stdout.write(f'\nKreirano {created} invite tokena.')
        self.stdout.write('CSV je ispisan na stdout — preusmjeri u fajl:')
        self.stdout.write('  venv/bin/python manage.py bulk_invite_ghost_firms --umbrella "Konjik" > invites.csv')
```

---

## KORAK 5 — URLs i routeregistry

```python
# Dodati u core/urls.py (PUBLIC — invite linkovi moraju raditi bez logina)
path('firma/preuzmi/<uuid:company_id>/', 
     __import__('registration.views', fromlist=['claim_company_form']).claim_company_form,
     name='claim_company'),
path('firma/preuzmi/<uuid:company_id>/submit/', 
     __import__('registration.views', fromlist=['submit_claim']).submit_claim,
     name='submit_claim'),
path('firma/aktiviraj/<str:token>/', 
     __import__('registration.views', fromlist=['activate_via_invite']).activate_via_invite,
     name='activate_invite'),

# Dodati u i18n_patterns (treba login)
path('firma/odobri/<uuid:claim_id>/', 
     __import__('registration.views', fromlist=['approve_claim']).approve_claim,
     name='approve_claim'),
path('firma/zahtjevi/', 
     __import__('registration.views', fromlist=['pending_claims']).pending_claims,
     name='pending_claims'),
path('posrednik/invite/<uuid:company_id>/', 
     __import__('registration.views', fromlist=['send_company_invite']).send_company_invite,
     name='send_company_invite'),
```

Dodati u `permissions/route_registry.py`:
```python
'claim_company':    AccessLevel.PUBLIC,
'submit_claim':     AccessLevel.PUBLIC,
'activate_invite':  AccessLevel.PUBLIC,
'approve_claim':    AccessLevel.AUTHENTICATED,
'pending_claims':   AccessLevel.AUTHENTICATED,
'send_company_invite': AccessLevel.AUTHENTICATED,
```

---

## KORAK 6 — Templatei (3 ključna)

### templates/registration/claim_company.html
- Prikazuje: naziv firme, OIB, broj faktura/partnera
- Forma: email, ime, prezime, telefon
- Tekst: "Vaša firma je već u sustavu. Unesite podatke i administrator će vam dati pristup."
- Ako pending=True: "Zahtjev je već poslan. Čekajte odobrenje."

### templates/registration/activate_invite.html
- Prikazuje: naziv firme, ime vlasnika, kratku statistiku (X faktura, Y partnera)
- Forma: lozinka + potvrda lozinke
- Gumb: "Aktivirajte pristup"

### templates/registration/approve_claim.html  
- Prikazuje: sve podatke claimera
- Firma statistika: fakture, partneri, journals
- Gumbi: "Odobri" | "Odbij (s razlogom)"

### templates/registration/pending_claims.html
- Lista svih pending zahtjeva
- Dostupno na: /firma/zahtjevi/
- Link iz Marija-inog dashboarda

---

## KORAK 7 — Sidebar link za Mariju

U base.html, u Marija-inu sekciju sidebara dodati:
```html
{% if user.is_staff or user.profile.role == 'company_admin' %}
<a href="{% url 'pending_claims' %}" onclick="closeSidebar()">
  <i class="fas fa-inbox"></i>
  <span>Zahtjevi za pristup</span>
  {% if pending_claims_count > 0 %}
  <span class="badge-red">{{ pending_claims_count }}</span>
  {% endif %}
</a>
{% endif %}
```

Context processor za badge:
```python
def pending_claims_badge(request):
    if not request.user.is_authenticated:
        return {'pending_claims_count': 0}
    try:
        from registration.models import CompanyClaimRequest
        from companies.models import Company
        
        user_company = request.user.profile.company
        count = CompanyClaimRequest.objects.filter(
            status='pending',
            company__umbrella_parent=user_company
        ).count()
        return {'pending_claims_count': count}
    except Exception:
        return {'pending_claims_count': 0}
```

---

## KORAK 8 — Verifikacija (OBAVEZNO prije commita)

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from registration.models import CompanyClaimRequest
from companies.models import Company

# Test 1: Claim request kreiranje
firm = Company.objects.filter(name__icontains='Sa-Ni Mont').first()
from django.utils import timezone

claim = CompanyClaimRequest.objects.create(
    company=firm,
    email='sanimonttest@test.com',
    first_name='Test',
    oib_confirmed=True,
    token_expires=timezone.now() + timezone.timedelta(days=7),
)
print(f'Claim kreiran: {claim.id}')
print(f'Token: {claim.verify_token[:20]}...')
print(f'is_token_valid: {claim.is_token_valid}')

# Test 2: Approve
from django.contrib.auth.models import User
marija = User.objects.get(username='marija.brtan')
user, pwd = claim.approve(reviewed_by=marija)
print(f'User kreiran: {user.username}')
print(f'Temp password: {pwd}')
print(f'Profile company: {user.profile.company.name}')
print(f'Može vidjeti Sa-Ni Mont fakture: {user.profile.company == firm}')

# Cleanup
user.delete()
claim.delete()
print('Test PASSED — cleanup done')
PYEOF

# Smoke test URLs
curl -s --max-time 8 -k -o /dev/null -w "claim form: %{http_code}\n" \
  https://limit-connect.com/firma/preuzmi/00000000-0000-0000-0000-000000000000/
```

---

## KORAK 9 — Bulk invite pokretanje (ODMAH po deploymentu)

```bash
# Dry run - provjeri
venv/bin/python manage.py bulk_invite_ghost_firms --umbrella "Konjik" --dry-run

# Stvarno kreiranje - output kao CSV za Mariju
venv/bin/python manage.py bulk_invite_ghost_firms --umbrella "Konjik" > /var/www/fina-connect/invites_konjik_$(date +%Y%m%d).csv

# Provjeri koliko tokena kreirano
venv/bin/python manage.py shell -c "
from registration.models import CompanyClaimRequest
print(f'Pending invite claims: {CompanyClaimRequest.objects.filter(status=\"pending\").count()}')
"
```

---

## COMMIT

```bash
git add registration/ companies/ templates/registration/ permissions/
git commit -m "feat(claim): Claim Your Business — 71 ghost firma dobiva pristup

CompanyClaimRequest model:
  - Vlasnik traži pristup firmi koja postoji bez korisnika
  - Token-based invite (30 dana valjanosti)
  - Status: pending → approved/rejected
  - approve() kreira User + UserProfile + CompanyMembership + UserRole

Tri ulaza u isti rezultat:
  A: /firma/preuzmi/<id>/ — vlasnik sam traži (OIB lookup → claim)
  B: /posrednik/invite/<id>/ — Marija šalje invite link vlasniku
  C: bulk_invite_ghost_firms management command — batch za sve 71

OIB lookup fix:
  'Firma u sustavu' → can_claim=True za firme bez vlasnika
  Direktan link na /firma/preuzmi/ umjesto DEAD END

WhatsApp: Marija dobiva obavijest + approve link
Email: Vlasnik dobiva login podaci nakon odobrenja

Sidebar badge: Marija vidi broj pending zahtjeva

NEMA DUPLICIRANJA PODATAKA — user se veže na POSTOJEĆU firmu
Vlasnik odmah vidi sve stare fakture, partnere, journals"
```

---

## VREMENSKI PLAN DO 15.04.

```
31.03. (sutra):  CC Code: Model + Korak 1-3 (core flow)
01.04.:          CC Code: Templatei + URLs (Korak 4-6)  
02.04.:          CC Code: Bulk invite script + verifikacija (Korak 7-9)
03.04.:          Ivan/Marija: Pokreni bulk invite za sve 71 firme
03-10.04.:       Vlasnici primaju WhatsApp/link → aktiviraju se
10.04.:          Review — koliko je aktivirano, što blokira
12-15.04.:       Finalni push — ručni follow-up za ostatak

CILJ: 50+ od 71 firmi aktivno do 15.04.
```

---

## NAPOMENE ZA CC

1. `CompanyClaimRequest` ide u `registration/models.py` — tamo već postoji CompanySubscription, UmbrellaInviteCode
2. `approve()` metoda mora biti transakciona — koristiti `@transaction.atomic`
3. Email za ghost firme: nemaju email u bazi. Za Ulaz A vlasnik upisuje email. Za Ulaz C Marija mora dodati email ručno ili CSV.
4. `bulk_invite_ghost_firms` command — kreiraj direktorij `registration/management/commands/` ako ne postoji
5. Sidebar badge (`pending_claims_count`) — dodaj u TEMPLATES context_processors u settings.py
6. OBAVEZNO: Javi Sonnet kad je Korak 9 (bulk invite) pokrenuto — pratimo konverziju

---

## STATUS: READY_FOR_CC_CODE — ROK 15.04. FIKSAN
