# CC_TASK: BookingSignature — Tjedan 1
# Naručio: Ivan Brtan (finalna arhitektura potvrđena)
# Kreirao: Sonnet — 2026-04-10
# Status: SPREMAN ZA IZVRŠENJE (nakon 15.04. launch)
# Procjena: 4-6 sati

---

## ODLUKE (ne diskutirati, implementirati)

- NEMA particioniranja (dodaje se tek na 100M+ zapisa)
- NEMA chain hash-a (WAL pokriva integritet na razini baze)
- NEMA Celery za audit (sinkroni INSERT u istoj transakciji)
- integrity_hash = SHA256(user_id + action + target_id + timestamp + SECRET_KEY)
- Sinkroni upis — ako transakcija propadne, ni audit ne ostaje

---

## KORAK 0: Provjeri prije pisanja koda

```bash
# Provjeri da ne postoji stari model
grep -r "BookingSignature" /var/www/fina-connect --include="*.py" | grep -v venv

# Provjeri INSTALLED_APPS za slobodan app slot
grep -n "INSTALLED_APPS" /var/www/fina-connect/core/settings.py

# Provjeri postoji li audit_chain.py (Sonnet ga je predložio — ne koristimo ga)
ls /var/www/fina-connect/core/audit_chain.py 2>/dev/null && echo "POSTOJI — ne diraj"
```

---

## KORAK 1: Novi app `booking_audit`

```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp booking_audit
```

Registriraj u `core/settings.py` INSTALLED_APPS:
```python
'booking_audit',
```

---

## KORAK 2: Model (booking_audit/models.py)

PROČITAJ CIJELI OVAJ BLOK prije pisanja. Ne dodavaj ništa što nije ovdje.

```python
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone


ACTION_CHOICES = [
    # Računovodstvo
    ('ledger_post',     'Knjiženje u konto'),
    ('ledger_delete',   'Brisanje knjiženja'),
    ('storno',          'Storno dokumenta'),
    # Fakturiranje
    ('invoice_create',  'Kreiranje fakture'),
    ('invoice_update',  'Izmjena fakture'),
    ('invoice_delete',  'Brisanje fakture'),
    # PDV i obrasci
    ('pdv_submit',      'Predaja PDV-S'),
    ('joppd_submit',    'Predaja JOPPD'),
    # Export
    ('export_csv',      'Export CSV/Excel'),
    ('export_pdf',      'Export PDF'),
    # Kritične promjene
    ('iban_change',     'Promjena IBAN-a'),
    ('user_change',     'Promjena korisničkih podataka'),
    ('company_settings','Promjena postavki tvrtke'),
    # Pristup
    ('workspace_switch','Promjena workspace-a'),
    ('login',           'Prijava u sustav'),
    ('logout',          'Odjava iz sustava'),
    ('pin_verify',      'PIN verifikacija'),
    # POS
    ('pos_open',        'Otvaranje smjene'),
    ('pos_close',       'Zatvaranje smjene'),
    ('pos_void',        'Storno POS računa'),
    # Arhiva
    ('doc_upload',      'Upload dokumenta'),
    ('doc_delete',      'Brisanje dokumenta'),
    # Ostalo
    ('bulk_delete',     'Masovno brisanje'),
    ('custom',          'Ostalo'),
]


class BookingSignature(models.Model):
    # Tko i za koga
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        related_name='booking_signatures',
        db_index=True,
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='booking_signatures',
        db_index=True,
    )
    workspace = models.ForeignKey(
        'companies.Workspace',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='booking_signatures',
    )

    # Što
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    target_model = models.CharField(max_length=100, blank=True)  # 'invoicing.Invoice'
    target_id = models.CharField(max_length=100, blank=True)
    changes = models.JSONField(default=dict)  # {'before': {}, 'after': {}}

    # Odakle
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    session_key = models.CharField(max_length=40, blank=True)

    # Autorizacija
    pin_verified = models.BooleanField(default=False)

    # Integritet
    integrity_hash = models.CharField(max_length=64, blank=True)

    # Kad
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Booking Signature'
        verbose_name_plural = 'Booking Signatures'
        indexes = [
            models.Index(fields=['user', 'timestamp'],    name='bs_user_ts_idx'),
            models.Index(fields=['company', 'timestamp'], name='bs_company_ts_idx'),
            models.Index(fields=['action', 'timestamp'],  name='bs_action_ts_idx'),
            models.Index(fields=['target_model', 'target_id'], name='bs_target_idx'),
        ]

    def __str__(self):
        return f"{self.user} | {self.action} | {self.timestamp:%Y-%m-%d %H:%M}"

    def compute_hash(self) -> str:
        """
        SHA-256: user_id + action + target_id + timestamp (ISO) + SECRET_KEY
        Ne koristi chain. Svaki zapis je samostalan dokaz.
        """
        raw = '|'.join([
            str(self.user_id),
            self.action,
            str(self.target_model),
            str(self.target_id),
            self.timestamp.isoformat() if self.timestamp else '',
            settings.SECRET_KEY,
        ])
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Provjeri da zapis nije mijenjan nakon upisa."""
        return self.integrity_hash == self.compute_hash()

    def save(self, *args, **kwargs):
        # Hash se računa JEDNOM, kod kreiranja. Ne mijenjati naknadno.
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.integrity_hash:
            self.integrity_hash = self.compute_hash()
            BookingSignature.objects.filter(pk=self.pk).update(
                integrity_hash=self.integrity_hash
            )
```

