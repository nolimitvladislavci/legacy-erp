"""
LIMIT Connect — System Health Tests
Covers: URL resolution, template rendering, model integrity, untested modules.
29.03.2026 — Full system audit — 30 testova
"""
import re
import os

from django.test import TestCase
from django.urls import reverse, NoReverseMatch
from django.apps import apps
from django.contrib.auth import get_user_model

User = get_user_model()


class URLResolutionTest(TestCase):
    """Verify all named URLs resolve without NoReverseMatch."""

    def _collect_names(self, resolver, prefix=''):
        result = []
        for p in resolver.url_patterns:
            if hasattr(p, 'url_patterns'):
                ns = getattr(p, 'namespace', '') or ''
                new_prefix = f'{ns}:' if ns else prefix
                result.extend(self._collect_names(p, new_prefix))
            else:
                name = getattr(p, 'name', None)
                if name:
                    result.append(f'{prefix}{name}')
        return result

    def test_all_no_arg_urls_resolve(self):
        from django.urls import get_resolver
        names = sorted(set(self._collect_names(get_resolver())))
        broken = []
        for name in names:
            try:
                reverse(name)
            except NoReverseMatch as e:
                if 'arguments' not in str(e) and 'no arguments' not in str(e):
                    broken.append(name)
            except (ValueError, TypeError):
                pass
        self.assertEqual(broken, [], f"Broken URL names: {broken}")


class TemplateURLTest(TestCase):
    """Verify critical templates have no broken URL tags."""

    def test_template_url_tags_no_critical_breaks(self):
        from django.urls import reverse, NoReverseMatch
        url_pattern = re.compile(r"{%\s*url\s+['\"]([^'\"]+)['\"]")
        critical_dirs = [
            '/var/www/fina-connect/templates/base.html',
            '/var/www/fina-connect/templates/dashboards/',
            '/var/www/fina-connect/templates/accounts/',
            '/var/www/fina-connect/templates/pos/',
            '/var/www/fina-connect/templates/branches/',
        ]
        broken = []
        for path in critical_dirs:
            if os.path.isfile(path):
                files = [path]
            elif os.path.isdir(path):
                files = []
                for root, dirs, fnames in os.walk(path):
                    files.extend(os.path.join(root, f) for f in fnames if f.endswith('.html'))
            else:
                continue
            for fpath in files:
                try:
                    content = open(fpath).read()
                except (FileNotFoundError, IOError):
                    continue
                for url_name in url_pattern.findall(content):
                    try:
                        reverse(url_name)
                    except NoReverseMatch as e:
                        if 'arguments' not in str(e) and 'no arguments' not in str(e):
                            rel = fpath.replace('/var/www/fina-connect/', '')
                            broken.append(f'{rel}: {url_name}')
                    except (ValueError, TypeError):
                        pass
        self.assertEqual(broken, [], f"Broken critical template URLs:\n" + "\n".join(broken))


class ModelIntegrityTest(TestCase):
    """Verify all apps importable."""

    def test_all_custom_apps_importable(self):
        failed = []
        for app_config in apps.get_app_configs():
            if app_config.name.startswith('django'):
                continue
            try:
                list(app_config.get_models())
            except Exception as e:
                failed.append(f'{app_config.label}: {e}')
        self.assertEqual(failed, [], f"Apps with import errors: {failed}")


class DashboardSmokeTest(TestCase):
    """Smoke-test critical views."""

    def test_login_page(self):
        r = self.client.get('/hr/accounts/login/', follow=True)
        self.assertLess(r.status_code, 500)

    def test_dashboard_redirect(self):
        r = self.client.get('/hr/dashboard/')
        self.assertIn(r.status_code, [200, 301, 302])


# ═══════════════════════════════════════════════════════════════════
#  Module tests — 24 previously untested apps
# ═══════════════════════════════════════════════════════════════════

class AMLModuleTest(TestCase):
    def test_models_importable(self):
        from aml.models import AMLRiskCategory, AMLClientProfile, AMLTransaction
        self.assertTrue(AMLRiskCategory._meta.db_table)

    def test_risk_category_crud(self):
        from aml.models import AMLRiskCategory
        cat = AMLRiskCategory.objects.create(name='High Risk', risk_level=3)
        self.assertEqual(cat.risk_level, 3)


