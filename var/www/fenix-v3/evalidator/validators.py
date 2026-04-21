"""
eValidator — Engine za validaciju dokumenata
============================================
Svaki validator implementira validate(data) -> List[Issue]
"""
import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Issue:
    code: str
    severity: str  # error | warning | info
    message: str
    field_path: str = ""
    expected: str = ""
    actual: str = ""

    def to_dict(self):
        return {
            "code": self.code,
            "severity": self.severity,
            "msg": self.message,
            "field": self.field_path,
            "expected": self.expected,
            "actual": self.actual,
        }


class BaseValidator:
    """Bazna klasa za sve validatore."""
    name = "BaseValidator"
    version = "1.0"

    def validate(self, data: dict) -> List[Issue]:
        raise NotImplementedError

    def _require_field(self, data, field, issues, label=None):
        val = data.get(field)
        if not val:
            issues.append(Issue(
                code=f"REQUIRED_{field.upper()}",
                severity="error",
                message=f"Obavezno polje '{label or field}' nedostaje",
                field_path=field,
            ))
        return val


class OIBValidator(BaseValidator):
    """Validacija OIB-a putem Luhn-10 algoritma."""
    name = "OIBValidator"

    def validate(self, data: dict) -> List[Issue]:
        issues = []
        oib = str(data.get("oib", "")).strip()
        if not oib:
            issues.append(Issue("OIB_MISSING", "error", "OIB nije naveden", "oib"))
            return issues
        if not re.fullmatch(r"\d{11}", oib):
            issues.append(Issue("OIB_FORMAT", "error",
                f"OIB mora imati točno 11 znamenki, dobiven: '{oib}'", "oib",
                expected="11 znamenki", actual=str(len(oib))))
            return issues
        # Luhn-10 provjera
        check = 10
        for digit in oib[:10]:
            check += int(digit)
            check = check % 10 or 10
            check = (check * 2) % 11
        expected_check = 11 - check if (11 - check) != 10 else 0
        if int(oib[10]) != expected_check:
            issues.append(Issue("OIB_CHECKSUM", "error",
                f"OIB kontrolna znamenka nevaljana (dobiven {oib[10]}, očekivan {expected_check})",
                "oib", expected=str(expected_check), actual=oib[10]))
        return issues


class HRInvoiceValidator(BaseValidator):
    """
    Validacija HR računa prema eRačun/UBL 2.1 standardu.
    Pokriva: OIB, IBAN, iznosi, PDV stope, obavezna polja.
    """
    name = "HRInvoiceValidator"
    VALID_VAT_RATES = {0, 5, 13, 25}
    IBAN_RE = re.compile(r"^HR\d{19}$")

    def validate(self, data: dict) -> List[Issue]:
        issues = []
        # Obavezna polja
        for f, label in [
            ("invoice_number", "Broj računa"),
            ("issue_date", "Datum izdavanja"),
            ("seller_name", "Naziv prodavatelja"),
            ("buyer_name", "Naziv kupca"),
            ("total_amount", "Ukupni iznos"),
        ]:
            self._require_field(data, f, issues, label)

        # OIB prodavatelja
        oib_issues = OIBValidator().validate({"oib": data.get("seller_oib", "")})
        for i in oib_issues:
            i.field_path = "seller_oib"
            issues.append(i)

        # OIB kupca (upozorenje, nije uvijek obavezno)
        buyer_oib = data.get("buyer_oib", "")
        if buyer_oib:
            oib_issues = OIBValidator().validate({"oib": buyer_oib})
            for i in oib_issues:
                i.severity = "warning"
                i.field_path = "buyer_oib"
                issues.append(i)

        # IBAN format
        iban = data.get("seller_iban", "")
        if iban and not self.IBAN_RE.match(iban.replace(" ", "").upper()):
            issues.append(Issue("IBAN_FORMAT", "warning",
                f"IBAN '{iban}' nije u HR formatu (HR + 19 znamenki)",
                "seller_iban", expected="HR + 19 znamenki"))

        # PDV stopa
        vat_rate = data.get("vat_rate")
        if vat_rate is not None:
            try:
                vat_float = float(vat_rate)
                if vat_float not in self.VALID_VAT_RATES:
                    issues.append(Issue("VAT_RATE", "warning",
                        f"PDV stopa {vat_float}% nije standardna HR stopa",
                        "vat_rate",
                        expected=str(self.VALID_VAT_RATES),
                        actual=str(vat_float)))
            except (TypeError, ValueError):
                issues.append(Issue("VAT_RATE_TYPE", "error",
                    "PDV stopa mora biti broj", "vat_rate"))

        # Iznosi moraju biti pozitivni
        for amount_field in ["total_amount", "net_amount", "vat_amount"]:
            val = data.get(amount_field)
            if val is not None:
                try:
                    if float(val) < 0:
                        issues.append(Issue(f"{amount_field.upper()}_NEGATIVE", "error",
                            f"Polje '{amount_field}' ne smije biti negativno",
                            amount_field, expected=">= 0", actual=str(val)))
                except (TypeError, ValueError):
                    pass

        return issues


