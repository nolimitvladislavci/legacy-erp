# CC_TASK_BORG_ACTIVATION.md
# Za: CC Code
# Rok: 15.04.2026. — ČVRST ROK
# Datum: 2026-03-30
# Prioritet: MAKSIMALNI — blokira 71 firmu s pravim podacima
#
# KONTEKST — ŠTO SE DOGODI:
# 92 firme u sustavu. 71 od njih ima prave podatke (fakture, partnere, konto)
# iz Synesis migracije koje je Marija Brtan unijela. Ali nitko se ne može
# prijaviti jer nema korisničkih računa. Vlasnici firmi ne znaju da im
# podaci čekaju. Ovo je "zarobljeni kapital" koji Marija mora osloboditi.
#
# ODMAH POPRAVLJENO (ne diraj):
# - 13 broken 2FA korisnika: totp_enabled→False ✓
# - 72 Konjik children: TC consent potpisan ✓
# - 12 korisnika: email_verified→True ✓
#
# ŠTO OSTAJE (ovaj task):
# Invite Engine + SmartEntry + Activation Dashboard + WhiteLabel + FAL Faza 4
#
# OVO JE "ODIJELO" PLATFORME — kad ovo bude gotovo, platforma je Borg.
# Server i infrastruktura slijede prihod. Kod ide prvi.

---

## MODUL 1 — Invite Engine (KRITIČNO — rok 3 dana)

### Što je problem
71 firma ima podatke. Nema emailova vlasnika u bazi.
Marija zna tko su ti vlasnici (vodi im računovodstvo).
Marija mora moći poslati personaliziranu pozivnicu svakom vlasniku.
Vlasnik klikne link → postaje korisnik → vidi svoje podatke.

### M1.1 — InviteToken model

```python
# accounts/models.py ili novi accounts/invite_models.py

import uuid
import secrets
from django.db import models
from django.utils import timezone

class CompanyInviteToken(models.Model):
    """
    Pozivnica za korisnika da pristupi postojećoj firmi.
    Marija generira, vlasnik firme klikne link → postaje korisnik.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    token = models.CharField(
        max_length=64, unique=True,
        default=secrets.token_urlsafe,
        db_index=True
    )
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='invite_tokens'
    )
    invited_by = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE,
        related_name='sent_invites'
    )
    # Što znamo o primatelju
    email = models.EmailField(help_text='Email vlasnika firme')
    first_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=30, default='company_admin',
        choices=[
            ('company_admin', 'Vlasnik / Admin'),
            ('accountant', 'Računovođa'),
            ('worker', 'Radnik'),
            ('partner', 'Partner'),
        ]
    )
    message = models.TextField(blank=True,
        help_text='Osobna poruka Marije klijentu')

    # Status
    STATUS = [
        ('pending', 'Čeka prihvaćanje'),
        ('accepted', 'Prihvaćeno'),
        ('expired', 'Isteklo'),
        ('cancelled', 'Otkazano'),
    ]
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accepted_invites'
    )

    # Tracking
    email_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)  # pixel tracking
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # default: 30 dana

    class Meta:
        verbose_name = 'Pozivnica za firmu'
        verbose_name_plural = 'Pozivnice za firme'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company.name} → {self.email} ({self.status})'

    @property
    def is_valid(self):
        return self.status == 'pending' and timezone.now() < self.expires_at

    @property
    def invite_url(self):
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://limit-connect.com')
        return f'{base}/pozivnica/{self.token}/'

    def mark_accepted(self, user):
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=['status', 'accepted_at', 'accepted_by'])

    @classmethod
    def create_for_company(cls, company, email, invited_by,
                           first_name='', role='company_admin',
                           message='', days=30):
        from datetime import timedelta
        # Canceli stare pending pozivnice za isti email+firma
        cls.objects.filter(
            company=company, email=email, status='pending'
        ).update(status='cancelled')

        return cls.objects.create(
            company=company,
            email=email,
            first_name=first_name,
            invited_by=invited_by,
            role=role,
            message=message,
            expires_at=timezone.now() + timedelta(days=days),
        )
```

Migracija:
```bash
venv/bin/python manage.py makemigrations accounts --name company_invite_token
venv/bin/python manage.py migrate
```

### M1.2 — Invite prihvaćanje (accept_invite view)

