"""Tests for Procurement module."""
from decimal import Decimal

from django.test import TestCase

from companies.models import Company
from procurement.models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Proc Co", oib="10101010101")

    def test_po_creation(self):
        po = PurchaseOrder.objects.create(
            company=self.company,
            po_number="PO-2026-001",
        )
        self.assertEqual(po.po_number, "PO-2026-001")
        self.assertIn("PO-2026-001", str(po))

    def test_po_item(self):
        po = PurchaseOrder.objects.create(
            company=self.company,
            po_number="PO-2026-002",
        )
        item = PurchaseOrderItem.objects.create(
            purchase_order=po,
            description="Office paper A4",
            quantity=Decimal("10"),
            unit_price=Decimal("5.0000"),
        )
        self.assertEqual(item.purchase_order, po)
        self.assertEqual(po.items.count(), 1)

    def test_auto_reorder_flag(self):
        po = PurchaseOrder.objects.create(
            company=self.company,
            po_number="PO-AUTO-001",
            notes="[AUTO-REORDER] Triggered by low stock",
        )
        self.assertIn("[AUTO-REORDER]", po.notes)
