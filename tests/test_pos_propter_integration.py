"""
Integracijski testovi: POS matematika + Propter agregacija.

Pokretanje:
    cd /var/www/fina-connect
    python manage.py test tests.test_pos_propter_integration -v2
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from companies.models import Company
from eracun.models import ERacun, ERacunItem
from pos.models import POSReceipt, POSSession, POSTerminal
from pos.services import add_receipt_item, create_receipt, open_session, process_payment
from propter.models import BillingPeriod, Otpremnica, OtpremnicaItem
from propter.services.aggregate import aggregate_to_eracun, close_period


class POSMathAndPaymentTest(TestCase):
    """Test 1: POS racun s vise stavki, popustima i razlicitim PDV stopama."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Firma d.o.o.", oib="11111111111")
        cls.user = User.objects.create_user(username="test_cashier", password="pass123")
        cls.terminal = POSTerminal.objects.create(
            company=cls.company,
            name="Kasa Test",
            terminal_code="TST01",
            pos_type="restaurant",
        )

    def test_pos_receipt_math_with_discount_and_mixed_tax(self):
        """
        Scenario: 2 Piva (2x3.00, PDV 25%, popust 10%) + 1 Pizza (10.00, PDV 5%, bez popusta).

        Pivo:
          Net = 2 * 3.00 * (1 - 0.10) = 5.40
          Tax = 5.40 * 0.25 = 1.35

        Pizza:
          Net = 1 * 10.00 = 10.00
          Tax = 10.00 * 0.05 = 0.50

        Subtotal = 15.40, Tax = 1.85, Total = 17.25
        """
        session = open_session(terminal=self.terminal, user=self.user, opening_cash=Decimal("100.00"))
        self.assertEqual(session.status, POSSession.Status.OPEN)

        receipt = create_receipt(session=session, table_number="Stol 5", note="Test")

        # Pivo s popustom
        add_receipt_item(
            receipt=receipt,
            inventory_item_id=None,
            description="Pivo 0.5L",
            quantity=Decimal("2"),
            unit_price=Decimal("3.00"),
            tax_rate=Decimal("25"),
            discount_percent=Decimal("10"),
        )

        # Pizza bez popusta
        add_receipt_item(
            receipt=receipt,
            inventory_item_id=None,
            description="Pizza Margarita",
            quantity=Decimal("1"),
            unit_price=Decimal("10.00"),
            tax_rate=Decimal("5"),
        )

        receipt.refresh_from_db()

        self.assertEqual(receipt.subtotal, Decimal("15.40"))
        self.assertEqual(receipt.tax_amount, Decimal("1.85"))
        self.assertEqual(receipt.total, Decimal("17.25"))

    def test_pos_payment_and_change(self):
        """Naplata gotovinom 20 EUR za racun od 17.25 EUR -> kusur 2.75."""
        session = open_session(terminal=self.terminal, user=self.user, opening_cash=Decimal("50.00"))
        receipt = create_receipt(session=session)

        add_receipt_item(
            receipt=receipt,
            inventory_item_id=None,
            description="Pivo",
            quantity=Decimal("2"),
            unit_price=Decimal("3.00"),
            tax_rate=Decimal("25"),
            discount_percent=Decimal("10"),
        )
        add_receipt_item(
            receipt=receipt,
            inventory_item_id=None,
            description="Pizza",
            quantity=Decimal("1"),
            unit_price=Decimal("10.00"),
            tax_rate=Decimal("5"),
        )

        receipt.refresh_from_db()
        result = process_payment(receipt=receipt, method="CASH", amount_paid=Decimal("20.00"), user=self.user)

        receipt.refresh_from_db()
        self.assertEqual(receipt.status, POSReceipt.Status.PAID)
        self.assertEqual(result["change"], Decimal("2.75"))
        self.assertEqual(result["total"], Decimal("17.25"))

    def test_pos_zero_discount(self):
        """Racun bez popusta: 3 artikla po 5.00 EUR, PDV 25%."""
        session = open_session(terminal=self.terminal, user=self.user)
        receipt = create_receipt(session=session)

        add_receipt_item(
            receipt=receipt,
            inventory_item_id=None,
            description="Artikl A",
            quantity=Decimal("3"),
            unit_price=Decimal("5.00"),
            tax_rate=Decimal("25"),
        )

        receipt.refresh_from_db()
        # Net = 15.00, Tax = 3.75, Total = 18.75
        self.assertEqual(receipt.subtotal, Decimal("15.00"))
        self.assertEqual(receipt.tax_amount, Decimal("3.75"))
        self.assertEqual(receipt.total, Decimal("18.75"))

    def test_pos_exact_payment_no_change(self):
        """Placanje tocnog iznosa -> kusur 0."""
        session = open_session(terminal=self.terminal, user=self.user)
        receipt = create_receipt(session=session)

        add_receipt_item(
            receipt=receipt,
            inventory_item_id=None,
            description="Kava",
            quantity=Decimal("1"),
            unit_price=Decimal("2.00"),
            tax_rate=Decimal("25"),
        )

        receipt.refresh_from_db()
        total = receipt.total  # 2.50
        result = process_payment(receipt=receipt, method="CASH", amount_paid=total, user=self.user)
        self.assertEqual(result["change"], Decimal("0"))


