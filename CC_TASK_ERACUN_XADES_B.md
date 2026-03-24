# CC_TASK_ERACUN_XADES_B — XAdES-B potpis + FINA sandbox test
## Agent: Claude Code | Prioritet: P0 | Bloker za produkciju
## Datum: 2026-03-24

---

## KONTEKST — što je DONE, što nedostaje

```
✅ UBL XML generator (build_fina_xml) — radi
✅ OIB checksum validacija — radi  
✅ SOAP envelope (wrap_soap) — radi
✅ FINA eRačun endpoint: https://eracun-test.fina.hr/eRacunServis — ispravan
✅ SOAPAction header: http://www.porezna-uprava.gov.hr/fin/2024/EvidentirajERacunZahtjev — ispravan
✅ get_cert_pem() — radi (cert_path → /etc/limit-connect/certs/konjik-doo-fina-certifikat-37590751921.A.1.p12)
✅ Certifikat: vrijedi do 2030-07-31

❌ sign_xml() koristi W3C XMLSig (signxml) — FINA zahtijeva XAdES-B (ETSI EN 319 132-1)
❌ Bez XAdES-B FINA vraća odbijanje (Sistemska pogreška ili pogrešna sig)
```

---

## ZADATAK

### 1. Kreiraj `eracun/services/xades_signer.py`

XAdES-B (Basic) je minimalni XAdES potpis koji FINA prihvaća.
Razlika od XMLSig: dodaje `xades:SignedProperties` s hashom certifikata i timestamp potpisivanja.

```python
"""
XAdES-B Electronic Signature — ETSI EN 319 132-1
Za FINA eRačun sustav (HR)

XAdES-B (Basic) = XMLSig + SignedProperties (certHash + signingTime)
"""
```

**Ovisnosti (sve već instalirane):**
```
lxml          — XML manipulacija  
cryptography  — RSA potpis, SHA-256, P12 parsing
signxml       — referenca za c14n
```

**XAdES-B struktura:**
```xml
<ds:Signature>
  <ds:SignedInfo>
    <ds:Reference URI="">           ← cijeli dokument
    <ds:Reference URI="#xades-id">  ← SignedProperties
  </ds:SignedInfo>
  <ds:SignatureValue/>
  <ds:KeyInfo>
    <ds:X509Data>
      <ds:X509Certificate/>         ← DER base64
    </ds:X509Data>
  </ds:KeyInfo>
  <ds:Object>
    <xades:QualifyingProperties>
      <xades:SignedProperties Id="xades-id">
        <xades:SignedSignatureProperties>
          <xades:SigningTime/>        ← ISO 8601
          <xades:SigningCertificate>
            <xades:Cert>
              <xades:CertDigest>
                <ds:DigestMethod Algorithm="sha256"/>
                <ds:DigestValue/>     ← SHA-256 hash certa
              </xades:CertDigest>
            </xades:Cert>
          </xades:SigningCertificate>
        </xades:SignedSignatureProperties>
      </xades:SignedProperties>
    </xades:QualifyingProperties>
  </ds:Object>
</ds:Signature>
```

**Namespaces:**
```python
NS_DS    = 'http://www.w3.org/2000/09/xmldsig#'
NS_XADES = 'http://uri.etsi.org/01903/v1.3.2#'
NS_EC    = 'http://www.w3.org/2001/10/xml-exc-c14n#'
```

**Algoritmi (FINA standard):**
```
Signature:      rsa-sha256    → http://www.w3.org/2001/04/xmldsig-more#rsa-sha256
Digest:         sha-256       → http://www.w3.org/2001/04/xmlenc#sha256
C14N:           exc-c14n      → http://www.w3.org/2001/10/xml-exc-c14n#
```

**Signer interface:**
```python
def sign_xades_b(xml_element, cert_pem: bytes, key_pem: bytes) -> bytes:
    """
    Potpis lxml elementa s XAdES-B.
    Returns UTF-8 bytes potpisan XML.
    """
```

---

### 2. Izmijeni `eracun/services/engine.py`

Jedina promjena: u `process_eracun()`, korak "3. Sign":

```python
# STARO (XMLSig — ne prolazi FINA):
signed_root = sign_xml(root, cert_pem, key_pem)
xml_payload = wrap_soap(signed_root)

# NOVO (XAdES-B):
from eracun.services.xades_signer import sign_xades_b
raw_xml = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8')
xml_signed = sign_xades_b(root, cert_pem, key_pem)
# wrap_soap radi na lxml elementu — parse nazad ako sign_xades_b vraća bytes:
signed_root = etree.fromstring(xml_signed) if isinstance(xml_signed, bytes) else xml_signed
xml_payload = wrap_soap(signed_root)
```

Stara `sign_xml()` funkcija ostaje u fajlu (backward compat za fiskalizaciju).

---

### 3. Sandbox test

```bash
cd /var/www/fina-connect
venv/bin/python - << 'EOF'
import os; os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django; django.setup()

from eracun.models import ERacun, ERacunConfig
from eracun.services.engine import process_eracun

# Konjik d.o.o. — ima FINA certifikat
from companies.models import Company
company = Company.objects.get(oib='37590751921')
config = ERacunConfig.objects.get(company=company)

# Uzmi zadnji eRačun ili kreiraj test
er = ERacun.objects.filter(company=company).order_by('-created_at').first()
if er:
    er.status = 'draft'
    er.save(update_fields=['status'])
    success, msg = process_eracun(er, config)
    print(f'Rezultat: {success} | {msg}')
    print(f'FINA response: {er.xml_response[:500] if er.xml_response else "N/A"}')
EOF
```

**Očekivani uspješni odgovor od FINA:**
```xml
<prihvacenZahtjev>true</prihvacenZahtjev>
```

**Ako sandbox vrati grešku s kodom** (npr. `ERR-001`, `ERR-012`) — dodaj u output i commitaj sa greškom u poruci.

---

### 4. Commit

```
git add eracun/services/xades_signer.py eracun/services/engine.py
git commit -m "feat(eracun): XAdES-B signer — ETSI EN 319 132-1, FINA eRačun compliance"
```

---

## NAPOMENE

- `cryptography` lib je instalirana: `venv/bin/pip show cryptography`
- certifikat path: `/etc/limit-connect/certs/konjik-doo-fina-certifikat-37590751921.A.1.p12`
- lozinka certifikata: provjeri `/etc/limit-connect/certs/.cert_password` (može biti prazan = `None`)
- Ako FINA sandbox nije dostupan (timeout/SSL): commitaj xades_signer.py, dodaj test koji verificira da je `<xades:SigningTime>` prisutan u output XML-u
- **Ne diraj** `sign_xml()` (stara funkcija) — koristi se za POS fiskalizaciju

---

## DEFINICIJA DONE

- [ ] `eracun/services/xades_signer.py` postoji
- [ ] `sign_xades_b()` producira XML s `<xades:SignedProperties>` i `<xades:SigningTime>`
- [ ] `process_eracun()` koristi XAdES-B umjesto XMLSig
- [ ] Sandbox test pokrenut i rezultat dokumentiran (success ili FINA error code)
- [ ] Commit napravljen
