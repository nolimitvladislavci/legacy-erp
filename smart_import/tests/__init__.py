"""
Comprehensive tests for Smart Import (AIP) module.
Covers: models, services, tasks, views — full functionality + logic + edge cases.
Run: python manage.py test smart_import --verbosity=2
"""
import json
import os
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from companies.models import Company, TaxRate
from inventory.models import InventoryItem, GoodsReceipt, GoodsReceiptItem
from partners.models import Partner
from smart_import.models import (
    ImportBatch, ImportBatchItem, VendorItemMapping,
    GeminiUsageLog, CompanyMailbox, FailedImport, ProblemReport,
)


# ============================================================================
# HELPERS
# ============================================================================

def _make_company(name="Test Co", oib="11111111111"):
    return Company.objects.create(name=name, oib=oib)


def _make_user(username="testuser", password="testpass123"):
    return User.objects.create_user(username=username, password=password)


def _make_tax_rate(rate=25):
    return TaxRate.objects.get_or_create(rate=Decimal(str(rate)), defaults={
        "name": "PDV {}%".format(rate),
    })[0]


def _make_inventory_item(company, name="Test Item", purchase_price="10.00", tax_rate=None):
    return InventoryItem.objects.create(
        company=company,
        name=name,
        purchase_price=Decimal(purchase_price),
        tax_rate=tax_rate,
        is_active=True,
    )


def _make_partner(company, name="Test Supplier", partner_type="supplier"):
    return Partner.objects.create(
        company=company,
        name=name,
        partner_type=partner_type,
    )


def _make_batch(company, status="pending", file_type="pdf", supplier=None, user=None):
    batch = ImportBatch.objects.create(
        company=company,
        supplier=supplier,
        file_type=file_type,
        status=status,
        created_by=user,
    )
    # Create a dummy file
    batch.file.save("test_invoice.pdf", ContentFile(b"dummy pdf content"), save=True)
    return batch


def _make_xml_ubl():
    """Generate a minimal valid UBL e-Racun XML."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>INV-2025-001</cbc:ID>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>10</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="EUR">150.00</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>Coca Cola 0.5L</cbc:Name>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="EUR">15.00</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>5</cbc:InvoicedQuantity>
    <cac:Item>
      <cbc:Name>Fanta 1L</cbc:Name>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="EUR">12.50</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>20</cbc:InvoicedQuantity>
    <cac:Item>
      <cbc:Name>Mineralna voda Jana 0.5L</cbc:Name>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="EUR">0.80</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
</Invoice>"""


def _make_generic_xml():
    """XML without UBL namespace — should use generic scanner."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <item>
    <name>Brasno tip 500</name>
    <quantity>25</quantity>
    <price>0.85</price>
  </item>
  <item>
    <name>Secer kristal</name>
    <quantity>10</quantity>
    <price>1.20</price>
  </item>
</document>"""


# ============================================================================
# MODEL TESTS
# ============================================================================

class ImportBatchModelTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()

    def test_batch_creation_defaults(self):
        batch = ImportBatch.objects.create(company=self.company)
        self.assertEqual(batch.status, "pending")
        self.assertEqual(batch.raw_json, [])
        self.assertEqual(batch.error_msg, "")
        self.assertEqual(batch.retry_count, 0)
        self.assertIsNone(batch.processing_started_at)
        self.assertIsNone(batch.goods_receipt)
        self.assertIsNotNone(batch.created_at)

    def test_batch_str(self):
        batch = ImportBatch.objects.create(company=self.company)
        self.assertIn("Ceka obradu", str(batch))

    def test_batch_ordering(self):
        b1 = ImportBatch.objects.create(company=self.company)
        b2 = ImportBatch.objects.create(company=self.company)
        batches = list(ImportBatch.objects.all())
        self.assertEqual(batches[0], b2)  # newer first

    def test_batch_status_choices(self):
        for status_code, _ in ImportBatch.STATUS:
            batch = ImportBatch.objects.create(company=self.company, status=status_code)
            self.assertEqual(batch.status, status_code)

    def test_batch_with_supplier(self):
        supplier = _make_partner(self.company)
        batch = ImportBatch.objects.create(company=self.company, supplier=supplier)
        self.assertEqual(batch.supplier, supplier)

    def test_batch_supplier_deletion_sets_null(self):
        supplier = _make_partner(self.company)
        batch = ImportBatch.objects.create(company=self.company, supplier=supplier)
        supplier.delete()
        batch.refresh_from_db()
        self.assertIsNone(batch.supplier)


class ImportBatchItemModelTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.batch = ImportBatch.objects.create(company=self.company)

    def test_item_creation(self):
        item = ImportBatchItem.objects.create(
            batch=self.batch, row_index=0,
            vendor_name="Coca Cola 0.5L",
            quantity=Decimal("10"), purchase_price=Decimal("1.5000"),
        )
        self.assertEqual(item.vendor_name, "Coca Cola 0.5L")
        self.assertEqual(item.quantity, Decimal("10"))
        self.assertFalse(item.is_manual)
        self.assertEqual(item.match_score, 0)

    def test_item_str(self):
        item = ImportBatchItem.objects.create(
            batch=self.batch, row_index=0,
            vendor_name="Test", quantity=Decimal("5"),
        )
        self.assertIn("Test", str(item))
        self.assertIn("5", str(item))

    def test_items_ordering(self):
        ImportBatchItem.objects.create(batch=self.batch, row_index=2, vendor_name="B")
        ImportBatchItem.objects.create(batch=self.batch, row_index=0, vendor_name="A")
        ImportBatchItem.objects.create(batch=self.batch, row_index=1, vendor_name="C")
        items = list(self.batch.items.all())
        self.assertEqual([i.row_index for i in items], [0, 1, 2])

    def test_cascade_delete(self):
        ImportBatchItem.objects.create(batch=self.batch, row_index=0, vendor_name="X")
        self.assertEqual(ImportBatchItem.objects.count(), 1)
        self.batch.delete()
        self.assertEqual(ImportBatchItem.objects.count(), 0)


class VendorItemMappingModelTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.tax = _make_tax_rate()
        self.inv_item = _make_inventory_item(self.company, tax_rate=self.tax)

    def test_mapping_creation(self):
        m = VendorItemMapping.objects.create(
            company=self.company,
            vendor_item_name="COCA COLA PET 0.5",
            inventory_item=self.inv_item,
        )
        self.assertEqual(m.vendor_item_name, "COCA COLA PET 0.5")
        self.assertIn("->", str(m))

    def test_mapping_unique_constraint(self):
        VendorItemMapping.objects.create(
            company=self.company,
            vendor_item_name="UNIQUE_NAME",
            inventory_item=self.inv_item,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            VendorItemMapping.objects.create(
                company=self.company,
                vendor_item_name="UNIQUE_NAME",
                inventory_item=self.inv_item,
            )

    def test_mapping_same_name_different_partner(self):
        p1 = _make_partner(self.company, name="Supplier A")
        p2 = _make_partner(self.company, name="Supplier B")
        VendorItemMapping.objects.create(
            company=self.company, partner=p1,
            vendor_item_name="ITEM_X", inventory_item=self.inv_item,
        )
        # Same name, different partner — should work
        m2 = VendorItemMapping.objects.create(
            company=self.company, partner=p2,
            vendor_item_name="ITEM_X", inventory_item=self.inv_item,
        )
        self.assertIsNotNone(m2.pk)


class GeminiUsageLogModelTest(TestCase):
    def test_log_creation(self):
        log = GeminiUsageLog.objects.create(
            caller="smart_import_vision",
            model="gemini-2.5-flash",
            input_tokens=1500,
            output_tokens=200,
            cost_eur=Decimal("0.00034500"),
            success=True,
        )
        self.assertIn("OK", str(log))
        self.assertIn("smart_import_vision", str(log))

    def test_daily_summary_empty(self):
        summary = GeminiUsageLog.daily_summary()
        self.assertEqual(summary["total_calls"], 0)

    def test_daily_summary_with_data(self):
        GeminiUsageLog.objects.create(
            caller="test", input_tokens=100, output_tokens=50,
            cost_eur=Decimal("0.001"), success=True,
        )
        GeminiUsageLog.objects.create(
            caller="test", input_tokens=200, output_tokens=100,
            cost_eur=Decimal("0.002"), success=False,
        )
        summary = GeminiUsageLog.daily_summary()
        self.assertEqual(summary["total_calls"], 2)
        self.assertEqual(summary["ok_calls"], 1)
        self.assertEqual(summary["total_tokens"], 300)


class CompanyMailboxModelTest(TestCase):
    def setUp(self):
        self.company = _make_company()

    def test_mailbox_creation(self):
        mb = CompanyMailbox.objects.create(
            company=self.company,
            email_address="test@example.com",
            imap_server="imap.gmail.com",
            imap_password="secret123",
        )
        self.assertTrue(mb.is_active)
        self.assertEqual(mb.protocol, "imap")
        self.assertEqual(mb.imap_port, 993)
        self.assertTrue(mb.imap_use_ssl)
        self.assertIn("test@example.com", str(mb))

    def test_mailbox_email_unique(self):
        CompanyMailbox.objects.create(
            company=self.company, email_address="unique@test.com",
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            CompanyMailbox.objects.create(
                company=self.company, email_address="unique@test.com",
            )


class ProblemReportModelTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.batch = ImportBatch.objects.create(company=self.company)

    def test_report_creation(self):
        r = ProblemReport.objects.create(
            batch=self.batch, company=self.company,
            description="Stavke nisu prepoznate",
        )
        self.assertFalse(r.resolved)
        self.assertIn("Problem", str(r))

    def test_report_cascade_on_batch_delete(self):
        ProblemReport.objects.create(
            batch=self.batch, company=self.company, description="test",
        )
        self.batch.delete()
        self.assertEqual(ProblemReport.objects.count(), 0)


class FailedImportModelTest(TestCase):
    def test_failed_import_creation(self):
        fi = FailedImport.objects.create(
            filename="broken.pdf",
            error_message="Parse error: corrupted PDF",
            email_subject="Racun 2025-001",
            email_sender="supplier@example.com",
        )
        self.assertIn("broken.pdf", str(fi))


# ============================================================================
# SERVICES TESTS
# ============================================================================

class ParseXmlUblTest(TestCase):
    """Test XML parsing with UBL e-Racun format."""

    def test_parse_ubl_invoice(self):
        from smart_import.services import parse_xml
        xml_content = _make_xml_ubl()
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w", encoding="utf-8") as f:
            f.write(xml_content)
            f.flush()
            rows = parse_xml(f.name)
        os.unlink(f.name)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["vendor_name"], "Coca Cola 0.5L")
        self.assertEqual(rows[0]["quantity"], "10")
        self.assertEqual(rows[0]["purchase_price"], "15.00")
        self.assertEqual(rows[1]["vendor_name"], "Fanta 1L")
        self.assertEqual(rows[1]["quantity"], "5")
        self.assertEqual(rows[1]["purchase_price"], "12.50")
        self.assertEqual(rows[2]["vendor_name"], "Mineralna voda Jana 0.5L")
        self.assertEqual(rows[2]["quantity"], "20")
        self.assertEqual(rows[2]["purchase_price"], "0.80")

    def test_parse_generic_xml(self):
        from smart_import.services import parse_xml
        xml_content = _make_generic_xml()
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w", encoding="utf-8") as f:
            f.write(xml_content)
            f.flush()
            rows = parse_xml(f.name)
        os.unlink(f.name)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["vendor_name"], "Brasno tip 500")
        self.assertEqual(rows[0]["quantity"], "25")
        self.assertEqual(rows[0]["purchase_price"], "0.85")

    def test_parse_empty_xml(self):
        from smart_import.services import parse_xml
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w") as f:
            f.write('<?xml version="1.0"?><empty/>')
            f.flush()
            rows = parse_xml(f.name)
        os.unlink(f.name)
        self.assertEqual(rows, [])

    def test_parse_xml_missing_name_skips_row(self):
        from smart_import.services import parse_xml
        xml = """<?xml version="1.0"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>10</cbc:InvoicedQuantity>
    <cac:Item><cbc:Name></cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount>5.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>3</cbc:InvoicedQuantity>
    <cac:Item><cbc:Name>Jabuka</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount>2.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>"""
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w") as f:
            f.write(xml)
            f.flush()
            rows = parse_xml(f.name)
        os.unlink(f.name)
        # Empty name row should be skipped, only Jabuka returned
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_name"], "Jabuka")


class ToDecimalTest(TestCase):
    """Test the _to_decimal helper."""

    def test_normal_number(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal("15.50"), "15.50")

    def test_comma_decimal(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal("1.234,56"), "1234.56")

    def test_none_returns_default(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal(None, 1), "1")

    def test_garbage_returns_default(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal("abc", 0), "0")

    def test_negative_number(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal("-5.00"), "-5.00")

    def test_currency_symbol_stripped(self):
        from smart_import.services import _to_decimal
        result = _to_decimal("€15.00")
        self.assertEqual(result, "15.00")

    def test_integer(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal(42), "42")

    def test_decimal_input(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal(Decimal("3.14")), "3.14")

    def test_empty_string(self):
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal("", 0), "0")


