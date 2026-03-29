"""
3 Kriptografska Drona:
1. EU DSS disclaimer na BORG Validator (lisica/kokošinjac)  
2. TSA timestamp integracija (XAdES-T)
3. Javne XSD sheme za nove standarde
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# DRON #1: EU DSS Disclaimer + link na validator
# ══════════════════════════════════════════════════════════════════════

val_path = os.path.join(BASE, 'templates/gov_export/validator.html')
with open(val_path) as f:
    c = f.read()

if 'EU DSS' not in c:
    old_footer = '<div class="footer">'
    new_footer = """<div class="card" style="border-color:rgba(201,168,76,.2)">
  <div style="display:flex;gap:1rem;align-items:start">
    <i class="fas fa-balance-scale" style="color:#c9a84c;font-size:1.5rem;flex-shrink:0;margin-top:2px"></i>
    <div>
      <h4 style="color:#c9a84c;font-size:.9rem;margin-bottom:.5rem">Neovisna verifikacija</h4>
      <p style="font-size:.8rem;color:#94a3b8;line-height:1.5;margin-bottom:.75rem">
        Ovaj XML je usklađen s <strong>EU eIDAS</strong> standardom (Uredba 910/2014). 
        XAdES potpis možete <strong>neovisno verificirati</strong> putem službenih alata:
      </p>
      <div style="display:flex;gap:.75rem;flex-wrap:wrap">
        <a href="https://ec.europa.eu/digital-building-blocks/DSS/webapp-demo/validation" target="_blank" rel="noopener"
           style="display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .8rem;background:#1e293b;border:1px solid #334155;border-radius:6px;color:#60a5fa;font-size:.78rem;text-decoration:none;font-weight:600">
          <i class="fas fa-external-link-alt"></i> EU DSS Validator (Europska komisija)
        </a>
        <a href="https://www.fina.hr/finadigicert" target="_blank" rel="noopener"
           style="display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .8rem;background:#1e293b;border:1px solid #334155;border-radius:6px;color:#60a5fa;font-size:.78rem;text-decoration:none;font-weight:600">
          <i class="fas fa-external-link-alt"></i> FINA DigiCert
        </a>
      </div>
      <p style="font-size:.72rem;color:#475569;margin-top:.75rem">
        LIMIT Connect BORG Validator je pomoćni alat. Za pravno obvezujuću verifikaciju 
        koristite službeni EU DSS Validator ili kvalificiranog pružatelja usluga povjerenja.
      </p>
    </div>
  </div>
</div>

