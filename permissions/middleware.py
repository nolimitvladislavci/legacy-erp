from django.utils.deprecation import MiddlewareMixin


class RolePermissionMiddleware(MiddlewareMixin):
    """Attach user_permissions (set of codenames) and user_role to request."""

    SKIP_PREFIXES = ('/static/', '/media/', '/admin/', '/i18n/', '/health/')

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.user_permissions = set()
            request.user_role = None
            return None

        # Skip for static / admin paths
        path = request.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            request.user_permissions = set()
            request.user_role = None
            return None

        from .manager import PermissionManager

        # Superadmin bypass — gets all permissions
        if request.user.is_superuser:
            from .models import Permission
            request.user_permissions = set(
                Permission.objects.filter(is_active=True).values_list('codename', flat=True)
            )
        else:
            request.user_permissions = PermissionManager.get_user_permissions(request.user)

        request.user_role = PermissionManager.get_user_role(request.user)
        return None
