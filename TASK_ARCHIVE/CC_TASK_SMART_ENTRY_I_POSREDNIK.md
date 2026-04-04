# CC_TASK_SMART_ENTRY_I_POSREDNIK.md
# Za: CC Code
# Datum: 2026-03-30
# Prioritet: VISOKO — blokira rast, Marija i Kruljac čekaju
# Procjena: 2-3 dana (3 faze, svaka deployable)
#
# FILOZOFIJA:
# Ne rješavamo poruke o greškama — rješavamo da greška nikad ne nastane.
# Ne pravimo "posrednički modul" — aktiviramo ono što već postoji.
#
# KONTEKST:
# - AgentReferral model: postoji, 66 referrala, 0 agenata (nikad seedano)
# - UmbrellaInviteCode: postoji, 0 kodova (nikad generiran)
# - CompanyPartnership: postoji, 71 veza (Konjik umbrella)
# - Korpaš umbrella: 6 children (Kruljac, KUD Dukat, Čizo...)
# - SmartEntry: ne postoji, radi se u ovom tasku
#
# DVA MODELA POSREDNIŠTVA (NE MIJEŠATI):
# Model A = Informacijski posrednik (Zakon o fiskalizaciji, ISO 27001 potreban)
#           → Konjik d.o.o. prema FINA/Poreznoj — ZASEBNI PROJEKT
# Model B = Reseller/Agent (poslovni model, bez posebne licence)
#           → Marija i Kruljac dovode klijente, dobivaju proviziju — ODMAH MOGUĆE
#
# Ovaj task rješava Model B + SmartEntry koji sve to omogućuje.

---

## FAZA A — SmartEntry (bez dead endova)

### A1. Backend: detect-email + smart-entry-magic

Dodati u `accounts/auth_views.py`:

```python
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
import json

@require_POST
@csrf_protect
def detect_email(request):
    """
    POST /api/auth/detect-email/
    Detektira stanje korisnika po emailu — nema dead endova.

    Vraća:
      NEW_USER      → može se registrirati
      EXISTING_USER → šaljemo magic link, nudi login
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
    except Exception:
        email = request.POST.get('email', '').strip().lower()

    if not email or '@' not in email:
        return JsonResponse({'state': 'INVALID', 'message': 'Unesite ispravnu email adresu.'})

    from django.contrib.auth.models import User
    user = User.objects.filter(email__iexact=email, is_active=True).first()

    if not user:
        return JsonResponse({'state': 'NEW_USER', 'email': email})

    # Postojeći korisnik — personalizirani odgovor bez osjetljivih podataka
    from accounts.models import CompanyMembership
    first_name = user.first_name or ''
    membership = CompanyMembership.objects.filter(
        user=user, is_active=True
    ).select_related('company').first()
    company_name = membership.company.name if membership else None

    return JsonResponse({
        'state': 'EXISTING_USER',
        'email': email,
        'first_name': first_name,
        'company_name': company_name,
        'login_url': '/hr/login/?email=' + email,
        'reset_url': '/password-reset/',
    })


@require_POST
@csrf_protect
def smart_entry_magic(request):
    """
    POST /api/auth/smart-entry-magic/
    Šalje magic login link za postojeće korisnike.
    Rate limit: 3 pokušaja / 10 minuta po IP-u.
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
    except Exception:
        email = request.POST.get('email', '').strip()

    # Sigurnosni odgovor — ne otkrivamo postoji li korisnik
    generic_ok = JsonResponse({'sent': True, 'message': 'Link poslan ako email postoji.'})

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        return generic_ok

    from accounts.auth_models import LoginAttempt, MagicToken
    ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')

    if LoginAttempt.is_blocked(ip, email, max_attempts=3, minutes=10):
        return JsonResponse({
            'sent': False,
            'retry_after': 600,
            'message': 'Link je nedavno poslan. Provjerite inbox ili pričekajte 10 minuta.',
        })

    magic = MagicToken.create_for_user(user, token_type='entry', hours=24)
    base_url = getattr(settings, 'SITE_URL', 'https://limit-connect.com')
    magic_url = f'{base_url}/auth/magic/{magic.token}/'

    from core.email_tasks import send_email_task
    send_email_task.delay(
        'LIMIT Connect — Link za prijavu',
        f'Poštovani {user.first_name or ""},\n\nKliknite za prijavu (vrijedi 24h):\n\n{magic_url}\n\n— LIMIT Connect',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    LoginAttempt.objects.create(email=email, ip_address=ip, success=True, method='smart_entry')
    masked = email[:3] + '***' + email[email.index('@'):]

    return JsonResponse({'sent': True, 'message': f'Link poslan na {masked}.'})
```

