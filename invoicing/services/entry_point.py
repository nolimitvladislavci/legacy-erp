"""
invoicing/services/entry_point.py

DocumentEntry — jedina klasa koja smije kreirati poslovni dokument.
Sve pristupne tocke (POS, Invoice, Import, API, eRacun inbox) prolaze ovdje.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
import logging

from django.db import transaction
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


@dataclass
class FiscalResult:
    """Rezultat fiskalne obrade."""
    success: bool
    zki: Optional[str] = None
    jir: Optional[str] = None
    message: str = ''
    demo: bool = False
    raw_response: dict = field(default_factory=dict)


@dataclass
class DocumentResult:
    """Rezultat kreiranja dokumenta."""
    invoice: object = None
    fiscal: FiscalResult = None
    stock_movements: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def success(self):
        return self.invoice is not None and not self.errors


class BaseFiscalHandler:
    """Bazna klasa za sve fiskalne handlere."""

    def process(self, invoice) -> FiscalResult:
        raise NotImplementedError

    def can_process(self, invoice) -> bool:
        return True


class NullFiscalHandler(BaseFiscalHandler):
    """Ne radi nista. Za testne/interne dokumente ili zemlje bez fiskalizacije."""

    def process(self, invoice) -> FiscalResult:
        return FiscalResult(success=True, message='No fiscal handler required.')


class HRCashFiscalHandler(BaseFiscalHandler):
    """HR fiskalizacija za gotovinske racune — omotava postojeci kod."""

    def __init__(self, company):
        self.company = company

    def can_process(self, invoice) -> bool:
        return getattr(invoice, 'country', 'HR') == 'HR' and invoice.doctype in ('R', 'RN', 'POS')

    def process(self, invoice) -> FiscalResult:
        from invoicing.services.fiscalize import fiscalize_invoice
        result = fiscalize_invoice(invoice)
        return FiscalResult(
            success=result.get('success', False),
            zki=result.get('zki'),
            jir=result.get('jir'),
            message=result.get('error', ''),
            demo=result.get('demo', False),
        )


class HRERacunHandler(BaseFiscalHandler):
    """HR e-Racun za B2B — omotava eracun modul."""

    def __init__(self, company):
        self.company = company

    def can_process(self, invoice) -> bool:
        return getattr(invoice, 'country', 'HR') == 'HR' and invoice.doctype == 'FA'

    def process(self, invoice) -> FiscalResult:
        try:
            from eracun.services.engine import create_eracun_from_invoice
            eracun = create_eracun_from_invoice(invoice)
            return FiscalResult(
                success=True,
                message=f'e-Racun {eracun.invoice_number} kreiran',
            )
        except Exception as e:
            return FiscalResult(success=False, message=str(e))


class FiscalHandlerRegistry:
    """Bira pravu koreografiju za kontekst."""

    @staticmethod
    def get(company, invoice) -> BaseFiscalHandler:
        country = getattr(invoice, 'country', 'HR')
        doctype = getattr(invoice, 'doctype', 'R')

        # Gotovinski racun u HR
        if country == 'HR' and doctype in ('R', 'RN', 'POS'):
            return HRCashFiscalHandler(company)

        # B2B racun u HR — Fiskalizacija 2.0 handler (delegira na posrednika)
        if country == 'HR' and doctype in ('FA', 'R'):
            try:
                cfg = company.eracun_config
                if cfg.is_active:
                    from invoicing.services.fiscal_f20 import ERacunFiskalizacija20Handler
                    return ERacunFiskalizacija20Handler(company)
            except Exception:
                pass
            # Fallback: stara fiskalizacija za gotovinu
            if doctype == 'R':
                return HRCashFiscalHandler(company)
            return NullFiscalHandler()

        # Ulazni racun — nema fiskalizacije
        if doctype in ('URA', 'S'):
            return NullFiscalHandler()

        # Njemacka: XRechnung + TSE
        if country == 'DE':
            from invoicing.services.fiscal_de import DEFiscalHandler
            return DEFiscalHandler(company)

        # Default: nema handlera
        return NullFiscalHandler()


class DocumentEntry:
    """
    Jedina klasa koja smije kreirati poslovni dokument.
    Sve pristupne tocke prolaze ovdje.
    """

    def __init__(self, company, created_by=None, source='manual', ip_address=None):
        self.company = company
        self.created_by = created_by
        self.source = source
        self.ip_address = ip_address

    @transaction.atomic
    def create(self, document_data: dict, items: list = None) -> DocumentResult:
        """
        Kreira dokument atomski. Ili sve prodje ili nista.

        Args:
            document_data: dict s Invoice poljima
            items: list of dicts s InvoiceItem poljima

        Returns:
            DocumentResult
        """
        from invoicing.models import Invoice, InvoiceItem
        from invoicing.services.events import log_invoice_event
        from invoicing.services.fiscalize import lock_invoice

        errors = []
        items = items or []

        # 1. Kreiraj Invoice
        try:
            doc_data = {**document_data}
            doc_data['company'] = self.company
            doc_data['created_by'] = self.created_by
            doc_data['source'] = self.source
            doc_data.setdefault('status', 'DRAFT')
            doc_data.setdefault('currency', 'EUR')
            doc_data.setdefault('country', 'HR')

            invoice = Invoice(**doc_data)
            invoice.save()
        except (IntegrityError, DatabaseError) as e:
            logger.error(f'DocumentEntry.create failed: {e}')
            return DocumentResult(errors=[str(e)])

        # 2. Kreiraj stavke
        for idx, item_data in enumerate(items):
            try:
                item_data = {**item_data}
                item_data['invoice'] = invoice
                item_data.setdefault('quantity', Decimal('1'))
                InvoiceItem.objects.create(**item_data)
            except (ValueError, TypeError) as e:
                errors.append(f'Item {idx}: {e}')

        # 3. Recalculate totals
        try:
            self._recalculate(invoice)
        except Exception as e:
            errors.append(f'Calc: {e}')

        # 4. Lock ako je confirmed
        if invoice.status in ('CONFIRMED', 'PAID', 'FISCALIZED'):
            lock_invoice(invoice)
            invoice.save(update_fields=['is_locked', 'deletion_protected_until'])

        # 5. Audit event
        log_invoice_event(
            invoice,
            event_type='created',
            title=f'Dokument kreiran ({self.source})',
            metadata={'source': self.source, 'items': len(items)},
            actor=self.created_by,
            ip_address=self.ip_address,
        )

        # 6. Fiscal handler (ako je CONFIRMED ili zatrazi se)
        fiscal_result = FiscalResult(success=True, message='Draft — no fiscal processing')
        auto_fiscalize = document_data.get('auto_fiscalize', False)
        if auto_fiscalize and invoice.status != 'DRAFT':
            handler = FiscalHandlerRegistry.get(self.company, invoice)
            if handler.can_process(invoice):
                fiscal_result = handler.process(invoice)
                if fiscal_result.success:
                    invoice.status = 'FISCALIZED'
                    invoice.save(update_fields=['status'])

        return DocumentResult(
            invoice=invoice,
            fiscal=fiscal_result,
            errors=errors,
        )

    def _recalculate(self, invoice):
        """Recalculate invoice totals from items."""
        from invoicing.models import InvoiceItem
        items = InvoiceItem.objects.filter(invoice=invoice)
        subtotal = sum(i.total_price for i in items)
        tax = sum(i.gross_total - i.total_price for i in items)
        invoice.subtotal = subtotal
        invoice.tax_amount = tax
        invoice.total = subtotal + tax
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total'])
