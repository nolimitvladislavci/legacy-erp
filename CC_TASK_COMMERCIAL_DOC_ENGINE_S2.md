# CC TASK: Commercial Document Engine — Sprint 2 (AI Sloj)
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-27
## Preduvjet: Sprint 1 (CC_TASK_COMMERCIAL_DOC_ENGINE_S1.md) mora biti DONE

---

## OBAVEZNO PROČITAJ PRVO

```bash
# Provjeri Sprint 1 je završen
grep "class DocumentValidator\|fiscal_rules\|generate_monthly_sammelrechnung" invoicing/document_validator.py invoicing/fiscal_rules.py propter/tasks.py 2>/dev/null
venv/bin/python manage.py check
cat FENIX_STATUS.md | grep "Sprint 1"
```

---

## SPRINT 2A — AI Scan: foto/PDF → popuni Invoice

### Kontekst
Postoji: `ScanBatch`, `ScanBatchImage` s `ai_confidence` poljem
Postoji: `ConversionRecord` s AI metapodacima
Postoji: `Invoice.photo` polje
Treba: hook koji prima sliku → AI izvlači → popunjava Invoice form

### InvoiceScanService

Kreiraj `invoicing/ai_scan.py`:

```python
"""
invoicing/ai_scan.py
AI skeniranje dokumenata → automatsko popunjavanje Invoice forme.
Tokovi:
  1. Korisnik fotografira papirni račun → URA se popunjava
  2. PDF ponude dobavljača → Ponuda se pretvara u novu
  3. Vizitkartice / partneri → auto-fill client podataka
"""
import base64
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('invoicing.ai_scan')


@dataclass
class ExtractedDocument:
    """Rezultat AI ekstrakcije iz slike/PDF."""
    # Partner
    partner_name:    str = ''
    partner_oib:     str = ''
    partner_address: str = ''
    
    # Dokument
    doc_number:   str = ''
    doc_date:     str = ''
    due_date:     str = ''
    doc_type:     str = ''  # 'invoice', 'offer', 'delivery_note'
    
    # Iznosi
    subtotal:    float = 0.0
    tax_amount:  float = 0.0
    total:       float = 0.0
    tax_rate:    float = 25.0
    
    # Stavke
    items: list = field(default_factory=list)
    
    # Meta
    confidence:  float = 0.0
    needs_review: bool = True
    raw_text:    str = ''
    warnings:    list = field(default_factory=list)


def extract_from_image(image_path_or_bytes, country='HR') -> ExtractedDocument:
    """
    Pošalji sliku Claudeu i dobij strukturirane podatke dokumenta.
    Radi s: JPG, PNG, PDF (konvertiran u sliku), foto mobitela.
    """
    import anthropic
    import os
    
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    # Pripremi image bytes
    if isinstance(image_path_or_bytes, str):
        with open(image_path_or_bytes, 'rb') as f:
            image_bytes = f.read()
    else:
        image_bytes = image_path_or_bytes
    
    image_b64 = base64.b64encode(image_bytes).decode()
    
    # Odredi media type
    media_type = 'image/jpeg'
    if image_bytes[:4] == b'%PDF':
        # PDF → konvertuj prvu stranicu u sliku (ili pošalji direktno)
        media_type = 'image/jpeg'  # Nakon konverzije
    elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        media_type = 'image/png'
    
    country_context = 'Hrvatska (HR): OIB, PDV, fiskalizacija' if country == 'HR' else 'Deutschland (DE): Steuernummer/USt-IdNr, MwSt'
    
    prompt = f"""Analiziraj ovaj dokument i izvuci podatke u JSON formatu.
Zemlja kontekst: {country_context}

Vrati SAMO JSON, bez dodatnog teksta:
{{
  "partner_name": "naziv tvrtke/osobe",
  "partner_oib": "OIB ili Steuernummer (samo brojevi)",
  "partner_address": "adresa",
  "doc_number": "broj dokumenta",
  "doc_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD ili null",
  "doc_type": "invoice|offer|delivery_note|receipt|other",
  "subtotal": 0.00,
  "tax_amount": 0.00,
  "total": 0.00,
  "tax_rate": 25.0,
  "items": [
    {{
      "description": "naziv stavke",
      "quantity": 1.0,
      "unit_price": 0.00,
      "tax_rate": 25.0,
      "line_total": 0.00
    }}
  ],
  "confidence": 0-100,
  "warnings": ["lista upozorenja ako nešto nije jasno"],
  "raw_text": "cijeli prepoznati tekst"
}}

Ako nešto nije vidljivo, stavi null ili 0. Nikad ne pogađaj OIB/Steuernummer — ako nije jasno vidljiv, stavi "".
"""
    
    try:
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=2000,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': image_b64,
                        }
                    },
                    {'type': 'text', 'text': prompt}
                ]
            }]
        )
        
        import json
        raw = response.content[0].text.strip()
        # Ukloni markdown code blocks ako postoje
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        
        data = json.loads(raw)
        
        result = ExtractedDocument(
            partner_name=data.get('partner_name', ''),
            partner_oib=data.get('partner_oib', ''),
            partner_address=data.get('partner_address', ''),
            doc_number=data.get('doc_number', ''),
            doc_date=data.get('doc_date', ''),
            due_date=data.get('due_date', ''),
            doc_type=data.get('doc_type', 'invoice'),
            subtotal=float(data.get('subtotal', 0) or 0),
            tax_amount=float(data.get('tax_amount', 0) or 0),
            total=float(data.get('total', 0) or 0),
            tax_rate=float(data.get('tax_rate', 25) or 25),
            items=data.get('items', []),
            confidence=float(data.get('confidence', 0) or 0),
            needs_review=float(data.get('confidence', 0) or 0) < 85,
            raw_text=data.get('raw_text', ''),
            warnings=data.get('warnings', []),
        )
        
        logger.info('AI scan confidence: %.1f%% | partner: %s | total: %.2f',
                    result.confidence, result.partner_name, result.total)
        return result
    
    except Exception as e:
        logger.error('AI scan failed: %s', e)
        return ExtractedDocument(confidence=0, needs_review=True,
                                 warnings=[f'AI scan nije uspio: {str(e)}'])


def apply_to_invoice_form(extracted: ExtractedDocument, invoice_data: dict) -> dict:
    """
    Primijeni ekstrahirane podatke na invoice form data dict.
    Samo popunjava prazna polja — ne prepisuje ono što je korisnik unio.
    """
    if extracted.partner_name and not invoice_data.get('client_name'):
        invoice_data['client_name'] = extracted.partner_name
    
    if extracted.partner_oib and not invoice_data.get('client_oib'):
        invoice_data['client_oib'] = extracted.partner_oib
    
    if extracted.partner_address and not invoice_data.get('client_address'):
        invoice_data['client_address'] = extracted.partner_address
    
    if extracted.doc_number and not invoice_data.get('internal_id'):
        invoice_data['internal_id'] = extracted.doc_number
    
    if extracted.total and not invoice_data.get('total'):
        invoice_data['total'] = extracted.total
        invoice_data['subtotal'] = extracted.subtotal
        invoice_data['tax_amount'] = extracted.tax_amount
    
    # Metadata za review
    invoice_data['_ai_confidence'] = extracted.confidence
    invoice_data['_ai_needs_review'] = extracted.needs_review
    invoice_data['_ai_warnings'] = extracted.warnings
    
    return invoice_data
```

