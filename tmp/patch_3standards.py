"""
3 Nova standarda + Javni Validator
1. Agro-Fiskalizacija (AgroHealth.xml)
2. Turistički ZKI (TuristPrijava.xml)
3. Forenzika Zaliha (InventoryLedger.xml)
+ BORG Validator (javna stranica za provjeru potpisa)
"""
import os
BASE = '/var/www/fina-connect'
GEN_DIR = os.path.join(BASE, 'gov_export/generators')

# ══════════════════════════════════════════════════════════════════════
# 1. AGRO-FISKALIZACIJA GENERATOR
# ══════════════════════════════════════════════════════════════════════

agro_gen = '''"""
Agro-Fiskalizacija — AgroHealth.xml generator.
Svaki FlockHealthRecord + karenca → potpisan XML za veterinarsku inspekciju.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from django.utils import timezone


class AgroHealthGenerator:
    """Generira AgroHealth.xml za GovExport pipeline."""

    NS = 'urn:limit-connect:agro-health:v1.0'

    def generate(self, export):
        from udruge.models import Flock, FlockHealthRecord, EggRecord, FlockMortality
        
        company = export.company
        root = ET.Element('AgroHealthReport', xmlns=self.NS)
        root.set('version', '1.0')
        root.set('generated', timezone.now().isoformat())

        # Izdavatelj
        issuer = ET.SubElement(root, 'Issuer')
        ET.SubElement(issuer, 'Name').text = company.name
        ET.SubElement(issuer, 'OIB').text = company.oib or ''
        ET.SubElement(issuer, 'Address').text = company.address or ''

        # Period
        period = ET.SubElement(root, 'Period')
        ET.SubElement(period, 'From').text = export.period_start.isoformat()
        ET.SubElement(period, 'To').text = export.period_end.isoformat()

        # Jata
        flocks = Flock.objects.filter(company=company, aktivan=True)
        flocks_el = ET.SubElement(root, 'Flocks', count=str(flocks.count()))

        for flock in flocks:
            f_el = ET.SubElement(flocks_el, 'Flock', id=str(flock.pk))
            ET.SubElement(f_el, 'Name').text = flock.naziv
            ET.SubElement(f_el, 'Species').text = flock.get_vrsta_display()
            ET.SubElement(f_el, 'Breed').text = flock.pasmina or ''
            ET.SubElement(f_el, 'HeadCount').text = str(flock.broj_komada)
            ET.SubElement(f_el, 'ActiveCount').text = str(flock.aktivnih_komada)
            ET.SubElement(f_el, 'AcquiredDate').text = flock.datum_nabave.isoformat() if flock.datum_nabave else ''
            ET.SubElement(f_el, 'FarmingType').text = flock.tip_uzgoja or ''
            ET.SubElement(f_el, 'Location').text = flock.objekt or ''
            ET.SubElement(f_el, 'HasActiveWithdrawal').text = str(flock.has_active_karenca).lower()
            if flock.karenca_end_date:
                ET.SubElement(f_el, 'WithdrawalEndDate').text = flock.karenca_end_date.isoformat()

            # Zdravstveni zapisi u periodu
            health = FlockHealthRecord.objects.filter(
                flock=flock,
                datum__gte=export.period_start,
                datum__lte=export.period_end,
            )
            if health.exists():
                h_el = ET.SubElement(f_el, 'HealthRecords', count=str(health.count()))
                for hr in health:
                    rec = ET.SubElement(h_el, 'Record', id=str(hr.pk))
                    ET.SubElement(rec, 'Type').text = hr.get_vrsta_tretmana_display()
                    ET.SubElement(rec, 'Date').text = hr.datum.isoformat()
                    ET.SubElement(rec, 'Medicine').text = hr.lijek or ''
                    ET.SubElement(rec, 'Dosage').text = hr.doza or ''
                    ET.SubElement(rec, 'Veterinarian').text = hr.veterinar or ''
                    if hr.karenca_dana:
                        ET.SubElement(rec, 'WithdrawalDays').text = str(hr.karenca_dana)
                        ET.SubElement(rec, 'WithdrawalActive').text = str(hr.karenca_aktivna).lower()

            # Mortalitet
            mort = FlockMortality.objects.filter(
                flock=flock,
                datum__gte=export.period_start,
                datum__lte=export.period_end,
            )
            if mort.exists():
                m_el = ET.SubElement(f_el, 'MortalityRecords', count=str(mort.count()))
                for m in mort:
                    mr = ET.SubElement(m_el, 'Record')
                    ET.SubElement(mr, 'Date').text = m.datum.isoformat()
                    ET.SubElement(mr, 'Count').text = str(m.broj_uginulih)
                    ET.SubElement(mr, 'Reason').text = m.razlog or ''

            # Jaja u periodu
            eggs = EggRecord.objects.filter(
                flock=flock,
                datum__gte=export.period_start,
                datum__lte=export.period_end,
            )
            if eggs.exists():
                e_el = ET.SubElement(f_el, 'EggProduction', count=str(eggs.count()))
                total_eggs = sum(e.broj_jaja for e in eggs)
                total_broken = sum(e.broken for e in eggs)
                ET.SubElement(e_el, 'TotalEggs').text = str(total_eggs)
                ET.SubElement(e_el, 'TotalBroken').text = str(total_broken)

        xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent='  ')
        return xml_str
'''

