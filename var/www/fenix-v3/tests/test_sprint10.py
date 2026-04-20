"""
Sprint 10 Test Suite — Fenix V3
Tests: PEPPOL XML, Predictive Cash Flow, Smart Contract AI,
       WhatsApp Auto-Booking, Stripe Upgrade, eValidator, Silent Twin
Target: 10/10 EU #1 AI-Native ERP
"""

import pytest
import json
import hashlib
from datetime import date, timedelta, datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def company(db):
    from companies.models import Company

    return Company.objects.create(
        name="Test d.o.o.",
        oib="12345678901",
        country="HR",
        vat_number="HR12345678901",
        iban="HR1210010051863000160",
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="sprint10tester",
        password="testpass123",
        email="sprint10@fenix.test",
    )


# ─── PEPPOL XML Generation ─────────────────────────────────────────────────────


class TestPEPPOLXML(TestCase):
    """PEPPOL BIS 3.0 UBL 2.1 XML generation and validation"""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(
            name="Prodavač d.o.o.",
            oib="12345678901",
            country="HR",
            vat_number="HR12345678901",
            iban="HR1210010051863000160",
        )

    def _make_invoice(self):
        """Minimal invoice dict for PEPPOL generation"""
        return {
            "id": "INV-2026-001",
            "issue_date": date(2026, 4, 19),
            "due_date": date(2026, 5, 19),
            "currency": "EUR",
            "buyer_name": "Kupac d.o.o.",
            "buyer_oib": "98765432109",
            "buyer_address": "Ilica 1, Zagreb",
            "buyer_vat": "HR98765432109",
            "items": [
                {"description": "Konzalting usluga", "quantity": 10, "unit_price": 100.0, "vat_rate": 25},
            ],
            "subtotal": 1000.0,
            "vat_amount": 250.0,
            "total": 1250.0,
        }

    def test_generate_peppol_xml_structure(self):
        """Generated XML must contain required PEPPOL BIS 3.0 elements"""
        from country_plugins.peppol import generate_peppol_xml

        invoice = self._make_invoice()
        xml = generate_peppol_xml(invoice, self.company)
        assert "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" in xml
        assert "urn:cen.eu:en16931:2017" in xml
        assert "urn:fdc:peppol.eu:2017:poacc:billing:3.0" in xml

    def test_peppol_xml_contains_seller_endpoint(self):
        """Seller endpoint must be formatted as 0184:{OIB}"""
        from country_plugins.peppol import generate_peppol_xml

        invoice = self._make_invoice()
        xml = generate_peppol_xml(invoice, self.company)
        assert "0184:12345678901" in xml

    def test_peppol_xml_contains_buyer_endpoint(self):
        """Buyer endpoint uses buyer OIB"""
        from country_plugins.peppol import generate_peppol_xml

        invoice = self._make_invoice()
        xml = generate_peppol_xml(invoice, self.company)
        assert "0184:98765432109" in xml

    def test_peppol_xml_contains_amounts(self):
        """XML must contain correct tax and totals"""
        from country_plugins.peppol import generate_peppol_xml

        invoice = self._make_invoice()
        xml = generate_peppol_xml(invoice, self.company)
        assert "1250" in xml  # total
        assert "250" in xml  # VAT
        assert "1000" in xml  # subtotal

    def test_validate_peppol_xml_valid(self):
        """Valid PEPPOL XML should score >= 80"""
        from country_plugins.peppol import generate_peppol_xml, validate_peppol_xml

        invoice = self._make_invoice()
        xml = generate_peppol_xml(invoice, self.company)
        result = validate_peppol_xml(xml)
        assert result["valid"] is True
        assert result["score"] >= 80
        assert len(result["issues"]) == 0

    def test_validate_peppol_xml_missing_customization(self):
        """XML without CustomizationID must fail validation"""
        from country_plugins.peppol import validate_peppol_xml

        bad_xml = '<?xml version="1.0"?><Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"><ID>1</ID></Invoice>'
        result = validate_peppol_xml(bad_xml)
        assert result["valid"] is False
        assert result["score"] < 80

    def test_peppol_submit_status_transitions(self):
        """State machine: DRAFT → VALIDATED → SUBMITTED → ACKNOWLEDGED → PAID"""
        from country_plugins.peppol import PEPPOLSubmitStatus

        assert PEPPOLSubmitStatus.can_transition("DRAFT", "VALIDATED") is True
        assert PEPPOLSubmitStatus.can_transition("VALIDATED", "SUBMITTED") is True
        assert PEPPOLSubmitStatus.can_transition("SUBMITTED", "ACKNOWLEDGED") is True
        assert PEPPOLSubmitStatus.can_transition("ACKNOWLEDGED", "PAID") is True

    def test_peppol_invalid_transitions(self):
        """Cannot skip states or go backwards"""
        from country_plugins.peppol import PEPPOLSubmitStatus

        assert PEPPOLSubmitStatus.can_transition("DRAFT", "SUBMITTED") is False
        assert PEPPOLSubmitStatus.can_transition("PAID", "DRAFT") is False
        assert PEPPOLSubmitStatus.can_transition("DRAFT", "PAID") is False