<div class="footer">"""
    c = c.replace(old_footer, new_footer)
    with open(val_path, 'w') as f:
        f.write(c)
    print("[OK] Validator — EU DSS disclaimer + neovisni linkovi")


# ══════════════════════════════════════════════════════════════════════
# DRON #2: TSA Timestamp (XAdES-T) — modul za vremenski žig
# ══════════════════════════════════════════════════════════════════════

tsa_code = '''"""
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
        sha256_oid = b'\\x30\\x0d\\x06\\x09\\x60\\x86\\x48\\x01\\x65\\x03\\x04\\x02\\x01\\x05\\x00'
        hash_octet = b'\\x04\\x20' + digest
        msg_imprint_seq = b'\\x30' + bytes([len(sha256_oid) + len(hash_octet)]) + sha256_oid + hash_octet
        version = b'\\x02\\x01\\x01'  # INTEGER 1
        cert_req = b'\\x01\\x01\\xff'  # BOOLEAN true
        inner = version + msg_imprint_seq + cert_req
        req_der = b'\\x30' + bytes([len(inner)]) + inner

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
'''

with open(os.path.join(BASE, 'gov_export/tsa.py'), 'w') as f:
    f.write(tsa_code)
print("[OK] gov_export/tsa.py — TSA modul (XAdES-T)")

# Integriraj TSA u pipeline
pipeline_path = os.path.join(BASE, 'gov_export/pipeline.py')
with open(pipeline_path) as f:
    pc = f.read()

if 'tsa' not in pc:
    # Dodaj TSA step nakon Sign
    old_send = "    # ── STEP 4: Send ──"
    new_tsa = """    # ── STEP 3b: Timestamp (XAdES-T) ──
    t0 = time.time()
    if export.is_signed:
        try:
            from .tsa import get_timestamp_token, embed_timestamp_in_xades
            xml_bytes = export.xml_content.encode('utf-8') if isinstance(export.xml_content, str) else export.xml_content
            ts_token = get_timestamp_token(xml_bytes)
            if ts_token:
                export.xml_content = embed_timestamp_in_xades(export.xml_content, ts_token)
                export.signature_method = 'XAdES-T'  # Upgrade od BES na T
                export.save(update_fields=['xml_content', 'signature_method'])
                results['timestamp'] = 'ok'
                GovExportLog.objects.create(
                    export=export, step='timestamp', status='ok',
                    message=f'TSA token: {len(ts_token)} bytes — XAdES-BES → XAdES-T',
                    duration_ms=int((time.time() - t0) * 1000), actor=user,
                )
            else:
                results['timestamp'] = 'skip: TSA unavailable'
                GovExportLog.objects.create(
                    export=export, step='timestamp', status='skip',
                    message='TSA server nedostupan — ostaje XAdES-BES',
                    duration_ms=int((time.time() - t0) * 1000), actor=user,
                )
        except Exception as e:
            results['timestamp'] = f'error: {e}'
            GovExportLog.objects.create(
                export=export, step='timestamp', status='error',
                message=str(e)[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
            )
    else:
        results['timestamp'] = 'skip: not signed'

    # ── STEP 4: Send ──"""
    
    pc = pc.replace(old_send, new_tsa)
    with open(pipeline_path, 'w') as f:
        f.write(pc)
    print("[OK] pipeline.py — TSA step dodan (Generate→Validate→Sign→Timestamp→Send)")


# ══════════════════════════════════════════════════════════════════════
# DRON #3: Javne XSD Sheme
# ══════════════════════════════════════════════════════════════════════

schema_dir = os.path.join(BASE, 'static/schemas')
os.makedirs(schema_dir, exist_ok=True)

# AgroHealth XSD
agro_xsd = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:ah="urn:limit-connect:agro-health:v1.0"
           targetNamespace="urn:limit-connect:agro-health:v1.0"
           elementFormDefault="qualified">

  <xs:element name="AgroHealthReport">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Issuer" type="ah:IssuerType"/>
        <xs:element name="Period" type="ah:PeriodType"/>
        <xs:element name="Flocks" type="ah:FlocksType"/>
      </xs:sequence>
      <xs:attribute name="version" type="xs:string" use="required"/>
      <xs:attribute name="generated" type="xs:dateTime" use="required"/>
    </xs:complexType>
  </xs:element>

  <xs:complexType name="IssuerType">
    <xs:sequence>
      <xs:element name="Name" type="xs:string"/>
      <xs:element name="OIB" type="xs:string"/>
      <xs:element name="Address" type="xs:string" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="PeriodType">
    <xs:sequence>
      <xs:element name="From" type="xs:date"/>
      <xs:element name="To" type="xs:date"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="FlocksType">
    <xs:sequence>
      <xs:element name="Flock" type="ah:FlockType" minOccurs="0" maxOccurs="unbounded"/>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

  <xs:complexType name="FlockType">
    <xs:sequence>
      <xs:element name="Name" type="xs:string"/>
      <xs:element name="Species" type="xs:string"/>
      <xs:element name="Breed" type="xs:string" minOccurs="0"/>
      <xs:element name="HeadCount" type="xs:integer"/>
      <xs:element name="ActiveCount" type="xs:integer"/>
      <xs:element name="AcquiredDate" type="xs:string" minOccurs="0"/>
      <xs:element name="FarmingType" type="xs:string" minOccurs="0"/>
      <xs:element name="Location" type="xs:string" minOccurs="0"/>
      <xs:element name="HasActiveWithdrawal" type="xs:boolean"/>
      <xs:element name="WithdrawalEndDate" type="xs:date" minOccurs="0"/>
      <xs:element name="HealthRecords" type="ah:HealthRecordsType" minOccurs="0"/>
      <xs:element name="MortalityRecords" type="ah:MortalityRecordsType" minOccurs="0"/>
      <xs:element name="EggProduction" type="ah:EggProductionType" minOccurs="0"/>
    </xs:sequence>
    <xs:attribute name="id" type="xs:string"/>
  </xs:complexType>

  <xs:complexType name="HealthRecordsType">
    <xs:sequence>
      <xs:element name="Record" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Type" type="xs:string"/>
            <xs:element name="Date" type="xs:date"/>
            <xs:element name="Medicine" type="xs:string" minOccurs="0"/>
            <xs:element name="Dosage" type="xs:string" minOccurs="0"/>
            <xs:element name="Veterinarian" type="xs:string" minOccurs="0"/>
            <xs:element name="WithdrawalDays" type="xs:integer" minOccurs="0"/>
            <xs:element name="WithdrawalActive" type="xs:boolean" minOccurs="0"/>
          </xs:sequence>
          <xs:attribute name="id" type="xs:string"/>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

  <xs:complexType name="MortalityRecordsType">
    <xs:sequence>
      <xs:element name="Record" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Date" type="xs:date"/>
            <xs:element name="Count" type="xs:integer"/>
            <xs:element name="Reason" type="xs:string" minOccurs="0"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

  <xs:complexType name="EggProductionType">
    <xs:sequence>
      <xs:element name="TotalEggs" type="xs:integer"/>
      <xs:element name="TotalBroken" type="xs:integer"/>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

</xs:schema>
'''