Dodati `'entry'` tip u `MagicToken.TOKEN_TYPE` (accounts/auth_models.py):
```python
('entry', _('Smart Entry — login link')),
```

Migracija:
```bash
venv/bin/python manage.py makemigrations accounts --name magic_token_entry_type
venv/bin/python manage.py migrate
```

### A2. View za SmartEntry stranicu

Dodati u `registration/views.py`:
```python
def smart_entry_page(request):
    """Jedna URL za sve: /pocni/ — email-first, nema dead endova."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    # Provjeri ?ref= parametar za agent referral
    ref_code = request.GET.get('ref', '').upper()
    plan = request.GET.get('plan', 'starter')
    return render(request, 'registration/smart_entry.html', {
        'ref_code': ref_code,
        'plan': plan,
    })
```

### A3. URL registracija

Dodati u `core/urls.py` (PUBLIC, bez i18n prefiksa):
```python
path('pocni/', __import__('registration.views', fromlist=['smart_entry_page']).smart_entry_page, name='smart_entry'),
path('api/auth/detect-email/', __import__('accounts.auth_views', fromlist=['detect_email']).detect_email, name='detect_email'),
path('api/auth/smart-entry-magic/', __import__('accounts.auth_views', fromlist=['smart_entry_magic']).smart_entry_magic, name='smart_entry_magic'),
```

Dodati u `permissions/route_registry.py`:
```python
'smart_entry':       AccessLevel.PUBLIC,
'detect_email':      AccessLevel.PUBLIC,
'smart_entry_magic': AccessLevel.PUBLIC,
```

### A4. Template: templates/registration/smart_entry.html

DIZAJN ZAHTJEVI:
- Jedan email field, jedan gumb, sve ostalo dinamički (AJAX)
- Stanje NEW_USER: prikaži mini-form (ime, firma, lozinka)
- Stanje EXISTING_USER: personalizirani pozdrav + magic link gumb + "Imam lozinku" link
- Stanje SENT: potvrda s maskiranim emailom + "pošalji ponovo" link
- Ref kod: ako postoji ?ref=MARIJA, prikaži "Registrirate se kod [Marija Brtan]"
- Responsive, dark tema, bez JS frameworka
- Cijeli flow: email → stanje → akcija = MAX 3 klika

Koristiti dark temu `/var/www/fina-connect/templates/website/brosura_croxmlverify.html` kao vizualni referent.

---

## FAZA B — Agent/Posrednik aktivacija

### B1. Seed Agent statusa za Mariju i Kruljac

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from partners.models import Partner, AgentReferral
from companies.models import Company, CompanyPartnership
from django.contrib.auth.models import User
from registration.models import UmbrellaInviteCode
from django.utils import timezone
import secrets

korpas = Company.objects.get(name='Korpaš d.o.o.')

# ── Marija Brtan kao agent ────────────────────────────────────
konjik = Company.objects.get(name__icontains='Konjik')
marija_user = User.objects.get(username='marija.brtan')

# Kreiraj Partner zapis za Mariju kao agenta
marija_partner, _ = Partner.objects.get_or_create(
    company=konjik,
    name='Marija Brtan',
    defaults={
        'partner_type': 'agent',
        'email': marija_user.email,
        'oib': '70086599476',
    }
)
print(f'Marija agent partner: {marija_partner.name} | type={marija_partner.partner_type}')

# ── Kruljac Ivica kao agent ───────────────────────────────────
ivica_user = User.objects.get(username='opg_kruljac')

