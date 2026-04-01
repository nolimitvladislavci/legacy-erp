"""
SAF-T HR Generator — OECD Standard Audit File for Tax, Croatia adaptation.

Generira XML per OECD SAF-T v2.0 shemu:
- Header: company info, fiscal year, date range
- MasterFiles: GL accounts, Customers, Suppliers, TaxTable, Products
- GeneralLedgerEntries: temeljnice + stavke knjizenja
- SourceDocuments: SalesInvoices, PurchaseInvoices

Koristi lxml.etree za namespace-aware XML s XSD validacijom.
"""
import logging
from decimal import Decimal
from lxml import etree

logger = logging.getLogger('konto.saft')

SAFT_NS = 'urn:OECD:StandardAuditFile-Tax:HR_2.0'
NSMAP = {None: SAFT_NS}


class SAFTGenerator:
    """Generate SAF-T HR XML for a company and date range."""

    def __init__(self, company, period_from, period_to):
        self.company = company
        self.period_from = period_from
        self.period_to = period_to

    def generate(self):
        """Generate full SAF-T XML string."""
        root = etree.Element('AuditFile', nsmap=NSMAP)
        self._build_header(root)
        self._build_masterfiles(root)
        self._build_general_ledger_entries(root)
        self._build_source_documents(root)
        return etree.tostring(root, pretty_print=True, xml_declaration=True,
                              encoding='UTF-8').decode('utf-8')

    def _el(self, parent, tag, text=None):
        """Helper: create SubElement with optional text."""
        el = etree.SubElement(parent, tag)
        if text is not None:
            el.text = str(text)
        return el

    # ── Header ─────────────────────────────────────────────────────

    def _build_header(self, root):
        header = self._el(root, 'Header')
        self._el(header, 'AuditFileVersion', '2.0')
        self._el(header, 'CompanyID', f'HR{self.company.oib}' if self.company.oib else '')
        self._el(header, 'TaxRegistrationNumber', self.company.oib or '')
        self._el(header, 'TaxAccountingBasis', 'Invoice')
        self._el(header, 'CompanyName', self.company.name)

        addr = self._el(header, 'CompanyAddress')
        self._el(addr, 'StreetName', getattr(self.company, 'address', '') or '')
        self._el(addr, 'City', getattr(self.company, 'city', '') or '')
        self._el(addr, 'PostalCode', getattr(self.company, 'zip_code', '') or '')
        self._el(addr, 'Country', 'HR')

        self._el(header, 'FiscalYear', str(self.period_from.year))
        self._el(header, 'StartDate', self.period_from.isoformat())
        self._el(header, 'EndDate', self.period_to.isoformat())
        self._el(header, 'CurrencyCode', 'EUR')
        self._el(header, 'DateCreated', self.period_to.isoformat())

    # ── MasterFiles ────────────────────────────────────────────────

    def _build_masterfiles(self, root):
        mf = self._el(root, 'MasterFiles')
        self._build_gl_accounts(mf)
        self._build_customers(mf)
        self._build_suppliers(mf)
        self._build_tax_table(mf)
        self._build_products(mf)

    def _build_gl_accounts(self, mf):
        from konto.models import KontoAccount
        accounts = KontoAccount.objects.filter(
            company=self.company, is_active=True
        ).order_by('code')

        if not accounts.exists():
            return

        gl = self._el(mf, 'GeneralLedgerAccounts')

        for acc in accounts:
            account_el = self._el(gl, 'Account')
            self._el(account_el, 'AccountID', acc.code)
            self._el(account_el, 'AccountDescription', acc.name)
            self._el(account_el, 'StandardAccountID', acc.code[:2])
            self._el(account_el, 'AccountType', self._map_account_type(acc.account_type))

            balance = acc.balance
            if balance >= 0:
                self._el(account_el, 'OpeningDebitBalance', f'{abs(balance):.2f}')
            else:
                self._el(account_el, 'OpeningCreditBalance', f'{abs(balance):.2f}')

    def _build_customers(self, mf):
        from partners.models import Partner
        from invoicing.models import Invoice

        # Partners koji imaju prodajne fakture u periodu
        customer_ids = Invoice.objects.filter(
            company=self.company,
            date_issued__date__gte=self.period_from,
            date_issued__date__lte=self.period_to,
            doctype__in=['PO', 'P', 'R', 'FA', 'RN'],
        ).values_list('partner_id', flat=True).distinct()

        customers = Partner.objects.filter(
            company=self.company, pk__in=customer_ids
        ).order_by('pk')

        if not customers.exists():
            return

        cust_el = self._el(mf, 'Customers')
        for partner in customers:
            c = self._el(cust_el, 'Customer')
            self._el(c, 'CustomerID', str(partner.pk))
            self._el(c, 'CompanyName', partner.name)

            addr = self._el(c, 'BillingAddress')
            self._el(addr, 'StreetName', partner.address or '')
            self._el(addr, 'City', partner.city or '')
            self._el(addr, 'PostalCode', partner.zip_code or '')
            self._el(addr, 'Country', partner.country or 'HR')

            if partner.oib:
                self._el(c, 'TaxID', partner.oib)

    def _build_suppliers(self, mf):
        from partners.models import Partner
        from invoicing.models import Invoice

        # Partners koji imaju ulazne fakture u periodu
        supplier_ids = Invoice.objects.filter(
            company=self.company,
            date_issued__date__gte=self.period_from,
            date_issued__date__lte=self.period_to,
            doctype__in=['URA'],
        ).values_list('partner_id', flat=True).distinct()

        suppliers = Partner.objects.filter(
            company=self.company, pk__in=supplier_ids
        ).order_by('pk')

        if not suppliers.exists():
            return

        supp_el = self._el(mf, 'Suppliers')
        for partner in suppliers:
            s = self._el(supp_el, 'Supplier')
            self._el(s, 'SupplierID', str(partner.pk))
            self._el(s, 'CompanyName', partner.name)

            addr = self._el(s, 'BillingAddress')
            self._el(addr, 'StreetName', partner.address or '')
            self._el(addr, 'City', partner.city or '')
            self._el(addr, 'PostalCode', partner.zip_code or '')
            self._el(addr, 'Country', partner.country or 'HR')

            if partner.oib:
                self._el(s, 'TaxID', partner.oib)

    def _build_tax_table(self, mf):
        from invoicing.models import InvoiceItem

        rates = InvoiceItem.objects.filter(
            invoice__company=self.company,
            invoice__date_issued__date__gte=self.period_from,
            invoice__date_issued__date__lte=self.period_to,
        ).values_list('tax_rate', flat=True).distinct()

        if not rates:
            return

        tt = self._el(mf, 'TaxTable')
        for rate in sorted(set(rates)):
            entry = self._el(tt, 'TaxTableEntry')
            self._el(entry, 'TaxType', 'VAT')
            self._el(entry, 'Description', f'PDV {rate}%')
            self._el(entry, 'TaxPercentage', f'{rate:.2f}')

    def _build_products(self, mf):
        from inventory.models import InventoryItem

        items = InventoryItem.objects.filter(
            company=self.company, is_active=True
        ).order_by('pk')[:5000]

        if not items.exists():
            return

        products = self._el(mf, 'Products')
        for item in items:
            p = self._el(products, 'Product')
            self._el(p, 'ProductCode', item.sku or str(item.pk))
            self._el(p, 'ProductDescription', item.name)
            self._el(p, 'ProductType', 'Goods' if getattr(item, 'is_service', False) is False else 'Service')
            if hasattr(item, 'unit'):
                self._el(p, 'UnitOfMeasure', item.unit or 'kom')

    # ── GeneralLedgerEntries ───────────────────────────────────────

    def _build_general_ledger_entries(self, root):
        from konto.models import JournalEntry
        from django.db.models import Sum

        entries = JournalEntry.objects.filter(
            company=self.company,
            date__gte=self.period_from,
            date__lte=self.period_to,
            is_posted=True,
        ).prefetch_related('lines', 'lines__account').order_by('date', 'pk')

        if not entries.exists():
            return

        gle = self._el(root, 'GeneralLedgerEntries')

        # Totals
        total_debit = Decimal('0')
        total_credit = Decimal('0')

        for je in entries:
            entry_el = self._el(gle, 'Entry')
            self._el(entry_el, 'TransactionID', je.entry_number)
            self._el(entry_el, 'Period', f'{je.date.year}-{je.date.month:02d}')
            self._el(entry_el, 'TransactionDate', je.date.isoformat())
            self._el(entry_el, 'Description', je.description)
            self._el(entry_el, 'SourceType', je.source_type or 'manual')

            for i, line in enumerate(je.lines.all(), 1):
                line_el = self._el(entry_el, 'Line')
                self._el(line_el, 'RecordID', str(i))
                self._el(line_el, 'AccountID', line.account.code)
                self._el(line_el, 'DebitCreditIndicator', 'D' if line.side == 'debit' else 'C')

                if line.side == 'debit':
                    self._el(line_el, 'DebitAmount', f'{line.amount:.2f}')
                    total_debit += line.amount
                else:
                    self._el(line_el, 'CreditAmount', f'{line.amount:.2f}')
                    total_credit += line.amount

                if line.description:
                    self._el(line_el, 'Description', line.description)

        self._el(gle, 'NumberOfEntries', str(entries.count()))
        self._el(gle, 'TotalDebit', f'{total_debit:.2f}')
        self._el(gle, 'TotalCredit', f'{total_credit:.2f}')

    # ── SourceDocuments ────────────────────────────────────────────

    def _build_source_documents(self, root):
        sd = self._el(root, 'SourceDocuments')
        self._build_sales_invoices(sd)
        self._build_purchase_invoices(sd)

    def _build_sales_invoices(self, sd):
        from invoicing.models import Invoice

        invoices = Invoice.objects.filter(
            company=self.company,
            date_issued__date__gte=self.period_from,
            date_issued__date__lte=self.period_to,
            doctype__in=['PO', 'P', 'R', 'FA', 'RN', 'A', 'GS'],
        ).prefetch_related('items').order_by('date_issued')

        if not invoices.exists():
            return

        si = self._el(sd, 'SalesInvoices')

        for inv in invoices:
            inv_el = self._el(si, 'Invoice')
            self._el(inv_el, 'InvoiceNo', inv.number)
            self._el(inv_el, 'InvoiceDate', inv.date_issued.strftime('%Y-%m-%d'))
            self._el(inv_el, 'InvoiceType', inv.doctype or 'R')

            if inv.partner_id:
                self._el(inv_el, 'CustomerID', str(inv.partner_id))

            for i, item in enumerate(inv.items.all(), 1):
                line = self._el(inv_el, 'InvoiceLine')
                self._el(line, 'LineNumber', str(i))
                self._el(line, 'ProductDescription', item.description or '')
                self._el(line, 'Quantity', f'{item.quantity:.4f}')
                self._el(line, 'UnitPrice', f'{item.unit_price:.2f}')
                self._el(line, 'TaxableAmount', f'{item.total_price:.2f}')
                self._el(line, 'TaxPercentage', f'{item.tax_rate:.2f}')

                tax_amount = item.total_price * item.tax_rate / Decimal('100')
                self._el(line, 'TaxAmount', f'{tax_amount:.2f}')
                self._el(line, 'LineTotal', f'{(item.total_price + tax_amount):.2f}')

            totals = self._el(inv_el, 'DocumentTotals')
            self._el(totals, 'TaxableAmount', f'{inv.subtotal:.2f}')
            self._el(totals, 'TaxAmount', f'{inv.tax_amount:.2f}')
            self._el(totals, 'NetTotal', f'{inv.total:.2f}')

    def _build_purchase_invoices(self, sd):
        from invoicing.models import Invoice

        invoices = Invoice.objects.filter(
            company=self.company,
            date_issued__date__gte=self.period_from,
            date_issued__date__lte=self.period_to,
            doctype__in=['URA'],
        ).prefetch_related('items').order_by('date_issued')

        if not invoices.exists():
            return

        pi = self._el(sd, 'PurchaseInvoices')

        for inv in invoices:
            inv_el = self._el(pi, 'Invoice')
            self._el(inv_el, 'InvoiceNo', inv.number)
            self._el(inv_el, 'InvoiceDate', inv.date_issued.strftime('%Y-%m-%d'))

            if inv.partner_id:
                self._el(inv_el, 'SupplierID', str(inv.partner_id))

            for i, item in enumerate(inv.items.all(), 1):
                line = self._el(inv_el, 'InvoiceLine')
                self._el(line, 'LineNumber', str(i))
                self._el(line, 'ProductDescription', item.description or '')
                self._el(line, 'Quantity', f'{item.quantity:.4f}')
                self._el(line, 'UnitPrice', f'{item.unit_price:.2f}')
                self._el(line, 'TaxableAmount', f'{item.total_price:.2f}')
                self._el(line, 'TaxPercentage', f'{item.tax_rate:.2f}')

                tax_amount = item.total_price * item.tax_rate / Decimal('100')
                self._el(line, 'TaxAmount', f'{tax_amount:.2f}')
                self._el(line, 'LineTotal', f'{(item.total_price + tax_amount):.2f}')

            totals = self._el(inv_el, 'DocumentTotals')
            self._el(totals, 'TaxableAmount', f'{inv.subtotal:.2f}')
            self._el(totals, 'TaxAmount', f'{inv.tax_amount:.2f}')
            self._el(totals, 'NetTotal', f'{inv.total:.2f}')

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _map_account_type(account_type):
        """Map Django AccountType to SAF-T AccountType."""
        mapping = {
            'asset': 'Asset',
            'liability': 'Liability',
            'equity': 'Equity',
            'income': 'Income',
            'expense': 'Expense',
        }
        return mapping.get(account_type, 'Other')