### API endpoint za scan

Dodati u `invoicing/views.py`:

```python
@login_required
def api_invoice_scan(request):
    """
    POST: image (file) → JSON s extracted podacima
    Frontend prima → pre-popunjava form
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'error': 'Nema slike'}, status=400)
    
    # Limit: 10MB
    if image_file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Slika prevelika (max 10MB)'}, status=400)
    
    from accounts.models import UserProfile
    try:
        company = UserProfile.objects.get(user=request.user).company
        country = getattr(company, 'country', 'HR') or 'HR'
    except Exception:
        country = 'HR'
    
    from invoicing.ai_scan import extract_from_image
    extracted = extract_from_image(image_file.read(), country=country)
    
    return JsonResponse({
        'success': True,
        'confidence': extracted.confidence,
        'needs_review': extracted.needs_review,
        'data': {
            'client_name':    extracted.partner_name,
            'client_oib':     extracted.partner_oib,
            'client_address': extracted.partner_address,
            'internal_id':    extracted.doc_number,
            'total':          extracted.total,
            'subtotal':       extracted.subtotal,
            'tax_amount':     extracted.tax_amount,
            'items':          extracted.items,
        },
        'warnings': extracted.warnings,
    })
```

URL dodati:
```python
path('api/scan/', views.api_invoice_scan, name='api_invoice_scan'),
```

