"""
invoicing/services/fiscal_de.py
German fiscal handler — XRechnung + TSE (Technische Sicherheitseinrichtung).

Germany requires:
1. XRechnung (CII format) for B2B/B2G invoices
2. TSE signature for cash register receipts (KassenSichV)
3. DSFinV-K export format for tax audits
"""
import logging
from .entry_point import BaseFiscalHandler, FiscalResult

logger = logging.getLogger(__name__)


class DEXRechnungHandler(BaseFiscalHandler):
    """
    German B2B e-invoice handler.
    Generates XRechnung (CII) and optionally ZUGFeRD PDF.
    """

    def __init__(self, company):
        self.company = company

    def can_process(self, invoice) -> bool:
        return (
            getattr(invoice, 'country', '') == 'DE'
            and invoice.doctype in ('R', 'FA')
        )

    def process(self, invoice) -> FiscalResult:
        from eracun.models import ERacun, ERacunItem, ERacunLog

        try:
            # 1. Create ERacun record
            eracun = ERacun.objects.create(
                company=self.company,
                direction='outgoing',
                invoice=invoice,
                doc_type='380',
                invoice_number=invoice.number,
                issue_date=invoice.date_issued.date() if hasattr(invoice.date_issued, 'date') else invoice.date_issued,
                due_date=getattr(invoice, 'date_due', None),
                currency=getattr(invoice, 'currency', 'EUR'),
                issuer_name=invoice.issuer_name or self.company.name,
                issuer_oib=invoice.issuer_oib or self.company.oib,
                issuer_address=invoice.issuer_address or '',
                issuer_country='DE',
                issuer_iban=invoice.issuer_iban or '',
                recipient_name=invoice.client_name,
                recipient_oib=invoice.client_oib or '',
                recipient_address=invoice.client_address or '',
                recipient_city=invoice.client_city or '',
                recipient_country=getattr(invoice, 'client_country', 'DE'),
                subtotal=invoice.subtotal,
                tax_amount=invoice.tax_amount,
                total=invoice.total,
                note=invoice.note or '',
                status='valid',
            )

            # Copy items
            for item in invoice.items.all():
                ERacunItem.objects.create(
                    eracun=eracun,
                    line_number=item.pk,
                    description=item.description,
                    quantity=item.quantity,
                    unit_code='EA',
                    unit_price=item.unit_price,
                    line_total=item.total_price,
                    tax_category='S',
                    tax_rate=item.tax_rate,
                    kpd_code=getattr(item, 'classification_code', '') or '',
                )

            # 2. Generate XRechnung XML
            from eracun.services.xrechnung import generate_xrechnung
            xml = generate_xrechnung(eracun)
            eracun.xml_request = xml
            eracun.save(update_fields=['xml_request'])

            ERacunLog.objects.create(
                eracun=eracun,
                action='xrechnung_generated',
                status='valid',
                message=f'XRechnung CII generiert: {eracun.invoice_number}',
                details={'format': 'CII', 'profile': 'XRechnung 3.0'},
            )

            return FiscalResult(
                success=True,
                message=f'XRechnung generiert: {eracun.invoice_number}',
                raw_response={'eracun_id': str(eracun.id), 'format': 'xrechnung'},
            )

        except Exception as e:
            logger.exception('DE XRechnung error')
            return FiscalResult(success=False, message=str(e))


class DETSEHandler(BaseFiscalHandler):
    """
    German TSE handler for cash register receipts (Kassenbons).
    TSE = Technische Sicherheitseinrichtung (technical security device).

    TSE providers: fiskaly (cloud), Deutsche Fiskal, Swissbit (hardware).
    This handler is a placeholder — actual TSE integration requires
    a contract with a TSE provider and their SDK.
    """

    def __init__(self, company):
        self.company = company

    def can_process(self, invoice) -> bool:
        return (
            getattr(invoice, 'country', '') == 'DE'
            and invoice.doctype in ('RN', 'POS')
        )

    def process(self, invoice) -> FiscalResult:
        # TSE signing requires external service
        # Placeholder until TSE provider is selected
        logger.info(f'DE TSE: would sign receipt {invoice.number} (TSE not yet configured)')
        return FiscalResult(
            success=True,
            message='TSE: Kassenbon erstellt (TSE-Signatur ausstehend)',
            raw_response={
                'tse_status': 'pending',
                'note': 'TSE provider not yet configured. Options: fiskaly.com, deutsche-fiskal.de, swissbit.com',
            },
        )


class DEFiscalHandler(BaseFiscalHandler):
    """
    Composite DE handler — routes to XRechnung or TSE based on document type.
    """

    def __init__(self, company):
        self.company = company

    def can_process(self, invoice) -> bool:
        return getattr(invoice, 'country', '') == 'DE'

    def process(self, invoice) -> FiscalResult:
        if invoice.doctype in ('RN', 'POS'):
            return DETSEHandler(self.company).process(invoice)
        else:
            return DEXRechnungHandler(self.company).process(invoice)
