
import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from accounts.models import UserProfile
from companies.models import Company
from documents.models import (
    Otpremnica, OtpremnicaItem,
    Primka, PrimkaItem,
    OtkupniBlok, OtkupniBlokItem,
    CMR, CMRItem,
)

User = get_user_model()


def _company(name, oib):
    return Company.objects.create(
        name=name, oib=oib, address="Test", city="Zagreb",
        country="HR", currency="EUR", is_platform_owner=True,
    )

def _user(username, company):
    u = User.objects.create_user(username=username, password="pass123")
    p, _ = UserProfile.objects.get_or_create(user=u)
    p.company = company; p.save()
    return u


class OtpremnicaModelTest(TestCase):
    def setUp(self):
        self.company = _company("OPG Otpr", "50000000001")
        self.user = _user("otpr_user", self.company)
        self.doc = Otpremnica.objects.create(
            company=self.company, doc_number="OTP-2026-0001",
            date_issued=datetime.date.today(), created_by=self.user,
        )

    def test_default_status(self):
        self.assertEqual(self.doc.status, "draft")

    def test_confirm(self):
        self.doc.confirm()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, "confirmed")
        self.assertIsNotNone(self.doc.date_confirmed)

    def test_cancel(self):
        self.doc.cancel()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, "cancelled")

    def test_item_line_total(self):
        item = OtpremnicaItem.objects.create(
            document=self.doc, product_name="Rajcica",
            quantity=Decimal("10"), unit="kg",
            unit_price=Decimal("3.50"), vat_rate=Decimal("5"),
        )
        self.assertAlmostEqual(item.line_total, 35.0)
        self.assertAlmostEqual(item.vat_amount, 1.75)

    def test_item_with_discount(self):
        item = OtpremnicaItem.objects.create(
            document=self.doc, product_name="Paprika",
            quantity=Decimal("20"), unit="kg",
            unit_price=Decimal("2.00"), vat_rate=Decimal("5"),
            discount_pct=Decimal("10"),
        )
        self.assertAlmostEqual(item.line_total, 36.0)

    def test_doc_total(self):
        OtpremnicaItem.objects.create(
            document=self.doc, product_name="A",
            quantity=Decimal("5"), unit="kg",
            unit_price=Decimal("4.00"), vat_rate=Decimal("5"),
        )
        OtpremnicaItem.objects.create(
            document=self.doc, product_name="B",
            quantity=Decimal("3"), unit="kg",
            unit_price=Decimal("10.00"), vat_rate=Decimal("25"),
        )
        self.assertAlmostEqual(self.doc.total, 50.0)


class PrimkaModelTest(TestCase):
    def setUp(self):
        self.company = _company("OPG Primka", "50000000002")

    def test_create_primka(self):
        doc = Primka.objects.create(
            company=self.company, doc_number="PRI-2026-0001",
            date_issued=datetime.date.today(),
        )
        self.assertEqual(doc.status, "draft")

    def test_primka_item_total(self):
        doc = Primka.objects.create(
            company=self.company, doc_number="PRI-2026-0002",
            date_issued=datetime.date.today(),
        )
        item = PrimkaItem.objects.create(
            document=doc, product_name="Jabuka",
            quantity=Decimal("100"), unit="kg",
            unit_price=Decimal("1.50"), vat_rate=Decimal("5"),
        )
        self.assertAlmostEqual(item.line_total, 150.0)


class OtkupniBlokModelTest(TestCase):
    def setUp(self):
        self.company = _company("OPG Otkup", "50000000003")

    def test_quality_class(self):
        doc = OtkupniBlok.objects.create(
            company=self.company, doc_number="OTK-2026-0001",
            date_issued=datetime.date.today(),
        )
        item = OtkupniBlokItem.objects.create(
            document=doc, product_name="Sljiva",
            quantity=Decimal("50"), unit="kg",
            unit_price=Decimal("2.20"), vat_rate=Decimal("5"),
            quality_class="I",
        )
        self.assertEqual(item.quality_class, "I")
        self.assertAlmostEqual(item.line_total, 110.0)


class CMRModelTest(TestCase):
    def setUp(self):
        self.company = _company("OPG CMR", "50000000004")

    def test_cmr_item(self):
        doc = CMR.objects.create(
            company=self.company, doc_number="CMR-2026-0001",
            date_issued=datetime.date.today(),
        )
        item = CMRItem.objects.create(
            document=doc, product_name="Psenica",
            quantity=Decimal("1000"), unit="kg",
            unit_price=Decimal("0.35"), vat_rate=Decimal("5"),
        )
        self.assertAlmostEqual(item.line_total, 350.0)


class ProcessDocViewTest(TestCase):
    def setUp(self):
        self.company = _company("View Co", "50000000005")
        self.user = _user("view_user", self.company)
        self.client = Client(SERVER_NAME="viskovic-group.de")
        self.client.force_login(self.user)

    def _get(self, url):
        return self.client.get(url, secure=True, HTTP_ACCEPT_LANGUAGE="de")

    def test_otpremnica_list_200(self):
        self.assertEqual(self._get("/documents/otpremnica/").status_code, 200)

    def test_primka_list_200(self):
        self.assertEqual(self._get("/documents/primka/").status_code, 200)

    def test_otkupni_list_200(self):
        self.assertEqual(self._get("/documents/otkupni/").status_code, 200)

    def test_cmr_list_200(self):
        self.assertEqual(self._get("/documents/cmr/").status_code, 200)

    def test_otpremnica_create_get_200(self):
        self.assertEqual(self._get("/documents/otpremnica/nova/").status_code, 200)

    def test_detail_200(self):
        doc = Otpremnica.objects.create(
            company=self.company, doc_number="OTP-VIEW-001",
            date_issued=datetime.date.today(),
        )
        self.assertEqual(self._get(f"/documents/otpremnica/{doc.pk}/").status_code, 200)

    def test_confirm_action(self):
        doc = Otpremnica.objects.create(
            company=self.company, doc_number="OTP-CONF-001",
            date_issued=datetime.date.today(),
        )
        resp = self.client.post(
            f"/documents/otpremnica/{doc.pk}/confirm/",
            secure=True, HTTP_ACCEPT_LANGUAGE="de"
        )
        self.assertIn(resp.status_code, [200, 302])
        doc.refresh_from_db()
        self.assertEqual(doc.status, "confirmed")

    def test_isolation(self):
        co_b = _company("Firma B Otp", "50000000006")
        user_b = _user("otp_user_b", co_b)
        Otpremnica.objects.create(
            company=self.company, doc_number="OTP-SECRET-A",
            date_issued=datetime.date.today(),
        )
        c_b = Client(SERVER_NAME="viskovic-group.de")
        c_b.force_login(user_b)
        resp = c_b.get("/documents/otpremnica/", secure=True, HTTP_ACCEPT_LANGUAGE="de")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "OTP-SECRET-A")

    def test_requires_login(self):
        c = Client(SERVER_NAME="viskovic-group.de")
        resp = c.get("/documents/otpremnica/", secure=True, HTTP_ACCEPT_LANGUAGE="de")
        self.assertEqual(resp.status_code, 302)
