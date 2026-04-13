from django.utils.deprecation import MiddlewareMixin
from django.db import DatabaseError


class RolePermissionMiddleware(MiddlewareMixin):
    """Attach user_permissions i user_role na request. FAL Faza 3."""

    SKIP_PREFIXES = ('/static/', '/media/', '/admin/', '/i18n/', '/health/')

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.user_permissions = set()
            request.user_role = None
            return None

        path = request.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            request.user_permissions = set()
            request.user_role = None
            return None

        from .models import Permission, UserRole

        user = request.user

        # Superuser bypass
        if user.is_superuser:
            request.user_permissions = set(
                Permission.objects.filter(is_active=True).values_list('codename', flat=True)
            )
            request.user_role = 'superadmin'
            return None

        # Company iz requesta
        company = getattr(request, 'current_company', None)

        # Permissions: provjeri profil brzi path, inace RBAC
        try:
            role = user.profile.role
            if role in ('company_admin', 'tenant_admin', 'superadmin'):
                request.user_permissions = set(
                    Permission.objects.filter(is_active=True).values_list('codename', flat=True)
                )
            else:
                # RBAC: dohvati permissions iz UserRole
                perms = set()
                urs = UserRole.objects.filter(
                    user=user, role__is_active=True
                ).select_related('role')
                if company:
                    from django.db.models import Q
                    urs = urs.filter(Q(company=company) | Q(company__isnull=True))
                for ur in urs:
                    if ur.is_valid():
                        perms.update(ur.role.get_all_permissions())
                request.user_permissions = perms
        except DatabaseError:
            request.user_permissions = set()

        # UserRole za request
        try:
            ur = UserRole.objects.filter(
                user=user, is_primary=True
            ).select_related('role').first()
            request.user_role = ur.role.role_type if ur else getattr(user.profile, 'role', None)
        except DatabaseError:
            request.user_role = None

        return None
