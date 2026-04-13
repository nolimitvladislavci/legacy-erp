"""
XAdES-BES potpis za FINA eRačun / fiskalizaciju.

Koristi signxml.xades.XAdESSigner (već instaliran, v4.3.1).
Nema novih dependency-ja — signxml, lxml i cryptography su u venv-u.

FINA zahtijeva XAdES-BES profil (Basic Electronic Signature):
- Enveloped potpis unutar SOAP Body elementa
- RSA-SHA256 algoritam
- Certifikat ugrađen u <ds:KeyInfo>
- <xades:QualifyingProperties> s SigningCertificate i SigningTime

Zamjenjuje stari sign_xml() koji je radio goli XML-DSIG.
"""
import logging
from lxml import etree

logger = logging.getLogger("eracun.xades_signer")


def sign_xades_b(root, cert_pem, key_pem):
    """
    Potpiši XML s XAdES-BES profilom.

    Args:
        root: lxml Element (FINA XML dokument)
        cert_pem: bytes — PEM certifikat
        key_pem: bytes — PEM privatni ključ

    Returns:
        lxml Element — potpisani XML s XAdES QualifyingProperties
    """
    from signxml.xades import XAdESSigner, XAdESDataObjectFormat
    from signxml import methods

    data_object = XAdESDataObjectFormat(
        Description="FINA eRacun / Fiskalizacija",
        MimeType="text/xml",
    )

    signer = XAdESSigner(
        data_object_format=data_object,
        # XAdES params
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
        method=methods.enveloped,
    )

    signed = signer.sign(
        root,
        key=key_pem,
        cert=cert_pem,
    )

    logger.info("XAdES-BES potpis uspješan")
    return signed


def verify_xades_b(signed_xml, cert_pem):
    """
    Verificiraj XAdES-BES potpis.

    Args:
        signed_xml: lxml Element ili bytes
        cert_pem: bytes — PEM certifikat za verifikaciju

    Returns:
        lxml Element — verificirani XML (baca exception ako nije validan)
    """
    from signxml.xades import XAdESVerifier

    if isinstance(signed_xml, bytes):
        signed_xml = etree.fromstring(signed_xml)

    verifier = XAdESVerifier()
    verified = verifier.verify(signed_xml, x509_cert=cert_pem)

    logger.info("XAdES-BES potpis verificiran")
    return verified