with open(os.path.join(schema_dir, 'agro-health-v1.0.xsd'), 'w') as f:
    f.write(agro_xsd)
print("[OK] static/schemas/agro-health-v1.0.xsd")

# Tourist Registration XSD
tourist_xsd = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:tr="urn:limit-connect:tourist-registration:v1.0"
           targetNamespace="urn:limit-connect:tourist-registration:v1.0"
           elementFormDefault="qualified">

  <xs:element name="TouristRegistration">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Issuer" type="tr:IssuerType"/>
        <xs:element name="Period" type="tr:PeriodType"/>
        <xs:element name="Guests" type="tr:GuestsType"/>
        <xs:element name="ExperienceGuests" type="tr:ExperienceGuestsType" minOccurs="0"/>
      </xs:sequence>
      <xs:attribute name="version" type="xs:string" use="required"/>
      <xs:attribute name="generated" type="xs:dateTime" use="required"/>
    </xs:complexType>
  </xs:element>

  <xs:complexType name="IssuerType">
    <xs:sequence>
      <xs:element name="Name" type="xs:string"/>
      <xs:element name="OIB" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="PeriodType">
    <xs:sequence>
      <xs:element name="From" type="xs:date"/>
      <xs:element name="To" type="xs:date"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="GuestsType">
    <xs:sequence>
      <xs:element name="Guest" minOccurs="0" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="BookingNumber" type="xs:string"/>
            <xs:element name="GuestName" type="xs:string"/>
            <xs:element name="GuestCount" type="xs:integer"/>
            <xs:element name="CheckIn" type="xs:date"/>
            <xs:element name="CheckOut" type="xs:date"/>
            <xs:element name="Status" type="xs:string"/>
            <xs:element name="ActualCheckIn" type="xs:dateTime" minOccurs="0"/>
            <xs:element name="LocalZKI" type="xs:string"/>
            <xs:element name="TrafficRecord" minOccurs="0" maxOccurs="unbounded">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="GuestName" type="xs:string"/>
                  <xs:element name="Nationality" type="xs:string" minOccurs="0"/>
                  <xs:element name="DocumentNumber" type="xs:string" minOccurs="0"/>
                  <xs:element name="EVisitorSynced" type="xs:boolean"/>
                  <xs:element name="EVisitorSyncedAt" type="xs:dateTime" minOccurs="0"/>
                </xs:sequence>
                <xs:attribute name="id" type="xs:string"/>
              </xs:complexType>
            </xs:element>
          </xs:sequence>
          <xs:attribute name="id" type="xs:string"/>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

  <xs:complexType name="ExperienceGuestsType">
    <xs:sequence>
      <xs:element name="Guest" minOccurs="0" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Name" type="xs:string"/>
            <xs:element name="Country" type="xs:string" minOccurs="0"/>
            <xs:element name="PaxCount" type="xs:integer"/>
            <xs:element name="Experience" type="xs:string"/>
            <xs:element name="Date" type="xs:date"/>
          </xs:sequence>
          <xs:attribute name="id" type="xs:string"/>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