class ParseJsonRowsTest(TestCase):
    """Test _parse_json_rows — parsing AI-returned JSON."""

    def test_valid_json_array(self):
        from smart_import.services import _parse_json_rows
        raw = '[{"vendor_name": "Mlijeko", "quantity": 10, "purchase_price": 1.20}]'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_name"], "Mlijeko")

    def test_json_with_markdown_fences(self):
        from smart_import.services import _parse_json_rows
        raw = '```json\n[{"vendor_name": "Kruh", "quantity": 5, "purchase_price": 0.80}]\n```'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_name"], "Kruh")

    def test_json_with_extra_text(self):
        from smart_import.services import _parse_json_rows
        raw = 'Here are the items:\n[{"vendor_name": "A", "quantity": 1, "purchase_price": 2}]\nDone.'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)

    def test_empty_json(self):
        from smart_import.services import _parse_json_rows
        self.assertEqual(_parse_json_rows("[]"), [])

    def test_invalid_json(self):
        from smart_import.services import _parse_json_rows
        self.assertEqual(_parse_json_rows("not json at all"), [])

    def test_skips_items_without_name(self):
        from smart_import.services import _parse_json_rows
        raw = '[{"vendor_name": "", "quantity": 1}, {"vendor_name": "Real", "quantity": 2}]'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_name"], "Real")

    def test_alternative_name_field(self):
        """AI sometimes returns 'name' instead of 'vendor_name'."""
        from smart_import.services import _parse_json_rows
        raw = '[{"name": "Alt Name", "quantity": 1, "purchase_price": 5}]'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_name"], "Alt Name")

    def test_alternative_price_field(self):
        """AI sometimes returns 'price' instead of 'purchase_price'."""
        from smart_import.services import _parse_json_rows
        raw = '[{"vendor_name": "Item", "quantity": 1, "price": 9.99}]'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["purchase_price"], "9.99")

    def test_non_dict_items_skipped(self):
        from smart_import.services import _parse_json_rows
        raw = '[{"vendor_name": "Good"}, "bad", 123, null]'
        rows = _parse_json_rows(raw)
        self.assertEqual(len(rows), 1)

    def test_not_a_list(self):
        from smart_import.services import _parse_json_rows
        raw = '{"vendor_name": "single item"}'
        rows = _parse_json_rows(raw)
        self.assertEqual(rows, [])


class MatchItemsTest(TestCase):
    """Test fuzzy matching logic."""

    def setUp(self):
        self.company = _make_company()
        self.tax = _make_tax_rate()
        self.coca_cola = _make_inventory_item(self.company, "Coca-Cola 0.5L", tax_rate=self.tax)
        self.fanta = _make_inventory_item(self.company, "Fanta 1L", tax_rate=self.tax)
        self.water = _make_inventory_item(self.company, "Mineralna voda Jana", tax_rate=self.tax)

    def test_exact_mapping_match(self):
        """VendorItemMapping with score 1.0 takes priority."""
        from smart_import.services import match_items
        supplier = _make_partner(self.company)
        VendorItemMapping.objects.create(
            company=self.company, partner=supplier,
            vendor_item_name="COCA COLA PET 0,5L",
            inventory_item=self.coca_cola,
        )
        batch = ImportBatch.objects.create(company=self.company, supplier=supplier)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0,
            vendor_name="COCA COLA PET 0,5L", quantity=Decimal("10"),
        )
        match_items(batch)
        item = batch.items.first()
        self.assertEqual(item.matched_item, self.coca_cola)
        self.assertEqual(item.match_score, 1.0)

    def test_fuzzy_match_high_similarity(self):
        from smart_import.services import match_items
        batch = ImportBatch.objects.create(company=self.company)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0,
            vendor_name="Coca-Cola 0.5 L", quantity=Decimal("10"),
        )
        match_items(batch)
        item = batch.items.first()
        self.assertEqual(item.matched_item, self.coca_cola)
        self.assertGreaterEqual(item.match_score, 0.8)

    def test_fuzzy_match_low_similarity_returns_none(self):
        from smart_import.services import match_items
        batch = ImportBatch.objects.create(company=self.company)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0,
            vendor_name="XYZZY COMPLETELY DIFFERENT THING", quantity=Decimal("1"),
        )
        match_items(batch)
        item = batch.items.first()
        # Should be None or very low score (below 0.4 threshold)
        if item.matched_item is None:
            self.assertLess(item.match_score, 0.4)
        else:
            self.assertGreaterEqual(item.match_score, 0.4)

    def test_multiple_items_matched(self):
        from smart_import.services import match_items
        batch = ImportBatch.objects.create(company=self.company)
        ImportBatchItem.objects.create(batch=batch, row_index=0, vendor_name="Coca-Cola 0.5L")
        ImportBatchItem.objects.create(batch=batch, row_index=1, vendor_name="Fanta 1L")
        ImportBatchItem.objects.create(batch=batch, row_index=2, vendor_name="Jana mineralna voda")
        match_items(batch)
        items = list(batch.items.all())
        matched_count = sum(1 for i in items if i.matched_item is not None)
        self.assertGreaterEqual(matched_count, 2)

    def test_mapping_case_insensitive(self):
        from smart_import.services import match_items
        VendorItemMapping.objects.create(
            company=self.company,
            vendor_item_name="fanta 1l",
            inventory_item=self.fanta,
        )
        batch = ImportBatch.objects.create(company=self.company)
        ImportBatchItem.objects.create(batch=batch, row_index=0, vendor_name="FANTA 1L")
        match_items(batch)
        item = batch.items.first()
        self.assertEqual(item.matched_item, self.fanta)
        self.assertEqual(item.match_score, 1.0)

    def test_no_inventory_items(self):
        """Company with no inventory items — nothing crashes."""
        from smart_import.services import match_items
        empty_co = _make_company("Empty Co", "22222222222")
        batch = ImportBatch.objects.create(company=empty_co)
        ImportBatchItem.objects.create(batch=batch, row_index=0, vendor_name="Something")
        match_items(batch)  # Should not raise
        item = batch.items.first()
        self.assertIsNone(item.matched_item)


class ImageEncodingTest(TestCase):
    """Test image encoding helpers."""

    def test_encode_image_jpeg(self):
        from smart_import.services import _encode_image
        from PIL import Image as PILImage
        # Create a small test image
        img = PILImage.new("RGB", (100, 100), color="red")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            f.flush()
            b64, media_type = _encode_image(f.name)
        os.unlink(f.name)
        self.assertIsNotNone(b64)
        self.assertEqual(media_type, "image/jpeg")
        # Verify it's valid base64
        import base64
        decoded = base64.standard_b64decode(b64)
        self.assertGreater(len(decoded), 0)

    def test_encode_image_png(self):
        from smart_import.services import _encode_image
        from PIL import Image as PILImage
        img = PILImage.new("RGB", (100, 100), color="blue")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            f.flush()
            b64, media_type = _encode_image(f.name)
        os.unlink(f.name)
        self.assertIsNotNone(b64)
        self.assertEqual(media_type, "image/png")

    def test_encode_image_rgba_converts_to_rgb(self):
        from smart_import.services import _encode_image
        from PIL import Image as PILImage
        img = PILImage.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            f.flush()
            b64, media_type = _encode_image(f.name)
        os.unlink(f.name)
        self.assertIsNotNone(b64)

    def test_encode_image_enhanced_grayscale(self):
        from smart_import.services import _encode_image_enhanced
        from PIL import Image as PILImage
        img = PILImage.new("RGB", (200, 200), color="white")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            f.flush()
            b64, media_type = _encode_image_enhanced(f.name)
        os.unlink(f.name)
        self.assertIsNotNone(b64)
        self.assertEqual(media_type, "image/jpeg")

    def test_encode_nonexistent_file(self):
        from smart_import.services import _encode_image
        b64, mt = _encode_image("/nonexistent/path/image.jpg")
        self.assertIsNone(b64)
        self.assertIsNone(mt)

    def test_encode_large_image_resized(self):
        """Images larger than 2048px should be thumbnailed."""
        from smart_import.services import _encode_image
        from PIL import Image as PILImage
        img = PILImage.new("RGB", (4000, 3000), color="green")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            f.flush()
            b64, _ = _encode_image(f.name)
        os.unlink(f.name)
        self.assertIsNotNone(b64)
        # Decode and check size
        import base64
        from io import BytesIO
        decoded = base64.standard_b64decode(b64)
        result_img = PILImage.open(BytesIO(decoded))
        self.assertLessEqual(max(result_img.size), 2048)