```python
# accounts/auth_views.py — dodati

def accept_invite(request, token):
    """
    GET/POST /pozivnica/<token>/
    Vlasnik firme prihvaća pozivnicu i kreira korisnika ili se prijavljuje.
    """
    from accounts.models import CompanyInviteToken

    try:
        invite = CompanyInviteToken.objects.select_related('company').get(token=token)
    except CompanyInviteToken.DoesNotExist:
        return render(request, 'accounts/invite_invalid.html', {
            'reason': 'Pozivnica ne postoji.'
        })

    if not invite.is_valid:
        return render(request, 'accounts/invite_invalid.html', {
            'reason': 'Pozivnica je istekla ili već prihvaćena.',
            'company': invite.company.name,
        })

    # Bilježi otvaranje
    if not invite.opened_at:
        invite.opened_at = timezone.now()
        invite.save(update_fields=['opened_at'])

    # Postoji li korisnik s tim emailom?
    from django.contrib.auth.models import User
    existing_user = User.objects.filter(email__iexact=invite.email, is_active=True).first()

    if request.method == 'GET':
        return render(request, 'accounts/accept_invite.html', {
            'invite': invite,
            'company': invite.company,
            'existing_user': existing_user,
            'email': invite.email,
        })

    # POST — prihvaćanje
    if existing_user:
        # Korisnik postoji → dodaj u firmu, prijavi ga
        _add_user_to_company(existing_user, invite)
        invite.mark_accepted(existing_user)
        from django.contrib.auth import login
        login(request, existing_user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('dashboard')
    else:
        # Novi korisnik → kreiraj account
        password = request.POST.get('password1', '')
        if len(password) < 8:
            return render(request, 'accounts/accept_invite.html', {
                'invite': invite, 'company': invite.company,
                'error': 'Lozinka mora imati najmanje 8 znakova.',
                'email': invite.email,
            })

        base_un = invite.email.split('@')[0].lower().replace('.', '_')[:28]
        username = base_un
        i = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_un}{i}'; i += 1

        user = User.objects.create_user(
            username=username,
            email=invite.email,
            password=password,
            first_name=invite.first_name or invite.email.split('@')[0].title(),
        )

        _add_user_to_company(user, invite)
        invite.mark_accepted(user)

        from django.contrib.auth import login
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('dashboard')


def _add_user_to_company(user, invite):
    """Poveži korisnika s firmom iz pozivnice."""
    from accounts.models import UserProfile, CompanyMembership
    from django.utils import timezone

    # UserProfile
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'company': invite.company,
            'role': invite.role,
            'email_verified': True,
            'email_verified_at': timezone.now(),
        }
    )
    if not created and profile.company != invite.company:
        # Korisnik već ima profil — dodaj kao membership
        pass

    # CompanyMembership
    from accounts.models import CompanyMembership
    CompanyMembership.objects.get_or_create(
        user=user,
        company=invite.company,
        defaults={
            'role': invite.role,
            'is_active': True,
            'is_default': True,
        }
    )

    # RBAC UserRole
    try:
        from permissions.models import Role, UserRole
        role = Role.objects.get(role_type=invite.role)
        UserRole.objects.get_or_create(
            user=user, role=role, company=invite.company,
            defaults={'is_primary': True}
        )
    except Exception:
        pass

    # TC Consent (vlasnik prihvaća pozivnicu = prihvaća uvjete)
    invite.company.has_signed_tc_consent = True
    invite.company.tc_consent_version = 'v1.0-2026'
    invite.company.tc_consent_signed_at = timezone.now()
    invite.company.save(update_fields=['has_signed_tc_consent', 'tc_consent_version', 'tc_consent_signed_at'])
```

### M1.3 — URL registracija

```python
# core/urls.py (PUBLIC, bez i18n prefiksa — mora raditi iz email linka):
path('pozivnica/<str:token>/',
     __import__('accounts.auth_views', fromlist=['accept_invite']).accept_invite,
     name='accept_invite'),
path('api/auth/send-invite/',
     __import__('accounts.invite_views', fromlist=['send_invite_api']).send_invite_api,
     name='send_invite_api'),
```

RouteRegistry:
```python
'accept_invite': AccessLevel.PUBLIC,
'send_invite_api': AccessLevel.AUTHENTICATED,
```

### M1.4 — Bulk Invite view (Marija koristi ovo)