class DEInvoiceValidator(BaseValidator):
    """Validacija DE fakture — ZUGFeRD / XRechnung."""
    name = "DEInvoiceValidator"
    STEUER_RE = re.compile(r"^\d{2,3}/\d{3}/\d{4,5}$")
    VALID_VAT_RATES = {0, 7, 19}

    def validate(self, data: dict) -> List[Issue]:
        issues = []
        for f, label in [
            ("invoice_number", "Rechnungsnummer"),
            ("issue_date", "Rechnungsdatum"),
            ("seller_name", "Verkäufername"),
        ]:
            self._require_field(data, f, issues, label)

        steuernummer = data.get("seller_steuernummer", "")
        if steuernummer and not self.STEUER_RE.match(steuernummer):
            issues.append(Issue("STEUER_FORMAT", "warning",
                f"Steuernummer format nevaljano: '{steuernummer}'",
                "seller_steuernummer", expected="XX/XXX/XXXXX"))

        vat_rate = data.get("vat_rate")
        if vat_rate is not None:
            try:
                if float(vat_rate) not in self.VALID_VAT_RATES:
                    issues.append(Issue("DE_VAT_RATE", "warning",
                        f"DE PDV stopa {vat_rate}% nije standardna (0%, 7%, 19%)",
                        "vat_rate", expected=str(self.VALID_VAT_RATES)))
            except (TypeError, ValueError):
                pass
        return issues


class PEPPOLValidator(BaseValidator):
    """PEPPOL BIS 3.0 validacija — obavezna HR B2G od 2026."""
    name = "PEPPOLValidator"

    def validate(self, data: dict) -> List[Issue]:
        issues = []
        # Endpoint ID (GLN ili OIB format)
        for f, label in [
            ("buyer_endpoint_id", "Buyer Endpoint ID"),
            ("seller_endpoint_id", "Seller Endpoint ID"),
            ("process_id", "Process ID"),
            ("document_currency", "Valuta"),
        ]:
            self._require_field(data, f, issues, label)

        # Valuta mora biti ISO 4217
        currency = data.get("document_currency", "")
        if currency and not re.fullmatch(r"[A-Z]{3}", currency):
            issues.append(Issue("CURRENCY_FORMAT", "error",
                f"Valuta '{currency}' mora biti ISO 4217 (npr. HRK, EUR, USD)",
                "document_currency", expected="3 slova ISO 4217"))

        # Process ID
        process_id = data.get("process_id", "")
        if process_id and "urn:fdc:peppol.eu" not in process_id:
            issues.append(Issue("PEPPOL_PROCESS", "warning",
                "Process ID ne počinje s 'urn:fdc:peppol.eu'",
                "process_id"))
        return issues


