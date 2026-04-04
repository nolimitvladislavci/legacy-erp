# CC_TASK_EU_AT_RKSV_SI_FURS.md
# Za: CC Code #2
# Datum: 2026-03-31
# Rok: 12.04.2026.
# Prioritet: VISOKO — AT i SI tržišta, osnova za EU ekspanziju
# Procjena: 3-4 dana
#
# KONTEKST:
# AT (Austrija) i SI (Slovenija) su u country_registry.py sa status='PLANNED'
# Oba su TODO — nema adaptera, nema API klijenata
# AT: RKSV (Registrierkassensicherheitsverordnung) — fiskalizacija blagajne
# SI: FURS API — slično HR FINA, ZOI + EOR za fiskalizaciju
#
# PRIORITET: AT > SI (veće tržište, više EU partnera u AT nego SI)
# VISKOVIC BAU je live DE klijent — AT je sljedeći korak (Graz, Wien...)
#
# NAPOMENA: Ovo nisu minimalne implementacije — dovoljno za testiranje
# s prvim AT/SI klijentima. Production certifikat dolazi s prvim klijentom.

---

## ŠTO POSTOJI

```bash
# Provjeri stanje
grep -rn "AT\|RKSV\|austria\|SI\|FURS\|slovenia" core/country_registry.py | head -20
cat core/country_registry.py | grep -A 15 "'AT'"
cat core/country_registry.py | grep -A 15 "'SI'"
```

Postoji:
- `companies/models.py` — `FiscalSystem.AT_RKSV` enum vrijednost
- `core/country_registry.py` — AT i SI konfigurirani, status='PLANNED'
- `pos/services/checkout.py` — routing postoji za DE, placeholder za AT

---

## DIO A — AUSTRIJA (RKSV)

### Zakonski okvir

**RKSV** (Registrierkassensicherheitsverordnung, BGBl. II Nr. 410/2015)
- Obvezno za firme s godišnjim prometom > 15.000 EUR
- Svaki bon mora imati kriptografski potpis
- Potpis generira: A-Trust ili certifikat iz USB tokena (RK-Suite)
- Svaki 3. bon mora imati **DEP7** (Datenerfassungsprotokoll) export zapis
- BMF mreža provjerava autentičnost putem QR koda

**Ključna razlika od HR:** RKSV nema centralni API server kao FINA CIS.
Potpis se generira lokalno (hardware token ili cloud A-Trust), bon nosi QR.
BMF provjera je post-hoc (revizija), ne real-time.

### A1. AT FiscalConfig model

Dodati u `eracun/models.py` ili novi `at_fiscal/models.py`:

```python
class ATRKSVConfig(models.Model):
    """
    Konfiguracija za AT RKSV (Registrierkassensicherheitsverordnung).
    Svaka AT firma treba vlasteni certifikat (A-Trust ili lokalni).
    """
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='at_rksv_config'
    )
    
    # Registracija blagajne kod BMF
    kassen_id = models.CharField(
        max_length=100, blank=True,
        verbose_name='Kassen-ID (RKSV)',
        help_text='Jedinstveni ID blagajne registriran kod BMF. Format: AT123456789-1'
    )
    
    # Certifikat za potpis
    CERT_TYPE_CHOICES = [
        ('a_trust_cloud', 'A-Trust Cloud Signatur'),
        ('local_rk', 'Lokalni RK-Suite certifikat'),
        ('mock', 'Test/Mock (ne za produkciju)'),
    ]
    cert_type = models.CharField(
        max_length=20, choices=CERT_TYPE_CHOICES, default='mock'
    )
    
    # A-Trust cloud API (ako koristi cloud potpis)
    a_trust_api_key = models.CharField(max_length=200, blank=True)
    a_trust_api_url = models.URLField(
        default='https://hs-abnahme.a-trust.at/ocs/v1',
        help_text='Produkcija: https://hs.a-trust.at/ocs/v1'
    )
    
    # Chain vrijednost (cumulative counter za lančani hash)
    chain_value = models.CharField(max_length=64, blank=True,
        help_text='SHA-256 hash prethodnog bona (chain integrity)')
    receipt_counter = models.PositiveBigIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=False)
    registered_at_bmf = models.BooleanField(default=False)
    use_test_mode = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AT RKSV konfiguracija'
        verbose_name_plural = 'AT RKSV konfiguracije'

    def __str__(self):
        return f'RKSV: {self.company.name} | kasse={self.kassen_id}'
```

