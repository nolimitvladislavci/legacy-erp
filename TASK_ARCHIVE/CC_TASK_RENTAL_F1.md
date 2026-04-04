# CC_TASK_RENTAL_F1 — Modeli + OCR + eVisitor + Račun
## Agent: Claude Code | Prioritet: P0

**Čitaj:** RENTAL_MASTER_PLAN.md, rental/models.py (OBAVEZNO!)  
**Ne pretpostavljaj polja — cat models.py je bio obavezan.**

---

## ZADATAK 1: Novi modeli — Guest i GuestDocument

Booking model ima guest_name/email/phone, ali **nema višestruke goste po bookingu** 
(obitelj = 4 osobe) i nema **dokumente**.

```python
# rental/models.py — dodaj

class Guest(models.Model):
    """Jedan gost u rezervaciji. Booking može imati više gostiju."""
    
    SEX_CHOICES = [('M','Muški'),('F','Ženski'),('X','Ostalo')]
    
    booking = models.ForeignKey(
        'Booking', on_delete=models.CASCADE, related_name='guests'
    )
    
    # Osnovni podaci (auto-popunjeno iz OCR)
    first_name    = models.CharField(max_length=100)
    last_name     = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    sex           = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True)
    nationality   = models.CharField(max_length=3, blank=True)  # ISO 3166 kod
    
    # Dokument
    document_type   = models.CharField(max_length=20, blank=True)  # passport, id_card
    document_number = models.CharField(max_length=30, blank=True)
    document_country= models.CharField(max_length=3, blank=True)
    document_expiry = models.DateField(null=True, blank=True)
    
    # eVisitor specific
    residence_country = models.CharField(max_length=3, blank=True)
    residence_city    = models.CharField(max_length=100, blank=True)
    
    # Status
    is_primary        = models.BooleanField(default=False)  # glavni gost
    evisitor_synced   = models.BooleanField(default=False)
    evisitor_synced_at= models.DateTimeField(null=True, blank=True)
    
    # GDPR
    consent_given    = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'last_name']
    
    def __str__(self):
        return f'{self.first_name} {self.last_name}'
    
    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def tourist_tax_category(self):
        """Kategorija boravišne pristojbe po dobi."""
        if not self.date_of_birth:
            return 'odrasli'
        from django.utils import timezone
        age = (timezone.now().date() - self.date_of_birth).days // 365
        if age < 12:
            return 'besplatno'
        elif age < 18:
            return 'popust_50'
        return 'odrasli'


class GuestDocument(models.Model):
    """Slika dokumenta gosta (za OCR i arhivu)."""
    
    guest   = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='documents')
    image   = models.ImageField(upload_to='guest_docs/%Y/%m/')
    
    # OCR rezultat
    ocr_raw       = models.JSONField(default=dict, blank=True)  # sirovi MRZ podaci
    ocr_confidence= models.FloatField(default=0.0)
    ocr_processed = models.BooleanField(default=False)
    
    # GDPR — automatsko brisanje
    delete_after  = models.DateTimeField(null=True, blank=True)  # 24h nakon check-outa
    
    created_at = models.DateTimeField(auto_now_add=True)


class RentalInvoice(models.Model):
    """Račun za boravak — vezan za Booking i Invoice modul."""
    
    booking     = models.OneToOneField('Booking', on_delete=models.CASCADE, related_name='rental_invoice')
    invoice     = models.OneToOneField(
        'invoicing.Invoice', on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Kalkulacija
    accommodation_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tourist_tax_total   = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cleaning_fee        = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total               = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Storniran/ispravljen
    is_cancelled  = models.BooleanField(default=False)
    
    created_at    = models.DateTimeField(auto_now_add=True)
    sent_at       = models.DateTimeField(null=True, blank=True)
    sent_to_email = models.EmailField(blank=True)
    sent_via_wa   = models.BooleanField(default=False)


class TrafficRecord(models.Model):
    """Evidencija o prometu (Obrazac EP) — zakonska obveza."""
    
    company       = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    rental_property = models.ForeignKey('rental.Property', on_delete=models.CASCADE, null=True, blank=True)
    booking       = models.ForeignKey('Booking', on_delete=models.SET_NULL, null=True, blank=True)
    
    # EP obrazac polja
    date          = models.DateField()
    invoice_number= models.CharField(max_length=30)
    guest_name    = models.CharField(max_length=200)
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    tourist_tax   = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total         = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at    = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date']
        verbose_name = 'EP Evidencija prometa'
```

---

## ZADATAK 2: OCR MRZ pipeline

Svaki dokument ima MRZ (Machine Readable Zone) — dva reda na dnu putovnice/osobne.