</xs:schema>
'''

with open(os.path.join(schema_dir, 'tourist-registration-v1.0.xsd'), 'w') as f:
    f.write(tourist_xsd)
print("[OK] static/schemas/tourist-registration-v1.0.xsd")

# Inventory Ledger XSD (skraćen ali funkcionalan)
inv_xsd = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:il="urn:limit-connect:inventory-ledger:v1.0"
           targetNamespace="urn:limit-connect:inventory-ledger:v1.0"
           elementFormDefault="qualified">

  <xs:element name="InventoryLedger">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Issuer" type="il:IssuerType"/>
        <xs:element name="Period" type="il:PeriodType"/>
        <xs:element name="Items" type="il:ItemsType"/>
        <xs:element name="Movements" type="il:MovementsType"/>
        <xs:element name="Summary" type="il:SummaryType"/>
      </xs:sequence>
      <xs:attribute name="version" type="xs:string" use="required"/>
      <xs:attribute name="generated" type="xs:dateTime" use="required"/>
    </xs:complexType>
  </xs:element>

  <xs:complexType name="IssuerType">
    <xs:sequence>
      <xs:element name="Name" type="xs:string"/>
      <xs:element name="OIB" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="PeriodType">
    <xs:sequence>
      <xs:element name="From" type="xs:date"/>
      <xs:element name="To" type="xs:date"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="ItemsType">
    <xs:sequence>
      <xs:element name="Item" minOccurs="0" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="SKU" type="xs:string"/>
            <xs:element name="Name" type="xs:string"/>
            <xs:element name="Unit" type="xs:string"/>
            <xs:element name="Quantity" type="xs:decimal"/>
            <xs:element name="UnitPrice" type="xs:decimal"/>
            <xs:element name="PurchasePrice" type="xs:decimal"/>
            <xs:element name="TotalValue" type="xs:decimal"/>
            <xs:element name="Allocation" minOccurs="0">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="ReservedInhouse" type="xs:decimal"/>
                  <xs:element name="ReservedMarketplace" type="xs:decimal"/>
                  <xs:element name="BufferPct" type="xs:integer"/>
                </xs:sequence>
              </xs:complexType>
            </xs:element>
            <xs:element name="SourceFlock" minOccurs="0">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="Name" type="xs:string"/>
                  <xs:element name="ActiveWithdrawal" type="xs:boolean"/>
                </xs:sequence>
                <xs:attribute name="id" type="xs:string"/>
              </xs:complexType>
            </xs:element>
            <xs:element name="Batches" minOccurs="0">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="Batch" maxOccurs="unbounded">
                    <xs:complexType>
                      <xs:sequence>
                        <xs:element name="LOT" type="xs:string"/>
                        <xs:element name="Quantity" type="xs:decimal"/>
                        <xs:element name="ExpiryDate" type="xs:date" minOccurs="0"/>
                      </xs:sequence>
                    </xs:complexType>
                  </xs:element>
                </xs:sequence>
                <xs:attribute name="count" type="xs:integer"/>
              </xs:complexType>
            </xs:element>
          </xs:sequence>
          <xs:attribute name="id" type="xs:string"/>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

  <xs:complexType name="MovementsType">
    <xs:sequence>
      <xs:element name="Movement" minOccurs="0" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Item" type="xs:string"/>
            <xs:element name="Type" type="xs:string"/>
            <xs:element name="Quantity" type="xs:decimal"/>
            <xs:element name="UnitPrice" type="xs:decimal"/>
            <xs:element name="Reason" type="xs:string" minOccurs="0"/>
            <xs:element name="Timestamp" type="xs:dateTime"/>
          </xs:sequence>
          <xs:attribute name="id" type="xs:string"/>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="count" type="xs:integer"/>
  </xs:complexType>

  <xs:complexType name="SummaryType">
    <xs:sequence>
      <xs:element name="TotalItems" type="xs:integer"/>
      <xs:element name="TotalValue" type="xs:decimal"/>
      <xs:element name="TotalMovements" type="xs:integer"/>
      <xs:element name="Currency" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

</xs:schema>
'''

