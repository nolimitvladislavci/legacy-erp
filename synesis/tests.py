"""Tests for Synesis integration module."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from companies.models import Company
from synesis.models import SynesisConfig, SynesisLog

User = get_user_model()


class SynesisConfigTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Synesis Co", oib="11111111111")
        self.config = SynesisConfig.objects.create(company=self.company)

    def test_config_creation(self):
        self.assertIsNotNone(self.config.api_token)
        self.assertTrue(len(self.config.api_token) > 10)

    def test_config_unique_per_company(self):
        """Each company can only have one SynesisConfig."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            SynesisConfig.objects.create(company=self.company)

    def test_token_uniqueness(self):
        co2 = Company.objects.create(name="Test Co 2", oib="22222222222")
        cfg2 = SynesisConfig.objects.create(company=co2)
        self.assertNotEqual(self.config.api_token, cfg2.api_token)

    def test_default_paths(self):
        self.assertIn("Storage.mdb", self.config.storage_db_path)
        self.assertIn("Journal.mdb", self.config.journal_db_path)


class SynesisLogTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Log Co", oib="33333333333")

    def test_log_creation(self):
        log = SynesisLog.objects.create(
            company=self.company,
            sync_type="partners",
            records_received=100,
            records_created=80,
            records_updated=20,
        )
        self.assertEqual(log.records_received, 100)
        self.assertEqual(log.sync_type, "partners")


class SynesisAPITest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="API Co", oib="44444444444")
        self.config = SynesisConfig.objects.create(company=self.company)
        self.factory = RequestFactory()

    def test_import_api_no_token(self):
        """API should reject requests without token."""
        from synesis.views import synesis_import_api

        request = self.factory.post("/api/synesis/import/", content_type="application/json")
        response = synesis_import_api(request)
        self.assertIn(response.status_code, [401, 403])

    def test_import_api_invalid_token(self):
        from synesis.views import synesis_import_api

        request = self.factory.post(
            "/api/synesis/import/", content_type="application/json", HTTP_AUTHORIZATION="Bearer invalid-token-123"
        )
        response = synesis_import_api(request)
        self.assertIn(response.status_code, [401, 403])


# ═══ JSON Import Tests ═══════════════════════════════════════════════

import json as _json
import os
import tempfile


class SynesisJSONImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="JSON Test Co", oib="88888888801")

    def _write_json(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            _json.dump(data, f)
        self.addCleanup(lambda: os.unlink(path) if os.path.exists(path) else None)
        return path

    def test_json_read_single_type(self):
        from synesis.mdb_service import read_json_file

        path = self._write_json({"type": "partners", "data": [{"PARTNER_NAME": "Test"}]})
        result = read_json_file(path)
        self.assertEqual(len(result["partners"]), 1)

    def test_json_read_multi_type(self):
        from synesis.mdb_service import read_json_file

        path = self._write_json({"partners": [{"PARTNER_NAME": "P1"}], "items": [{"ITEM_NAME": "I1"}]})
        result = read_json_file(path)
        self.assertEqual(len(result["partners"]), 1)
        self.assertEqual(len(result["items"]), 1)

    def test_json_raw_array_detection(self):
        from synesis.mdb_service import read_json_file

        path = self._write_json([{"PARTNER_NAME": "R1", "PARTNER_ID": "1"}])
        result = read_json_file(path)
        self.assertEqual(len(result["partners"]), 1)

    def test_json_summary(self):
        from synesis.mdb_service import json_summary

        path = self._write_json({"partners": [{}] * 5, "items": [{}] * 10})
        s = json_summary(path)
        self.assertEqual(s["PARTNERS"], 5)
        self.assertEqual(s["ITEMS"], 10)

    def test_json_partners_preview(self):
        from synesis.mdb_service import json_partners_preview

        path = self._write_json(
            {
                "partners": [
                    {"PARTNER_ID": "1", "PARTNER_NAME": "Konjik", "PARTNER_VATNUMBER": "12345678901"},
                ]
            }
        )
        p = json_partners_preview(path)
        self.assertEqual(p[0]["name"], "Konjik")
        self.assertEqual(p[0]["oib"], "12345678901")

    def test_json_import_no_duplicates(self):
        from synesis.mdb_service import import_json_to_erp

        path = self._write_json(
            {
                "partners": [
                    {"PARTNER_NAME": "NoDup", "PARTNER_ID": "1", "PARTNER_VATNUMBER": "SYN-ND1"},
                ]
            }
        )
        import_json_to_erp(path, self.company)
        r2 = import_json_to_erp(path, self.company)
        self.assertEqual(r2.get("partners", {}).get("created", 0), 0)

    def test_json_import_items(self):
        from synesis.mdb_service import import_json_to_erp

        path = self._write_json(
            {
                "items": [
                    {"ITEM_ID": "777", "ITEM_NAME": "Pecivo", "ITEM_MEASURE": "kom", "ITEM_NETPRICE": "1.50"},
                ]
            }
        )
        r = import_json_to_erp(path, self.company)
        self.assertGreaterEqual(r.get("items", {}).get("created", 0), 1)

    def test_json_empty_handled(self):
        from synesis.mdb_service import import_json_to_erp

        path = self._write_json({})
        r = import_json_to_erp(path, self.company)
        self.assertEqual(r, {})