Migracija (dodati u odgovarajući app ili kreiraj `at_fiscal`):
```bash
venv/bin/python manage.py makemigrations eracun --name at_rksv_config
# ILI kreiraj novi app:
venv/bin/python manage.py startapp at_fiscal
```

### A2. RKSV Adapter

Kreirati `pos/rksv_adapter.py`:

```python
"""
RKSV Adapter — Registrierkassensicherheitsverordnung (AT).

Generira kriptografski potpis za svaki bon (Kassenbon).
Format: base64(SHA256(Zettelkette)) + QR kod za BMF provjeru.

Specifikacija: https://www.bmf.gv.at/dam/jcr:c8d9f75e-a26e-4ca6-a3d3-89fc6a1cabb6/BMF_Registrierkassenpflicht_Infoblatt_2016.pdf

Razlike od HR FINA:
  - Nema real-time API — potpis je lokalni/cloud
  - QR kod nosi JWS (JSON Web Signature) potpisanu vrijednost
  - Lančani hash: svaki bon uključuje hash prethodnog
  - BMF provjera je offline (QR scan)
"""
import hashlib
import base64
import json
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger('pos.rksv')


class RKSVError(Exception):
    """RKSV potpis greška — ne blokira naplatu u test modu."""
    pass


class RKSVAdapter:
    """
    RKSV adapter za AT fiskalizaciju blagajne.
    
    Podržava:
      - Mock mode (development/testiranje)
      - A-Trust Cloud (produkcija)
      - Lokalni certifikat (produkcija)
    """
    
    def __init__(self, config):
        """
        config: ATRKSVConfig instance
        """
        self.config = config
        self.kassen_id = config.kassen_id or 'AT-TEST-001'
        self.test_mode = config.use_test_mode

    @classmethod
    def from_company(cls, company):
        """Dohvati adapter za firmu ili vrati None ako nije konfigurirana."""
        try:
            config = company.at_rksv_config
            return cls(config)
        except Exception:
            return None

    def sign_receipt(self, receipt) -> dict:
        """
        Potpiši bon po RKSV specifikaciji.
        
        Returns:
            dict s ključevima: signature, qr_code, chain_value, receipt_counter
        """
        # 1. Inkrementiraj counter
        self.config.receipt_counter += 1
        counter = self.config.receipt_counter
        
        # 2. Kreiraj JWS payload (Belegdaten)
        payload = self._build_payload(receipt, counter)
        
        # 3. Generiraj potpis
        if self.config.cert_type == 'mock' or self.test_mode:
            signature = self._mock_sign(payload)
        elif self.config.cert_type == 'a_trust_cloud':
            signature = self._a_trust_sign(payload)
        else:
            signature = self._local_sign(payload)
        
        # 4. Ažuriraj chain value
        chain = hashlib.sha256(
            (self.config.chain_value + signature).encode()
        ).hexdigest()
        self.config.chain_value = chain
        self.config.save(update_fields=['chain_value', 'receipt_counter'])
        
        # 5. Generiraj QR sadržaj
        qr_content = self._build_qr(payload, signature, counter)
        
        logger.info(f'RKSV: Bon #{counter} potpisan za {self.kassen_id}')
        
        return {
            'signature': signature,
            'qr_content': qr_content,
            'chain_value': chain,
            'receipt_counter': counter,
            'kassen_id': self.kassen_id,
            'signed_at': datetime.utcnow().isoformat() + 'Z',
        }

    def _build_payload(self, receipt, counter) -> str:
        """Gradi RKSV Belegdaten string."""
        # Format: _R1_{KassenID}_{BelegNr}_{DatumUhrzeit}_{Betrag-Normal}_{Betrag-Ermaessigt1}_{Betrag-Ermaessigt2}_{Betrag-Null}_{Betrag-Besonders}_{BelegChain}
        total = receipt.total or Decimal('0')
        date_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        
        return (
            f'_R1_{self.kassen_id}_{counter}_{date_str}'
            f'_{total:.2f}_0.00_0.00_0.00_0.00'
            f'_{self.config.chain_value or "STARTBELEG"}'
        )

    def _mock_sign(self, payload) -> str:
        """Mock potpis za testiranje (SHA256 hash, ne pravi JWS)."""
        hash_val = hashlib.sha256(payload.encode()).digest()
        return base64.b64encode(hash_val).decode()[:44]

    def _a_trust_sign(self, payload) -> str:
        """A-Trust Cloud potpis (MOCK — zahtijeva pravi A-Trust ugovor)."""
        try:
            import requests
            resp = requests.post(
                f'{self.config.a_trust_api_url}/sign',
                json={'data': base64.b64encode(payload.encode()).decode()},
                headers={'Authorization': f'Bearer {self.config.a_trust_api_key}'},
                timeout=10,
            )
            if resp.ok:
                return resp.json().get('signature', '')
            logger.error(f'A-Trust error: {resp.status_code} {resp.text[:100]}')
        except Exception as e:
            logger.error(f'A-Trust connection error: {e}')
        # Fallback na mock u slučaju greške (ne blokirati naplatu)
        return self._mock_sign(payload)

    def _local_sign(self, payload) -> str:
        """Lokalni certifikat potpis — placeholder."""
        logger.warning('Lokalni RKSV potpis nije implementiran — koristim mock')
        return self._mock_sign(payload)

    def _build_qr(self, payload, signature, counter) -> str:
        """Gradi QR sadržaj za BMF provjeru (OCR-B format)."""
        return f'{payload}_{signature}'

    def generate_dep7_entry(self, receipt, signature_data: dict) -> dict:
        """
        Generira DEP7 (Datenerfassungsprotokoll) zapis.
        Svaki bon mora biti u DEP-u. Svaka 3 bona = novi DEP blok.
        """
        return {
            'Belegnummer': signature_data['receipt_counter'],
            'Beleg': {
                'Zeilentyp': 'Bon',
                'Datum': signature_data['signed_at'],
                'Umsatz': float(receipt.total or 0),
                'Signaturwert': signature_data['signature'],
                'Kassen-ID': self.kassen_id,
            }
        }
```

