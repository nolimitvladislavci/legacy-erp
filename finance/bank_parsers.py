"""
finance/bank_parsers.py — SEPA camt.053 XML parser + pain.001 generator

Podržava:
  - camt.053.001.02 (ZABA, PBZ, Erste — stariji format)
  - camt.053.001.08 (novi ISO 20022 format)
  - Auto-detekcija namespace-a bez pretpostavki
  - Dedup: external_id = sha256(iban + ntry_ref + datum + iznos)
  - Auto-mapiranje na BankAccount po IBAN-u iz XML-a
  - pain.001 generator za masovna plaćanja (SUPP/SALA)

Integracija: poziva se iz finance/views.py → bank_import_xml view
"""

import hashlib
import uuid
import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from lxml import etree


# ─── Namespace konstante ────────────────────────────────────────────────────

CAMT053_NAMESPACES = [
    'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02',
    'urn:iso:std:iso:20022:tech:xsd:camt.053.001.08',
    'urn:iso:std:iso:20022:tech:xsd:camt.053.001.06',
]

PAIN001_NS = 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'


# ─── Helper: namespace-agnostic xpath ───────────────────────────────────────

def _ns(tree_or_element):
    """
    Izvlači default namespace iz elementa ili stabla.
    Vraća dict {'n': 'urn:...'} ili {} ako nema namespace-a.
    Otporan na None, prazan nsmap, nested namespace deklaracije.
    """
    nsmap = {}
    try:
        raw = tree_or_element.nsmap if hasattr(tree_or_element, 'nsmap') else {}
        default = raw.get(None, '')
        if default:
            nsmap = {'n': default}
        else:
            # Fallback: pokušaj pronaći poznat camt namespace
            for v in raw.values():
                if 'camt.053' in v:
                    nsmap = {'n': v}
                    break
    except Exception:
        pass
    return nsmap


def _xpath_text(element, path, ns, default=''):
    """Sigurni xpath, uvijek vraca str via /text() suffix."""
    try:
        text_path = path if path.endswith('/text()') else path + '/text()'
        result = element.xpath(text_path, namespaces=ns)
        return result[0].strip() if result else default
    except Exception:
        return default


def _xpath_first(element, path, ns):
    """Vraća prvi element ili None."""
    try:
        result = element.xpath(path, namespaces=ns)
        return result[0] if result else None
    except Exception:
        return None


# ─── camt.053 Parser ────────────────────────────────────────────────────────

