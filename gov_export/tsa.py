"""
TSA (Time Stamping Authority) integracija — kriptografski vremenski žig.

XAdES-T = XAdES-BES + Timestamp od nezavisnog TSA servera.
Dokazuje KADA je dokument potpisan — ni server ni klijent ne mogu mijenjati.

Podržani TSA serveri:
- FINA TSA (https://tsa.fina.hr/) — za produkciju
- FreeTSA (https://freetsa.org/tsr) — za testiranje
"""
import hashlib
import logging
import requests
from django.conf import settings

logger = logging.getLogger('gov_export.tsa')

# TSA endpoints
TSA_SERVERS = {
    'fina': 'https://tsa.fina.hr/',
    'freetsa': 'http://freetsa.org/tsr',
}

DEFAULT_TSA = getattr(settings, 'GOVEXPORT_TSA', 'fina')


def get_timestamp_token(data_bytes, tsa_server=None):
    """
    Pošalji SHA-256 hash prema TSA serveru i dobij RFC 3161 timestamp token.
    
    Args:
        data_bytes: bytes — sadržaj za timestampiranje (XML)
        tsa_server: str — 'fina' ili 'freetsa' (default: settings.GOVEXPORT_TSA)
    
    Returns:
        bytes — DER-encoded TimeStampToken, ili None ako TSA nije dostupan
    """
    server = tsa_server or DEFAULT_TSA
    url = TSA_SERVERS.get(server)
    if not url:
        logger.warning('TSA server %s nije poznat', server)
        return None

    # SHA-256 hash
    digest = hashlib.sha256(data_bytes).digest()

    # RFC 3161 TimeStampReq — ručna konstrukcija (bez rfc3161ng dependency)
    # Koristimo ASN.1 DER encoding za minimalni TSReq
    try:
        import asn1crypto.tsp as tsp
        import asn1crypto.algos as algos
        import asn1crypto.core as core
        
        msg_imprint = tsp.MessageImprint({
            'hash_algorithm': algos.DigestAlgorithm({'algorithm': 'sha256'}),
            'hashed_message': digest,
        })
        
        ts_req = tsp.TimeStampReq({
            'version': 'v1',
            'message_imprint': msg_imprint,
            'cert_req': True,
        })
        
        req_der = ts_req.dump()
    except ImportError:
        # Fallback: ručni minimalni ASN.1 DER za SHA-256 TSReq
        # Sequence { version=1, messageImprint { sha256, hash }, certReq=true }
        logger.info('asn1crypto not available, using raw DER TSReq')
        sha256_oid = b'\x30\x0d\x06\x09\x60\x86\x48\x01\x65\x03\x04\x02\x01\x05\x00'
        hash_octet = b'\x04\x20' + digest
        msg_imprint_seq = b'\x30' + bytes([len(sha256_oid) + len(hash_octet)]) + sha256_oid + hash_octet
        version = b'\x02\x01\x01'  # INTEGER 1
        cert_req = b'\x01\x01\xff'  # BOOLEAN true
        inner = version + msg_imprint_seq + cert_req
        req_der = b'\x30' + bytes([len(inner)]) + inner

    try:
        resp = requests.post(
            url,
            data=req_der,
            headers={'Content-Type': 'application/timestamp-query'},
            timeout=(3, 10),
        )
        
        if resp.status_code == 200:
            logger.info('TSA timestamp dobiven od %s (%d bytes)', server, len(resp.content))
            return resp.content
        else:
            logger.warning('TSA %s vratio %d', server, resp.status_code)
            return None
    except requests.exceptions.RequestException as e:
        logger.warning('TSA %s nedostupan: %s', server, e)
        return None


def embed_timestamp_in_xades(xml_content, timestamp_token):
    """
    Ugradi TSA timestamp token u XAdES potpis.
    Pretvara XAdES-BES → XAdES-T.
    """
    if not timestamp_token:
        return xml_content
    
    import base64
    ts_b64 = base64.b64encode(timestamp_token).decode('ascii')
    
    # Inject SignatureTimeStamp u XAdES UnsignedProperties
    ts_xml = (
        '<xades:UnsignedProperties>'
        '<xades:UnsignedSignatureProperties>'
        '<xades:SignatureTimeStamp>'
        f'<xades:EncapsulatedTimeStamp>{ts_b64}</xades:EncapsulatedTimeStamp>'
        '</xades:SignatureTimeStamp>'
        '</xades:UnsignedSignatureProperties>'
        '</xades:UnsignedProperties>'
    )
    
    if isinstance(xml_content, bytes):
        xml_content = xml_content.decode('utf-8')
    
    # Inject prije zatvaranja QualifyingProperties
    if '</xades:QualifyingProperties>' in xml_content:
        xml_content = xml_content.replace(
            '</xades:QualifyingProperties>',
            ts_xml + '</xades:QualifyingProperties>'
        )
    elif '</ds:Signature>' in xml_content:
        # Fallback: dodaj kao Object unutar Signature
        xml_content = xml_content.replace(
            '</ds:Signature>',
            f'<ds:Object Id="TSA-Token">{ts_b64}</ds:Object></ds:Signature>'
        )
    
    return xml_content