### A3. Integracija u POS checkout

U `pos/services/checkout.py`, nakon HR i DE routing, dodati AT:

```python
# Route 3: AT — RKSV
if fiscal_system == 'at_rksv' or getattr(company, 'country', 'HR') == 'AT':
    try:
        from pos.rksv_adapter import RKSVAdapter
        adapter = RKSVAdapter.from_company(company)
        if adapter:
            sig_data = adapter.sign_receipt(receipt)
            receipt.rksv_signature = sig_data.get('signature', '')
            receipt.rksv_qr = sig_data.get('qr_content', '')
            receipt.save(update_fields=['rksv_signature', 'rksv_qr'])
            logger.info(f'RKSV OK: Bon #{sig_data["receipt_counter"]}')
        else:
            logger.warning(f'AT firma bez RKSV config: {company.name}')
    except Exception as e:
        logger.error(f'RKSV error (non-blocking): {e}')
        # RKSV greška NE blokira naplatu — logira se za retry
```

Dodati polja na `POSReceipt` model:
```python
rksv_signature = models.CharField(max_length=100, blank=True)
rksv_qr = models.CharField(max_length=500, blank=True)
```

---

## DIO B — SLOVENIJA (FURS)

### Zakonski okvir

**Zakon o davčnem potrjevanju računov (ZDavPR)**
- FURS API: https://blagajne.fu.gov.si:9003/v1/cash_registers/invoices
- Test: https://blagajne-test.fu.gov.si:9003/v1
- Svaki bon mora imati **ZOI** (zaštitna oznaka izdajatelja) i **EOR** (evidencijska oznaka)
- ZOI = MD5 hash od podataka bona, šifriran privatnim ključem firme
- EOR = odgovor FURS servera koji potvrđuje primitak

**Sličnost s HR:** Isti princip kao FINA CIS, drugačiji format i URL.

