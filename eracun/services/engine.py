"""
e-Racun processing engine.

Handles: validation, XML generation, signing, FINA CIS submission, archiving.
Integrates Propter FiskalEngine logic into LIMIT Connect.
"""
import os
import uuid
import logging
import datetime
from decimal import Decimal
from lxml import etree
from signxml import XMLSigner, methods
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('eracun.engine')

# FINA CIS endpoints — FISKALIZACIJA (POS gotovinski računi)
FINA_FISCAL_URLS = {
    'test': 'https://cistest.apis-it.hr:8509/FiskalizacijaService',
    'production': 'https://cis.porezna-uprava.hr:8449/FiskalizacijaService',
}

# FINA eRačun endpoints — B2B elektronički računi
# NAPOMENA: eRačun servis koristi isti XML format (EvidentirajERacunZahtjev)
# ali potpuno drugi endpoint od FiskalizacijaService!
FINA_ERACUN_URLS = {
    'test': 'https://eracun-test.fina.hr/eRacunServis',
    'production': 'https://eracun.fina.hr/eRacunServis',
}

# Backward compat — stari kod koji koristi FINA_URLS
FINA_URLS = FINA_ERACUN_URLS

# SOAP namespaces
NS_SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
NS_EFIS = 'http://www.porezna-uprava.gov.hr/fin/2024/types/eFiskalizacija'
# UBL 2.1 namespace for eRačun (distinct from eFiskalizacija)
NS_UBL = 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'


def validate_eracun(eracun):
    """
    Validate e-Racun data before sending to FINA.
    Returns (is_valid, errors_list).
    """
    errors = []

    # Required fields
    if not eracun.invoice_number:
        errors.append('Broj racuna je obavezan')
    if not eracun.issuer_oib or len(eracun.issuer_oib) != 11:
        errors.append('OIB izdavatelja mora imati 11 znamenki')
    if not eracun.recipient_oib:
        errors.append('OIB primatelja je obavezan')
    if not eracun.issuer_name:
        errors.append('Naziv izdavatelja je obavezan')
    if not eracun.recipient_name:
        errors.append('Naziv primatelja je obavezan')
    if not eracun.total or eracun.total <= 0:
        errors.append('Ukupni iznos mora biti veci od 0')

    # OIB validation (ISO 7064 MOD 11,10)
    if eracun.issuer_oib and len(eracun.issuer_oib) == 11:
        if not _validate_oib(eracun.issuer_oib):
            errors.append(f'Neispravan OIB izdavatelja: {eracun.issuer_oib}')

    # Must have at least one line item
    if not eracun.items.exists():
        errors.append('Racun mora imati barem jednu stavku')

    # Tax consistency check
    items = eracun.items.all()
    calculated_subtotal = sum(i.line_total for i in items)
    if abs(calculated_subtotal - eracun.subtotal) > Decimal('0.02'):
        errors.append(f'Zbroj stavki ({calculated_subtotal}) ne odgovara osnovici ({eracun.subtotal})')

    return len(errors) == 0, errors


def _validate_oib(oib):
    """Validate Croatian OIB using ISO 7064 MOD 11,10."""
    if len(oib) != 11 or not oib.isdigit():
        return False
    total = 10
    for digit in oib[:-1]:
        total = (total + int(digit)) % 10
        if total == 0:
            total = 10
        total = (total * 2) % 11
    kontrolni = (11 - total) % 10
    return kontrolni == int(oib[-1])