---

## KORAK 3: Helper funkcija (booking_audit/utils.py)

```python
# booking_audit/utils.py
"""
Jedina ulazna točka za kreiranje BookingSignature.
Pozivaj ovo — nikad direktno BookingSignature.objects.create().
"""

from .models import BookingSignature


def log_action(
    action: str,
    user,
    request=None,
    company=None,
    workspace=None,
    target_model: str = '',
    target_id=None,
    before: dict = None,
    after: dict = None,
    pin_verified: bool = False,
) -> BookingSignature:
    """
    Kreira BookingSignature zapis.
    SINKRONO — pozivaj u istoj Django transakciji kao akcija.
    
    Primjer:
        from booking_audit.utils import log_action
        log_action(
            action='storno',
            user=request.user,
            request=request,
            company=invoice.company,
            target_model='invoicing.Invoice',
            target_id=invoice.pk,
            before={'status': 'issued'},
            after={'status': 'cancelled'},
            pin_verified=True,
        )
    """
    ip = ''
    ua = ''
    sk = ''

    if request:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
        ua = request.META.get('HTTP_USER_AGENT', '')[:300]
        sk = request.session.session_key or ''

    return BookingSignature.objects.create(
        action=action,
        user=user,
        company=company,
        workspace=workspace,
        target_model=str(target_model)[:100],
        target_id=str(target_id)[:100] if target_id else '',
        changes={
            'before': before or {},
            'after': after or {},
        },
        ip_address=ip or None,
        user_agent=ua,
        session_key=sk,
        pin_verified=pin_verified,
    )
```

---

## KORAK 4: Admin (booking_audit/admin.py)

```python
from django.contrib import admin
from .models import BookingSignature


@admin.register(BookingSignature)
class BookingSignatureAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user', 'action', 'company',
        'target_model', 'target_id', 'pin_verified', 'integrity_ok'
    ]
    list_filter = ['action', 'pin_verified', 'timestamp']
    search_fields = ['user__username', 'target_id', 'ip_address']
    readonly_fields = [
        'user', 'company', 'workspace', 'action', 'target_model',
        'target_id', 'changes', 'ip_address', 'user_agent',
        'session_key', 'pin_verified', 'integrity_hash', 'timestamp'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    def integrity_ok(self, obj):
        ok = obj.verify_integrity()
        return '✅' if ok else '🚨 TAMPERED'
    integrity_ok.short_description = 'Hash OK'

    def has_add_permission(self, request):
        return False  # Nikad ručno dodavati

    def has_delete_permission(self, request, obj=None):
        return False  # Nikad brisati — 11 godina retencija

    def has_change_permission(self, request, obj=None):
        return False  # Read-only
```

