"""
Croatian Fiscalization (Fiskalizacija) – core engine.

ZKI  = MD5( RSA_SHA1_sign( OIB|DatVrijeme|BrOznRac|OznPosPr|OznNapUr|IznosUkupno ) )
SOAP = signed XML-DSig envelope → FINA CIS → returns JIR (UUID)

References:
  FINA technical specification v1.7 (Fiskalizacija 2.0)
  https://www.porezna-uprava.hr/HR_Fiskalizacija/Documents/Fiskalizacija%20-%20Tehnicka%20specifikacija%20za%20korisnike_v1.7.pdf
"""
import hashlib
import logging
import os
import tempfile
import uuid
from base64 import b64encode
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from lxml import etree

logger = logging.getLogger(__name__)

# ── Namespaces ────────────────────────────────────────────────────────────────
SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
WSSE_NS = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
WSU_NS  = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
DS_NS   = 'http://www.w3.org/2000/09/xmldsig#'
FISK_NS = 'http://www.apis-it.hr/fin/2012/types/f73'

DEMO_URL = 'https://cistest.apis-it.hr:8449/FiskalizacijaService'
PROD_URL = 'https://cis.porezna-uprava.hr:8449/FiskalizacijaService'
ZAGREB   = ZoneInfo('Europe/Zagreb')

NACIN_PLAC = {
    'CASH':    'G',   # gotovina
    'CARD':    'K',   # kartica
    'MOBILE':  'K',   # mobilno → kartica
    'VOUCHER': 'O',   # ostalo
    'ACCOUNT': 'T',   # transakcijski račun
}


# ── Certificate helpers ───────────────────────────────────────────────────────
def load_p12(cert_path: str, password: str):
    """
    Load a PKCS#12 (.p12) certificate.
    Returns: (private_key, cert_der_bytes, cert_pem_bytes, key_pem_bytes)
    """
    with open(cert_path, 'rb') as fh:
        p12_data = fh.read()
    pwd_bytes = password.encode() if password else None
    key, cert, chain = load_key_and_certificates(p12_data, pwd_bytes)
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem  = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return key, cert_der, cert_pem, key_pem


# ── ZKI computation ───────────────────────────────────────────────────────────
def generate_zki(
    oib: str,
    dt: datetime,
    br_ozn_rac: int,
    ozn_pos_pr: str,
    ozn_nap_ur: str,
    iznos_ukupno: Decimal,
    private_key,
) -> str:
    """
    Zaštitni Kod Izdavatelja (ZKI) per FINA spec:
      input  = OIB|dd.MM.yyyyTHH:mm:ss|BrOznRac|OznPosPr|OznNapUr|iznos.dd
      ZKI    = MD5( RSA_PKCS1v15_SHA1_sign(input) )  → 32-char lowercase hex
    """
    dt_str    = dt.strftime('%d.%m.%YT%H:%M:%S')
    iznos_str = f'{iznos_ukupno:.2f}'
    input_str = f'{oib}|{dt_str}|{br_ozn_rac}|{ozn_pos_pr}|{ozn_nap_ur}|{iznos_str}'
    sig = private_key.sign(input_str.encode('utf-8'),
                           asym_padding.PKCS1v15(), hashes.SHA1())
    return hashlib.md5(sig).hexdigest()


# ── XML helpers ───────────────────────────────────────────────────────────────
def _T(ns, local):
    return f'{{{ns}}}{local}'


def _exc_c14n(element) -> bytes:
    """Exclusive canonicalization of a single element."""
    tmp = deepcopy(element)
    out = BytesIO()
    etree.ElementTree(tmp).write_c14n(out, exclusive=True, with_comments=False)
    return out.getvalue()