### UI hook (u create.html)

```javascript
// Dodati "Skeniranje" gumb u invoice create form
document.getElementById('scan-btn').addEventListener('click', async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*,application/pdf';
    input.capture = 'environment'; // kamera na mobitelu
    
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        showLoadingOverlay('AI skenira dokument...');
        
        const formData = new FormData();
        formData.append('image', file);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        
        const resp = await fetch('/hr/invoicing/api/scan/', {
            method: 'POST',
            body: formData,
        });
        const data = await resp.json();
        hideLoadingOverlay();
        
        if (data.success) {
            // Popuni form
            if (data.data.client_name) setFormField('client_name', data.data.client_name);
            if (data.data.client_oib)  setFormField('client_oib',  data.data.client_oib);
            if (data.data.total)       setFormField('total',        data.data.total);
            
            if (data.confidence < 85) {
                showWarning(`AI pouzdanost: ${data.confidence}% — molimo provjerite podatke`);
            }
            if (data.warnings.length) {
                showWarnings(data.warnings);
            }
        }
    };
    input.click();
});
```

---

## SPRINT 2B — Compliance Watchdog Proširenje

Kreiraj Gemini task file (pozvat će se iz Celery):

```python
# limit_connect_ai/services/invoice_compliance_watchdog.py

"""
Svaki tjedan provjeri:
1. Ima li firmi s pogrešnim PDV stopama na artiklima
2. Ima li avansnih računa bez završnih > 90 dana
3. Ima li DE računa bez e-Rechnung oznake (od 2025)
4. Ima li firmi s fiscal_exempt=False koji bi trebali biti exempt
5. Novi propisi (NN RSS + EUR-Lex) koji utječu na faktiriranje

Rezultat: lista ComplianceWatchItem zapisa + obavijest adminu
"""

def run_invoice_compliance_check(company):
    """Provjeri jednu firmu."""
    from invoicing.models import Invoice, InvoiceItem
    from inventory.models import InventoryItem
    from django.utils import timezone
    from datetime import timedelta
    from limit_connect_ai.models import ComplianceWatchItem
    
    today = timezone.now().date()
    issues = []
    
    # 1. PDV stope
    nkd = getattr(company, 'nkd_code', None)
    if nkd:
        nkd_code = getattr(nkd, 'code', '')
        food_nkds = ('10.', '47.2', '56.', '01.')
        if any(nkd_code.startswith(x) for x in food_nkds):
            wrong_rate = InventoryItem.objects.filter(
                company=company,
                tax_rate=25,
            ).count()
            if wrong_rate > 0:
                issues.append({
                    'category': 'PDV',
                    'severity': 'high',
                    'title': f'{wrong_rate} artikala s PDV 25% u prehrambenoj djelatnosti',
                    'description': f'NKD {nkd_code} → trebali bi biti PDV 5%. Provjeri artikle.',
                    'action_url': '/hr/inventory/',
                })
    
    # 2. Avansni bez završnog > 90 dana
    avans_stari = Invoice.objects.filter(
        company=company,
        doctype='A',
        date_issued__date__lt=today - timedelta(days=90),
        status__in=('CONFIRMED', 'SENT', 'PAID'),
    ).count()
    if avans_stari:
        issues.append({
            'category': 'AVANS',
            'severity': 'medium',
            'title': f'{avans_stari} avansnih računa bez završnog (>90 dana)',
            'description': 'Porezna uprava može tražiti objašnjenje za nezatvorene predujmove.',
            'action_url': '/hr/invoicing/?doctype=A',
        })
    
    # 3. DE e-Rechnung (od 2025)
    if getattr(company, 'country', 'HR') == 'DE':
        de_bez_eracun = Invoice.objects.filter(
            company=company,
            doctype__in=('R', 'FA'),
            date_issued__year__gte=2025,
        ).exclude(
            status='STORNO'
        ).count()
        if de_bez_eracun > 0:
            issues.append({
                'category': 'DE_COMPLIANCE',
                'severity': 'high',
                'title': f'{de_bez_eracun} DE B2B računa bez e-Rechnung oznake',
                'description': 'Od 01.01.2025. B2B e-Rechnung obvezan u DE (§14 UStG).',
                'action_url': '/hr/einvoice/',
            })
    
    # Kreiraj ComplianceWatchItem za svaki problem
    for issue in issues:
        ComplianceWatchItem.objects.get_or_create(
            company=company,
            category=issue['category'],
            defaults={
                'title': issue['title'],
                'description': issue['description'],
                'severity': issue['severity'],
                'is_active': True,
                'action_url': issue.get('action_url', ''),
            }
        )
    
    return len(issues)
```