class ContractValidator(BaseValidator):
    """
    Validacija ugovora prema HR pravu (ZOO — Zakon o obveznim odnosima).
    Pokriva: ugovorne strane, predmet, datum, potpise, OIB stranaka.
    """
    name = "ContractValidator"
    version = "1.0"

    # Minimalna duljina predmeta ugovora (znakova)
    MIN_SUBJECT_LEN = 10

    def validate(self, data: dict) -> List[Issue]:
        issues = []

        # --- Obavezna polja ---
        for f, label in [
            ("contract_number",    "Broj ugovora"),
            ("contract_date",      "Datum ugovora"),
            ("party_a_name",       "Naziv stranke A (naručitelj/kupac)"),
            ("party_b_name",       "Naziv stranke B (izvođač/prodavatelj)"),
            ("subject",            "Predmet ugovora"),
        ]:
            self._require_field(data, f, issues, label)

        # --- Predmet mora biti opisnog karaktera ---
        subject = data.get("subject", "")
        if subject and len(str(subject).strip()) < self.MIN_SUBJECT_LEN:
            issues.append(Issue(
                code="CONTRACT_SUBJECT_TOO_SHORT",
                severity="error",
                message=f"Predmet ugovora prekratak (min {self.MIN_SUBJECT_LEN} znakova)",
                field_path="subject",
                expected=f">= {self.MIN_SUBJECT_LEN} znakova",
                actual=str(len(str(subject).strip())),
            ))

        # --- OIB stranke A (error ako postoji ali je neispravan) ---
        oib_a = data.get("party_a_oib", "")
        if oib_a:
            for i in OIBValidator().validate({"oib": oib_a}):
                i.field_path = "party_a_oib"
                issues.append(i)
        else:
            issues.append(Issue(
                code="CONTRACT_PARTY_A_OIB_MISSING",
                severity="warning",
                message="OIB stranke A nije naveden — preporučeno za vjerodostojnost ugovora",
                field_path="party_a_oib",
            ))

        # --- OIB stranke B ---
        oib_b = data.get("party_b_oib", "")
        if oib_b:
            for i in OIBValidator().validate({"oib": oib_b}):
                i.field_path = "party_b_oib"
                issues.append(i)
        else:
            issues.append(Issue(
                code="CONTRACT_PARTY_B_OIB_MISSING",
                severity="warning",
                message="OIB stranke B nije naveden — preporučeno za vjerodostojnost ugovora",
                field_path="party_b_oib",
            ))

        # --- Datum ugovora — format provjera ---
        contract_date = data.get("contract_date", "")
        if contract_date:
            date_ok = bool(re.fullmatch(
                r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}",
                str(contract_date).strip()
            ))
            if not date_ok:
                issues.append(Issue(
                    code="CONTRACT_DATE_FORMAT",
                    severity="error",
                    message=f"Datum ugovora '{contract_date}' nije u prepoznatom formatu",
                    field_path="contract_date",
                    expected="YYYY-MM-DD ili DD.MM.YYYY",
                    actual=str(contract_date),
                ))

        # --- Potpisi — barem jedan potpis obavezan ---
        signatures = data.get("signatures", [])
        if not signatures:
            issues.append(Issue(
                code="CONTRACT_NO_SIGNATURES",
                severity="error",
                message="Ugovor nema evidentiranih potpisa (potpuni ili elektronički)",
                field_path="signatures",
                expected="min 1 potpis",
            ))
        elif len(signatures) < 2:
            issues.append(Issue(
                code="CONTRACT_SINGLE_SIGNATURE",
                severity="warning",
                message="Samo jedna strana potpisala ugovor — nedostaje potpis suprotne strane",
                field_path="signatures",
                expected="2 potpisa (obje strane)",
                actual=str(len(signatures)),
            ))

        # --- Vrijednost ugovora (nije obavezna, ali ako postoji mora biti pozitivna) ---
        value = data.get("contract_value")
        if value is not None:
            try:
                if float(value) < 0:
                    issues.append(Issue(
                        code="CONTRACT_VALUE_NEGATIVE",
                        severity="error",
                        message="Vrijednost ugovora ne smije biti negativna",
                        field_path="contract_value",
                        expected=">= 0",
                        actual=str(value),
                    ))
            except (TypeError, ValueError):
                issues.append(Issue(
                    code="CONTRACT_VALUE_TYPE",
                    severity="error",
                    message="Vrijednost ugovora mora biti broj",
                    field_path="contract_value",
                ))

        # --- Trajanje — ako postoji datum isteka, mora biti nakon datuma ugovora ---
        expiry_date = data.get("expiry_date", "")
        if expiry_date and contract_date:
            # Normalizacija u YYYY-MM-DD za usporedbu
            def _norm(d):
                d = str(d).strip()
                if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", d):
                    dd, mm, yyyy = d.split(".")
                    return f"{yyyy}-{mm}-{dd}"
                return d
            try:
                if _norm(expiry_date) <= _norm(contract_date):
                    issues.append(Issue(
                        code="CONTRACT_EXPIRY_BEFORE_START",
                        severity="error",
                        message="Datum isteka ugovora mora biti nakon datuma potpisivanja",
                        field_path="expiry_date",
                        expected=f"> {contract_date}",
                        actual=str(expiry_date),
                    ))
            except Exception:
                pass

        return issues


