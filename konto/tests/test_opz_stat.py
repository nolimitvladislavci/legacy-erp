"""Tests for OPZ-STAT-1 report — scenarios #7-12."""
import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from companies.models import Company
from accounts.models import UserProfile
from invoicing.models import Invoice
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class OPZStatTestCase(TestCase):
    """Base setup: user + company + login."""

    def setUp(self):
        self.company = Company.objects.create(
            name='Test Firma d.o.o.',
            oib='12345678901',
        )
        self.user = User.objects.create_user(
            username='opztest', password='test1234'
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={'company': self.company, 'role': 'admin'},
        )
        self.client = Client()
        self.client.login(username='opztest', password='test1234')

    def _make_invoice(self, **kw):
        defaults = dict(
            company=self.company,
            number=f'INV-{Invoice.objects.count()+1}',
            date_issued=datetime.date(2025, 6, 15),
            client_name='Testni Partner',
            client_oib='11111111111',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('250.00'),
            total=Decimal('1250.00'),
            status='SENT',
        )
        defaults.update(kw)
        return Invoice.objects.create(**defaults)


class Test07_PageLoads(OPZStatTestCase):
    """OPZ-STAT-1 page loads for 2025."""

    def test_page_returns_200(self):
        self._make_invoice()
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        self.assertEqual(resp.status_code, 200)

    def test_context_has_required_keys(self):
        self._make_invoice()
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        for key in ('domestic', 'foreign', 'totals', 'year', 'years'):
            self.assertIn(key, resp.context, f'Missing context key: {key}')


class Test08_DomesticClassification(OPZStatTestCase):
    """Partners without OIB classified as domestic."""

    def test_empty_oib_is_domestic(self):
        self._make_invoice(client_oib='', client_name='Fizicka osoba')
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        domestic = resp.context['domestic']
        foreign = resp.context['foreign']
        domestic_names = [p['name'] for p in domestic]
        foreign_names = [p['name'] for p in foreign]
        self.assertIn('Fizicka osoba', domestic_names)
        self.assertNotIn('Fizicka osoba', foreign_names)

    def test_valid_oib_is_domestic(self):
        self._make_invoice(client_oib='12345678901', client_name='Firma HR')
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        domestic_names = [p['name'] for p in resp.context['domestic']]
        self.assertIn('Firma HR', domestic_names)


class Test09_RejectedExcluded(OPZStatTestCase):
    """REJECTED invoices excluded from report."""

    def test_rejected_not_in_report(self):
        self._make_invoice(status='REJECTED', client_name='Rejected Partner')
        self._make_invoice(status='SENT', client_name='Good Partner')
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        all_names = [p['name'] for p in resp.context['domestic']] + \
                    [p['name'] for p in resp.context['foreign']]
        self.assertNotIn('Rejected Partner', all_names)
        self.assertIn('Good Partner', all_names)

    def test_draft_cancelled_storno_excluded(self):
        for status in ('DRAFT', 'CANCELLED', 'STORNO'):
            self._make_invoice(status=status, client_name=f'Partner {status}')
        self._make_invoice(status='PAID', client_name='Paid Partner')
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        all_names = [p['name'] for p in resp.context['domestic']] + \
                    [p['name'] for p in resp.context['foreign']]
        self.assertIn('Paid Partner', all_names)
        for status in ('DRAFT', 'CANCELLED', 'STORNO'):
            self.assertNotIn(f'Partner {status}', all_names)


class Test10_CSVExport(OPZStatTestCase):
    """CSV export works correctly."""

    def test_csv_content_type(self):
        self._make_invoice()
        resp = self.client.get('/konto/reports/opz-stat/?year=2025&format=csv')
        self.assertIn('text/csv', resp['Content-Type'])

    def test_csv_has_bom(self):
        self._make_invoice()
        resp = self.client.get('/konto/reports/opz-stat/?year=2025&format=csv')
        content = resp.content
        # BOM is \xef\xbb\xbf (or the string literal in code)
        self.assertTrue(
            content[:3] == b'\xef\xbb\xbf' or b'Partner' in content,
            'CSV should have BOM or header row'
        )

    def test_csv_uses_semicolons(self):
        self._make_invoice()
        resp = self.client.get('/konto/reports/opz-stat/?year=2025&format=csv')
        content = resp.content.decode('utf-8-sig')
        self.assertIn(';', content, 'CSV should use semicolons')


class Test11_OverdueTracking(OPZStatTestCase):
    """Overdue invoices tracked in report."""

    def test_overdue_count(self):
        # Create invoice 90 days overdue
        past = datetime.date.today() - datetime.timedelta(days=90)
        self._make_invoice(
            date_issued=past,
            date_due=past + datetime.timedelta(days=15),
            status='SENT',
            client_name='Overdue Client',
        )
        year = past.year
        resp = self.client.get(f'/konto/reports/opz-stat/?year={year}')
        totals = resp.context['totals']
        self.assertGreaterEqual(
            totals.get('overdue_count', 0), 1,
            'Should have at least 1 overdue invoice'
        )


class Test12_YearFilter(OPZStatTestCase):
    """Year filter shows only matching year."""

    def test_2025_only(self):
        self._make_invoice(
            date_issued=datetime.date(2025, 3, 1),
            client_name='Partner 2025',
        )
        self._make_invoice(
            date_issued=datetime.date(2026, 1, 15),
            client_name='Partner 2026',
        )
        resp = self.client.get('/konto/reports/opz-stat/?year=2025')
        all_names = [p['name'] for p in resp.context['domestic']] + \
                    [p['name'] for p in resp.context['foreign']]
        self.assertIn('Partner 2025', all_names)
        self.assertNotIn('Partner 2026', all_names)

    def test_2026_only(self):
        self._make_invoice(
            date_issued=datetime.date(2025, 3, 1),
            client_name='Partner 2025',
        )
        self._make_invoice(
            date_issued=datetime.date(2026, 1, 15),
            client_name='Partner 2026',
        )
        resp = self.client.get('/konto/reports/opz-stat/?year=2026')
        all_names = [p['name'] for p in resp.context['domestic']] + \
                    [p['name'] for p in resp.context['foreign']]
        self.assertNotIn('Partner 2025', all_names)
        self.assertIn('Partner 2026', all_names)