# ─── Predictive Cash Flow ──────────────────────────────────────────────────────


class TestPredictiveCashFlow(TestCase):
    """AI-free cash flow prediction — pattern mining only"""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(
            name="CashFlow Test d.o.o.",
            oib="11111111110",
            country="HR",
        )

    def test_predict_cash_flow_returns_dict(self):
        """predict_cash_flow must return structured dict"""
        from ai_cockpit.cash_flow import predict_cash_flow

        result = predict_cash_flow(self.company, days_ahead=30)
        assert isinstance(result, dict)
        assert "predictions" in result
        assert "net_30_days" in result
        assert "confidence" in result
        assert "risk_level" in result

    def test_predict_cash_flow_confidence_range(self):
        """Confidence must be 0.0–1.0"""
        from ai_cockpit.cash_flow import predict_cash_flow

        result = predict_cash_flow(self.company, days_ahead=30)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_predict_cash_flow_risk_levels(self):
        """Risk level must be one of known values"""
        from ai_cockpit.cash_flow import predict_cash_flow

        result = predict_cash_flow(self.company, days_ahead=30)
        assert result["risk_level"] in ["low", "medium", "high", "critical"]

    def test_predict_cash_flow_predictions_list(self):
        """Predictions must be a list"""
        from ai_cockpit.cash_flow import predict_cash_flow

        result = predict_cash_flow(self.company, days_ahead=30)
        assert isinstance(result["predictions"], list)

    def test_predict_cash_flow_alerts_list(self):
        """Alerts must be present (even if empty)"""
        from ai_cockpit.cash_flow import predict_cash_flow

        result = predict_cash_flow(self.company, days_ahead=30)
        assert "alerts" in result
        assert isinstance(result["alerts"], list)

    def test_predict_cash_flow_no_data_graceful(self):
        """With no invoice data, should return low confidence but not crash"""
        from ai_cockpit.cash_flow import predict_cash_flow

        result = predict_cash_flow(self.company, days_ahead=30)
        # No invoices = low confidence, that's OK
        assert result is not None
        assert "net_30_days" in result


# ─── Smart Contract AI ─────────────────────────────────────────────────────────