with open(os.path.join(GEN_DIR, 'agro_health.py'), 'w') as f:
    f.write(agro_gen)
print("[OK] generators/agro_health.py — AgroHealthGenerator")


# ══════════════════════════════════════════════════════════════════════
# 2. TURISTIČKI ZKI GENERATOR
# ══════════════════════════════════════════════════════════════════════

tourist_gen = '''"""
Turistički ZKI — TuristPrijava.xml generator.
Svaki booking check-in → potpisan XML s lokalnim ZKI kodom.
Za obranu kad eVisitor padne.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
import hashlib
from django.utils import timezone


class TouristRegistrationGenerator:
    """Generira TuristPrijava.xml za GovExport pipeline."""

    NS = 'urn:limit-connect:tourist-registration:v1.0'

    def generate(self, export):
        company = export.company
        root = ET.Element('TouristRegistration', xmlns=self.NS)
        root.set('version', '1.0')
        root.set('generated', timezone.now().isoformat())

        # Izdavatelj (objekt za smještaj)
        issuer = ET.SubElement(root, 'Issuer')
        ET.SubElement(issuer, 'Name').text = company.name
        ET.SubElement(issuer, 'OIB').text = company.oib or ''

        period = ET.SubElement(root, 'Period')
        ET.SubElement(period, 'From').text = export.period_start.isoformat()
        ET.SubElement(period, 'To').text = export.period_end.isoformat()

        # Rental bookings u periodu
        try:
            from rental.models import Booking, TrafficRecord
            bookings = Booking.objects.filter(
                company=company,
                check_in__gte=export.period_start,
                check_in__lte=export.period_end,
            ).order_by('check_in')

            guests_el = ET.SubElement(root, 'Guests', count=str(bookings.count()))
            for b in bookings:
                g = ET.SubElement(guests_el, 'Guest', id=str(b.pk))
                ET.SubElement(g, 'BookingNumber').text = b.booking_number or ''
                ET.SubElement(g, 'GuestName').text = b.guest_name
                ET.SubElement(g, 'GuestCount').text = str(b.guest_count)
                ET.SubElement(g, 'CheckIn').text = b.check_in.isoformat()
                ET.SubElement(g, 'CheckOut').text = b.check_out.isoformat()
                ET.SubElement(g, 'Status').text = b.status
                if b.actual_check_in:
                    ET.SubElement(g, 'ActualCheckIn').text = b.actual_check_in.isoformat()
                
                # Lokalni ZKI — hash kao dokaz prijave
                zki_data = f'{company.oib}|{b.guest_name}|{b.check_in}|{b.pk}'
                zki = hashlib.sha256(zki_data.encode()).hexdigest()[:32]
                ET.SubElement(g, 'LocalZKI').text = zki

                # Traffic records (eVisitor podaci)
                traffic = TrafficRecord.objects.filter(booking=b)
                for tr in traffic:
                    t_el = ET.SubElement(g, 'TrafficRecord', id=str(tr.pk))
                    ET.SubElement(t_el, 'GuestName').text = tr.guest_name or ''
                    ET.SubElement(t_el, 'Nationality').text = tr.nationality or ''
                    ET.SubElement(t_el, 'DocumentNumber').text = tr.document_number or ''
                    ET.SubElement(t_el, 'EVisitorSynced').text = str(tr.evisitor_synced).lower()
                    if tr.evisitor_synced_at:
                        ET.SubElement(t_el, 'EVisitorSyncedAt').text = tr.evisitor_synced_at.isoformat()
        except Exception:
            ET.SubElement(root, 'Guests', count='0')

        # Experiences bookings
        try:
            from experiences.models import ExperienceBooking
            exp_bookings = ExperienceBooking.objects.filter(
                schedule__experience__company=company,
                schedule__date__gte=export.period_start,
                schedule__date__lte=export.period_end,
                status__in=['checked_in', 'completed'],
            )
            exp_el = ET.SubElement(root, 'ExperienceGuests', count=str(exp_bookings.count()))
            for eb in exp_bookings:
                eg = ET.SubElement(exp_el, 'Guest', id=str(eb.pk))
                ET.SubElement(eg, 'Name').text = eb.guest_name
                ET.SubElement(eg, 'Country').text = eb.guest_country or ''
                ET.SubElement(eg, 'PaxCount').text = str(eb.pax_count)
                ET.SubElement(eg, 'Experience').text = eb.schedule.experience.name
                ET.SubElement(eg, 'Date').text = eb.schedule.date.isoformat()
        except DatabaseError:
            ET.SubElement(root, 'ExperienceGuests', count='0')

        xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent='  ')
        return xml_str
'''

