"""
core/dok_package.py — .dok format generator

.dok je ZIP arhiva s MPEG-7 kompatibilnim XML manifestom.
Struktura:
    manifest.xml   — MPEG-7 opis sadržaja + eArhivator namespace
    master/        — originalni dokumenti (neizmijenjeni)
    schema.xsd     — embedana kopija sheme (čitljivo za 100 godina)
    readme.txt     — HR + EN + DE objašnjenje

Filozofija: self-describing format.
Otvori ga za 100 godina bez interneta i znat ćeš što je i što znači.
"""

import hashlib
import io
import zipfile
from datetime import datetime, timezone

DOK_VERSION = "1.0"
DOK_NS = "https://earhivator.hr/ns/dok/1.0"
EARHIVATOR_NS = "https://fenix.limit-connect.com/ns/earhivator/1.0"


# ─────────────────────────────────────────────────────────────────────────────
# XSD SHEMA (embedana — ne URL, nego sadržaj)
# ─────────────────────────────────────────────────────────────────────────────
EMBEDDED_SCHEMA_XSD = """\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="https://earhivator.hr/ns/dok/1.0"
           xmlns:dok="https://earhivator.hr/ns/dok/1.0"
           elementFormDefault="qualified"
           version="1.0">

  <xs:element name="DokManifest">
    <xs:complexType>
      <xs:all>
        <xs:element name="Header"     type="dok:HeaderType"/>
        <xs:element name="Issuer"     type="dok:IssuerType"/>
        <xs:element name="ChainBlock" type="dok:ChainBlockType"/>
        <xs:element name="Documents"  type="dok:DocumentsType"/>
        <xs:element name="Integrity"  type="dok:IntegrityType"/>
        <xs:element name="Legal"      type="dok:LegalType"/>
      </xs:all>
    </xs:complexType>
  </xs:element>

  <xs:complexType name="HeaderType">
    <xs:sequence>
      <xs:element name="FormatVersion"  type="xs:string"/>
      <xs:element name="FormatName"     type="xs:string"/>
      <xs:element name="Created"        type="xs:dateTime"/>
      <xs:element name="Generator"      type="xs:string"/>
      <xs:element name="SealToken"      type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="IssuerType">
    <xs:sequence>
      <xs:element name="Name"  type="xs:string"/>
      <xs:element name="OIB"   type="xs:string"/>
      <xs:element name="Role"  type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="ChainBlockType">
    <xs:sequence>
      <xs:element name="BlockNumber" type="xs:integer"/>
      <xs:element name="PrevHash"    type="xs:string"/>
      <xs:element name="BlockHash"   type="xs:string"/>
      <xs:element name="Timestamp"   type="xs:dateTime"/>
      <xs:element name="Title"       type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="DocumentsType">
    <xs:sequence>
      <xs:element name="Document" type="dok:DocumentType"
                  minOccurs="1" maxOccurs="unbounded"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="DocumentType">
    <xs:sequence>
      <xs:element name="FileName"  type="xs:string"/>
      <xs:element name="MimeType"  type="xs:string"/>
      <xs:element name="SHA256"    type="xs:string"/>
      <xs:element name="SizeBytes" type="xs:integer"/>
      <xs:element name="Path"      type="xs:string"/>
    </xs:sequence>
    <xs:attribute name="index" type="xs:integer" use="required"/>
  </xs:complexType>

  <xs:complexType name="IntegrityType">
    <xs:sequence>
      <xs:element name="PakageHash"      type="xs:string"/>
      <xs:element name="HashAlgorithm"   type="xs:string"/>
      <xs:element name="VerifyURL"       type="xs:anyURI"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="LegalType">
    <xs:sequence>
      <xs:element name="Basis"    type="xs:string"/>
      <xs:element name="Country"  type="xs:string"/>
      <xs:element name="Language" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

</xs:schema>
"""


