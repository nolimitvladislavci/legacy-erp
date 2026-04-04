# CC TASK: Commercial Document Engine — Sprint 1 (Žičanje)
## Agent: CC Code | Prioritet: KRITIČAN | Datum: 2026-03-27
## Autonomija: Sonnet ovlastio — radi bez odobrenja, commitaj svaki sprint zasebno

---

## OBAVEZNO PROČITAJ PRVO

```bash
cat FENIX_STATUS.md | head -30
git log --oneline -5
# ČITAJ modele prije pisanja koda:
cat propter/models.py
cat invoicing/models.py | head -200
cat invoicing/signals.py
venv/bin/python manage.py check
```

---

## KONTEKST — ŠTO POSTOJI (ne graditi iznova)

### propter.Otpremnica (GOTOV model, 0 korištenja)
- BillingPeriod veza — skuplja OTP kroz mjesec
- Status: DRAFT→ISSUED→AGGREGATED→CANCELLED
- Source: POS/MANUAL/SYNESIS/API/INVOICE
- auto-number, auto billing_period_assignment
- OtpremnicaItem s EN 16931 unit kodovima

### invoicing.Invoice (GOTOV model)
- doctype: PO/P/R/A/S/GS/FA/URA/RN
- source_document FK (samo na Invoice, treba proširiti)
- related_invoice FK (storno/avans veza)
- signals.py → auto-knjiženje u konto
- Company.fiscal_exempt — postoji
- InventoryItem.is_nonprofit_activity — postoji

### propter.BillingPeriod (GOTOV model)
- otpremnica_count: 0 svuda — nikad nije wire-an

---

## SPRINT 1A — Novi doctypes i model proširenja

### 1. Dodaj doctypes u Invoice

```python
# invoicing/models.py — u DOCTYPE_CHOICES dodaj:
('OTP', _('Otpremnica (Lieferschein)')),
('ZR',  _('Zbirni račun (Sammelrechnung)')),
('NAR', _('Narudžbenica')),
```

### 2. Provjeri treba li migracija

Ako `doctype` CharField max_length >= 3, nije potrebna.
```bash
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from invoicing.models import Invoice
f = Invoice._meta.get_field('doctype')
print('max_length:', f.max_length)
"
```
Ako < 3, povećaj max_length i napravi migraciju.

### 3. Fiskalizacija decision engine

Kreiraj `invoicing/fiscal_rules.py`:

```python
"""
invoicing/fiscal_rules.py
Centralni engine za odluku o fiskalizaciji.
Korisnik NIKAD ne mora ručno odlučivati.
"""
from typing import Tuple


# Doctypes koji NIKAD ne idu na fiskalizaciju
NON_FISCAL_DOCTYPES = frozenset({
    'PO',   # Ponuda
    'P',    # Predračun
    'OTP',  # Otpremnica
    'ZR',   # Zbirni račun
    'NAR',  # Narudžbenica
    'URA',  # Ulazni račun
})

# Doctypes koji UVIJEK idu na fiskalizaciju (HR)
FISCAL_DOCTYPES_HR = frozenset({
    'R', 'R1', 'R2', 'RN', 'A', 'S',
})


def should_fiscalize(invoice) -> Tuple[bool, str]:
    """
    Centralna odluka: ide li račun na HR fiskalizaciju?
    
    Vraća: (True/False, razlog_string)
    Korisnik vidi samo razlog ako je False — ne mora birati.
    """
    company = invoice.company

    # 1. DE račun — ne HR fiskalizacija
    if getattr(invoice, 'country', 'HR') == 'DE':
        return False, 'DE račun — DSFinV-K, ne HR fiskalizacija'

    # 2. Firma je generalno exempt
    if getattr(company, 'fiscal_exempt', False):
        return False, 'Firma nije obveznik fiskalizacije'

    # 3. Doctype koji nikad ne ide
    if invoice.doctype in NON_FISCAL_DOCTYPES:
        return False, f'Vrsta dokumenta {invoice.doctype} ne fiskalizira se'

    # 4. Udruga s nonprofit artiklima
    if company.business_type in ('udruga', 'ustanova'):
        try:
            items = invoice.items.all()
            if items.exists():
                all_nonprofit = all(
                    getattr(i.inventory_item, 'is_nonprofit_activity', False)
                    for i in items
                    if i.inventory_item_id
                )
                if all_nonprofit:
                    return False, 'Svi artikli su nonprofit aktivnost udruge'
        except Exception:
            pass

    # 5. Iznos 0 — ne fiskalizira se
    if getattr(invoice, 'total', 0) == 0:
        return False, 'Nulti iznos — fiskalizacija nije potrebna'

    # 6. HR gotovinski/bezgotovinski — ide
    if invoice.doctype in FISCAL_DOCTYPES_HR:
        return True, 'HR fiskalizacija obvezna'

    return False, 'Nije prepoznat slučaj za fiskalizaciju'


def get_pdv_rate_for_item(item, company) -> Tuple[float, str]:
    """
    AI provjera PDV stope — je li stopa ispravna za NKD?
    Vraća: (stopa, upozorenje_ili_None)
    """
    nkd = getattr(company, 'nkd_code', None)
    nkd_code = getattr(nkd, 'code', '') if nkd else ''

    # Prehrambeni sektor: NKD 10.x, 47.2x → PDV 5%
    food_nkds = ('10.', '47.2', '56.', '01.')
    if any(nkd_code.startswith(x) for x in food_nkds):
        if getattr(item, 'tax_rate', 25) == 25:
            return 5.0, f'NKD {nkd_code} → trebao bi biti PDV 5%, a postavljeno je 25%'

    return getattr(item, 'tax_rate', 25), None
```

### 4. Ubaci fiscal_rules u Invoice.save() i signals

U `invoicing/models.py` u `save()` metodu:
```python
def save(self, *args, **kwargs):
    # ... postojeći kod ...
    
    # Auto-fiskalizacija provjera (ne blokira, samo bilježi)
    if not hasattr(self, '_skip_fiscal_check'):
        try:
            from invoicing.fiscal_rules import should_fiscalize
            should, reason = should_fiscalize(self)
            # Spremi u internal_note ako je promjena
            if not should and self.doctype in ('R', 'R1', 'RN', 'A'):
                if not self.internal_note or 'fiscal_skip' not in self.internal_note:
                    self.internal_note = (self.internal_note or '') + f'\n[fiscal_skip: {reason}]'
        except Exception:
            pass
    
    super().save(*args, **kwargs)
```

---

## SPRINT 1B — Wire: POS → Otpremnica

### Cilj
Svaki POS bon koji je R1/gotovinski i ima inventarne artikle → kreira propter.Otpremnica

### Gdje ubaciti hook

U `pos/signals.py` ili u `pos/services/checkout.py` nakon kreiranja POSReceipt:

```python
# pos/worktime_bridge.py ili pos/signals.py — dodati:

def pos_receipt_to_otpremnica(receipt):
    """
    Kreira Otpremnica iz POS bona.
    Automatski — korisnik ništa ne radi.
    
    Trigger: POSReceipt kreiran s artiklima koji imaju inventory_item
    Skip: training receipts, nulti iznosi
    """
    if getattr(receipt, 'is_training', False):
        return None
    if receipt.total == 0:
        return None
    
    # Provjeri ima li inventarnih artikala
    from pos.models import POSReceiptItem
    items_with_inv = POSReceiptItem.objects.filter(
        receipt=receipt,
        inventory_item__isnull=False,
    ).select_related('inventory_item')
    
    if not items_with_inv.exists():
        return None  # Usluge/radovi ne trebaju otpremnicu
    
    from propter.models import Otpremnica, OtpremnicaItem, BillingPeriod
    
    # Provjeri da otpremnica već ne postoji
    if Otpremnica.objects.filter(pos_receipt_id=str(receipt.pk)).exists():
        return None
    
    company = receipt.company
    bp = BillingPeriod.get_or_create_current(company)
    
    # Kupac (iz receipta ili anonimni)
    recipient_name = getattr(receipt, 'client_name', '') or 'Gotovinski kupac'
    recipient_oib  = getattr(receipt, 'client_oib', '')  or ''
    
    otp = Otpremnica.objects.create(
        company=company,
        billing_period=bp,
        pos_receipt_id=str(receipt.pk),
        issue_date=receipt.created_at.date(),
        delivery_date=receipt.created_at.date(),
        recipient_name=recipient_name,
        recipient_oib=recipient_oib,
        subtotal=receipt.subtotal if hasattr(receipt, 'subtotal') else receipt.total,
        tax_amount=receipt.tax_amount if hasattr(receipt, 'tax_amount') else 0,
        total=receipt.total,
        source=Otpremnica.Source.POS,
        status=Otpremnica.Status.ISSUED,
    )
    
    # Stavke
    for i, item in enumerate(items_with_inv, 1):
        OtpremnicaItem.objects.create(
            otpremnica=otp,
            line_number=i,
            description=item.name or item.inventory_item.name,
            quantity=item.quantity,
            unit='EA',
            unit_price=item.unit_price,
            tax_rate=item.tax_rate if hasattr(item, 'tax_rate') else 25,
            line_total=item.total_price if hasattr(item, 'total_price') else item.unit_price * item.quantity,
        )
    
    # Ažuriraj BillingPeriod counter
    BillingPeriod.objects.filter(pk=bp.pk).update(
        otpremnica_count=models.F('otpremnica_count') + 1
    )
    
    return otp
```

### Gdje pozvati

```python
# U pos/services/checkout.py, nakon receipt.save():
try:
    from pos.worktime_bridge import pos_receipt_to_otpremnica
    pos_receipt_to_otpremnica(receipt)
except Exception as e:
    logger.warning('pos_receipt_to_otpremnica failed: %s', e)
    # Ne blokirati POS! Samo logirati.
```

PROVJERI PRVO pravi naziv servisa:
```bash
ls pos/services/
grep "def process_receipt\|def checkout\|def complete" pos/services/*.py | head -10
```

---

## SPRINT 1C — Wire: Invoice → Otpremnica

Kad se kreira faktura doctype='R' s artiklima koji imaju inventory:

```python
# invoicing/signals.py — dodati uz postojeće signale:

@receiver(post_save, sender='invoicing.Invoice')
def auto_create_otpremnica(sender, instance, created, **kwargs):
    """
    Invoice R/FA → kreira Otpremnica ako ima inventarnih stavki.
    Samo pri kreiranju, ne pri svakom save.
    """
    if not created:
        return
    if instance.doctype not in ('R', 'FA', 'R1', 'R2'):
        return
    
    try:
        items_with_inv = instance.items.filter(
            inventory_item__isnull=False
        )
        if not items_with_inv.exists():
            return
        
        from propter.models import Otpremnica, OtpremnicaItem, BillingPeriod
        
        bp = BillingPeriod.get_or_create_current(instance.company)
        
        otp = Otpremnica.objects.create(
            company=instance.company,
            billing_period=bp,
            invoice_id=str(instance.pk),
            issue_date=instance.date_issued.date() if hasattr(instance.date_issued, 'date') else instance.date_issued,
            delivery_date=getattr(instance, 'date_delivery', None),
            recipient_name=instance.client_name,
            recipient_oib=instance.client_oib or '',
            recipient_address=instance.client_address or '',
            subtotal=instance.subtotal,
            tax_amount=instance.tax_amount,
            total=instance.total,
            source=Otpremnica.Source.INVOICE,
            status=Otpremnica.Status.ISSUED,
        )
        
        for i, item in enumerate(items_with_inv, 1):
            OtpremnicaItem.objects.create(
                otpremnica=otp,
                line_number=i,
                description=item.description or item.name,
                quantity=item.quantity,
                unit='EA',
                unit_price=item.unit_price,
                tax_rate=item.tax_percent if hasattr(item, 'tax_percent') else 25,
                line_total=item.total if hasattr(item, 'total') else item.unit_price * item.quantity,
            )
        
        # Spremi referencu na Invoice
        instance.source_document_id = otp.pk
        sender.objects.filter(pk=instance.pk).update(internal_note=(instance.internal_note or '') + f'\n[OTP: {otp.number}]')
        
    except Exception as e:
        import logging
        logging.getLogger('invoicing').warning('auto_create_otpremnica failed for %s: %s', instance.number, e)
```