kruljac_partner, _ = Partner.objects.get_or_create(
    company=korpas,
    name='Kruljac Ivica',
    defaults={
        'partner_type': 'agent',
        'email': 'opg.kruljac@limit-connect.com',
        'oib': '82540277049',
    }
)
print(f'Kruljac agent partner: {kruljac_partner.name} | type={kruljac_partner.partner_type}')

# ── Generiraj UmbrellaInviteCode za svakog agenta ─────────────
for agent_partner, umbrella, code, label in [
    (marija_partner, konjik,  'REF-MARIJA-2026', 'Marija Brtan'),
    (kruljac_partner, korpas, 'REF-KORPAŠ-2026', 'Kruljac Ivica'),
]:
    invite, created = UmbrellaInviteCode.objects.get_or_create(
        code=code,
        defaults={
            'umbrella_company': umbrella,
            'plan_slug': 'starter',
            'relation_type': 'client',
            'max_uses': 100,
            'free_months': 1,
            'created_by': User.objects.filter(is_superuser=True).first(),
            'note': f'Referral kod za {label}',
        }
    )
    print(f'InviteCode {"kreiran" if created else "postoji"}: {code} → {umbrella.name}')

print('\nAgent setup GOTOV.')
PYEOF
```

### B2. Povezi AgentReferral sa pretplatama

Provjeri ima li AgentReferral linked na CompanySubscription:
```bash
grep -n "AgentReferral\|referral\|agent" registration/models.py | head -10
```

Ako nema direktne veze, dodati FK u `CompanySubscription`:
```python
# U registration/models.py — CompanySubscription:
referral = models.ForeignKey(
    'partners.AgentReferral',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='subscriptions',
    verbose_name='Referral (agent)',
)
```

Migracija:
```bash
venv/bin/python manage.py makemigrations registration --name subscription_referral_link
venv/bin/python manage.py migrate
```

### B3. SmartEntry → automatski poveži ref kod s registracijom

U `register_step4` (registration/views.py), nakon što je korisnik kreiran,
provjeri session za ref_code i poveži AgentReferral:

```python
# Dodati u register_step4, nakon kreiranja korisnika i kompanije:
ref_code = request.session.get('reg_ref_code', '')
if ref_code:
    try:
        from registration.models import UmbrellaInviteCode
        from partners.models import AgentReferral, Partner

        invite = UmbrellaInviteCode.objects.get(code=ref_code)
        # Umbrella veza
        company.umbrella_parent = invite.umbrella_company
        company.save(update_fields=['umbrella_parent'])
        # AgentReferral zapis
        agent_partner = Partner.objects.filter(
            company=invite.umbrella_company,
            partner_type='agent'
        ).first()
        if agent_partner:
            from django.utils import timezone
            from datetime import timedelta
            referral = AgentReferral.objects.create(
                agent=agent_partner,
                referred_company=company,
                referral_code=ref_code + '-' + company.oib[:6],
                status='active',
                commission_percent=20,
                commission_months=12,
                expires_at=timezone.now() + timedelta(days=365),
            )
            subscription.referral = referral
            subscription.save(update_fields=['referral'])
            logger.info('AgentReferral kreiran: %s → %s', agent_partner.name, company.name)
    except Exception as e:
        logger.warning('AgentReferral creation failed: %s', e)
```

U smart_entry_page, spremi ref_code u session:
```python
def smart_entry_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    ref_code = request.GET.get('ref', '').upper()
    if ref_code:
        request.session['reg_ref_code'] = ref_code
        # Provjeri postoji li invite code i prikaži agenta
        try:
            from registration.models import UmbrellaInviteCode
            invite = UmbrellaInviteCode.objects.get(code=ref_code)
            agent_name = invite.note.replace('Referral kod za ', '') if invite.note else invite.umbrella_company.name
        except Exception:
            agent_name = None
    else:
        agent_name = None
    return render(request, 'registration/smart_entry.html', {
        'ref_code': ref_code,
        'agent_name': agent_name,
        'plan': request.GET.get('plan', 'starter'),
    })
