# CC_TASK_API_KEY_AUTH — Passwordless API Key autentifikacija
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-25

**Čitaj prvo:** FENIX_STATUS.md, accounts/models.py, accounts/auth_views.py

---

## Kontekst — Zašto

Trenutno: login = lozinka + opcionalni TOTP (aplikacija na mobitelu)
Problem: novi korisnici moraju skidati Google Authenticator → frka pri onboardingu
Cilj: nova registracija → dobiva API ključ → prijava s ključem, bez aplikacije

Postojeće ne mijenjamo:
- DeviceToken (UUID barcode, POS auto-login) → ostaje
- TOTP (totp_secret/totp_enabled) → ostaje kao opcija za veću zaštitu
- Lozinka → ostaje za stare korisnike i fallback

---

## ZADATAK 1 — Model: UserAPIKey

**Fajl:** `accounts/models.py` — dodaj na kraj

```python
import secrets, hashlib as _hashlib


def _generate_api_key():
    """lc_live_ + 32 hex znaka. Vidljivo jednom korisniku, u bazi samo hash."""
    return 'lc_live_' + secrets.token_hex(32)


class UserAPIKey(models.Model):
    """
    API ključ za passwordless login i programski pristup.
    Prikazuje se korisniku JEDNOM pri kreiranju.
    U bazi čuvamo SAMO SHA-256 hash.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name='Korisnik',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name='Tvrtka',
    )
    name = models.CharField(
        max_length=100,
        default='Primarni ključ',
        verbose_name='Naziv ključa',
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='SHA-256 hash ključa',
    )
    key_prefix = models.CharField(
        max_length=16,
        verbose_name='Prefiks (za prikaz)',
        help_text='Prvih 12 znakova ključa — za identifikaciju u adminu',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktivan')
    scopes = models.JSONField(
        default=list,
        verbose_name='Ovlasti',
        help_text='Prazno = puna prava korisnika. Npr. ["read", "invoicing"]',
    )
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Zadnja upotreba')
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Ističe')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'API ključ'
        verbose_name_plural = 'API ključevi'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.key_prefix}...) — {self.user.username}'

    @classmethod
    def create_for_user(cls, user, company, name='Primarni ključ', ip=None):
        """
        Kreira novi API ključ. Vraća (instance, plaintext_key).
        plaintext_key se prikazuje JEDNOM i nigdje ne sprema.
        """
        from django.utils import timezone
        raw_key = _generate_api_key()
        key_hash = _hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]

        # Deaktiviraj stare ključeve istog naziva
        cls.objects.filter(user=user, company=company, name=name).update(is_active=False)

        instance = cls.objects.create(
            user=user,
            company=company,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            created_by_ip=ip,
        )
        return instance, raw_key

    @classmethod
    def authenticate(cls, raw_key):
        """
        Provjeri ključ. Vraća (user, company) ili (None, None).
        Ažurira last_used_at.
        """
        from django.utils import timezone
        key_hash = _hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = cls.objects.select_related('user', 'company').get(
                key_hash=key_hash,
                is_active=True,
            )
        except cls.DoesNotExist:
            return None, None

        # Provjeri expiry
        if api_key.expires_at and api_key.expires_at < timezone.now():
            return None, None

        # Ažuriraj last_used
        cls.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        return api_key.user, api_key.company
```

Migracija:
```bash
venv/bin/python manage.py makemigrations accounts
venv/bin/python manage.py migrate
```

---

## ZADATAK 2 — Login view s API ključem

**Fajl:** `accounts/auth_views.py` — dodaj novi view

```python
from django.views.decorators.http import require_POST
from django.contrib.auth import login as auth_login
from django.http import JsonResponse
from accounts.models import UserAPIKey


def api_key_login(request):
    """
    POST /auth/api-key-login/
    Body: {"api_key": "lc_live_..."}
    
    Radi za:
    - AJAX login s API ključem
    - Portal prijava (Zlatan, B2B portal)  
    - Programski pristup (webhook, integracije)
    """
    if request.method == 'GET':
        # Prikaži formu
        return render(request, 'accounts/api_key_login.html')

    import json
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            raw_key = data.get('api_key', '')
        else:
            raw_key = request.POST.get('api_key', '')
    except Exception:
        raw_key = ''

    if not raw_key or not raw_key.startswith('lc_live_'):
        if request.content_type == 'application/json':
            return JsonResponse({'error': 'Nevažeći format ključa'}, status=400)
        messages.error(request, 'Nevažeći API ključ.')
        return render(request, 'accounts/api_key_login.html')

    user, company = UserAPIKey.authenticate(raw_key)

    if not user:
        if request.content_type == 'application/json':
            return JsonResponse({'error': 'Ključ nije pronađen ili je istekao'}, status=401)
        messages.error(request, 'API ključ nije valjan ili je istekao.')
        return render(request, 'accounts/api_key_login.html')

    # Login korisnika
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    # Postavi aktivnu firmu u session
    request.session['company_id'] = str(company.id)
    request.session['active_company'] = company.name

    if request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'redirect': '/hr/dashboard/',
            'user': user.username,
            'company': company.name,
        })

    return redirect('dashboard')
```