---

## SPRINT 1D — Zbirna faktura (Sammelrechnung) — Celery task

```python
# propter/tasks.py (kreiraj ili dopuni)

from celery import shared_task
import logging
logger = logging.getLogger('propter')


@shared_task(name='propter.generate_monthly_sammelrechnung', bind=True, max_retries=2)
def generate_monthly_sammelrechnung(self):
    """
    Pokreće se 1. u mjesecu u 06:00.
    Za svaku firmu s otvorenim BillingPeriod-om prošlog mjeseca:
    1. Grupira Otpremnice po partneru (recipient_oib)
    2. Kreira Invoice doctype='ZR' (Zbirni Račun / Sammelrechnung)
    3. Stavke: popis svih OTP-a s datumima
    4. Zatvara BillingPeriod
    """
    from django.utils import timezone
    from propter.models import BillingPeriod, Otpremnica
    from invoicing.models import Invoice, InvoiceItem
    from django.db.models import Sum, Count
    import datetime
    
    # Prošli mjesec
    today = timezone.now().date()
    if today.month == 1:
        target_year, target_month = today.year - 1, 12
    else:
        target_year, target_month = today.year, today.month - 1
    
    periods = BillingPeriod.objects.filter(
        year=target_year,
        month=target_month,
        status=BillingPeriod.Status.OPEN,
        otpremnica_count__gt=0,
    ).select_related('company')
    
    generated = 0
    
    for period in periods:
        try:
            # Provjeri ima li izdanih OTP-a
            otps = Otpremnica.objects.filter(
                billing_period=period,
                status=Otpremnica.Status.ISSUED,
            ).order_by('issue_date')
            
            if not otps.exists():
                period.status = BillingPeriod.Status.CLOSED
                period.closed_at = timezone.now()
                period.save(update_fields=['status', 'closed_at'])
                continue
            
            # Grupiraj po partneru
            partners = otps.values('recipient_oib', 'recipient_name').distinct()
            
            for partner in partners:
                partner_otps = otps.filter(recipient_oib=partner['recipient_oib'])
                
                # Izračunaj ukupno
                totals = partner_otps.aggregate(
                    subtotal=Sum('subtotal'),
                    tax=Sum('tax_amount'),
                    total=Sum('total'),
                    count=Count('id'),
                )
                
                # Generiraj broj zbirne fakture
                company = period.company
                last_zr = Invoice.objects.filter(
                    company=company,
                    doctype='ZR',
                ).order_by('-date_issued').first()
                zr_num = f"ZR-{target_year}-{(int(last_zr.number.split('-')[-1]) + 1) if last_zr and last_zr.number else 1:04d}"
                
                # Tekst tijela — popis OTP-a (zakonski uvjet HR i DE)
                otp_lines = '\n'.join([
                    f"OTP-{otp.number} od {otp.issue_date} — {otp.total} EUR"
                    for otp in partner_otps
                ])
                note = (
                    f"Zbirni račun za period {target_month:02d}/{target_year}\n"
                    f"Uključuje {totals['count']} otpremnica:\n{otp_lines}"
                )
                
                # Kreiraj Invoice ZR
                zr = Invoice.objects.create(
                    company=company,
                    doctype='ZR',
                    number=zr_num,
                    date_issued=timezone.now(),
                    date_due=timezone.now().date() + datetime.timedelta(days=30),
                    client_name=partner['recipient_name'],
                    client_oib=partner['recipient_oib'] or '',
                    subtotal=totals['subtotal'] or 0,
                    tax_amount=totals['tax'] or 0,
                    total=totals['total'] or 0,
                    status='DRAFT',
                    note=note,
                    internal_note=f'[Auto-generated] BillingPeriod {period.pk}',
                    country=getattr(company, 'country', 'HR') or 'HR',
                )
                
                # OTP-i → AGGREGATED
                partner_otps.update(status=Otpremnica.Status.AGGREGATED)
                
                generated += 1
                logger.info('ZR %s kreiran za %s (%s OTP)', zr_num, company.name, totals['count'])
            
            # Zatvori period
            period.status = BillingPeriod.Status.INVOICED
            period.invoiced_at = timezone.now()
            period.save(update_fields=['status', 'invoiced_at'])
        
        except Exception as e:
            logger.error('Sammelrechnung failed for period %s: %s', period.pk, e)
            continue
    
    return {'generated': generated, 'periods_processed': periods.count()}
```

