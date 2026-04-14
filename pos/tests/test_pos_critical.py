"""
pos/tests/test_pos_critical.py
Critical path: POS bon kreiranje, status, fiskalni podaci i company izolacija.

Validirani OIBi koriste ISO 7064 Luhn-10 checksum.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounts.models import UserProfile
from companies.models import Company
from pos.models import POSReceipt, POSSession, POSTerminal

User = get_user_model()

# Validirani OIB-ovi (ISO 7064 checksum — provjera: validate_oib_hr)
VALID_OIB_1 = "98765432106"
VALID_OIB_2 = "11111111119"


class POSReceiptCriticalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="postestcritical",
            password="Test1234!",
            email="postestcritical@test.com",
        )
        self.company = Company.objects.create(
            name="POS Critical Test d.o.o.",
            oib=VALID_OIB_1,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.company = self.company
        profile.save()

        self.terminal = POSTerminal.objects.create(
            company=self.company,
            name="Kritična Kasa",
            terminal_code="KS-CRIT-001",
            pos_type="retail",
        )
        self.session = POSSession.objects.create(
            terminal=self.terminal,
            operator=self.user,
            session_number=1,
            status="open",
        )
        self._receipt_counter = 0

    def _make_receipt(self, session=None, **kwargs):
        self._receipt_counter += 1
        defaults = {
            "session": session or self.session,
            "receipt_number": self._receipt_counter,
            "total": Decimal("50.00"),
            "subtotal": Decimal("40.00"),
            "tax_amount": Decimal("10.00"),
        }
        defaults.update(kwargs)
        return POSReceipt.objects.create(**defaults)

    # ── Status tests ────────────────────────────────────────────

    def test_pos_receipt_default_status_open(self):
        """Novi POSReceipt → status OPEN"""
        receipt = self._make_receipt()
        self.assertEqual(receipt.status, POSReceipt.Status.OPEN)
        self.assertEqual(receipt.status, "open")

    def test_pos_receipt_status_paid(self):
        """POSReceipt OPEN → PAID"""
        receipt = self._make_receipt()
        receipt.status = POSReceipt.Status.PAID
        receipt.save(update_fields=["status"])
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "paid")

    def test_pos_receipt_status_cancelled(self):
        """POSReceipt može biti storniran (CANCELLED)"""
        receipt = self._make_receipt()
        receipt.status = POSReceipt.Status.CANCELLED
        receipt.save(update_fields=["status"])
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "cancelled")

    # ── Fiskalni podaci ─────────────────────────────────────────

    def test_pos_receipt_has_uuid(self):
        """POSReceipt ima UUID (identifikator za fiskalizaciju)"""
        receipt = self._make_receipt()
        self.assertIsNotNone(receipt.uuid)

    def test_pos_receipt_invoice_field_exists(self):
        """POSReceipt ima invoice FK za ZKI/JIR (NULL dok se ne fiskalizira)"""
        receipt = self._make_receipt()
        self.assertTrue(hasattr(receipt, "invoice"))
        self.assertIsNone(receipt.invoice)

    def test_pos_receipt_mock_fiscal_zki_jir(self):
        """Mocked fiskalizacija: Invoice sa ZKI/JIR se veže na receipt"""
        from django.utils import timezone

        from invoicing.models import Invoice

        inv = Invoice.objects.create(
            number="POS-MOCK-FISCAL-001",
            client_name="Mock Kupac",
            date_issued=timezone.now(),
            status="FISCALIZED",
            total=Decimal("50.00"),
            subtotal=Decimal("40.00"),
            tax_amount=Decimal("10.00"),
            zki="abc123def456abc123def456abc12300",
            jir="11111111-1111-1111-1111-111111111111",
            is_fiscalized=True,
        )
        receipt = self._make_receipt()
        receipt.invoice = inv
        receipt.save(update_fields=["invoice"])
        receipt.refresh_from_db()
        self.assertIsNotNone(receipt.invoice)
        self.assertEqual(receipt.invoice.zki, "abc123def456abc123def456abc12300")
        self.assertTrue(receipt.invoice.is_fiscalized)

    # ── Company izolacija ───────────────────────────────────────

    def test_pos_receipt_belongs_to_company(self):
        """POSReceipt pripada tvrtki kroz session → terminal → company"""
        receipt = self._make_receipt()
        self.assertEqual(receipt.session.terminal.company, self.company)

    def test_pos_receipt_company_switch_isolation(self):
        """Receipt iz sesije 2 pripada tvrtki 2, ne tvrtki 1"""
        company2 = Company.objects.create(
            name="POS Firma 2 d.o.o.",
            oib=VALID_OIB_2,
        )
        terminal2 = POSTerminal.objects.create(
            company=company2,
            name="Kasa Firma 2",
            terminal_code="KS-CRIT-002",
            pos_type="retail",
        )
        session2 = POSSession.objects.create(
            terminal=terminal2,
            operator=self.user,
            session_number=1,
            status="open",
        )
        receipt2 = self._make_receipt(session=session2)
        self.assertEqual(receipt2.session.terminal.company, company2)
        self.assertNotEqual(receipt2.session.terminal.company, self.company)