URL u `accounts/urls.py`:
```python
path('api-key-login/', auth_views.api_key_login, name='api_key_login'),
```

---

## ZADATAK 3 — Template: login s API ključem

**Fajl:** `accounts/templates/accounts/api_key_login.html`

```html
{% extends "base.html" %}
{% block content %}
<div class="container" style="max-width:460px; margin:80px auto;">
  <div class="card p-4">
    <h4 class="mb-1">Prijava s API ključem</h4>
    <p class="text-muted small mb-4">Unesite ključ koji ste dobili pri registraciji
       ili iz Postavki → Sigurnost.</p>
    
    {% if messages %}
      {% for msg in messages %}
      <div class="alert alert-danger">{{ msg }}</div>
      {% endfor %}
    {% endif %}

    <form method="post">
      {% csrf_token %}
      <div class="mb-3">
        <label class="form-label fw-500">API ključ</label>
        <input type="password" name="api_key" class="form-control font-monospace"
               placeholder="lc_live_..." autocomplete="off" autofocus>
        <div class="form-text">Format: lc_live_ + 32 znaka</div>
      </div>
      <button type="submit" class="btn btn-primary w-100">Prijavi se</button>
    </form>

    <hr class="my-3">
    <div class="text-center small text-muted">
      <a href="{% url 'login' %}">Prijava s lozinkom</a>
      &nbsp;·&nbsp;
      <a href="{% url 'password_reset' %}">Zaboravili ste ključ?</a>
    </div>
  </div>
</div>
{% endblock %}
```

---

## ZADATAK 4 — Auto-kreiranje ključa pri registraciji

U `registration/views.py`, u funkciji `admin_approve_registration()` (ili gdje se kreira User),
**odmah nakon `user.save()`** dodaj:

```python
# Auto-kreiraj API ključ za novog korisnika
from accounts.models import UserAPIKey
_, api_key_plain = UserAPIKey.create_for_user(
    user=user,
    company=company,
    name='Primarni ključ',
    ip=request.META.get('REMOTE_ADDR'),
)

# Spremi u session da se prikaže jednom na welcome ekranu
request.session['new_api_key'] = api_key_plain
# Nakon refresh sessiona, ključ se briše (prikazan samo jednom)
```

Na welcome ekranu (onboarding step 1) prikaži ključ:
```python
# U welcome view-u:
new_key = request.session.pop('new_api_key', None)
context['new_api_key'] = new_key  # None ako nije nova registracija
```

```html
{% if new_api_key %}
<div class="alert alert-warning">
  <strong>🔑 Vaš API ključ (prikazuje se samo jednom!)</strong>
  <div class="font-monospace mt-2 p-2 bg-white border rounded" id="apiKeyDisplay">
    {{ new_api_key }}
  </div>
  <button class="btn btn-sm btn-outline-secondary mt-2"
          onclick="navigator.clipboard.writeText('{{ new_api_key }}'); this.textContent='✓ Kopirano'">
    Kopiraj ključ
  </button>
  <p class="small text-muted mt-2">
    Spremate ga na sigurno mjesto. Ako ga izgubite, generirați novi u Postavkama → Sigurnost.
  </p>
</div>
{% endif %}
```

---

## ZADATAK 5 — Postavke: upravljanje ključevima

**Fajl:** `accounts/settings_views.py` (ili gdje su postavke korisnika)

