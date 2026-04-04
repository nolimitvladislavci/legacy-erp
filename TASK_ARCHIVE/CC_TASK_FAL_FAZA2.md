# CC_TASK_FAL_FAZA2.md
# Za: CC Code
# Datum: 2026-03-30
# Prioritet: VISOKO
# Procjena: 2-3 sata

## KONTEKST

Faza 1 FAL-a je završena (commit db7fb0b6):
- `permissions/route_registry.py` postoji i radi
- `Force2FAMiddleware` i `ForceTCMiddleware` refaktorirani
- Verifikacija: `/no-limit/ 200`, 2FA loop eliminiran

Sada radiš Fazu 2: PermissionEngine + seed RBAC baze.

Provjeri stanje:
```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from permissions.models import Permission, Role, UserRole
print('Permissions:', Permission.objects.count())
print('Roles:', Role.objects.count())
print('UserRoles:', UserRole.objects.count())
"
```
Očekivano: sve 0 — permissions app postoji ali nikad nije seedana.

---

## KORAK 1 — Kreiraj permissions/engine.py

Kreiraj fajl `/var/www/fina-connect/permissions/engine.py` s ovim sadržajem:

```python
"""
PermissionEngine — jedini evaluator pristupa u sustavu.
FAL Faza 2.

Redoslijed evaluacije (Default Deny):
  1. is_superuser          → GRANT
  2. user.is_active=False  → DENY
  3. Company deaktivirana  → DENY
  4. UserProfile.role      → GRANT za superadmin/company_admin u svojoj firmi
  5. CompanyMembership     → DENY ako nije član firme
  6. RBAC Roles            → GRANT ako ima UserRole s tom permission
  7. PermissionOverride    → može GRANT ili REVOKE
  8. Default               → DENY

Svaka odluka vraća AccessDecision s razlogom — nikad ne baca exception.
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('fal.engine')


@dataclass
class AccessDecision:
    """Rezultat evaluacije. Uvijek ima objašnjenje."""
    granted: bool
    reason: str
    evaluator: str
    user_id: Optional[int] = None
    company_id: Optional[str] = None
    permission: Optional[str] = None

    def __bool__(self):
        return self.granted

    def log(self):
        status = "GRANT" if self.granted else "DENY"
        logger.info(
            f"{status} | user={self.user_id} | co={self.company_id} | "
            f"perm={self.permission} | eval={self.evaluator} | {self.reason}"
        )


class PermissionEngine:
    """Centralni evaluator pristupa. Koristi get_engine() singleton."""

    def evaluate(self, user, permission: str, company=None) -> AccessDecision:
        """Evaluiraj pristup. Nikad ne baca exception."""
        kw = dict(
            user_id=user.pk,
            company_id=str(company.pk) if company else None,
            permission=permission,
        )

        # 1. Superuser
        if user.is_superuser:
            return AccessDecision(True, 'Superuser bypass', 'SUPERUSER', **kw)

        # 2. Aktivan korisnik
        if not user.is_active:
            return AccessDecision(False, 'Korisnik nije aktivan', 'USER_ACTIVE', **kw)

        # 3. Company blacklist
        if company and getattr(company, 'is_deactivated', False):
            return AccessDecision(False, f'Firma {company.name} deaktivirana', 'COMPANY_BLACKLIST', **kw)

        # 4. UserProfile.role brzi path
        try:
            role = user.profile.role
            if role == 'superadmin':
                return AccessDecision(True, 'Profile: superadmin', 'PROFILE_ROLE', **kw)
            if role in ('company_admin', 'tenant_admin'):
                if company is None or self._user_in_company(user, company):
                    return AccessDecision(True, f'Profile: {role}', 'PROFILE_ROLE', **kw)
        except Exception:
            pass

        # 5. CompanyMembership
        if company and not self._user_in_company(user, company):
            return AccessDecision(
                False, f'Nije član firme {company.name}', 'COMPANY_MEMBERSHIP', **kw
            )

        # 6. RBAC
        rbac = self._check_rbac(user, permission, company)
        if rbac is not None:
            reason = f'RBAC {"grant" if rbac else "deny"}: {permission}'
            return AccessDecision(rbac, reason, 'RBAC', **kw)

        # 7. Override
        override = self._check_override(user, permission, company)
        if override is not None:
            return AccessDecision(override, f'Override: {permission}', 'OVERRIDE', **kw)

        # 8. Default DENY
        return AccessDecision(False, f'Nema ovlasti za {permission}', 'DEFAULT_DENY', **kw)

    def _user_in_company(self, user, company) -> bool:
        from accounts.models import CompanyMembership
        return CompanyMembership.objects.filter(
            user=user, company=company, is_active=True
        ).exists()

    def _check_rbac(self, user, permission: str, company) -> Optional[bool]:
        from permissions.models import UserRole
        from django.db.models import Q
        qs = UserRole.objects.filter(
            user=user, role__is_active=True
        ).select_related('role')
        if company:
            qs = qs.filter(Q(company=company) | Q(company__isnull=True))
        if not qs.exists():
            return None
        for ur in qs:
            if ur.is_valid():
                if permission in ur.role.get_all_permissions():
                    return True
        return False

    def _check_override(self, user, permission: str, company) -> Optional[bool]:
        from permissions.models import PermissionOverride
        from django.db.models import Q
        from django.utils import timezone
        qs = PermissionOverride.objects.filter(
            user=user,
            permission__codename=permission,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now()))
        if company:
            qs = qs.filter(Q(company=company) | Q(company__isnull=True))
        ov = qs.order_by('-created_at').first()
        return ov.grant if ov else None

    def has_permission(self, user, permission: str, company=None) -> bool:
        """Shortcut — vraća bool."""
        return bool(self.evaluate(user, permission, company))


_instance = None

def get_engine() -> PermissionEngine:
    global _instance
    if _instance is None:
        _instance = PermissionEngine()
    return _instance
```

