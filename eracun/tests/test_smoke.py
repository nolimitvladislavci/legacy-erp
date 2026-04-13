"""
Comprehensive test suite — 60+ tests covering ALL modules in LIMIT Connect.
Catches 500 errors, import errors, template errors, missing context, DB errors.

Run: python manage.py test eracun.tests.test_smoke --verbosity=2
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


class DataFactory:
    """Creates realistic test data for all modules."""

    @classmethod
    def create_all(cls):
        data = {}
        data['user'] = cls.create_user()
        data['admin'] = cls.create_admin()
        data['company'] = cls.create_company()
        data['profile'] = cls.create_profile(data['admin'], data['company'])
        data['user_profile'] = cls.create_profile(data['user'], data['company'], role='worker')
        data['subscription'] = cls.create_subscription(data['company'])
        data['partner'] = cls.create_partner(data['company'])
        data['project'] = cls.create_project(data['company'], data['admin'])
        data.update(cls.create_invoicing_data(data['company'], data['admin']))
        data.update(cls.create_eracun_data(data['company'], data['admin']))
        data.update(cls.create_inventory_data(data['company']))
        data.update(cls.create_worktime_data(data['company'], data['admin'], data['project']))
        data.update(cls.create_pos_data(data['company'], data['admin']))
        data.update(cls.create_rental_data(data['company']))
        data.update(cls.create_payment_data(data['company']))
        data.update(cls.create_finance_data(data['company']))
        data.update(cls.create_document_data(data['company'], data['admin']))
        data.update(cls.create_assessment_data(data['company'], data['admin']))
        data.update(cls.create_work_order_data(data['company'], data['admin']))
        data.update(cls.create_insurance_data(data['company']))
        data.update(cls.create_payroll_data(data['company']))
        return data

    @classmethod
    def create_user(cls, username='testuser', is_staff=False):
        return User.objects.create_user(
            username=username, password='testpass123',
            email=f'{username}@test.hr',
            first_name='Test', last_name='User',
            is_staff=is_staff,
        )

    @classmethod
    def create_admin(cls):
        return User.objects.create_superuser(
            username='testadmin', password='testpass123',
            email='admin@test.hr',
            first_name='Admin', last_name='Test',
        )

    @classmethod
    def create_company(cls):
        from companies.models import Company
        return Company.objects.create(
            name='Test Firma d.o.o.',
            oib='12345678903',
        )

    @classmethod
    def create_profile(cls, user, company, role='superadmin'):
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults={'company': company, 'role': role}
        )
        return profile

    @classmethod
    def create_subscription(cls, company):
        from registration.models import CompanySubscription, PricingPlan
        all_modules = 'invoicing,pos,inventory,worktime,projects,appointments,partners,documents,finance,webshop,rental,fitness,insurance,calculator,interventions,tracking,assessment,outreach,marketplace,ai_assistant,konto,booking,gastro,reports,burza,delivery,payroll,work_orders'
        plan, _ = PricingPlan.objects.get_or_create(
            name='Test Enterprise',
            defaults={
                'price_monthly': Decimal('0.00'),
                'currency': 'EUR',
                'included_modules': all_modules,
                'is_active': True,
            }
        )
        sub, _ = CompanySubscription.objects.get_or_create(
            company=company,
            defaults={
                'pricing_plan': plan,
                'is_active': True,
                'valid_from': '2026-01-01',
                'monthly_fee': Decimal('0.00'),
            }
        )
        return sub

    @classmethod
    def create_partner(cls, company):
        from partners.models import Partner
        return Partner.objects.create(
            company=company,
            name='Partner d.o.o.',
            oib='11111111111',
            partner_type='customer',
        )

    @classmethod
    def create_project(cls, company, user):
        from projects.models import Project
        return Project.objects.create(
            name='Test Projekt', code='TST-PRJ-001',
            company=company, manager=user, status='active',
        )

    @classmethod
    def create_invoicing_data(cls, company, user):
        from invoicing.models import Invoice, InvoiceItem
        inv = Invoice.objects.create(
            company=company, doctype='Racun', country='HR',
            number='TEST-001',
            date_issued=datetime.date.today(),
            date_due=datetime.date.today(),
            client_name='Kupac d.o.o.', client_oib='98765432109',
            client_address='Testna 1', client_city='Zagreb', client_country='HR',
            issuer_name='Test Firma d.o.o.', issuer_oib='12345678903',
            issuer_address='Ulica 1', issuer_iban='HR1234567890123456789',
            payment_method='Transakcijski',
            subtotal=Decimal('1000.00'), tax_percent=Decimal('25'),
            tax_amount=Decimal('250.00'), total=Decimal('1250.00'),
            status='DRAFT', created_by=user,
        )
        InvoiceItem.objects.create(
            invoice=inv, description='Usluga programiranja',
            quantity=Decimal('10'), unit='sat',
            unit_price=Decimal('100.00'), total_price=Decimal('1000.00'),
        )
        return {'invoice': inv}

    @classmethod
    def create_eracun_data(cls, company, user):
        from eracun.models import ERacun, ERacunConfig, ERacunItem, ERacunTaxSummary
        config, _ = ERacunConfig.objects.get_or_create(
            company=company,
            defaults={'is_active': True, 'cert_oib': '12345678903', 'use_test_env': True}
        )
        er = ERacun.objects.create(
            company=company, doc_type='380', invoice_number='ER-TEST-001',
            issue_date=datetime.date.today(), due_date=datetime.date.today(),
            currency='EUR',
            issuer_name='Test Firma d.o.o.', issuer_oib='12345678903',
            issuer_iban='HR1234567890123456789',
            recipient_name='Kupac d.o.o.', recipient_oib='98765432109',
            subtotal=Decimal('1000.00'), tax_amount=Decimal('250.00'),
            total=Decimal('1250.00'), payment_means_code='30',
            created_by=user,
        )
        ERacunItem.objects.create(
            eracun=er, line_number=1, description='Usluga programiranja',
            quantity=Decimal('10'), unit_code='HUR',
            unit_price=Decimal('100.0000'), line_total=Decimal('1000.00'),
            tax_category='S', tax_rate=Decimal('25'),
        )
        ERacunTaxSummary.objects.create(
            eracun=er, tax_category='S', tax_rate=Decimal('25'),
            taxable_amount=Decimal('1000.00'), tax_amount=Decimal('250.00'),
        )
        return {'eracun_config': config, 'eracun': er}

    @classmethod
    def create_inventory_data(cls, company):
        from inventory.models import InventoryItem
        item = InventoryItem.objects.create(
            company=company, name='Test Artikl', sku='TST-001',
            unit='kom', unit_price=Decimal('50.00'),
            purchase_price=Decimal('25.00'), quantity=Decimal('100.00'),
        )
        return {'inventory_item': item}

    @classmethod
    def create_worktime_data(cls, company, user, project):
        try:
            from worktime.models import TimeEntry
            entry = TimeEntry.objects.create(
                user=user, company=company, project=project,
                date=datetime.date.today(), duration=Decimal('8.00'),
                status='PENDING', description='Test rad',
            )
            return {'time_entry': entry}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def create_pos_data(cls, company, user):
        try:
            from pos.models import POSSession
            session = POSSession.objects.create(
                company=company, user=user,
                opening_cash=Decimal('100.00'),
            )
            return {'pos_session': session}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def create_rental_data(cls, company):
        try:
            from rental.models import Booking, Property
            prop = Property.objects.create(
                company=company, name='Soba 101',
                property_type='room', price_per_night=Decimal('50.00'),
            )
            booking = Booking.objects.create(
                company=company, rental_property=prop,
                guest_name='Test Gost', guest_email='gost@test.hr',
                check_in=datetime.date.today(),
                check_out=datetime.date.today() + datetime.timedelta(days=2),
                total_price=Decimal('100.00'), status='confirmed',
            )
            return {'rental_property': prop, 'booking': booking}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def create_payment_data(cls, company):
        try:
            from payments.models import PaymentConfig
            cfg, _ = PaymentConfig.objects.get_or_create(company=company)
            return {'payment_config': cfg}
        except DatabaseError:
            return {}

    @classmethod
    def create_finance_data(cls, company):
        try:
            from finance.models import Transaction
            tx = Transaction.objects.create(
                company=company, description='Test transakcija',
                amount=Decimal('500.00'), transaction_type='income',
                date=datetime.date.today(),
            )
            return {'transaction': tx}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def create_document_data(cls, company, user):
        try:
            from documents.models import Document
            doc = Document.objects.create(
                company=company, doc_type='otpremnica',
                number='OTP-001', date=datetime.date.today(),
                created_by=user,
            )
            return {'document': doc}
        except (IntegrityError, DatabaseError):
            return {}

    @classmethod
    def create_assessment_data(cls, company, user):
        try:
            from assessment.models import Assessment
            a = Assessment.objects.create(
                company=company, title='Test procjena',
                created_by=user, status='draft',
            )
            return {'assessment': a}
        except (IntegrityError, DatabaseError):
            return {}

    @classmethod
    def create_work_order_data(cls, company, user):
        try:
            from work_orders.models import WorkOrder
            wo = WorkOrder.objects.create(
                company=company, title='Test radni nalog',
                created_by=user, status='open',
            )
            return {'work_order': wo}
        except (IntegrityError, DatabaseError):
            return {}

    @classmethod
    def create_insurance_data(cls, company):
        try:
            from insurance.models import InsurancePolicy
            pol = InsurancePolicy.objects.create(
                company=company, policy_number='POL-001',
                provider='Test Osiguranje',
                start_date=datetime.date.today(),
                end_date=datetime.date.today() + datetime.timedelta(days=365),
                premium=Decimal('1000.00'),
            )
            return {'insurance_policy': pol}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def create_payroll_data(cls, company):
        try:
            from payroll.models import PayrollRun
            pr = PayrollRun.objects.create(
                company=company,
                period_start=datetime.date.today().replace(day=1),
                period_end=datetime.date.today(),
                status='draft',
            )
            return {'payroll_run': pr}
        except (IntegrityError, DatabaseError):
            return {}


# ==========================================================================
# TEST 1: Core & Dashboard pages
# ==========================================================================

class CoreSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_main_dashboard(self):
        r = self.client.get('/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_company_dashboard(self):
        r = self.client.get('/dashboard/company/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_accounts_page(self):
        r = self.client.get('/accounts/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_company_settings(self):
        r = self.client.get('/companies/settings/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 2: Invoicing module (6 tests)
# ==========================================================================

class InvoicingSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_invoice_list(self):
        r = self.client.get('/invoicing/')
        self.assertNotEqual(r.status_code, 500)

    def test_invoice_canvas(self):
        r = self.client.get('/invoicing/canvas/')
        self.assertNotEqual(r.status_code, 500)

    def test_invoice_profiles(self):
        r = self.client.get('/invoicing/profiles/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_invoice_pdf(self):
        inv = self.data['invoice']
        r = self.client.get(f'/invoicing/{inv.pk}/pdf/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_invoice_wizard(self):
        r = self.client.get('/invoicing/wizard/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_invoice_new(self):
        r = self.client.get('/invoicing/new/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 3: e-Racun module (11 tests)
# ==========================================================================

class ERacunUnitTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_eracun_model_created(self):
        er = self.data['eracun']
        self.assertEqual(er.invoice_number, 'ER-TEST-001')
        self.assertEqual(er.total, Decimal('1250.00'))
        self.assertEqual(er.items.count(), 1)
        self.assertEqual(er.tax_summaries.count(), 1)

    def test_ubl_xml_generation(self):
        from eracun.services.ubl_generator import generate_ubl_xml
        er = self.data['eracun']
        xml_bytes = generate_ubl_xml(er)
        self.assertIn(b'Invoice', xml_bytes)
        self.assertIn(b'CustomizationID', xml_bytes)
        self.assertIn(b'ER-TEST-001', xml_bytes)
        self.assertIn(b'12345678903', xml_bytes)
        self.assertIn(b'1250.00', xml_bytes)
        self.assertIn(b'HUR', xml_bytes)

    def test_validation_passes(self):
        from eracun.services.engine import validate_eracun
        er = self.data['eracun']
        is_valid, errors = validate_eracun(er)
        self.assertTrue(is_valid, f'Validation failed: {errors}')

    def test_validation_fails_no_items(self):
        from eracun.models import ERacun
        from eracun.services.engine import validate_eracun
        er = ERacun.objects.create(
            company=self.data['company'], invoice_number='EMPTY-001',
            issue_date=datetime.date.today(),
            issuer_name='Test', issuer_oib='12345678903',
            recipient_name='Kupac', recipient_oib='98765432109',
            total=Decimal('100.00'),
        )
        is_valid, errors = validate_eracun(er)
        self.assertFalse(is_valid)

    def test_oib_validation(self):
        from eracun.services.engine import _validate_oib
        self.assertTrue(_validate_oib('37590751921'))
        self.assertFalse(_validate_oib('12345678900'))
        self.assertFalse(_validate_oib('short'))

    def test_create_from_invoice(self):
        from eracun.services.engine import create_eracun_from_invoice
        inv = self.data['invoice']
        er = create_eracun_from_invoice(inv, user=self.data['admin'])
        self.assertEqual(er.invoice_number, 'TEST-001')
        self.assertEqual(er.total, Decimal('1250.00'))
        self.assertEqual(er.items.count(), 1)

    def test_api_key_generated(self):
        config = self.data['eracun_config']
        self.assertTrue(len(config.api_key) > 20)

    def test_dashboard_view(self):
        r = self.client.get('/eracun/')
        self.assertNotEqual(r.status_code, 500)

    def test_settings_view(self):
        r = self.client.get('/eracun/settings/')
        self.assertNotEqual(r.status_code, 500)

    def test_detail_view(self):
        er = self.data['eracun']
        r = self.client.get(f'/eracun/{er.pk}/')
        self.assertNotEqual(r.status_code, 500)

    def test_xml_download(self):
        er = self.data['eracun']
        r = self.client.get(f'/eracun/{er.pk}/xml/', follow=True)
        self.assertEqual(r.status_code, 200)


# ==========================================================================
# TEST 4: Inventory module (4 tests)
# ==========================================================================

class InventorySmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_item_list(self):
        r = self.client.get('/inventory/')
        self.assertNotEqual(r.status_code, 500)

    def test_stock_overview(self):
        r = self.client.get('/inventory/overview/')
        self.assertNotEqual(r.status_code, 500)

    def test_receipts_list(self):
        r = self.client.get('/inventory/receipts/')
        self.assertNotEqual(r.status_code, 500)

    def test_item_detail(self):
        item = self.data['inventory_item']
        r = self.client.get(f'/inventory/{item.pk}/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 5: Worktime module (3 tests)
# ==========================================================================

class WorktimeSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_worker_dashboard(self):
        r = self.client.get('/worktime/')
        self.assertNotEqual(r.status_code, 500)

    def test_manager_dashboard(self):
        r = self.client.get('/worktime/manager/')
        self.assertNotEqual(r.status_code, 500)

    def test_analytics(self):
        r = self.client.get('/worktime/analytics/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 6: Partners module (2 tests)
# ==========================================================================

class PartnersSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_partner_list(self):
        r = self.client.get('/partners/')
        self.assertNotEqual(r.status_code, 500)

    def test_partner_detail(self):
        r = self.client.get(f'/partners/{self.data["partner"].pk}/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 7: Projects module (2 tests)
# ==========================================================================

class ProjectsSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_project_list(self):
        r = self.client.get('/projects/')
        self.assertNotEqual(r.status_code, 500)

    def test_project_detail(self):
        r = self.client.get(f'/projects/{self.data["project"].pk}/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 8: Documents module (3 tests)
# ==========================================================================

class DocumentsSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_document_list(self):
        r = self.client.get('/documents/')
        self.assertNotEqual(r.status_code, 500)

    def test_otpremnica_list(self):
        r = self.client.get('/documents/otpremnica/')
        self.assertNotEqual(r.status_code, 500)

    def test_primka_list(self):
        r = self.client.get('/documents/primka/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 9: POS module (6 tests)
# ==========================================================================

class POSSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_pos_dashboard(self):
        r = self.client.get('/pos/')
        self.assertNotEqual(r.status_code, 500)

    def test_pos_settings(self):
        r = self.client.get('/pos/settings/')
        self.assertNotEqual(r.status_code, 500)

    def test_pos_gastro(self):
        r = self.client.get('/pos/gastro/')
        self.assertNotEqual(r.status_code, 500)

    def test_pos_expiry(self):
        r = self.client.get('/pos/expiry/')
        self.assertNotEqual(r.status_code, 500)

    def test_pos_waiter(self):
        r = self.client.get('/pos/waiter/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_pos_vouchers(self):
        r = self.client.get('/pos/vouchers/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 10: Rental module (5 tests)
# ==========================================================================

class RentalSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_rental_dashboard(self):
        r = self.client.get('/rental/')
        self.assertNotEqual(r.status_code, 500)

    def test_rental_properties(self):
        r = self.client.get('/rental/properties/')
        self.assertNotEqual(r.status_code, 500)

    def test_rental_bookings(self):
        r = self.client.get('/rental/bookings/')
        self.assertNotEqual(r.status_code, 500)

    def test_rental_housekeeping(self):
        r = self.client.get('/rental/housekeeping/')
        self.assertNotEqual(r.status_code, 500)

    def test_rental_calendar(self):
        r = self.client.get('/rental/calendar/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 11: Finance module (2 tests)
# ==========================================================================

class FinanceSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_finance_list(self):
        r = self.client.get('/finance/')
        self.assertNotEqual(r.status_code, 500)

    def test_cashflow_api(self):
        r = self.client.get('/finance/cashflow-api/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 12: Konto module (7 tests)
# ==========================================================================

class KontoSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_dashboard(self):
        r = self.client.get('/konto/')
        self.assertNotEqual(r.status_code, 500)

    def test_chart_of_accounts(self):
        r = self.client.get('/konto/accounts/')
        self.assertNotEqual(r.status_code, 500)

    def test_journal(self):
        r = self.client.get('/konto/journal/')
        self.assertNotEqual(r.status_code, 500)

    def test_transactions(self):
        r = self.client.get('/konto/transactions/')
        self.assertNotEqual(r.status_code, 500)

    def test_pnl_report(self):
        r = self.client.get('/konto/reports/pnl/')
        self.assertNotEqual(r.status_code, 500)

    def test_balance_sheet(self):
        r = self.client.get('/konto/reports/balance-sheet/')
        self.assertNotEqual(r.status_code, 500)

    def test_vat_report(self):
        r = self.client.get('/konto/reports/vat/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 13: Payments module (2 tests)
# ==========================================================================

class PaymentsSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_payments_dashboard(self):
        r = self.client.get('/payments/')
        self.assertNotEqual(r.status_code, 500)

    def test_payments_settings(self):
        r = self.client.get('/payments/settings/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 14: Delivery module (5 tests)
# ==========================================================================

class DeliverySmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_delivery_dashboard(self):
        r = self.client.get('/delivery/')
        self.assertNotEqual(r.status_code, 500)

    def test_consolidated(self):
        r = self.client.get('/delivery/consolidated/')
        self.assertNotEqual(r.status_code, 500)

    def test_dispatcher(self):
        r = self.client.get('/delivery/dispatcher/')
        self.assertNotEqual(r.status_code, 500)

    def test_haccp(self):
        r = self.client.get('/delivery/haccp/')
        self.assertNotEqual(r.status_code, 500)

    def test_warehouse(self):
        r = self.client.get('/delivery/warehouse/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 15: Reports module (3 tests)
# ==========================================================================

class ReportsSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_reports_dashboard(self):
        r = self.client.get('/reports/')
        self.assertNotEqual(r.status_code, 500)

    def test_revenue_report(self):
        r = self.client.get('/reports/revenue/')
        self.assertNotEqual(r.status_code, 500)

    def test_worktime_report(self):
        r = self.client.get('/reports/worktime/')
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 16: Other modules (1 test each)
# ==========================================================================

class OtherModulesSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_synesis(self):
        r = self.client.get('/synesis/')
        self.assertNotEqual(r.status_code, 500)

    def test_smart_import(self):
        r = self.client.get('/smart-import/')
        self.assertNotEqual(r.status_code, 500)

    def test_calculator(self):
        r = self.client.get('/calculator/')
        self.assertNotEqual(r.status_code, 500)

    def test_calculator_bom(self):
        r = self.client.get('/calculator/bom/')
        self.assertNotEqual(r.status_code, 500)

    def test_webshop(self):
        r = self.client.get('/webshop/')
        self.assertNotEqual(r.status_code, 500)

    def test_webshop_orders(self):
        r = self.client.get('/webshop/orders/')
        self.assertNotEqual(r.status_code, 500)

    def test_fitness(self):
        r = self.client.get('/fitness/')
        self.assertNotEqual(r.status_code, 500)

    def test_fitness_dashboard(self):
        r = self.client.get('/fitness/dashboard/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_insurance(self):
        r = self.client.get('/insurance/')
        self.assertNotEqual(r.status_code, 500)

    def test_interventions(self):
        r = self.client.get('/interventions/')
        self.assertNotEqual(r.status_code, 500)

    def test_tracking(self):
        r = self.client.get('/tracking/')
        self.assertNotEqual(r.status_code, 500)

    def test_assessment(self):
        r = self.client.get('/assessment/')
        self.assertNotEqual(r.status_code, 500)

    def test_burza(self):
        r = self.client.get('/burza/')
        self.assertNotEqual(r.status_code, 500)

    def test_marketplace(self):
        r = self.client.get('/marketplace/')
        self.assertNotEqual(r.status_code, 500)

    def test_marketplace_seller(self):
        r = self.client.get('/marketplace/seller/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_outreach(self):
        r = self.client.get('/outreach/')
        self.assertNotEqual(r.status_code, 500)

    def test_outreach_contacts(self):
        r = self.client.get('/outreach/contacts/')
        self.assertNotEqual(r.status_code, 500)

    def test_appointments(self):
        r = self.client.get('/appointments/')
        self.assertNotEqual(r.status_code, 500)

    def test_appointments_calendar(self):
        r = self.client.get('/appointments/calendar/')
        self.assertNotEqual(r.status_code, 500)

    def test_appointments_services(self):
        r = self.client.get('/appointments/service/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_payroll(self):
        r = self.client.get('/payroll/')
        self.assertNotEqual(r.status_code, 500)

    def test_work_orders(self):
        r = self.client.get('/work-orders/')
        self.assertNotEqual(r.status_code, 500)

    def test_work_orders_vehicles(self):
        r = self.client.get('/work-orders/vehicles/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_website_editor(self):
        r = self.client.get('/website/editor/')
        self.assertNotEqual(r.status_code, 500)

    def test_notifications(self):
        r = self.client.get('/notifications/')
        self.assertNotEqual(r.status_code, 500)

    def test_ai_assistant(self):
        r = self.client.get('/ai-assistant/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 17: Superadmin pages (4 tests)
# ==========================================================================

class SuperadminSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_superadmin_dashboard(self):
        r = self.client.get('/superadmin/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_superadmin_companies(self):
        r = self.client.get('/superadmin/companies/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_superadmin_registrations(self):
        r = self.client.get('/superadmin/registrations/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_control_tower(self):
        r = self.client.get('/superadmin/control-tower/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 18: Form submissions (POST) (6 tests)
# ==========================================================================

class FormSubmissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_eracun_settings_post(self):
        r = self.client.post('/eracun/settings/', {
            'is_active': 'on', 'use_test_env': 'on',
            'cert_oib': '12345678903',
            'oznaka_prostora': 'P1', 'oznaka_uredjaja': '1',
        }, follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_partner_create_post(self):
        r = self.client.post('/partners/new/', {
            'name': 'Novi Partner', 'oib': '22222222222',
            'partner_type': 'supplier',
        }, follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_inventory_item_create_post(self):
        r = self.client.post('/inventory/new/', {
            'name': 'Novi Artikl', 'sku': 'NEW-001',
            'unit': 'kom', 'unit_price': '25.00',
        }, follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_project_create_post(self):
        r = self.client.post('/projects/new/', {
            'name': 'Novi Projekt', 'code': 'NP-001',
            'status': 'planning',
        }, follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_eracun_send_post(self):
        er = self.data['eracun']
        r = self.client.post(f'/eracun/{er.pk}/send/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_worktime_add_post(self):
        r = self.client.post('/worktime/add/', {
            'project': self.data['project'].pk,
            'date': datetime.date.today().isoformat(),
            'duration': '8.00',
            'description': 'Test unos',
        }, follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 19: API endpoints (7 tests)
# ==========================================================================

class APIEndpointTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_invoice_api_profiles(self):
        r = self.client.get('/invoicing/api/profiles/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_invoice_api_tax_rates(self):
        r = self.client.get('/invoicing/api/tax-rates/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_eracun_api_list(self):
        config = self.data['eracun_config']
        r = self.client.get('/eracun/api/list/', HTTP_AUTHORIZATION=f'Bearer {config.api_key}')
        self.assertNotEqual(r.status_code, 500)

    def test_eracun_api_status(self):
        config = self.data['eracun_config']
        er = self.data['eracun']
        r = self.client.get(f'/eracun/api/status/{er.pk}/', HTTP_AUTHORIZATION=f'Bearer {config.api_key}')
        self.assertNotEqual(r.status_code, 500)

    def test_notification_api(self):
        r = self.client.get('/notifications/api/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_konto_chart_api(self):
        r = self.client.get('/konto/api/chart/', follow=True)
        self.assertNotEqual(r.status_code, 500)

    def test_pos_barcode_api(self):
        r = self.client.get('/pos/api/barcode/?code=1234567890', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 20: Access control (5 tests)
# ==========================================================================

class AccessControlTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_dashboard_requires_login(self):
        r = self.client.get('/')
        self.assertIn(r.status_code, [301, 302])

    def test_invoicing_requires_login(self):
        r = self.client.get('/invoicing/')
        self.assertIn(r.status_code, [301, 302])

    def test_eracun_requires_login(self):
        r = self.client.get('/eracun/')
        self.assertIn(r.status_code, [301, 302])

    def test_pos_requires_login(self):
        r = self.client.get('/pos/')
        self.assertIn(r.status_code, [301, 302])

    def test_superadmin_requires_login(self):
        r = self.client.get('/superadmin/')
        self.assertIn(r.status_code, [301, 302])

    def test_registration_public(self):
        r = self.client.get('/register/', follow=True)
        self.assertNotEqual(r.status_code, 500)


# ==========================================================================
# TEST 21: Propter SaaS Tests (4 tests)
# ==========================================================================

class PropterSmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DataFactory.create_all()
        # Create PropterTenant for test company
        from registration.models import PropterTenant
        cls.data['propter_tenant'] = PropterTenant.objects.create(
            company=cls.data['company'],
            tier='bookkeeper',
            operator_name='Test Knjigovodstvo',
            monthly_fee=Decimal('175.00'),
            max_companies=10,
            is_active=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_propter_dashboard(self):
        r = self.client.get('/register/propter/')
        self.assertNotEqual(r.status_code, 500)

    def test_propter_create_tenant_page(self):
        r = self.client.get('/register/propter/new/')
        self.assertNotEqual(r.status_code, 500)

    def test_propter_tenant_detail(self):
        t = self.data['propter_tenant']
        r = self.client.get(f'/register/propter/{t.pk}/')
        self.assertNotEqual(r.status_code, 500)

    def test_propter_tenant_model(self):
        t = self.data['propter_tenant']
        self.assertEqual(t.tier, 'bookkeeper')
        self.assertEqual(t.monthly_fee, Decimal('175.00'))
        self.assertEqual(t.max_companies, 10)
        self.assertTrue(t.is_active)