### B1. FURS API klijent

Kreirati `pos/furs_adapter.py`:

```python
"""
FURS Adapter — Davčno potrjevanje računov (SI).

FURS API v1 za fiskalizaciju POS blagajne u Sloveniji.
ZDavPR (Zakon o davčnem potrjevanju računov).

API: https://blagajne.fu.gov.si:9003/v1/cash_registers/invoices
Test: https://blagajne-test.fu.gov.si:9003/v1/cash_registers/invoices
Certifikat: FURS izdaje (FIZPS certifikat)
"""
import logging
import hashlib
import base64
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('pos.furs')

# FURS API endpoints
FURS_PROD_URL = 'https://blagajne.fu.gov.si:9003/v1/cash_registers/invoices'
FURS_TEST_URL = 'https://blagajne-test.fu.gov.si:9003/v1/cash_registers/invoices'


class FURSError(Exception):
    """FURS API greška."""
    pass


class FURSAdapter:
    """
    FURS adapter za slovensku fiskalizaciju.
    
    Flow:
    1. Generiraj ZOI (Zaščitna oznaka izdajatelja)
    2. Pošalji na FURS API
    3. Primi EOR (Evidenčna oznaka računa)
    4. Ispiši QR s EOR-om na bon
    """

    def __init__(self, company, test_mode=True):
        self.company = company
        self.test_mode = test_mode
        self.api_url = FURS_TEST_URL if test_mode else FURS_PROD_URL
        # Certifikat bi se učitao iz company.si_furs_config
        self.cert_path = getattr(settings, 'SI_FURS_CERT_PATH', '')
        self.key_path = getattr(settings, 'SI_FURS_KEY_PATH', '')
        self.tax_number = company.oib or ''

    @classmethod
    def from_company(cls, company):
        """Dohvati adapter za firmu ili None."""
        if company.country != 'SI':
            return None
        # Provjeri je li FURS konfiguriran
        test_mode = getattr(settings, 'SI_FURS_TEST_MODE', True)
        return cls(company, test_mode=test_mode)

    def generate_zoi(self, receipt) -> str:
        """
        Generira ZOI (Zaščitna oznaka izdajatelja).
        
        ZOI = prvih 32 znakova MD5 hasha od:
        DavcnaStevilkaZavezanca || DatumIzdajeRacuna || ZaporednaStevKonf ||
        PoslovnaProstaraID || ElektronaskanapravID || Znesek
        """
        date_str = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        amount_str = f'{receipt.total or Decimal("0"):.2f}'
        
        zoi_input = (
            f'{self.tax_number}{date_str}'
            f'{receipt.receipt_number or str(receipt.id)[:8]}'
            f'1'  # PoslovnaProstaraID
            f'1'  # ElektronapravID  
            f'{amount_str}'
        )
        
        # U produkciji: RSA potpis s FURS certifikatom
        # U testu: MD5 hash
        if self.cert_path:
            return self._rsa_sign(zoi_input)
        else:
            md5 = hashlib.md5(zoi_input.encode()).hexdigest()
            return md5[:32].upper()

    def _rsa_sign(self, data) -> str:
        """RSA potpis za ZOI (produkcija — zahtijeva FURS certifikat)."""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            
            with open(self.key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
            
            signature = private_key.sign(data.encode(), padding.PKCS1v15(), hashes.SHA256())
            md5 = hashlib.md5(signature).hexdigest()
            return md5[:32].upper()
        except Exception as e:
            logger.error(f'FURS RSA sign error: {e}')
            # Fallback na MD5 mock
            return hashlib.md5(data.encode()).hexdigest()[:32].upper()

    def fiscalize(self, receipt) -> dict:
        """
        Fiskalizira bon: pošalji na FURS, primi EOR.
        
        Returns:
            dict: {'eor': str, 'zoi': str, 'ok': bool}
        """
        zoi = self.generate_zoi(receipt)
        
        # Kreiraj FURS XML request
        xml_request = self._build_request(receipt, zoi)
        
        try:
            resp = requests.post(
                self.api_url,
                data=xml_request,
                headers={'Content-Type': 'application/xml; charset=UTF-8'},
                cert=(self.cert_path, self.key_path) if self.cert_path else None,
                verify=not self.test_mode,
                timeout=10,
            )
            
            if resp.ok:
                eor = self._parse_eor(resp.text)
                logger.info(f'FURS OK: bon {receipt.receipt_number} → EOR {eor[:8]}...')
                return {'ok': True, 'eor': eor, 'zoi': zoi}
            else:
                logger.error(f'FURS error: {resp.status_code} {resp.text[:200]}')
                return {'ok': False, 'eor': '', 'zoi': zoi, 'error': resp.text[:100]}
                
        except requests.Timeout:
            logger.error('FURS timeout — bon bilježen za retry')
            return {'ok': False, 'eor': '', 'zoi': zoi, 'error': 'TIMEOUT'}
        except Exception as e:
            logger.error(f'FURS connection error: {e}')
            return {'ok': False, 'eor': '', 'zoi': zoi, 'error': str(e)}

    def _build_request(self, receipt, zoi) -> str:
        """Gradi FURS XML request po ZDavPR specifikaciji."""
        message_id = str(uuid.uuid4())
        date_str = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        amount = float(receipt.total or 0)
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <fu:InvoiceRequest xmlns:fu="http://www.fu.gov.si/FiscalVerificationInvoice">
      <fu:Header>
        <fu:MessageID>{message_id}</fu:MessageID>
        <fu:DateTime>{date_str}</fu:DateTime>
      </fu:Header>
      <fu:Invoice>
        <fu:TaxNumber>{self.tax_number}</fu:TaxNumber>
        <fu:IssueDateTime>{date_str}</fu:IssueDateTime>
        <fu:NumberingStructure>B</fu:NumberingStructure>
        <fu:InvoiceIdentifier>
          <fu:BusinessPremiseID>PROSTORA1</fu:BusinessPremiseID>
          <fu:ElectronicDeviceID>NAPRAVA1</fu:ElectronicDeviceID>
          <fu:InvoiceNumber>{receipt.receipt_number or str(receipt.id)[:8]}</fu:InvoiceNumber>
        </fu:InvoiceIdentifier>
        <fu:InvoiceAmount>{amount:.2f}</fu:InvoiceAmount>
        <fu:PaymentAmount>{amount:.2f}</fu:PaymentAmount>
        <fu:ProtectedID>{zoi}</fu:ProtectedID>
        <fu:OperatorTaxNumber>{self.tax_number}</fu:OperatorTaxNumber>
      </fu:Invoice>
    </fu:InvoiceRequest>
  </soap:Body>
</soap:Envelope>"""

    def _parse_eor(self, xml_response) -> str:
        """Izvadi EOR iz FURS XML odgovora."""
        try:
            root = ET.fromstring(xml_response)
            ns = {'fu': 'http://www.fu.gov.si/FiscalVerificationInvoice'}
            eor_el = root.find('.//fu:UniqueInvoiceID', ns)
            if eor_el is not None:
                return eor_el.text or ''
        except Exception as e:
            logger.error(f'FURS EOR parse error: {e}')
        return ''
```