```python
def api_keys_settings(request):
    """
    GET  /hr/settings/api-keys/     — prikaži ključeve
    POST /hr/settings/api-keys/     — generiraj novi ili deaktiviraj
    """
    from accounts.models import UserAPIKey
    company = get_active_company(request)  # tvoja helper funkcija

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'generate':
            name = request.POST.get('name', 'Novi ključ')
            _, new_key = UserAPIKey.create_for_user(
                user=request.user,
                company=company,
                name=name,
                ip=request.META.get('REMOTE_ADDR'),
            )
            # Prikaži jednom
            messages.success(request, f'NEW_KEY:{new_key}')  # poseban format za template
            return redirect('api_keys_settings')

        elif action == 'revoke':
            key_id = request.POST.get('key_id')
            UserAPIKey.objects.filter(
                id=key_id, user=request.user, company=company
            ).update(is_active=False)
            messages.success(request, 'Ključ deaktiviran.')
            return redirect('api_keys_settings')

    keys = UserAPIKey.objects.filter(
        user=request.user,
        company=company,
    ).order_by('-created_at')

    # Izvuci novi ključ iz messages ako postoji
    new_key_display = None
    storage = messages.get_messages(request)
    remaining = []
    for msg in storage:
        if str(msg).startswith('NEW_KEY:'):
            new_key_display = str(msg)[8:]
        else:
            remaining.append(msg)

    return render(request, 'accounts/api_keys.html', {
        'keys': keys,
        'new_key_display': new_key_display,
        'remaining_messages': remaining,
    })
```

---

## ZADATAK 6 — Admin panel

**Fajl:** `accounts/admin.py`

```python
from accounts.models import UserAPIKey

@admin.register(UserAPIKey)
class UserAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'name', 'key_prefix', 'is_active',
                    'last_used_at', 'created_at']
    list_filter = ['is_active', 'company']
    search_fields = ['user__username', 'company__name', 'key_prefix']
    readonly_fields = ['key_hash', 'key_prefix', 'last_used_at', 'last_used_ip', 'created_at']
    actions = ['deactivate_keys', 'regenerate_and_email']

    def deactivate_keys(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} ključ(eva) deaktivirano.')
    deactivate_keys.short_description = 'Deaktiviraj odabrane ključeve'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
```

---

## ZADATAK 7 — Sigurnost: rate limiting na login endpoint

U `accounts/auth_views.py`, IZNAD api_key_login view-a:

```python
from django.core.cache import cache
from django.utils import timezone

def _check_rate_limit(ip, max_attempts=10, window_seconds=300):
    """Max 10 pokušaja na 5 minuta po IP-u."""
    key = f'api_key_login_attempts:{ip}'
    attempts = cache.get(key, 0)
    if attempts >= max_attempts:
        return False
    cache.set(key, attempts + 1, window_seconds)
    return True
```

U api_key_login view, ODMAH NA POČETKU:
```python
ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
if not _check_rate_limit(ip):
    return JsonResponse({'error': 'Previše pokušaja. Pričekajte 5 minuta.'}, status=429)
```

---

## ZADATAK 8 — URL na login stranici

Na glavnoj login stranici (accounts/templates/accounts/login.html), dodaj link:

```html
<div class="text-center mt-3 small">
  <a href="{% url 'api_key_login' %}">Prijava s API ključem</a>
  &nbsp;·&nbsp;
  <a href="{% url 'password_reset' %}">Zaboravili ste lozinku?</a>
</div>
```

---

## Backward compatibility — NE DIRA

- TOTP (totp_secret, totp_enabled) → netaknuto
- DeviceToken (barcode POS login) → netaknuto
- Lozinka login → netaknuto, ostaje default
- API ključ = nova OPCIJA, ne zamjena

---

## DONE kriterij

- [ ] `UserAPIKey` model + migracija
- [ ] `UserAPIKey.create_for_user()` vraća (instance, plaintext_key)
- [ ] `UserAPIKey.authenticate()` vraća (user, company) ili (None, None)
- [ ] `api_key_login` view radi (GET forma + POST login)
- [ ] Rate limiting: max 10 pokušaja / 5 min / IP
- [ ] Auto-kreiranje ključa pri novoj registraciji
- [ ] Welcome ekran prikazuje ključ jednom
- [ ] Postavke: korisnik može generirati novi / deaktivirati stari
- [ ] Admin: vidi, deaktivira, pretraži
- [ ] Test: `UserAPIKey.create_for_user()` + `authenticate()` → round-trip OK
- [ ] Stare auth metode netaknute (TOTP, DeviceToken, lozinka)
- [ ] Commit: "feat(auth): UserAPIKey passwordless login — lc_live_ format, SHA-256 hash"