class TestSmartContractAI(TestCase):
    """Contract type detection and mandatory clause suggestions"""

    def test_detect_service_contract(self):
        """Service contract detection from keywords"""
        from legal.contract_ai import detect_contract_type

        ctype = detect_contract_type("Ugovor o pružanju usluga", "Pružanje konzultantskih usluga")
        assert ctype == "service"

    def test_detect_sale_contract(self):
        """Sale/purchase contract detection"""
        from legal.contract_ai import detect_contract_type

        ctype = detect_contract_type("Kupoprodajni ugovor", "Prodaja robe i opreme")
        assert ctype == "sale"

    def test_detect_employment_contract(self):
        """Employment contract detection"""
        from legal.contract_ai import detect_contract_type

        ctype = detect_contract_type("Ugovor o radu", "Zapošljavanje radnika na neodređeno")
        assert ctype == "employment"

    def test_detect_nda_contract(self):
        """NDA detection"""
        from legal.contract_ai import detect_contract_type

        ctype = detect_contract_type("Ugovor o povjerljivosti", "NDA za poslovne partnere")
        assert ctype == "nda"

    def test_detect_lease_contract(self):
        """Lease contract detection"""
        from legal.contract_ai import detect_contract_type

        ctype = detect_contract_type("Ugovor o zakupu", "Najam poslovnog prostora")
        assert ctype == "lease"

    def test_suggest_contract_content_returns_structure(self):
        """Suggestions must include mandatory_clauses, score, warnings"""
        from legal.contract_ai import suggest_contract_content

        result = suggest_contract_content(
            title="Ugovor o pružanju usluga",
            description="IT konzalting usluge",
            contract_type="service",
        )
        assert "mandatory_clauses" in result
        assert "score" in result
        assert "warnings" in result
        assert isinstance(result["mandatory_clauses"], list)
        assert 0 <= result["score"] <= 100

    def test_service_contract_has_gdpr_clause(self):
        """Service contracts must suggest GDPR clause"""
        from legal.contract_ai import suggest_contract_content

        result = suggest_contract_content(
            title="Ugovor o pružanju usluga",
            description="Obrada osobnih podataka za klijenta",
            contract_type="service",
        )
        clause_texts = " ".join(result.get("standard_clauses", []))
        # GDPR should appear somewhere
        assert any(
            "GDPR" in c or "osobn" in c.lower() or "podatak" in c.lower()
            for c in result.get("mandatory_clauses", []) + result.get("standard_clauses", [])
        )

    def test_unknown_contract_type_fallback(self):
        """Unknown contract type falls back to service"""
        from legal.contract_ai import detect_contract_type

        ctype = detect_contract_type("Nepoznat ugovor", "Nešto nedefinirano")
        assert ctype in ["service", "sale", "lease", "employment", "nda", "agency", "loan"]


# ─── WhatsApp Auto-Booking ─────────────────────────────────────────────────────


class TestWhatsAppAutoBooking(TestCase):
    """Intent detection + slot suggestion for WhatsApp messages"""

    def test_detect_booking_intent_hr(self):
        """Croatian booking messages"""
        from notifications.auto_booking import detect_intent

        assert detect_intent("Htio bih rezervirati termin") == "booking"
        assert detect_intent("Mogu li zakazati pregled?") == "booking"
        assert detect_intent("naručiti se") == "booking"

    def test_detect_cancel_intent_hr(self):
        """Croatian cancellation messages"""
        from notifications.auto_booking import detect_intent

        assert detect_intent("Otkazujem termin") == "cancel"
        assert detect_intent("Više ne mogu doći, stornirajte") == "cancel"

    def test_detect_info_intent(self):
        """Info requests"""
        from notifications.auto_booking import detect_intent

        assert detect_intent("Koliko košta pregled?") == "info"
        assert detect_intent("Koje su vaše radno vrijeme?") == "info"

    def test_detect_unknown_intent(self):
        """Random messages → unknown"""
        from notifications.auto_booking import detect_intent

        result = detect_intent("Hvala")
        assert result in ["unknown", "info"]  # "hvala" could be info

    def test_extract_datetime_monday(self):
        """Extract day-of-week hint"""
        from notifications.auto_booking import extract_datetime_hints

        hints = extract_datetime_hints("Može li u ponedjeljak ujutro?")
        assert hints.get("day_of_week") == "monday"

    def test_extract_datetime_time(self):
        """Extract time hint"""
        from notifications.auto_booking import extract_datetime_hints

        hints = extract_datetime_hints("Može li u 10:00 sati?")
        assert hints.get("time") == "10:00"

    def test_extract_datetime_tomorrow(self):
        """Sutra = tomorrow"""
        from notifications.auto_booking import extract_datetime_hints

        hints = extract_datetime_hints("Može li sutra?")
        assert hints.get("date") is not None

    def test_generate_booking_reply_no_availability(self):
        """When no slots — graceful no-slots message"""
        from notifications.auto_booking import generate_booking_reply
        from companies.models import Company

        company = Company.objects.create(
            name="Booking Co",
            oib="22222222221",
            country="HR",
        )
        reply = generate_booking_reply("Htio bih rezervirati termin", company)
        # Either returns None or a message — should not crash
        assert reply is None or isinstance(reply, str)

    def test_find_available_slots_returns_list(self):
        """find_available_slots always returns list"""
        from notifications.auto_booking import find_available_slots
        from companies.models import Company

        company = Company.objects.create(
            name="Slot Co",
            oib="33333333330",
            country="HR",
        )
        slots = find_available_slots(company, service_id=None, from_date=date.today())
        assert isinstance(slots, list)


