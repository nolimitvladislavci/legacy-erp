"""Tests for Traceability module."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from traceability.models import ProductTrace, TraceEvent


class TraceabilityTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Trace Co", oib="15151515151")
        from marketplace.models import MarketplaceProduct

        self.product = MarketplaceProduct.objects.create(
            seller_company=self.company,
            name="Organic Cheese",
            slug="organic-cheese-test",
            unit_price=Decimal("10.00"),
        )

    def test_product_trace(self):
        trace = ProductTrace.objects.create(
            product=self.product,
            producer_company=self.company,
            producer_name="OPG Trace",
        )
        self.assertEqual(trace.producer_name, "OPG Trace")

    def test_trace_event(self):
        trace = ProductTrace.objects.create(
            product=self.product,
            producer_company=self.company,
            producer_name="OPG Milk",
        )
        event = TraceEvent.objects.create(
            trace=trace,
            event_type="received",
            timestamp=timezone.now(),
        )
        self.assertEqual(event.trace, trace)
        self.assertEqual(trace.events.count(), 1)