### Registracija u Celery Beat (core/settings.py)
```python
# CELERY_BEAT_SCHEDULE — dodati:
'propter-monthly-sammelrechnung': {
    'task': 'propter.generate_monthly_sammelrechnung',
    'schedule': crontab(day_of_month='1', hour='6', minute='0'),
},
```

---

## SPRINT 1E — DocumentValidator (AI zaštita)

Kreiraj `invoicing/document_validator.py`:

```python
"""
invoicing/document_validator.py
AI-assisted validation — eliminiraj ljudske greške.
Korisnik NIKAD ne mora znati pravila napamet.
"""
from dataclasses import dataclass, field
from typing import List
from enum import Enum


class Severity(Enum):
    BLOCK   = 'block'    # Sprječava save
    WARN    = 'warn'     # Upozorenje, ali može nastaviti
    INFO    = 'info'     # Informacija


@dataclass
class ValidationIssue:
    code:     str
    severity: Severity
    message:  str
    field:    str = ''
    action:   str = ''  # Prijedlog akcije


class DocumentValidator:
    """
    Svaki Invoice prolazi kroz ovaj validator pri save().
    Centralno mjesto — nikad duplicirana logika.
    """
    
    def validate(self, invoice) -> List[ValidationIssue]:
        issues = []
        
        issues.extend(self._check_fiscal(invoice))
        issues.extend(self._check_dates(invoice))
        issues.extend(self._check_de_compliance(invoice))
        issues.extend(self._check_duplicates(invoice))
        issues.extend(self._check_pdv_rates(invoice))
        issues.extend(self._check_avans_chain(invoice))
        issues.extend(self._check_udruga_rules(invoice))
        
        return issues
    
    def _check_fiscal(self, inv) -> List[ValidationIssue]:
        issues = []
        from invoicing.fiscal_rules import should_fiscalize
        should, reason = should_fiscalize(inv)
        
        # Pokušaj fiskalizirati nešto što ne treba
        if getattr(inv, 'is_fiscalized', False) and not should:
            issues.append(ValidationIssue(
                code='FISKAL_UNNECESSARY',
                severity=Severity.WARN,
                message=f'Račun je fiskaliziran ali nije trebao biti: {reason}',
                field='is_fiscalized',
                action='Provjerite tip dokumenta i status firme'
            ))
        return issues
    
    def _check_dates(self, inv) -> List[ValidationIssue]:
        issues = []
        from django.utils import timezone
        today = timezone.now().date()
        
        issued = getattr(inv, 'date_issued', None)
        if issued:
            if hasattr(issued, 'date'):
                issued = issued.date()
            
            # Datum isporuke u budućnosti > 30 dana
            delivery = getattr(inv, 'date_delivery', None)
            if delivery and delivery > today:
                from datetime import timedelta
                if (delivery - today).days > 30:
                    issues.append(ValidationIssue(
                        code='DATE_DELIVERY_FAR_FUTURE',
                        severity=Severity.WARN,
                        message=f'Datum isporuke je {(delivery-today).days} dana u budućnosti',
                        field='date_delivery',
                    ))
        
        # Rok plaćanja je prošao i račun nije plaćen
        due = getattr(inv, 'date_due', None)
        if due and due < today and inv.status not in ('PAID', 'STORNO', 'CANCELLED'):
            issues.append(ValidationIssue(
                code='DUE_DATE_PASSED',
                severity=Severity.INFO,
                message=f'Rok plaćanja je prošao ({due}) — razmislite o opomeni',
                field='date_due',
                action='Pokrenite opomenu iz dunning modula'
            ))
        return issues
    
    def _check_de_compliance(self, inv) -> List[ValidationIssue]:
        issues = []
        if getattr(inv, 'country', 'HR') != 'DE':
            return issues
        
        # §14 UStG — obavezne komponente DE računa
        if not getattr(inv, 'client_oib', ''):
            issues.append(ValidationIssue(
                code='DE_NO_STEUERNR',
                severity=Severity.WARN,
                message='DE račun bez Steuernummer/USt-IdNr primatelja (§14 Abs.4 UStG)',
                field='client_oib',
                action='Unesite Steuernummer kupca'
            ))
        
        if not getattr(inv, 'date_delivery', None):
            issues.append(ValidationIssue(
                code='DE_NO_LEISTUNGSDATUM',
                severity=Severity.WARN,
                message='DE račun bez Leistungsdatum (§14 Abs.4 Nr.6 UStG) — PDV može biti osporiv',
                field='date_delivery',
                action='Unesite datum isporuke/usluge ili upišite u napomenu'
            ))
        
        # B2B DE → e-Račun od 2025
        if inv.doctype in ('R', 'FA', 'R1') and getattr(inv, 'date_issued', None):
            issued_year = getattr(inv.date_issued, 'year', None) or (inv.date_issued.year if hasattr(inv.date_issued, 'year') else None)
            if issued_year and issued_year >= 2025:
                # Provjeri ima li eRacun
                if not getattr(inv, 'eracun_sent', False):
                    issues.append(ValidationIssue(
                        code='DE_ERECHNUNG_REQUIRED',
                        severity=Severity.INFO,
                        message='B2B DE račun od 2025 treba biti poslan kao e-Rechnung (XRechnung/ZUGFeRD)',
                        field='',
                        action='Pošaljite putem eRačun modula'
                    ))
        return issues
    
    def _check_duplicates(self, inv) -> List[ValidationIssue]:
        issues = []
        if not inv.pk:  # Novi zapis
            from invoicing.models import Invoice
            same_number = Invoice.objects.filter(
                company=inv.company,
                number=inv.number,
            ).exclude(pk=inv.pk if inv.pk else None)
            
            if same_number.exists():
                issues.append(ValidationIssue(
                    code='DUPLICATE_NUMBER',
                    severity=Severity.BLOCK,
                    message=f'Broj dokumenta {inv.number} već postoji!',
                    field='number',
                ))
        return issues
    
    def _check_pdv_rates(self, inv) -> List[ValidationIssue]:
        issues = []
        try:
            from invoicing.fiscal_rules import get_pdv_rate_for_item
            for item in inv.items.all():
                inv_item = getattr(item, 'inventory_item', None)
                if inv_item:
                    expected_rate, warning = get_pdv_rate_for_item(inv_item, inv.company)
                    if warning:
                        issues.append(ValidationIssue(
                            code='PDV_RATE_MISMATCH',
                            severity=Severity.WARN,
                            message=warning,
                            field=f'items[{item.pk}].tax_percent',
                            action=f'Promijenite PDV stopu na {expected_rate}%'
                        ))
        except Exception:
            pass
        return issues
    
    def _check_avans_chain(self, inv) -> List[ValidationIssue]:
        issues = []
        if inv.doctype == 'A':
            from django.utils import timezone
            from datetime import timedelta
            issued = getattr(inv, 'date_issued', None)
            if issued:
                if hasattr(issued, 'date'):
                    issued = issued.date()
                if (timezone.now().date() - issued).days > 90:
                    # Postoji li završni račun?
                    related = getattr(inv, 'related_invoices', None)
                    has_final = related and related.filter(doctype='R').exists() if related else False
                    if not has_final:
                        issues.append(ValidationIssue(
                            code='AVANS_NO_FINAL',
                            severity=Severity.WARN,
                            message='Avansni račun stariji od 90 dana bez završnog računa',
                            field='related_invoice',
                            action='Kreirajte završni račun ili zatvorite predujam'
                        ))
        return issues
    
    def _check_udruga_rules(self, inv) -> List[ValidationIssue]:
        issues = []
        company = inv.company
        if company.business_type not in ('udruga', 'ustanova'):
            return issues
        
        # Provjeri je li clanarina oporeziva — udruge imaju poseban tretman
        try:
            for item in inv.items.all():
                name = (item.description or '').lower()
                if any(x in name for x in ('članarin', 'clanarin', 'clanska', 'membership')):
                    if getattr(item, 'tax_percent', 0) > 0:
                        issues.append(ValidationIssue(
                            code='UDRUGA_CLANARINA_PDV',
                            severity=Severity.WARN,
                            message='Članarina udruge obično nije predmet PDV-a (NN 73/13)',
                            field=f'items[{item.pk}].tax_percent',
                            action='Provjerite s računovođom — članarine su najčešće PDV exempt'
                        ))
        except Exception:
            pass
        return issues


# Singleton
validator = DocumentValidator()
```