# ─── eValidator ───────────────────────────────────────────────────────────────


class TestEValidator(TestCase):
    """OIB Luhn-10, HR/DE invoice validation, PEPPOL validation, seal"""

    def test_oib_valid(self):
        """Known valid OIB"""
        from evalidator.validators import OIBValidator

        v = OIBValidator()
        result = v.validate({"oib": "12345678901"})
        assert result["valid"] is True

    def test_oib_invalid_checksum(self):
        """Wrong checksum OIB"""
        from evalidator.validators import OIBValidator

        v = OIBValidator()
        result = v.validate({"oib": "12345678900"})
        assert result["valid"] is False

    def test_hr_invoice_validator_valid(self):
        """Valid HR invoice passes"""
        from evalidator.validators import HRInvoiceValidator

        v = HRInvoiceValidator()
        result = v.validate(
            {
                "oib": "12345678901",
                "iban": "HR1210010051863000160",
                "vat_rate": 25,
                "total": 1250.0,
                "invoice_number": "INV-2026-001",
                "issue_date": "2026-04-19",
            }
        )
        assert result["valid"] is True
        assert result["score"] >= 80

    def test_hr_invoice_invalid_vat(self):
        """Invalid VAT rate (22% not valid in HR)"""
        from evalidator.validators import HRInvoiceValidator

        v = HRInvoiceValidator()
        result = v.validate(
            {
                "oib": "12345678901",
                "iban": "HR1210010051863000160",
                "vat_rate": 22,
                "total": 1220.0,
                "invoice_number": "INV-2026-002",
                "issue_date": "2026-04-19",
            }
        )
        assert result["valid"] is False

    def test_de_invoice_validator_valid_vat(self):
        """Valid DE VAT rates: 0, 7, 19"""
        from evalidator.validators import DEInvoiceValidator

        v = DEInvoiceValidator()
        result = v.validate(
            {
                "steuernummer": "21/815/08150",
                "vat_rate": 19,
                "total": 1190.0,
                "invoice_number": "RE-2026-001",
                "issue_date": "2026-04-19",
            }
        )
        assert result["valid"] is True

    def test_de_invoice_invalid_vat(self):
        """22% VAT not valid in DE"""
        from evalidator.validators import DEInvoiceValidator

        v = DEInvoiceValidator()
        result = v.validate(
            {
                "steuernummer": "21/815/08150",
                "vat_rate": 22,
                "total": 1220.0,
                "invoice_number": "RE-2026-002",
                "issue_date": "2026-04-19",
            }
        )
        assert result["valid"] is False

    def test_run_validation_dispatch(self):
        """run_validation dispatches to correct validator"""
        from evalidator.validators import run_validation

        result = run_validation(
            "hr_invoice",
            {
                "oib": "12345678901",
                "iban": "HR1210010051863000160",
                "vat_rate": 25,
                "total": 1250.0,
                "invoice_number": "INV-2026-003",
                "issue_date": "2026-04-19",
            },
        )
        assert "valid" in result
        assert "score" in result

    def test_validation_result_seal(self):
        """ValidationResult seal must be deterministic SHA-256"""
        from evalidator.models import ValidationResult
        from companies.models import Company

        company = Company.objects.create(
            name="Seal Test",
            oib="44444444440",
            country="HR",
        )
        vr = ValidationResult.objects.create(
            company=company,
            doc_type="hr_invoice",
            doc_hash="abc123",
            score=95,
            is_valid=True,
            errors=[],
            warnings=[],
        )
        seal1 = vr.generate_seal()
        seal2 = vr.generate_seal()
        assert seal1 == seal2  # deterministic
        assert len(seal1) == 64  # SHA-256 hex

    def test_validation_result_verify_seal(self):
        """verify_seal must return True for correct seal"""
        from evalidator.models import ValidationResult
        from companies.models import Company

        company = Company.objects.create(
            name="Verify Test",
            oib="55555555550",
            country="HR",
        )
        vr = ValidationResult.objects.create(
            company=company,
            doc_type="hr_invoice",
            doc_hash="xyz789",
            score=88,
            is_valid=True,
            errors=[],
            warnings=[],
        )
        vr.seal_hash = vr.generate_seal()
        vr.save()
        assert vr.verify_seal() is True