class PropterAggregationTest(TestCase):
    """Test 2: Propter pipeline — otpremnice -> close_period -> aggregate_to_eracun."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Propter Test d.o.o.", oib="22222222222")
        cls.user = User.objects.create_user(username="test_propter", password="pass123")

    def test_billing_period_creation(self):
        """get_or_create_current vraca period za tekuci mjesec."""
        period = BillingPeriod.get_or_create_current(self.company)
        self.assertEqual(period.status, BillingPeriod.Status.OPEN)
        self.assertEqual(period.company, self.company)

    def test_otpremnica_auto_assigns_period(self):
        """Otpremnica.save() automatski dodjeljuje billing_period."""
        otp = Otpremnica.objects.create(
            company=self.company,
            issue_date="2026-03-10",
            recipient_name="Test Kupac",
            recipient_oib="33333333333",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("25.00"),
            total=Decimal("125.00"),
            status=Otpremnica.Status.ISSUED,
        )
        self.assertIsNotNone(otp.billing_period)
        self.assertEqual(otp.billing_period.company, self.company)

    def test_close_period_calculates_totals(self):
        """close_period zbraja iznose otpremnica i postavlja CLOSED."""
        period = BillingPeriod.get_or_create_current(self.company)

        Otpremnica.objects.create(
            company=self.company,
            billing_period=period,
            issue_date="2026-03-01",
            recipient_name="Kupac A",
            recipient_oib="44444444444",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("25.00"),
            total=Decimal("125.00"),
            status=Otpremnica.Status.ISSUED,
        )
        Otpremnica.objects.create(
            company=self.company,
            billing_period=period,
            issue_date="2026-03-15",
            recipient_name="Kupac A",
            recipient_oib="44444444444",
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("2.50"),
            total=Decimal("52.50"),
            status=Otpremnica.Status.ISSUED,
        )

        close_period(period, self.user)
        period.refresh_from_db()

        self.assertEqual(period.status, BillingPeriod.Status.CLOSED)
        self.assertEqual(period.otpremnica_count, 2)
        self.assertEqual(period.total_net, Decimal("150.00"))
        self.assertEqual(period.total_tax, Decimal("27.50"))
        self.assertEqual(period.total_with_tax, Decimal("177.50"))

    def test_aggregate_to_eracun_creates_invoice(self):
        """aggregate_to_eracun kreira ERacun sa stavkama iz otpremnica."""
        period = BillingPeriod.get_or_create_current(self.company)

        otp1 = Otpremnica.objects.create(
            company=self.company,
            billing_period=period,
            issue_date="2026-03-01",
            recipient_name="Restoran X",
            recipient_oib="55555555555",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("25.00"),
            total=Decimal("125.00"),
            status=Otpremnica.Status.ISSUED,
        )
        OtpremnicaItem.objects.create(
            otpremnica=otp1,
            description="Odojak 10kg",
            quantity=Decimal("10"),
            unit_price=Decimal("10.00"),
            tax_rate=Decimal("25"),
            line_total=Decimal("100.00"),
        )

        otp2 = Otpremnica.objects.create(
            company=self.company,
            billing_period=period,
            issue_date="2026-03-15",
            recipient_name="Restoran X",
            recipient_oib="55555555555",
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("2.50"),
            total=Decimal("52.50"),
            status=Otpremnica.Status.ISSUED,
        )
        OtpremnicaItem.objects.create(
            otpremnica=otp2,
            description="Kruh 50 kom",
            quantity=Decimal("50"),
            unit_price=Decimal("1.00"),
            tax_rate=Decimal("5"),
            line_total=Decimal("50.00"),
        )

        # Zatvori period
        close_period(period, self.user)

        # Agregiraj u e-Racun
        eracun = aggregate_to_eracun(period, self.user)

        self.assertIsNotNone(eracun)
        self.assertIsInstance(eracun, ERacun)

        # Iznosi
        self.assertEqual(eracun.subtotal, Decimal("150.00"))
        self.assertEqual(eracun.tax_amount, Decimal("27.50"))
        self.assertEqual(eracun.total, Decimal("177.50"))

        # Stavke
        items = ERacunItem.objects.filter(eracun=eracun)
        self.assertEqual(items.count(), 2)

        descriptions = [i.description for i in items]
        self.assertTrue(any("Odojak 10kg" in d for d in descriptions))
        self.assertTrue(any("Kruh 50 kom" in d for d in descriptions))

        # Period status
        period.refresh_from_db()
        self.assertEqual(period.status, BillingPeriod.Status.INVOICED)
        self.assertNotEqual(period.zbirni_eracun_id, "")

        # Otpremnice status
        otp1.refresh_from_db()
        otp2.refresh_from_db()
        self.assertEqual(otp1.status, Otpremnica.Status.AGGREGATED)
        self.assertEqual(otp2.status, Otpremnica.Status.AGGREGATED)

    def test_aggregate_idempotent(self):
        """Drugi poziv aggregate_to_eracun ne kreira duplikat."""
        period = BillingPeriod.get_or_create_current(self.company)

        otp = Otpremnica.objects.create(
            company=self.company,
            billing_period=period,
            issue_date="2026-03-05",
            recipient_name="Kupac Z",
            recipient_oib="66666666666",
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("50.00"),
            total=Decimal("250.00"),
            status=Otpremnica.Status.ISSUED,
        )
        OtpremnicaItem.objects.create(
            otpremnica=otp,
            description="Vino 20L",
            quantity=Decimal("20"),
            unit_price=Decimal("10.00"),
            tax_rate=Decimal("25"),
            line_total=Decimal("200.00"),
        )

        close_period(period, self.user)
        eracun1 = aggregate_to_eracun(period, self.user)
        eracun2 = aggregate_to_eracun(period, self.user)

        self.assertEqual(eracun1.pk, eracun2.pk)
        self.assertEqual(ERacun.objects.filter(invoice_number__startswith="ZBIRNI-").count(), 1)