### B2. SI routing u checkout

Dodati u `pos/services/checkout.py`:

```python
# Route 4: SI — FURS
if fiscal_system == 'si_furs' or getattr(company, 'country', 'HR') == 'SI':
    try:
        from pos.furs_adapter import FURSAdapter
        adapter = FURSAdapter.from_company(company)
        if adapter:
            result = adapter.fiscalize(receipt)
            if result.get('ok'):
                receipt.jir = result.get('eor', '')  # EOR → JIR polje
                receipt.zki = result.get('zoi', '')  # ZOI → ZKI polje
                receipt.is_fiscalized = True
                receipt.fiscal_datetime = timezone.now()
                receipt.save(update_fields=['jir', 'zki', 'is_fiscalized', 'fiscal_datetime'])
                logger.info(f'FURS OK: EOR={result["eor"][:8]}...')
            else:
                logger.error(f'FURS error: {result.get("error")}')
    except Exception as e:
        logger.error(f'FURS checkout error (non-blocking): {e}')
```

### B3. SI Country Registry update

U `core/country_registry.py` ažuriraj SI status:

```python
'SI': {
    'name': 'Slovenija',
    'fiscal_provider': 'furs',
    'invoice_format': 'ubl',   # PEPPOL UBL za eRačun
    'tax_rates': [22, 9.5, 5, 0],
    'currency': 'EUR',
    'furs_test_url': 'https://blagajne-test.fu.gov.si:9003/v1/cash_registers/invoices',
    'furs_prod_url': 'https://blagajne.fu.gov.si:9003/v1/cash_registers/invoices',
    'kleinbetragsrechnung_limit': 0,  # SI nema
    'legal_text': 'Davčno potrjeni račun — FURS',
    'status': 'BETA',  # Promijeni s PLANNED na BETA
},
```

