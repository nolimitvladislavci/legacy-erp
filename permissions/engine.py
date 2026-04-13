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
        except AttributeError:
            pass

        # 5. CompanyMembership
        if company and not self._user_in_company(user, company):
            return AccessDecision(
                False, f'Nije clan firme {company.name}', 'COMPANY_MEMBERSHIP', **kw
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
        from django.db.models import Q

        from permissions.models import UserRole
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
        from django.db.models import Q
        from django.utils import timezone

        from permissions.models import PermissionOverride
        qs = PermissionOverride.objects.filter(
            user=user,
            permission__codename=permission,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now()))
        if company:
            qs = qs.filter(Q(company=company) | Q(company__isnull=True))
        ov = qs.order_by('-created_at').first()
        return ov.grant if ov else None

    def has_permission(self, user, permission: str, company=None) -> bool:
        """Shortcut — vraca bool."""
        return bool(self.evaluate(user, permission, company))

    def has_any_permission(self, user, permission_list, company=None) -> bool:
        """Shortcut — True ako ima barem jednu."""
        return any(self.has_permission(user, p, company) for p in permission_list)


_instance = None

def get_engine() -> PermissionEngine:
    global _instance
    if _instance is None:
        _instance = PermissionEngine()
    return _instance