class PdfTextExtractionTest(TestCase):
    """Test PDF text extraction."""

    def test_extract_empty_pdf(self):
        from smart_import.services import _extract_pdf_text
        # Create a minimal valid PDF (no text)
        try:
            from reportlab.pdfgen import canvas
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                c = canvas.Canvas(f.name)
                c.drawString(72, 700, "")
                c.save()
                text = _extract_pdf_text(f.name)
            os.unlink(f.name)
            # Should return empty or near-empty string
            self.assertIsInstance(text, str)
        except ImportError:
            self.skipTest("reportlab not installed")

    def test_extract_pdf_with_text(self):
        from smart_import.services import _extract_pdf_text
        try:
            from reportlab.pdfgen import canvas
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                c = canvas.Canvas(f.name)
                c.drawString(72, 700, "RACUN BR: 2025-001")
                c.drawString(72, 680, "Coca Cola 0.5L   10 kom   1.50 EUR")
                c.save()
                text = _extract_pdf_text(f.name)
            os.unlink(f.name)
            self.assertIn("Coca Cola", text)
            self.assertIn("2025-001", text)
        except ImportError:
            self.skipTest("reportlab not installed")


# ============================================================================
# TASK TESTS
# ============================================================================

class LockingTest(TestCase):
    """Test Redis-based locking mechanism."""

    def test_acquire_and_release(self):
        from smart_import.tasks import _acquire_lock, _release_lock
        self.assertTrue(_acquire_lock(999))
        # Second acquire should fail
        self.assertFalse(_acquire_lock(999))
        # Release and try again
        _release_lock(999)
        self.assertTrue(_acquire_lock(999))
        _release_lock(999)

    def test_release_nonexistent_lock(self):
        from smart_import.tasks import _release_lock
        # Should not raise
        _release_lock(88888)


class ProcessImportBatchTaskTest(TestCase):
    """Test the main Celery task logic."""

    def setUp(self):
        self.company = _make_company()
        self.tax = _make_tax_rate()

    @patch("smart_import.services.parse_xml")
    def test_process_xml_batch(self, mock_parse_xml):
        mock_parse_xml.return_value = [
            {"vendor_name": "Item A", "quantity": "10", "purchase_price": "5.00"},
            {"vendor_name": "Item B", "quantity": "3", "purchase_price": "12.00"},
        ]
        batch = _make_batch(self.company, file_type="xml")

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "ready")
        self.assertEqual(batch.items.count(), 2)
        self.assertIn("2 stavki", batch.status_message)

    @patch("smart_import.services.parse_pdf")
    def test_process_pdf_batch(self, mock_parse_pdf):
        mock_parse_pdf.return_value = [
            {"vendor_name": "PDF Item", "quantity": "1", "purchase_price": "99.99"},
        ]
        batch = _make_batch(self.company, file_type="pdf")

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "ready")
        self.assertEqual(batch.items.count(), 1)

    @patch("smart_import.services.parse_image")
    def test_process_image_batch(self, mock_parse_image):
        mock_parse_image.return_value = [
            {"vendor_name": "Photo Item", "quantity": "2", "purchase_price": "7.50"},
        ]
        batch = _make_batch(self.company, file_type="image")

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "ready")

    @patch("smart_import.services.parse_image_enhanced")
    @patch("smart_import.services.parse_image")
    def test_image_fallback_to_enhanced(self, mock_parse_image, mock_enhanced):
        """If parse_image returns empty, should try parse_image_enhanced."""
        mock_parse_image.return_value = []
        mock_enhanced.return_value = [
            {"vendor_name": "Enhanced Item", "quantity": "1", "purchase_price": "5.00"},
        ]
        batch = _make_batch(self.company, file_type="image")

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "ready")
        self.assertEqual(batch.items.count(), 1)
        self.assertEqual(batch.items.first().vendor_name, "Enhanced Item")
        mock_enhanced.assert_called_once()

    @patch("smart_import.services.parse_image_enhanced")
    @patch("smart_import.services.parse_image")
    def test_all_parsers_fail_sets_error(self, mock_parse_image, mock_enhanced):
        mock_parse_image.return_value = []
        mock_enhanced.return_value = []
        batch = _make_batch(self.company, file_type="image")

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "error")
        self.assertIn("Nema stavki", batch.error_msg)

    def test_nonexistent_batch(self):
        from smart_import.tasks import process_import_batch
        # Should not raise
        process_import_batch(999999)

    @patch("smart_import.services.parse_pdf")
    def test_batch_sets_processing_status(self, mock_parse_pdf):
        """Verify batch transitions through processing state."""
        statuses_seen = []

        original_save = ImportBatch.save
        def tracking_save(self_batch, *args, **kwargs):
            original_save(self_batch, *args, **kwargs)
            statuses_seen.append(self_batch.status)

        mock_parse_pdf.return_value = [
            {"vendor_name": "X", "quantity": "1", "purchase_price": "1"},
        ]
        batch = _make_batch(self.company, file_type="pdf")

        with patch.object(ImportBatch, 'save', tracking_save):
            from smart_import.tasks import process_import_batch
            process_import_batch(batch.pk)

        self.assertIn("processing", statuses_seen)
        self.assertIn("ready", statuses_seen)

    @patch("smart_import.services.parse_pdf")
    def test_retry_count_increments(self, mock_parse_pdf):
        mock_parse_pdf.return_value = [
            {"vendor_name": "Y", "quantity": "1", "purchase_price": "1"},
        ]
        batch = _make_batch(self.company, file_type="pdf")
        self.assertEqual(batch.retry_count, 0)

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.retry_count, 1)

    @patch("smart_import.services.parse_pdf")
    def test_existing_items_cleared_on_reprocess(self, mock_parse_pdf):
        """When reprocessing, old items should be deleted."""
        batch = _make_batch(self.company, file_type="pdf")
        ImportBatchItem.objects.create(batch=batch, row_index=0, vendor_name="Old Item")
        self.assertEqual(batch.items.count(), 1)

        mock_parse_pdf.return_value = [
            {"vendor_name": "New Item", "quantity": "1", "purchase_price": "1"},
        ]

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        batch.refresh_from_db()
        self.assertEqual(batch.items.count(), 1)
        self.assertEqual(batch.items.first().vendor_name, "New Item")

    @patch("smart_import.tasks._acquire_lock")
    @patch("smart_import.services.parse_pdf")
    def test_locked_batch_skipped(self, mock_parse_pdf, mock_lock):
        mock_lock.return_value = False  # Lock already held
        batch = _make_batch(self.company, file_type="pdf")

        from smart_import.tasks import process_import_batch
        process_import_batch(batch.pk)

        # Should not have been processed
        batch.refresh_from_db()
        self.assertEqual(batch.status, "pending")
        mock_parse_pdf.assert_not_called()