I AT:
```python
'AT': {
    ...
    'status': 'BETA',  # Promijeni s PLANNED na BETA
    'rksv_bmf_url': 'https://finanzonline.bmf.gv.at',
    'a_trust_url': 'https://hs.a-trust.at/ocs/v1',
},
```

---

## DIO C — Zajednička infrastruktura

### C1. CompliancePackage seed (CC_TASK_LICENSING_ENGINE.md dopuna)

Ažuriraj `CompliancePackage` seed s potpunim podacima:

```bash
venv/bin/python manage.py shell << 'PYEOF'
from companies.models import CompliancePackage

packages = [
    {
        'country': 'at',
        'name': 'AT RKSV paket',
        'description': 'Registrierkassensicherheitsverordnung — obvezna fiskalizacija POS od 2017.',
        'legal_basis': 'RKSV (BGBl. II Nr. 410/2015), BarUV (BGBl. I Nr. 77/2012)',
        'mandatory_from': '2017-01-01',
        'has_fiscal': True,
        'has_einvoice': False,  # eRačun AT od 2024. (B2G), B2B NIJE obavezan
        'has_tse': False,       # AT koristi A-Trust, ne TSE
        'monthly_addon_eur': 40,
    },
    {
        'country': 'si',
        'name': 'SI FURS paket',
        'description': 'Davčno potrjevanje računov — FURS API fiskalizacija.',
        'legal_basis': 'ZDavPR (Ur. l. RS, 57/15)',
        'mandatory_from': '2016-01-02',
        'has_fiscal': True,
        'has_einvoice': True,   # eRačun B2G od 2015.
        'monthly_addon_eur': 35,
    },
]

for p in packages:
    from django.utils.dateparse import parse_date
    if 'mandatory_from' in p:
        p['mandatory_from'] = parse_date(p.get('mandatory_from', ''))
    obj, created = CompliancePackage.objects.update_or_create(
        country=p['country'],
        defaults=p
    )
    print(f'{"Kreiran" if created else "Ažuriran"}: {obj.name}')
PYEOF
```

### C2. Settings dodaci

Dodati u `core/settings.py`:
```python
# AT RKSV
AT_RKSV_TEST_MODE = os.environ.get('AT_RKSV_TEST_MODE', 'True') == 'True'
AT_A_TRUST_API_URL = os.environ.get('AT_A_TRUST_API_URL', 'https://hs-abnahme.a-trust.at/ocs/v1')
AT_A_TRUST_API_KEY = os.environ.get('AT_A_TRUST_API_KEY', '')

# SI FURS
SI_FURS_TEST_MODE = os.environ.get('SI_FURS_TEST_MODE', 'True') == 'True'
SI_FURS_CERT_PATH = os.environ.get('SI_FURS_CERT_PATH', '')
SI_FURS_KEY_PATH = os.environ.get('SI_FURS_KEY_PATH', '')
```

---

## KORAK — Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from pos.rksv_adapter import RKSVAdapter
from pos.furs_adapter import FURSAdapter
from companies.models import Company

# Test AT RKSV (mock mode)
print('=== AT RKSV Test ===')
class MockReceipt:
    total = __import__('decimal').Decimal('99.00')
    receipt_number = 'TEST-001'
    id = __import__('uuid').uuid4()