```python
# accounts/invite_views.py — novi fajl

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
import json

@login_required
def bulk_invite_view(request):
    """
    /moji-klijenti/pozovi/ — Marija poziva klijente u bulk.
    Prikazuje listu firmi pod Konjik umbrellom bez korisnika.
    Marija može za svaku upisati email i poslati pozivnicu jednim klikom.
    """
    from companies.models import Company

    try:
        my_company = request.user.profile.company
    except Exception:
        return redirect('dashboard')

    # Sve firme pod ovom umbrellom
    children = Company.objects.filter(umbrella_parent=my_company)

    # Koje nemaju korisnika
    from accounts.models import UserProfile, CompanyInviteToken
    firms_data = []
    for c in children.order_by('name'):
        has_user = UserProfile.objects.filter(company=c).exists()
        pending_invite = CompanyInviteToken.objects.filter(
            company=c, status='pending'
        ).first()
        accepted_invite = CompanyInviteToken.objects.filter(
            company=c, status='accepted'
        ).first()

        # Broj faktura (pokazuje vrijednost podataka)
        try:
            from invoicing.models import Invoice
            inv_count = Invoice.objects.filter(company=c).count()
        except:
            inv_count = 0

        firms_data.append({
            'company': c,
            'has_user': has_user,
            'invoice_count': inv_count,
            'pending_invite': pending_invite,
            'accepted_invite': accepted_invite,
            'status': 'active' if has_user else ('invited' if pending_invite else 'waiting'),
        })

    stats = {
        'total': len(firms_data),
        'active': sum(1 for f in firms_data if f['status'] == 'active'),
        'invited': sum(1 for f in firms_data if f['status'] == 'invited'),
        'waiting': sum(1 for f in firms_data if f['status'] == 'waiting'),
    }

    return render(request, 'accounts/bulk_invite.html', {
        'firms': firms_data,
        'stats': stats,
        'my_company': my_company,
    })


@login_required
def send_invite_api(request):
    """
    POST /api/auth/send-invite/
    Pošalji pozivnicu za jednu firmu.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    company_id = data.get('company_id')
    email = data.get('email', '').strip()
    first_name = data.get('first_name', '').strip()
    role = data.get('role', 'company_admin')
    message = data.get('message', '')
    channel = data.get('channel', 'email')  # 'email' ili 'whatsapp'

    if not company_id or not email:
        return JsonResponse({'ok': False, 'error': 'company_id i email su obavezni'})

    from companies.models import Company
    from accounts.models import CompanyInviteToken

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Firma ne postoji'})

    # Kreiraj invite token
    invite = CompanyInviteToken.create_for_company(
        company=company,
        email=email,
        invited_by=request.user,
        first_name=first_name,
        role=role,
        message=message,
    )

    # Pošalji pozivnicu
    if channel == 'whatsapp':
        _send_invite_whatsapp(invite, request.user)
    else:
        _send_invite_email(invite, request.user)

    return JsonResponse({
        'ok': True,
        'invite_url': invite.invite_url,
        'token': invite.token,
        'expires': invite.expires_at.isoformat(),
    })


def _send_invite_email(invite, sender):
    """Pošalji pozivnicu emailom."""
    from django.conf import settings
    from core.email_tasks import send_email_task

    sender_name = sender.get_full_name() or sender.username
    company_name = invite.company.name

    subject = f'Pozivnica — pristup vašim podacima u {company_name}'
    body = f'''Poštovani {invite.first_name or ''},

{sender_name} vas poziva da pristupite poslovnim podacima firme {company_name} u LIMIT Connect sustavu.

Vaši podaci su već pripremljeni — možete vidjeti fakture, partnere i financijske izvještaje.

Kliknite na link da prihvatite pozivnicu:
{invite.invite_url}

Link vrijedi 30 dana.

{('Poruka od ' + sender_name + ': ' + invite.message) if invite.message else ''}

— LIMIT Connect | limit-connect.com
'''
    send_email_task.delay(
        subject, body, settings.DEFAULT_FROM_EMAIL, [invite.email]
    )
    invite.email_sent_at = __import__('django.utils.timezone', fromlist=['timezone']).timezone.now()
    invite.save(update_fields=['email_sent_at'])


def _send_invite_whatsapp(invite, sender):
    """Pošalji pozivnicu WhatsAppom."""
    try:
        from core.whatsapp import send_text
        sender_name = sender.get_full_name() or sender.username
        msg = (
            f'Pozdrav {invite.first_name or ""}! '
            f'{sender_name} vas poziva da pristupite podacima firme '
            f'{invite.company.name} u LIMIT Connect sustavu.\n\n'
            f'Kliknite: {invite.invite_url}\n\n'
            f'Vaši podaci su već unutra!'
        )
        send_text(phone=invite.email, message=msg)  # email kao placeholder — treba phone number
        from django.utils import timezone
        invite.whatsapp_sent_at = timezone.now()
        invite.save(update_fields=['whatsapp_sent_at'])
    except Exception as e:
        import logging
        logging.getLogger('invite').error(f'WhatsApp invite failed: {e}')
```