class SEPACamtParser:
    """
    Robustni camt.053 XML parser za HR banke (ZABA, PBZ, Erste, OTP).

    Ispravlja 4 greške iz predloženog koda:
      1. Namespace detekcija: koristi _ns() helper, otporan na None/nested ns
      2. Nema [0] bez provjere: sve xpath pozive štiti _xpath_text/_xpath_first
      3. external_id = sha256(iban+ref+datum+iznos) — jedinstven i otporan na
         banke koje ponavljaju NtryRef za storno transakcije (PBZ)
      4. Polje 'reference' → ispravno 'reference_number' iz BankTransaction modela

    Dodatno: auto-mapiranje BankAccount po IBAN-u iz XML zaglavlja.
    """

    def __init__(self, xml_content: bytes):
        """
        xml_content: surovi bytes iz uploadanog fajla.
        Koristi lxml.etree.fromstring — brže od minidom, podržava large files.
        """
        self.root = etree.fromstring(xml_content)
        self.ns = _ns(self.root)

        # Pronađi Document element (ponekad je root, ponekad je child)
        self.doc = self.root
        if self.ns:
            doc_candidate = _xpath_first(self.root, 'n:BkToCstmrStmt', self.ns)
            if doc_candidate is not None:
                self.doc = doc_candidate

    def parse(self, company, import_batch: str = None) -> dict:
        """
        Parsira XML i kreira BankTransaction retke za zadanu company.

        Vraća:
          {
            'created': int,
            'skipped': int,   # duplikati
            'errors': int,
            'statements': int,
            'matched_accounts': list[str],  # IBAN-ovi koje smo pronašli
            'unresolved_ibans': list[str],  # IBAN-ovi kojih nema u BankAccount
          }
        """
        from konto.models import BankAccount, BankTransaction

        if not import_batch:
            import_batch = str(uuid.uuid4())[:8]

        stats = {
            'created': 0, 'skipped': 0, 'errors': 0,
            'statements': 0, 'matched_accounts': [], 'unresolved_ibans': [],
        }

        # Iteracija kroz Statement-e (jedan XML može imati više bankovnih računa)
        stmts = self.doc.xpath('.//n:Stmt', namespaces=self.ns) if self.ns \
            else self.doc.findall('.//{*}Stmt')

        for stmt in stmts:
            stats['statements'] += 1
            bank_account, stmt_iban = self._resolve_bank_account(
                stmt, company)

            if bank_account is None:
                if stmt_iban not in stats['unresolved_ibans']:
                    stats['unresolved_ibans'].append(stmt_iban)
                # Nastavljamo — kreiramo transakcije bez BankAccount veze
                # (mogu se naknadno dodijeliti)
            else:
                if stmt_iban not in stats['matched_accounts']:
                    stats['matched_accounts'].append(stmt_iban)

            # Iteracija kroz Ntry (stavke izvoda)
            entries = stmt.xpath('.//n:Ntry', namespaces=self.ns) if self.ns \
                else stmt.findall('.//{*}Ntry')

            for ntry in entries:
                try:
                    result = self._process_entry(
                        ntry, company, bank_account, import_batch)
                    if result == 'created':
                        stats['created'] += 1
                    elif result == 'skipped':
                        stats['skipped'] += 1
                    else:
                        stats['errors'] += 1
                except Exception:
                    stats['errors'] += 1

        return stats

    def _resolve_bank_account(self, stmt, company):
        """
        Čita IBAN iz Stmt/Acct/Id/IBAN i pronalazi BankAccount u bazi.
        Vraća (BankAccount|None, iban_string).
        """
        from konto.models import BankAccount

        iban = _xpath_text(stmt, './/n:Acct/n:Id/n:IBAN', self.ns)
        if not iban:
            # Fallback: neki bankovni sistemi koriste Othr/Id
            iban = _xpath_text(stmt, './/n:Acct/n:Id/n:Othr/n:Id', self.ns)

        if not iban:
            return None, ''

        # Normalizacija IBAN-a (makni razmake, uppercase)
        iban_clean = iban.replace(' ', '').upper()

        try:
            ba = BankAccount.objects.get(
                company=company,
                iban__iexact=iban_clean,
                is_active=True
            )
            return ba, iban_clean
        except BankAccount.DoesNotExist:
            return None, iban_clean

    def _process_entry(self, ntry, company, bank_account, import_batch) -> str:
        """
        Procesira jednu Ntry stavku.
        Vraća: 'created' | 'skipped' | 'error'
        """
        from konto.models import BankTransaction

        # ── 1. Iznos i tip transakcije ──────────────────────────────────────
        amt_text = _xpath_text(ntry, 'n:Amt', self.ns)
        if not amt_text:
            amt_text = _xpath_text(ntry, './/n:TxDtls/n:Amt/n:InstdAmt', self.ns)
        if not amt_text:
            return 'error'

        try:
            amount = Decimal(amt_text.replace(',', '.'))
        except InvalidOperation:
            return 'error'

        cdt_dbt = _xpath_text(ntry, 'n:CdtDbtInd', self.ns)
        txn_type = 'inflow' if cdt_dbt == 'CRDT' else 'outflow'

        # ── 2. Datumi ───────────────────────────────────────────────────────
        booking_date_str = _xpath_text(ntry, 'n:BookgDt/n:Dt', self.ns)
        value_date_str   = _xpath_text(ntry, 'n:ValDt/n:Dt', self.ns)

        txn_date  = self._parse_date(booking_date_str)
        value_date = self._parse_date(value_date_str)
        if txn_date is None:
            txn_date = datetime.date.today()

        # ── 3. Referenca transakcije (NtryRef iz banke) ─────────────────────
        ntry_ref = _xpath_text(ntry, 'n:NtryRef', self.ns)
        if not ntry_ref:
            ntry_ref = _xpath_text(ntry, './/n:AcctSvcrRef', self.ns)

        # ── 4. Poziv na broj (CdtrRefInf ili Ustrd) ─────────────────────────
        # Redoslijed: strukturirana referenca > slobodan tekst
        reference_number = _xpath_text(
            ntry, './/n:TxDtls/n:RmtInf/n:Strd/n:CdtrRefInf/n:Ref', self.ns)
        if not reference_number:
            reference_number = _xpath_text(
                ntry, './/n:TxDtls/n:RmtInf/n:Ustrd', self.ns)
        if not reference_number:
            reference_number = _xpath_text(ntry, './/n:RmtInf/n:Ustrd', self.ns)

        # ── 5. Platitelj/Primatelj ───────────────────────────────────────────
        # Za inflow: platitelj je Dbtr, za outflow: primatelj je Cdtr
        if txn_type == 'inflow':
            cp_name = _xpath_text(
                ntry, './/n:TxDtls/n:RltdPties/n:Dbtr/n:Nm', self.ns)
            cp_iban = _xpath_text(
                ntry, './/n:TxDtls/n:RltdPties/n:DbtrAcct/n:Id/n:IBAN', self.ns)
        else:
            cp_name = _xpath_text(
                ntry, './/n:TxDtls/n:RltdPties/n:Cdtr/n:Nm', self.ns)
            cp_iban = _xpath_text(
                ntry, './/n:TxDtls/n:RltdPties/n:CdtrAcct/n:Id/n:IBAN', self.ns)

        # Fallback za starije formate
        if not cp_name:
            cp_name = _xpath_text(ntry, './/n:NtryDtls/n:TxDtls/n:RltdPties/n:Dbtr/n:Nm', self.ns)

        description = _xpath_text(ntry, './/n:AddtlNtryInf', self.ns)
        if not description:
            description = reference_number

        # ── 6. external_id: sha256(iban + ntry_ref + datum + iznos) ─────────
        # Otporniji od samog NtryRef jer PBZ reciklira reference za storno txn
        iban_for_hash = (bank_account.iban if bank_account else 'UNKNOWN')
        raw_key = f"{iban_for_hash}|{ntry_ref}|{txn_date}|{amount}|{cdt_dbt}"
        external_id = hashlib.sha256(raw_key.encode()).hexdigest()[:64]

        # ── 7. Dedup + kreiranje ─────────────────────────────────────────────
        if BankTransaction.objects.filter(external_id=external_id).exists():
            return 'skipped'

        create_kwargs = dict(
            company=company,
            transaction_date=txn_date,
            value_date=value_date or txn_date,
            amount=amount,
            transaction_type=txn_type,
            counterparty_name=(cp_name or '')[:300],
            counterparty_iban=(cp_iban or '')[:34],
            description=(description or '')[:500],
            reference_number=(reference_number or '')[:100],
            status='unmatched',
            import_batch=import_batch,
            external_id=external_id,
        )
        if bank_account:
            create_kwargs['bank_account'] = bank_account

        BankTransaction.objects.create(**create_kwargs)
        return 'created'

    @staticmethod
    def _parse_date(s: str) -> Optional[datetime.date]:
        """Parsira ISO datum iz XML-a (YYYY-MM-DD ili YYYY-MM-DDThh:mm:ss)."""
        if not s:
            return None
        try:
            return datetime.date.fromisoformat(s[:10])
        except (ValueError, AttributeError):
            return None