---

## KORAK 5: Migracija i test

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations booking_audit
venv/bin/python manage.py migrate booking_audit

# Test u Django shellu
venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
from booking_audit.utils import log_action

u = User.objects.first()
sig = log_action(
    action='custom',
    user=u,
    target_model='test.Model',
    target_id='999',
    before={'status': 'a'},
    after={'status': 'b'},
)
print('Kreiran:', sig.pk)
print('Hash:', sig.integrity_hash[:16], '...')
print('Verify:', sig.verify_integrity())
assert sig.verify_integrity(), 'HASH GREŠKA!'
print('OK — BookingSignature radi')
"
```

---

## KORAK 6: Hookaj na 3 kritična mjesta (proof of concept)

Ne treba sve odjednom — samo 3 mjesta kao dokaz da funkcionira:

### 6a. Login
```python
# core/views.py — u login_view(), nakon login(request, user):
from booking_audit.utils import log_action
log_action(
    action='login',
    user=user,
    request=request,
    company=getattr(user.profile, 'active_company', None) if hasattr(user, 'profile') else None,
)
```

### 6b. Storno fakture (pronađi storno view u invoicing ili documents)
```python
# Dodaj u storno view, u atomičnoj transakciji s akcijom:
from booking_audit.utils import log_action
log_action(
    action='storno',
    user=request.user,
    request=request,
    company=invoice.company,
    target_model='invoicing.Invoice',
    target_id=invoice.pk,
    before={'status': invoice_before_status},
    after={'status': 'cancelled'},
)
```

### 6c. Workspace switch
```python
# Pronađi workspace_switch view u companies:
from booking_audit.utils import log_action
log_action(
    action='workspace_switch',
    user=request.user,
    request=request,
    company=new_company,
    before={'company': old_company.name},
    after={'company': new_company.name},
)
```

---

## KORAK 7: Verifikacija

```bash
# Provjeri da zapisi postoje
venv/bin/python manage.py shell -c "
from booking_audit.models import BookingSignature
total = BookingSignature.objects.count()
broken = BookingSignature.objects.all()[:100]
broken_count = sum(1 for s in broken if not s.verify_integrity())
print(f'Ukupno: {total}')
print(f'Broken hash (sample 100): {broken_count}')
assert broken_count == 0, 'HASH GREŠKA!'
print('OK')
"

# Provjeri u adminu
# https://limit-connect.com/[admin-url]/booking_audit/bookingsignature/
```

---

## KORAK 8: Git commit

```bash
cd /var/www/fina-connect
git add booking_audit/
git add core/settings.py
git commit -m "feat: BookingSignature — digitalni potpis svake računovodstvene akcije

- Novi app booking_audit s modelom BookingSignature
- SHA-256 integrity hash (user+action+target+timestamp+SECRET_KEY)
- Sinkroni upis u istoj transakciji
- 4 indeksa (user/company/action/target)
- Admin: read-only, bez brisanja, hash verifikacija
- log_action() helper kao jedina ulazna točka
- Hookano na: login, storno, workspace_switch"
```

---

## ZABRANJENO

- NE dodavati Celery za async upis
- NE dodavati chain hash (previous_hash)
- NE particionirati tablicu
- NE modificirati core_systemauditlog
- NE modificirati base.html, core/settings.py osim INSTALLED_APPS

## TJEDAN 2 (ne sad)
- `require_pin_for_action` dekorator
- PIN verify view za osjetljive akcije
- Hookanje na sve storno/brisanje/export viewove

## SESSION TIMEOUT (Tjedan 3)
- InactivityTimeoutMiddleware: 45min bez aktivnosti = logout
- Max session: 8h (ne 4h — Marija radi cijeli dan)
- Settings: SESSION_COOKIE_AGE = 28800 (8 * 3600)