class ArhivaValidator(BaseValidator):
    """
    Validacija arhivskih dokumenata prema HR Zakonu o arhivskom gradivu
    i arhivima (NN 61/18). Minimalna provjera metapodataka.
    """
    name = "ArhivaValidator"
    version = "1.0"

    def validate(self, data: dict) -> List[Issue]:
        issues = []

        for f, label in [
            ("document_title",    "Naziv dokumenta"),
            ("document_date",     "Datum dokumenta"),
            ("document_type",     "Vrsta dokumenta"),
            ("creator",           "Stvaratelj dokumenta"),
        ]:
            self._require_field(data, f, issues, label)

        # Retention period — preporučeni minimum 5 godina (računovodstvo)
        retention_years = data.get("retention_years")
        if retention_years is not None:
            try:
                ry = int(retention_years)
                if ry < 1:
                    issues.append(Issue(
                        "ARHIVA_RETENTION_ZERO", "error",
                        "Rok čuvanja mora biti najmanje 1 godina",
                        "retention_years", expected=">= 1", actual=str(ry)
                    ))
                elif ry < 5:
                    issues.append(Issue(
                        "ARHIVA_RETENTION_SHORT", "warning",
                        f"Rok čuvanja {ry}g kraći od preporučenih 5 godina za računovodstvene dokumente",
                        "retention_years", expected=">= 5", actual=str(ry)
                    ))
            except (TypeError, ValueError):
                pass

        # Hash integritet — ako je dan, mora biti SHA-256 format
        doc_hash = data.get("document_hash", "")
        if doc_hash and not re.fullmatch(r"[a-fA-F0-9]{64}", doc_hash):
            issues.append(Issue(
                "ARHIVA_HASH_FORMAT", "warning",
                "Hash dokumenta nije SHA-256 format (64 hex znaka)",
                "document_hash", expected="64 hex znaka (SHA-256)"
            ))

        return issues


class PayrollValidator(BaseValidator):
    """
    Validacija platnih lista prema HR propisima:
    Zakon o radu (NN 93/14, 127/17, 98/19, 151/22).
    """
    name = "PayrollValidator"
    version = "1.0"

    # Minimalna plaća 2024 (bruto)
    MIN_GROSS_HR = 840.0  # EUR

    def validate(self, data: dict) -> List[Issue]:
        issues = []

        for f, label in [
            ("employee_name",   "Ime i prezime radnika"),
            ("employee_oib",    "OIB radnika"),
            ("period_from",     "Obračunsko razdoblje od"),
            ("period_to",       "Obračunsko razdoblje do"),
            ("gross_salary",    "Bruto plaća"),
            ("net_salary",      "Neto plaća"),
        ]:
            self._require_field(data, f, issues, label)

        # OIB radnika
        emp_oib = data.get("employee_oib", "")
        if emp_oib:
            for i in OIBValidator().validate({"oib": emp_oib}):
                i.field_path = "employee_oib"
                issues.append(i)

        # Bruto >= minimalna plaća
        gross = data.get("gross_salary")
        if gross is not None:
            try:
                g = float(gross)
                if g < self.MIN_GROSS_HR:
                    issues.append(Issue(
                        "PAYROLL_BELOW_MIN_WAGE", "error",
                        f"Bruto plaća {g:.2f} EUR ispod zakonskog minimuma {self.MIN_GROSS_HR:.2f} EUR",
                        "gross_salary",
                        expected=f">= {self.MIN_GROSS_HR} EUR",
                        actual=f"{g:.2f} EUR",
                    ))
            except (TypeError, ValueError):
                issues.append(Issue(
                    "PAYROLL_GROSS_TYPE", "error",
                    "Bruto plaća mora biti broj", "gross_salary"
                ))

        # Neto < Bruto
        net = data.get("net_salary")
        if net is not None and gross is not None:
            try:
                if float(net) >= float(gross):
                    issues.append(Issue(
                        "PAYROLL_NET_GTE_GROSS", "error",
                        "Neto plaća ne smije biti jednaka ili veća od bruto plaće",
                        "net_salary",
                        expected=f"< {gross}",
                        actual=str(net),
                    ))
            except (TypeError, ValueError):
                pass

        # Provjera MBO (Matični broj osiguranika) — nije OIB, 9 znamenki
        mbo = data.get("employee_mbo", "")
        if mbo and not re.fullmatch(r"\d{9}", str(mbo)):
            issues.append(Issue(
                "PAYROLL_MBO_FORMAT", "warning",
                f"MBO '{mbo}' nije u ispravnom formatu (9 znamenki)",
                "employee_mbo", expected="9 znamenki"
            ))

        return issues