# ─── pain.001 Generator ──────────────────────────────────────────────────────

class Pain001Generator:
    """
    SEPA pain.001.001.03 generator za masovna plaćanja.

    Podržava:
      - SUPP: plaćanje dobavljačima (iz odobrenih URA Invoice-a)
      - SALA: isplata plaća (iz EmployeeProfile + TimeEntry agregata)

    Koristi podatke koji već postoje u modelu:
      - Invoice.partner.iban / Invoice.partner.swift
      - Invoice.total, Invoice.number, Invoice.reference_number
      - EmployeeProfile.bank_account (IBAN), EmployeeProfile.hourly_rate
      - Company.iban, Company.swift (nalogodavac)
    """

    def __init__(self, company, bank_account, initiating_user=None):
        """
        company: Company instanca (nalogodavac)
        bank_account: BankAccount instanca (račun s kojeg se plaća)
        """
        self.company = company
        self.bank_account = bank_account
        self.user = initiating_user
        self.msg_id = f"FINA-{uuid.uuid4().hex[:16].upper()}"
        self.creation_dt = datetime.datetime.utcnow()

    def generate_supplier_payments(self, invoice_ids=None) -> bytes:
        """
        Generira pain.001 za plaćanje dobavljača.

        invoice_ids: lista pk-ova Invoice objeketa s doctype='R' i partner_type='supplier'
                     Ako None, uzima sve odobrene neplaćene URA fakture.

        Vraća: XML bytes spreman za upload u e-banking.
        """
        from invoicing.models import Invoice
        from partners.models import Partner

        if invoice_ids:
            invoices = Invoice.objects.filter(
                pk__in=invoice_ids,
                company=self.company,
            ).select_related('partner')
        else:
            # Sve neplaćene fakture prema dobavljačima
            supplier_ids = Partner.objects.filter(
                company=self.company,
                partner_type='supplier',
            ).values_list('pk', flat=True)

            invoices = Invoice.objects.filter(
                company=self.company,
                status__in=['UNPAID', 'OVERDUE'],
                doctype='R',
                partner__in=supplier_ids,
            ).select_related('partner')

        payments = []
        for inv in invoices:
            partner = getattr(inv, 'partner', None)
            if not partner:
                continue
            cdtr_iban = (partner.iban or '').replace(' ', '').upper()
            cdtr_bic  = (partner.swift or '').strip()
            if not cdtr_iban:
                continue  # Preskačemo dobavljače bez IBAN-a

            payments.append({
                'end_to_end_id': f"INV-{inv.number}",
                'amount': inv.total or Decimal('0'),
                'currency': inv.currency or 'EUR',
                'cdtr_name': partner.name[:70],
                'cdtr_iban': cdtr_iban,
                'cdtr_bic': cdtr_bic,
                'remittance_info': inv.reference_number or inv.number,
                'purpose_code': 'SUPP',
            })

        return self._build_xml(payments, purpose_batch='SUPP')

    def generate_salary_payments(self, period_start, period_end) -> bytes:
        """
        Generira pain.001 za isplatu plaća za zadano razdoblje.

        period_start, period_end: datetime.date
        Koristi TimeEntry(status='APPROVED') + EmployeeProfile.hourly_rate

        Vraća: XML bytes.
        """
        from worktime.models import TimeEntry, EmployeeProfile
        from django.db.models import Sum

        # Agregiraj odobrene sate po radniku za period
        entries = TimeEntry.objects.filter(
            company=self.company,
            status='APPROVED',
            date__gte=period_start,
            date__lte=period_end,
        ).values('user').annotate(
            total_hours=Sum('regular_hours'),
            overtime_hours=Sum('overtime_hours'),
        )

        payments = []
        for entry_agg in entries:
            try:
                emp = EmployeeProfile.objects.get(
                    user_id=entry_agg['user'],
                    company=self.company,
                )
            except EmployeeProfile.DoesNotExist:
                continue

            emp_iban = (emp.bank_account or '').replace(' ', '').upper()
            if not emp_iban:
                continue  # Radnik nema IBAN u profilu

            regular_h = entry_agg['total_hours'] or Decimal('0')
            overtime_h = entry_agg['overtime_hours'] or Decimal('0')
            gross = (regular_h * emp.hourly_rate +
                     overtime_h * emp.overtime_rate)

            if gross <= 0:
                continue

            full_name = emp.user.get_full_name() or emp.user.username

            payments.append({
                'end_to_end_id': f"SALA-{emp.user.pk}-{period_end.strftime('%Y%m')}",
                'amount': gross.quantize(Decimal('0.01')),
                'currency': 'EUR',
                'cdtr_name': full_name[:70],
                'cdtr_iban': emp_iban,
                'cdtr_bic': '',
                'remittance_info': (
                    f"Placa {period_start.strftime('%m/%Y')} "
                    f"{regular_h}h + {overtime_h}h OT"
                ),
                'purpose_code': 'SALA',
            })

        return self._build_xml(payments, purpose_batch='SALA')

    def _build_xml(self, payments: list, purpose_batch: str) -> bytes:
        """
        Gradi pain.001.001.03 XML strukturu.
        payments: lista dict-ova s ključevima iz generate_*_payments
        """
        if not payments:
            raise ValueError("Nema plaćanja za generiranje XML-a.")

        ctrl_sum = sum(p['amount'] for p in payments)
        nbof_txs = len(payments)

        NSMAP = {None: PAIN001_NS}
        doc = etree.Element('Document', nsmap=NSMAP)
        cstmr = etree.SubElement(doc, 'CstmrCdtTrfInitn')

        # ── GrpHdr ──────────────────────────────────────────────────────────
        grp = etree.SubElement(cstmr, 'GrpHdr')
        etree.SubElement(grp, 'MsgId').text = self.msg_id
        etree.SubElement(grp, 'CreDtTm').text = (
            self.creation_dt.strftime('%Y-%m-%dT%H:%M:%S'))
        etree.SubElement(grp, 'NbOfTxs').text = str(nbof_txs)
        etree.SubElement(grp, 'CtrlSum').text = str(ctrl_sum)

        initg = etree.SubElement(grp, 'InitgPty')
        etree.SubElement(initg, 'Nm').text = self.company.name[:70]
        if self.company.oib:
            id_el = etree.SubElement(initg, 'Id')
            org_id = etree.SubElement(id_el, 'OrgId')
            othr = etree.SubElement(org_id, 'Othr')
            etree.SubElement(othr, 'Id').text = self.company.oib

        # ── PmtInf ──────────────────────────────────────────────────────────
        pmt = etree.SubElement(cstmr, 'PmtInf')
        etree.SubElement(pmt, 'PmtInfId').text = f"{self.msg_id}-{purpose_batch}"
        etree.SubElement(pmt, 'PmtMtd').text = 'TRF'
        etree.SubElement(pmt, 'NbOfTxs').text = str(nbof_txs)
        etree.SubElement(pmt, 'CtrlSum').text = str(ctrl_sum)

        pmt_tp = etree.SubElement(pmt, 'PmtTpInf')
        svc_lvl = etree.SubElement(pmt_tp, 'SvcLvl')
        etree.SubElement(svc_lvl, 'Cd').text = 'SEPA'
        lcl_inst = etree.SubElement(pmt_tp, 'LclInstrm')
        etree.SubElement(lcl_inst, 'Cd').text = 'CORE'
        etree.SubElement(pmt_tp, 'CtgyPurp').text = purpose_batch

        # Datum izvršenja: sutra (banke odbijaju prošle datume)
        exec_date = (datetime.date.today() +
                     datetime.timedelta(days=1)).isoformat()
        etree.SubElement(pmt, 'ReqdExctnDt').text = exec_date

        # Nalogodavac (Debtor)
        dbtr = etree.SubElement(pmt, 'Dbtr')
        etree.SubElement(dbtr, 'Nm').text = self.company.name[:70]

        dbtr_acct = etree.SubElement(pmt, 'DbtrAcct')
        dbtr_id = etree.SubElement(dbtr_acct, 'Id')
        etree.SubElement(dbtr_id, 'IBAN').text = (
            self.bank_account.iban.replace(' ', '').upper())

        dbtr_agt = etree.SubElement(pmt, 'DbtrAgt')
        fin_inst = etree.SubElement(dbtr_agt, 'FinInstnId')
        if self.bank_account.swift:
            etree.SubElement(fin_inst, 'BIC').text = self.bank_account.swift
        else:
            etree.SubElement(fin_inst, 'Othr').text = 'NOTPROVIDED'

        # ── CdtTrfTxInf (jedna po primatelju) ───────────────────────────────
        for p in payments:
            tx = etree.SubElement(pmt, 'CdtTrfTxInf')

            pmt_id = etree.SubElement(tx, 'PmtId')
            etree.SubElement(pmt_id, 'EndToEndId').text = p['end_to_end_id'][:35]

            amt_el = etree.SubElement(tx, 'Amt')
            inst_amt = etree.SubElement(amt_el, 'InstdAmt')
            inst_amt.set('Ccy', p['currency'])
            inst_amt.text = str(p['amount'])

            if p.get('cdtr_bic'):
                cdtr_agt = etree.SubElement(tx, 'CdtrAgt')
                fi = etree.SubElement(cdtr_agt, 'FinInstnId')
                etree.SubElement(fi, 'BIC').text = p['cdtr_bic']

            cdtr = etree.SubElement(tx, 'Cdtr')
            etree.SubElement(cdtr, 'Nm').text = p['cdtr_name']

            cdtr_acct = etree.SubElement(tx, 'CdtrAcct')
            cdtr_id = etree.SubElement(cdtr_acct, 'Id')
            etree.SubElement(cdtr_id, 'IBAN').text = p['cdtr_iban']

            # Svrha plaćanja (SALA/SUPP)
            purp = etree.SubElement(tx, 'Purp')
            etree.SubElement(purp, 'Cd').text = p['purpose_code']

            # Poziv na broj / opis
            rmt = etree.SubElement(tx, 'RmtInf')
            etree.SubElement(rmt, 'Ustrd').text = p['remittance_info'][:140]

        return etree.tostring(
            doc,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8',
        )


