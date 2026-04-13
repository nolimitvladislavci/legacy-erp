"""
invoicing/services/fiscal_f20.py
Fiskalizacija 2.0 handler — delegira na informacijskog posrednika.
"""
import logging
from .entry_point import BaseFiscalHandler, FiscalResult
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


class ERacunFiskalizacija20Handler(BaseFiscalHandler):
    """
    Delegira e-Racun na informacijskog posrednika (FINA, Moj-eRacun, PONDI).
    Koristi posrednikov API za slanje, ne gradi vlastiti AS4 stack.
    """

    def __init__(self, company):
        self.company = company
        self._config = None

    @property
    def config(self):
        if not self._config:
            try:
                self._config = self.company.eracun_config
            except AttributeError:
                self._config = None
        return self._config

    def can_process(self, invoice) -> bool:
        return (
            getattr(invoice, 'country', 'HR') == 'HR'
            and invoice.doctype in ('R', 'FA')
            and self.config is not None
            and self.config.is_active
        )

    def process(self, invoice) -> FiscalResult:
        """
        1. Generiraj UBL XML (nas kod)
        2. Posalji posredniku putem API-ja (njihov kod)
        3. Zapisi rezultat
        """
        from eracun.models import ERacunLog
        from eracun.services.ubl_generator import generate_ubl_xml

        try:
            # 1. Kreiraj ERacun zapis
            eracun = self._create_eracun_record(invoice)

            # 2. Generiraj UBL XML s KPD siframa
            xml_string = generate_ubl_xml(eracun)
            eracun.xml_request = xml_string
            eracun.save(update_fields=['xml_request'])

            # 3. Posalji posredniku
            posrednik = self._get_posrednik()
            if posrednik:
                result = posrednik.send(eracun, xml_string)
                eracun.posrednik_status = result.get('status', 'sent')
                eracun.posrednik_id = result.get('id', '')
                eracun.posrednik_response = result
                eracun.status = 'sent'
                eracun.sent_at = __import__('django.utils.timezone', fromlist=['now']).now()
            else:
                # Nema posrednika — samo spremi XML
                eracun.posrednik_status = 'pending'
                eracun.status = 'valid'

            eracun.save()

            ERacunLog.objects.create(
                eracun=eracun,
                action='fiscal_f20',
                status=eracun.status,
                message=f'Fiskalizacija 2.0: {eracun.posrednik or "pending"}',
                details={'posrednik': eracun.posrednik, 'handler': 'ERacunFiskalizacija20Handler'},
            )

            return FiscalResult(
                success=True,
                message=f'e-Racun kreiran ({eracun.posrednik_status})',
                raw_response={'eracun_id': str(eracun.id)},
            )

        except (IntegrityError, DatabaseError) as e:
            logger.exception('Fiskalizacija 2.0 error')
            return FiscalResult(success=False, message=str(e))

    def _create_eracun_record(self, invoice):
        """Create ERacun record from Invoice."""
        from eracun.models import ERacun, ERacunItem

        eracun = ERacun.objects.create(
            company=self.company,
            direction='outgoing',
            invoice=invoice,
            doc_type='380',
            invoice_number=invoice.number,
            issue_date=invoice.date_issued.date() if hasattr(invoice.date_issued, 'date') else invoice.date_issued,
            due_date=invoice.date_due,
            currency=getattr(invoice, 'currency', 'EUR'),

            issuer_name=invoice.issuer_name or self.company.name,
            issuer_oib=invoice.issuer_oib or self.company.oib,
            issuer_address=invoice.issuer_address or '',
            issuer_iban=invoice.issuer_iban or '',

            recipient_name=invoice.client_name,
            recipient_oib=invoice.client_oib or '',
            recipient_address=invoice.client_address or '',
            recipient_city=invoice.client_city or '',

            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            total=invoice.total,

            note=invoice.note or '',
            posrednik=self.config.posrednik if hasattr(self.config, 'posrednik') else '',
            status='draft',
        )

        # Copy items with KPD codes
        for item in invoice.items.all():
            kpd = ''
            if hasattr(item, 'inventory_item') and item.inventory_item:
                kpd = getattr(item.inventory_item, 'nkd_code', '') or ''

            ERacunItem.objects.create(
                eracun=eracun,
                line_number=item.pk,
                description=item.description,
                quantity=item.quantity,
                unit_code='EA',
                unit_price=item.unit_price,
                discount_percent=item.discount_percent,
                line_total=item.total_price,
                tax_category='S',
                tax_rate=item.tax_rate,
                kpd_code=kpd,
            )

        return eracun

    def _get_posrednik(self):
        """Get posrednik API client based on config."""
        posrednik_name = getattr(self.config, 'posrednik', '') if self.config else ''

        if posrednik_name == 'fina':
            return FINAPosrednikAPI(self.config)
        elif posrednik_name == 'moj_eracun':
            return MojERacunAPI(self.config)
        elif posrednik_name == 'pondi':
            return PondiAPI(self.config)

        # Nema konfiguriranog posrednika
        return None


# === Posrednik API adapteri (placeholder — implementacija kad se odabere posrednik) ===

class BasePosrednikAPI:
    """Base class for posrednik API integration."""

    def __init__(self, config):
        self.config = config

    def send(self, eracun, xml_string) -> dict:
        raise NotImplementedError

    def check_status(self, posrednik_id) -> dict:
        raise NotImplementedError


class FINAPosrednikAPI(BasePosrednikAPI):
    """FINA e-Racun posrednik API."""

    def send(self, eracun, xml_string) -> dict:
        # TODO: Implementirati kad FINA dostavi API specifikaciju
        # Kontakt: peppol@fina.hr
        logger.info(f'FINA API: would send {eracun.invoice_number}')
        return {'status': 'pending', 'id': '', 'message': 'FINA API not yet configured'}

    def check_status(self, posrednik_id) -> dict:
        return {'status': 'pending'}


class MojERacunAPI(BasePosrednikAPI):
    """Moj-eRacun.hr posrednik API."""

    def send(self, eracun, xml_string) -> dict:
        # TODO: Implementirati kad se sklopi ugovor s Moj-eRacun
        logger.info(f'Moj-eRacun API: would send {eracun.invoice_number}')
        return {'status': 'pending', 'id': '', 'message': 'Moj-eRacun API not yet configured'}

    def check_status(self, posrednik_id) -> dict:
        return {'status': 'pending'}


class PondiAPI(BasePosrednikAPI):
    """ePoslovanje (PONDI) posrednik API."""

    def send(self, eracun, xml_string) -> dict:
        logger.info(f'PONDI API: would send {eracun.invoice_number}')
        return {'status': 'pending', 'id': '', 'message': 'PONDI API not yet configured'}

    def check_status(self, posrednik_id) -> dict:
        return {'status': 'pending'}