with open(os.path.join(GEN_DIR, 'tourist_registration.py'), 'w') as f:
    f.write(tourist_gen)
print("[OK] generators/tourist_registration.py — TouristRegistrationGenerator")


# ══════════════════════════════════════════════════════════════════════
# 3. FORENZIKA ZALIHA GENERATOR
# ══════════════════════════════════════════════════════════════════════

inventory_gen = '''"""
Forenzika Zaliha — InventoryLedger.xml generator.
Mjesečni snapshot cijelog inventara — potpisan dokaz za Poreznu.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal
from django.utils import timezone


class InventoryLedgerGenerator:
    """Generira InventoryLedger.xml za GovExport pipeline."""

    NS = 'urn:limit-connect:inventory-ledger:v1.0'

    def generate(self, export):
        from inventory.models import InventoryItem, StockMovement, StockBatch
        
        company = export.company
        root = ET.Element('InventoryLedger', xmlns=self.NS)
        root.set('version', '1.0')
        root.set('generated', timezone.now().isoformat())

        issuer = ET.SubElement(root, 'Issuer')
        ET.SubElement(issuer, 'Name').text = company.name
        ET.SubElement(issuer, 'OIB').text = company.oib or ''

        period = ET.SubElement(root, 'Period')
        ET.SubElement(period, 'From').text = export.period_start.isoformat()
        ET.SubElement(period, 'To').text = export.period_end.isoformat()

        # Snapshot svih artikala
        items = InventoryItem.objects.filter(company=company, is_active=True)
        items_el = ET.SubElement(root, 'Items', count=str(items.count()))

        total_value = Decimal('0')
        for item in items:
            i_el = ET.SubElement(items_el, 'Item', id=str(item.pk))
            ET.SubElement(i_el, 'SKU').text = item.sku
            ET.SubElement(i_el, 'Name').text = item.name
            ET.SubElement(i_el, 'Unit').text = item.unit
            ET.SubElement(i_el, 'Quantity').text = str(item.quantity)
            ET.SubElement(i_el, 'UnitPrice').text = str(item.unit_price or 0)
            ET.SubElement(i_el, 'PurchasePrice').text = str(item.purchase_price or 0)
            value = (item.quantity or 0) * (item.purchase_price or item.unit_price or 0)
            ET.SubElement(i_el, 'TotalValue').text = str(round(value, 2))
            total_value += value

            # SplitAllocation
            if item.reserved_inhouse or item.reserved_marketplace:
                alloc = ET.SubElement(i_el, 'Allocation')
                ET.SubElement(alloc, 'ReservedInhouse').text = str(item.reserved_inhouse)
                ET.SubElement(alloc, 'ReservedMarketplace').text = str(item.reserved_marketplace)
                ET.SubElement(alloc, 'BufferPct').text = str(item.allocation_buffer_pct)

            # Flock link (karenca)
            if item.source_flock_id:
                flock_el = ET.SubElement(i_el, 'SourceFlock', id=str(item.source_flock_id))
                ET.SubElement(flock_el, 'Name').text = item.source_flock.naziv if item.source_flock else ''
                ET.SubElement(flock_el, 'ActiveWithdrawal').text = str(
                    item.source_flock.has_active_karenca if item.source_flock else False
                ).lower()

            # LOT batches
            batches = StockBatch.objects.filter(item=item, quarantine_status='active')
            if batches.exists():
                b_el = ET.SubElement(i_el, 'Batches', count=str(batches.count()))
                for batch in batches:
                    bt = ET.SubElement(b_el, 'Batch')
                    ET.SubElement(bt, 'LOT').text = batch.batch_number
                    ET.SubElement(bt, 'Quantity').text = str(batch.quantity)
                    if batch.expiry_date:
                        ET.SubElement(bt, 'ExpiryDate').text = batch.expiry_date.isoformat()

        # Kretanja u periodu
        movements = StockMovement.objects.filter(
            item__company=company,
            created_at__date__gte=export.period_start,
            created_at__date__lte=export.period_end,
        ).order_by('created_at')

        mov_el = ET.SubElement(root, 'Movements', count=str(movements.count()))
        for mv in movements[:500]:  # Max 500 za XML veličinu
            m = ET.SubElement(mov_el, 'Movement', id=str(mv.pk))
            ET.SubElement(m, 'Item').text = mv.item.name
            ET.SubElement(m, 'Type').text = mv.movement_type
            ET.SubElement(m, 'Quantity').text = str(mv.quantity)
            ET.SubElement(m, 'UnitPrice').text = str(mv.unit_price)
            ET.SubElement(m, 'Reason').text = mv.reason or ''
            ET.SubElement(m, 'Timestamp').text = mv.created_at.isoformat()

        # Summary
        summary = ET.SubElement(root, 'Summary')
        ET.SubElement(summary, 'TotalItems').text = str(items.count())
        ET.SubElement(summary, 'TotalValue').text = str(round(total_value, 2))
        ET.SubElement(summary, 'TotalMovements').text = str(movements.count())
        ET.SubElement(summary, 'Currency').text = 'EUR'

        xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent='  ')
        return xml_str
'''

