"""Tests for Maintenance module."""
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.test import TestCase

from companies.models import Company
from maintenance.models import Asset, MaintenanceLog, MaintenanceSchedule


class AssetTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Maint Co", oib="13131313131")

    def test_asset_creation(self):
        asset = Asset.objects.create(
            company=self.company,
            name="Server Rack A",
            location="Datacenter 1",
        )
        self.assertEqual(asset.name, "Server Rack A")
        self.assertIn("Server Rack", str(asset))

    def test_maintenance_log(self):
        asset = Asset.objects.create(
            company=self.company,
            name="Printer HP",
        )
        log = MaintenanceLog.objects.create(
            asset=asset,
            description="Replaced toner",
        )
        self.assertEqual(log.asset, asset)