### Integriraj u Invoice.save()

```python
# invoicing/models.py — u clean() ili save():
def clean(self):
    from invoicing.document_validator import validator
    issues = validator.validate(self)
    blocking = [i for i in issues if i.severity.value == 'block']
    if blocking:
        from django.core.exceptions import ValidationError
        raise ValidationError({i.field or '__all__': i.message for i in blocking})
    # Upozorenja spremi za UI
    self._validation_warnings = [i for i in issues if i.severity.value in ('warn', 'info')]
```

---

## SPRINT 1F — Z-izvještaj PDF auto-generacija

### Pronađi session close točku
```bash
grep -n "session_close\|close_session\|def.*close\|status.*closed" pos/views.py pos/services/*.py | head -15
grep -n "POSDailyReport" pos/views.py pos/services/*.py | head -10
```

### Dodaj PDF generaciju
```python
# U session close logici — nakon što se kreira POSDailyReport:
try:
    from pos.pdf_service import generate_z_report_pdf
    pdf_content = generate_z_report_pdf(daily_report)
    from django.core.files.base import ContentFile
    daily_report.z_report_pdf.save(
        f'z_report_{daily_report.terminal.name}_{daily_report.date}.pdf',
        ContentFile(pdf_content),
        save=True
    )
except Exception as e:
    logger.warning('Z-report PDF generation failed: %s', e)
```

