# CC_TASK_FAL_FAZA3.md
# Za: CC Code
# Datum: 2026-03-30
# Prioritet: VISOKO
# Procjena: 3-4 sata
#
# Faza 2 DONE (commit bae9956a) — analiza otkrila 3 problema koja blokiraju Fazu 3.
# Ovaj task rješava probleme i dodaje AI Scoped Token.

---

## ANALIZA FAZE 2 — Što treba popraviti

### Problem 1 — KRITIČAN: Pogrešni superuseri
3 korisnika imaju is_superuser=True a ne trebaju:
- antonio.brtan   (role=admin)       → treba company_admin, NE superuser
- niksa.viskovic  (role=admin)       → treba company_admin, NE superuser
- marija.brtan    (role=tenant_admin) → treba company_admin, NE superuser

Sve dok su is_superuser=True, engine.evaluate() vraća GRANT na Koraku 1
i RBAC je potpuno zaobiđen za te korisnike.

### Problem 2 — SREDNJI: UserRole tablica je prazna (0 redaka)
RBAC Korak 6 nikad ne provjeri ništa — workeri padaju na DEFAULT_DENY
za sve što nije pokriveno Korakom 4 (PROFILE_ROLE string check).

### Problem 3 — MANJI: 13 preostalih PermissionManager referenci
permissions/templatetags/permission_tags.py (2 reference)
permissions/decorators.py — require_role koristi PermissionManager.get_user_role()
permissions/middleware.py — RolePermissionMiddleware koristi PermissionManager

---

## KORAK 1 — Popravi pogrešne superusere

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from django.contrib.auth.models import User

# PAŽNJA: NE dirati ivan_brtan, dragan.jakovljevic, superadmin
# Oni legitimno trebaju is_superuser=True

demote = {
    'antonio.brtan': 'company_admin',
    'niksa.viskovic': 'company_admin',
    'marija.brtan':  'company_admin',
}

for username, new_role in demote.items():
    try:
        u = User.objects.get(username=username)
        u.is_superuser = False
        u.is_staff = True  # Zadrži is_staff za admin panel pristup
        u.save(update_fields=['is_superuser', 'is_staff'])
        # Ažuriraj profile role
        u.profile.role = new_role
        u.profile.save(update_fields=['role'])
        print(f'OK: {username} → is_superuser=False, role={new_role}')
    except Exception as e:
        print(f'ERROR {username}: {e}')

# Verifikacija
print('\nKorisnici s is_superuser=True nakon promjene:')
for u in User.objects.filter(is_superuser=True):
    print(f'  {u.username}')
PYEOF
```

Provjeri da su samo ova 3 korisnika sada is_superuser=True:
- ivan_brtan
- dragan.jakovljevic
- superadmin (system)

---

## KORAK 2 — Migriraj UserRoles iz profile.role

Assign UserRole za sve aktivne korisnike prema trenutnom profile.role.
Bez ovoga RBAC Korak 6 nikad ne može ništa procijeniti.

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from django.contrib.auth.models import User
from permissions.models import Role, UserRole
from accounts.models import CompanyMembership

# Mapiranje profile.role → Role.role_type
ROLE_MAP = {
    'superadmin':    'company_admin',   # superadmin nema vlastiti Role — bypass je is_superuser
    'company_admin': 'company_admin',
    'tenant_admin':  'company_admin',   # tenant_admin = company_admin na razini platforme
    'accountant':    'accountant',
    'manager':       'manager',
    'worker':        'worker',
    'partner':       'partner',
    'investor':      'partner',
    'guest':         'guest',
}

created = 0
skipped = 0
errors = 0

active_users = User.objects.filter(is_active=True).select_related('profile')

for user in active_users:
    if user.is_superuser:
        skipped += 1
        continue  # Superuseri ne trebaju UserRole — imaju Korak 1 bypass

    try:
        profile_role = user.profile.role
    except Exception:
        skipped += 1
        continue

    role_type = ROLE_MAP.get(profile_role, 'worker')
    
    try:
        role = Role.objects.get(role_type=role_type)
    except Role.DoesNotExist:
        print(f'  WARN: Role {role_type} ne postoji za {user.username}')
        errors += 1
        continue

    # Dohvati firme korisnika
    memberships = CompanyMembership.objects.filter(
        user=user, is_active=True
    ).select_related('company')

    if memberships.exists():
        for mem in memberships:
            ur, c = UserRole.objects.get_or_create(
                user=user,
                role=role,
                company=mem.company,
                defaults={'is_primary': mem.is_default, 'created_by': None}
            )
            if c:
                created += 1
    else:
        # Korisnik bez company membership → global role (company=None)
        ur, c = UserRole.objects.get_or_create(
            user=user, role=role, company=None,
            defaults={'is_primary': True}
        )
        if c:
            created += 1

print(f'\nUserRole migration:')
print(f'  Kreirano: {created}')
print(f'  Preskočeno (superuser/no-profile): {skipped}')
print(f'  Greške: {errors}')
print(f'  Ukupno UserRoles: {UserRole.objects.count()}')
PYEOF
```

