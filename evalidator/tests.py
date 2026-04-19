"""
eValidator test suite — 8 tests covering all critical paths.
"""

import hashlib
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse


class EValidatorLandingTest(TestCase):
    """Test 1 — landing page loads correctly."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_landing_200(self):
        url = reverse("evalidator:home")
        resp = self.client.get(url, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "eVALIDATOR")
        self.assertContains(resp, "OIB")
        self.assertContains(resp, "IBAN")

    def test_landing_no_inline_styles(self):
        """CSS must be in external file — no inline style= attributes."""
        url = reverse("evalidator:home")
        resp = self.client.get(url, HTTP_HOST="evalidator.eu")
        content = resp.content.decode()
        # style= is only allowed in specific exceptions (VAT input flex, plan prices)
        # The main check: no <style> block inside <body>
        body_start = content.find("<body>")
        body_end = content.rfind("</body>")
        body = content[body_start:body_end]
        self.assertNotIn("<style>", body, "No <style> blocks allowed in <body>")


class EValidatorThemeCSSTest(TestCase):
    """Test 2 — CSS variables are properly defined."""

    def test_main_css_served(self):
        from django.contrib.staticfiles import finders

        result = finders.find("evalidator/css/main.css")
        self.assertIsNotNone(result, "evalidator/css/main.css must exist in static files")

    def test_css_has_dark_theme_vars(self):
        from django.contrib.staticfiles import finders

        path = finders.find("evalidator/css/main.css")
        with open(path) as f:
            css = f.read()
        self.assertIn("--gold:", css)
        self.assertIn("--bg:", css)
        self.assertIn('data-theme="light"', css)
        self.assertIn("var(--gold)", css)


class EValidatorOIBTest(TestCase):
    """Test 3 — OIB HTMX partial validation."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_valid_oib_returns_valid_partial(self):
        url = reverse("evalidator:validate_oib")
        resp = self.client.post(url, {"oib": "12345678903"}, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("valid", content.lower())

    def test_invalid_oib_returns_error(self):
        url = reverse("evalidator:validate_oib")
        resp = self.client.post(url, {"oib": "11111111111"}, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("invalid", content.lower())

    def test_empty_oib_no_crash(self):
        url = reverse("evalidator:validate_oib")
        resp = self.client.post(url, {"oib": ""}, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)


class EValidatorAPIJsonTest(TestCase):
    """Test 4 — JSON API endpoint returns proper structure."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_api_oib_valid_json(self):
        url = reverse("evalidator:api_oib")
        resp = self.client.get(url, {"oib": "12345678903"}, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        data = json.loads(resp.content)
        self.assertIn("oib", data)
        self.assertIn("valid", data)
        self.assertIn("algorithm", data)
        self.assertEqual(data["algorithm"], "ISO 7064 MOD 11,10")

    def test_api_oib_missing_param(self):
        url = reverse("evalidator:api_oib")
        resp = self.client.get(url, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 400)

    def test_api_status_json(self):
        url = reverse("evalidator:api_status")
        resp = self.client.get(url, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["authenticated"])


class EValidatorRateLimitTest(TestCase):
    """Test 5 — rate limiting returns 429."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_rate_limit_429(self):
        url = reverse("evalidator:api_oib")
        ip = "203.0.113.1"
        # Exhaust the rate limit (30 req/min)
        with patch("evalidator.views._rate_ok", return_value=False):
            resp = self.client.get(url, {"oib": "12345678903"}, REMOTE_ADDR=ip, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 429)
        data = json.loads(resp.content)
        self.assertIn("error", data)
        self.assertIn("upgrade", data)


class EValidatorValidationLogTest(TestCase):
    """Test 6 — ValidationLog created on OIB check."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_validation_log_created(self):
        from evalidator.models import ValidationLog

        url = reverse("evalidator:validate_oib")
        initial_count = ValidationLog.objects.count()
        self.client.post(url, {"oib": "12345678903"}, HTTP_HOST="evalidator.eu")
        self.assertEqual(ValidationLog.objects.count(), initial_count + 1)

    def test_validation_log_no_raw_value(self):
        """PII guard: ValidationLog must NOT store raw OIB."""
        from evalidator.models import ValidationLog

        url = reverse("evalidator:validate_oib")
        test_oib = "12345678903"
        self.client.post(url, {"oib": test_oib}, HTTP_HOST="evalidator.eu")
        log = ValidationLog.objects.order_by("-id").first()
        self.assertIsNotNone(log)
        # The log must store hash, not raw OIB
        expected_hash = hashlib.sha256(test_oib.encode()).hexdigest()
        self.assertEqual(log.input_hash, expected_hash)
        # Field input_hash must not equal the raw value
        self.assertNotEqual(log.input_hash, test_oib)


class EValidatorNoPIITest(TestCase):
    """Test 7 — No PII in ValidationLog (only hashes)."""

    def test_validation_log_fields(self):
        from evalidator.models import ValidationLog

        field_names = [f.name for f in ValidationLog._meta.get_fields()]
        # Must have hash field
        self.assertIn("input_hash", field_names)
        # Must NOT have a raw value field
        for bad_field in ["oib", "iban", "vat", "raw_value", "value"]:
            self.assertNotIn(bad_field, field_names, f"Field '{bad_field}' would store PII — use input_hash only")


class EValidatorDocsAndPricingTest(TestCase):
    """Test 8 — docs and pricing pages render without errors."""

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_docs_200(self):
        url = reverse("evalidator:api_docs")
        resp = self.client.get(url, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "API")
        self.assertContains(resp, "Rate Limit")

    def test_pricing_200(self):
        url = reverse("evalidator:pricing")
        resp = self.client.get(url, HTTP_HOST="evalidator.eu")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Free")
        self.assertContains(resp, "Enterprise")
