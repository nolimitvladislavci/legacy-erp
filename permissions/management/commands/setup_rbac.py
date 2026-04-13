"""
Setup RBAC groups with proper permissions.
Run: python manage.py setup_rbac

Creates 4 groups:
  - Radnik (Worker): view-only on own data
  - Voditelj (Manager): view + manage team
  - Admin (Company Admin): full CRUD on company data
  - Superadmin: everything

Then assigns existing users to groups based on their profile.role.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


# Permission mappings per group
GROUP_PERMISSIONS = {
    'Radnik': {
        # Workers: view own worktime, appointments, projects
        'worktime': ['view_worktimeentry', 'add_worktimeentry', 'change_worktimeentry'],
        'appointments': ['view_appointment'],
        'projects': ['view_project', 'view_task'],
        'pos': ['view_possession', 'add_possession', 'change_possession', 'view_positem'],
        'invoicing': ['view_invoice'],
        'inventory': ['view_inventoryitem', 'view_stockmovement'],
        'documents': ['view_document'],
    },
    'Voditelj': {
        # Managers: everything workers can + manage team
        'worktime': ['view_worktimeentry', 'add_worktimeentry', 'change_worktimeentry',
                     'delete_worktimeentry', 'view_worktimesummary'],
        'appointments': ['view_appointment', 'add_appointment', 'change_appointment',
                        'delete_appointment'],
        'projects': ['view_project', 'add_project', 'change_project',
                    'view_task', 'add_task', 'change_task'],
        'pos': ['view_possession', 'add_possession', 'change_possession',
                'delete_possession', 'view_positem', 'add_positem'],
        'invoicing': ['view_invoice', 'add_invoice'],
        'inventory': ['view_inventoryitem', 'view_stockmovement', 'add_stockmovement'],
        'documents': ['view_document', 'add_document', 'change_document'],
        'partners': ['view_partner'],
    },
    'Admin': {
        # Company admins: full CRUD on most things
        'worktime': '*',
        'appointments': '*',
        'projects': '*',
        'pos': '*',
        'invoicing': '*',
        'inventory': '*',
        'documents': '*',
        'partners': '*',
        'konto': '*',
        'payroll': '*',
        'eracun': '*',
    },
    'Superadmin': {
        # Everything
        '__all__': True,
    },
}

# Map profile roles to groups
ROLE_TO_GROUP = {
    'worker': 'Radnik',
    'employee': 'Radnik',
    'project_manager': 'Voditelj',
    'company_admin': 'Admin',
    'superadmin': 'Superadmin',
    'partner': 'Radnik',
    'investor': 'Radnik',
}


class Command(BaseCommand):
    help = 'Setup RBAC groups and assign users based on profile roles.'

    def handle(self, *args, **options):
        created_groups = 0
        assigned_users = 0

        for group_name, app_perms in GROUP_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                created_groups += 1
                self.stdout.write(f'  Created group: {group_name}')

            if app_perms.get('__all__'):
                # Superadmin gets ALL permissions
                group.permissions.set(Permission.objects.all())
                self.stdout.write(f'    -> {Permission.objects.count()} permissions (all)')
            else:
                perms = []
                for app_label, codenames in app_perms.items():
                    if codenames == '*':
                        # All permissions for this app
                        app_perms_qs = Permission.objects.filter(
                            content_type__app_label=app_label
                        )
                        perms.extend(app_perms_qs)
                    else:
                        for codename in codenames:
                            try:
                                perm = Permission.objects.get(
                                    codename=codename,
                                    content_type__app_label=app_label,
                                )
                                perms.append(perm)
                            except Permission.DoesNotExist:
                                # Permission might not exist yet
                                pass
                            except Permission.MultipleObjectsReturned:
                                perm = Permission.objects.filter(
                                    codename=codename,
                                    content_type__app_label=app_label,
                                ).first()
                                if perm:
                                    perms.append(perm)

                group.permissions.set(perms)
                self.stdout.write(f'    -> {len(perms)} permissions')

        # Assign users to groups
        from django.contrib.auth.models import User
        for user in User.objects.all():
            try:
                role = user.profile.role
            except AttributeError:
                role = None

            if not role:
                continue

            group_name = ROLE_TO_GROUP.get(role)
            if not group_name:
                continue

            try:
                group = Group.objects.get(name=group_name)
                if not user.groups.filter(pk=group.pk).exists():
                    user.groups.add(group)
                    assigned_users += 1
                    self.stdout.write(f'  {user.username} -> {group_name}')
            except Group.DoesNotExist:
                pass

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {created_groups} groups created, {assigned_users} users assigned'
        ))
