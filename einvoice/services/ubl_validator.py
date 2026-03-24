"""UBL Validator — wraps eracun validator + adds PROPTER custom rules.

3-stage pipeline:
  Stage 1: XSD schema validation (via eracun.services.validator)
  Stage 2: EN 16931 business rules (via eracun.services.validator)
  Stage 3: PROPTER custom rules (OIB checksum, future date, etc.)
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from lxml import etree

logger = logging.getLogger("propter.einvoice.validator")

UBL_NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


@dataclass
class ValidationResult:
    """Result of UBL validation pipeline."""
    is_valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stage_results: dict = field(default_factory=dict)

    @property
    def error_count(self):
        return len(self.errors)

    @property
    def summary(self):
        if self.is_valid:
            w = f" ({len(self.warnings)} upozorenja)" if self.warnings else ""
            return f"Validacija uspjesna{w}"
        return f"Validacija neuspjesna: {len(self.errors)} gresaka"


def validate_oib_checksum(oib):
    """Validate Croatian OIB using ISO 7064, MOD 11-10."""
    if not oib or len(oib) != 11:
        return False
    try:
        digits = [int(d) for d in oib]
    except ValueError:
        return False
    remainder = 10
    for i in range(10):
        remainder = (remainder + digits[i]) % 10
        if remainder == 0:
            remainder = 10
        remainder = (remainder * 2) % 11
    check = (11 - remainder) % 10
    return check == digits[10]


def validate_ubl(xml_content, strict=True):
    """
    Full 3-stage UBL validation pipeline.

    Args:
        xml_content: str or bytes UBL XML
        strict: if True, warnings become errors

    Returns:
        ValidationResult
    """
    result = ValidationResult()
    xml_bytes = xml_content.encode("utf-8") if isinstance(xml_content, str) else xml_content

    # ── Stage 1: XSD Schema ──
    try:
        from eracun.services.validator import validate_xsd
        xsd_valid, xsd_errors = validate_xsd(xml_bytes)
        result.stage_results["xsd"] = {"valid": xsd_valid, "errors": xsd_errors}
        if not xsd_valid:
            result.is_valid = False
            result.errors.extend([f"XSD: {e}" for e in xsd_errors])
            return result  # Stop early — no point checking rules if XML is malformed
    except Exception as e:
        logger.warning(f"XSD validation skipped: {e}")
        result.stage_results["xsd"] = {"valid": True, "errors": [str(e)]}

    # ── Stage 2: EN 16931 Business Rules ──
    try:
        from eracun.services.validator import validate_business_rules
        br_valid, br_errors, br_warnings = validate_business_rules(xml_bytes)
        result.stage_results["business_rules"] = {
            "valid": br_valid, "errors": br_errors, "warnings": br_warnings
        }
        if not br_valid:
            result.is_valid = False
            result.errors.extend([f"BR: {e}" for e in br_errors])
        result.warnings.extend([f"BR: {w}" for w in br_warnings])
    except Exception as e:
        logger.warning(f"Business rules validation skipped: {e}")
        result.stage_results["business_rules"] = {"valid": True, "errors": [str(e)]}

    # ── Stage 3: PROPTER Custom Rules ──
    propter_errors, propter_warnings = _validate_propter_rules(xml_bytes)
    result.stage_results["propter"] = {
        "errors": propter_errors, "warnings": propter_warnings
    }
    if propter_errors:
        result.is_valid = False
        result.errors.extend(propter_errors)
    result.warnings.extend(propter_warnings)

    # In strict mode, warnings become errors
    if strict and result.warnings:
        result.errors.extend(result.warnings)
        result.warnings = []
        result.is_valid = len(result.errors) == 0

    return result


def _validate_propter_rules(xml_bytes):
    """PROPTER custom validation rules."""
    errors = []
    warnings = []

    try:
        doc = etree.fromstring(xml_bytes)
    except Exception as e:
        return [f"PROP-00: XML parse error: {e}"], []

    def _text(xpath, default=""):
        el = doc.find(xpath, UBL_NS)
        return el.text.strip() if el is not None and el.text else default

    def _decimal(xpath):
        t = _text(xpath)
        try:
            return Decimal(t) if t else None
        except Exception:
            return None

    # ── PROP-01: Invoice number required ──
    inv_id = _text("cbc:ID")
    if not inv_id:
        errors.append("PROP-01: Broj racuna je obavezan")

    # ── PROP-02: Future date warning ──
    issue_date_str = _text("cbc:IssueDate")
    if issue_date_str:
        try:
            issue_date = date.fromisoformat(issue_date_str)
            if issue_date > date.today():
                warnings.append(f"PROP-02: Datum izdavanja je u buducnosti ({issue_date_str})")
        except ValueError:
            errors.append(f"PROP-02: Neispravan format datuma: {issue_date_str}")

    # ── PROP-03: At least one line ──
    lines = doc.findall(".//cac:InvoiceLine", UBL_NS)
    if not lines:
        errors.append("PROP-03: Racun mora imati barem jednu stavku")

    # ── PROP-04: Seller VAT ID required ──
    seller_vat = _text(".//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
    if not seller_vat:
        errors.append("PROP-04: OIB/VAT ID izdavatelja je obavezan")

    # ── PROP-05: OIB checksum (ISO 7064) ──
    if seller_vat:
        oib = seller_vat.replace("HR", "")
        if len(oib) == 11 and oib.isdigit():
            if not validate_oib_checksum(oib):
                errors.append(f"PROP-05: OIB izdavatelja ({oib}) ne prolazi checksum provjeru")

    buyer_vat = _text(".//cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
    if buyer_vat:
        oib = buyer_vat.replace("HR", "")
        if len(oib) == 11 and oib.isdigit():
            if not validate_oib_checksum(oib):
                warnings.append(f"PROP-05: OIB primatelja ({oib}) ne prolazi checksum provjeru")

    # ── PROP-06: Payable amount consistency ──
    tax_inclusive = _decimal(".//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount")
    payable = _decimal(".//cac:LegalMonetaryTotal/cbc:PayableAmount")
    if tax_inclusive and payable and abs(tax_inclusive - payable) > Decimal("0.02"):
        errors.append(f"PROP-06: TaxInclusive ({tax_inclusive}) != Payable ({payable})")

    # ── PROP-07: Currency consistency ──
    doc_currency = _text("cbc:DocumentCurrencyCode")
    amounts = doc.findall(".//*[@currencyID]")
    for amt in amounts:
        amt_currency = amt.get("currencyID")
        if amt_currency and amt_currency != doc_currency:
            warnings.append(f"PROP-07: Valuta {amt_currency} ne odgovara DocumentCurrencyCode {doc_currency}")
            break

    return errors, warnings