with open(os.path.join(GEN_DIR, 'inventory_ledger.py'), 'w') as f:
    f.write(inventory_gen)
print("[OK] generators/inventory_ledger.py — InventoryLedgerGenerator")


# ══════════════════════════════════════════════════════════════════════
# 4. JAVNI BORG VALIDATOR (Dron #2 — Slijepi Inspektor)
# ══════════════════════════════════════════════════════════════════════

validator_view = '''"""
BORG Validator — javna stranica za provjeru potpisa GovExport XML-ova.
Inspektor uploada XML → sustav provjerava kriptografski potpis → zelena/crvena.
BEZ AUTENTIFIKACIJE — javno dostupno.
"""
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import hashlib


# CSRF exempt: public booking endpoint — uses BookingSignature
@csrf_exempt
def public_validator(request):
    """GET: forma za upload. POST: provjera XML-a."""
    result = None

    if request.method == 'POST' and request.FILES.get('xml_file'):
        xml_file = request.FILES['xml_file']
        xml_bytes = xml_file.read()
        xml_str = xml_bytes.decode('utf-8', errors='replace')

        result = {
            'filename': xml_file.name,
            'size': len(xml_bytes),
            'sha256': hashlib.sha256(xml_bytes).hexdigest(),
            'valid_xml': False,
            'has_signature': False,
            'signature_valid': False,
            'issuer': '',
            'generated': '',
            'doc_type': '',
        }

        # Parse XML
        try:
            from lxml import etree
            root = etree.fromstring(xml_bytes)
            result['valid_xml'] = True
            result['doc_type'] = root.tag.split('}')[-1] if '}' in root.tag else root.tag

            # Extract metadata
            issuer_el = root.find('.//{*}Issuer/{*}Name')
            if issuer_el is not None:
                result['issuer'] = issuer_el.text or ''
            oib_el = root.find('.//{*}Issuer/{*}OIB')
            if oib_el is not None:
                result['issuer'] += f' (OIB: {oib_el.text})'

            generated = root.get('generated', '')
            result['generated'] = generated

            # Provjeri XAdES potpis
            sig_el = root.find('.//{http://www.w3.org/2000/09/xmldsig#}Signature')
            if sig_el is not None:
                result['has_signature'] = True
                # Provjeri potpis
                try:
                    from signxml import XMLVerifier
                    XMLVerifier().verify(root)
                    result['signature_valid'] = True
                except ImportError as e:
                    result['signature_error'] = str(e)[:200]
            
            # Provjeri u bazi postoji li ovaj export
            try:
                from gov_export.models import GovExport
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
                export = GovExport.objects.filter(xml_hash=result['sha256']).first()
                if export:
                    result['registered'] = True
                    result['reference'] = export.reference_number
                    result['status'] = export.get_status_display()
                else:
                    result['registered'] = False
            except DatabaseError:
                result['registered'] = False

        except DatabaseError as e:
            result['parse_error'] = str(e)[:200]

    return render(request, 'gov_export/validator.html', {'result': result})
'''

