"""
Permission Manager - Core permission checking logic
"""
from django.core.cache import cache
from django.db import models, DatabaseError, IntegrityError
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import Permission, PermissionOverride, Role, UserRole


class PermissionManager:
    """Centralized permission management"""

    CACHE_TIMEOUT = 300  # 5 minutes

    @classmethod
    def get_user_permissions(cls, user, company=None):
        """Get all permissions for user."""
        if user.is_superuser:
            return set(Permission.objects.filter(is_active=True).values_list("codename", flat=True))
        try:
            if user.profile.role in ("tenant_admin", "company_admin"):
                return set(Permission.objects.filter(is_active=True).values_list("codename", flat=True))
        except DatabaseError:
            pass
        from django.core.cache import cache
        cache_key = f"user_perms_{user.pk}_{company.pk if company else 0}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        perms = set()
        user_roles = UserRole.objects.filter(user=user, role__is_active=True).select_related("role")
        if company:
            user_roles = user_roles.filter(models.Q(company=company) | models.Q(company__isnull=True))
        for ur in user_roles:
            if ur.is_valid():
                perms.update(ur.role.get_all_permissions())
        overrides = PermissionOverride.objects.filter(user=user).select_related("permission")
        if company:
            overrides = overrides.filter(models.Q(company=company) | models.Q(company__isnull=True))
        for ov in overrides:
            if ov.is_granted:
                perms.add(ov.permission.codename)
            else:
                perms.discard(ov.permission.codename)
        cache.set(cache_key, perms, cls.CACHE_TIMEOUT)
        return perms

    @classmethod
    def has_permission(cls, user, permission_codename, company=None):
        """Check if user has specific permission."""
        if user.is_superuser:
            return True
        try:
            if user.profile.role in ("tenant_admin", "company_admin"):
                return True
        except AttributeError:
            pass
        if "." in permission_codename:
            module, action = permission_codename.split(".", 1)
            try:
                perm = Permission.objects.get(module=module, action=action)
                permission_codename = perm.codename
            except Permission.DoesNotExist:
                return False
        user_perms = cls.get_user_permissions(user, company)
        return permission_codename in user_perms

    @classmethod
    def has_any_permission(cls, user, permission_list, company=None):
        """Check if user has ANY of the permissions"""
        user_perms = cls.get_user_permissions(user, company)
        return any(p in user_perms for p in permission_list)

    @classmethod
    def has_all_permissions(cls, user, permission_list, company=None):
        """Check if user has ALL of the permissions"""
        user_perms = cls.get_user_permissions(user, company)
        return all(p in user_perms for p in permission_list)

    @classmethod
    def get_user_role(cls, user, company=None):
        """Get user's primary role"""
        query = UserRole.objects.filter(
            user=user,
            is_primary=True,
            role__is_active=True
        ).select_related('role')

        if company:
            query = query.filter(
                models.Q(company=company) | models.Q(company__isnull=True)
            )

        ur = query.first()
        return ur.role if ur and ur.is_valid() else None

    @classmethod
    def assign_role(cls, user, role_type, company=None, created_by=None, is_primary=True):
        """Assign role to user"""
        try:
            role = Role.objects.get(role_type=role_type)
        except Role.DoesNotExist:
            raise ValueError(f"Role '{role_type}' does not exist")

        # If primary, unset other primary roles
        if is_primary:
            UserRole.objects.filter(user=user, company=company).update(is_primary=False)

        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=role,
            company=company,
            defaults={
                'is_primary': is_primary,
                'created_by': created_by
            }
        )

        return user_role

    @classmethod
    def clear_user_cache(cls, user):
        """Clear all cached permissions for user"""
        # Clear basic cache
        cache_key = f"user_perms_{user.id}"
        cache.delete(cache_key)

        # Clear company-specific caches
        from companies.models import Company
        for company in Company.objects.all():
            cache_key = f"user_perms_{user.id}_company_{company.id}"
            cache.delete(cache_key)
