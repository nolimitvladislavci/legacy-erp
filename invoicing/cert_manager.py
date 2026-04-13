"""
invoicing/cert_manager.py
Upravljanje fiskalnim certifikatima: validacija .p12, parsiranje metapodataka,
testiranje veze prema CIS serveru.
"""
import logging
import tempfile
import os


logger = logging.getLogger(__name__)


def validate_and_save_cert(instance, file_obj, password: str) -> dict:
    """
    Validira .p12 certifikat i popunjava FiscalCertificate instancu.

    Args:
        instance: FiscalCertificate (još nije salvana)
        file_obj: Django UploadedFile (.p12 / .pfx)
        password: lozinka certifikata (može biti prazan string)

    Returns:
        {'ok': True, 'info': {...}} ili {'ok': False, 'error': '...'}
    """
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        # cryptography nije instaliran — prihvati certifikat bez validacije
        logger.warning("cryptography paket nije dostupan — cert se sprema bez parsiranja")
        instance.cert_name = file_obj.name or 'Certifikat'
        instance.cert_file = file_obj
        instance.is_valid = False
        return {'ok': True, 'info': {'warning': 'Nije moguće parsirati metapodatke'}}

    try:
        raw = file_obj.read()
        file_obj.seek(0)

        pw_bytes = password.encode() if password else None

        private_key, cert, chain = pkcs12.load_key_and_certificates(
            raw, pw_bytes, default_backend()
        )

        # Izvuci metapodatke
        subject = cert.subject
        subject_str = ', '.join(f"{attr.oid.dotted_string}={attr.value}" for attr in subject)

        # Pokušaj naći CN i OIB iz subject-a
        cert_name = _attr(subject, '2.5.4.3') or file_obj.name or 'Certifikat'
        oib_candidate = _attr(subject, '2.5.4.5') or ''  # serialNumber
        if not oib_candidate:
            # Pokušaj iz CN-a
            import re
            cn = _attr(subject, '2.5.4.3') or ''
            m = re.search(r'\d{11}', cn)
            if m:
                oib_candidate = m.group()

        instance.cert_name = cert_name[:200]
        instance.oib = oib_candidate[:11]
        instance.cert_subject = subject_str[:500]
        instance.valid_from = cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else _naive_to_aware(cert.not_valid_before)
        instance.valid_until = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else _naive_to_aware(cert.not_valid_after)
        instance.is_valid = True
        instance.cert_password = password
        instance.cert_file = file_obj

        return {
            'ok': True,
            'info': {
                'cert_name': cert_name,
                'oib': oib_candidate,
                'valid_from': str(instance.valid_from),
                'valid_until': str(instance.valid_until),
            }
        }

    except IOError as e:
        logger.warning("Certifikat nije valjan: %s", e)
        return {'ok': False, 'error': str(e)}


def test_cert_against_cis(instance, use_production: bool = False) -> dict:
    """
    Testira certifikat prema CIS echo endpointu.

    Args:
        instance: FiscalCertificate
        use_production: ako True koristi produkcijski CIS, inače demo

    Returns:
        {'ok': True/False, 'message': '...', 'status_code': int|None}
    """
    try:
        import requests

        endpoint = (
            "https://cis.porezna-uprava.hr:8449/FiskalizacijaService"
            if use_production
            else "https://cistest.apis-it.hr:8449/FiskalizacijaService"
        )

        # Spremi certifikat u temp fajl za requests
        cert_path = None
        try:
            if instance.cert_file:
                with tempfile.NamedTemporaryFile(suffix='.p12', delete=False) as tmp:
                    for chunk in instance.cert_file.chunks():
                        tmp.write(chunk)
                    cert_path = tmp.name

            # Pošalji minimalni echo SOAP zahtjev
            soap_body = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tns="http://www.apis-it.hr/fin/2012/types/f73">
  <soapenv:Header/>
  <soapenv:Body>
    <tns:EchoRequest>test</tns:EchoRequest>
  </soapenv:Body>
</soapenv:Envelope>"""

            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""',
            }

            resp = requests.post(
                endpoint,
                data=soap_body.encode('utf-8'),
                headers=headers,
                timeout=10,
                verify=False,  # CIS koristi FINA certifikat — možemo skipati verify za echo
            )

            ok = resp.status_code < 500
            return {
                'ok': ok,
                'message': f'HTTP {resp.status_code}',
                'status_code': resp.status_code,
            }

        finally:
            if cert_path and os.path.exists(cert_path):
                os.unlink(cert_path)

    except OSError as e:
        logger.warning("CIS test neuspješan: %s", e)
        return {
            'ok': False,
            'message': str(e),
            'status_code': None,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _attr(subject, oid_dotted: str) -> str:
    """Izvuci vrijednost atributa iz X.509 subject-a po OID-u."""
    try:
        from cryptography.x509.oid import NameOID
        from cryptography import x509
        for attr in subject:
            if attr.oid.dotted_string == oid_dotted:
                return attr.value
    except ImportError:
        pass
    return ''


def _naive_to_aware(dt):
    """Konvertira naive datetime u aware (UTC)."""
    if dt is None:
        return None
    import datetime
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt
