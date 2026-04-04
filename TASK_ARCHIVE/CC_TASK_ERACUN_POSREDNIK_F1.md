# CC_TASK_ERACUN_POSREDNIK_F1 — XAdES + TSA + Schematron
## Agent: Claude Code | Prioritet: P0 | Bloker za registraciju

**Naručitelj:** Konjik d.o.o. / Marija Brtan  
**Cilj:** LIMIT Connect kao registrirani informacijski posrednik za e-Račun HR

**OBAVEZNO ČITAJ PRVO:**
- cat eracun/services/engine.py
- cat eracun/services/ubl_generator.py
- cat eracun/models.py (eracun/)

---

## STANJE DANAS

```
✅ UBL 2.1 generator (generate_ubl_xml)
✅ XSD validacija (UBL-Invoice-2.1.xsd + common schemas)
✅ EN 16931 business rules (40 pravila)
✅ XMLSig potpis (signxml, rsa-sha256) — ALI NIJE XAdES!
✅ SOAP envelope za FINA CIS
✅ FINA sandbox endpoint konfiguriran
✅ Moj-eRacun.hr wrapper
✅ ERacun model, migrations, views
✅ Schematron biblioteka (lxml.isoschematron) — ALI NEMA HR PRAVILA!

❌ XAdES-B potpis (ETSI standard, FINA zahtjev)
❌ RFC 3161 TSA vremenski žig
❌ HR Schematron pravila (od Ministarstva financija)
❌ End-to-end FINA sandbox test
```

---

## ZADATAK 1: XAdES-B potpis

### Problem

Trenutni `sign_xml()` u engine.py koristi W3C XML Signature (XMLSig).
FINA i EN 16931 zahtijevaju **XAdES-B** (ETSI EN 319 132-1).

XAdES-B dodaje:
- `xades:SignedProperties` element
- Referencu na certifikat u potpisu
- `xades:SigningCertificate` s hash-om certifikata
- `xades:SigningTime` element

### Implementacija

```python
# eracun/services/xades_signer.py — NOVI FAJL

"""
XAdES-B XML Advanced Electronic Signature
ETSI EN 319 132-1 — za FINA eRačun sukladnost

XAdES-B (Basic) — minimalni zahtjev za FINA
XAdES-T (Timestamp) — s vremenskim žigom (zadatak 2)
"""
import hashlib
import base64
import uuid
from datetime import datetime, timezone
from lxml import etree
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography import x509

# Namespaces
NS_DS   = 'http://www.w3.org/2000/09/xmldsig#'
NS_XADES= 'http://uri.etsi.org/01903/v1.3.2#'

def sign_xades_b(xml_bytes: bytes, cert_pem: bytes, key_pem: bytes, 
                 key_password: bytes = None) -> bytes:
    """
    Potpiše XML s XAdES-B potpisom.
    
    Input:  xml_bytes (UTF-8 UBL XML)
    Output: xml_bytes s XAdES-B potpisom umetnutim u dokument
    
    Struktura:
    <Invoice>
      ...
      <ext:UBLExtensions>
        <ext:UBLExtension>
          <ext:ExtensionContent>
            <ds:Signature Id="id-xades-b">
              <ds:SignedInfo>...</ds:SignedInfo>
              <ds:SignatureValue>...</ds:SignatureValue>
              <ds:KeyInfo>
                <ds:X509Data>
                  <ds:X509Certificate>BASE64_CERT</ds:X509Certificate>
                </ds:X509Data>
              </ds:KeyInfo>
              <ds:Object>
                <xades:QualifyingProperties Target="#id-xades-b">
                  <xades:SignedProperties Id="signed-props">
                    <xades:SignedSignatureProperties>
                      <xades:SigningTime>2026-03-24T12:00:00Z</xades:SigningTime>
                      <xades:SigningCertificateV2>
                        <xades:Cert>
                          <xades:CertDigest>
                            <ds:DigestMethod Algorithm="SHA-256"/>
                            <ds:DigestValue>BASE64_CERT_HASH</ds:DigestValue>
                          </xades:CertDigest>
                        </xades:Cert>
                      </xades:SigningCertificateV2>
                    </xades:SignedSignatureProperties>
                  </xades:SignedProperties>
                </xades:QualifyingProperties>
              </ds:Object>
            </ds:Signature>
          </ext:ExtensionContent>
        </ext:UBLExtension>
      </ext:UBLExtensions>
      ...
    </Invoice>
    """
    # Učitaj certifikat i ključ
    cert = x509.load_pem_x509_certificate(cert_pem)
    private_key = serialization.load_pem_private_key(key_pem, password=key_password)
    
    # Parsed XML
    root = etree.fromstring(xml_bytes)
    
    # Certifikat DER → base64
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode()
    
    # Hash certifikata (SHA-256)
    cert_hash = hashlib.sha256(cert_der).digest()
    cert_hash_b64 = base64.b64encode(cert_hash).decode()
    
    # Signing time
    signing_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    sig_id = f'id-xades-b-{uuid.uuid4().hex[:8]}'
    signed_props_id = f'signed-props-{uuid.uuid4().hex[:8]}'
    
    # Izgradi XAdES strukture
    # ... (kompletna implementacija prema ETSI EN 319 132-1)
    # Reference implementacija: signxml + ručno XAdES elementi
    
    # Digest dokumenta (canonicalized)
    from lxml.etree import tostring
    c14n = tostring(root, method='c14n', exclusive=True)
    doc_hash = hashlib.sha256(c14n).digest()
    doc_hash_b64 = base64.b64encode(doc_hash).decode()
    
    # Potpis SignedInfo
    signed_info_xml = _build_signed_info(doc_hash_b64, signed_props_id)
    si_c14n = etree.tostring(signed_info_xml, method='c14n', exclusive=True)
    signature_bytes = private_key.sign(si_c14n, padding.PKCS1v15(), hashes.SHA256())
    signature_b64 = base64.b64encode(signature_bytes).decode()
    
    # Umetni Signature u dokument
    signature_el = _build_xades_b_element(
        sig_id, signed_props_id, signed_info_xml,
        signature_b64, cert_b64, cert_hash_b64, signing_time
    )
    
    # Dodaj u UBLExtensions ili izravno u dokument
    _insert_signature(root, signature_el)
    
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)
```

**NAPOMENA:** Ako se implementacija pokaže previše kompleksnom, koristi `py-xades` library:
```bash
venv/bin/pip install py-xades --break-system-packages
```

---

## ZADATAK 2: RFC 3161 TSA — Vremenski žig

```python
# eracun/services/tsa_client.py — NOVI FAJL

"""
RFC 3161 Time Stamp Authority klijent za FINA TSA.

FINA TSA endpoint: https://tsa.fina.hr/tsa
Testni TSA (besplatni): http://timestamp.digicert.com
                        http://tsa.belgium.be/connect
"""
import hashlib
import base64
import requests
from lxml import etree

FINA_TSA_URL  = 'https://tsa.fina.hr/tsa'
TEST_TSA_URLS = [
    'http://timestamp.digicert.com',
    'http://tsa.belgium.be/connect',
    'http://timestamp.apple.com/ts01',
]

def get_timestamp(data: bytes, use_test: bool = True) -> bytes:
    """
    Dohvati RFC 3161 timestamp za zadane podatke.
    
    Input:  data (bytes koje se timestampaju — obično hash dokumenta)
    Output: timestamp token (bytes) za umetanje u XAdES-T
    """
    import hashlib
    
    # SHA-256 hash podataka
    data_hash = hashlib.sha256(data).digest()
    
    # TimeStampReq ASN.1 (DER encoded)
    # Koristimo pyhanko-pdf ili rfc3161ng library
    try:
        import rfc3161ng
        
        tsa_url = TEST_TSA_URLS[0] if use_test else FINA_TSA_URL
        
        timestamp = rfc3161ng.get_timestamp(
            data=data,
            hash_algorithm='sha256',
            url=tsa_url,
            nonce=True,
        )
        return timestamp
        
    except ImportError:
        # Fallback: manual RFC 3161 request
        return _manual_tsa_request(data_hash, use_test)


def _manual_tsa_request(data_hash: bytes, use_test: bool) -> bytes:
    """Ručni RFC 3161 zahtjev bez external library."""
    # TSA Request (minimalni ASN.1)
    # MessageImprint: SHA-256 OID + hash
    sha256_oid = b'\x30\x31\x30\x0d\x06\x09\x60\x86\x48\x01\x65\x03\x04\x02\x01\x05\x00\x04\x20'
    message_imprint = sha256_oid + data_hash
    
    # TimeStampReq
    tsr = (
        b'\x30\x00'  # SEQUENCE (placeholder)
        b'\x02\x01\x01'  # version: 1
        b'\x30\x00'  # messageImprint placeholder
        + message_imprint
    )
    
    tsa_url = TEST_TSA_URLS[0] if use_test else FINA_TSA_URL
    
    resp = requests.post(
        tsa_url,
        data=tsr,
        headers={'Content-Type': 'application/timestamp-query'},
        timeout=10,
    )
    
    if resp.status_code == 200:
        return resp.content  # TimeStampResp (DER)
    
    raise RuntimeError(f'TSA error {resp.status_code}: {resp.text[:200]}')


def embed_timestamp_in_xades(xml_bytes: bytes, use_test: bool = True) -> bytes:
    """
    Nadogradi XAdES-B u XAdES-T dodavanjem timestampa.
    
    Traži <ds:SignatureValue> element i timestampa njegovu vrijednost.
    Timestamp se umeće kao <xades:SignatureTimeStamp> u QualifyingProperties.
    """
    root = etree.fromstring(xml_bytes)
    
    # Nađi SignatureValue
    ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
    sig_val_el = root.find('.//ds:SignatureValue', ns)
    
    if sig_val_el is None:
        raise ValueError('XML nema XAdES potpis — pozovi sign_xades_b() prvo')
    
    sig_val_bytes = base64.b64decode(sig_val_el.text.strip())
    timestamp_token = get_timestamp(sig_val_bytes, use_test)
    
    # Umetni u QualifyingProperties
    # ... (XAdES-T proširenje)
    
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)
```