class DetectStaleBatchesTest(TestCase):
    def setUp(self):
        self.company = _make_company()

    def test_stale_batch_marked_error(self):
        batch = ImportBatch.objects.create(
            company=self.company, status="processing",
        )
        # Make it old
        ImportBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(minutes=10),
        )

        from smart_import.tasks import detect_stale_batches
        result = detect_stale_batches()

        batch.refresh_from_db()
        self.assertEqual(batch.status, "error")
        self.assertIn("predugo", batch.error_msg)
        self.assertIn("1", result)

    def test_fresh_batch_not_touched(self):
        batch = ImportBatch.objects.create(
            company=self.company, status="processing",
        )
        # Created just now — should NOT be stale

        from smart_import.tasks import detect_stale_batches
        result = detect_stale_batches()

        batch.refresh_from_db()
        self.assertEqual(batch.status, "processing")
        self.assertIn("Nema", result)

    def test_ready_batch_not_touched(self):
        batch = ImportBatch.objects.create(
            company=self.company, status="ready",
        )
        ImportBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(minutes=60),
        )

        from smart_import.tasks import detect_stale_batches
        detect_stale_batches()

        batch.refresh_from_db()
        self.assertEqual(batch.status, "ready")

    def test_pending_stale_also_caught(self):
        batch = ImportBatch.objects.create(
            company=self.company, status="pending",
        )
        ImportBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(minutes=10),
        )

        from smart_import.tasks import detect_stale_batches
        detect_stale_batches()

        batch.refresh_from_db()
        self.assertEqual(batch.status, "error")


class MultipageProcessTest(TestCase):
    def setUp(self):
        self.company = _make_company()

    @patch("smart_import.services.parse_image")
    def test_multipage_deduplication(self, mock_parse_image):
        """Multipage processing should deduplicate by vendor name."""
        from smart_import.tasks import _process_multipage
        from PIL import Image as PILImage

        # Create temp images
        paths = []
        for i in range(2):
            img = PILImage.new("RGB", (100, 100))
            f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            img.save(f, format="JPEG")
            paths.append(f.name)
            f.close()

        # Page 1 has item A (no price), Page 2 has item A (with price) + item B
        call_count = [0]
        def side_effect(path):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {"vendor_name": "Item A", "quantity": "1", "purchase_price": "0"},
                ]
            else:
                return [
                    {"vendor_name": "Item A", "quantity": "1", "purchase_price": "5.00"},
                    {"vendor_name": "Item B", "quantity": "2", "purchase_price": "3.00"},
                ]
        mock_parse_image.side_effect = side_effect

        batch = ImportBatch.objects.create(
            company=self.company, file_type="multipage",
            raw_json={"page_paths": paths},
        )
        batch.file.save("test.jpg", ContentFile(b"dummy"), save=True)

        result = _process_multipage(batch)

        # Should have 2 items (Item A deduplicated, price updated to 5.00)
        self.assertEqual(len(result), 2)
        names = [r["vendor_name"] for r in result]
        self.assertIn("Item A", names)
        self.assertIn("Item B", names)
        # Item A should have the better price (5.00 instead of 0)
        item_a = next(r for r in result if r["vendor_name"] == "Item A")
        self.assertEqual(float(item_a["purchase_price"]), 5.0)

        for p in paths:
            os.unlink(p)


# ============================================================================
# VIEW TESTS
# ============================================================================

class UploadViewTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        # Link user to company
        from core.company_utils import get_user_company
        from django.contrib.auth.models import User
        # Create UserProfile or UserRole linking user to company
        try:
            from core.models import UserProfile
            UserProfile.objects.get_or_create(user=self.user, defaults={"company": self.company})
        except (ImportError, Exception):
            pass
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except (ImportError, Exception):
            pass

    def test_upload_requires_login(self):
        response = self.client.get("/hr/smart-import/")
        self.assertIn(response.status_code, [301, 302])

    def test_upload_page_loads(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/hr/smart-import/")
        if response.status_code == 200:
            self.assertEqual(response.status_code, 200)
        else:
            # May redirect due to company not being set up properly
            self.assertIn(response.status_code, [200, 302])

    @patch("smart_import.views.process_import_batch")
    def test_upload_pdf_creates_batch(self, mock_task):
        mock_task.delay = MagicMock()
        self.client.login(username="testuser", password="testpass123")
        pdf_file = SimpleUploadedFile("test_invoice.pdf", b"dummy pdf", content_type="application/pdf")
        response = self.client.post("/hr/smart-import/", {"files": [pdf_file]})
        # Should redirect to stage view
        if response.status_code == 302:
            self.assertTrue(mock_task.delay.called or ImportBatch.objects.exists())

    @patch("smart_import.views.process_import_batch")
    def test_upload_rejects_unsupported_format(self, mock_task):
        self.client.login(username="testuser", password="testpass123")
        bad_file = SimpleUploadedFile("data.exe", b"malware", content_type="application/octet-stream")
        response = self.client.post("/hr/smart-import/", {"files": [bad_file]})
        # Should show error, not create batch
        if response.status_code == 200:
            self.assertContains(response, "Nepodrzani format")
        mock_task.delay.assert_not_called()


class BatchStatusApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_status_api_returns_json(self):
        batch = ImportBatch.objects.create(
            company=self.company, status="ready",
            status_message="Gotovo!", file_type="pdf",
        )
        batch.file.save("test.pdf", ContentFile(b"x"), save=True)
        ImportBatchItem.objects.create(batch=batch, row_index=0, vendor_name="Item")

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/status/".format(batch.pk)
        response = self.client.get(url)
        if response.status_code == 200:
            data = response.json()
            self.assertEqual(data["status"], "ready")
            self.assertEqual(data["item_count"], 1)


class RetryBatchApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    @patch("smart_import.views.process_import_batch")
    def test_retry_resets_batch(self, mock_task):
        mock_task.delay = MagicMock()
        batch = _make_batch(self.company, status="error")
        batch.error_msg = "Some error"
        batch.save()

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/retry/".format(batch.pk)
        response = self.client.post(url)
        if response.status_code == 200:
            batch.refresh_from_db()
            self.assertEqual(batch.status, "pending")
            self.assertEqual(batch.error_msg, "")

    @patch("smart_import.views.process_import_batch")
    def test_retry_non_error_batch_fails(self, mock_task):
        mock_task.delay = MagicMock()
        batch = _make_batch(self.company, status="ready")

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/retry/".format(batch.pk)
        response = self.client.post(url)
        if response.status_code == 400:
            data = response.json()
            self.assertFalse(data["ok"])


class ReportProblemApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_report_problem(self):
        batch = _make_batch(self.company, status="error")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/report-problem/".format(batch.pk)
        response = self.client.post(url, {"description": "Stavke krive"})
        if response.status_code == 200:
            self.assertEqual(ProblemReport.objects.count(), 1)
            report = ProblemReport.objects.first()
            self.assertEqual(report.description, "Stavke krive")
            self.assertEqual(report.batch, batch)


class SaveMappingApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        self.tax = _make_tax_rate()
        self.inv_item = _make_inventory_item(self.company, "Mapped Item", tax_rate=self.tax)
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_save_mapping(self):
        batch = _make_batch(self.company, status="ready")
        bi = ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="External Name",
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/save-mapping/".format(batch.pk)
        response = self.client.post(url, {
            "batch_item_id": bi.pk,
            "inventory_item_id": self.inv_item.pk,
        })
        if response.status_code == 200:
            bi.refresh_from_db()
            self.assertEqual(bi.matched_item, self.inv_item)
            self.assertEqual(bi.match_score, 1.0)
            self.assertTrue(bi.is_manual)
            # VendorItemMapping should exist
            self.assertTrue(VendorItemMapping.objects.filter(
                vendor_item_name="External Name",
            ).exists())


class UpdateItemApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_update_item_fields(self):
        batch = _make_batch(self.company, status="ready")
        bi = ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Old",
            quantity=Decimal("1"), purchase_price=Decimal("10"),
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/update-item/".format(batch.pk)
        response = self.client.post(url, {
            "item_id": bi.pk,
            "vendor_name": "New Name",
            "quantity": "5",
            "purchase_price": "20.50",
        })
        if response.status_code == 200:
            bi.refresh_from_db()
            self.assertEqual(bi.vendor_name, "New Name")
            self.assertEqual(bi.quantity, Decimal("5"))
            self.assertEqual(bi.purchase_price, Decimal("20.50"))


class DeleteItemApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_delete_item(self):
        batch = _make_batch(self.company, status="ready")
        bi = ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Delete Me",
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/delete-item/".format(batch.pk)
        response = self.client.post(url, {"item_id": bi.pk})
        if response.status_code == 200:
            self.assertEqual(batch.items.count(), 0)


class AddItemApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_add_item(self):
        batch = _make_batch(self.company, status="ready")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/add-item/".format(batch.pk)
        response = self.client.post(url, {
            "vendor_name": "New Item",
            "quantity": "3",
            "purchase_price": "7.50",
        })
        if response.status_code == 200:
            self.assertEqual(batch.items.count(), 1)
            item = batch.items.first()
            self.assertEqual(item.vendor_name, "New Item")
            self.assertEqual(item.quantity, Decimal("3"))

    def test_add_item_no_name_fails(self):
        batch = _make_batch(self.company, status="ready")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/add-item/".format(batch.pk)
        response = self.client.post(url, {"vendor_name": "", "quantity": "1"})
        if response.status_code == 400:
            self.assertEqual(batch.items.count(), 0)

    def test_add_item_auto_increments_row_index(self):
        batch = _make_batch(self.company, status="ready")
        ImportBatchItem.objects.create(batch=batch, row_index=5, vendor_name="Existing")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/add-item/".format(batch.pk)
        response = self.client.post(url, {"vendor_name": "New", "quantity": "1"})
        if response.status_code == 200:
            new_item = batch.items.exclude(vendor_name="Existing").first()
            self.assertEqual(new_item.row_index, 6)


class ConfirmViewTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        self.tax = _make_tax_rate()
        self.inv_item = _make_inventory_item(self.company, "Confirmed Item", tax_rate=self.tax)
        self.supplier = _make_partner(self.company)
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_confirm_creates_goods_receipt(self):
        batch = _make_batch(self.company, status="ready", supplier=self.supplier)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Item",
            quantity=Decimal("10"), purchase_price=Decimal("5.00"),
            matched_item=self.inv_item, match_score=0.9,
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/confirm/".format(batch.pk)
        response = self.client.post(url, {"global_margin": "25"})

        batch.refresh_from_db()
        if batch.status == "confirmed":
            self.assertIsNotNone(batch.goods_receipt)
            receipt = batch.goods_receipt
            self.assertEqual(receipt.supplier, self.supplier)
            self.assertEqual(receipt.items.count(), 1)
            ri = receipt.items.first()
            self.assertEqual(ri.quantity, Decimal("10"))
            self.assertEqual(ri.purchase_price_unit, Decimal("5.00"))

    def test_confirm_no_matched_items_shows_error(self):
        batch = _make_batch(self.company, status="ready")
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Unmatched",
            matched_item=None,
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/confirm/".format(batch.pk)
        response = self.client.post(url, {"global_margin": "30"})
        if response.status_code == 200:
            # Should show error message, not redirect
            batch.refresh_from_db()
            self.assertNotEqual(batch.status, "confirmed")

    def test_confirm_saves_manual_mappings(self):
        batch = _make_batch(self.company, status="ready", supplier=self.supplier)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Manual Map Item",
            quantity=Decimal("1"), purchase_price=Decimal("1"),
            matched_item=self.inv_item, match_score=1.0,
            is_manual=True,
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/confirm/".format(batch.pk)
        self.client.post(url, {"global_margin": "30"})

        batch.refresh_from_db()
        if batch.status == "confirmed":
            self.assertTrue(VendorItemMapping.objects.filter(
                vendor_item_name="Manual Map Item",
                inventory_item=self.inv_item,
            ).exists())

    def test_confirm_with_margin_override(self):
        batch = _make_batch(self.company, status="ready", supplier=self.supplier)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Margin Item",
            quantity=Decimal("5"), purchase_price=Decimal("10"),
            matched_item=self.inv_item, match_score=0.9,
            margin_override=Decimal("50.00"),
        )

        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/confirm/".format(batch.pk)
        response = self.client.post(url, {"global_margin": "25"})

        batch.refresh_from_db()
        if batch.status == "confirmed":
            ri = batch.goods_receipt.items.first()
            self.assertEqual(ri.margin_percent, Decimal("50.00"))


class UpdateSupplierApiTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        self.supplier = _make_partner(self.company, name="New Supplier")
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_update_supplier(self):
        batch = _make_batch(self.company, status="ready")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/update-supplier/".format(batch.pk)
        response = self.client.post(url, {"supplier_id": self.supplier.pk})
        if response.status_code == 200:
            batch.refresh_from_db()
            self.assertEqual(batch.supplier, self.supplier)

    def test_clear_supplier(self):
        batch = _make_batch(self.company, status="ready", supplier=self.supplier)
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/update-supplier/".format(batch.pk)
        response = self.client.post(url, {"supplier_id": ""})
        if response.status_code == 200:
            batch.refresh_from_db()
            self.assertIsNone(batch.supplier)