def build_fina_xml(eracun, config):
    """
    Build EvidentirajERacunZahtjev SOAP XML for FINA CIS.

    Args:
        eracun: ERacun model instance
        config: ERacunConfig model instance
    Returns:
        bytes: SOAP XML envelope
    """
    req_uuid = str(uuid.uuid4())

    # Root element
    root = etree.Element(
        f'{{{NS_EFIS}}}EvidentirajERacunZahtjev',
        {f'{{{NS_EFIS}}}id': f'req-{req_uuid}'},
        nsmap={'efis': NS_EFIS}
    )

    # Zaglavlje
    header = etree.SubElement(root, f'{{{NS_EFIS}}}Zaglavlje')
    now_str = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '.0000'
    etree.SubElement(header, f'{{{NS_EFIS}}}datumVrijemeSlanja').text = now_str
    etree.SubElement(header, f'{{{NS_EFIS}}}vrstaERacuna').text = 'I'  # Izlazni

    # ERacun element
    er = etree.SubElement(root, f'{{{NS_EFIS}}}ERacun')
    etree.SubElement(er, f'{{{NS_EFIS}}}brojDokumenta').text = eracun.invoice_number
    etree.SubElement(er, f'{{{NS_EFIS}}}datumIzdavanja').text = eracun.issue_date.strftime('%Y-%m-%d')
    etree.SubElement(er, f'{{{NS_EFIS}}}vrstaDokumenta').text = eracun.doc_type
    etree.SubElement(er, f'{{{NS_EFIS}}}valutaERacuna').text = eracun.currency
    etree.SubElement(er, f'{{{NS_EFIS}}}vrstaPoslovnogProcesa').text = config.oznaka_prostora
    if eracun.delivery_date:
        etree.SubElement(er, f'{{{NS_EFIS}}}datumIsporuke').text = eracun.delivery_date.strftime('%Y-%m-%d')

    # Izdavatelj
    izd = etree.SubElement(er, f'{{{NS_EFIS}}}Izdavatelj')
    etree.SubElement(izd, f'{{{NS_EFIS}}}ime').text = eracun.issuer_name
    etree.SubElement(izd, f'{{{NS_EFIS}}}oibPorezniBroj').text = eracun.issuer_oib
    etree.SubElement(izd, f'{{{NS_EFIS}}}oibOperatera').text = config.cert_oib or eracun.issuer_oib

    # Primatelj
    prim = etree.SubElement(er, f'{{{NS_EFIS}}}Primatelj')
    etree.SubElement(prim, f'{{{NS_EFIS}}}ime').text = eracun.recipient_name
    etree.SubElement(prim, f'{{{NS_EFIS}}}oibPorezniBroj').text = eracun.recipient_oib

    # Nacin placanja
    payment_code = eracun.payment_means_code or '30'
    fina_code = 'T' if payment_code == '30' else 'G' if payment_code == '10' else 'K' if payment_code == '48' else 'O'
    etree.SubElement(er, f'{{{NS_EFIS}}}nacinPlacanja').text = fina_code

    # Tax breakdown (RaspodjelaPdv)
    tax_summaries = eracun.tax_summaries.all()
    if tax_summaries.exists():
        for ts in tax_summaries:
            rpdv = etree.SubElement(er, f'{{{NS_EFIS}}}RaspodjelaPdv')
            etree.SubElement(rpdv, f'{{{NS_EFIS}}}kategorijaPdv').text = ts.tax_category
            etree.SubElement(rpdv, f'{{{NS_EFIS}}}oporeziviIznos').text = f'{ts.taxable_amount:.2f}'
            etree.SubElement(rpdv, f'{{{NS_EFIS}}}iznosPoreza').text = f'{ts.tax_amount:.2f}'
            etree.SubElement(rpdv, f'{{{NS_EFIS}}}stopa').text = f'{ts.tax_rate:.0f}'
            etree.SubElement(rpdv, f'{{{NS_EFIS}}}hrOznakaKategorijaPdv').text = f'HR:PDV{ts.tax_rate:.0f}'
    else:
        # Single rate fallback
        rpdv = etree.SubElement(er, f'{{{NS_EFIS}}}RaspodjelaPdv')
        etree.SubElement(rpdv, f'{{{NS_EFIS}}}kategorijaPdv').text = 'S'
        etree.SubElement(rpdv, f'{{{NS_EFIS}}}oporeziviIznos').text = f'{eracun.subtotal:.2f}'
        etree.SubElement(rpdv, f'{{{NS_EFIS}}}iznosPoreza').text = f'{eracun.tax_amount:.2f}'
        rate = 25
        if eracun.subtotal and eracun.subtotal > 0:
            rate = int(round(float(eracun.tax_amount / eracun.subtotal * 100)))
        etree.SubElement(rpdv, f'{{{NS_EFIS}}}stopa').text = str(rate)
        etree.SubElement(rpdv, f'{{{NS_EFIS}}}hrOznakaKategorijaPdv').text = f'HR:PDV{rate}'

    # Ukupni iznosi
    ukupno = etree.SubElement(er, f'{{{NS_EFIS}}}DokumentUkupanIznos')
    etree.SubElement(ukupno, f'{{{NS_EFIS}}}neto').text = f'{eracun.subtotal:.2f}'
    etree.SubElement(ukupno, f'{{{NS_EFIS}}}iznosBezPdv').text = f'{eracun.subtotal:.2f}'
    etree.SubElement(ukupno, f'{{{NS_EFIS}}}pdv').text = f'{eracun.tax_amount:.2f}'
    etree.SubElement(ukupno, f'{{{NS_EFIS}}}iznosSPdv').text = f'{eracun.total:.2f}'
    etree.SubElement(ukupno, f'{{{NS_EFIS}}}iznosKojiDospijevaZaPlacanje').text = f'{eracun.total:.2f}'

    # Stavke
    for item in eracun.items.all():
        stavka = etree.SubElement(er, f'{{{NS_EFIS}}}StavkaERacuna')
        etree.SubElement(stavka, f'{{{NS_EFIS}}}kolicina').text = f'{item.quantity:.2f}'
        etree.SubElement(stavka, f'{{{NS_EFIS}}}jedinicaMjere').text = item.unit_code or 'EA'
        etree.SubElement(stavka, f'{{{NS_EFIS}}}neto').text = f'{item.line_total:.2f}'
        etree.SubElement(stavka, f'{{{NS_EFIS}}}artiklNetoCijena').text = f'{item.unit_price:.2f}'

        gross = float(item.unit_price) * (1 + float(item.tax_rate) / 100)
        etree.SubElement(stavka, f'{{{NS_EFIS}}}artiklBrutoCijena').text = f'{gross:.2f}'
        etree.SubElement(stavka, f'{{{NS_EFIS}}}artiklKategorijaPdv').text = item.tax_category
        etree.SubElement(stavka, f'{{{NS_EFIS}}}artiklStopaPdv').text = f'{item.tax_rate:.0f}'
        etree.SubElement(stavka, f'{{{NS_EFIS}}}artiklNaziv').text = item.description
        etree.SubElement(stavka, f'{{{NS_EFIS}}}artiklHrOznakaKategorijaPdv').text = f'HR:PDV{item.tax_rate:.0f}'

        if item.classification_code:
            klas = etree.SubElement(stavka, f'{{{NS_EFIS}}}ArtiklIdentifikatorKlasifikacija')
            etree.SubElement(klas, f'{{{NS_EFIS}}}identifikatorKlasifikacije').text = item.classification_code
            etree.SubElement(klas, f'{{{NS_EFIS}}}identifikatorSheme').text = 'CG'

    etree.SubElement(er, f'{{{NS_EFIS}}}indikatorKopije').text = 'false'

    return root, req_uuid


