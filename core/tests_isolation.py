"""
Company Isolation Tests — firma A ne smije vidjeti podatke firme B.
Pokretanje: python manage.py test core.tests_isolation --verbosity=2
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from accounts.models import UserProfile


def _make_company(oib):
    from companies.models import Company
    return Company.objects.create(name='Co_' + oib, oib=oib)


def _make_user(company, username):
    u = User.objects.create_superuser(username=username, password='pass', email='')
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u


class InvoiceIsolationTest(TestCase):
    def setUp(self):
        from invoicing.models import Invoice
        import uuid
        from django.utils import timezone
        self.co_a = _make_company('10000000001')
        self.co_b = _make_company('10000000002')
        self.user_b = _make_user(self.co_b, 'inv_user_b')
        self.inv_a = Invoice.objects.create(
            company=self.co_a, number='INV-A-001', doctype='RACUN',
            uuid=uuid.uuid4(), date_issued=timezone.now(),
            currency='EUR', subtotal=100, tax_amount=25, total=125, status='DRAFT',
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_invoice_a(self):
        resp = self.client.get('/invoicing/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'INV-A-001')


class PartnerIsolationTest(TestCase):
    def setUp(self):
        from partners.models import Partner
        import uuid
        self.co_a = _make_company('20000000001')
        self.co_b = _make_company('20000000002')
        self.user_b = _make_user(self.co_b, 'par_user_b')
        self.partner_a = Partner.objects.create(
            company=self.co_a, name='Tajna Firma A',
            oib='33333333333', is_active=True,
            portal_token=uuid.uuid4(),
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_partner_a(self):
        resp = self.client.get('/partners/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Tajna Firma A')


class ProjectIsolationTest(TestCase):
    def setUp(self):
        from projects.models import Project
        self.co_a = _make_company('30000000001')
        self.co_b = _make_company('30000000002')
        self.user_b = _make_user(self.co_b, 'proj_user_b')
        self.project_a = Project.objects.create(
            company=self.co_a, name='Tajni Projekt A',
            code='PRJ-A', status='planning',
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_project_a(self):
        resp = self.client.get('/projects/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Tajni Projekt A')


class DocumentIsolationTest(TestCase):
    def setUp(self):
        from documents.models import Document
        from django.utils import timezone
        self.co_a = _make_company('40000000001')
        self.co_b = _make_company('40000000002')
        self.user_b = _make_user(self.co_b, 'doc_user_b')
        self.doc_a = Document.objects.create(
            company=self.co_a, doc_number='DOC-TAJNA-A',
            doc_type='other', date_issued=timezone.now().date(),
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_document_a(self):
        resp = self.client.get('/documents/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'DOC-TAJNA-A')


class POSIsolationTest(TestCase):
    def setUp(self):
        from pos.models import POSTerminal
        self.co_a = _make_company('50000000001')
        self.co_b = _make_company('50000000002')
        self.user_b = _make_user(self.co_b, 'pos_user_b')
        self.terminal_a = POSTerminal.objects.create(
            company=self.co_a, name='Kasa Firme A',
            terminal_code='KASA-A', is_active=True,
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_terminal_a(self):
        resp = self.client.get('/pos/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Kasa Firme A')


class InventoryIsolationTest(TestCase):
    def setUp(self):
        from inventory.models import InventoryItem
        from decimal import Decimal
        self.co_a = _make_company('60000000001')
        self.co_b = _make_company('60000000002')
        self.user_b = _make_user(self.co_b, 'inv2_user_b')
        self.item_a = InventoryItem.objects.create(
            company=self.co_a, name='Tajni Artikl A',
            sku='SKU-SECRET-A', unit='kom',
            unit_price=Decimal('9.99'),
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_item_a(self):
        resp = self.client.get('/inventory/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Tajni Artikl A')


class WorkOrderIsolationTest(TestCase):
    def setUp(self):
        from work_orders.models import WorkOrder
        self.co_a = _make_company('70000000001')
        self.co_b = _make_company('70000000002')
        self.user_b = _make_user(self.co_b, 'wo_user_b')
        self.wo_a = WorkOrder.objects.create(
            company=self.co_a, order_number='WO-TAJNA-A',
            status='draft', description='Tajni opis A',
        )
        self.client = Client()
        self.client.force_login(self.user_b)

    def test_user_b_cannot_see_work_order_a(self):
        resp = self.client.get('/work-orders/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'WO-TAJNA-A')