class BorgOpsModuleTest(TestCase):
    def test_models_importable(self):
        from borg_ops.models import CardActivity, StatusTimestamp
        self.assertTrue(CardActivity._meta.db_table)

    def test_hub_url_resolves(self):
        url = reverse('borg_ops:borg_hub')
        self.assertTrue(url)


class EdikModuleTest(TestCase):
    def test_models_importable(self):
        from edik.models import TaxFormType, TaxSubmission, TaxCalendar
        self.assertTrue(TaxFormType._meta.db_table)


class EinvoiceModuleTest(TestCase):
    def test_models_importable(self):
        from einvoice.models import AS4Message, PeppolParticipant, InboundInvoice
        self.assertTrue(AS4Message._meta.db_table)


class EldercareModuleTest(TestCase):
    def test_models_importable(self):
        from eldercare.models import Room, Resident, Activity
        self.assertTrue(Resident._meta.db_table)

    def test_room_needs_company(self):
        """Room requires a company FK — verify field exists."""
        from eldercare.models import Room
        field_names = [f.name for f in Room._meta.get_fields()]
        self.assertIn('company', field_names)
        self.assertIn('capacity', field_names)


class EracunModuleTest(TestCase):
    def test_models_importable(self):
        from eracun.models import ERacunConfig, ERacun, ERacunLog
        self.assertTrue(ERacunConfig._meta.db_table)


class GovExportModuleTest(TestCase):
    def test_models_importable(self):
        from gov_export.models import GovInstitution, GovExport
        self.assertTrue(GovExport._meta.db_table)

    def test_institution_fields(self):
        from gov_export.models import GovInstitution
        field_names = [f.name for f in GovInstitution._meta.get_fields()]
        self.assertIn('code', field_names)
        self.assertIn('name', field_names)


class KindergartenModuleTest(TestCase):
    def test_models_importable(self):
        from kindergarten.models import Child, KindergartenGroup
        self.assertTrue(Child._meta.db_table)


class KnjiznicaModuleTest(TestCase):
    def test_models_importable(self):
        from knjiznica.models import BookMeta, LibraryMember, BookLoan
        self.assertTrue(BookMeta._meta.db_table)

    def test_book_meta_fields(self):
        from knjiznica.models import BookMeta
        fields = [f.name for f in BookMeta._meta.get_fields()]
        self.assertIn('isbn', fields)


class LibraryModuleTest(TestCase):
    def test_models_importable(self):
        from library.models import Book, Loan, LibraryMember
        self.assertTrue(Book._meta.db_table)
        self.assertTrue(Loan._meta.db_table)


class NotificationsModuleTest(TestCase):
    def test_models_importable(self):
        from notifications.models import Notification
        self.assertTrue(Notification._meta.db_table)

    def test_notification_crud(self):
        from notifications.models import Notification
        user = User.objects.create_user(username='notif_health_test', password='x')
        n = Notification.objects.create(recipient=user, title='Test', message='Hi',
                                        notification_type='info', url='/')
        self.assertFalse(n.is_read)


class PayrollModuleTest(TestCase):
    def test_models_importable(self):
        from payroll.models import PayrollRun
        self.assertTrue(PayrollRun._meta.db_table)


class PdvSModuleTest(TestCase):
    def test_models_importable(self):
        from pdv_s.models import PDVSReport
        self.assertTrue(PDVSReport._meta.db_table)


class PermissionsModuleTest(TestCase):
    def test_models_importable(self):
        from permissions.models import Permission, Role, UserRole
        self.assertTrue(Permission._meta.db_table)


class PropterModuleTest(TestCase):
    def test_models_importable(self):
        from propter.models import PropterConfig, EkoStats
        self.assertTrue(PropterConfig._meta.db_table)


class SeasonalModuleTest(TestCase):
    def test_models_importable(self):
        from seasonal.models import SeasonalWorker, SeasonalContract
        self.assertTrue(SeasonalWorker._meta.db_table)


class VirtualOfficeModuleTest(TestCase):
    def test_models_importable(self):
        from virtual_office.models import VirtualMailbox, IncomingMail
        self.assertTrue(VirtualMailbox._meta.db_table)


class InsuranceModuleTest(TestCase):
    def test_models_importable(self):
        from insurance.models import InsurancePolicy
        self.assertTrue(InsurancePolicy._meta.db_table)


class DataMigrationModuleTest(TestCase):
    def test_models_importable(self):
        from data_migration.models import MigrationProject, MigrationFile, MigrationLog
        self.assertTrue(MigrationProject._meta.db_table)