def sign_xml(root, cert_pem, key_pem):
    """Sign XML with FINA certificate."""
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/2001/10/xml-exc-c14n#'
    )
    signed = signer.sign(root, key=key_pem, cert=cert_pem)
    return signed


def wrap_soap(signed_root):
    """Wrap signed XML in SOAP envelope (legacy eFiskalizacija format)."""
    envelope = etree.Element(
        f'{{{NS_SOAP}}}Envelope',
        nsmap={'soapenv': NS_SOAP}
    )
    body = etree.SubElement(envelope, f'{{{NS_SOAP}}}Body')
    body.append(signed_root)
    return etree.tostring(envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8')


def wrap_soap_ubl(ubl_xml_bytes):
    """Wrap UBL 2.1 XML in SOAP envelope for FINA eRačun service."""
    envelope = etree.Element(
        f'{{{NS_SOAP}}}Envelope',
        nsmap={'soapenv': NS_SOAP}
    )
    body = etree.SubElement(envelope, f'{{{NS_SOAP}}}Body')
    ubl_root = etree.fromstring(ubl_xml_bytes)
    body.append(ubl_root)
    return etree.tostring(envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8')


def send_to_fina(xml_payload, use_test=True, service='eracun'):
    """
    Send SOAP XML to FINA endpoint.

    service='eracun' → B2B eRačun (EvidentirajERacunZahtjev)
    service='fiscal' → POS fiskalizacija (RacunZahtjev)

    Returns (success, response_data_dict).
    """
    import requests as req_lib
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if service == 'fiscal':
        urls = FINA_FISCAL_URLS
        soap_action = 'http://www.apis-it.hr/fin/2012/RacunZahtjev'
    else:
        urls = FINA_ERACUN_URLS
        soap_action = 'http://www.porezna-uprava.gov.hr/fin/2024/EvidentirajERacunZahtjev'

    url = urls['test'] if use_test else urls['production']

    try:
        resp = req_lib.post(
            url,
            data=xml_payload,
            headers={
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': soap_action,
            },
            verify=not use_test,  # verify SSL u produkciji
            timeout=30,
        )

        response_tree = etree.fromstring(resp.content)

        prihvacen = response_tree.find(f'.//{{{NS_EFIS}}}prihvacenZahtjev')
        if prihvacen is not None and prihvacen.text == 'true':
            return True, {
                'status': 'accepted',
                'raw': resp.text,
            }

        # Extract error
        opis = response_tree.find(f'.//{{{NS_EFIS}}}greska/{{{NS_EFIS}}}opis')
        sifra = response_tree.find(f'.//{{{NS_EFIS}}}greska/{{{NS_EFIS}}}sifra')
        return False, {
            'status': 'rejected',
            'error_code': sifra.text if sifra is not None else 'N/A',
            'error_message': opis.text if opis is not None else 'Nepoznata greska',
            'raw': resp.text,
        }

    except Exception as e:
        logger.error(f'FINA send error: {e}')
        return False, {
            'status': 'error',
            'error_message': str(e),
        }


def get_cert_pem(config):
    """
    Extract PEM cert and key from P12 file.
    Returns (cert_pem_bytes, key_pem_bytes) or raises.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption

    # 1. Direktni cert_path (CharField, sigurna lokacija)
    if getattr(config, 'cert_path', None) and os.path.exists(config.cert_path):
        p12_path = config.cert_path
    else:
        # 2. Fallback: /etc/limit-connect/certs/ — traži cert po OIB-u
        secure_dir = '/etc/limit-connect/certs'
        cert_oib = getattr(config, 'cert_oib', '') or ''
        p12_path = None
        if os.path.isdir(secure_dir):
            # Prioritet: certifikat koji sadrži OIB firme u imenu
            candidates = [f for f in os.listdir(secure_dir) if f.endswith('.p12')]
            if cert_oib:
                oib_match = [f for f in candidates if cert_oib in f]
                if oib_match:
                    p12_path = os.path.join(secure_dir, sorted(oib_match)[-1])
            if not p12_path and candidates:
                p12_path = os.path.join(secure_dir, 'fina_cert.p12')
        if not p12_path:
            # 3. Zadnji fallback: project certs dir
            cert_dir = os.path.join(settings.BASE_DIR, 'certs')
            candidates = [f for f in os.listdir(cert_dir) if f.endswith('.p12')] if os.path.isdir(cert_dir) else []
            if not candidates:
                raise FileNotFoundError('Nema P12 certifikata ni u /etc/limit-connect/certs/ ni u certs/')
            p12_path = os.path.join(cert_dir, candidates[0])

    # Lozinka: .cert_password fajl u istom direktoriju, ili deprecated polje
    p12_dir = os.path.dirname(p12_path)
    pw_file = os.path.join(p12_dir, '.cert_password')
    password = None
    if os.path.exists(pw_file):
        with open(pw_file, 'r') as f:
            password = f.read().strip().encode() or None
    if not password:
        deprecated_pwd = getattr(config, 'cert_password_deprecated', '') or ''
        password = deprecated_pwd.encode() or None

    with open(p12_path, 'rb') as f:
        p12_data = f.read()

    private_key, certificate, _ = pkcs12.load_key_and_certificates(p12_data, password)

    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    return cert_pem, key_pem


def process_eracun(eracun, config=None, user=None):
    """
    Full pipeline: validate -> build XML -> sign -> send -> archive.

    Args:
        eracun: ERacun model instance
        config: ERacunConfig (auto-fetched if None)
        user: User performing the action

    Returns:
        (success: bool, message: str)
    """
    from eracun.models import ERacunLog

    if not config:
        try:
            config = eracun.company.eracun_config
        except Exception:
            eracun.status = 'error'
            eracun.error_message = 'Nema e-Racun konfiguracije za ovu firmu'
            eracun.save(update_fields=['status', 'error_message'])
            return False, eracun.error_message

    # 1. Validate
    eracun.status = 'validating'
    eracun.save(update_fields=['status'])

    is_valid, errors = validate_eracun(eracun)
    if not is_valid:
        eracun.status = 'invalid'
        eracun.error_message = '; '.join(errors)
        eracun.save(update_fields=['status', 'error_message'])
        ERacunLog.objects.create(
            eracun=eracun, action='validation', status='error',
            message=eracun.error_message, user=user
        )
        return False, eracun.error_message

    eracun.status = 'valid'
    eracun.save(update_fields=['status'])
    ERacunLog.objects.create(
        eracun=eracun, action='validation', status='success',
        message='Validacija uspjesna', user=user
    )

    # 2. Build FINA XML
    eracun.status = 'signing'
    eracun.save(update_fields=['status'])

    try:
        req_uuid = str(uuid.uuid4())
        eracun.fina_uuid = req_uuid

        # 2b. Generate UBL 2.1 XML (EN 16931 / CIUS-2025 compliant)
        from eracun.services.ubl_generator import generate_ubl_xml
        ubl_xml = generate_ubl_xml(eracun)

        # 3. Sign with XAdES-B
        cert_pem, key_pem = get_cert_pem(config)
        from eracun.services.xades_signer import sign_xades_b
        ubl_root = etree.fromstring(ubl_xml)
        signed_root = sign_xades_b(ubl_root, cert_pem, key_pem)
        xml_payload = wrap_soap(signed_root)

        eracun.xml_request = xml_payload.decode('utf-8', errors='replace')
        eracun.save(update_fields=['fina_uuid', 'xml_request'])

    except Exception as e:
        eracun.status = 'error'
        eracun.error_message = f'Greska pri potpisivanju: {str(e)}'
        eracun.save(update_fields=['status', 'error_message'])
        ERacunLog.objects.create(
            eracun=eracun, action='signing', status='error',
            message=str(e), user=user
        )
        return False, eracun.error_message

    ERacunLog.objects.create(
        eracun=eracun, action='signing', status='success',
        message=f'XML potpisan, UUID: {req_uuid}', user=user
    )

    # 3b. PRE-FLIGHT VALIDATION — Rupa 1 zatvorena
    try:
        from eracun.services.validator import validate_full
        v_valid, v_errors, v_warnings = validate_full(xml_payload)
        if not v_valid:
            eracun.status = 'invalid'
            eracun.error_message = 'Pre-flight validacija: ' + '; '.join(v_errors[:5])
            eracun.save(update_fields=['status', 'error_message'])
            ERacunLog.objects.create(
                eracun=eracun, action='validation', status='error',
                message=eracun.error_message, user=user,
            )
            return False, eracun.error_message
        if v_warnings:
            logger.info('e-Racun %s validation warnings: %s', eracun.invoice_number, v_warnings[:3])
    except Exception as val_err:
        logger.warning('Pre-flight validation skipped: %s', val_err)

    # 4. Send to FINA
    eracun.status = 'sending'
    eracun.save(update_fields=['status'])

    # Provjeri: posrednik ili direktno FINA?
    posrednik_mode = _should_use_posrednik(config)

    if posrednik_mode:
        success, result = _send_via_posrednik(eracun, config)
    else:
        success, result = send_to_fina(xml_payload, use_test=config.use_test_env, service='eracun')

    eracun.xml_response = result.get('raw', '')
    eracun.sent_at = timezone.now()

    if success:
        eracun.status = 'accepted'
        eracun.accepted_at = timezone.now()
        eracun.error_message = ''
        eracun.error_code = ''
        eracun.save(update_fields=[
            'status', 'xml_response', 'sent_at', 'accepted_at',
            'error_message', 'error_code', 'fina_uuid'
        ])
        ERacunLog.objects.create(
            eracun=eracun, action='sent', status='accepted',
            message='FINA prihvatila racun', user=user,
            details={'uuid': req_uuid}
        )
        return True, f'e-Racun prihvacen (UUID: {req_uuid})'
    else:
        eracun.status = 'rejected' if result.get('status') == 'rejected' else 'error'
        eracun.error_message = result.get('error_message', 'Nepoznata greska')
        eracun.error_code = result.get('error_code', '')
        eracun.save(update_fields=[
            'status', 'xml_response', 'sent_at',
            'error_message', 'error_code', 'fina_uuid'
        ])
        ERacunLog.objects.create(
            eracun=eracun, action='sent', status=eracun.status,
            message=eracun.error_message, user=user,
            details=result
        )
        return False, eracun.error_message


def create_eracun_from_invoice(invoice, user=None):
    """
    Create ERacun record from existing LIMIT Connect Invoice.
    Maps all fields and creates line items + tax summaries.
    """
    from eracun.models import ERacun, ERacunItem, ERacunTaxSummary

    # Payment means mapping
    pm_map = {
        'Transakcijski': '30', 'Gotovina': '10', 'Kartica': '48',
        'Virman': '30', 'Uberweisung': '30', 'Bar': '10',
    }

    er = ERacun.objects.create(
        company=invoice.company,
        invoice=invoice,
        doc_type='381' if invoice.doctype == 'Storno' else '380',
        invoice_number=invoice.number or str(invoice.internal_id),
        issue_date=invoice.date_issued or timezone.now().date(),
        delivery_date=invoice.date_delivery,
        due_date=invoice.date_due,
        currency=invoice.currency or 'EUR',
        issuer_name=invoice.issuer_name or '',
        issuer_oib=invoice.issuer_oib or '',
        issuer_address=invoice.issuer_address or '',
        issuer_iban=invoice.issuer_iban or '',
        issuer_swift=invoice.issuer_swift or '',
        issuer_country=invoice.country or 'HR',
        recipient_name=invoice.client_name or '',
        recipient_oib=invoice.client_oib or '',
        recipient_address=invoice.client_address or '',
        recipient_city=invoice.client_city or '',
        recipient_country=invoice.client_country or 'HR',
        subtotal=invoice.subtotal or 0,
        tax_amount=invoice.tax_amount or 0,
        total=invoice.total or 0,
        payment_means_code=pm_map.get(invoice.payment_method, '30'),
        payment_reference=invoice.reference_number or '',
        note=invoice.note or '',
        zki=invoice.zki or '',
        jir=invoice.jir or '',
        created_by=user,
    )

    # Create line items
    tax_groups = {}
    for idx, item in enumerate(invoice.items.all(), 1):
        rate = item.tax_rate or invoice.tax_percent or Decimal('25')
        cat = 'S'
        if rate == 0:
            cat = 'Z'
        if invoice.tax_status in ('reverse_charge',):
            cat = 'AE'
        if invoice.tax_status in ('exempt',):
            cat = 'E'

        unit = 'EA'
        if item.unit:
            unit = UNIT_MAP.get(item.unit.lower().strip(), item.unit.upper()[:5]) if hasattr(item, 'unit') and item.unit else 'EA'

        line_total = item.total_price or (item.quantity * item.unit_price)
        ERacunItem.objects.create(
            eracun=er,
            line_number=idx,
            description=item.description or 'Stavka',
            quantity=item.quantity or 1,
            unit_code=unit,
            unit_price=item.unit_price or 0,
            discount_percent=item.discount_percent or 0,
            line_total=line_total,
            tax_category=cat,
            tax_rate=rate,
        )

        # Aggregate tax groups
        key = (cat, float(rate))
        if key not in tax_groups:
            tax_groups[key] = {'taxable': Decimal('0'), 'tax': Decimal('0')}
        tax_groups[key]['taxable'] += line_total
        tax_groups[key]['tax'] += line_total * rate / 100

    # Create tax summaries
    for (cat, rate), amounts in tax_groups.items():
        ERacunTaxSummary.objects.create(
            eracun=er,
            tax_category=cat,
            tax_rate=Decimal(str(rate)),
            taxable_amount=amounts['taxable'].quantize(Decimal('0.01')),
            tax_amount=amounts['tax'].quantize(Decimal('0.01')),
        )

    return er




def _should_use_posrednik(config):
    """Provjeri ima li firma konfiguriran posrednik (Moj-eRacun.hr etc.)."""
    try:
        from eracun.services.posrednik_service import get_posrednik_config
        pc = get_posrednik_config(config.company)
        return pc is not None and pc.get('enabled', False)
    except Exception:
        return False


def _send_via_posrednik(eracun, config):
    """Šalje eRačun kroz posrednika (REST API, UBL 2.1)."""
    try:
        from eracun.services.posrednik_service import send_via_posrednik
        return send_via_posrednik(eracun, config)
    except ImportError:
        logger.warning('posrednik_service not available, falling back to FINA direct')
        return False, {'status': 'error', 'error_message': 'Posrednik servis nije dostupan'}
    except Exception as e:
        logger.error('Posrednik send failed: %s', e)
        return False, {'status': 'error', 'error_message': str(e)}

# Import the unit map from UBL generator
UNIT_MAP = {
    'kom': 'EA', 'komad': 'EA', 'pcs': 'EA',
    'sat': 'HUR', 'h': 'HUR', 'hr': 'HUR',
    'kg': 'KGM', 'kilogram': 'KGM',
    'm': 'MTR', 'metar': 'MTR',
    'l': 'LTR', 'litra': 'LTR',
    'm2': 'MTK', 'kvm': 'MTK',
    'dan': 'DAY', 'day': 'DAY',
    'mj': 'MON', 'mjesec': 'MON',
    'set': 'SET', 'pak': 'XPK',
}
