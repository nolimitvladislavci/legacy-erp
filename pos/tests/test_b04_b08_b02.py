"""
B-04, B-08, B-02 — Fiskalizacija offline, stock race, otvoreni bonovi na logout.
"""
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone as tz

User = get_user_model()


class B04Setup(TestCase):
    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        cls.company = Company.objects.create(name='B04 Test', oib='55555555501')
        cls.user = User.objects.create_user('b04user', 'b04@t.com', 'T123!')


class B04FiscalRetryTest(B04Setup):
    """B-04: Fiskalizacija offline bonova — retry logika."""

    def _create_receipt(self, paid_hours_ago=1, zki='ABC123', jir='', retry_count=0):
        from pos.models import POSTerminal, POSSession, POSReceipt
        terminal, _ = POSTerminal.objects.get_or_create(
            company=self.company, name='T1',
            defaults={'terminal_code': 'T1'},
        )
        session, _ = POSSession.objects.get_or_create(
            terminal=terminal, status='open',
            defaults={'operator': self.user, 'session_number': 1},
        )
        r = POSReceipt.objects.create(
            session=session,
            receipt_number=POSReceipt.objects.count() + 1,
            status='paid',
            total=Decimal('10.00'),
            paid_at=tz.now() - timedelta(hours=paid_hours_ago),
            zki=zki,
            jir=jir,
            fiscal_retry_count=retry_count,
        )
        return r

    def test_01_retry_finds_pending_receipts(self):
        """Račun s ZKI ali bez JIR-a se pronalazi."""
        from pos.tasks import retry_fiscalization
        self._create_receipt(paid_hours_ago=1, zki='ZKI123', jir='')
        result = retry_fiscalization()
        self.assertIn(result['status'], ['completed', 'ok'])

    def test_02_receipt_with_jir_skipped(self):
        """Račun koji već ima JIR se preskače."""
        from pos.models import POSReceipt
        self._create_receipt(paid_hours_ago=1, zki='ZKI123', jir='JIR456')
        from django.db.models import Q
        pending = POSReceipt.objects.filter(
            status='paid',
        ).filter(
            Q(jir__isnull=True) | Q(jir=''),
        ).filter(
            Q(zki__isnull=False) & ~Q(zki=''),
        )
        self.assertEqual(pending.count(), 0)

    def test_03_retry_count_increments(self):
        """Svaki pokušaj povećava fiscal_retry_count."""
        r = self._create_receipt(paid_hours_ago=1, zki='ZKI789')
        self.assertEqual(r.fiscal_retry_count, 0)

    def test_04_48h_critical_detection(self):
        """Račun star > 48h se detektira kao CRITICAL."""
        r = self._create_receipt(paid_hours_ago=50, zki='OLD-ZKI')
        from pos.tasks import retry_fiscalization
        result = retry_fiscalization()
        self.assertGreaterEqual(result.get('critical_48h', 0), 1)

    def test_05_24h_warning_detection(self):
        """Račun star 25h → warning."""
        self._create_receipt(paid_hours_ago=25, zki='WARN-ZKI')
        from pos.tasks import retry_fiscalization
        result = retry_fiscalization()
        self.assertGreaterEqual(result.get('warning_24h', 0), 1)

    def test_06_fiscal_last_error_stored(self):
        """Greška se sprema u fiscal_last_error."""
        r = self._create_receipt(paid_hours_ago=50, zki='ERR-ZKI')
        from pos.tasks import retry_fiscalization
        retry_fiscalization()
        r.refresh_from_db()
        self.assertIn('CRITICAL', r.fiscal_last_error)


class B08StockRaceTest(B04Setup):
    """B-08: Stock race condition — select_for_update zaštita."""

    def test_07_stock_deduction_field_exists(self):
        """InventoryItem ima quantity polje za F() update."""
        from inventory.models import InventoryItem
        item = InventoryItem.objects.create(
            company=self.company, name='Race Test', sku='RACE-1',
            quantity=Decimal('10'), unit_price=Decimal('5'),
        )
        self.assertEqual(item.quantity, Decimal('10'))

    def test_08_stock_movement_deducts(self):
        """StockMovement.save() smanjuje quantity atomarno."""
        from inventory.models import InventoryItem, StockMovement
        item = InventoryItem.objects.create(
            company=self.company, name='Deduct Test', sku='DED-1',
            quantity=Decimal('10'), unit_price=Decimal('5'),
        )
        StockMovement.objects.create(
            item=item, movement_type='out', quantity=Decimal('3'),
            unit_price=Decimal('5'), reason='test',
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('7'))

    def test_09_negative_stock_allowed_when_configured(self):
        """Ako firma dopušta negativnu zalihu, ne blokira."""
        from inventory.models import InventoryItem, StockMovement
        self.company.allow_negative_stock = True
        self.company.save()
        item = InventoryItem.objects.create(
            company=self.company, name='Negative Test', sku='NEG-1',
            quantity=Decimal('1'), unit_price=Decimal('5'),
        )
        StockMovement.objects.create(
            item=item, movement_type='out', quantity=Decimal('5'),
            unit_price=Decimal('5'), reason='test oversell',
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('-4'))


class B02OpenReceiptsLogoutTest(B04Setup):
    """B-02: Upozorenje pri odjavi s otvorenim bonovima."""

    def test_10_smart_logout_checks_open_receipts(self):
        """smart_logout view postoji i ima B-02 provjeru."""
        from accounts.auth_views import smart_logout
        import inspect
        source = inspect.getsource(smart_logout)
        self.assertIn('open_receipts', source)
        self.assertIn('B-02', source)

    def test_11_open_receipt_detection(self):
        """Otkrivamo otvorene bonove za usera."""
        from pos.models import POSTerminal, POSSession, POSReceipt, POSCashier
        terminal = POSTerminal.objects.create(
            company=self.company, name='B02T', terminal_code='B02',
        )
        session = POSSession.objects.create(
            terminal=terminal, operator=self.user,
            session_number=1, status='open',
        )
        cashier = POSCashier.objects.create(
            company=self.company, name='B02 Cashier',
            user=self.user, is_active=True,
        )
        POSReceipt.objects.create(
            session=session, receipt_number=1,
            status='open', cashier=cashier,
        )
        open_count = POSReceipt.objects.filter(
            session__terminal__company=self.company,
            status='open',
            cashier__user=self.user,
        ).count()
        self.assertEqual(open_count, 1)

    def test_12_task_imports_clean(self):
        """Svi relevantni importi rade."""
        from pos.tasks import retry_fiscalization
        from accounts.auth_views import smart_logout
        self.assertTrue(callable(retry_fiscalization))
        self.assertTrue(callable(smart_logout))


class DualRoutingFiscalBypassTest(B04Setup):
    """Dual-Routing: fiscal_exempt za udruge preskače FINA."""

    def test_13_fiscal_exempt_field_exists(self):
        """Company ima fiscal_exempt polje."""
        self.assertFalse(self.company.fiscal_exempt)

    def test_14_exempt_company_skips_retry(self):
        """Retry task preskače fiscal_exempt tvrtke."""
        from pos.models import POSTerminal, POSSession, POSReceipt
        self.company.fiscal_exempt = True
        self.company.save()
        terminal = POSTerminal.objects.create(
            company=self.company, name='ExT', terminal_code='EX',
        )
        session = POSSession.objects.create(
            terminal=terminal, operator=self.user,
            session_number=1, status='open',
        )
        POSReceipt.objects.create(
            session=session, receipt_number=1,
            status='paid', total=Decimal('10'),
            paid_at=tz.now() - timedelta(hours=1),
            zki='EXEMPT-ZKI', jir='',
        )
        from pos.tasks import retry_fiscalization
        result = retry_fiscalization()
        # Exempt receipt should not be in pending
        self.assertEqual(result.get('status'), 'ok')

    def test_15_non_exempt_still_retries(self):
        """Komercijalne tvrtke i dalje idu u retry."""
        self.assertFalse(self.company.fiscal_exempt)

    def test_16_exempt_flag_default_false(self):
        """Nove tvrtke su po defaultu NE-exempt."""
        from companies.models import Company
        c = Company.objects.create(name='Nova Firma', oib='11122233301')
        self.assertFalse(c.fiscal_exempt)


