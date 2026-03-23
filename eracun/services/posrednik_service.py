"""
e-Racun Posrednik Service — slanje/primanje e-racuna kroz registrirane posrednike.

Podrzani posrednici:
1. Moj-eRacun.hr (FINA ovlasteni) — API REST
2. Fina eRacun (direktno) — SOAP/AS4
3. Custom API (bilo koji posrednik s REST API-jem)

Usage:
    from eracun.services.posrednik_service import PosrednikService
    result = PosrednikService.send(eracun)
    inbox = PosrednikService.fetch_inbox(company)
"""
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('eracun.posrednik')


class PosrednikService:
    """Univerzalni servis za slanje e-racuna kroz posrednike."""

    # Registrirani posrednici u HR
    POSREDNICI = {
        'moj_eracun': {
            'name': 'Moj-eRacun.hr',
            'api_base': 'https://api.moj-eracun.hr/v1',
            'test_base': 'https://test-api.moj-eracun.hr/v1',
            'auth': 'bearer',  # Bearer token
            'formats': ['UBL2.1', 'CII'],
        },
        'fina_eracun': {
            'name': 'FINA eRacun',
            'api_base': 'https://eracun.fina.hr/api/v1',
            'test_base': 'https://test-eracun.fina.hr/api/v1',
            'auth': 'certificate',  # Mutual TLS
            'formats': ['UBL2.1'],
        },
        'custom': {
            'name': 'Custom API',
            'api_base': '',
            'auth': 'bearer',
            'formats': ['UBL2.1', 'CII', 'ZUGFeRD'],
        },
    }

    @classmethod
    def get_config(cls, company):
        """
        Dohvati posrednik konfiguraciju.
        Prvo trazi u ERacunConfig (per-company settings page),
        fallback na company.settings['posrednik'] (JSON).
        Svaki komitent moze imati svog posrednika.
        """
        # Primarno: ERacunConfig model (settings page)
        try:
            from eracun.models import ERacunConfig
            ec = ERacunConfig.objects.filter(company=company).first()
            if ec and getattr(ec, 'posrednik_type', ''):
                return {
                    'type': ec.posrednik_type or 'moj_eracun',
                    'api_key': getattr(ec, 'posrednik_api_key', '') or '',
                    'api_secret': getattr(ec, 'posrednik_api_secret', '') or '',
                    'api_url': getattr(ec, 'posrednik_api_url', '') or '',
                    'username': getattr(ec, 'posrednik_username', '') or '',
                    'password': getattr(ec, 'posrednik_password', '') or '',
                    'test_mode': getattr(ec, 'posrednik_test_mode', True),
                    'auto_send': getattr(ec, 'is_active', False),
                    'company_id': getattr(ec, 'posrednik_company_id', '') or '',
                }
        except Exception:
            pass

        # Fallback: company.settings JSON
        cfg = company.settings.get('posrednik', {}) if company.settings else {}
        return {
            'type': cfg.get('type', 'moj_eracun'),
            'api_key': cfg.get('api_key', ''),
            'api_secret': cfg.get('api_secret', ''),
            'api_url': cfg.get('api_url', ''),
            'username': cfg.get('username', ''),
            'password': cfg.get('password', ''),
            'test_mode': cfg.get('test_mode', True),
            'auto_send': cfg.get('auto_send', False),
        }

    @classmethod
    def is_configured(cls, company):
        """Provjeri ima li firma konfiguriranog posrednika."""
        cfg = cls.get_config(company)
        return bool(cfg.get('api_key') or cfg.get('username'))

    @classmethod
    def send(cls, eracun):
        """
        Posalji e-racun kroz posrednika.

        Args:
            eracun: ERacun model objekt

        Returns:
            dict: {ok, posrednik_id, message} ili {ok: False, error}
        """
        company = eracun.company
        cfg = cls.get_config(company)

        if not cls.is_configured(company):
            return {'ok': False, 'error': 'Posrednik nije konfiguriran. Postavke: /eracun/settings/'}

        posrednik_type = cfg['type']

        # Generiraj XML
        from eracun.services.ubl_generator import generate_ubl_xml
        xml_content = generate_ubl_xml(eracun)

        # Pre-flight validacija (Rupa 1)
        try:
            from eracun.services.validator import validate_full
            v_ok, v_err, v_warn = validate_full(xml_content)
            if not v_ok:
                return {'ok': False, 'error': 'XML validacija: ' + '; '.join(v_err[:3])}
        except Exception:
            pass  # Graceful — ne blokiraj slanje ako validator crashne

        # Update status
        eracun.status = 'sending'
        eracun.save(update_fields=['status'])

        try:
            if posrednik_type == 'moj_eracun':
                result = cls._send_moj_eracun(eracun, xml_content, cfg)
            elif posrednik_type == 'fina_eracun':
                result = cls._send_fina(eracun, xml_content, cfg)
            elif posrednik_type == 'custom':
                result = cls._send_custom(eracun, xml_content, cfg)
            else:
                result = {'ok': False, 'error': 'Nepoznat tip posrednika: %s' % posrednik_type}

            if result.get('ok'):
                eracun.status = 'sent'
                eracun.fina_uuid = result.get('posrednik_id', '')
                eracun.save(update_fields=['status', 'fina_uuid'])

                # Log
                from eracun.models import ERacunLog
                ERacunLog.objects.create(
                    eracun=eracun,
                    action='send',
                    status='success',
                    details='Poslano kroz %s: %s' % (posrednik_type, result.get('posrednik_id', '')),
                )

                logger.info('e-Racun %s poslan kroz %s: %s', eracun.invoice_number, posrednik_type, result)
            else:
                eracun.status = 'error'
                eracun.error_message = result.get('error', '')[:500]
                eracun.save(update_fields=['status', 'error_message'])

                from eracun.models import ERacunLog
                ERacunLog.objects.create(
                    eracun=eracun,
                    action='send',
                    status='error',
                    details=result.get('error', ''),
                )

            return result

        except Exception as e:
            eracun.status = 'error'
            eracun.error_message = str(e)[:500]
            eracun.save(update_fields=['status', 'error_message'])
            logger.error('Posrednik send error: %s', e)
            return {'ok': False, 'error': str(e)}

    @classmethod
    def _send_moj_eracun(cls, eracun, xml_content, cfg):
        """Slanje kroz Moj-eRacun.hr API."""
        base = cfg.get('test_base', cls.POSREDNICI['moj_eracun']['test_base']) if cfg.get('test_mode') else cls.POSREDNICI['moj_eracun']['api_base']
        api_key = cfg.get('api_key', '')

        try:
            resp = requests.post(
                '%s/outgoing-invoices' % base,
                headers={
                    'Authorization': 'Bearer %s' % api_key,
                    'Content-Type': 'application/xml',
                    'Accept': 'application/json',
                },
                data=xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content,
                timeout=30,
            )

            if resp.status_code in (200, 201, 202):
                data = resp.json()
                return {
                    'ok': True,
                    'posrednik_id': data.get('id', data.get('invoiceId', '')),
                    'message': 'Poslano na Moj-eRacun.hr',
                    'status': data.get('status', 'sent'),
                }
            else:
                return {
                    'ok': False,
                    'error': 'Moj-eRacun HTTP %d: %s' % (resp.status_code, resp.text[:200]),
                }

        except requests.Timeout:
            return {'ok': False, 'error': 'Moj-eRacun timeout (30s)'}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @classmethod
    def _send_fina(cls, eracun, xml_content, cfg):
        """Slanje direktno kroz FINA eRacun (AS4/SOAP)."""
        # FINA zahtijeva mutual TLS s certifikatom
        return {'ok': False, 'error': 'FINA direktno slanje zahtijeva certifikat posrednika (ISO 27001). Koristite Moj-eRacun.hr.'}

    @classmethod
    def _send_custom(cls, eracun, xml_content, cfg):
        """Slanje kroz custom API posrednika."""
        api_url = cfg.get('api_url', '')
        api_key = cfg.get('api_key', '')

        if not api_url:
            return {'ok': False, 'error': 'Custom API URL nije konfiguriran'}

        try:
            resp = requests.post(
                api_url,
                headers={
                    'Authorization': 'Bearer %s' % api_key,
                    'Content-Type': 'application/xml',
                },
                data=xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content,
                timeout=30,
            )
            if resp.status_code in (200, 201, 202):
                return {'ok': True, 'posrednik_id': '', 'message': 'Poslano na custom posrednik'}
            else:
                return {'ok': False, 'error': 'HTTP %d: %s' % (resp.status_code, resp.text[:200])}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @classmethod
    def fetch_inbox(cls, company, since=None):
        """Dohvati primljene e-racune od posrednika."""
        cfg = cls.get_config(company)
        if not cls.is_configured(company):
            return {'ok': False, 'error': 'Posrednik nije konfiguriran'}

        posrednik_type = cfg['type']
        if posrednik_type != 'moj_eracun':
            return {'ok': False, 'error': 'Inbox fetch podrzano samo za Moj-eRacun.hr'}

        base = cfg.get('test_base', cls.POSREDNICI['moj_eracun']['test_base']) if cfg.get('test_mode') else cls.POSREDNICI['moj_eracun']['api_base']
        api_key = cfg.get('api_key', '')

        try:
            params = {}
            if since:
                params['since'] = since.isoformat()

            resp = requests.get(
                '%s/incoming-invoices' % base,
                headers={
                    'Authorization': 'Bearer %s' % api_key,
                    'Accept': 'application/json',
                },
                params=params,
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                invoices = data.get('invoices', data.get('items', []))
                return {
                    'ok': True,
                    'count': len(invoices),
                    'invoices': invoices,
                }
            else:
                return {'ok': False, 'error': 'HTTP %d' % resp.status_code}

        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @classmethod
    def get_incoming_xml(cls, company, invoice_id):
        """
        Two-Step Fetch: dohvati puni UBL 2.1 XML za ulazni račun po ID-u.
        Vraća XML string ili None.
        """
        cfg = cls.get_config(company)
        if not cls.is_configured(company):
            return None

        posrednik_type = cfg['type']
        base = (
            cfg.get('test_base', cls.POSREDNICI.get(posrednik_type, {}).get('test_base', ''))
            if cfg.get('test_mode')
            else cls.POSREDNICI.get(posrednik_type, {}).get('api_base', '')
        )
        api_key = cfg.get('api_key', '')

        if not base:
            return None

        try:
            resp = requests.get(
                '%s/incoming-invoices/%s/xml' % (base, invoice_id),
                headers={
                    'Authorization': 'Bearer %s' % api_key,
                    'Accept': 'application/xml, application/json',
                },
                timeout=15,
            )

            if resp.status_code != 200:
                logger.warning('get_incoming_xml HTTP %d for %s', resp.status_code, invoice_id)
                return None

            content_type = resp.headers.get('Content-Type', '')

            # Ako posrednik vraća JSON s base64 kodiranim XML-om
            if 'application/json' in content_type:
                import base64
                data = resp.json()
                xml_b64 = data.get('Xml', '') or data.get('Document', '') or data.get('xml', '')
                if xml_b64:
                    try:
                        return base64.b64decode(xml_b64).decode('utf-8')
                    except Exception:
                        return xml_b64  # Možda nije base64
                return None

            # Čisti XML response
            return resp.text

        except Exception as e:
            logger.error('get_incoming_xml error for %s: %s', invoice_id, e)
            return None

    @classmethod
    def check_status(cls, eracun):
        """Provjeri status poslanog e-racuna kod posrednika."""
        cfg = cls.get_config(eracun.company)
        if not eracun.fina_uuid:
            return {'status': 'unknown', 'error': 'Nema posrednik ID'}

        posrednik_type = cfg['type']
        if posrednik_type != 'moj_eracun':
            return {'status': eracun.status}

        base = cls.POSREDNICI['moj_eracun']['test_base'] if cfg.get('test_mode') else cls.POSREDNICI['moj_eracun']['api_base']

        try:
            resp = requests.get(
                '%s/outgoing-invoices/%s' % (base, eracun.fina_uuid),
                headers={'Authorization': 'Bearer %s' % cfg.get('api_key', '')},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get('status', '').lower()
                if status in ('delivered', 'accepted'):
                    eracun.status = 'accepted'
                elif status in ('rejected',):
                    eracun.status = 'rejected'
                    eracun.error_message = data.get('rejectReason', '')
                eracun.save(update_fields=['status', 'error_message'])
                return {'status': eracun.status, 'data': data}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

        return {'status': eracun.status}