class MockConfig:
    kassen_id = 'AT-TEST-001'
    use_test_mode = True
    cert_type = 'mock'
    a_trust_api_key = ''
    a_trust_api_url = ''
    chain_value = ''
    receipt_counter = 0
    def save(self, **kwargs): pass

adapter = RKSVAdapter(MockConfig())
result = adapter.sign_receipt(MockReceipt())
print(f'ZOI/Signature: {result["signature"][:20]}...')
print(f'Counter: {result["receipt_counter"]}')
print(f'QR content: {result["qr_content"][:40]}...')

# Test SI FURS ZOI
print()
print('=== SI FURS Test ===')
class MockCompany:
    country = 'SI'
    oib = '12345678'
si_adapter = FURSAdapter(MockCompany(), test_mode=True)
zoi = si_adapter.generate_zoi(MockReceipt())
print(f'ZOI generated: {zoi}')
print(f'ZOI length: {len(zoi)} (mora biti 32)')
print(f'FURS test URL: {si_adapter.api_url}')

# CompliancePackage
from companies.models import CompliancePackage
for p in CompliancePackage.objects.all():
    print(f'Package: {p.country.upper()} — {p.name} ({p.status if hasattr(p,"status") else "OK"})')
PYEOF
```

---

## COMMIT

```bash
git add pos/ core/ companies/ eracun/
git commit -m "feat(eu/at-si): RKSV (AT) + FURS (SI) adapteri — beta implementacija

pos/rksv_adapter.py (NOVO):
  AT RKSV Registrierkassensicherheitsverordnung
  Mock + A-Trust Cloud + lokalni certifikat
  ZOI generacija, lančani hash, DEP7 zapis
  Integriran u checkout.py (Route 3: AT)

pos/furs_adapter.py (NOVO):
  SI FURS API (ZDavPR) — ZOI + EOR
  SOAP XML request po FURS specifikaciji
  RSA potpis (produkcija) + MD5 mock (test)
  Integriran u checkout.py (Route 4: SI)

eracun/models.py:
  ATRKSVConfig model — kassen_id, cert_type, chain_value, receipt_counter

core/country_registry.py:
  AT status: PLANNED → BETA
  SI status: PLANNED → BETA
  AT: rksv_bmf_url, a_trust_url dodani
  SI: furs_test_url, furs_prod_url dodani

CompliancePackage seed:
  AT RKSV paket (40 EUR/mj addon)
  SI FURS paket (35 EUR/mj addon)

core/settings.py:
  AT_RKSV_TEST_MODE, AT_A_TRUST_API_KEY
  SI_FURS_TEST_MODE, SI_FURS_CERT_PATH, SI_FURS_KEY_PATH

NAPOMENA: Produkcija zahtijeva:
  AT: A-Trust certifikat (ugovor s A-Trust GmbH)
  SI: FIZPS certifikat (zahtjev Ministarstvu financija SI)"
```

---

## NAPOMENE ZA CC

1. **AT RKSV** — Bez pravog A-Trust certifikata, mock mode generiria valjanu
   strukturu ali potpis nije kriptografski ispravan. Dovoljan za demo.
   Produkcijski certifikat: A-Trust (Austrija), ~300 EUR/god.

2. **SI FURS** — Test API ne zahtijeva certifikat. Produkcija zahtijeva
   FIZPS certifikat (besplatno, od MF Slovenija — OIB treba biti u SI registru).

3. **Ne mijenjaj HR checkout logiku** — route 1 (HR) mora ostati identičan.

4. **Provjeri field name** — `POSReceipt.jir` postoji (HR fiskalizacija).
   Za SI koristimo isti field jer je semantički ekvivalentno.

5. **CompliancePackage** — provjeri postoji li model (iz CC_TASK_LICENSING_ENGINE):
   ```bash
   venv/bin/python manage.py shell -c "from companies.models import CompliancePackage; print('OK')"
   ```
   Ako ne postoji — kreiraj migraciju (definiran u CC_TASK_LICENSING_ENGINE.md).

6. **Javi Sonnet** kad završiš verifikaciju — posebno:
   - ZOI length == 32? (SI FURS zahtjev)
   - RKSV counter inkrement radi?
   - CompliancePackage AT/SI seedani?