class GDPRValidator(BaseValidator):
    """
    Validacija GDPR dokumentacije prema Uredbi (EU) 2016/679
    i ZZOP (Zakon o zaštiti osobnih podataka, NN 42/18).
    """
    name = "GDPRValidator"
    version = "1.0"

    LEGAL_BASES = {
        "consent",           # čl. 6(1)(a)
        "contract",          # čl. 6(1)(b)
        "legal_obligation",  # čl. 6(1)(c)
        "vital_interests",   # čl. 6(1)(d)
        "public_task",       # čl. 6(1)(e)
        "legitimate_interest",  # čl. 6(1)(f)
    }

    def validate(self, data: dict) -> List[Issue]:
        issues = []

        for f, label in [
            ("data_subject",      "Ispitanik (ime/ID)"),
            ("data_controller",   "Voditelj obrade"),
            ("legal_basis",       "Pravna osnova obrade"),
            ("processing_purpose","Svrha obrade"),
            ("data_categories",   "Kategorije osobnih podataka"),
        ]:
            self._require_field(data, f, issues, label)

        # Pravna osnova mora biti jedna od definiranih
        legal_basis = data.get("legal_basis", "")
        if legal_basis and legal_basis not in self.LEGAL_BASES:
            issues.append(Issue(
                "GDPR_LEGAL_BASIS_INVALID", "error",
                f"Pravna osnova '{legal_basis}' nije valjana prema čl. 6 GDPR-a",
                "legal_basis",
                expected=str(self.LEGAL_BASES),
                actual=legal_basis,
            ))

        # Rok čuvanja osobnih podataka mora biti definiran
        retention = data.get("retention_period", "")
        if not retention:
            issues.append(Issue(
                "GDPR_RETENTION_MISSING", "error",
                "Rok čuvanja osobnih podataka mora biti definiran (načelo ograničenja pohrane)",
                "retention_period",
            ))

        # Posebne kategorije podataka zahtijevaju eksplicitnu suglasnost (čl. 9)
        sensitive = data.get("special_categories", [])
        if sensitive:
            legal_basis = data.get("legal_basis", "")
            if legal_basis != "consent":
                explicit_consent = data.get("explicit_consent", False)
                if not explicit_consent:
                    issues.append(Issue(
                        "GDPR_SPECIAL_CATEGORIES_NO_CONSENT", "error",
                        "Posebne kategorije osobnih podataka (čl. 9) zahtijevaju eksplicitnu privolu ispitanika",
                        "explicit_consent",
                        expected="True",
                    ))

        # DPO kontakt — obavezan za javna tijela ili sustavnu obradu
        requires_dpo = data.get("requires_dpo", False)
        if requires_dpo and not data.get("dpo_contact"):
            issues.append(Issue(
                "GDPR_DPO_MISSING", "warning",
                "Naznačena je obaveza imenovanja DPO-a, ali kontakt nije naveden",
                "dpo_contact",
            ))

        # Automatska odluka — mora biti navedena (čl. 22)
        automated = data.get("automated_decision", False)
        if automated:
            safeguards = data.get("automated_safeguards", "")
            if not safeguards:
                issues.append(Issue(
                    "GDPR_AUTOMATED_NO_SAFEGUARDS", "error",
                    "Automatska odluka bez ljudskog nadzora zahtijeva zaštitne mjere (čl. 22 GDPR)",
                    "automated_safeguards",
                ))

        return issues


VALIDATOR_REGISTRY = {
    "invoice_hr":     HRInvoiceValidator(),
    "invoice_de":     DEInvoiceValidator(),
    "invoice_peppol": PEPPOLValidator(),
    "contract":       ContractValidator(),
    "arhiva":         ArhivaValidator(),
    "payroll":        PayrollValidator(),
    "gdpr":           GDPRValidator(),
    "custom":         BaseValidator(),
}


def run_validation(doc_type: str, data: dict) -> dict:
    """
    Pokretanje validacije — vraća dict s issues + score.
    score = 100 - (errors*20 + warnings*5)
    """
    validator = VALIDATOR_REGISTRY.get(doc_type, BaseValidator())
    issues = validator.validate(data)
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    score = max(0, 100 - errors * 20 - warnings * 5)
    status = "valid" if errors == 0 else "invalid"
    if errors == 0 and warnings > 0:
        status = "warning"
    return {
        "status": status,
        "score": score,
        "issues": [i.to_dict() for i in issues],
        "rules_checked": len(issues) + 3,  # aproks.
        "rules_passed": len(issues) + 3 - errors - warnings,
        "validator": validator.name,
        "validator_version": validator.version,
    }