# ─────────────────────────────────────────────────────────────────────────────
# README (HR + EN + DE)
# ─────────────────────────────────────────────────────────────────────────────
README_CONTENT = """\
================================================================
eArhivator .dok paket — Digitalni dokaz postojanja
================================================================

HR — HRVATSKI
-------------
Ova .dok datoteka je kriptografski zapečaćen paket dokumenata.
Sadrži originalne dokumente (u mapi master/) i XML manifest
koji opisuje sadržaj, hasheve i lanac integriteta.

Verifikacija: Otvorite verify_url iz manifest.xml u web pregledniku.
Format: ZIP arhiva. Otvorite bilo kojim ZIP programom.
Shema: schema.xsd opisuje strukturu manifest.xml-a.

Pravna osnova: eIDAS Art. 41 (HR: ZED NN 150/05)
Integritet: SHA-256 — ako se ijedan bit promijeni, hash ne odgovara.

================================================================

EN — ENGLISH
------------
This .dok file is a cryptographically sealed document package.
It contains original documents (in the master/ folder) and an
XML manifest describing the content, hashes, and integrity chain.

Verification: Open the verify_url from manifest.xml in a browser.
Format: ZIP archive. Open with any ZIP tool.
Schema: schema.xsd describes the structure of manifest.xml.

Legal basis: eIDAS Art. 41
Integrity: SHA-256 — if a single bit changes, the hash fails.

================================================================

DE — DEUTSCH
------------
Diese .dok-Datei ist ein kryptografisch versiegeltes Dokumentenpaket.
Es enthält Originaldokumente (im Ordner master/) und ein XML-Manifest,
das Inhalt, Hashes und die Integritätskette beschreibt.

Verifizierung: Öffnen Sie die verify_url aus manifest.xml im Browser.
Format: ZIP-Archiv. Mit jedem ZIP-Programm öffnen.
Schema: schema.xsd beschreibt die Struktur von manifest.xml.

Rechtsgrundlage: eIDAS Art. 41
Integrität: SHA-256 — ändert sich ein Bit, schlägt der Hash fehl.

================================================================
Generator: eArhivator v1.0 — https://earhivator.hr
"""