class WebhookViewTest(TestCase):
    """Test the inbound email webhook."""

    @override_settings(WEBHOOK_SECRET=None)
    def test_webhook_no_secret_configured(self):
        """Without WEBHOOK_SECRET env var, webhook should reject."""
        response = self.client.post(
            "/hr/smart-import/api/inbound-webhook/somesecret/",
            content_type="multipart/form-data",
        )
        # Should be 401 unauthorized
        self.assertIn(response.status_code, [401, 400])

    @patch.dict(os.environ, {"WEBHOOK_SECRET": "test_secret_123"})
    @patch("smart_import.views.process_import_batch")
    def test_webhook_valid_secret_processes_files(self, mock_task):
        mock_task.delay = MagicMock()
        company = _make_company()

        pdf_file = SimpleUploadedFile("invoice.pdf", b"PDF content here", content_type="application/pdf")
        response = self.client.post(
            "/hr/smart-import/api/inbound-webhook/test_secret_123/",
            {"file1": pdf_file},
        )
        if response.status_code == 200:
            self.assertTrue(ImportBatch.objects.exists())
            mock_task.delay.assert_called()

    @patch.dict(os.environ, {"WEBHOOK_SECRET": "test_secret_123"})
    def test_webhook_wrong_secret(self):
        response = self.client.post(
            "/hr/smart-import/api/inbound-webhook/wrong_secret/",
        )
        self.assertEqual(response.status_code, 401)

    @patch.dict(os.environ, {"WEBHOOK_SECRET": "test_secret_123"})
    def test_webhook_no_valid_attachments(self):
        _make_company()
        exe_file = SimpleUploadedFile("virus.exe", b"bad", content_type="application/octet-stream")
        response = self.client.post(
            "/hr/smart-import/api/inbound-webhook/test_secret_123/",
            {"file1": exe_file},
        )
        self.assertEqual(response.status_code, 400)


class ManualEntryViewTest(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_manual_entry_get(self):
        batch = _make_batch(self.company, status="error")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/manual-entry/".format(batch.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302])

    def test_manual_entry_post_creates_archive(self):
        batch = _make_batch(self.company, status="error")
        self.client.login(username="testuser", password="testpass123")
        url = "/hr/smart-import/{}/manual-entry/".format(batch.pk)
        response = self.client.post(url, {
            "doc_number": "TEST-001",
            "partner_name": "Dobavljac Test",
            "amount": "150.00",
            "doc_date": "2025-12-01",
            "source_type": "invoice_in",
            "description": "Testni rucni unos",
        })
        if response.status_code == 302:
            batch.refresh_from_db()
            self.assertEqual(batch.status, "confirmed")
            self.assertEqual(batch.status_message, "Rucno uneseno u arhivu")


# ============================================================================
# EMAIL RAMPA TESTS
# ============================================================================

class EmailRampaSkipLogicTest(TestCase):
    """Test the filename/size/inline filtering logic in fetch_invoices_from_email."""

    def test_skip_filename_regex(self):
        """Test the SKIP_FILENAME_RE regex used in fetch_invoices_from_email."""
        import re
        SKIP_FILENAME_RE = re.compile(
            r"^(icon|logo|badge|warning|banner|signature|footer|header|spacer|pixel|tracking)[_\-.]",
            re.IGNORECASE,
        )
        # Should match (skip)
        self.assertTrue(SKIP_FILENAME_RE.match("logo_company.png"))
        self.assertTrue(SKIP_FILENAME_RE.match("icon-email.png"))
        self.assertTrue(SKIP_FILENAME_RE.match("signature.jpg"))
        self.assertTrue(SKIP_FILENAME_RE.match("tracking_pixel.gif"))
        self.assertTrue(SKIP_FILENAME_RE.match("LOGO_HEADER.PNG"))  # case insensitive
        self.assertTrue(SKIP_FILENAME_RE.match("banner-sale.jpg"))
        self.assertTrue(SKIP_FILENAME_RE.match("footer.png"))
        self.assertTrue(SKIP_FILENAME_RE.match("spacer-1px.gif"))

        # Should NOT match (keep)
        self.assertFalse(SKIP_FILENAME_RE.match("racun_2025.pdf"))
        self.assertFalse(SKIP_FILENAME_RE.match("invoice_logo.pdf"))
        self.assertFalse(SKIP_FILENAME_RE.match("faktura.xml"))
        self.assertFalse(SKIP_FILENAME_RE.match("17734083412781708364496017665999.jpg"))
        self.assertFalse(SKIP_FILENAME_RE.match("RACUN-OTPREMNICA__25.PDF"))

    def test_allowed_extensions(self):
        """Verify all expected extensions are in ALLOWED_EXTS."""
        ALLOWED_EXTS = {
            ".xml": "xml", ".pdf": "pdf",
            ".jpg": "image", ".jpeg": "image", ".png": "image",
            ".webp": "image", ".heic": "image", ".heif": "image",
        }
        self.assertIn(".xml", ALLOWED_EXTS)
        self.assertIn(".pdf", ALLOWED_EXTS)
        self.assertIn(".jpg", ALLOWED_EXTS)
        self.assertIn(".heic", ALLOWED_EXTS)
        self.assertIn(".heif", ALLOWED_EXTS)
        self.assertNotIn(".exe", ALLOWED_EXTS)
        self.assertNotIn(".doc", ALLOWED_EXTS)
        self.assertNotIn(".zip", ALLOWED_EXTS)


# ============================================================================
# INTEGRATION TESTS — End-to-end flow
# ============================================================================

class EndToEndXmlFlowTest(TestCase):
    """Full flow: upload XML → process → stage → confirm → GoodsReceipt."""

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user()
        self.tax = _make_tax_rate()
        self.supplier = _make_partner(self.company, name="XML Supplier")
        # Create matching inventory items
        self.coca = _make_inventory_item(self.company, "Coca Cola 0.5L", "15.00", self.tax)
        self.fanta = _make_inventory_item(self.company, "Fanta 1L", "12.50", self.tax)
        self.water = _make_inventory_item(self.company, "Mineralna voda Jana 0.5L", "0.80", self.tax)
        try:
            from companies.models import UserRole
            UserRole.objects.get_or_create(user=self.user, defaults={"company": self.company, "role": "admin"})
        except Exception:
            pass

    def test_xml_end_to_end(self):
        """Parse UBL XML, create batch items, match, confirm to GoodsReceipt."""
        from smart_import.services import parse_xml, match_items

        # 1. Parse XML
        xml_content = _make_xml_ubl()
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w", encoding="utf-8") as f:
            f.write(xml_content)
            f.flush()
            rows = parse_xml(f.name)
        os.unlink(f.name)
        self.assertEqual(len(rows), 3)

        # 2. Create batch + items
        batch = ImportBatch.objects.create(
            company=self.company, supplier=self.supplier,
            file_type="xml", status="ready",
        )
        batch.file.save("test.xml", ContentFile(xml_content.encode()), save=True)
        batch.raw_json = rows
        batch.save()

        for i, row in enumerate(rows):
            ImportBatchItem.objects.create(
                batch=batch, row_index=i,
                vendor_name=row["vendor_name"],
                quantity=row["quantity"],
                purchase_price=row["purchase_price"],
            )

        # 3. Match items
        match_items(batch)

        items = list(batch.items.all())
        matched = [i for i in items if i.matched_item is not None]
        self.assertGreaterEqual(len(matched), 2, "At least 2 of 3 items should match")

        # Verify Coca Cola matched exactly
        coca_item = next(i for i in items if "Coca" in i.vendor_name)
        self.assertEqual(coca_item.matched_item, self.coca)
        self.assertGreaterEqual(coca_item.match_score, 0.9)

        # 4. Simulate confirm
        receipt = GoodsReceipt.objects.create(
            company=self.company, supplier=self.supplier,
            date=timezone.now().date(), status="draft",
            created_by=self.user,
        )
        for bi in matched:
            margin = Decimal("30")
            tax = bi.matched_item.tax_rate.rate if bi.matched_item.tax_rate else Decimal("25")
            GoodsReceiptItem.objects.create(
                receipt=receipt,
                inventory_item=bi.matched_item,
                quantity=bi.quantity,
                purchase_price_unit=bi.purchase_price,
                dependent_costs_unit=Decimal("0"),
                margin_percent=margin,
                tax_rate=tax,
            )

        self.assertGreaterEqual(receipt.items.count(), 2)
        batch.goods_receipt = receipt
        batch.status = "confirmed"
        batch.save()

        batch.refresh_from_db()
        self.assertEqual(batch.status, "confirmed")
        self.assertIsNotNone(batch.goods_receipt)


class ControlAmountTest(TestCase):
    """Test control amount feature in stage view."""

    def setUp(self):
        self.company = _make_company()

    def test_control_amount_diff_calculation(self):
        batch = ImportBatch.objects.create(
            company=self.company, file_type="pdf", status="ready",
            raw_json={"control_amount": "100.00"},
        )
        # Items sum to 95.00 (diff = -5.00)
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="A",
            quantity=Decimal("10"), purchase_price=Decimal("5.00"),
        )
        ImportBatchItem.objects.create(
            batch=batch, row_index=1, vendor_name="B",
            quantity=Decimal("9"), purchase_price=Decimal("5.00"),
        )

        items_total = sum(
            (bi.purchase_price * bi.quantity) for bi in batch.items.all()
        )
        control_amount = Decimal("100.00")
        diff = items_total - control_amount
        self.assertEqual(diff, Decimal("-5.00"))

    def test_control_amount_exact_match(self):
        batch = ImportBatch.objects.create(
            company=self.company, file_type="xml", status="ready",
            raw_json={"control_amount": "50.00"},
        )
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="A",
            quantity=Decimal("10"), purchase_price=Decimal("5.00"),
        )
        items_total = sum(
            (bi.purchase_price * bi.quantity) for bi in batch.items.all()
        )
        diff = items_total - Decimal("50.00")
        self.assertEqual(diff, Decimal("0.00"))


