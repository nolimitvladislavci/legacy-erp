"""
Initialize default permissions and roles
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from permissions.models import Permission, Role


class Command(BaseCommand):
    help = 'Initialize default permissions and roles'

    def handle(self, *args, **options):
        self.stdout.write('🔐 Initializing permissions...')

        with transaction.atomic():
            # Define all permissions
            permissions_data = [
                # Users
                ('users', 'view', 'users.view', 'View Users'),
                ('users', 'create', 'users.create', 'Create Users'),
                ('users', 'edit', 'users.edit', 'Edit Users'),
                ('users', 'delete', 'users.delete', 'Delete Users'),
                ('users', 'manage', 'users.manage', 'Manage Users & Roles'),

                # Companies
                ('companies', 'view', 'companies.view', 'View Companies'),
                ('companies', 'create', 'companies.create', 'Create Companies'),
                ('companies', 'edit', 'companies.edit', 'Edit Companies'),
                ('companies', 'delete', 'companies.delete', 'Delete Companies'),
                ('companies', 'manage', 'companies.manage', 'Manage Companies'),

                # Partners
                ('partners', 'view', 'partners.view', 'View Partners'),
                ('partners', 'create', 'partners.create', 'Create Partners'),
                ('partners', 'edit', 'partners.edit', 'Edit Partners'),
                ('partners', 'delete', 'partners.delete', 'Delete Partners'),

                # Invoices
                ('invoices', 'view', 'invoices.view', 'View Invoices'),
                ('invoices', 'create', 'invoices.create', 'Create Invoices'),
                ('invoices', 'edit', 'invoices.edit', 'Edit Invoices'),
                ('invoices', 'delete', 'invoices.delete', 'Delete Invoices'),
                ('invoices', 'approve', 'invoices.approve', 'Approve Invoices'),
                ('invoices', 'export', 'invoices.export', 'Export Invoices'),

                # Documents
                ('documents', 'view', 'documents.view', 'View Documents'),
                ('documents', 'create', 'documents.create', 'Upload Documents'),
                ('documents', 'edit', 'documents.edit', 'Edit Documents'),
                ('documents', 'delete', 'documents.delete', 'Delete Documents'),
                ('documents', 'manage', 'documents.manage', 'Manage Documents'),

                # Finance
                ('finance', 'view', 'finance.view', 'View Finance'),
                ('finance', 'create', 'finance.create', 'Create Finance Records'),
                ('finance', 'edit', 'finance.edit', 'Edit Finance Records'),
                ('finance', 'approve', 'finance.approve', 'Approve Finance'),
                ('finance', 'export', 'finance.export', 'Export Finance Data'),

                # Work Time
                ('worktime', 'view', 'worktime.view', 'View Work Time'),
                ('worktime', 'create', 'worktime.create', 'Create Time Entries'),
                ('worktime', 'edit', 'worktime.edit', 'Edit Time Entries'),
                ('worktime', 'delete', 'worktime.delete', 'Delete Time Entries'),
                ('worktime', 'approve', 'worktime.approve', 'Approve Time Entries'),
                ('worktime', 'export', 'worktime.export', 'Export Time Data'),

                # Projects
                ('projects', 'view', 'projects.view', 'View Projects'),
                ('projects', 'create', 'projects.create', 'Create Projects'),
                ('projects', 'edit', 'projects.edit', 'Edit Projects'),
                ('projects', 'delete', 'projects.delete', 'Delete Projects'),
                ('projects', 'manage', 'projects.manage', 'Manage Projects'),

                # Reports
                ('reports', 'view', 'reports.view', 'View Reports'),
                ('reports', 'create', 'reports.create', 'Create Reports'),
                ('reports', 'export', 'reports.export', 'Export Reports'),

                # Calculator
                ('calculator', 'view', 'calculator.view', 'View Calculator'),
                ('calculator', 'create', 'calculator.create', 'Create Estimates'),
                ('calculator', 'edit', 'calculator.edit', 'Edit Estimates'),

                # System
                ('system', 'view', 'system.view', 'View System Settings'),
                ('system', 'manage', 'system.manage', 'Manage System Settings'),
            ]

            perm_objects = {}
            for module, action, codename, name in permissions_data:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    defaults={
                        'module': module,
                        'action': action,
                        'name': name,
                    }
                )
                perm_objects[codename] = perm
                if created:
                    self.stdout.write(f'  ✓ Created: {codename}')

            # Define roles
            roles_data = [
                ('superadmin', '👑 Super Admin', 'all'),
                ('company_admin', '🏢 Company Admin', [
                    'users.view', 'users.create', 'users.edit',
                    'companies.view', 'companies.edit',
                    'partners.view', 'partners.create', 'partners.edit',
                    'invoices.view', 'invoices.create', 'invoices.edit', 'invoices.approve',
                    'documents.view', 'documents.create', 'documents.edit',
                    'finance.view', 'finance.create', 'finance.edit',
                    'worktime.view', 'worktime.approve', 'worktime.export',
                    'projects.view', 'projects.create', 'projects.edit', 'projects.manage',
                    'reports.view', 'reports.create', 'reports.export',
                    'calculator.view', 'calculator.create', 'calculator.edit',
                ]),
                ('accountant', '💼 Accountant', [
                    'invoices.view', 'invoices.create', 'invoices.edit', 'invoices.export',
                    'finance.view', 'finance.create', 'finance.edit', 'finance.export',
                    'documents.view', 'documents.create',
                    'reports.view', 'reports.export',
                    'partners.view',
                ]),
                ('manager', '📊 Manager', [
                    'users.view',
                    'worktime.view', 'worktime.approve', 'worktime.export',
                    'projects.view', 'projects.edit',
                    'reports.view', 'reports.export',
                    'documents.view',
                ]),
                ('worker', '👷 Worker', [
                    'worktime.view', 'worktime.create', 'worktime.edit',
                    'documents.view',
                    'projects.view',
                ]),
                ('partner', '🤝 Partner', [
                    'invoices.view',
                    'documents.view',
                    'projects.view',
                ]),
                ('investor', '💰 Investor', [
                    'finance.view',
                    'reports.view',
                    'companies.view',
                ]),
                ('guest', '👁️ Guest', [
                    'projects.view',
                    'reports.view',
                ]),
            ]

            for role_type, name, perms in roles_data:
                role, created = Role.objects.get_or_create(
                    role_type=role_type,
                    defaults={'name': name}
                )

                if perms == 'all':
                    role.permissions.set(Permission.objects.all())
                else:
                    role_perms = [perm_objects[p] for p in perms if p in perm_objects]
                    role.permissions.set(role_perms)

                if created:
                    self.stdout.write(f'  ✓ Created role: {name}')
                else:
                    self.stdout.write(f'  ↻ Updated role: {name}')

        self.stdout.write(self.style.SUCCESS('✅ Permissions initialized!'))