**Instalacija:**
```bash
venv/bin/pip install rfc3161ng --break-system-packages
```

---

## ZADATAK 3: HR Schematron pravila

Preuzmi HR Schematron fajlove s:
```
https://eracun.mfin.hr/schematron/CIUS-HR-2025.sch
https://eracun.mfin.hr/schematron/PEPPOL-EN16931.sch
```

Ako URL ne radi, provjeri:
```
https://www.mfin.hr/hr/e-racun/tehnicke-specifikacije/
```

Spremi u: `eracun/schemas/schematron/`

Dodaj u `validator.py`:
```python
SCHEMATRON_HR = os.path.join(XSD_DIR, 'schematron', 'CIUS-HR-2025.sch')

def validate_schematron_hr(xml_bytes):
    """Validira XML prema HR CIUS-2025 Schematron pravilima."""
    if not os.path.exists(SCHEMATRON_HR):
        logger.warning('HR Schematron not found — skipping')
        return True, []
    
    from lxml.isoschematron import Schematron
    schema = etree.parse(SCHEMATRON_HR)
    validator = Schematron(schema, store_report=True)
    doc = etree.fromstring(xml_bytes)
    is_valid = validator.validate(doc)
    
    errors = []
    if not is_valid:
        report = validator.validation_report
        for failed in report.findall('.//{http://purl.oclc.org/dsdl/svrl}failed-assert'):
            errors.append(failed.find('{http://purl.oclc.org/dsdl/svrl}text').text)
    
    return is_valid, errors
```

---

## ZADATAK 4: End-to-end FINA Sandbox test

