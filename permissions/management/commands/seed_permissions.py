"""
Seed permissions, roles, and auto-assign UserRoles from UserProfile.role.
Usage: python manage.py seed_permissions
"""
from django.core.management.base import BaseCommand
from permissions.models import Permission, Role, UserRole


MODULES = [
    'users', 'companies', 'partners', 'invoices', 'documents',
    'finance', 'worktime', 'projects', 'reports', 'calculator', 'system',
]
ACTIONS = ['view', 'create', 'edit', 'delete', 'approve', 'export', 'import', 'manage']

# role_type -> list of 'module.action' codenames (or '*' = all, 'module.*' = all actions)
ROLE_PERMS = {
    'superadmin': ['*'],
    'company_admin': [
        'users.*', 'companies.*', 'partners.*', 'invoices.*', 'documents.*',
        'finance.*', 'worktime.*', 'projects.*', 'reports.*', 'calculator.*',
        # everything except system.manage
        'system.view', 'system.create', 'system.edit', 'system.delete',
        'system.approve', 'system.export', 'system.import',
    ],
    'accountant': [
        'invoices.*', 'finance.*', 'reports.*', 'partners.view',
    ],
    'manager': [
        'worktime.*', 'projects.*', 'reports.view', 'reports.export', 'users.view',
    ],
    'worker': [
        'worktime.view', 'worktime.create', 'projects.view',
    ],
    'partner': [
        'invoices.view', 'documents.view', 'projects.view',
    ],
    'investor': [
        'finance.view', 'reports.view', 'reports.export', 'projects.view',
    ],
    'guest': [
        'users.view', 'companies.view', 'projects.view', 'reports.view',
    ],
}

ROLE_NAMES = {
    'superadmin': 'Super Admin',
    'company_admin': 'Company Admin',
    'accountant': 'Accountant',
    'manager': 'Manager',
    'worker': 'Worker',
    'partner': 'Partner',
    'investor': 'Investor',
    'guest': 'Guest',
}

# UserProfile.role -> RBAC role_type
PROFILE_ROLE_MAP = {
    'superadmin': 'superadmin',
    'company_admin': 'company_admin',
    'project_manager': 'manager',
    'worker': 'worker',
    'investor': 'investor',
    'partner': 'partner',
}


def _expand(spec_list):
    """Expand 'module.*' and '*' into concrete 'module.action' codenames."""
    result = set()
    for spec in spec_list:
        if spec == '*':
            for m in MODULES:
                for a in ACTIONS:
                    result.add(f'{m}.{a}')
        elif spec.endswith('.*'):
            mod = spec[:-2]
            for a in ACTIONS:
                result.add(f'{mod}.{a}')
        else:
            result.add(spec)
    return result


class Command(BaseCommand):
    help = 'Seed 88 permissions, 8 roles, and auto-assign user roles'

    def handle(self, *args, **options):
        # 1) Seed Permissions
        created_perms = 0
        for mod in MODULES:
            for act in ACTIONS:
                codename = f'{mod}.{act}'
                _, created = Permission.objects.get_or_create(
                    module=mod,
                    action=act,
                    defaults={
                        'codename': codename,
                        'name': f'{mod.title()} - {act.title()}',
                    },
                )
                if created:
                    created_perms += 1
        self.stdout.write(f'Permissions: {created_perms} created, {len(MODULES)*len(ACTIONS)} total')

        # 2) Seed Roles
        created_roles = 0
        for role_type, name in ROLE_NAMES.items():
            role, created = Role.objects.get_or_create(
                role_type=role_type,
                defaults={'name': name, 'description': f'{name} role'},
            )
            if created:
                created_roles += 1
            # Assign permissions
            codenames = _expand(ROLE_PERMS.get(role_type, []))
            perms = Permission.objects.filter(codename__in=codenames)
            role.permissions.set(perms)
        self.stdout.write(f'Roles: {created_roles} created, {len(ROLE_NAMES)} total')

        # 3) Auto-assign UserRoles from UserProfile.role
        assigned = 0
        try:
            from accounts.models import UserProfile
            for profile in UserProfile.objects.select_related('user').all():
                rbac_type = PROFILE_ROLE_MAP.get(profile.role)
                if not rbac_type:
                    continue
                try:
                    role = Role.objects.get(role_type=rbac_type)
                except Role.DoesNotExist:
                    continue
                _, created = UserRole.objects.get_or_create(
                    user=profile.user,
                    role=role,
                    defaults={'is_primary': True},
                )
                if created:
                    assigned += 1
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'UserRole auto-assign skipped: {e}'))
        self.stdout.write(self.style.SUCCESS(f'UserRoles assigned: {assigned}'))