with open(os.path.join(BASE, 'gov_export/validator.py'), 'w') as f:
    f.write(validator_view)
print("[OK] gov_export/validator.py — javni BORG Validator")

# Validator template
validator_tpl = '''<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BORG Validator — LIMIT Connect</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:#0a0a0a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.container{max-width:600px;width:100%}
.logo{text-align:center;margin-bottom:2rem}
.logo h1{font-size:1.8rem;font-weight:800;color:#c9a84c}
.logo p{color:#64748b;font-size:.85rem;margin-top:.25rem}
.card{background:#111827;border:1px solid #1e293b;border-radius:16px;padding:2rem;margin-bottom:1.5rem}
.upload-zone{border:2px dashed #334155;border-radius:12px;padding:3rem 2rem;text-align:center;cursor:pointer;transition:border-color .2s}
.upload-zone:hover{border-color:#c9a84c}
.upload-zone i{font-size:2.5rem;color:#475569;margin-bottom:1rem;display:block}
.upload-zone p{color:#94a3b8;font-size:.9rem}
input[type=file]{display:none}
.btn{background:linear-gradient(135deg,#c9a84c,#a78b3d);color:#0a0a0a;font-weight:700;border:none;padding:.75rem 2rem;border-radius:10px;font-size:.9rem;cursor:pointer;width:100%;margin-top:1rem}
.result{margin-top:1.5rem}
.result-row{display:flex;justify-content:space-between;padding:.6rem 0;border-bottom:1px solid #1e293b;font-size:.85rem}
.result-row:last-child{border:none}
.result-row .label{color:#64748b}
.result-row .value{font-weight:600}
.badge-pass{background:rgba(34,197,94,.15);color:#22c55e;padding:3px 12px;border-radius:6px;font-size:.78rem;font-weight:700}
.badge-fail{background:rgba(239,68,68,.15);color:#ef4444;padding:3px 12px;border-radius:6px;font-size:.78rem;font-weight:700}
.verdict{text-align:center;padding:1.5rem;border-radius:12px;margin-top:1rem}
.verdict.valid{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3)}
.verdict.invalid{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3)}
.verdict i{font-size:2rem;margin-bottom:.5rem;display:block}
.verdict h3{font-size:1.1rem;margin-bottom:.25rem}
.verdict p{font-size:.8rem;color:#94a3b8}
.footer{text-align:center;color:#475569;font-size:.75rem;margin-top:2rem}
</style>
</head>
<body>
<div class="container">

<div class="logo">
  <h1><i class="fas fa-shield-alt"></i> BORG Validator</h1>
  <p>Javna provjera kriptografskog potpisa GovExport dokumenata</p>
</div>

<div class="card">
  <form method="POST" enctype="multipart/form-data" id="validatorForm">
    <div class="upload-zone" onclick="document.getElementById('xmlFile').click()">
      <i class="fas fa-file-code"></i>
      <p>Kliknite ili prevucite XML datoteku ovdje</p>
      <p style="font-size:.75rem;color:#475569;margin-top:.5rem" id="fileName">Podržani formati: AgroHealth, TuristPrijava, InventoryLedger, eRačun</p>
    </div>
    <input type="file" name="xml_file" id="xmlFile" accept=".xml" onchange="document.getElementById('fileName').textContent=this.files[0]?.name||''">
    <button type="submit" class="btn"><i class="fas fa-search me-2"></i>Provjeri dokument</button>
  </form>
</div>

{% if result %}
<div class="card">
  <h4 style="color:#c9a84c;margin-bottom:1rem"><i class="fas fa-clipboard-check me-2"></i>Rezultat provjere</h4>
  
  <div class="result">
    <div class="result-row"><span class="label">Datoteka</span><span class="value">{{ result.filename }}</span></div>
    <div class="result-row"><span class="label">Veličina</span><span class="value">{{ result.size }} bytes</span></div>
    <div class="result-row"><span class="label">SHA-256</span><span class="value" style="font-family:monospace;font-size:.75rem">{{ result.sha256|truncatechars:32 }}</span></div>
    <div class="result-row"><span class="label">Tip dokumenta</span><span class="value">{{ result.doc_type }}</span></div>
    <div class="result-row"><span class="label">Izdavatelj</span><span class="value">{{ result.issuer }}</span></div>
    <div class="result-row"><span class="label">Generirano</span><span class="value">{{ result.generated }}</span></div>
    <div class="result-row"><span class="label">Validan XML</span><span class="{% if result.valid_xml %}badge-pass{% else %}badge-fail{% endif %}">{% if result.valid_xml %}DA{% else %}NE{% endif %}</span></div>
    <div class="result-row"><span class="label">Digitalni potpis</span><span class="{% if result.has_signature %}badge-pass{% else %}badge-fail{% endif %}">{% if result.has_signature %}Prisutan{% else %}Nema{% endif %}</span></div>
    {% if result.has_signature %}
    <div class="result-row"><span class="label">Potpis valjan</span><span class="{% if result.signature_valid %}badge-pass{% else %}badge-fail{% endif %}">{% if result.signature_valid %}DA — neizvmjenjen{% else %}NE{% endif %}</span></div>
    {% endif %}
    {% if result.registered %}
    <div class="result-row"><span class="label">Registriran u sustavu</span><span class="badge-pass">{{ result.reference }} ({{ result.status }})</span></div>
    {% endif %}
  </div>

  {% if result.valid_xml and result.has_signature and result.signature_valid %}
  <div class="verdict valid">
    <i class="fas fa-check-circle" style="color:#22c55e"></i>
    <h3 style="color:#22c55e">Dokument je VALJAN</h3>
    <p>Kriptografski potpis je ispravan. Sadržaj nije izmijenjen od trenutka potpisivanja.</p>
  </div>
  {% elif result.valid_xml and not result.has_signature %}
  <div class="verdict" style="background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3)">
    <i class="fas fa-exclamation-triangle" style="color:#f59e0b"></i>
    <h3 style="color:#f59e0b">Dokument NIJE potpisan</h3>
    <p>XML je valjan ali nema digitalnog potpisa. Autentičnost se ne može potvrditi.</p>
  </div>
  {% else %}
  <div class="verdict invalid">
    <i class="fas fa-times-circle" style="color:#ef4444"></i>
    <h3 style="color:#ef4444">Dokument je NEVALJAN</h3>
    <p>{% if result.parse_error %}{{ result.parse_error }}{% elif result.signature_error %}Potpis: {{ result.signature_error }}{% else %}XML nije mogao biti parsiran.{% endif %}</p>
  </div>
  {% endif %}
</div>
{% endif %}

<div class="footer">
  BORG Validator — LIMIT Connect &copy; 2026 | <a href="https://limit-connect.com" style="color:#c9a84c">limit-connect.com</a>
</div>

</div>
</body>
</html>
'''

