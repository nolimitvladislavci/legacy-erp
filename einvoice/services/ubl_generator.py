"""UBL Generator bridge — adapts invoicing.Invoice to eracun UBL generator.

Reuses the battle-tested eracun/services/ubl_generator.py (351 LOC)
rather than reimplementing UBL 2.1 from scratch.

Pattern: Invoice model → InvoiceAdapter (ERacun-like) → generate_ubl_xml()
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("propter.einvoice.ubl_generator")


@dataclass
class LineItemAdapter:
    """Adapts InvoiceItem to ERacunItem interface."""
    line_number: int = 1
    description: str = ""
    quantity: Decimal = Decimal("1")
    unit_code: str = "EA"
    unit_price: Decimal = Decimal("0")
    discount_percent: Decimal = Decimal("0")
    line_total: Decimal = Decimal("0")
    tax_category: str = "S"
    tax_rate: Decimal = Decimal("25")
    classification_code: str = ""


@dataclass
class TaxSummaryAdapter:
    """Adapts tax breakdown to ERacunTaxSummary interface."""
    tax_category: str = "S"
    tax_rate: Decimal = Decimal("25")
    taxable_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")


@dataclass
class InvoiceAdapter:
    """Adapts invoicing.Invoice to ERacun-compatible interface.

    The eracun UBL generator expects an object with specific attributes.
    This adapter maps Invoice fields to that interface.
    """
    # Document
    invoice_number: str = ""
    issue_date: date = None
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None
    doc_type: str = "380"
    note: str = ""
    currency: str = "EUR"
    buyer_reference: str = ""
    order_reference: str = ""

    # Issuer (seller = company)
    issuer_name: str = ""
    issuer_oib: str = ""
    issuer_address: str = ""
    issuer_city: str = ""
    issuer_postal: str = ""
    issuer_country: str = "HR"
    issuer_iban: str = ""
    issuer_swift: str = ""

    # Recipient (buyer = client)
    recipient_name: str = ""
    recipient_oib: str = ""
    recipient_address: str = ""
    recipient_city: str = ""
    recipient_postal: str = ""
    recipient_country: str = "HR"

    # Payment
    payment_means_code: str = "30"
    payment_reference: str = ""
    payment_model: str = "HR00"

    # Fiskalizacija
    zki: str = ""
    jir: str = ""

    # Amounts
    subtotal: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

    # Related objects (populated by from_invoice)
    _items: list = field(default_factory=list)
    _tax_summaries: list = field(default_factory=list)

    class items:
        """Fake manager to mimic ERacun.items.all()"""
        pass

    class tax_summaries:
        """Fake manager to mimic ERacun.tax_summaries.all()"""
        pass

    def __post_init__(self):
        # Wire up fake managers
        self.items = type('ItemsManager', (), {
            'all': lambda s: self._items,
            'order_by': lambda s, *a: self._items,
        })()
        self.tax_summaries = type('TaxManager', (), {
            'all': lambda s: self._tax_summaries,
        })()

    @classmethod
    def from_invoice(cls, invoice):
        """Create adapter from invoicing.Invoice instance."""
        company = invoice.company

        # Map payment type
        payment_map = {
            'TRANSAKCIJSKI': '30', 'GOTOVINA': '10', 'KARTICA': '48',
            'VIRMAN': '30', 'KOMPENZACIJA': '97',
        }
        payment_code = payment_map.get(
            getattr(invoice, 'payment_type', 'TRANSAKCIJSKI'), '30'
        )

        # Get partner info for recipient address
        partner = getattr(invoice, 'partner', None)
        recipient_address = ""
        recipient_city = ""
        recipient_postal = ""
        recipient_country = "HR"
        if partner:
            recipient_address = getattr(partner, 'address', '') or ''
            recipient_city = getattr(partner, 'city', '') or ''
            recipient_postal = getattr(partner, 'postal_code', '') or ''
            recipient_country = getattr(partner, 'country', 'HR') or 'HR'

        # Calculate tax
        items_qs = invoice.items.all() if hasattr(invoice, 'items') else []
        subtotal = invoice.subtotal or Decimal("0")
        total = invoice.total or Decimal("0")
        tax_amount = total - subtotal

        adapter = cls(
            invoice_number=invoice.number,
            issue_date=invoice.issue_date or date.today(),
            due_date=getattr(invoice, 'due_date', None),
            delivery_date=getattr(invoice, 'delivery_date', None),
            doc_type="380",
            note=getattr(invoice, 'note', '') or '',
            currency=getattr(invoice, 'currency', 'EUR') or 'EUR',
            issuer_name=company.name if company else '',
            issuer_oib=company.oib if company else '',
            issuer_address=getattr(company, 'address', '') or '',
            issuer_city=getattr(company, 'city', '') or '',
            issuer_postal=getattr(company, 'postal_code', '') or '',
            issuer_country=getattr(company, 'country', 'HR') or 'HR',
            issuer_iban=getattr(company, 'iban', '') or '',
            issuer_swift=getattr(company, 'swift', '') or '',
            recipient_name=invoice.client_name or '',
            recipient_oib=invoice.client_oib or '',
            recipient_address=recipient_address,
            recipient_city=recipient_city,
            recipient_postal=recipient_postal,
            recipient_country=recipient_country,
            payment_means_code=payment_code,
            payment_reference=getattr(invoice, 'reference_number', '') or '',
            payment_model=getattr(invoice, 'payment_model', 'HR00') or 'HR00',
            zki=getattr(invoice, 'zki', '') or '',
            jir=getattr(invoice, 'jir', '') or '',
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=total,
        )

        # Build line items
        from eracun.services.ubl_generator import map_unit_code
        for idx, item in enumerate(items_qs, 1):
            tax_rate = getattr(item, 'tax_rate', Decimal("25")) or Decimal("25")
            adapter._items.append(LineItemAdapter(
                line_number=idx,
                description=item.description or '',
                quantity=item.quantity or Decimal("1"),
                unit_code=map_unit_code(getattr(item, 'unit', 'EA')),
                unit_price=item.unit_price or Decimal("0"),
                line_total=getattr(item, 'total_price', Decimal("0")) or Decimal("0"),
                tax_rate=tax_rate,
                tax_category="S" if tax_rate > 0 else "E",
            ))

        # Build tax summary (aggregate by rate)
        tax_groups = {}
        for item in adapter._items:
            rate = item.tax_rate
            if rate not in tax_groups:
                tax_groups[rate] = {"base": Decimal("0"), "tax": Decimal("0")}
            tax_groups[rate]["base"] += item.line_total
            tax_groups[rate]["tax"] += (item.line_total * rate / Decimal("100")).quantize(Decimal("0.01"))

        for rate, amounts in tax_groups.items():
            adapter._tax_summaries.append(TaxSummaryAdapter(
                tax_category="S" if rate > 0 else "E",
                tax_rate=rate,
                taxable_amount=amounts["base"],
                tax_amount=amounts["tax"],
            ))

        return adapter

    @classmethod
    def from_eracun(cls, eracun):
        """Create adapter from eracun.ERacun instance (passthrough)."""
        # ERacun already has the right interface, but wrap for consistency
        return eracun  # Just pass through — eracun already works


def generate_ubl_for_invoice(invoice, profile="HR"):
    """
    Generate UBL 2.1 XML from an invoicing.Invoice model instance.

    Args:
        invoice: invoicing.Invoice instance
        profile: "HR" for CIUS-HR, "DE" for XRechnung, "EU" for Peppol

    Returns:
        str: UBL XML content
    """
    adapter = InvoiceAdapter.from_invoice(invoice)

    if profile == "DE":
        from eracun.services.xrechnung import generate_xrechnung
        return generate_xrechnung(adapter)
    else:
        from eracun.services.ubl_generator import generate_ubl_xml
        xml_bytes = generate_ubl_xml(adapter)
        if isinstance(xml_bytes, bytes):
            return xml_bytes.decode("utf-8")
        return xml_bytes


def generate_ubl_for_eracun(eracun, profile="HR"):
    """Generate UBL from existing eracun.ERacun model (direct passthrough)."""
    if profile == "DE":
        from eracun.services.xrechnung import generate_xrechnung
        return generate_xrechnung(eracun)
    else:
        from eracun.services.ubl_generator import generate_ubl_xml
        xml_bytes = generate_ubl_xml(eracun)
        if isinstance(xml_bytes, bytes):
            return xml_bytes.decode("utf-8")
        return xml_bytes