---

## MODUL 2 — SmartEntry /pocni/ (KRITIČNO — rok 1 dan)

### Direktno iz CC_TASK_SMART_ENTRY_I_POSREDNIK.md — implementiraj sve.

Provjeri što od toga postoji:
```bash
# Provjeri postoji li /pocni/ URL
venv/bin/python manage.py shell -c "
from django.urls import reverse
try:
    print('smart_entry:', reverse('smart_entry'))
except: print('smart_entry: NE POSTOJI')
try:
    print('detect_email:', reverse('detect_email'))
except: print('detect_email: NE POSTOJI')
"
```

Ako ne postoji — implementiraj prema CC_TASK_SMART_ENTRY_I_POSREDNIK.md.

Jedina razlika: SmartEntry template sada mora imati treći state:
```
NEW_USER         → registracija (postojeće)
EXISTING_USER    → magic link (postojeće)
INVITE_PENDING   → "Imate pozivnicu! Prijavite se da je prihvatite."
```

Detect email API proširiti:
```python
# U detect_email view — dodati provjeru invite tokena:
from accounts.models import CompanyInviteToken
pending_invite = CompanyInviteToken.objects.filter(
    email__iexact=email,
    status='pending'
).select_related('company').first()

if pending_invite and pending_invite.is_valid:
    return JsonResponse({
        'state': 'INVITE_PENDING',
        'email': email,
        'company_name': pending_invite.company.name,
        'invite_url': pending_invite.invite_url,
        'message': f'Imate pozivnicu za {pending_invite.company.name}! Kliknite da prihvatite.',
    })
```

---

## MODUL 3 — Activation Dashboard (Marija vidi status)

### M3.1 — /moji-klijenti/ view

```python
# Proširiti agent_dashboard (iz CC_TASK_SMART_ENTRY_I_POSREDNIK.md)
# da uključi Invite status

@login_required
def activation_dashboard(request):
    """
    /moji-klijenti/ — kompletni dashboard za Mariju/Kruljac.
    Prikazuje: klijenti, invite status, prihodi, invite linkovi.
    """
    from companies.models import Company
    from accounts.models import CompanyInviteToken, UserProfile

    try:
        my_company = request.user.profile.company
    except Exception:
        return redirect('dashboard')

    # Sve firme
    children = Company.objects.filter(umbrella_parent=my_company).order_by('name')

    dashboard_data = []
    for c in children:
        users = UserProfile.objects.filter(company=c).select_related('user')
        latest_invite = CompanyInviteToken.objects.filter(
            company=c
        ).order_by('-created_at').first()

        try:
            from invoicing.models import Invoice
            from django.db.models import Sum
            inv_data = Invoice.objects.filter(company=c).aggregate(
                count=__import__('django.db.models', fromlist=['Count']).Count('id'),
                total=Sum('grand_total')
            )
        except:
            inv_data = {'count': 0, 'total': 0}

        if users.exists():
            status = 'active'
        elif latest_invite and latest_invite.status == 'accepted':
            status = 'active'
        elif latest_invite and latest_invite.status == 'pending':
            status = 'invited'
        else:
            status = 'waiting'

        dashboard_data.append({
            'company': c,
            'status': status,
            'users': list(users),
            'latest_invite': latest_invite,
            'invoice_count': inv_data.get('count', 0),
            'invoice_total': inv_data.get('total', 0),
        })

    # Generirni invite link za ovaj account
    from registration.models import UmbrellaInviteCode
    invite_code = UmbrellaInviteCode.objects.filter(
        umbrella_company=my_company, is_active=True
    ).first()

    return render(request, 'accounts/activation_dashboard.html', {
        'firms': dashboard_data,
        'my_company': my_company,
        'invite_code': invite_code,
        'invite_link': f'https://limit-connect.com/pocni/?ref={invite_code.code}' if invite_code else None,
        'stats': {
            'total': len(dashboard_data),
            'active': sum(1 for f in dashboard_data if f['status'] == 'active'),
            'invited': sum(1 for f in dashboard_data if f['status'] == 'invited'),
            'waiting': sum(1 for f in dashboard_data if f['status'] == 'waiting'),
        }
    })
```