# ─────────────────────────────────────────────────────────────────────────────
# MANIFEST XML GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def build_manifest_xml(
    seal_token: str,
    issuer_name: str,
    issuer_oib: str,
    block_number: int,
    prev_hash: str,
    block_hash: str,
    timestamp: datetime,
    title: str,
    documents: list[dict],  # [{name, hash, size, mime, path}]
    package_hash: str,
    verify_base_url: str = "https://evalidator.hr",
) -> str:
    """Gradi MPEG-7 kompatibilan XML manifest za .dok paket."""
    from xml.dom import minidom
    from xml.etree import ElementTree as ET

    root = ET.Element(
        "DokManifest",
        attrib={
            "xmlns": DOK_NS,
            "xmlns:ear": EARHIVATOR_NS,
            "version": DOK_VERSION,
            "formatName": "eArhivator DOK",
        },
    )

    # Header
    hdr = ET.SubElement(root, "Header")
    ET.SubElement(hdr, "FormatVersion").text = DOK_VERSION
    ET.SubElement(hdr, "FormatName").text = "eArhivator DOK — Digitalni dokaz postojanja"
    ET.SubElement(hdr, "Created").text = datetime.now(timezone.utc).isoformat()
    ET.SubElement(hdr, "Generator").text = "eArhivator v1.0 (fenix.limit-connect.com)"
    ET.SubElement(hdr, "SealToken").text = seal_token

    # Issuer
    iss = ET.SubElement(root, "Issuer")
    ET.SubElement(iss, "Name").text = issuer_name
    ET.SubElement(iss, "OIB").text = issuer_oib
    ET.SubElement(iss, "Role").text = "Nosač intelektualnog vlasništva / IP Owner"

    # ChainBlock
    cb = ET.SubElement(root, "ChainBlock")
    ET.SubElement(cb, "BlockNumber").text = str(block_number)
    ET.SubElement(cb, "PrevHash").text = prev_hash
    ET.SubElement(cb, "BlockHash").text = block_hash
    ET.SubElement(cb, "Timestamp").text = timestamp.isoformat()
    ET.SubElement(cb, "Title").text = title
    if block_number == 0:
        ET.SubElement(cb, "IsGenesis").text = "true"

    # Documents
    docs_el = ET.SubElement(root, "Documents")
    for i, doc in enumerate(documents):
        d = ET.SubElement(docs_el, "Document", attrib={"index": str(i)})
        ET.SubElement(d, "FileName").text = doc["name"]
        ET.SubElement(d, "MimeType").text = doc.get("mime", "application/octet-stream")
        ET.SubElement(d, "SHA256").text = doc["hash"]
        ET.SubElement(d, "SizeBytes").text = str(doc.get("size", 0))
        ET.SubElement(d, "Path").text = f"master/{doc['name']}"

    # Integrity
    integ = ET.SubElement(root, "Integrity")
    ET.SubElement(integ, "PakageHash").text = package_hash
    ET.SubElement(integ, "HashAlgorithm").text = "sha256"
    ET.SubElement(integ, "VerifyURL").text = f"{verify_base_url}/verify/{seal_token}/"

    # Legal
    legal = ET.SubElement(root, "Legal")
    ET.SubElement(legal, "Basis").text = "eIDAS Art. 41 | ZED HR NN 150/05 | GDPR Art. 6(1)(b)"
    ET.SubElement(legal, "Country").text = "HR"
    ET.SubElement(legal, "Language").text = "hr,en,de"

    # Pretty print
    raw = ET.tostring(root, encoding="unicode", xml_declaration=False)
    dom = minidom.parseString(f'<?xml version="1.0" encoding="UTF-8"?>{raw}')
    return dom.toprettyxml(indent="  ", encoding=None).replace(
        '<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8"?>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# .DOK PAKET GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def create_dok_package(
    seal_token: str,
    issuer_name: str,
    issuer_oib: str,
    block_number: int,
    prev_hash: str,
    block_hash: str,
    timestamp: datetime,
    title: str,
    files: list[dict],  # [{name, content: bytes, mime}]
    verify_base_url: str = "https://evalidator.hr",
) -> tuple[bytes, str, list[dict]]:
    """
    Kreira .dok paket (ZIP bytes).

    Returns:
        (zip_bytes, package_hash, documents_meta)
        documents_meta = [{name, hash, size, mime}] za ChainBlockPOE.documents_json
    """
    buf = io.BytesIO()
    documents_meta = []

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. master/ — originalni dokumenti
        for f in files:
            content = f["content"]
            name = f["name"]
            mime = f.get("mime", "application/octet-stream")
            sha256 = hashlib.sha256(content).hexdigest()
            zf.writestr(f"master/{name}", content)
            documents_meta.append(
                {
                    "name": name,
                    "hash": sha256,
                    "size": len(content),
                    "mime": mime,
                    "path": f"master/{name}",
                }
            )

        # 2. manifest.xml
        manifest = build_manifest_xml(
            seal_token=seal_token,
            issuer_name=issuer_name,
            issuer_oib=issuer_oib,
            block_number=block_number,
            prev_hash=prev_hash,
            block_hash=block_hash,
            timestamp=timestamp,
            title=title,
            documents=documents_meta,
            package_hash="COMPUTING",  # placeholder, replace below
            verify_base_url=verify_base_url,
        )
        zf.writestr("manifest.xml", manifest.encode("utf-8"))

        # 3. schema.xsd — embedana shema
        zf.writestr("schema.xsd", EMBEDDED_SCHEMA_XSD.encode("utf-8"))

        # 4. readme.txt
        zf.writestr("readme.txt", README_CONTENT.encode("utf-8"))

    zip_bytes = buf.getvalue()

    # Package hash — SHA-256 cijelog ZIP-a
    package_hash = hashlib.sha256(zip_bytes).hexdigest()

    # Regeneriraj manifest s pravim package_hash
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, mode="w", compression=zipfile.ZIP_DEFLATED) as zf2:
        for f in files:
            zf2.writestr(f"master/{f['name']}", f["content"])
        manifest_final = build_manifest_xml(
            seal_token=seal_token,
            issuer_name=issuer_name,
            issuer_oib=issuer_oib,
            block_number=block_number,
            prev_hash=prev_hash,
            block_hash=block_hash,
            timestamp=timestamp,
            title=title,
            documents=documents_meta,
            package_hash=package_hash,
            verify_base_url=verify_base_url,
        )
        zf2.writestr("manifest.xml", manifest_final.encode("utf-8"))
        zf2.writestr("schema.xsd", EMBEDDED_SCHEMA_XSD.encode("utf-8"))
        zf2.writestr("readme.txt", README_CONTENT.encode("utf-8"))

    final_bytes = buf2.getvalue()
    final_hash = hashlib.sha256(final_bytes).hexdigest()

    return final_bytes, final_hash, documents_meta