```python
# rental/ocr.py

def extract_mrz_with_haiku(image_path: str) -> dict:
    """
    Haiku Vision čita MRZ iz slike dokumenta.
    
    MRZ format primjer (putovnica):
    P<HRCBRTAN<<IVAN<<<<<<<<<<<<<<<<<<<<<
    AB123456<0HRC9101011M2601011<<<<<<<<<2
    
    Returns: {
        'first_name': 'IVAN',
        'last_name': 'BRTAN',
        'date_of_birth': '1991-01-01',
        'document_number': 'AB123456',
        'nationality': 'HRC',
        'sex': 'M',
        'expiry_date': '2026-01-01',
        'document_type': 'passport',
        'confidence': 0.95,
    }
    """
    import anthropic, base64
    
    with open(image_path, 'rb') as f:
        data = f.read()
    
    mime = 'image/jpeg'
    if data[:4] == bytes([0x89, 0x50, 0x4e, 0x47]):
        mime = 'image/png'
    
    client = anthropic.Anthropic()
    
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=400,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': mime,
                        'data': base64.b64encode(data).decode()
                    }
                },
                {
                    'type': 'text',
                    'text': '''Pročitaj MRZ (Machine Readable Zone) s ovog dokumenta i ekstrahiraj podatke.
MRZ su redovi s velikim slovima, brojevima i znakovima "<" na dnu dokumenta.

Vrati SAMO JSON bez komentara:
{
  "document_type": "passport|id_card|driving_license|unknown",
  "first_name": "",
  "last_name": "",
  "date_of_birth": "YYYY-MM-DD ili null",
  "document_number": "",
  "nationality": "3-slovna ISO šifra npr HRV DEU AUT",
  "sex": "M|F|X",
  "expiry_date": "YYYY-MM-DD ili null",
  "issuing_country": "3-slovna ISO šifra",
  "confidence": 0.95
}

Ako ne možeš pročitati MRZ, postavi confidence=0.0 i prazne stringove.
NE kopaj fotkane podatke osim iz MRZ zone — samo strojno čitljivi dio.'''
                }
            ]
        }]
    )
    
    import json, re
    text = msg.content[0].text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        result = json.loads(match.group())
        # Normalize nationality
        if result.get('nationality') == 'HRC':
            result['nationality'] = 'HRV'
        return result
    
    return {'confidence': 0.0, 'document_type': 'unknown'}


def apply_ocr_to_guest(guest_document_pk: int) -> dict:
    """Celery-friendly funkcija: OCR → popuni Guest polja."""
    from rental.models import GuestDocument, Guest
    
    doc = GuestDocument.objects.get(pk=guest_document_pk)
    result = extract_mrz_with_haiku(doc.image.path)
    
    doc.ocr_raw = result
    doc.ocr_confidence = result.get('confidence', 0)
    doc.ocr_processed = True
    doc.save()
    
    if result.get('confidence', 0) > 0.5:
        guest = doc.guest
        if result.get('first_name') and not guest.first_name:
            guest.first_name = result['first_name'].title()
        if result.get('last_name') and not guest.last_name:
            guest.last_name = result['last_name'].title()
        if result.get('date_of_birth'):
            from datetime import date
            try:
                guest.date_of_birth = date.fromisoformat(result['date_of_birth'])
            except Exception:
                pass
        if result.get('document_number'):
            guest.document_number = result['document_number']
        if result.get('nationality'):
            guest.nationality = result['nationality']
        if result.get('sex'):
            guest.sex = result['sex']
        if result.get('document_type'):
            guest.document_type = result['document_type']
        guest.save()
    
    return result
```

---

## ZADATAK 3: eVisitor XML export