```

---

## FAZA C — Agent Dashboard (Marija i Kruljac vide svoje klijente)

### C1. View: moji_klijenti

Dodati u `registration/views.py` ili novi `partners/agent_views.py`:

```python
@login_required
def agent_dashboard(request):
    """
    Dashboard za agenta — moji klijenti, moja zarada.
    Dostupno: Marija, Kruljac, svi s partner_type='agent'.
    """
    from partners.models import AgentReferral, Partner

    # Pronađi agent partner za ovog usera
    agent_partners = Partner.objects.filter(
        email=request.user.email,
        partner_type='agent',
    )
    if not agent_partners.exists():
        return render(request, 'partners/agent_not_found.html')

    referrals = AgentReferral.objects.filter(
        agent__in=agent_partners
    ).select_related('referred_company').order_by('-created_at')

    total_earned = sum(r.total_earned for r in referrals)
    total_paid = sum(r.total_paid for r in referrals)
    balance = total_earned - total_paid
    active_count = referrals.filter(status='active').count()

    # Generiraj invite linkove
    from registration.models import UmbrellaInviteCode
    invite_codes = UmbrellaInviteCode.objects.filter(
        umbrella_company__in=[p.company for p in agent_partners]
    )
    invite_links = [
        {
            'code': ic.code,
            'url': f'https://limit-connect.com/pocni/?ref={ic.code}',
            'uses': ic.times_used,
            'max_uses': ic.max_uses,
        }
        for ic in invite_codes
    ]

    return render(request, 'partners/agent_dashboard.html', {
        'referrals': referrals,
        'total_earned': total_earned,
        'total_paid': total_paid,
        'balance': balance,
        'active_count': active_count,
        'invite_links': invite_links,
    })
```

### C2. URL

Dodati u `core/urls.py` (u i18n_patterns, treba login):
```python
path('moji-klijenti/', 
     __import__('partners.agent_views', fromlist=['agent_dashboard']).agent_dashboard,
     name='agent_dashboard'),