---

## KORAK 3 — Migracija preostalih PermissionManager referenci

### 3a. permission_tags.py

```bash
cd /var/www/fina-connect && python3 - << 'PYEOF'
with open('permissions/templatetags/permission_tags.py', 'r') as f:
    content = f.read()

old = '''from permissions.manager import PermissionManager

register = template.Library()
@register.simple_tag(takes_context=True)
def has_permission(context, permission_codename, company=None):
    """
    Check permission in template
    
    Usage:
        {% load permission_tags %}
        {% has_permission 'invoices.create' as can_create %}
        {% if can_create %}
            <button>Create Invoice</button>
        {% endif %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False

    return PermissionManager.has_permission(request.user, permission_codename, company)
@register.filter
def has_perm(user, permission_codename):
    """
    Filter version
    
    Usage:
        {% if request.user|has_perm:"invoices.create" %}
            ...
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    return PermissionManager.has_permission(user, permission_codename)'''

new = '''from permissions.engine import get_engine

register = template.Library()

@register.simple_tag(takes_context=True)
def has_permission(context, permission_codename, company=None):
    """
    Provjera ovlasti u templateu.
    Koristi: {% has_permission 'invoices.create' as can_create %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    return get_engine().has_permission(request.user, permission_codename, company)

@register.filter
def has_perm(user, permission_codename):
    """
    Filter verzija: {% if request.user|has_perm:"invoices.create" %}
    """
    if not user.is_authenticated:
        return False
    return get_engine().has_permission(user, permission_codename)'''

if old in content:
    content = content.replace(old, new, 1)
    with open('permissions/templatetags/permission_tags.py', 'w') as f:
        f.write(content)
    print('permission_tags.py: OK')
else:
    print('permission_tags.py: pattern nije nađen — provjeri ručno')
PYEOF
```

### 3b. RolePermissionMiddleware — ažuriraj da koristi engine

```bash
cd /var/www/fina-connect && python3 - << 'PYEOF'
with open('permissions/middleware.py', 'r') as f:
    content = f.read()

new_content = '''from django.utils.deprecation import MiddlewareMixin


class RolePermissionMiddleware(MiddlewareMixin):
    """
    Attach user_permissions i user_role na request.
    FAL Faza 3: koristi get_engine() i RouteRegistry.
    """

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.user_permissions = set()
            request.user_role = None
            return None

        from permissions.route_registry import RouteRegistry, AccessLevel
        level = RouteRegistry.get_access_level(request)
        if level in (AccessLevel.PUBLIC,):
            request.user_permissions = set()
            request.user_role = None
            return None

        from permissions.engine import get_engine
        from permissions.models import Permission, UserRole

        engine = get_engine()
        user = request.user

        if user.is_superuser:
            request.user_permissions = set(
                Permission.objects.filter(is_active=True).values_list('codename', flat=True)
            )
            request.user_role = 'superadmin'
            return None

        # Dohvati company iz requesta
        company = getattr(request, 'current_company', None)

        # Sve permissions koje korisnik ima za tu company
        try:
            request.user_permissions = engine.get_engine().get_user_permissions(user, company) if hasattr(engine, 'get_user_permissions') else set()
        except Exception:
            # Fallback: provjeri profil
            try:
                role = user.profile.role
                if role in ('company_admin', 'tenant_admin', 'superadmin'):
                    request.user_permissions = set(
                        Permission.objects.filter(is_active=True).values_list('codename', flat=True)
                    )
                else:
                    request.user_permissions = set()
            except Exception:
                request.user_permissions = set()

        # UserRole za request
        try:
            ur = UserRole.objects.filter(user=user, is_primary=True).select_related('role').first()
            request.user_role = ur.role.role_type if ur else getattr(user.profile, 'role', None)
        except Exception:
            request.user_role = None

        return None
'''

with open('permissions/middleware.py', 'w') as f:
    f.write(new_content)
print('permissions/middleware.py: OK')
PYEOF
```