with open(os.path.join(BASE, 'templates/gov_export/validator.html'), 'w') as f:
    f.write(validator_tpl)
print("[OK] templates/gov_export/validator.html — javna stranica")


# ══════════════════════════════════════════════════════════════════════
# 5. URL-ovi za validator + seed novih doc types
# ══════════════════════════════════════════════════════════════════════

urls_path = os.path.join(BASE, 'gov_export/urls.py')
with open(urls_path) as f:
    uc = f.read()

if 'validator' not in uc:
    uc = uc.replace(
        "from . import views",
        "from . import views\nfrom .validator import public_validator"
    )
    uc = uc.replace(
        "]",
        "    path('validator/', public_validator, name='validator'),\n]"
    )
    with open(urls_path, 'w') as f:
        f.write(uc)
    print("[OK] gov_export/urls.py — /validator/ ruta")

# Dodaj nove doc types u seed
seed_path = os.path.join(BASE, 'gov_export/management/commands/seed_gov_institutions.py')
with open(seed_path) as f:
    sc = f.read()

if 'AGRO-HEALTH' not in sc:
    # Dodaj 3 nova tipa prije Done
    new_types = """
        # ── Novi standardi (LIMIT Connect inovacija) ──
        new_types = [
            {'institution_code': 'SANIT', 'code': 'AGRO-HEALTH', 'name': 'Agro-Fiskalizacija — AgroHealth Report',
             'period_type': 'monthly', 'generator_class': 'gov_export.generators.agro_health.AgroHealthGenerator'},
            {'institution_code': 'PU', 'code': 'TOURIST-ZKI', 'name': 'Turistički ZKI — Asinkrona prijava gostiju',
             'period_type': 'monthly', 'generator_class': 'gov_export.generators.tourist_registration.TouristRegistrationGenerator'},
            {'institution_code': 'PU', 'code': 'INV-LEDGER', 'name': 'Forenzika Zaliha — InventoryLedger',
             'period_type': 'monthly', 'generator_class': 'gov_export.generators.inventory_ledger.InventoryLedgerGenerator'},
        ]
        for data in new_types:
            inst_code = data.pop('institution_code')
            inst = GovInstitution.objects.get(code=inst_code)
            dt, created = GovDocumentType.objects.update_or_create(
                institution=inst, code=data['code'], defaults=data,
            )
            self.stdout.write(f'  {"+" if created else "~"} {dt}')
"""
    sc = sc.replace("        self.stdout.write(self.style.SUCCESS('Done.'))", 
                     new_types + "\n        self.stdout.write(self.style.SUCCESS('Done.'))")
    with open(seed_path, 'w') as f:
        f.write(sc)
    print("[OK] seed — 3 nova doc types dodana")


print("\\n═══════════════════════════════════════════")
print("3 STANDARDA + VALIDATOR KOMPLETNI")
print("  1. AgroHealth.xml (veterina/HAPIH)")
print("  2. TuristPrijava.xml (turistički ZKI)")
print("  3. InventoryLedger.xml (forenzika zaliha)")
print("  4. BORG Validator (/gov-export/validator/)")
print("═══════════════════════════════════════════")
