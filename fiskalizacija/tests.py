"""Tests for Fiskalizacija module."""

from django.test import TestCase

from companies.models import Company
from fiskalizacija.models import FiscalConfig


class FiscalConfigTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Fiskal Co", oib="12121212121")

    def test_config_creation(self):
        config = FiscalConfig.objects.create(company=self.company)
        self.assertEqual(config.company, self.company)

    def test_config_str(self):
        config = FiscalConfig.objects.create(company=self.company)
        self.assertIn(self.company.name, str(config))