---

## KORAK 4 — AI Scoped Token (Faza 3 originalni cilj)

### 4a. Kreiraj permissions/ai_policy.py

```python
# permissions/ai_policy.py
"""
AI Policy Layer — Scoped Token za Gemini, CC Code, Haiku.
FAL Faza 3.

AI agenti ne smiju imati blanko ček za bazu.
Svaki task generira AIAccessToken koji definira što smije:
  - allowed_models: koje modele smije čitati/pisati
  - allowed_actions: ['read', 'create', 'update'] — bez 'delete' po defaultu
  - company_scope: za koju firmu operira
  - expires_at: token istječe

AI_POLICY_VIOLATION se logira i može triggerirati WhatsApp alarm.
"""
import uuid
import logging
from datetime import timedelta
from django.db import models
from django.utils import timezone

logger = logging.getLogger('fal.ai_policy')


class AIAgentType(models.TextChoices):
    GEMINI = 'gemini', 'Google Gemini'
    CLAUDE_CODE = 'claude_code', 'Claude Code (CC)'
    HAIKU = 'haiku', 'Claude Haiku'
    SONNET = 'sonnet', 'Claude Sonnet'
    MCP = 'mcp', 'MCP Tool Call'


class AIAccessToken(models.Model):
    """Token za AI agent operacije. Generira se na početku svakog taska."""
    token_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    agent_type = models.CharField(max_length=20, choices=AIAgentType.choices)
    task_ref = models.CharField(max_length=200, help_text='CC_TASK ili GEMINI_TASK naziv')

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        help_text='null = platform-wide (samo za superadmin taskove)'
    )
    allowed_models = models.JSONField(
        default=list,
        help_text='["invoicing.Invoice", "partners.Partner"] ili ["*"] za sve'
    )
    allowed_actions = models.JSONField(
        default=lambda: ['read'],
        help_text='["read", "create", "update"] — delete zahtijeva eksplicitno odobrenje'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=500, blank=True)

    operations_count = models.PositiveIntegerField(default=0)
    violations_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'permissions'
        db_table = 'ai_access_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.agent_type} | {self.task_ref} | exp={self.expires_at:%Y-%m-%d %H:%M}'

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.revoked_at and timezone.now() < self.expires_at

    def can_access(self, model_label: str, action: str) -> bool:
        """Provjeri može li AI pristupiti modelu s danom akcijom."""
        if not self.is_valid:
            self._log_violation(model_label, action, 'Token nevažeći ili istekao')
            return False

        allowed = self.allowed_models
        if '*' not in allowed and model_label not in allowed:
            app_label = model_label.split('.')[0]
            if f'{app_label}.*' not in allowed:
                self._log_violation(model_label, action, f'Model {model_label} nije u scope')
                return False

        if action not in self.allowed_actions:
            self._log_violation(model_label, action, f'Akcija {action} nije dozvoljena')
            return False

        self.operations_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['operations_count', 'last_used_at'])
        logger.info(f'AI_ACCESS | {self.agent_type} | {model_label}.{action} | {self.task_ref}')
        return True

    def _log_violation(self, model_label: str, action: str, reason: str):
        self.violations_count += 1
        self.save(update_fields=['violations_count'])
        logger.warning(
            f'AI_POLICY_VIOLATION | agent={self.agent_type} | '
            f'model={model_label} | action={action} | reason={reason} | '
            f'task={self.task_ref} | token={self.token_id}'
        )
        # WhatsApp alert ako previše violations
        if self.violations_count >= 3:
            self._alert_violations()

    def _alert_violations(self):
        try:
            from core.whatsapp import send_text
            send_text(
                phone='+4915771998747',
                message=(
                    f'FAL ALERT: AI_POLICY_VIOLATION\n'
                    f'Agent: {self.agent_type}\n'
                    f'Task: {self.task_ref}\n'
                    f'Violations: {self.violations_count}\n'
                    f'Token: {str(self.token_id)[:8]}...'
                )
            )
        except Exception:
            pass

    def revoke(self, reason: str = 'Manual revoke'):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoke_reason = reason
        self.save(update_fields=['is_active', 'revoked_at', 'revoke_reason'])


# ── PREDEFINIRANJI PROFILI ─────────────────────────────────────────────────
AI_PROFILES = {
    'compliance_watchdog': {
        'allowed_models': ['invoicing.Invoice', 'documents.ArhivaEntry', 'eracun.EInvoice'],
        'allowed_actions': ['read'],
        'duration_hours': 24,
    },
    'ai_inbox_processor': {
        'allowed_models': ['documents.ArhivaEntry'],
        'allowed_actions': ['read', 'update'],
        'duration_hours': 2,
    },
    'daily_report': {
        'allowed_models': ['invoicing.*', 'pos.*', 'worktime.*'],
        'allowed_actions': ['read'],
        'duration_hours': 4,
    },
    'gemini_patrol': {
        'allowed_models': ['documents.ArhivaEntry', 'invoicing.Invoice', 'pos.Receipt'],
        'allowed_actions': ['read'],
        'duration_hours': 1,
    },
    'warehouse_w1': {
        'allowed_models': ['inventory.InventoryItem', 'inventory.GoodsReceipt'],
        'allowed_actions': ['read', 'create', 'update'],
        'duration_hours': 2,
    },
    'livestock_vet': {
        'allowed_models': ['livestock.Livestock', 'livestock.HealthRecord'],
        'allowed_actions': ['read', 'create'],
        'duration_hours': 4,
    },
}


def create_ai_token(
    agent_type: str,
    task_ref: str,
    allowed_models: list,
    allowed_actions: list = None,
    company=None,
    duration_hours: int = 4,
) -> 'AIAccessToken':
    """Factory za kreiranje AI tokena na početku svakog taska."""
    if allowed_actions is None:
        allowed_actions = ['read']

    if 'delete' in allowed_actions:
        logger.warning(f'AI token s DELETE ovlastima kreiran za task: {task_ref}')

    token = AIAccessToken.objects.create(
        agent_type=agent_type,
        task_ref=task_ref,
        company=company,
        allowed_models=allowed_models,
        allowed_actions=allowed_actions,
        expires_at=timezone.now() + timedelta(hours=duration_hours),
    )
    logger.info(
        f'AI_TOKEN_CREATED | {agent_type} | {task_ref} | '
        f'models={allowed_models} | actions={allowed_actions} | '
        f'expires={token.expires_at:%H:%M}'
    )
    return token


def token_from_profile(
    agent_type: str,
    task_ref: str,
    profile_name: str,
    company=None,
) -> 'AIAccessToken':
    """Kreiraj token iz predefiniranog profila."""
    if profile_name not in AI_PROFILES:
        raise ValueError(f'Nepoznati profil: {profile_name}. Dostupno: {list(AI_PROFILES.keys())}')
    profile = AI_PROFILES[profile_name]
    return create_ai_token(
        agent_type=agent_type,
        task_ref=task_ref,
        allowed_models=profile['allowed_models'],
        allowed_actions=profile['allowed_actions'],
        company=company,
        duration_hours=profile['duration_hours'],
    )
```