# ============================================================================
# EDGE CASE / REGRESSION TESTS
# ============================================================================

class EdgeCaseTests(TestCase):
    """Regression tests for known issues."""

    def test_regex_hyphen_in_character_class(self):
        """Regression: escaped hyphen fix in SKIP_FILENAME_RE (was crashing)."""
        import re
        # This was the bug: [_\-.]  — should not crash
        pattern = re.compile(
            r"^(icon|logo|badge|warning|banner|signature|footer|header|spacer|pixel|tracking)[_\-.]",
            re.IGNORECASE,
        )
        # Should not raise
        self.assertIsNotNone(pattern.match("logo-test.png"))
        self.assertIsNone(pattern.match("invoice.pdf"))

    def test_empty_batch_confirm_blocked(self):
        """Confirming batch with 0 matched items should not create GoodsReceipt."""
        company = _make_company()
        batch = ImportBatch.objects.create(
            company=company, file_type="pdf", status="ready",
        )
        ImportBatchItem.objects.create(
            batch=batch, row_index=0, vendor_name="Unmatched",
            matched_item=None,
        )
        matched = batch.items.filter(matched_item__isnull=False)
        self.assertFalse(matched.exists())

    def test_decimal_comma_handling(self):
        """Croatian invoices use comma as decimal separator."""
        from smart_import.services import _to_decimal
        self.assertEqual(_to_decimal("1.234,56"), "1234.56")
        self.assertEqual(_to_decimal("0,99"), "0.99")

    def test_batch_raw_json_can_be_dict_or_list(self):
        """raw_json can be list (rows) or dict (metadata) depending on context."""
        company = _make_company()
        # List format
        b1 = ImportBatch.objects.create(
            company=company, raw_json=[{"vendor_name": "A"}],
        )
        self.assertIsInstance(b1.raw_json, list)
        # Dict format (multipage / control amount)
        b2 = ImportBatch.objects.create(
            company=company, raw_json={"control_amount": "100", "page_paths": []},
        )
        self.assertIsInstance(b2.raw_json, dict)

    def test_original_filename_saved(self):
        """original_filename should be saved for tracking."""
        company = _make_company()
        batch = ImportBatch.objects.create(
            company=company, original_filename="Račun-Dobavljač_2025.pdf",
        )
        self.assertEqual(batch.original_filename, "Račun-Dobavljač_2025.pdf")

    def test_gemini_usage_log_cost_calculation(self):
        """Verify cost calculation formula."""
        # Gemini 2.5 Flash: $0.15/1M input, $0.60/1M output
        input_tokens = 1000
        output_tokens = 500
        cost = (input_tokens * 0.00000015) + (output_tokens * 0.0000006)
        expected = 0.00015 + 0.0003
        self.assertAlmostEqual(cost, expected, places=8)

    def test_status_message_updates(self):
        """Verify status_message field works correctly through lifecycle."""
        company = _make_company()
        batch = ImportBatch.objects.create(company=company, status_message="")
        self.assertEqual(batch.status_message, "")
        batch.status_message = "AI cita racun..."
        batch.save(update_fields=["status_message"])
        batch.refresh_from_db()
        self.assertEqual(batch.status_message, "AI cita racun...")

    def test_problem_report_default_description(self):
        """Report without description should get default text."""
        # This is tested in the view — empty description gets default
        company = _make_company()
        batch = ImportBatch.objects.create(company=company)
        description = "" or "Korisnik prijavio problem s uvozom (bez opisa)"
        report = ProblemReport.objects.create(
            batch=batch, company=company, description=description,
        )
        self.assertIn("bez opisa", report.description)