```

### C3. Template: templates/partners/agent_dashboard.html

Prikazuje:
- **Hero stat kartice**: Aktivnih klijenata | Ukupno zarađeno | Neisplaćeno
- **Invite linkovi**: Copy-to-clipboard gumb, QR kod, broj korištenja
- **Lista klijenata**: Firma | Plan | Datum | Status provizije | Zarada
- **Sidebar link** u base.html: Pokazuje se samo ako je user agent_partner

### C4. Sidebar link (base.html)

Dodati u sidebar uz ostale linkove:
```html
{% if request.user.is_authenticated %}
  {# Provjeri u contextu je li user agent — postavlja se u middleware ili view #}
  {% if user_is_agent %}
    <a href="{% url 'agent_dashboard' %}" onclick="closeSidebar()">
      <i class="fas fa-handshake"></i> <span>Moji klijenti</span>
    </a>
  {% endif %}
{% endif %}
```

Za `user_is_agent` — dodati u context processor ili middleware:
```python
# U permissions/context_processors.py:
def user_is_agent(request):
    if not request.user.is_authenticated:
        return {'user_is_agent': False}
    from partners.models import Partner
    is_agent = Partner.objects.filter(
        email=request.user.email,
        partner_type='agent',
        is_active=True,
    ).exists()
    return {'user_is_agent': is_agent}
```

---

## VERIFIKACIJA — Kompletan scenarij

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from django.test import Client
import json

c = Client()

# 1. Novi korisnik — SmartEntry detect
resp = c.post('/api/auth/detect-email/',
    json.dumps({'email': 'novi.test@example.com'}),
    content_type='application/json')
print(f'Novi korisnik: {resp.json()["state"]} (očekivano: NEW_USER)')

# 2. Katarina — SmartEntry detect
resp2 = c.post('/api/auth/detect-email/',
    json.dumps({'email': 'katarina.furdi@limit-connect.com'}),
    content_type='application/json')
d = resp2.json()
print(f'Katarina: state={d["state"]}, name={d.get("first_name")}, co={d.get("company_name")}')

# 3. Agent setup
from partners.models import Partner
agents = Partner.objects.filter(partner_type='agent')
print(f'\nAgenti u sustavu: {agents.count()}')
for a in agents:
    print(f'  {a.name} | {a.email}')

# 4. Invite kodovi
from registration.models import UmbrellaInviteCode
codes = UmbrellaInviteCode.objects.all()
print(f'\nInvite kodovi: {codes.count()}')
for ic in codes:
    url = f'https://limit-connect.com/pocni/?ref={ic.code}'
    print(f'  {ic.code}: {url}')

# 5. /pocni/ stranica
resp3 = c.get('/pocni/')
print(f'\n/pocni/ HTTP: {resp3.status_code} (očekivano: 200 ili 302)')
PYEOF
```

---

## COMMIT SEKVENCA

```bash
cd /var/www/fina-connect

# Faza A
git add accounts/auth_views.py accounts/auth_models.py registration/views.py \
        core/urls.py permissions/route_registry.py \
        templates/registration/smart_entry.html
git commit -m "feat(smart-entry): Email-first ulazna točka bez dead endova

/pocni/ — jedna URL za sve korisnike
detect_email API — stanje: NEW_USER / EXISTING_USER
smart_entry_magic — magic link za postojeće korisnike
MagicToken token_type 'entry' dodan

NEW_USER  → mini registracijski form (ime, firma, lozinka)
EXISTING_USER → personalizirani pozdrav + magic link + 'imam lozinku'

Kraj Katarina scenarija: email exists → link na login, ne dead end
?ref=KOD → automatski sprema referral u session"

# Faza B
git add partners/ registration/models.py
git commit -m "feat(agent): Marija i Kruljac kao resellers

AgentReferral seed: Marija (REF-MARIJA-2026), Kruljac (REF-KORPAŠ-2026)
UmbrellaInviteCode generiran za oba agenta
CompanySubscription.referral FK dodan
register_step4: automatski kreira AgentReferral iz ref koda

/pocni/?ref=REF-MARIJA-2026 → novi klijent se veže uz Mariju"

# Faza C
git add partners/agent_views.py templates/partners/ permissions/context_processors.py
git commit -m "feat(agent-dashboard): Posrednički dashboard

/moji-klijenti/ — lista klijenata, zarada, neisplaćeno
Copy-to-clipboard invite linkovi s QR kodom
user_is_agent context processor → sidebar link
Dostupno: Marija, Kruljac, svi partner_type='agent'"
```

---

## NAPOMENE ZA CC

1. PROVJERI redoslijed: Faza A mora biti deployable sama (nema dependencies na B/C)

2. U `smart_entry.html` — ako ?ref= postoji, prikaži:
   "Registrirate se pod referral kodom [Ime agenta]"
   Ovo je socijalni proof koji povećava konverziju.

3. Context processor `user_is_agent` — OBAVEZNO dodati u TEMPLATES['OPTIONS']['context_processors']
   u core/settings.py inače sidebar link neće raditi.

4. AgentReferral.referral_code mora biti unique — generiraj:
   `REF-MARIJA-2026-{company.oib[:6]}` ili UUID suffix

5. BITNO: /pocni/ URL NE smije biti pod i18n prefiksom (/hr/pocni/) —
   mora raditi i iz WhatsApp linka koji Marija pošalje klijentu
   (WhatsApp ne prati redirecte)

6. Nakon Faze C — javi Sonnet:
   "SmartEntry + Agent DONE" + URL invite linka za Mariju i Kruljac

---

## MARKETING MATERIJAL (pripremi nakon tehničke implementacije)

Marija šalje klijentima ovaj WhatsApp:
```
Registrirajte se za LIMIT Connect — 1 besplatni mjesec:
https://limit-connect.com/pocni/?ref=REF-MARIJA-2026

Pratim vaš onboarding osobno. 📊
```

Kruljac šalje:
```
Probajte LIMIT Connect za OPG — besplatno prvi mj:
https://limit-connect.com/pocni/?ref=REF-KORPAŠ-2026
```

---

## STATUS: READY_FOR_CC_CODE
## Faza A → B → C, svaka neovisna, svaka deployable
## Rok: SmartEntry (Faza A) danas, B+C sutra