with open(os.path.join(schema_dir, 'inventory-ledger-v1.0.xsd'), 'w') as f:
    f.write(inv_xsd)
print("[OK] static/schemas/inventory-ledger-v1.0.xsd")


# Schema index page
index_html = '''<!DOCTYPE html>
<html lang="hr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LIMIT Connect — Javne XML Sheme</title>
<style>body{font-family:system-ui;background:#0a0a0a;color:#e2e8f0;padding:2rem;max-width:800px;margin:0 auto}
a{color:#c9a84c}h1{color:#c9a84c}table{width:100%;border-collapse:collapse;margin:1rem 0}
th,td{text-align:left;padding:.75rem;border-bottom:1px solid #1e293b}th{color:#94a3b8;font-size:.8rem;text-transform:uppercase}</style>
</head><body>
<h1>LIMIT Connect — Javne XML Sheme</h1>
<p style="color:#94a3b8">Sheme za neovisnu verifikaciju GovExport dokumenata. Slobodno za preuzimanje i implementaciju.</p>
<table>
<tr><th>Standard</th><th>Namespace</th><th>XSD</th></tr>
<tr><td>Agro-Fiskalizacija v1.0</td><td><code>urn:limit-connect:agro-health:v1.0</code></td><td><a href="agro-health-v1.0.xsd">agro-health-v1.0.xsd</a></td></tr>
<tr><td>Turistički ZKI v1.0</td><td><code>urn:limit-connect:tourist-registration:v1.0</code></td><td><a href="tourist-registration-v1.0.xsd">tourist-registration-v1.0.xsd</a></td></tr>
<tr><td>Forenzika Zaliha v1.0</td><td><code>urn:limit-connect:inventory-ledger:v1.0</code></td><td><a href="inventory-ledger-v1.0.xsd">inventory-ledger-v1.0.xsd</a></td></tr>
</table>
<p style="color:#475569;font-size:.8rem;margin-top:2rem">
Licence: MIT. Slobodno koristite za vlastite implementacije.<br>
Verifikacija potpisa: <a href="https://ec.europa.eu/digital-building-blocks/DSS/webapp-demo/validation">EU DSS Validator</a><br>
&copy; 2026 LIMIT Connect | <a href="https://limit-connect.com">limit-connect.com</a>
</p></body></html>
'''

with open(os.path.join(schema_dir, 'index.html'), 'w') as f:
    f.write(index_html)
print("[OK] static/schemas/index.html — javna schema stranica")


print("\\n═══════════════════════════════════════════")
print("3 KRIPTOGRAFSKA DRONA NEUTRALIZIRANA")
print("  1. EU DSS disclaimer + neovisni linkovi")
print("  2. TSA modul (XAdES-T) u pipeline")
print("  3. 3 javne XSD sheme + index stranica")
print("═══════════════════════════════════════════")