### M3.2 — Template: templates/accounts/activation_dashboard.html

UI elementi:
- **Hero**: 3 kartice — Aktivni klijenti / Poslana pozivnica / Čekaju pozivnicu
- **Invite link widget**: copy-to-clipboard, QR kod
- **Firma lista** s tri sekcije (accordion ili tabs):
  - **Čekaju pozivnicu** (71 firma) → inline form: email + ime + POŠALJI gumb
  - **Pozvani** (čekaju odgovor) → "Pošalji podsjetnik" gumb
  - **Aktivni** → zeleni checkmark, username, zadnji login
- **WhatsApp gumb** za svaki red → otvara wa.me/ link s predpopunjenom porukom

### M3.3 — URL

```python
# core/urls.py u i18n_patterns:
path('moji-klijenti/', 
     __import__('accounts.invite_views', fromlist=['activation_dashboard']).activation_dashboard,
     name='activation_dashboard'),
path('moji-klijenti/pozovi/',
     __import__('accounts.invite_views', fromlist=['bulk_invite_view']).bulk_invite_view,
     name='bulk_invite'),
```

Sidebar link (base.html) — pokazuje se kad je user umbrella admin:
```html
{% if request.user.profile.company.is_umbrella %}
  <a href="{% url 'activation_dashboard' %}">
    <i class="fas fa-users"></i> <span>Moji klijenti</span>
  </a>
{% endif %}
```

---

## MODUL 4 — WhiteLabel Engine (rok 1 dan)

Implementirati prema CC_TASK_LICENSING_ENGINE.md.

PROVJERI i dopuni:
```bash
grep -rn "WhiteLabelConfig" /var/www/fina-connect --include="*.py" | grep -v venv | grep -v test
```

Ako model ne postoji → kreiraj prema task fajlu.

---

## MODUL 5 — FAL Faza 4: Audit Log fix (rok 1 dan)

### Kritičan problem
`core_systemauditlog` ima 1.254.041 redaka u jednom mjesecu.
74% baze. `konto.LedgerLine` (806k) i `konto.JournalEntry` (227k) su immutable
modeli koji se nikad ne mijenjaju — auditiranje ih je besmisleno i skupo.

### Fix

```python
# Provjeri koji middleware/signal radi audit log
grep -rn "AuditLog\|audit_log\|SystemAuditLog\|AuditMiddleware" /var/www/fina-connect/core/ --include="*.py" | head -20
```

Isključi audit za volume tablice:
```python
# U konto/models.py — pronađi LedgerLine i JournalEntry klase
# Dodaj class attribute koji AuditMiddleware poštuje:

class LedgerLine(models.Model):
    AUDIT_ENABLED = False  # Immutable — ne treba audit
    # ... ostatak modela

class JournalEntry(models.Model):
    AUDIT_ENABLED = False  # Immutable — ne treba audit
    # ... ostatak modela
```

AuditMiddleware provjera:
```python
# core/audit.py — pronađi gdje se kreira SystemAuditLog
# Dodaj provjeru:
if not getattr(sender, 'AUDIT_ENABLED', True):
    return  # Skip audit za ovaj model
```

Rotacija starih logova (arhiviranje):
```python
# core/management/commands/archive_audit_log.py
# Management command koji se pokreće svake nedjelje:
# Premješta zapise starije od 90 dana u audit_archive tablicu
# ili briše ako nije potrebno za compliance
```

---

## VERIFIKACIJA — Kompletni scenarij

Nakon implementacije, test:

```bash
venv/bin/python manage.py shell << 'PYEOF'
# 1. Marija kreira pozivnicu za Sa-Ni Mont
from companies.models import Company
from accounts.models import CompanyInviteToken
from django.contrib.auth.models import User

marija = User.objects.get(username='marija.brtan')
sani = Company.objects.filter(name__icontains='Sa-Ni').first()

invite = CompanyInviteToken.create_for_company(
    company=sani,
    email='test@saninimont.hr',
    invited_by=marija,
    first_name='Petar',
    message='Vaši podaci su pripremljeni, čeka vas 209 faktura.',
)
print(f'Pozivnica kreirana: {invite.invite_url}')
print(f'Valid: {invite.is_valid}')

# 2. Provjeri /pocni/ detektira INVITE_PENDING
from django.test import Client
c = Client()
import json
resp = c.post('/api/auth/detect-email/',
    json.dumps({'email': 'test@saninimont.hr'}),
    content_type='application/json')
data = resp.json()
print(f'detect_email state: {data["state"]} (očekivano: INVITE_PENDING)')
print(f'company: {data.get("company_name")}')

# 3. Provjeri activation dashboard
print(f'\nFirme bez korisnika (treba ići na 0):')
from accounts.models import UserProfile
no_user = Company.objects.filter(umbrella_parent__name__icontains='Konjik').exclude(
    userprofile__isnull=False
)
print(f'  {no_user.count()} firmi bez korisnika')

PYEOF
```

---

## REDOSLIJED IMPLEMENTACIJE (15.04. rok)

```
Dan 1 (31.03):
  ✓ CompanyInviteToken model + migracija
  ✓ accept_invite view + template
  ✓ send_invite_api view

Dan 2 (01.04):
  ✓ SmartEntry /pocni/ (detect_email + INVITE_PENDING state)
  ✓ Activation dashboard (/moji-klijenti/)
  ✓ bulk_invite_view

Dan 3 (02.04):
  ✓ WhiteLabelConfig model + middleware + context processor
  ✓ base.html integracija

Dan 4 (03.04):
  ✓ FAL Faza 4: Audit log fix (LedgerLine, JournalEntry)
  ✓ Redis caching za permissions i WhiteLabel

Dan 5 (04.04):
  ✓ Test suite: sve scenarije
  ✓ Marija šalje pozivnice za 71 firmu
  ✓ FENIX_STATUS.md ažuriran

Dana 6-15 (buffer):
  ✓ Bugfixi koji izađu
  ✓ UX poboljšanja na temelju prvih pozivnica
  ✓ WhatsApp notifikacije za prihvaćene pozivnice
```

---

## COMMIT SEKVENCA

```bash
git add accounts/ templates/accounts/ core/urls.py permissions/route_registry.py
git commit -m "feat(borg-activation): Invite Engine + SmartEntry + Activation Dashboard

CompanyInviteToken model:
  - token, company, email, role, status, expires_at
  - email_sent_at, whatsapp_sent_at, opened_at, reminder_sent_at
  - create_for_company() factory, is_valid property

accept_invite view (/pozivnica/<token>/):
  - Detektira postojeći vs novi korisnik
  - Kreira korisnika, veže ga uz firmu
  - TC consent automatski prihvaćen
  - RBAC UserRole dodijeljen

detect_email API — prošireno s INVITE_PENDING state

Activation Dashboard (/moji-klijenti/):
  - 3 sekcije: Čekaju / Pozvani / Aktivni
  - Inline send invite form
  - WhatsApp deeplink za svaku firmu
  - Invite kod + copy-to-clipboard

WhiteLabelConfig + WhiteLabelMiddleware
FAL Faza 4: Audit log — LedgerLine/JournalEntry AUDIT_ENABLED=False

71 firma s pravim podacima sada dobiva put do aktivacije."
```

---

## NAPOMENE ZA CC

1. **Redoslijed je bitan**: InviteToken model i accept_invite MORAJU ići prije SmartEntry
   jer SmartEntry ovisi o InviteToken za INVITE_PENDING state.

2. **accept_invite view je PUBLIC** (RouteRegistry) — ne treba login za otvaranje linka.
   Nakon prihvaćanja → automatski se prijavljuje.

3. **Email je sve što imamo** — nijedna firma nema telefon u bazi.
   WhatsApp kanal u send_invite_api treba phone number, email nemoj koristiti.
   Za sada: email je primarni kanal, WhatsApp je Marija šalje ručno.

4. **Activation dashboard** je prioritet iznad bulk_invite_view —
   Marija treba vidjeti status prve. Bulk send je sekundaran.

5. **OBAVEZNO verificiraj**: nakon implementacije pokreni verifikacijski shell.
   Posebno: detect_email → INVITE_PENDING state mora raditi.

6. **Javi Sonnet**: "BORG ACTIVATION DONE" + URL /pozivnica/ + URL /moji-klijenti/
   + broj firmi koje su prešle iz 'waiting' u 'invited' status.

---

## STATUS: READY_FOR_CC_CODE
## Rok: 15.04.2026. — BORG ACTIVATION kompletna
