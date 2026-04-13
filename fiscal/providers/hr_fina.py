"""
HR Fiskalizacija - FINA CIS provider
Prema: Zakon o fiskalizaciji u prometu gotovinom (NN 133/12, 115/16, 106/18)
ZKI: RSA-MD5 potpis prema Pravilniku
CIS SOAP: https://cis.porezna-uprava.hr:8449/FiskalizacijaService
"""
import hashlib
import logging
import os
import tempfile
import uuid
from datetime import datetime

from ..base import BaseFiscalProvider, FiscalResult

logger = logging.getLogger(__name__)

CIS_TEST = "https://cistest.porezna-uprava.hr:8449/FiskalizacijaService"
CIS_PROD = "https://cis.porezna-uprava.hr:8449/FiskalizacijaService"


class HRFinaProvider(BaseFiscalProvider):

    def fiscalize(self, receipt_data: dict) -> FiscalResult:
        cert_path = self._get_cert_path()
        cert_password = self.config.certificate_password

        zki = self._generate_zki(receipt_data, cert_path, cert_password)

        if self.config.is_test_mode and not cert_path:
            mock_jir = str(uuid.uuid4())
            return FiscalResult(
                success=True, zki=zki, jir=mock_jir,
                raw_request='TEST MODE - no CIS call',
                raw_response='mock JIR: ' + mock_jir,
            )

        result = self._send_to_cis(receipt_data, zki, cert_path, cert_password)

        # Fallback: u test modu, ako CIS vrati gresku, generiraj mock JIR
        if not result.success and self.config.is_test_mode:
            mock_jir = str(uuid.uuid4())
            logger.warning('CIS test failed (%s), using mock JIR: %s', result.raw_response[:80] if result.raw_response else 'unknown', mock_jir)
            return FiscalResult(
                success=True, zki=zki, jir=mock_jir,
                raw_request=result.raw_request,
                raw_response='MOCK FALLBACK (CIS error): ' + mock_jir,
            )

        return result

    def test_connection(self) -> bool:
        return self.echo()

    def echo(self) -> bool:
        try:
            import requests
            endpoint = CIS_PROD if not self.config.is_test_mode else CIS_TEST
            soap = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
                ' xmlns:tns="http://www.apis-it.hr/fin/2012/types/f73">'
                '<soapenv:Body><tns:EchoRequest>test</tns:EchoRequest></soapenv:Body>'
                '</soapenv:Envelope>'
            )
            _v = False if 'cistest' in endpoint else True
            r = requests.post(endpoint, data=soap.encode('utf-8'),
                              headers={'Content-Type': 'text/xml; charset=utf-8'},
                              timeout=(1.5, 2), verify=_v)
            return r.status_code == 200
        except requests.RequestException as e:
            logger.error("CIS echo failed: %s", e)
            return False

    def _get_cert_path(self):
        if self.config.certificate_file:
            return self.config.certificate_file.path
        return None

    def _generate_zki(self, data, cert_path=None, cert_password=None):
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives.serialization import pkcs12

            if cert_path and os.path.exists(cert_path):
                with open(cert_path, 'rb') as f:
                    cert_data = f.read()
                password = cert_password.encode() if cert_password else None
                private_key, certificate, _ = pkcs12.load_key_and_certificates(
                    cert_data, password, default_backend()
                )
            else:
                return self._demo_zki(data)

            dt = data['datetime'].strftime('%d.%m.%YT%H:%M:%S')
            premise = self.config.business_premise_id or 'PP1'
            device = self.config.device_id or '1'

            sign_data = (
                "{oib}{dt}{seq}{premise}{device}{total}".format(
                    oib=self.config.oib,
                    dt=dt,
                    seq=data['receipt_number'].split('/')[0],
                    premise=premise,
                    device=device,
                    total="{:.2f}".format(data['total_amount']),
                )
            )

            signature = private_key.sign(
                sign_data.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.MD5()
            )
            zki = hashlib.md5(signature).hexdigest()
            logger.info("ZKI generiran: %s...", zki[:8])
            return zki

        except ImportError:
            logger.warning("cryptography not installed - using demo ZKI")
            return self._demo_zki(data)
        except (FileNotFoundError, PermissionError, IOError) as e:
            logger.error("ZKI error: %s", e)
            return self._demo_zki(data)

    def _demo_zki(self, data):
        raw = "{oib}{dt}{num}{total}".format(
            oib=self.config.oib,
            dt=data['datetime'].strftime('%d.%m.%YT%H:%M:%S'),
            num=data['receipt_number'],
            total="{:.2f}".format(data['total_amount']),
        )
        return hashlib.md5(raw.encode()).hexdigest()

    def _send_to_cis(self, data, zki, cert_path, cert_password):
        try:
            import requests
            from lxml import etree

            endpoint = CIS_PROD if not self.config.is_test_mode else CIS_TEST
            premise = self.config.business_premise_id or 'PP1'
            device = self.config.device_id or '1'
            dt_str = data['datetime'].strftime('%d.%m.%YT%H:%M:%S')
            receipt_seq = data['receipt_number'].split('/')[0]
            poruka_id = str(uuid.uuid4())

            pdv_xml = ""
            for tax in data.get('tax_amounts', []):
                if tax['base'] > 0:
                    pdv_xml += (
                        "\n                <tns:Porez>"
                        "\n                    <tns:Stopa>{rate:.2f}</tns:Stopa>"
                        "\n                    <tns:Osnovica>{base:.2f}</tns:Osnovica>"
                        "\n                    <tns:Iznos>{amount:.2f}</tns:Iznos>"
                        "\n                </tns:Porez>"
                    ).format(rate=tax['rate'], base=tax['base'], amount=tax['amount'])

            payment_code = self._payment_code(data.get('payments') or data.get('payment_method', 'cash'))
            operator_oib = data.get('operator_oib', self.config.oib)

            ns = "http://www.apis-it.hr/fin/2012/types/f73"
            soap_ns = "http://schemas.xmlsoap.org/soap/envelope/"

            soap_body = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<soapenv:Envelope xmlns:soapenv="{soap_ns}" xmlns:tns="{ns}">\n'
                '    <soapenv:Header/>\n'
                '    <soapenv:Body>\n'
                '        <tns:RacunZahtjev Id="RacunZahtjev">\n'
                '            <tns:Zaglavlje>\n'
                '                <tns:IdPoruke>{poruka_id}</tns:IdPoruke>\n'
                '                <tns:DatumVrijeme>{now}</tns:DatumVrijeme>\n'
                '            </tns:Zaglavlje>\n'
                '            <tns:Racun>\n'
                '                <tns:Oib>{oib}</tns:Oib>\n'
                '                <tns:USustPdv>true</tns:USustPdv>\n'
                '                <tns:DatVrijeme>{dt_str}</tns:DatVrijeme>\n'
                '                <tns:OznSlijed>P</tns:OznSlijed>\n'
                '                <tns:BrRac>\n'
                '                    <tns:BrOznRac>{receipt_seq}</tns:BrOznRac>\n'
                '                    <tns:OznPosPr>{premise}</tns:OznPosPr>\n'
                '                    <tns:OznNapUr>{device}</tns:OznNapUr>\n'
                '                </tns:BrRac>\n'
                '                <tns:Pdv>{pdv_xml}\n'
                '                </tns:Pdv>\n'
                '                <tns:IznosUkupno>{total:.2f}</tns:IznosUkupno>\n'
                '                <tns:NacinPlac>{payment_code}</tns:NacinPlac>\n'
                '                <tns:OibOper>{operator_oib}</tns:OibOper>\n'
                '                <tns:ZastKod>{zki}</tns:ZastKod>\n'
                '                <tns:NakDost>false</tns:NakDost>\n'
                '            </tns:Racun>\n'
                '        </tns:RacunZahtjev>\n'
                '    </soapenv:Body>\n'
                '</soapenv:Envelope>'
            ).format(
                soap_ns=soap_ns, ns=ns, poruka_id=poruka_id,
                now=datetime.now().strftime('%d.%m.%YT%H:%M:%S'),
                oib=self.config.oib, dt_str=dt_str,
                receipt_seq=receipt_seq, premise=premise, device=device,
                pdv_xml=pdv_xml, total=data['total_amount'],
                payment_code=payment_code, operator_oib=operator_oib, zki=zki,
            )

            if cert_path and os.path.exists(cert_path):
                soap_body = self._sign_xml(soap_body, cert_path, cert_password)

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': ns + '/RacunZahtjev',
            }
            cert_tuple = self._extract_pem(cert_path, cert_password) if cert_path else None

            _v = False if 'cistest' in endpoint else True
            response = requests.post(
                endpoint, data=soap_body.encode('utf-8'),
                headers=headers, cert=cert_tuple, verify=_v, timeout=(1.5, 2)
            )

            if response.status_code == 200:
                root = etree.fromstring(response.content)
                jir_el = root.find('.//{%s}Jir' % ns)
                if jir_el is not None and jir_el.text:
                    return FiscalResult(
                        success=True, zki=zki, jir=jir_el.text,
                        raw_request=soap_body, raw_response=response.text
                    )
                greska = root.find('.//{%s}Greska' % ns)
                if greska is not None:
                    sifra = greska.findtext('{%s}SifraGreske' % ns, '?')
                    poruka = greska.findtext('{%s}PorukaGreske' % ns, response.text[:200])
                    err = "CIS greska %s: %s" % (sifra, poruka)
                    return FiscalResult(
                        success=False, zki=zki, error_message=err,
                        raw_request=soap_body, raw_response=response.text
                    )

            return FiscalResult(
                success=False, zki=zki,
                error_message="HTTP %d: %s" % (response.status_code, response.text[:200]),
                raw_request=soap_body, raw_response=response.text
            )

        except OSError as e:
            logger.error("CIS error: %s", e)
            if self.config.is_test_mode:
                mock_jir = str(uuid.uuid4())
                return FiscalResult(
                    success=True, zki=zki, jir=mock_jir,
                    error_message="CIS nedostupan (test mode): %s" % e,
                )
            return FiscalResult(success=False, zki=zki, error_message=str(e))

    @staticmethod
    def _payment_code(method_or_list):
        """
        FINA NacinPlac: G=Gotovina, K=Kartica, T=Transakcijski, O=Ostalo.
        Pravilo: ako ima CASH → uvijek G (čl. 9 Zakona o fiskalizaciji).
        """
        single = {
            'cash': 'G', 'gotovina': 'G', 'voucher': 'G',
            'card': 'K', 'kartica': 'K',
            'transfer': 'T', 'transakcijski': 'T', 'virman': 'T', 'account': 'T',
            'mobile': 'O', 'revolut': 'O', 'aircash': 'O', 'crypto': 'O',
        }
        if isinstance(method_or_list, list):
            methods = {str(p.get('method', p) if isinstance(p, dict) else p).lower()
                       for p in method_or_list}
            if methods & {'cash', 'gotovina', 'voucher'}:
                return 'G'
            if methods <= {'card', 'kartica'}:
                return 'K'
            if methods <= {'transfer', 'transakcijski', 'virman', 'account'}:
                return 'T'
            return 'O'
        return single.get(str(method_or_list).lower(), 'O')

    @staticmethod
    def _sign_xml(xml_string, cert_path, cert_password):
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import pkcs12
            from lxml import etree
            from signxml import XMLSigner

            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            password = cert_password.encode() if cert_password else None
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                cert_data, password, default_backend()
            )
            root = etree.fromstring(xml_string.encode())
            signer = XMLSigner(method=XMLSigner.transform_enveloped)
            signed = signer.sign(root, key=private_key, cert=certificate)
            return etree.tostring(signed, encoding='unicode')
        except (FileNotFoundError, PermissionError, IOError) as e:
            logger.warning("XML signing failed: %s", e)
            return xml_string

    @staticmethod
    def _extract_pem(cert_path, cert_password):
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, pkcs12

            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            password = cert_password.encode() if cert_password else None
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                cert_data, password, default_backend()
            )
            key_file = tempfile.NamedTemporaryFile(delete=False, suffix='.key')
            cert_file = tempfile.NamedTemporaryFile(delete=False, suffix='.crt')
            key_file.write(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
            cert_file.write(certificate.public_bytes(Encoding.PEM))
            key_file.close()
            cert_file.close()
            return (cert_file.name, key_file.name)
        except (FileNotFoundError, PermissionError, IOError) as e:
            logger.warning("PEM extraction failed: %s", e)
            return None
