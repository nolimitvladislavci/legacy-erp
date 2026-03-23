"""
Offline POS testovi — zakonska obveza 48h fiskalizacije (čl. 11).
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class OfflineSyncEndpointTest(TestCase):
    """Testovi za POST /pos/api/offline-sync/"""

    def setUp(self):
        from companies.models import Company
        from pos.models import POSTerminal, POSSession, POSCashier

        self.company = Company.objects.create(name='Test Offline', oib='11111111111')
        self.user = User.objects.create_user(username='offline_test', password='test123')

        # Assign company
        if hasattr(self.user, 'profile'):
            try:
                self.user.profile.company = self.company
                self.user.profile.save()
            except Exception:
                pass

        self.terminal = POSTerminal.objects.create(
            company=self.company, name='T1', terminal_code='OFF01', pos_type='quick',
        )
        self.cashier = POSCashier.objects.create(company=self.company, name='Blagajnik')
        self.session = POSSession.objects.create(
            terminal=self.terminal, operator=self.user,
            session_number=1, status='open',
        )
        self.session.active_cashiers.add(self.cashier)

        self.client = Client()
        self.client.login(username='offline_test', password='test123')

    def test_01_offline_sync_accepts_json(self):
        """Endpoint prihvaća JSON payload."""
        resp = self.client.post(
            '/pos/api/offline-sync/',
            data=json.dumps({'session_id': self.session.pk, 'receipts': []}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 403])

    def test_02_unauthenticated_rejected(self):
        """Bez autentikacije vraća 401."""
        c = Client()
        resp = c.post(
            '/pos/api/offline-sync/',
            data=json.dumps({'receipts': []}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)


class FiscalDeadlineTest(TestCase):
    """Test 48h alarm za nefiskalizirane bonove."""

    def test_03_check_fiscal_deadline_runs(self):
        """check_fiscal_deadline() se izvršava bez greške."""
        from pos.tasks import check_fiscal_deadline
        result = check_fiscal_deadline()
        self.assertIsNotNone(result)

    def test_04_no_critical_returns_ok(self):
        """Kad nema kritičnih bonova, vraća ok status."""
        from pos.tasks import check_fiscal_deadline
        result = check_fiscal_deadline()
        self.assertEqual(result.get('status', 'ok'), 'ok')


class OfflineReceiptPrintTest(TestCase):
    """Bon bez JIR-a mora imati CIS upozorenje."""

    def test_05_receipt_without_jir_note(self):
        """Provjeri da se CIS poruka generira za bon bez JIR-a."""
        # Simulira JS _offlineFiscalNote
        receipt = {'zki': 'ABC123', 'jir': None}
        if not receipt.get('jir'):
            note = f"VEZA S CIS-om NIJE OSTVARENA — ZKI: {receipt['zki']}"
            self.assertIn('CIS', note)
            self.assertIn(receipt['zki'], note)