```python
# rental/evisitor.py

def build_evisitor_xml(booking, guests=None) -> str:
    """
    Generira XML za eVisitor API.
    
    eVisitor prima XML u formatu koji propisuje HTZ.
    Ovo je lokalni XML — NE šaljemo direktno (nemamo API ključ).
    Iznajmljivač ga može ručno uploadati na eVisitor.hr.
    
    Returns: XML string
    """
    from xml.etree.ElementTree import Element, SubElement, tostring, indent
    import xml.etree.ElementTree as ET
    from django.utils import timezone
    
    if guests is None:
        guests = booking.guests.all()
    
    root = Element('eVisitorImport')
    root.set('version', '1.0')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    
    for guest in guests:
        prijava = SubElement(root, 'Prijava')
        
        SubElement(prijava, 'VrstaPrijave').text = 'DOLAZAK'
        SubElement(prijava, 'NazivObjekta').text = booking.rental_property.name
        SubElement(prijava, 'DatumDolaska').text = booking.check_in.strftime('%Y-%m-%d')
        SubElement(prijava, 'DatumOdlaska').text = booking.check_out.strftime('%Y-%m-%d')
        
        SubElement(prijava, 'Ime').text = guest.first_name
        SubElement(prijava, 'Prezime').text = guest.last_name
        SubElement(prijava, 'DatumRodenja').text = (
            guest.date_of_birth.strftime('%Y-%m-%d') if guest.date_of_birth else ''
        )
        SubElement(prijava, 'Spol').text = guest.sex or 'M'
        SubElement(prijava, 'Drzavljanstvo').text = guest.nationality or 'HRV'
        SubElement(prijava, 'VrstaDokumenta').text = guest.document_type or 'putovnica'
        SubElement(prijava, 'BrojDokumenta').text = guest.document_number or ''
        SubElement(prijava, 'DrzavaIzdavanjaDokumenta').text = guest.document_country or guest.nationality or 'HRV'
        SubElement(prijava, 'DrzavaBoravistaStanovnistva').text = guest.residence_country or guest.nationality or 'HRV'
    
    ET.indent(root, space='  ')
    xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
```

---

## ZADATAK 4: Automatski račun iz Bookinga

```python
# rental/invoice_service.py

def create_rental_invoice(booking) -> 'RentalInvoice':
    """
    Kreira Invoice iz bookinga i veže ga za RentalInvoice.
    Koristi postojeći invoicing.Invoice model.
    """
    from invoicing.models import Invoice, InvoiceItem
    from rental.models import RentalInvoice
    from decimal import Decimal
    
    # Izračun
    nights = (booking.check_out - booking.check_in).days
    acc_total = booking.price_per_night * nights
    
    guest_count = booking.guests.count() or booking.guest_count
    tt_total = booking.rental_property.tourist_tax * guest_count * nights
    cleaning = booking.rental_property.cleaning_fee
    total = acc_total + tt_total + cleaning
    
    # Kreira Invoice
    invoice = Invoice.objects.create(
        company=booking.company,
        doctype='R',
        client_name=booking.guest_name,
        client_email=booking.guest_email,
        date_issued=booking.actual_check_out.date() if booking.actual_check_out else booking.check_out,
        date_due=booking.actual_check_out.date() if booking.actual_check_out else booking.check_out,
        subtotal=acc_total + cleaning,
        tax_amount=Decimal('0'),  # paušalci ne zaračunavaju PDV
        total=total,
        tax_percent=Decimal('0'),
        currency='EUR',
        note=f'Boravak: {booking.check_in} — {booking.check_out} | {booking.rental_property.name}',
    )
    
    # Stavke
    InvoiceItem.objects.create(
        invoice=invoice,
        description=f'Smještaj {booking.rental_property.name} ({nights} noći × {booking.price_per_night}€)',
        quantity=nights,
        unit='noć',
        unit_price=booking.price_per_night,
        total_price=acc_total,
        tax_rate=Decimal('0'),
    )
    
    if tt_total > 0:
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f'Boravišna pristojba ({guest_count} osoba × {nights} noći × {booking.rental_property.tourist_tax}€)',
            quantity=1,
            unit='pau',
            unit_price=tt_total,
            total_price=tt_total,
            tax_rate=Decimal('0'),
        )
    
    if cleaning > 0:
        InvoiceItem.objects.create(
            invoice=invoice,
            description='Naknada za čišćenje',
            quantity=1,
            unit='pau',
            unit_price=cleaning,
            total_price=cleaning,
            tax_rate=Decimal('0'),
        )
    
    # RentalInvoice
    ri = RentalInvoice.objects.create(
        booking=booking,
        invoice=invoice,
        accommodation_total=acc_total,
        tourist_tax_total=tt_total,
        cleaning_fee=cleaning,
        total=total,
    )
    
    # ArhivaEntry
    from documents.models import ArhivaEntry
    ArhivaEntry.objects.create(
        company=booking.company,
        source_type='rental_invoice',
        source_id=str(invoice.pk),
        doc_number=invoice.number,
        doc_date=invoice.date_issued,
        partner_name=booking.guest_name,
        amount=total,
        currency='EUR',
    )
    
    return ri
```

---

## ZADATAK 5: Migrations

```bash
venv/bin/python manage.py makemigrations rental
venv/bin/python manage.py migrate rental
```

---

## DONE kriterij

```bash
venv/bin/python manage.py test rental --verbosity=2
# Mora proći:
# test_guest_tourist_tax_category — dijete < 12 = besplatno
# test_create_rental_invoice — booking → invoice → arhiva
# test_mrz_ocr_returns_dict — mock Haiku, provjeri strukturu
# test_evisitor_xml_valid — XML parsira se bez greške
```