### 4b. Kreiraj i pokreni migraciju za AIAccessToken

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations permissions --name ai_access_token
venv/bin/python manage.py migrate permissions
```

### 4c. Verifikacija AI Policy

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from permissions.ai_policy import create_ai_token, token_from_profile

# Test 1: Read-only token
token = create_ai_token(
    agent_type='gemini',
    task_ref='GEMINI_TASK_TEST',
    allowed_models=['invoicing.Invoice', 'documents.ArhivaEntry'],
    allowed_actions=['read'],
)
print(f'Token kreiran: {token.token_id} | valid={token.is_valid}')
print(f'  Invoice.read: {token.can_access("invoicing.Invoice", "read")}')
print(f'  Invoice.delete: {token.can_access("invoicing.Invoice", "delete")}')
print(f'  Partner.read: {token.can_access("partners.Partner", "read")}')
print(f'  violations: {token.violations_count}')

# Test 2: Profil
token2 = token_from_profile('haiku', 'HAIKU_DAILY_REPORT', 'daily_report')
print(f'\nHaiku daily_report token: {token2.is_valid}')
print(f'  pos.Receipt read: {token2.can_access("pos.Receipt", "read")}')
print(f'  pos.Receipt delete: {token2.can_access("pos.Receipt", "delete")}')

print('\nAI Policy: OK')
PYEOF
```

