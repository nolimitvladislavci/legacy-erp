"""
invoicing/document_validator.py
AI-assisted validation — eliminiraj ljudske greške.
Korisnik NIKAD ne mora znati pravila napamet.

8 pravila:
1. Fiscal check (should_fiscalize consistency)
2. Date validation (delivery, due date)
3. DE §14 UStG compliance
4. Duplicate number detection
5. PDV rate check (NKD-based)
6. Avans chain check (>90 days without final)
7. Udruga rules (članarina PDV)
8. Synesis filter (ne validirati historijske)
"""
from dataclasses import dataclass, field
from typing import List
from enum import Enum


class Severity(Enum):
    BLOCK = 'block'    # Sprječava save
    WARN  = 'warn'     # Upozorenje, ali može nastaviti
    INFO  = 'info'     # Informacija


@dataclass
class ValidationIssue:
    code:     str
    severity: Severity
    message:  str
    field:    str = ''
    action:   str = ''


class DocumentValidator:
    """
    Svaki Invoice prolazi kroz ovaj validator.
    Centralno mjesto — nikad duplicirana logika.
    """

    def validate(self, invoice) -> List[ValidationIssue]:
        issues = []

        # Rule 8: skip historical Synesis imports
        if getattr(invoice, 'synesis_id', None):
            return issues

        issues.extend(self._check_fiscal(invoice))
        issues.extend(self._check_dates(invoice))
        issues.extend(self._check_de_compliance(invoice))
        issues.extend(self._check_duplicates(invoice))
        issues.extend(self._check_pdv_rates(invoice))
        issues.extend(self._check_avans_chain(invoice))
        issues.extend(self._check_udruga_rules(invoice))

        return issues

    def _check_fiscal(self, inv) -> List[ValidationIssue]:
        issues = []
        from invoicing.fiscal_rules import should_fiscalize
        should, reason = should_fiscalize(inv)

        if getattr(inv, 'is_fiscalized', False) and not should:
            issues.append(ValidationIssue(
                code='FISKAL_UNNECESSARY',
                severity=Severity.WARN,
                message=f'Račun je fiskaliziran ali nije trebao biti: {reason}',
                field='is_fiscalized',
                action='Provjerite tip dokumenta i status firme'
            ))
        return issues

    def _check_dates(self, inv) -> List[ValidationIssue]:
        issues = []
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()

        issued = getattr(inv, 'date_issued', None)
        if issued:
            if hasattr(issued, 'date'):
                issued = issued.date()

            # Datum isporuke u budućnosti > 30 dana
            delivery = getattr(inv, 'date_delivery', None)
            if delivery and delivery > today:
                if (delivery - today).days > 30:
                    issues.append(ValidationIssue(
                        code='DATE_DELIVERY_FAR_FUTURE',
                        severity=Severity.WARN,
                        message=f'Datum isporuke je {(delivery-today).days} dana u budućnosti',
                        field='date_delivery',
                    ))

        # Rok plaćanja prošao, a račun nije plaćen
        due = getattr(inv, 'date_due', None)
        if due and due < today and getattr(inv, 'status', '') not in ('PAID', 'STORNO', 'CANCELLED'):
            issues.append(ValidationIssue(
                code='DUE_DATE_PASSED',
                severity=Severity.INFO,
                message=f'Rok plaćanja je prošao ({due})',
                field='date_due',
                action='Pokrenite opomenu iz dunning modula'
            ))
        return issues

    def _check_de_compliance(self, inv) -> List[ValidationIssue]:
        issues = []
        if getattr(inv, 'country', 'HR') != 'DE':
            return issues

        # §14 UStG — obavezne komponente DE računa
        if not getattr(inv, 'client_oib', ''):
            issues.append(ValidationIssue(
                code='DE_NO_STEUERNR',
                severity=Severity.WARN,
                message='DE račun bez Steuernummer/USt-IdNr primatelja (§14 Abs.4 UStG)',
                field='client_oib',
                action='Unesite Steuernummer kupca'
            ))

        if not getattr(inv, 'date_delivery', None):
            issues.append(ValidationIssue(
                code='DE_NO_LEISTUNGSDATUM',
                severity=Severity.WARN,
                message='DE račun bez Leistungsdatum (§14 Abs.4 Nr.6 UStG)',
                field='date_delivery',
                action='Unesite datum isporuke/usluge'
            ))

        # B2B DE → e-Račun od 2025
        if inv.doctype in ('R', 'FA', 'RN'):
            issued = getattr(inv, 'date_issued', None)
            issued_year = None
            if issued:
                issued_year = issued.year if hasattr(issued, 'year') else None
            if issued_year and issued_year >= 2025:
                if not getattr(inv, 'eracun_sent', False):
                    issues.append(ValidationIssue(
                        code='DE_ERECHNUNG_REQUIRED',
                        severity=Severity.INFO,
                        message='B2B DE račun od 2025 treba biti e-Rechnung (XRechnung/ZUGFeRD)',
                        action='Pošaljite putem eRačun modula'
                    ))
        return issues

    def _check_duplicates(self, inv) -> List[ValidationIssue]:
        issues = []
        if not inv.pk and getattr(inv, 'number', ''):
            from invoicing.models import Invoice
            company = getattr(inv, 'company', None)
            if company:
                same_number = Invoice.objects.filter(
                    company=company,
                    number=inv.number,
                )
                if same_number.exists():
                    issues.append(ValidationIssue(
                        code='DUPLICATE_NUMBER',
                        severity=Severity.BLOCK,
                        message=f'Broj dokumenta {inv.number} već postoji!',
                        field='number',
                    ))
        return issues

    def _check_pdv_rates(self, inv) -> List[ValidationIssue]:
        issues = []
        if not inv.pk:
            return issues
        try:
            from invoicing.fiscal_rules import get_pdv_rate_for_item
            company = inv.company
            for item in inv.items.all():
                inv_item = getattr(item, 'inventory_item', None)
                if inv_item:
                    _, warning = get_pdv_rate_for_item(inv_item, company)
                    if warning:
                        issues.append(ValidationIssue(
                            code='PDV_RATE_MISMATCH',
                            severity=Severity.WARN,
                            message=warning,
                            field=f'items[{item.pk}].tax_rate',
                            action='Promijenite PDV stopu'
                        ))
        except Exception:
            pass
        return issues

    def _check_avans_chain(self, inv) -> List[ValidationIssue]:
        issues = []
        if getattr(inv, 'doctype', '') != 'A':
            return issues
        from django.utils import timezone
        from datetime import timedelta
        issued = getattr(inv, 'date_issued', None)
        if issued:
            if hasattr(issued, 'date'):
                issued = issued.date()
            if (timezone.now().date() - issued).days > 90:
                related = getattr(inv, 'related_invoice', None)
                if not related:
                    issues.append(ValidationIssue(
                        code='AVANS_NO_FINAL',
                        severity=Severity.WARN,
                        message='Avansni račun stariji od 90 dana bez završnog računa',
                        field='related_invoice',
                        action='Kreirajte završni račun ili zatvorite predujam'
                    ))
        return issues

    def _check_udruga_rules(self, inv) -> List[ValidationIssue]:
        issues = []
        company = getattr(inv, 'company', None)
        if not company or getattr(company, 'business_type', '') not in ('udruga', 'ustanova'):
            return issues
        if not inv.pk:
            return issues

        try:
            for item in inv.items.all():
                name = (item.description or '').lower()
                if any(x in name for x in ('članarin', 'clanarin', 'clanska', 'membership')):
                    rate = float(getattr(item, 'tax_rate', 0) or 0)
                    if rate > 0:
                        issues.append(ValidationIssue(
                            code='UDRUGA_CLANARINA_PDV',
                            severity=Severity.WARN,
                            message='Članarina udruge obično nije predmet PDV-a (NN 73/13)',
                            field=f'items[{item.pk}].tax_rate',
                            action='Članarine su najčešće PDV exempt'
                        ))
        except (ValueError, TypeError):
            pass
        return issues


# Singleton
validator = DocumentValidator()
