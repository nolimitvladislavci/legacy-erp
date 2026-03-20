from django.contrib import admin

from .models import Permission, PermissionOverride, Role, UserRole


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'module', 'action', 'name', 'is_active']
    list_filter = ['module', 'action', 'is_active']
    search_fields = ['codename', 'name', 'description']
    filter_horizontal = ['requires']
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['role_type', 'name', 'parent_role', 'is_active']
    list_filter = ['role_type', 'is_active']
    filter_horizontal = ['permissions']
    search_fields = ['name', 'description']
@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'company', 'is_primary', 'valid_from', 'valid_until']
    list_filter = ['role', 'is_primary', 'company']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user', 'created_by']
@admin.register(PermissionOverride)
class PermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ['user', 'permission', 'grant', 'company', 'valid_until']
    list_filter = ['grant', 'company']
    search_fields = ['user__username', 'permission__codename', 'reason']
    raw_id_fields = ['user', 'created_by']