---

## KORAK 2 — Seed permissions i roles

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from permissions.models import Permission, Role

# --- PERMISSIONS ---
PERMS = [
    ('invoices',   ['view','create','edit','delete','approve','export']),
    ('documents',  ['view','create','edit','delete','export']),
    ('finance',    ['view','create','edit','approve','export']),
    ('partners',   ['view','create','edit','delete']),
    ('inventory',  ['view','create','edit','delete']),
    ('pos',        ['view','create','edit']),
    ('worktime',   ['view','create','edit','export']),
    ('payroll',    ['view','create','export']),
    ('reports',    ['view','export']),
    ('users',      ['view','create','edit','delete','manage']),
    ('companies',  ['view','edit','manage']),
    ('system',     ['manage']),
    ('ai',         ['read','write','execute']),
    ('golubar',    ['view','create','edit','delete']),
    ('knjiznica',  ['view','create','edit','delete']),
    ('udruge',     ['view','create','edit','delete']),
    ('livestock',  ['view','create','edit','delete']),
    ('eracun',     ['view','create','send','approve']),
]

created_p = 0
for module, actions in PERMS:
    for action in actions:
        codename = f'{module}.{action}'
        p, c = Permission.objects.get_or_create(
            module=module, action=action,
            defaults={'codename': codename, 'name': f'{module} {action}', 'is_active': True}
        )
        if c:
            created_p += 1

print(f'Permissions kreirane: {created_p}, ukupno: {Permission.objects.count()}')

# --- ROLES s permissionima ---
ROLES = {
    'company_admin': Permission.objects.filter(is_active=True),  # sve
    'accountant':    Permission.objects.filter(module__in=['invoices','finance','documents','reports','eracun','partners']),
    'manager':       Permission.objects.filter(module__in=['invoices','documents','partners','inventory','pos','reports','worktime']).exclude(action='delete'),
    'worker':        Permission.objects.filter(module__in=['pos','worktime','documents']).filter(action__in=['view','create']),
    'partner':       Permission.objects.filter(module__in=['invoices','documents']).filter(action='view'),
    'guest':         Permission.objects.filter(module='reports', action='view'),
}