---

## KORAK 5 — Verifikacija ENGINE nakon popravka superusera

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from permissions.engine import get_engine
from django.contrib.auth.models import User

engine = get_engine()

print('=== ENGINE TEST NAKON FAZE 3 ===')

# Ivan — superuser → GRANT
ivan = User.objects.get(username='ivan_brtan')
d = engine.evaluate(ivan, 'users.delete')
print(f'ivan / users.delete: {d.granted} [{d.evaluator}]')

# Marija — company_admin (više nije superuser) → PROFILE_ROLE GRANT
marija = User.objects.get(username='marija.brtan')
d2 = engine.evaluate(marija, 'invoices.create')
print(f'marija / invoices.create: {d2.granted} [{d2.evaluator}] {d2.reason}')
# Očekivano: GRANT [PROFILE_ROLE]

# Marija ne smije brisati usere
d3 = engine.evaluate(marija, 'users.delete')
print(f'marija / users.delete: {d3.granted} [{d3.evaluator}] {d3.reason}')

# Worker na POS
worker = User.objects.filter(profile__role='worker').first()
if worker:
    d4 = engine.evaluate(worker, 'pos.create')
    d5 = engine.evaluate(worker, 'finance.approve')
    print(f'{worker.username} / pos.create: {d4.granted} [{d4.evaluator}]')
    print(f'{worker.username} / finance.approve: {d5.granted} [{d5.evaluator}]')

from permissions.models import UserRole
print(f'\nUserRole redaka: {UserRole.objects.count()}')
PYEOF
```

---

## KORAK 6 — Commit

```bash
cd /var/www/fina-connect
git add permissions/ 
git commit -m "feat(fal/faza3): AI Scoped Token + superuser fix + UserRole seed

KRITIČAN FIX:
  - antonio.brtan, niksa.viskovic, marija.brtan: is_superuser=True → False
  - Sada engine ispravno prolazi kroz RBAC za njih

UserRole migracija:
  - N UserRoles kreirano iz CompanyMembership + profile.role
  - RBAC Korak 6 sada može evaluirati za workere

permissions/ai_policy.py — novi modul:
  - AIAccessToken model: allowed_models, allowed_actions, expires_at
  - Preddefinirani profili: compliance_watchdog, ai_inbox, daily_report, gemini_patrol
  - AI_POLICY_VIOLATION logira se + WhatsApp alert na 3+ violations
  - Funkcije: create_ai_token(), token_from_profile()

permissions/templatetags/permission_tags.py → get_engine()
permissions/middleware.py → RouteRegistry + engine

Migrations: 0002_ai_access_token

Slijedeće (Faza 4): AccessAuditLog + superadmin dashboard"
```

---

## NAPOMENE ZA CC

1. OBAVEZNO: U Koraku 1 NE dirati ove korisnike:
   - ivan_brtan (is_superuser mora ostati True)
   - dragan.jakovljevic (is_superuser mora ostati True)
   - superadmin (system user)

2. Provjeri `permissions/models.py` — AIAccessToken model treba dodati tamo
   ILI ga staviti u zasebnu migraciju. engine.py NEMA modele — AIAccessToken
   ide u models.py ili u ai_policy.py ako ga Django detektira tamo.
   
   PROVJERI: Da li Django detektira modele iz ai_policy.py?
   ```bash
   grep -rn "app_label.*permissions" /var/www/fina-connect/permissions/ --include="*.py"
   ```
   Ako ne — premjesti AIAccessToken u permissions/models.py.

3. Ako UserRole seed puca zbog unique_together — koristi get_or_create, ne create.

4. OBAVEZNO: Javi Sonnet rezultat verifikacije (Korak 5) — posebno:
   - marija.brtan / invoices.create evaluator mora biti PROFILE_ROLE (ne SUPERUSER)
   - Worker / finance.approve mora biti DEFAULT_DENY