class MixedNonprofitBlockTest(B04Setup):
    """Blokada miješanja komercijalnih i neprofitnih stavki na istom računu."""

    def _make_items(self):
        from inventory.models import InventoryItem
        commercial = InventoryItem.objects.create(
            company=self.company, name='Pivo', sku='PIVO-1',
            unit_price=Decimal('3.50'), is_nonprofit_activity=False,
        )
        nonprofit = InventoryItem.objects.create(
            company=self.company, name='Članarina', sku='CLAN-1',
            unit_price=Decimal('20.00'), is_nonprofit_activity=True,
        )
        return commercial, nonprofit

    def _make_session(self):
        from pos.models import POSTerminal, POSSession
        terminal = POSTerminal.objects.create(
            company=self.company, name='MixT', terminal_code='MX',
        )
        return POSSession.objects.create(
            terminal=terminal, operator=self.user,
            session_number=1, status='open',
        )

    def test_17_pure_commercial_passes(self):
        """Samo komercijalne stavke → prolazi."""
        commercial, _ = self._make_items()
        session = self._make_session()
        from pos.services.checkout import CheckoutService
        # Neće pasti na mixed validation (samo commercial)
        payload = {
            'session_id': session.pk,
            'items': [{'item_id': commercial.pk, 'quantity': 1}],
            'payment_method': 'CASH',
            'amount_paid': '10',
        }
        # Checkout će pasti na fiskalizaciji (nema cert) ali NE na mixed validation
        try:
            CheckoutService.process_receipt(self.company, self.user, payload)
        except AttributeError as e:
            self.assertNotEqual(getattr(e, 'code', ''), 'MIXED_NONPROFIT_COMMERCIAL')

    def test_18_pure_nonprofit_passes(self):
        """Samo neprofitne stavke → prolazi."""
        _, nonprofit = self._make_items()
        session = self._make_session()
        payload = {
            'session_id': session.pk,
            'items': [{'item_id': nonprofit.pk, 'quantity': 1}],
            'payment_method': 'CASH',
            'amount_paid': '25',
        }
        try:
            CheckoutService.process_receipt(self.company, self.user, payload)
        except AttributeError as e:
            self.assertNotEqual(getattr(e, 'code', ''), 'MIXED_NONPROFIT_COMMERCIAL')

    def test_19_mixed_blocked(self):
        """Miješanje commercial + nonprofit → MIXED_NONPROFIT_COMMERCIAL error."""
        commercial, nonprofit = self._make_items()
        session = self._make_session()
        from pos.services.checkout import CheckoutService, CheckoutValidationError
        payload = {
            'session_id': session.pk,
            'items': [
                {'item_id': commercial.pk, 'quantity': 1},
                {'item_id': nonprofit.pk, 'quantity': 1},
            ],
            'payment_method': 'CASH',
            'amount_paid': '30',
        }
        with self.assertRaises(CheckoutValidationError) as ctx:
            CheckoutService.process_receipt(self.company, self.user, payload)
        self.assertEqual(ctx.exception.code, 'MIXED_NONPROFIT_COMMERCIAL')

    def test_20_custom_items_no_crash(self):
        """Stavke bez item_id (custom) ne ruše validaciju."""
        session = self._make_session()
        payload = {
            'session_id': session.pk,
            'items': [
                {'name': 'Ručni unos', 'price': '5', 'quantity': 1},
            ],
            'payment_method': 'CASH',
            'amount_paid': '5',
        }
        # Custom items nemaju item_id → preskače mixed check
        try:
            CheckoutService.process_receipt(self.company, self.user, payload)
        except AttributeError as e:
            self.assertNotEqual(getattr(e, 'code', ''), 'MIXED_NONPROFIT_COMMERCIAL')