for role_type, perms in ROLES.items():
    role, created = Role.objects.get_or_create(
        role_type=role_type,
        defaults={'name': role_type.replace('_',' ').title(), 'is_active': True}
    )
    role.permissions.set(perms)
    print(f'Role {role_type}: {role.permissions.count()} perms {"(nova)" if created else "(update)"}')

print('Seed GOTOV.')
PYEOF
```

---

## KORAK 3 — Verifikacija engine-a

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from permissions.engine import get_engine
from django.contrib.auth.models import User

engine = get_engine()

# Test 1: Superuser
ivan = User.objects.get(username='ivan_brtan')
d = engine.evaluate(ivan, 'invoices.delete')
print(f'ivan_brtan delete invoice: {d.granted} | {d.evaluator} | {d.reason}')

# Test 2: company_admin (Marija)
marija = User.objects.get(username='marija.brtan')
d2 = engine.evaluate(marija, 'invoices.create')
print(f'marija.brtan create invoice: {d2.granted} | {d2.evaluator} | {d2.reason}')

# Test 3: worker
worker = User.objects.filter(profile__role='worker').first()
if worker:
    d3 = engine.evaluate(worker, 'payroll.view')
    print(f'worker payroll.view: {d3.granted} | {d3.evaluator} | {d3.reason}')
    d4 = engine.evaluate(worker, 'invoices.delete')
    print(f'worker invoices.delete: {d4.granted} | {d4.evaluator} | {d4.reason}')

print('PermissionEngine: OK')
PYEOF
```

---

## KORAK 4 — Integracija u dekorator require_permission

Provjeri `permissions/decorators.py` — funkcija `require_permission` poziva `PermissionManager.has_permission()`.
Zamijeni da poziva `get_engine().has_permission()`:

```python
# permissions/decorators.py — u require_permission decoratoru zamijeni:
# STARO:
#   has_perm = PermissionManager.has_permission(request.user, permission_codename, company)
# NOVO:
#   from permissions.engine import get_engine
#   has_perm = get_engine().has_permission(request.user, permission_codename, company)
```

Provjeri koliko mjesta koristi PermissionManager.has_permission:
```bash
grep -rn "PermissionManager.has_permission" /var/www/fina-connect --include="*.py" | grep -v venv | grep -v test
```

---

## KORAK 5 — Commit

```bash
cd /var/www/fina-connect
git add permissions/engine.py permissions/decorators.py
git commit -m "feat(fal/faza2): PermissionEngine Default Deny + RBAC seed

permissions/engine.py — novi evaluator, 8 koraka Default Deny
AccessDecision dataclass: granted, reason, evaluator, user_id

Seed:
- N permissions (18 modula × prosječno 4 akcije)
- 6 roles: company_admin (sve), accountant, manager, worker, partner, guest
- Role.permissions seeded iz baze

require_permission dekorator → get_engine().has_permission()

Slijedeće (Faza 3): AI Scoped Token za Gemini/CC/Haiku"
```

---

## NAPOMENE ZA CC

1. Provjeri `permissions/models.py` prije nego počneš — model Permission ima `unique_together = [['module', 'action']]`.
   Seed mora koristiti `get_or_create` s tim ključevima.

2. `Role.get_all_permissions()` vraća listu codename stringova — provjeri metodu u models.py:
   ```bash
   grep -A 10 "def get_all_permissions" /var/www/fina-connect/permissions/models.py
   ```

3. Ako seed puca na module choices — provjeri `MODULE_CHOICES` u Permission modelu i dodaj modele
   koji nedostaju (golubar, knjiznica, udruge, livestock, eracun).

4. Nakon commita — javi Sonnet: "FAL Faza 2 gotova" + rezultat verifikacijskog shell-a.