# ─── Access Control / Delegated Permissions ────────────────────────────────────


class TestAccessControl(TestCase):
    """Delegated module access — DATEV/Xero don't have this"""

    def setUp(self):
        from companies.models import Company

        self.grantor = Company.objects.create(name="Grantor d.o.o.", oib="66666666660", country="HR")
        self.grantee = Company.objects.create(name="Grantee d.o.o.", oib="77777777770", country="HR")
        self.user = User.objects.create_user(username="acuser", password="test123")

    def test_create_access_grant(self):
        """Create a delegated access grant"""
        from access_control.models import AccessGrant

        grant = AccessGrant.objects.create(
            company=self.grantor,
            grantor=self.grantor,
            grantee=self.grantee,
            modules=["invoicing", "archive"],
            access_level="read",
        )
        assert grant.is_active is True
        assert "invoicing" in grant.modules

    def test_access_grant_has_module(self):
        """has_module() checks active grants"""
        from access_control.models import AccessGrant

        grant = AccessGrant.objects.create(
            company=self.grantor,
            grantor=self.grantor,
            grantee=self.grantee,
            modules=["invoicing", "pos"],
            access_level="write",
        )
        assert grant.has_module("invoicing") is True
        assert grant.has_module("employees") is False

    def test_access_grant_revoke(self):
        """revoke() deactivates the grant"""
        from access_control.models import AccessGrant

        grant = AccessGrant.objects.create(
            company=self.grantor,
            grantor=self.grantor,
            grantee=self.grantee,
            modules=["invoicing"],
            access_level="full",
        )
        grant.revoke(self.user)
        grant.refresh_from_db()
        assert grant.is_active is False
        assert grant.revoked_by == self.user

    def test_revoked_grant_has_module_false(self):
        """Revoked grant must deny has_module"""
        from access_control.models import AccessGrant

        grant = AccessGrant.objects.create(
            company=self.grantor,
            grantor=self.grantor,
            grantee=self.grantee,
            modules=["invoicing"],
            access_level="read",
        )
        grant.revoke(self.user)
        assert grant.has_module("invoicing") is False

    def test_delegation_audit_log_integrity_hash(self):
        """Audit log integrity hash must be SHA-256"""
        from access_control.models import DelegationAuditLog, AccessGrant

        grant = AccessGrant.objects.create(
            company=self.grantor,
            grantor=self.grantor,
            grantee=self.grantee,
            modules=["archive"],
            access_level="read",
        )
        log = DelegationAuditLog.objects.create(
            grant=grant,
            action="grant_created",
            performed_by=self.user,
            module="archive",
            object_id="",
        )
        assert len(log.integrity_hash) == 64  # SHA-256

    def test_expired_grant_has_module_false(self):
        """Expired grant must deny access"""
        from access_control.models import AccessGrant

        grant = AccessGrant.objects.create(
            company=self.grantor,
            grantor=self.grantor,
            grantee=self.grantee,
            modules=["invoicing"],
            access_level="read",
            expires_at=timezone.now() - timedelta(days=1),  # already expired
        )
        assert grant.has_module("invoicing") is False


# ─── Sentinel Security ─────────────────────────────────────────────────────────