# ── Build SOAP envelope with XMLDSig ─────────────────────────────────────────
def build_signed_soap(
    receipt,
    oib: str,
    ozn_pos_pr: str,
    ozn_nap_ur: str,
    zki: str,
    dt: datetime,
    private_key,
    cert_der: bytes,
) -> bytes:
    """
    Build a complete WS-Security signed SOAP envelope for RacunZahtjev.
    Signature covers the tns:Racun element (XML-DSig, RSA-SHA256).
    """
    msg_id = str(uuid.uuid4())

    nsmap_root = {
        'soapenv': SOAP_NS,
        'tns':     FISK_NS,
        'wsse':    WSSE_NS,
        'wsu':     WSU_NS,
        'ds':      DS_NS,
    }

    # ── Envelope ──────────────────────────────────────────────────────────────
    env  = etree.Element(_T(SOAP_NS, 'Envelope'), nsmap=nsmap_root)
    hdr  = etree.SubElement(env, _T(SOAP_NS, 'Header'))
    body = etree.SubElement(env, _T(SOAP_NS, 'Body'))

    # ── WS-Security header ────────────────────────────────────────────────────
    wsse = etree.SubElement(hdr, _T(WSSE_NS, 'Security'))
    wsse.set(_T(SOAP_NS, 'mustUnderstand'), '1')

    bst_id = 'X509Token'
    bst = etree.SubElement(wsse, _T(WSSE_NS, 'BinarySecurityToken'))
    bst.set(_T(WSU_NS, 'Id'), bst_id)
    bst.set('ValueType',
            'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3')
    bst.set('EncodingType',
            'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary')
    bst.text = b64encode(cert_der).decode()

    # ── SOAP Body: RacunZahtjev ────────────────────────────────────────────────
    zahtjev  = etree.SubElement(body, _T(FISK_NS, 'RacunZahtjev'))
    zaglavlje = etree.SubElement(zahtjev, _T(FISK_NS, 'Zaglavlje'))
    etree.SubElement(zaglavlje, _T(FISK_NS, 'IdPoruke')).text      = msg_id
    etree.SubElement(zaglavlje, _T(FISK_NS, 'DatumVrijeme')).text  = dt.strftime('%d.%m.%YT%H:%M:%S')

    # Build Racun element
    racun = _build_racun(receipt, oib, ozn_pos_pr, ozn_nap_ur, zki, dt)
    zahtjev.append(racun)

    # ── Step 1: digest Racun ──────────────────────────────────────────────────
    racun_c14n   = _exc_c14n(racun)
    digest_b64   = b64encode(hashlib.sha256(racun_c14n).digest()).decode()

    # ── Step 2: build SignedInfo ──────────────────────────────────────────────
    sig_el       = etree.SubElement(wsse, _T(DS_NS, 'Signature'))
    signed_info  = etree.SubElement(sig_el, _T(DS_NS, 'SignedInfo'))

    c14n_meth = etree.SubElement(signed_info, _T(DS_NS, 'CanonicalizationMethod'))
    c14n_meth.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')

    sig_meth  = etree.SubElement(signed_info, _T(DS_NS, 'SignatureMethod'))
    sig_meth.set('Algorithm', 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256')

    ref = etree.SubElement(signed_info, _T(DS_NS, 'Reference'))
    ref.set('URI', '#Racun')
    trs = etree.SubElement(ref, _T(DS_NS, 'Transforms'))
    tr  = etree.SubElement(trs, _T(DS_NS, 'Transform'))
    tr.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')
    dm  = etree.SubElement(ref, _T(DS_NS, 'DigestMethod'))
    dm.set('Algorithm', 'http://www.w3.org/2001/04/xmlenc#sha256')
    etree.SubElement(ref, _T(DS_NS, 'DigestValue')).text = digest_b64

    # ── Step 3: sign SignedInfo ───────────────────────────────────────────────
    si_c14n = _exc_c14n(signed_info)
    sig_raw = private_key.sign(si_c14n, asym_padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = b64encode(sig_raw).decode()

    sig_val = etree.SubElement(sig_el, _T(DS_NS, 'SignatureValue'))
    sig_val.text = sig_b64

    # ── KeyInfo ───────────────────────────────────────────────────────────────
    ki  = etree.SubElement(sig_el, _T(DS_NS, 'KeyInfo'))
    str_el = etree.SubElement(ki, _T(WSSE_NS, 'SecurityTokenReference'))
    ref_el = etree.SubElement(str_el, _T(WSSE_NS, 'Reference'))
    ref_el.set('URI', f'#{bst_id}')
    ref_el.set('ValueType',
               'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3')

    return etree.tostring(env, xml_declaration=True, encoding='UTF-8')


def _build_racun(receipt, oib, ozn_pos_pr, ozn_nap_ur, zki, dt) -> etree._Element:
    """Build tns:Racun XML element from POSReceipt."""
    ns = FISK_NS
    nsmap = {'tns': FISK_NS, 'wsu': WSU_NS}
    racun = etree.Element(_T(ns, 'Racun'), nsmap=nsmap)
    racun.set(_T(WSU_NS, 'Id'), 'Racun')

    def sub(parent, name, text=None):
        el = etree.SubElement(parent, _T(ns, name))
        if text is not None:
            el.text = str(text)
        return el

    # Company in VAT system?
    try:
        u_pdv = 'true' if receipt.session.terminal.company.is_vat_registered else 'false'
    except Exception:
        u_pdv = 'true'

    sub(racun, 'Oib', oib)
    sub(racun, 'USustPdv', u_pdv)
    sub(racun, 'DatVrijeme', dt.strftime('%d.%m.%YT%H:%M:%S'))
    sub(racun, 'OznSlijed', 'P')   # P = Prodaja

    br_rac_el = sub(racun, 'BrRac')
    sub(br_rac_el, 'BrOznRac', receipt.receipt_number)
    sub(br_rac_el, 'OznPosPr', ozn_pos_pr)
    sub(br_rac_el, 'OznNapUr', ozn_nap_ur)

    # PDV breakdown grouped by rate
    from collections import defaultdict
    tax_groups = defaultdict(lambda: {'osnovica': Decimal('0'), 'iznos': Decimal('0')})
    for item in receipt.items.all():
        rate = item.tax_rate
        net  = item.quantity * item.unit_price * (1 - item.discount_percent / 100)
        tax  = net * rate / 100
        tax_groups[f'{rate:.2f}']['osnovica'] += net
        tax_groups[f'{rate:.2f}']['iznos']    += tax

    if tax_groups:
        pdv_el = sub(racun, 'Pdv')
        for stopa, vals in tax_groups.items():
            p = sub(pdv_el, 'Porez')
            sub(p, 'Stopa',    stopa)
            sub(p, 'Osnovica', f'{vals["osnovica"]:.2f}')
            sub(p, 'Iznos',    f'{vals["iznos"]:.2f}')

    sub(racun, 'IznosUkupno', f'{receipt.total:.2f}')

    # Payment method
    nacin = 'G'
    pay   = receipt.payment_lines.first()
    if pay:
        nacin = NACIN_PLAC.get(pay.method, 'O')
    sub(racun, 'NacinPlac', nacin)

    # HR Napojnica (od 01.01.2024 — NN 156/2023)
    tip_items = [i for i in receipt.items.all() if i.is_tip and not i.is_tip_employer]
    if tip_items:
        from decimal import Decimal
        tip_total = sum(i.unit_price * i.quantity for i in tip_items)
        if tip_total > 0:
            nap_el = sub(racun, 'Napojnica')
            sub(nap_el, 'IznosN', f'{tip_total:.2f}')
            # Nacin placanja napojnice: K=Kartica, G=Gotovina
            tip_pay = 'G'
            if pay and pay.method in ('CARD', 'REVOLUT', 'MOBILE'):
                tip_pay = 'K'
            sub(nap_el, 'NacinPlacanjaN', tip_pay)

    sub(racun, 'OibOper', oib)    # Operator OIB (ideally individual's OIB)
    sub(racun, 'ZastKod', zki)
    sub(racun, 'NakDost', 'false')

    return racun


# ── HTTP send ─────────────────────────────────────────────────────────────────
def _send_to_fina(soap_xml: bytes, url: str, cert_pem: bytes, key_pem: bytes) -> str:
    """POST signed SOAP to FINA CIS. Returns JIR string."""
    headers = {'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': ''}

    # Write temp PEM files for requests mutual-TLS
    with tempfile.NamedTemporaryFile(suffix='.pem', delete=False) as fc:
        fc.write(cert_pem);  cert_tmp = fc.name
    with tempfile.NamedTemporaryFile(suffix='.key', delete=False) as fk:
        fk.write(key_pem);   key_tmp  = fk.name
    try:
        # Demo (cistest) = self-signed cert, verify=False
        # Prod (cis.porezna-uprava.hr) = DigiCert CA, verify system bundle
        _verify = False if 'cistest' in url else True
        resp = requests.post(
            url, data=soap_xml, headers=headers,
            cert=(cert_tmp, key_tmp),
            verify=_verify,
            timeout=(1.5, 2),
        )
        # Ne raise na 500 – FINA vraca SOAP error body u HTTP 500 responsu
    finally:
        os.unlink(cert_tmp)
        os.unlink(key_tmp)

    root = etree.fromstring(resp.content)

    # Happy path: JIR returned
    jir_el = root.find(f'.//{{{FISK_NS}}}Jir')
    if jir_el is not None and jir_el.text:
        return jir_el.text.strip()

    # Error path
    graska = root.find(f'.//{{{FISK_NS}}}Greske')
    if graska is not None:
        errs = []
        for g in graska:
            kod = g.find(f'{{{FISK_NS}}}SifraGreske')
            msg = g.find(f'{{{FISK_NS}}}PorukaGreske')
            errs.append(f'{getattr(kod,"text","?")} – {getattr(msg,"text","?")}')
        raise RuntimeError(f'FINA greška: {"; ".join(errs)}')

    raise RuntimeError(f'Neočekivani FINA odgovor: {resp.text[:300]}')


# ── Ping (EchoZahtjev) ────────────────────────────────────────────────────────
def ping_fina(cert_path: str, password: str, demo: bool = True) -> bool:
    """Send EchoZahtjev. Returns True if CIS responds 200."""
    url = DEMO_URL if demo else PROD_URL
    try:
        key, cert_der, cert_pem, key_pem = load_p12(cert_path, password)
        dt  = datetime.now(ZAGREB)
        envelope = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:tns="http://www.apis-it.hr/fin/2012/types/f73">'
            '<soapenv:Header/><soapenv:Body>'
            f'<tns:PingZahtjev><tns:Zaglavlje>'
            f'<tns:IdPoruke>{uuid.uuid4()}</tns:IdPoruke>'
            f'<tns:DatumVrijeme>{dt.strftime("%d.%m.%YT%H:%M:%S")}</tns:DatumVrijeme>'
            '</tns:Zaglavlje></tns:PingZahtjev>'
            '</soapenv:Body></soapenv:Envelope>'
        ).encode('utf-8')

        with tempfile.NamedTemporaryFile(suffix='.pem', delete=False) as fc:
            fc.write(cert_pem);  ct = fc.name
        with tempfile.NamedTemporaryFile(suffix='.key', delete=False) as fk:
            fk.write(key_pem);   kt = fk.name
        try:
            _v = False if 'cistest' in url else True
            r = requests.post(url, data=envelope,
                              headers={'Content-Type': 'text/xml; charset=UTF-8'},
                              cert=(ct, kt), verify=_v, timeout=(1.5, 2))
            return r.status_code in (200, 500) and b"Envelope" in r.content
        finally:
            os.unlink(ct); os.unlink(kt)
    except Exception as exc:
        logger.warning(f'FINA ping greška: {exc}')
        return False


# ── Main entry point (called from pos/views.py) ───────────────────────────────
def fiscalize_receipt(receipt) -> str | None:
    """
    Fiscalize a paid POS receipt.
    Returns JIR on success, None if not configured, raises on FINA error.
    """
    try:
        company = receipt.session.terminal.company
        config  = company.fiscal_config
    except Exception:
        return None

    if not config.is_active or not config.cert_filename:
        return None

    cert_path = config.cert_path
    password  = config.get_password()

    key, cert_der, cert_pem, key_pem = load_p12(cert_path, password)
    oib = company.oib

    # Convert paid_at to Zagreb local time for FINA
    from django.utils import timezone as dj_tz
    paid_at = receipt.paid_at or dj_tz.now()
    if dj_tz.is_aware(paid_at):
        dt = paid_at.astimezone(ZAGREB).replace(tzinfo=None)
    else:
        dt = paid_at

    ozn_pos = config.ozn_pos_pr
    ozn_ur  = config.ozn_nap_ur or receipt.session.terminal.terminal_code[:20]

    zki = generate_zki(oib, dt, receipt.receipt_number, ozn_pos, ozn_ur,
                       receipt.total, key)

    soap_xml = build_signed_soap(receipt, oib, ozn_pos, ozn_ur, zki, dt,
                                 key, cert_der)

    url = DEMO_URL if config.is_demo else PROD_URL
    try:
        jir = _send_to_fina(soap_xml, url, cert_pem, key_pem)
    except (RuntimeError, Exception) as _fisk_err:
        if config.is_demo:
            # Demo fallback: generirati mock JIR kad CIS test ne radi
            import uuid as _uuid
            jir = 'DEMO-' + str(_uuid.uuid4())[:8]
            logger.warning('CIS demo greska (%s), mock JIR: %s', str(_fisk_err)[:80], jir)
        else:
            raise

    # Store ZKI + JIR on receipt
    receipt.zki             = zki
    receipt.jir             = jir
    receipt.fiscal_datetime = dj_tz.now()
    receipt.save(update_fields=['zki', 'jir', 'fiscal_datetime'])

    logger.info(f'Receipt #{receipt.receipt_number} fiscalized OK. JIR={jir[:8]}...')
    return jir
