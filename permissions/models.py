"""
🔐 RBAC Permission System
Granular role-based access control
"""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from core.managers import CompanyManager


class Permission(models.Model):
    """Granular permissions across all modules"""

    MODULE_CHOICES = [
        ('users', '👥 Users'),
        ('companies', '🏢 Companies'),
        ('partners', '🤝 Partners'),
        ('invoices', '📄 Invoices'),
        ('documents', '📎 Documents'),
        ('finance', '💰 Finance'),
        ('worktime', '⏱️ Work Time'),
        ('projects', '📊 Projects'),
        ('reports', '📈 Reports'),
        ('calculator', '🧮 Calculator'),
        ('system', '⚙️ System'),
    ]

    ACTION_CHOICES = [
        ('view', '👁️ View'),
        ('create', '➕ Create'),
        ('edit', '✏️ Edit'),
        ('delete', '🗑️ Delete'),
        ('approve', '✅ Approve'),
        ('export', '📤 Export'),
        ('import', '📥 Import'),
        ('manage', '⚙️ Manage'),
    ]

    module = models.CharField(max_length=50, choices=MODULE_CHOICES, db_index=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    codename = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Hierarchical permissions
    requires = models.ManyToManyField('self', blank=True, symmetrical=False,
                                     related_name='unlocks',
                                     help_text="Required permissions")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'permissions'
        ordering = ['module', 'action']
        indexes = [
            models.Index(fields=['module', 'action']),
            models.Index(fields=['codename']),
        ]
        unique_together = [['module', 'action']]

    def __str__(self):
        return f"{self.get_module_display()}: {self.get_action_display()}"

    def get_full_codename(self):
        """Return module.action format"""
        return f"{self.module}.{self.action}"
class Role(models.Model):
    """User roles with permission sets"""

    ROLE_TYPES = [
        ('superadmin', '👑 Super Admin'),
        ('company_admin', '🏢 Company Admin'),
        ('accountant', '💼 Accountant'),
        ('manager', '📊 Manager'),
        ('worker', '👷 Worker'),
        ('partner', '🤝 Partner'),
        ('investor', '💰 Investor'),
        ('guest', '👁️ Guest'),
    ]

    role_type = models.CharField(max_length=50, choices=ROLE_TYPES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, related_name='roles', blank=True)

    # Role hierarchy
    parent_role = models.ForeignKey('self', null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='child_roles')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        ordering = ['role_type']

    def __str__(self):
        return self.get_role_type_display()

    def get_all_permissions(self):
        """Get permissions including inherited from parent"""
        perms = set(self.permissions.filter(is_active=True).values_list('codename', flat=True))

        # Inherit from parent
        if self.parent_role:
            perms.update(self.parent_role.get_all_permissions())

        return list(perms)

    def clear_cache(self):
        """Clear cached permissions for this role"""
        cache_key = f"role_perms_{self.role_type}"
        cache.delete(cache_key)
class UserRole(models.Model):
    """User-Role assignment with scope"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_assignments')

    # Scope limitations
    company = models.ForeignKey('companies.Company', null=True, blank=True,
                               on_delete=models.CASCADE,
                               help_text="Limit role to specific company")

    # Time-based access
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    is_primary = models.BooleanField(default=True,
                                     help_text="Primary role for user")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True,
                                  on_delete=models.SET_NULL,
                                  related_name='assigned_roles')
    objects = CompanyManager()

    class Meta:
        db_table = 'user_roles'
        ordering = ['-is_primary', 'role']
        indexes = [
            models.Index(fields=['user', 'role']),
            models.Index(fields=['company']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

    def is_valid(self):
        """Check if role assignment is currently valid"""
        from django.utils import timezone
        now = timezone.now()

        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False

        return True
class PermissionOverride(models.Model):
    """Override specific permissions for users"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permission_overrides')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    # Grant or revoke
    grant = models.BooleanField(default=True, help_text="True=Grant, False=Revoke")

    # Scope
    company = models.ForeignKey('companies.Company', null=True, blank=True,
                               on_delete=models.CASCADE)

    reason = models.TextField(help_text="Why this override exists")

    valid_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                  related_name='granted_overrides')
    objects = CompanyManager()

    class Meta:
        db_table = 'permission_overrides'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'permission']),
        ]

    def __str__(self):
        action = "GRANT" if self.grant else "REVOKE"
        return f"{action}: {self.user.username} - {self.permission.codename}"
# ============================================================================
# SIGNALS - Clear cache on changes
# ============================================================================
@receiver([post_save, post_delete], sender=Role)
def clear_role_cache(sender, instance, **kwargs):
    """Clear role cache when permissions change"""
    instance.clear_cache()
@receiver([post_save, post_delete], sender=UserRole)
def clear_user_permission_cache(sender, instance, **kwargs):
    """Clear user permission cache"""
    cache_key = f"user_perms_{instance.user.id}"
    cache.delete(cache_key)
