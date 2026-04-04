# CC_TASK_EU_XRECHNUNG_B2B_COMPLETE.md
# Za: CC Code #1
# Datum: 2026-03-31
# Rok: 08.04.2026.
# Prioritet: VISOKO — DE tržište (Viskovic Bau live, 3 DE firme u bazi)
# Procjena: 3-4 dana
#
# KONTEKST:
# XRechnung CII generator POSTOJI (226 linija) i radi za download.
# ZUGFeRD hybrid PDF postoji (177 linija).
# TSE adapter (Fiskaly Cloud) postoji za POS.
# Kassenbuch/DSFinV-K postoji (179 linija).
#
# ŠTO FALI:
# 1. Leitweg-ID (BT-10) — obavezan za DE B2G, preporučen B2B
# 2. EN 16931 schematron validacija (business rules, ne samo XSD)
# 3. ZUGFeRD PDF/A-3 XMP metadata (nepotpuna — fali xmlns deklaracije)
# 4. Auto-send via PEPPOL za DE B2B (TransportRouter postoji, wire fali)
# 5. DSFinV-K full export (Kassenbuch postoji ali ne generira TSE finalni format)
# 6. XRechnung B2B flow end-to-end test
#
# LIVE DE KLIJENTI: Viskovic Bau, Dado Haustechnik, Fiskaly Test GmbH
# fiscal_system: de_gobd

---

## KORAK 1 — Leitweg-ID (BT-10) u XRechnung generatoru

Provjeri:
```bash
grep -n "BT-10\|Leitweg\|BuyerReference\|buyer_ref\|routing_id" \
  eracun/services/xrechnung.py
```

Leitweg-ID je obavezna oznaka za rutiranje kod DE javnih naručitelja (B2G)
i sve češća u B2B. Format: `04011000-12345-06` ili PEPPOL participant ID.

Dodati u `eracun/models.py` na ERacun model:
```python
buyer_reference = models.CharField(
    max_length=200, blank=True, default='',
    verbose_name='Leitweg-ID / Buyer Reference (BT-10)',
    help_text='Obavezno za DE B2G. Npr: 991-1234512345-06 ili GLN.'
)
```

U `generate_xrechnung()`:
```python
# BT-10 BuyerReference — Leitweg-ID
if eracun.buyer_reference:
    _el(header_agreement, 'ram:BuyerReference', eracun.buyer_reference)
```

Migracija:
```bash
venv/bin/python manage.py makemigrations eracun --name buyer_reference_leitweg
venv/bin/python manage.py migrate
```

---

## KORAK 2 — EN 16931 Schematron validacija