# ─── Parcijalne uplate — query za dashboard widget ──────────────────────────

def get_partial_payment_discrepancies(company):
    """
    Vraća listu pariranih transakcija gdje uplata NE pokriva puni iznos računa.

    Koristi se za 'Financijska odstupanja' widget na Kontrolnom Tornju.
    N+1 zaštita: jedan annotate upit, nema petlje po Invoice-ima.

    Vraća queryset dict-ova:
      {
        'invoice_id': int,
        'invoice_number': str,
        'invoice_total': Decimal,
        'total_paid': Decimal,
        'gap': Decimal,         # razlika (negativna = preplata)
        'client_name': str,
        'days_overdue': int,
      }
    """
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce
    from django.utils import timezone
    from konto.models import BankTransaction
    from invoicing.models import Invoice

    today = timezone.now().date()

    # Sve partirane transakcije za ovu tvrtku, grupirane po računu
    paid_by_invoice = (
        BankTransaction.objects
        .filter(
            company=company,
            status='matched',
            transaction_type='inflow',
            matched_invoice__isnull=False,
        )
        .values('matched_invoice')
        .annotate(total_paid=Sum('amount'))
    )
    paid_map = {row['matched_invoice']: row['total_paid']
                for row in paid_by_invoice}

    if not paid_map:
        return []

    # Dohvati račune koji imaju barem jednu pariranu transakciju
    invoices = Invoice.objects.filter(
        company=company,
        pk__in=paid_map.keys(),
        status__in=['UNPAID', 'OVERDUE', 'PAID'],
    ).only('pk', 'number', 'total', 'client_name', 'date_due')

    discrepancies = []
    for inv in invoices:
        inv_total = inv.total or Decimal('0')
        total_paid = paid_map.get(inv.pk, Decimal('0'))
        gap = inv_total - total_paid

        # Preskači ako je razlika manja od 0.01 € (floating point šum)
        if abs(gap) < Decimal('0.01'):
            continue

        days_overdue = 0
        if inv.date_due and inv.date_due < today:
            days_overdue = (today - inv.date_due).days

        discrepancies.append({
            'invoice_id': inv.pk,
            'invoice_number': inv.number,
            'invoice_total': inv_total,
            'total_paid': total_paid,
            'gap': gap,
            'client_name': inv.client_name,
            'days_overdue': days_overdue,
        })

    # Sortiraj: najstarija odstupanja gore
    discrepancies.sort(key=lambda x: x['days_overdue'], reverse=True)
    return discrepancies