---

## SPRINT 2C — One A4 Master Template

### Kreiraj `invoicing/templates/invoicing/invoice_master.html`

Struktura:
```
invoice_master.html
  → učitava context processorom:
    - doctype → bira blokove
    - country → bira legal footer
    - is_sammelrechnung → dodaje OTP popis
```

```html
{% comment %}
invoice_master.html — Jedini A4 template za sve vrste dokumenata
Zamjenjuje: invoice_hr.html, invoice_de.html, invoice_hr_modern.html,
            invoice_de_modern.html, invoice_bilingual.html
{% endcomment %}
{% load i18n static %}
<!DOCTYPE html>
<html lang="{{ invoice.country|lower }}">
<head>
<meta charset="UTF-8">
<style>
  /* Profesionalni A4 CSS */
  @page { size: A4; margin: 15mm 20mm 15mm 20mm; }
  body { font-family: 'Arial', sans-serif; font-size: 10pt; color: #1a1a1a; }
  .header { display: flex; justify-content: space-between; margin-bottom: 8mm; }
  .logo img { max-height: 20mm; }
  .doc-title { font-size: 18pt; font-weight: bold; color: #0F2B4C; }
  .doc-number { font-size: 10pt; color: #666; }
  .parties { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; margin: 5mm 0; }
  .party-box { border: 0.3mm solid #ddd; padding: 3mm; border-radius: 1mm; }
  .party-label { font-size: 7pt; color: #888; text-transform: uppercase; margin-bottom: 1mm; }
  table.items { width: 100%; border-collapse: collapse; margin: 5mm 0; }
  table.items th { background: #0F2B4C; color: white; padding: 2mm 3mm; font-size: 9pt; }
  table.items td { padding: 2mm 3mm; border-bottom: 0.2mm solid #eee; font-size: 9pt; }
  table.items tr:nth-child(even) td { background: #f8f9fa; }
  .totals { margin-left: auto; width: 70mm; }
  .totals table { width: 100%; }
  .totals .grand-total { font-size: 13pt; font-weight: bold; color: #0F2B4C; }
  .legal-footer { margin-top: 8mm; padding-top: 3mm; border-top: 0.3mm solid #ddd; font-size: 8pt; color: #888; }
  .qr-block { position: absolute; bottom: 20mm; right: 20mm; }
  .sammel-list { font-size: 8pt; margin: 3mm 0; background: #f5f7fa; padding: 3mm; border-radius: 1mm; }
  .fiscal-badge { font-size: 7pt; color: #28a745; }
  .watermark { opacity: 0.08; font-size: 60pt; transform: rotate(-30deg); position: fixed; top: 50%; left: 20%; color: #0F2B4C; pointer-events: none; }
  @media print { .no-print { display: none; } }
</style>
</head>
<body>

{% if invoice.status == 'DRAFT' %}
<div class="watermark">NACRT</div>
{% endif %}

<!-- HEADER -->
<div class="header">
  <div class="logo">
    {% if invoice.company.logo %}
      <img src="{{ invoice.company.logo.url }}">
    {% else %}
      <div class="doc-company-name" style="font-size:14pt;font-weight:bold;color:#0F2B4C;">{{ invoice.company.name }}</div>
    {% endif %}
  </div>
  <div style="text-align:right;">
    <div class="doc-title">
      {% if invoice.doctype == 'PO' %}{% trans "PONUDA" %}{% if invoice.country == 'DE' %} / ANGEBOT{% endif %}
      {% elif invoice.doctype == 'P' %}{% trans "PREDRAČUN" %}{% if invoice.country == 'DE' %} / KOSTENVORANSCHLAG{% endif %}
      {% elif invoice.doctype == 'OTP' %}{% trans "OTPREMNICA" %}{% if invoice.country == 'DE' %} / LIEFERSCHEIN{% endif %}
      {% elif invoice.doctype == 'ZR' %}{% trans "ZBIRNI RAČUN" %}{% if invoice.country == 'DE' %} / SAMMELRECHNUNG{% endif %}
      {% elif invoice.doctype == 'NAR' %}{% trans "NARUDŽBENICA" %}{% if invoice.country == 'DE' %} / BESTELLUNG{% endif %}
      {% elif invoice.doctype == 'A' %}{% trans "AVANSNI RAČUN" %}{% if invoice.country == 'DE' %} / ABSCHLAGSRECHNUNG{% endif %}
      {% elif invoice.doctype == 'S' %}{% trans "STORNO RAČUN" %}{% if invoice.country == 'DE' %} / STORNORECHNUNG{% endif %}
      {% elif invoice.doctype == 'GS' %}GUTSCHRIFT
      {% else %}{% trans "RAČUN" %}{% if invoice.country == 'DE' %} / RECHNUNG{% endif %}
      {% endif %}
    </div>
    <div class="doc-number">Br. / Nr.: <strong>{{ invoice.number }}</strong></div>
    <div style="font-size:9pt;">{% trans "Datum" %}: {{ invoice.date_issued|date:"d.m.Y." }}</div>
    {% if invoice.date_due %}<div style="font-size:9pt;">{% trans "Rok plaćanja" %} / Fälligkeit: {{ invoice.date_due|date:"d.m.Y." }}</div>{% endif %}
    {% if invoice.date_delivery %}<div style="font-size:9pt;">{% trans "Datum isporuke" %} / Leistungsdatum: {{ invoice.date_delivery|date:"d.m.Y." }}</div>{% endif %}
  </div>
</div>

<!-- PARTIES -->
<div class="parties">
  <div class="party-box">
    <div class="party-label">{% trans "Izdavatelj" %} / Absender</div>
    <strong>{{ invoice.issuer_name|default:invoice.company.name }}</strong><br>
    {{ invoice.issuer_address|default:invoice.company.address|linebreaksbr }}<br>
    {% if invoice.country == 'HR' %}OIB: {{ invoice.issuer_oib|default:invoice.company.oib }}
    {% else %}St-Nr./USt-IdNr.: {{ invoice.issuer_oib|default:invoice.company.vat_id }}
    {% endif %}<br>
    {% if invoice.iban %}IBAN: {{ invoice.iban }}{% endif %}
  </div>
  <div class="party-box">
    <div class="party-label">{% trans "Primatelj" %} / Empfänger</div>
    <strong>{{ invoice.client_name }}</strong><br>
    {{ invoice.client_address|linebreaksbr }}<br>
    {% if invoice.client_oib %}
      {% if invoice.country == 'HR' %}OIB: {{ invoice.client_oib }}
      {% else %}USt-IdNr./St-Nr.: {{ invoice.client_oib }}
      {% endif %}
    {% endif %}
    {% if invoice.client_email %}<br>{{ invoice.client_email }}{% endif %}
  </div>
</div>

<!-- SAMMELRECHNUNG blok (samo za ZR) -->
{% if invoice.doctype == 'ZR' and invoice.note %}
<div class="sammel-list">
  <strong>{% trans "Uključene otpremnice" %} / Enthaltene Lieferscheine:</strong><br>
  {{ invoice.note|linebreaksbr }}
</div>
{% endif %}

<!-- AVANS reference -->
{% if invoice.doctype in 'R,FA' and invoice.related_invoice %}
<div style="font-size:9pt;background:#fff3cd;padding:2mm;margin:3mm 0;border-radius:1mm;">
  {% trans "Odbitak predujma po" %} {{ invoice.related_invoice.number }} od {{ invoice.related_invoice.date_issued|date:"d.m.Y." }}
</div>
{% endif %}

<!-- STAVKE -->
<table class="items">
  <thead>
    <tr>
      <th style="width:5%">#</th>
      <th style="width:45%">{% trans "Opis" %} / Bezeichnung</th>
      <th style="width:10%;text-align:right">{% trans "Kol." %}</th>
      <th style="width:8%">{% trans "JM" %}</th>
      <th style="width:12%;text-align:right">{% trans "Jed.cijena" %}</th>
      <th style="width:8%;text-align:right">PDV/%</th>
      <th style="width:12%;text-align:right">{% trans "Iznos" %}</th>
    </tr>
  </thead>
  <tbody>
    {% for item in invoice.items.all %}
    <tr>
      <td>{{ forloop.counter }}</td>
      <td>{{ item.description }}</td>
      <td style="text-align:right">{{ item.quantity }}</td>
      <td>{{ item.unit|default:"kom" }}</td>
      <td style="text-align:right">{{ item.unit_price|floatformat:2 }} {{ invoice.currency }}</td>
      <td style="text-align:right">{{ item.tax_percent|floatformat:0 }}%</td>
      <td style="text-align:right">{{ item.total|floatformat:2 }} {{ invoice.currency }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<!-- TOTALI -->
<div class="totals">
  <table>
    <tr><td>{% trans "Osnovica" %} / Nettobetrag:</td><td style="text-align:right">{{ invoice.subtotal|floatformat:2 }} {{ invoice.currency }}</td></tr>
    <tr><td>{% if invoice.country == 'HR' %}PDV {{ invoice.tax_percent|floatformat:0 }}%:{% else %}MwSt {{ invoice.tax_percent|floatformat:0 }}%:{% endif %}</td><td style="text-align:right">{{ invoice.tax_amount|floatformat:2 }} {{ invoice.currency }}</td></tr>
    {% if invoice.related_invoice and invoice.doctype in 'R,FA' %}
    <tr><td style="color:#c0392b;">{% trans "Odbitak predujma" %}:</td><td style="text-align:right;color:#c0392b;">- {{ invoice.related_invoice.total|floatformat:2 }} {{ invoice.currency }}</td></tr>
    {% endif %}
    <tr class="grand-total"><td><strong>{% trans "UKUPNO" %} / GESAMT:</strong></td><td style="text-align:right"><strong>{{ invoice.total|floatformat:2 }} {{ invoice.currency }}</strong></td></tr>
  </table>
</div>

<!-- PLAĆANJE -->
{% if invoice.doctype not in 'PO,P,OTP,NAR' %}
<div style="margin-top:5mm;font-size:9pt;">
  {% if invoice.payment_method == 'VIRMAN' or invoice.payment_method == 'TRANSFER' %}
    IBAN: {{ invoice.iban }} | SWIFT: {{ invoice.swift|default:"-" }}<br>
    {% if invoice.country == 'HR' %}Poziv na broj: {{ invoice.reference_number|default:invoice.number }}{% endif %}
  {% endif %}
  {% if invoice.note %}<br><em>{{ invoice.note }}</em>{% endif %}
</div>
{% endif %}

<!-- LEGAL FOOTER — HR -->
{% if invoice.country == 'HR' %}
<div class="legal-footer">
  {% if invoice.is_fiscalized %}
    <span class="fiscal-badge">✓ Fiskalizirano</span> | 
    JIR: {{ invoice.jir }} | ZKI: {{ invoice.zki }}<br>
    Datum fiskalizacije: {{ invoice.fiscal_datetime|date:"d.m.Y. H:i" }}
  {% endif %}
  {% if invoice.doctype == 'ZR' %}
    Zbirni račun izdan sukladno čl. 79. Zakona o PDV-u. Otpremnice su sastavni dio ovog računa.
  {% endif %}
  {% if invoice.company.is_vat_registered %}
    PDV registracija: {{ invoice.company.vat_id|default:invoice.company.oib }}
  {% else %}
    Nije obveznik PDV-a sukladno čl. 90. Zakona o PDV-u (NN 73/13).
  {% endif %}
</div>
{% endif %}

<!-- LEGAL FOOTER — DE -->
{% if invoice.country == 'DE' %}
<div class="legal-footer">
  {% if invoice.doctype == 'ZR' %}
    Sammelrechnung für den Abrechnungszeitraum. Die zugehörigen Lieferscheine sind Bestandteil dieser Rechnung (§14 Abs.4 UStG, §31 UStDV).
  {% endif %}
  {% if invoice.company.is_kleinunternehmer %}
    Kein Ausweis von Umsatzsteuer, da Kleinunternehmer gemäß § 19 UStG.
  {% else %}
    Steuernummer: {{ invoice.issuer_oib|default:invoice.company.vat_id }}
    Leistungszeitraum: {{ invoice.date_delivery|date:"d.m.Y."|default:"entspricht Rechnungsdatum" }}
  {% endif %}
  Aufbewahrungsfrist: 10 Jahre gemäß §14b UStG / §147 AO.
</div>
{% endif %}

<!-- QR (samo HR fiskalizirani) -->
{% if invoice.qr_code_base64 and invoice.is_fiscalized %}
<div class="qr-block">
  <img src="data:image/png;base64,{{ invoice.qr_code_base64 }}" style="width:25mm;height:25mm;">
</div>
{% endif %}

</body>
</html>
```

### Zamijeni stare templatee u views

```bash
# Nađi sve pozive starih templatea
grep -rn "invoice_hr.html\|invoice_de.html\|invoice_hr_modern\|invoice_de_modern\|invoice_bilingual" invoicing/views.py
```

Zamijeni sve s `'invoicing/invoice_master.html'`.

---

## DONE KRITERIJ Sprint 2

```bash
# AI scan endpoint
curl -X POST https://limit-connect.com/hr/invoicing/api/scan/ \
  -H "X-CSRFToken: test" \
  -F "image=@/tmp/test_invoice.jpg" | head -50

# Master template dostupan
ls invoicing/templates/invoicing/invoice_master.html

# Compliance checker
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from limit_connect_ai.services.invoice_compliance_watchdog import run_invoice_compliance_check
from companies.models import Company
c = Company.objects.first()
issues = run_invoice_compliance_check(c)
print('Issues found:', issues)
"

venv/bin/python manage.py check
git log --oneline -6
```
