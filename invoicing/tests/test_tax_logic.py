"""Tests for invoicing/tax_logic.py — pure logic, no DB needed."""

from decimal import Decimal

from django.test import SimpleTestCase

from invoicing.tax_logic import (
    calculate_items,
    calculate_tax,
    check_kleinunternehmer_eligibility,
    get_applicable_rate,
    get_pdv_footer_note,
    get_tax_rates,
    get_tax_statuses,
    is_reverse_charge,
)


class TestCalculateTax(SimpleTestCase):
    def test_hr_standard(self):
        r = calculate_tax(Decimal("100"), country="HR")
        self.assertEqual(r["tax_rate"], Decimal("25"))
        self.assertEqual(r["tax_amount"], Decimal("25.00"))
        self.assertEqual(r["total"], Decimal("125.00"))
        self.assertEqual(r["tax_status"], "standard")

    def test_de_standard(self):
        r = calculate_tax(Decimal("100"), country="DE")
        self.assertEqual(r["tax_rate"], Decimal("19"))
        self.assertEqual(r["tax_amount"], Decimal("19.00"))
        self.assertEqual(r["total"], Decimal("119.00"))

    def test_explicit_rate(self):
        r = calculate_tax(Decimal("200"), tax_rate=Decimal("13"))
        self.assertEqual(r["tax_rate"], Decimal("13"))
        self.assertEqual(r["tax_amount"], Decimal("26.00"))

    def test_zero_rate_exempt(self):
        r = calculate_tax(Decimal("500"), tax_status="exempt")
        self.assertEqual(r["tax_rate"], Decimal("0"))
        self.assertEqual(r["tax_amount"], Decimal("0.00"))
        self.assertEqual(r["total"], Decimal("500.00"))

    def test_pausalac(self):
        r = calculate_tax(Decimal("100"), tax_status="pausalac")
        self.assertEqual(r["tax_rate"], Decimal("0"))
        self.assertEqual(r["tax_status"], "pausalac")

    def test_kleinunternehmer(self):
        r = calculate_tax(Decimal("100"), tax_status="kleinunternehmer")
        self.assertEqual(r["tax_rate"], Decimal("0"))

    def test_reverse_charge(self):
        r = calculate_tax(Decimal("1000"), tax_status="reverse_charge")
        self.assertEqual(r["tax_rate"], Decimal("0"))
        self.assertEqual(r["tax_status"], "reverse_charge")

    def test_reduced_hr(self):
        r = calculate_tax(Decimal("100"), tax_status="reduced", country="HR")
        self.assertEqual(r["tax_rate"], Decimal("13"))

    def test_reduced2_hr(self):
        r = calculate_tax(Decimal("100"), tax_status="reduced2", country="HR")
        self.assertEqual(r["tax_rate"], Decimal("5"))

    def test_reduced_de(self):
        r = calculate_tax(Decimal("100"), tax_status="reduced", country="DE")
        self.assertEqual(r["tax_rate"], Decimal("7"))

    def test_rounding(self):
        r = calculate_tax(Decimal("33.33"), tax_rate=Decimal("25"))
        # 33.33 * 0.25 = 8.3325 → rounds to 8.33
        self.assertEqual(r["tax_amount"], Decimal("8.33"))

    def test_zero_base(self):
        r = calculate_tax(Decimal("0"))
        self.assertEqual(r["total"], Decimal("0.00"))

    def test_unknown_country_falls_back_to_hr(self):
        r = calculate_tax(Decimal("100"), country="XX")
        self.assertEqual(r["tax_rate"], Decimal("25"))


class TestCalculateItems(SimpleTestCase):
    def test_single_item(self):
        items = [{"qty": 2, "price": "50", "tax_rate": 25}]
        result = calculate_items(items)
        self.assertEqual(result["subtotal"], Decimal("100"))
        self.assertEqual(result["tax_total"], Decimal("25"))
        self.assertEqual(result["total"], Decimal("125"))
        self.assertEqual(len(result["items"]), 1)

    def test_multiple_items(self):
        items = [
            {"qty": 1, "price": "100", "tax_rate": 25},
            {"qty": 2, "price": "50", "tax_status": "exempt"},
        ]
        result = calculate_items(items, country="HR")
        self.assertEqual(result["subtotal"], Decimal("200"))
        self.assertEqual(result["tax_total"], Decimal("25"))

    def test_empty_items(self):
        result = calculate_items([])
        self.assertEqual(result["subtotal"], Decimal("0"))
        self.assertEqual(result["total"], Decimal("0"))

    def test_de_items(self):
        items = [{"qty": 1, "price": "100"}]
        result = calculate_items(items, country="DE")
        self.assertEqual(result["items"][0]["tax_rate"], Decimal("19"))