Kreiraj `pos/pdf_service.py`:
```python
def generate_z_report_pdf(report):
    """Generira Z-izvještaj PDF. Vraća bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=20*2.83, rightMargin=20*2.83,
                            topMargin=20*2.83, bottomMargin=20*2.83)
    styles = getSampleStyleSheet()
    story = []
    
    # Header
    story.append(Paragraph(f"Z-IZVJEŠTAJ — {report.terminal.name}", styles['Title']))
    story.append(Paragraph(f"Datum: {report.date} | Kompanija: {report.company.name}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Promet
    data = [
        ['Gotovina', f"{report.cash_total} EUR"],
        ['Kartice', f"{report.card_total} EUR"],
        ['Mobilno', f"{report.mobile_total} EUR"],
        ['Ukupno', f"{report.total_revenue} EUR"],
        ['Broj računa', str(report.receipt_count)],
        ['Storniranih', str(report.cancelled_count)],
        ['Prosječni bon', f"{report.average_ticket} EUR"],
    ]
    table = Table(data, colWidths=[200, 150])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
```

---

## DONE KRITERIJ

```bash
# 1. Fiscal rules
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from invoicing.fiscal_rules import should_fiscalize
from invoicing.models import Invoice
inv = Invoice(doctype='PO', total=100)
print('PO fiskal:', should_fiscalize(inv))
inv2 = Invoice(doctype='R', total=100)
print('R fiskal:', should_fiscalize(inv2))
"

# 2. Validator
venv/bin/python manage.py check

# 3. OTP wire
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from propter.models import Otpremnica, BillingPeriod
print('OTP model OK')
"

# 4. Celery task registriran
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from celery import current_app
tasks = [t for t in current_app.tasks if 'propter' in t or 'sammel' in t]
print('Propter tasks:', tasks)
"

# 5. Tests
venv/bin/python manage.py test invoicing.tests --verbosity=1 --no-input 2>&1 | tail -5

# 6. FENIX_STATUS ažurirati + git commit po sprintu
```