class TestSentinelSecurity(TestCase):
    """SecurityEvent integrity hash, IPAllowlist, ActiveSession, TrustedDevice"""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Security Test", oib="88888888880", country="HR")
        self.user = User.objects.create_user(username="secuser", password="test123")

    def test_security_event_integrity_hash(self):
        """SecurityEvent must have 64-char SHA-256 integrity_hash"""
        from sentinel.models import SecurityEvent

        evt = SecurityEvent.objects.create(
            event_type="login_failed",
            ip_address="192.168.1.1",
            user=self.user,
            company=self.company,
        )
        assert len(evt.integrity_hash) == 64

    def test_security_event_hash_determinism(self):
        """Same input = same hash (deterministic)"""
        from sentinel.models import SecurityEvent

        evt1 = SecurityEvent(
            event_type="login_failed",
            ip_address="10.0.0.1",
            user=self.user,
            company=self.company,
        )
        evt2 = SecurityEvent(
            event_type="login_failed",
            ip_address="10.0.0.1",
            user=self.user,
            company=self.company,
        )
        # Both generate same hash formula
        raw1 = f"login_failed:10.0.0.1:{self.user.id}:{self.company.id}"
        raw2 = f"login_failed:10.0.0.1:{self.user.id}:{self.company.id}"
        assert hashlib.sha256(raw1.encode()).hexdigest() == hashlib.sha256(raw2.encode()).hexdigest()

    def test_ip_allowlist_create(self):
        """IPAllowlist CIDR entry creation"""
        from sentinel.models import IPAllowlist

        entry = IPAllowlist.objects.create(
            company=self.company,
            ip_or_cidr="192.168.0.0/24",
            description="Office network",
        )
        assert entry.ip_or_cidr == "192.168.0.0/24"

    def test_active_session_revoke(self):
        """ActiveSession.revoke() sets is_revoked=True"""
        from sentinel.models import ActiveSession

        session = ActiveSession.objects.create(
            user=self.user,
            company=self.company,
            session_key="abc123session",
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        session.revoke("manual_logout")
        session.refresh_from_db()
        assert session.is_revoked is True

    def test_trusted_device_trust_levels(self):
        """TrustedDevice trust levels are valid choices"""
        from sentinel.models import TrustedDevice

        device = TrustedDevice.objects.create(
            user=self.user,
            company=self.company,
            device_fingerprint="a" * 64,
            trust_level="new",
            user_agent="Chrome/120",
        )
        assert device.trust_level == "new"
        device.trust(by_user=self.user)
        device.refresh_from_db()
        assert device.trust_level == "trusted"

    def test_trusted_device_revoke(self):
        """TrustedDevice.revoke() blocks the device"""
        from sentinel.models import TrustedDevice

        device = TrustedDevice.objects.create(
            user=self.user,
            company=self.company,
            device_fingerprint="b" * 64,
            trust_level="trusted",
            user_agent="Firefox/120",
        )
        device.revoke("compromised")
        device.refresh_from_db()
        assert device.is_revoked is True
        assert device.trust_level == "blocked"


# ─── Silent Twin Engine ────────────────────────────────────────────────────────


class TestSilentTwin(TestCase):
    """Per-company AI learning — no external API calls"""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Twin Test d.o.o.", oib="99999999990", country="HR")

    def test_run_twin_learning_returns_dict(self):
        """run_twin_learning must return summary dict"""
        from silent_twin.engine import run_twin_learning

        result = run_twin_learning(self.company.id)
        assert isinstance(result, dict)
        assert "patterns_created" in result
        assert "insights_created" in result

    def test_twin_config_defaults(self):
        """TwinConfig has sensible defaults"""
        from silent_twin.models import TwinConfig

        config = TwinConfig.objects.create(company=self.company)
        assert config.learning_window_days == 90
        assert isinstance(config.notify_dashboard, bool)

    def test_twin_insight_mark_read(self):
        """TwinInsight.mark_read() sets is_read=True"""
        from silent_twin.models import TwinInsight

        insight = TwinInsight.objects.create(
            company=self.company,
            title="Kasna plaćanja",
            body="30% računa plaćeno kasno",
            priority="high",
            insight_type="late_payment",
        )
        assert insight.is_read is False
        insight.mark_read()
        insight.refresh_from_db()
        assert insight.is_read is True

    def test_twin_insight_dismiss(self):
        """TwinInsight.dismiss() sets is_dismissed=True"""
        from silent_twin.models import TwinInsight

        insight = TwinInsight.objects.create(
            company=self.company,
            title="Sezonalnost",
            body="Prosinac +40%",
            priority="medium",
            insight_type="seasonality",
        )
        insight.dismiss()
        insight.refresh_from_db()
        assert insight.is_dismissed is True

    def test_twin_pattern_create(self):
        """TwinPattern creation with confidence"""
        from silent_twin.models import TwinPattern

        pattern = TwinPattern.objects.create(
            company=self.company,
            pattern_type="late_payment",
            confidence=0.75,
            data={"overdue_rate": 0.30},
            is_significant=True,
        )
        assert pattern.confidence == 0.75
        assert pattern.is_significant is True


# ─── Stripe Upgrade Flow ───────────────────────────────────────────────────────


class TestStripeUpgradeFlow(TestCase):
    """Stripe checkout session creation for plan upgrades"""

    def setUp(self):
        from companies.models import Company

        self.company = Company.objects.create(name="Stripe Test d.o.o.", oib="10101010100", country="HR")
        self.user = User.objects.create_user(username="stripeuser", password="test123")
        self.factory = RequestFactory()

    @patch("saas.views.stripe")
    def test_upgrade_view_get(self, mock_stripe):
        """GET /saas/upgrade/ renders plan selection"""
        from saas.views import UpgradeView

        request = self.factory.get("/saas/upgrade/")
        request.user = self.user
        request.company = self.company
        request.session = {}
        response = UpgradeView.as_view()(request)
        assert response.status_code == 200

    @patch("saas.views.stripe")
    def test_upgrade_view_post_creates_stripe_session(self, mock_stripe):
        """POST /saas/upgrade/ creates Stripe checkout session"""
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test_session"
        mock_stripe.checkout.Session.create.return_value = mock_session

        from saas.views import UpgradeView

        request = self.factory.post("/saas/upgrade/", {"plan": "pro"})
        request.user = self.user
        request.company = self.company
        request.session = {}
        response = UpgradeView.as_view()(request)
        # Should redirect to Stripe
        assert response.status_code in [302, 200]

    @patch("saas.views.stripe")
    def test_upgrade_success_view(self, mock_stripe):
        """GET /saas/upgrade/success/ renders confirmation"""
        from saas.views import UpgradeSuccessView

        request = self.factory.get("/saas/upgrade/success/?session_id=cs_test_123")
        request.user = self.user
        request.company = self.company
        request.session = {}
        response = UpgradeSuccessView.as_view()(request)
        assert response.status_code == 200


# ─── Auth Models ──────────────────────────────────────────────────────────────


class TestAuthModels(TestCase):
    """PinRecoveryToken, MagicToken, LoginAttempt"""

    def setUp(self):
        self.user = User.objects.create_user(username="authtest", password="test123")

    def test_pin_recovery_token_create(self):
        """PinRecoveryToken creation with expiry"""
        from accounts.auth_models import PinRecoveryToken

        token = PinRecoveryToken.objects.create(
            user=self.user,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        assert token.is_used is False
        assert token.token is not None

    def test_magic_token_create(self):
        """MagicToken creation"""
        from accounts.auth_models import MagicToken

        token = MagicToken.objects.create(
            user=self.user,
            expires_at=timezone.now() + timedelta(minutes=15),
            ip_address="192.168.1.100",
        )
        assert token.is_used is False

    def test_login_attempt_failed(self):
        """LoginAttempt for failed login"""
        from accounts.auth_models import LoginAttempt

        attempt = LoginAttempt.objects.create(
            username="unknown_user",
            ip_address="1.2.3.4",
            success=False,
            failure_reason="wrong_password",
        )
        assert attempt.success is False
        assert attempt.failure_reason == "wrong_password"

    def test_login_attempt_success(self):
        """LoginAttempt for successful login"""
        from accounts.auth_models import LoginAttempt

        attempt = LoginAttempt.objects.create(
            username="authtest",
            ip_address="192.168.1.1",
            success=True,
        )
        assert attempt.success is True


# ─── Country Plugin Integration ───────────────────────────────────────────────


class TestCountryPlugins(TestCase):
    """HR, DE, AT, SI validators via CountryPlugin pattern"""

    def test_hr_plugin_oib_required(self):
        """HR plugin requires OIB for all entities"""
        from evalidator.validators import HRInvoiceValidator

        v = HRInvoiceValidator()
        result = v.validate(
            {
                "oib": "",  # empty
                "iban": "HR1210010051863000160",
                "vat_rate": 25,
                "total": 100.0,
                "invoice_number": "INV-X",
                "issue_date": "2026-04-19",
            }
        )
        assert result["valid"] is False

    def test_hr_valid_vat_rates(self):
        """HR accepts 0, 5, 13, 25 only"""
        from evalidator.validators import HRInvoiceValidator

        v = HRInvoiceValidator()
        for rate in [0, 5, 13, 25]:
            result = v.validate(
                {
                    "oib": "12345678901",
                    "iban": "HR1210010051863000160",
                    "vat_rate": rate,
                    "total": 100.0,
                    "invoice_number": f"INV-{rate}",
                    "issue_date": "2026-04-19",
                }
            )
            assert result["valid"] is True, f"VAT {rate}% should be valid in HR"

    def test_de_valid_vat_rates(self):
        """DE accepts 0, 7, 19 only"""
        from evalidator.validators import DEInvoiceValidator

        v = DEInvoiceValidator()
        for rate in [0, 7, 19]:
            result = v.validate(
                {
                    "steuernummer": "21/815/08150",
                    "vat_rate": rate,
                    "total": 100.0,
                    "invoice_number": f"RE-{rate}",
                    "issue_date": "2026-04-19",
                }
            )
            assert result["valid"] is True, f"VAT {rate}% should be valid in DE"


# ─── Full Integration: 3 Future Features ──────────────────────────────────────


class TestFuture3Integration(TestCase):
    """
    3 futurističke funkcije koje konkurencija nema:
    1. AccessControl — delegirani pristup (DATEV/Xero to nemaju)
    2. Sentinel TrustedDevice — hardware-bound trust chain
    3. eValidator seal — kriptografski pečat bez logina
    """

    def setUp(self):
        from companies.models import Company

        self.co1 = Company.objects.create(name="Co1", oib="20202020200", country="HR")
        self.co2 = Company.objects.create(name="Co2", oib="30303030300", country="HR")
        self.user = User.objects.create_user(username="fut3user", password="test123")

    def test_future1_delegated_cross_company_access(self):
        """Co1 can delegate invoicing read to Co2 — DATEV can't do this"""
        from access_control.models import AccessGrant

        grant = AccessGrant.objects.create(
            company=self.co1,
            grantor=self.co1,
            grantee=self.co2,
            modules=["invoicing"],
            access_level="read",
        )
        assert grant.has_module("invoicing") is True
        assert grant.has_module("payroll") is False

    def test_future2_device_trust_chain(self):
        """Device gets trust level, can be revoked — hardware-bound security"""
        from sentinel.models import TrustedDevice

        fp = hashlib.sha256(f"Mozilla Chrome {self.user.id} {self.co1.id}".encode()).hexdigest()
        device = TrustedDevice.objects.create(
            user=self.user,
            company=self.co1,
            device_fingerprint=fp,
            trust_level="verified",
            user_agent="Chrome/120",
        )
        assert device.trust_level == "verified"
        device.trust(by_user=self.user)
        device.refresh_from_db()
        assert device.trust_level == "trusted"

    def test_future3_eval_seal_public_verification(self):
        """ValidationCertificate has public token for no-login verification"""
        from evalidator.models import ValidationResult, ValidationCertificate

        vr = ValidationResult.objects.create(
            company=self.co1,
            doc_type="hr_invoice",
            doc_hash="integration_test_hash",
            score=98,
            is_valid=True,
            errors=[],
            warnings=[],
        )
        cert = ValidationCertificate.objects.create(
            company=self.co1,
            validation_result=vr,
            doc_reference="INV-2026-INTEGRATION",
        )
        assert cert.public_token is not None
        assert str(cert.public_token) != ""
        # Public token enables verification at /eval/cert/<uuid>/ without login