```python
# eracun/management/commands/test_fina_sandbox.py

"""
Django management command za testiranje FINA sandboxa.
Kreira testni e-Račun, potpisuje ga XAdES-B, šalje na sandbox.

Pokretanje:
  venv/bin/python manage.py test_fina_sandbox --company-oib 37590751921
"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Test FINA sandbox end-to-end'
    
    def add_arguments(self, parser):
        parser.add_argument('--company-oib', type=str, default='37590751921')
    
    def handle(self, *args, **options):
        from eracun.models import ERacun, ERacunConfig, ERacunItem
        from eracun.services.engine import validate_eracun, build_fina_xml
        from eracun.services.ubl_generator import generate_ubl_xml
        from eracun.services.validator import validate_xsd
        from companies.models import Company
        from decimal import Decimal
        import uuid
        
        oib = options['company_oib']
        company = Company.objects.filter(oib=oib).first()
        if not company:
            self.stderr.write(f'Firma s OIB {oib} ne postoji')
            return
        
        # Kreiraj testni e-Račun
        eracun = ERacun.objects.create(
            company=company,
            invoice_number=f'TEST-{uuid.uuid4().hex[:6].upper()}',
            invoice_type='380',  # Commercial Invoice
            invoice_date='2026-03-24',
            due_date='2026-04-24',
            issuer_oib=oib,
            issuer_name=company.name,
            issuer_address=company.address or 'Test adresa',
            recipient_oib='12345678901',  # Test OIB
            recipient_name='Testni primatelj d.o.o.',
            recipient_address='Testna 1, 10000 Zagreb',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('250.00'),
            total=Decimal('1250.00'),
            currency='EUR',
            note='Testni e-Račun za FINA sandbox validaciju',
        )
        ERacunItem.objects.create(
            eracun=eracun,
            description='Testna usluga',
            quantity=Decimal('1'),
            unit='sat',
            unit_price=Decimal('1000.00'),
            tax_rate=Decimal('25.00'),
            line_total=Decimal('1000.00'),
        )
        
        self.stdout.write(f'Kreiran testni e-Račun: {eracun.pk}')
        
        # Validacija
        is_valid, errors = validate_eracun(eracun)
        if not is_valid:
            self.stderr.write(f'Validacija pala: {errors}')
            eracun.delete()
            return
        self.stdout.write('✅ validate_eracun: PASS')
        
        # UBL XML generacija
        xml_bytes = generate_ubl_xml(eracun)
        self.stdout.write(f'✅ UBL XML: {len(xml_bytes)} bytes')
        
        # XSD validacija
        xsd_valid, xsd_errors = validate_xsd(xml_bytes)
        if not xsd_valid:
            self.stderr.write(f'XSD validacija pala: {xsd_errors}')
        else:
            self.stdout.write('✅ XSD validacija: PASS')
        
        # Spremi XML za inspekciju
        with open(f'/tmp/test_eracun_{eracun.pk}.xml', 'wb') as f:
            f.write(xml_bytes)
        self.stdout.write(f'XML spremen: /tmp/test_eracun_{eracun.pk}.xml')
        
        # TODO: XAdES-B potpis + FINA sandbox slanje
        self.stdout.write('⚠️  XAdES-B: nije implementiran (zadatak 1)')
        self.stdout.write('⚠️  FINA sandbox slanje: čeka XAdES-B')
        
        eracun.delete()
        self.stdout.write('✅ Test završen')
```

---

## DONE kriterij

```bash
# 1. XAdES-B radi
venv/bin/python -c "
from eracun.services.xades_signer import sign_xades_b
print('XAdES-B: OK')
"

# 2. TSA radi (test TSA)
venv/bin/python -c "
from eracun.services.tsa_client import get_timestamp
ts = get_timestamp(b'test data', use_test=True)
print('TSA OK, token:', len(ts), 'bytes')
"

# 3. Sandbox test
venv/bin/python manage.py test_fina_sandbox --company-oib 37590751921
```

---

## ADMINISTRATIVNI KORACI (Ivan/Marija, nije kod)

```
1. Kupnja kvalificiranog certifikata:
   - FINA: https://www.fina.hr/pki-certifikati
   - AKD: https://www.akd.hr
   - Cijena: ~200-400 EUR/god
   - Rok: 5-10 radnih dana

2. Registracija u Registar informacijskih posrednika:
   - Ministarstvo gospodarstva
   - Zahtjev + tehnička dokumentacija + certifikat
   - Rok odobrenja: 30-90 dana

3. FINA sandbox pristup:
   - Zahtjev na: eracun@fina.hr
   - Potrebno: OIB tvrtke + tehnički kontakt
   - Rok: 5-10 radnih dana

4. (Opcionalno v2) Peppol Access Point:
   - OpenPeppol membership: ~500 EUR/god
   - Certifikacija: 3-6 månader
   - Tek nakon HR registracije
```