class TestIsReverseCharge(SimpleTestCase):
    def _mock_company(self, vat_id="HR12345678901", country="HR"):
        class C:
            pass

        c = C()
        c.vat_id = vat_id
        c.country = country
        return c

    def test_cross_border_with_vat(self):
        co = self._mock_company(vat_id="HR12345678901", country="HR")
        self.assertTrue(is_reverse_charge(co, "DE123456789", "DE"))

    def test_same_country_no_reverse_charge(self):
        co = self._mock_company(vat_id="HR12345678901", country="HR")
        self.assertFalse(is_reverse_charge(co, "HR98765432109", "HR"))

    def test_no_company(self):
        self.assertFalse(is_reverse_charge(None, "DE123456789", "DE"))

    def test_no_company_vat(self):
        co = self._mock_company(vat_id="", country="HR")
        co.oib = ""
        self.assertFalse(is_reverse_charge(co, "DE123456789", "DE"))

    def test_no_client_vat(self):
        co = self._mock_company()
        self.assertFalse(is_reverse_charge(co, "", "DE"))

    def test_no_client_country(self):
        co = self._mock_company()
        self.assertFalse(is_reverse_charge(co, "DE123456789", ""))


class TestKleinunternehmer(SimpleTestCase):
    def test_eligible(self):
        result = check_kleinunternehmer_eligibility(None, 15000, 30000)
        self.assertTrue(result["eligible"])

    def test_prev_year_too_high(self):
        result = check_kleinunternehmer_eligibility(None, 25000)
        self.assertFalse(result["eligible"])
        self.assertIn("22000", result["reason"])

    def test_current_year_too_high(self):
        result = check_kleinunternehmer_eligibility(None, 10000, 55000)
        self.assertFalse(result["eligible"])
        self.assertIn("50000", result["reason"])

    def test_exact_prev_limit(self):
        result = check_kleinunternehmer_eligibility(None, 22000)
        self.assertTrue(result["eligible"])

    def test_no_current_estimate(self):
        result = check_kleinunternehmer_eligibility(None, 10000)
        self.assertTrue(result["eligible"])


class TestGetTaxRates(SimpleTestCase):
    def test_hr_rates(self):
        rates = get_tax_rates("HR")
        rate_values = [r["rate"] for r in rates]
        self.assertIn(Decimal("25"), rate_values)
        self.assertIn(Decimal("13"), rate_values)
        self.assertIn(Decimal("5"), rate_values)

    def test_de_rates(self):
        rates = get_tax_rates("DE")
        rate_values = [r["rate"] for r in rates]
        self.assertIn(Decimal("19"), rate_values)
        self.assertIn(Decimal("7"), rate_values)

    def test_returns_list_of_dicts(self):
        rates = get_tax_rates("HR")
        self.assertIsInstance(rates, list)
        for r in rates:
            self.assertIn("rate", r)
            self.assertIn("label", r)
            self.assertIn("status", r)


class TestGetTaxStatuses(SimpleTestCase):
    def test_returns_all(self):
        statuses = get_tax_statuses()
        values = [s["value"] for s in statuses]
        self.assertIn("standard", values)
        self.assertIn("pausalac", values)
        self.assertIn("kleinunternehmer", values)
        self.assertIn("reverse_charge", values)


class TestGetApplicableRate(SimpleTestCase):
    def _mock_company(self, pdv_status="standard", country="HR"):
        class C:
            pass

        c = C()
        c.pdv_status = pdv_status
        c.country = country
        return c

    def test_reverse_charge(self):
        rate, note = get_applicable_rate(None, reverse_charge=True)
        self.assertEqual(rate, Decimal("0"))
        self.assertEqual(note, "reverse_charge")

    def test_no_company(self):
        rate, note = get_applicable_rate(None, invoice_country="HR")
        self.assertEqual(rate, Decimal("25"))

    def test_pausalac(self):
        co = self._mock_company(pdv_status="pausalac")
        rate, note = get_applicable_rate(co)
        self.assertEqual(rate, Decimal("0"))
        self.assertEqual(note, "pausalac")

    def test_standard_hr(self):
        co = self._mock_company()
        rate, note = get_applicable_rate(co)
        self.assertEqual(rate, Decimal("25"))

    def test_de_company(self):
        co = self._mock_company(country="DE")
        rate, note = get_applicable_rate(co)
        self.assertEqual(rate, Decimal("19"))


class TestGetPdvFooterNote(SimpleTestCase):
    def test_reverse_charge_hr(self):
        note = get_pdv_footer_note(None, reverse_charge=True, lang="hr")
        self.assertIn("Reverse Charge", note)

    def test_reverse_charge_de(self):
        note = get_pdv_footer_note(None, reverse_charge=True, lang="de")
        self.assertIn("Reverse Charge", note)
        self.assertIn("Steuerschuldnerschaft", note)

    def test_pausalac_note(self):
        class C:
            pdv_status = "pausalac"

        note = get_pdv_footer_note(C())
        self.assertIn("pausalni", note.lower())

    def test_kleinunternehmer_note(self):
        class C:
            pdv_status = "kleinunternehmer"

        note = get_pdv_footer_note(C())
        self.assertIn("§19", note)

    def test_standard_no_note(self):
        class C:
            pdv_status = "standard"

        note = get_pdv_footer_note(C())
        self.assertEqual(note, "")

    def test_no_company(self):
        note = get_pdv_footer_note(None)
        self.assertEqual(note, "")