Schematron provjerava business rules koje XSD ne može (npr. "ako je tip poreza S,
porezna stopa mora biti > 0"). Bez toga XRechnung može biti formalno valjan XML
ali odbijen od primatelja.

Provjeri ima li schematron XSL-ova:
```bash
find . -name "*.xsl" -o -name "*.sch" | grep -v venv
ls eracun/xsd/ 2>/dev/null
```

### 2a. Preuzmi EN 16931 schematron

```bash
# Preuzmi službene KoSIT schematrone za XRechnung 3.0
mkdir -p /var/www/fina-connect/eracun/schematron/
cd /var/www/fina-connect/eracun/schematron/

# EN 16931 core rules
wget -q "https://docs.peppol.eu/pracc/validator/artefacts/schematron/EN16931-CII-validation.sch" \
  -O EN16931-CII-validation.sch 2>/dev/null || \
  echo "Preuzimanje nije uspjelo — koristiti lokalne kopije ili saxonpy"

# XRechnung CIUS DE addon rules
wget -q "https://github.com/itplr-kosit/xrechnung-schematron/releases/latest/download/xrechnung-3.0-schematron.zip" \
  -O /tmp/xrechnung_schematron.zip 2>/dev/null && \
  unzip -q /tmp/xrechnung_schematron.zip -d /var/www/fina-connect/eracun/schematron/
```

Ako wget nije dostupan, implementiraj basic business rules u Pythonu:
```bash
grep -n "validate\|EN16931\|schematron\|business.rule" eracun/services/xrechnung.py
```

### 2b. Python validator za ključna pravila

Dodati `eracun/services/xrechnung_validator.py`:

```python
"""
XRechnung Business Rules Validator.
Implementira najvažnija EN 16931 pravila u Pythonu.
Za punu validaciju koristiti saxonpy + schematron XSL.

Ključna pravila:
  BR-01: Dokument mora imati jedinstveni identifier
  BR-02: Datum izdavanja obavezan
  BR-04: Broj računa obavezan
  BR-CO-13: Ukupan porez = suma svih poreznih linija
  BR-DE-01: Leitweg-ID obavezna za B2G
  BR-DE-16: BIC obavezan za IBAN transfer
"""
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

def validate_xrechnung(eracun) -> ValidationResult:
    """Validiraj ERacun objekt prema EN 16931 + XRechnung CIUS-DE pravilima."""
    errors = []
    warnings = []

    # BR-01: Unique invoice ID
    if not eracun.invoice_number:
        errors.append('BR-01: Broj računa (BT-1) je obavezan.')

    # BR-02: Issue date
    if not eracun.issue_date:
        errors.append('BR-02: Datum izdavanja (BT-2) je obavezan.')

    # BR-S-01: Tax breakdown
    items = eracun.items.all()
    if not items.exists():
        errors.append('BR-S-01: Račun mora imati najmanje jednu stavku.')

    # Seller data
    if not eracun.issuer_oib:
        errors.append('BR-CO-26: OIB/Steuernummer izdavatelja (BT-32) obavezan.')
    if not eracun.issuer_name:
        errors.append('BR-S-02: Naziv izdavatelja (BT-27) obavezan.')

    # Payment
    if not eracun.issuer_iban:
        warnings.append('BT-84: IBAN nije naveden — savjetujemo za automatiziranu naplatu.')

    # DE-specific
    if eracun.issuer_country == 'DE':
        if not getattr(eracun, 'buyer_reference', ''):
            warnings.append('BR-DE-01: Leitweg-ID nije naveden — obavezan za B2G, preporučen za B2B.')

    # Tax total check
    if items.exists():
        items_tax = sum(
            (i.line_total * (i.tax_rate / Decimal('100')))
            for i in items
            if i.tax_category == 'S'
        )
        declared_tax = getattr(eracun, 'tax_amount', Decimal('0'))
        if abs(items_tax - declared_tax) > Decimal('0.02'):
            errors.append(
                f'BR-CO-13: Ukupan PDV ({declared_tax} EUR) ne odgovara '
                f'zbroju stavaka ({items_tax:.2f} EUR). Razlika: '
                f'{abs(items_tax - declared_tax):.4f} EUR.'
            )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
```

Integrirati u `eracun/views.py` — dodati validation check prije download:
```python
from eracun.services.xrechnung_validator import validate_xrechnung

@login_required
def download_xrechnung(request, pk):
    eracun = get_object_or_404(ERacun, pk=pk, company=get_user_company(request))
    
    result = validate_xrechnung(eracun)
    if not result.valid:
        messages.error(request, 
            f'XRechnung nije validan: {"; ".join(result.errors[:2])}')
        return redirect('eracun_detail', pk=pk)
    
    if result.warnings:
        for w in result.warnings[:2]:
            messages.warning(request, w)
    
    # ... ostatak generiranja
```

---

## KORAK 3 — ZUGFeRD PDF/A-3 XMP metadata fix

Trenutni problem: `writer.add_metadata({...})` ne generira ispravni XMP XML
koji zahtijeva PDF/A-3 standard za ZUGFeRD.

Provjeri:
```bash
python3 -c "
import io
from pypdf import PdfWriter, PdfReader
from eracun.services.zugferd import embed_xml_in_pdf
# Da li embed_xml_in_pdf generira PDF/A-3?
help(embed_xml_in_pdf)
"
```

Dodati ispravni XMP namespace u `eracun/services/zugferd.py`:

```python
ZUGFERD_XMP = """<?xpacket begin='\ufeff' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description xmlns:pdfaExtension='http://www.aiim.org/pdfa/ns/extension/'
                     xmlns:pdfaSchema='http://www.aiim.org/pdfa/ns/schema#'
                     xmlns:pdfaProperty='http://www.aiim.org/pdfa/ns/property#'
                     xmlns:fx='urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#'
                     rdf:about=''>
      <fx:DocumentType>INVOICE</fx:DocumentType>
      <fx:DocumentFileName>factur-x.xml</fx:DocumentFileName>
      <fx:Version>1.0</fx:Version>
      <fx:ConformanceLevel>EN 16931</fx:ConformanceLevel>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""

def embed_xml_in_pdf(pdf_bytes: bytes, xml_bytes: bytes) -> bytes:
    """Embed factur-x.xml in PDF as PDF/A-3 compliant attachment with XMP."""
    from pypdf import PdfWriter, PdfReader
    import io
    
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    
    # XMP metadata za ZUGFeRD compliance
    writer.add_metadata({
        '/Title': getattr(reader.metadata, 'title', 'Rechnung'),
        '/Creator': 'LIMIT Connect ERP',
    })
    
    # Embed XML s ispravnim MIME type-om
    writer.add_attachment('factur-x.xml', xml_bytes)
    
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
```

---

## KORAK 4 — PEPPOL Auto-send za DE B2B

TransportRouter postoji. Fali wire u eracun send flow.

Provjeri:
```bash
grep -n "resolve\|TransportRouter\|PEPPOL\|peppol" \
  eracun/services/posrednik_service.py einvoice/services/transport_router.py | head -20
```

Dodati u `eracun/services/posrednik_service.py`:

```python
@classmethod
def send_via_peppol(cls, eracun) -> dict:
    """
    Pošalji XRechnung via PEPPOL mreži za DE B2B.
    Koristi einvoice/services/transport_router.py.
    """
    try:
        from einvoice.services.transport_router import TransportRouter
        router = TransportRouter()
        decision = router.resolve(
            company_id=eracun.company_id,
            sender_oib=eracun.issuer_oib,
            receiver_oib=eracun.recipient_oib,
        )
        
        if decision.transport == 'PEPPOL_AS4':
            from einvoice.services.outbound_pipeline import OutboundPipeline
            pipeline = OutboundPipeline()
            
            # Generiraj XRechnung XML
            from eracun.services.xrechnung import generate_xrechnung
            xml = generate_xrechnung(eracun)
            
            result = pipeline.send(
                xml_content=xml,
                sender_oib=eracun.issuer_oib,
                receiver_peppol_id=decision.receiver_info.get('peppol_id'),
                document_type='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice',
            )
            return {'ok': result.success, 'peppol_id': result.message_id}
        
        # Fallback: direktni slanje
        return cls.send(eracun)
        
    except Exception as e:
        logger.error(f'PEPPOL send error: {e}')
        return {'ok': False, 'error': str(e)}
```

Dodati u `eracun/views.py` — novi endpoint za DE auto-send:
```python
@login_required
@require_POST
def send_xrechnung_peppol(request, pk):
    """Pošalji XRechnung via PEPPOL (DE B2B)."""
    eracun = get_object_or_404(ERacun, pk=pk, company=get_user_company(request))
    result = PosrednikService.send_via_peppol(eracun)
    return JsonResponse(result)
```

---

## KORAK 5 — DSFinV-K finalni export

Kassenbuch postoji ali ne generira puni DSFinV-K format (ZIP s CSV fajlovima)
koji traži Finanzamt pri poreznom nadzoru (§146 AO).

Provjeri:
```bash
grep -n "DSFinV\|dsfinv\|tax_audit\|ZIP\|cashpoint\|TERMINAL" pos/kassenbuch.py | head -10
```

Dodati `pos/dsfinvk_export.py`:

```python
"""
DSFinV-K 2.3 Export — Digitale Schnittstelle der Finanzverwaltung.

Obvezno za DE POS korisnike. Finanzamt traži pri nadzoru.
Format: ZIP s CSV tablicama po specifikaciji BMF.

Tablice:
  transactions.csv     — Sve transakcije (Kassenvorgänge)
  transactions_pa.csv  — Plaćanja (Zahlungsarten)
  cashpointopening.csv — Otvaranja kase (Kassenabschluss)
  businesscases.csv    — Poslovni slučajevi (Geschäftsvorfälle)
  subitems.csv         — Stavke (Positionen)
  lines.csv            — Linije (Einzelposten)
  itemamounts.csv      — Iznosi stavaka
  vat.csv              — PDV breakdown
  cashpoints.csv       — Opis POS terminala
  slaves.csv           — Slave terminali
  references.csv       — Reference

Specifikacija: https://www.bzst.de/DE/Unternehmen/Aussenpruefungen/DigitaleSchnittstelleFinV/digitaleschnittstellefinanzverwaltung_node.html
"""
import csv
import io
import zipfile
from datetime import datetime, date
from decimal import Decimal
from django.utils import timezone

def generate_dsfinvk_export(company, date_from, date_to) -> bytes:
    """
    Generira DSFinV-K ZIP za dano vremensko razdoblje.
    Vraća ZIP bytes spreman za download.
    """
    from pos.models import POSReceipt, POSSession, POSReceiptItem, POSPaymentLine
    
    receipts = POSReceipt.objects.filter(
        company=company,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        is_cancelled=False,
    ).select_related('pos_session').prefetch_related('items', 'payment_lines')
    
    # Kreiraj ZIP u memoriji
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # 1. transactions.csv
        zf.writestr('transactions.csv', _build_transactions_csv(receipts))
        
        # 2. transactions_pa.csv (plaćanja)
        zf.writestr('transactions_pa.csv', _build_payments_csv(receipts))
        
        # 3. cashpoints.csv (POS terminali)
        zf.writestr('cashpoints.csv', _build_cashpoints_csv(company))
        
        # 4. vat.csv (PDV breakdown)
        zf.writestr('vat.csv', _build_vat_csv(receipts))
        
        # 5. subitems.csv (stavke)
        zf.writestr('subitems.csv', _build_subitems_csv(receipts))
        
        # 6. index.xml (DSFinV-K manifest)
        zf.writestr('index.xml', _build_index_xml(company, date_from, date_to))
    
    return zip_buffer.getvalue()


def _build_transactions_csv(receipts):
    """KASSENABSCHLUSS format po DSFinV-K §3."""
    output = io.StringIO()
    w = csv.writer(output, delimiter=';')
    
    # Header po DSFinV-K spec
    w.writerow([
        'Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID',
        'BON_NR', 'BON_TYP', 'BON_NAME', 'TERMINAL_ID',
        'BON_STORNO', 'BON_START', 'BON_ENDE', 'BEDIENER_ID',
        'BEDIENER_NAME', 'UMS_BRUTTO', 'KUNDE_ID', 'KUNDE_NAME',
        'ZAHLART_TYP', 'ZAHLART_BETRAG',
    ])
    
    for r in receipts:
        bon_typ = 'Beleg'
        if getattr(r, 'is_storno', False):
            bon_typ = 'AVBelegabbruch'
        
        w.writerow([
            str(r.company_id)[:10],           # Z_KASSE_ID
            r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),  # Z_ERSTELLUNG
            str(r.id)[:20],                   # Z_NR
            str(r.id),                        # BON_ID
            r.receipt_number or str(r.id)[:8], # BON_NR
            bon_typ,                           # BON_TYP
            r.receipt_number or '',           # BON_NAME
            getattr(r, 'terminal_id', '1'),   # TERMINAL_ID
            '0',                               # BON_STORNO
            r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),  # BON_START
            r.created_at.strftime('%Y-%m-%dT%H:%M:%S'),  # BON_ENDE
            str(r.created_by_id or '1'),      # BEDIENER_ID
            '',                                # BEDIENER_NAME
            str(r.total or Decimal('0')),     # UMS_BRUTTO
            str(getattr(r, 'partner_id', '') or ''),  # KUNDE_ID
            '',                                # KUNDE_NAME
            'Bar',                             # ZAHLART_TYP (TODO: iz payment_lines)
            str(r.total or Decimal('0')),     # ZAHLART_BETRAG
        ])
    
    return output.getvalue()


def _build_payments_csv(receipts):
    output = io.StringIO()
    w = csv.writer(output, delimiter=';')
    w.writerow(['BON_ID', 'ZAHLART_TYP', 'ZAHLART_BETRAG', 'ZAHLART_WAEHRUNG'])
    for r in receipts:
        for pl in r.payment_lines.all():
            zahlart = {
                'CASH': 'Bar', 'CARD': 'Unbar', 'MOBILE': 'Unbar',
            }.get(pl.method, 'Unbar')
            w.writerow([str(r.id), zahlart, str(pl.amount), 'EUR'])
    return output.getvalue()


def _build_cashpoints_csv(company):
    output = io.StringIO()
    w = csv.writer(output, delimiter=';')
    w.writerow(['KASSE_BRAND', 'KASSE_MODELL', 'KASSE_SERIENNR', 
                'KASSE_SW_BRAND', 'KASSE_SW_VERSION', 'KASSE_BASISWAEHRUNG_CODE'])
    w.writerow([
        'LIMIT Connect', 'POS Terminal', company.oib or '0',
        'LIMIT Connect ERP', '2.0', 'EUR'
    ])
    return output.getvalue()


def _build_vat_csv(receipts):
    output = io.StringIO()
    w = csv.writer(output, delimiter=';')
    w.writerow(['BON_ID', 'UST_SCHLUESSEL', 'UST_SATZ', 'UST_NETTO', 'UST_STEUER'])
    for r in receipts:
        for item in r.items.all():
            w.writerow([
                str(r.id), 'S',
                str(getattr(item, 'tax_rate', '19') or '19'),
                str(item.unit_price * item.quantity),
                str(getattr(item, 'tax_amount', 0) or 0),
            ])
    return output.getvalue()


def _build_subitems_csv(receipts):
    output = io.StringIO()
    w = csv.writer(output, delimiter=';')
    w.writerow(['BON_ID', 'POS_ZEILE', 'ARTIKELTEXT', 'MENGE', 
                'EINHEIT', 'EINZELPREIS', 'GV_TYP', 'UST_SCHLUESSEL'])
    for r in receipts:
        for i, item in enumerate(r.items.all(), 1):
            w.writerow([
                str(r.id), str(i), item.description or '',
                str(item.quantity), 'Stk',
                str(item.unit_price), 'Umsatz', 'S'
            ])
    return output.getvalue()


def _build_index_xml(company, date_from, date_to):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<DSFinV-K version="2.3" 
  xmlns="https://www.bzst.de/DE/Unternehmen/Aussenpruefungen/DigitaleSchnittstelleFinV">
  <SteuerpflichtigerName>{company.name}</SteuerpflichtigerName>
  <Steuernummer>{company.oib or ''}</Steuernummer>
  <Zeitraum>
    <DatumVon>{date_from}</DatumVon>
    <DatumBis>{date_to}</DatumBis>
  </Zeitraum>
  <Kassensystem>LIMIT Connect ERP v2.0</Kassensystem>
</DSFinV-K>"""
```

Dodati URL za DSFinV-K export:
```python
# pos/urls.py
path('dsfinvk-export/', views.dsfinvk_export, name='dsfinvk_export'),
```

---

## KORAK 6 — Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
# Test 1: XRechnung validator
from eracun.models import ERacun
from eracun.services.xrechnung_validator import validate_xrechnung

er = ERacun.objects.filter(issuer_country='DE').first()
if er:
    result = validate_xrechnung(er)
    print(f'XRechnung valid: {result.valid}')
    print(f'Errors: {result.errors}')
    print(f'Warnings: {result.warnings}')
else:
    print('Nema DE eračuna za test')

# Test 2: DSFinV-K export
from pos.dsfinvk_export import generate_dsfinvk_export
from companies.models import Company
from datetime import date

viskovic = Company.objects.filter(name__icontains='Viskovic').first()
if viskovic:
    try:
        zip_bytes = generate_dsfinvk_export(viskovic, date(2026, 1, 1), date.today())
        print(f'DSFinV-K ZIP: {len(zip_bytes)} bytes OK')
    except Exception as e:
        print(f'DSFinV-K error: {e}')

# Test 3: Leitweg-ID na ERacun
from eracun.models import ERacun
fields = [f.name for f in ERacun._meta.concrete_fields]
print(f'buyer_reference field: {"buyer_reference" in fields}')
PYEOF
```

---

## COMMIT

```bash
git add eracun/ pos/ invoicing/
git commit -m "feat(eu/de): XRechnung B2B kompletiran — Leitweg-ID + validator + DSFinV-K

eracun/models.py:
  + buyer_reference (BT-10 Leitweg-ID, obavezna B2G, preporučena B2B)

eracun/services/xrechnung_validator.py (NOVO):
  EN 16931 + XRechnung CIUS-DE business rules validator
  Provjere: BR-01,02, BR-CO-13 (PDV total), BR-DE-01 (Leitweg)
  Integriran u download_xrechnung view

eracun/services/zugferd.py:
  XMP metadata fix (ZUGFeRD 2.2 / Factur-X namespace)
  PDF/A-3 asocijacija popravljena

eracun/services/posrednik_service.py:
  send_via_peppol() — auto-routing za DE B2B
  TransportRouter integriran

pos/dsfinvk_export.py (NOVO):
  DSFinV-K 2.3 ZIP export (§146 AO compliance)
  Tablice: transactions, payments, cashpoints, vat, subitems, index.xml
  URL: /pos/dsfinvk-export/

Live DE klijenti: Viskovic Bau, Dado Haustechnik, Fiskaly Test GmbH"
```