---

## NAPOMENE

1. **NE blokirati POS** — sve invoice/otpremnica akcije su u try/except
2. **Migracije samo ako treba** — max_length provjeri prije
3. **Čitaj models.py** za svaki app prije pisanja koda — field nazivi se razlikuju
4. **Commit po sprintu** — 1A, 1B, 1C, 1D, 1E, 1F zasebno
5. **propter/tasks.py** — kreiraj ako ne postoji, dodaj celery imports


---

## ⚠️ KRITIČNI PARAMETAR — DODANO 2026-03-27

**OBAVEZNO ČITAJ AGENT_PARAMS_TESTNI_PODACI.md PRIJE SVAKOG COMPLIANCE KODA.**

```
cat AGENT_PARAMS_TESTNI_PODACI.md
```

### Što znači za Sprint 1

**DocumentValidator i fiscal_rules smiju provjeravati SAMO:**
```python
# Uvijek na početku validate() i should_fiscalize():
if invoice.synesis_id or (invoice.date_issued and invoice.date_issued.year < 2026):
    return []  # Skip — historijski podaci, ne naši propisi
```

**Celery Sammelrechnung task:**
```python
# Samo otpremnice iz 2026+
otps = Otpremnica.objects.filter(
    billing_period=period,
    status=Otpremnica.Status.ISSUED,
    issue_date__year__gte=2026,  # OBVEZNO
)
```

**Svi compliance reporti:**
Naslov mora sadržavati: "Analiza se odnosi samo na produkcijske podatke (2026+). Historijskih 15.325 Synesis dokumenata (2011-2025) je isključeno."


---
## ⚠️ LEGAL PARAMS — AŽURIRANO 2026-03-27

**OBAVEZNO ČITAJ PRIJE COMPLIANCE KODA:**
```bash
cat LEGAL_PARAMS_MASTER.md
```

**LEGAL_PARAMS_MASTER.md** sadrži:
- HR PDV stope po godinama (2013–2026+) s NN brojevima
- HR Fiskalizacija v1.0→v2.0 (NN 133/12 → NN 89/25) s točnim datumima
- DE MwSt povijest (uključivo COVID 16%/5% 07-12.2020.)
- DE E-Rechnung timeline (2025 primanje, 2026-2028 slanje)
- HRK/EUR tranzicija (01.01.2023., tečaj 7,53450)
- Compliance matrica po periodu
- SQL/Django filter za produkcijske dokumente
