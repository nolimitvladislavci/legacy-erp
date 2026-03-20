# CC Task — Mega simulacija: korisničke rute kroz sve module

## Misija
Pokreni sve testove. Pronađi bugove. Dokumentiraj.
Ovo je kompletni health check sustava prije produkcije.

## KORAK 1 — Pokreni sve testove, spremi rezultate

```bash
cd /var/www/fina-connect

# Pokreni sve, spremi output
venv/bin/python manage.py test \
  pos documents invoicing eracun worktime udruge \
  konto partners inventory accounts core \
  appointments fiskalizacija superadmin_ai \
  --verbosity=1 --keepdb 2>&1 | tee /tmp/test_results_full.txt

echo "EXIT: $?" >> /tmp/test_results_full.txt

# Summary
echo "=== SUMMARY ===" >> /tmp/test_results_full.txt
grep -E "^(OK|FAIL|ERROR|Ran [0-9])" /tmp/test_results_full.txt | tail -5
```

## KORAK 2 — Izvuci FAIL i ERROR

```bash
grep -E "^(FAIL|ERROR): " /tmp/test_results_full.txt > /tmp/test_failures.txt
echo "Broj failova:" $(wc -l < /tmp/test_failures.txt)
cat /tmp/test_failures.txt
```

## KORAK 3 — Korisničke simulacije (5 stvarnih scenarija)

### Scenarij A — Šeki otvara smjenu i prodaje
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
import os; os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
from django.contrib.auth.models import User
from companies.models import Company
from pos.models import POSTerminal, POSSession, POSReceipt
from pos.services import open_session, create_receipt, add_receipt_item, process_payment, close_session
from decimal import Decimal

print('=== Scenarij A: Šeki POS ===')
try:
    seki = Company.objects.get(name='UVIJEK FRIŠKO')
    terminal = POSTerminal.objects.filter(company=seki, is_active=True).first()
    user = User.objects.get(username='shevqet')
    
    # 1. Otvori smjenu
    session = open_session(terminal, user, Decimal('200.00'))
    print(f'✅ Smjena #{session.session_number} otvorena')
    
    # 2. Kreiraj bon
    receipt = create_receipt(session)
    print(f'✅ Bon #{receipt.receipt_number} kreiran')
    
    # 3. Dodaj artikl
    from inventory.models import InventoryItem
    kruh = InventoryItem.objects.filter(company=seki, is_active=True).first()
    item = add_receipt_item(receipt, kruh, kruh.name if kruh else 'Kruh', Decimal('1'), Decimal('1.20'))
    print(f'✅ Stavka dodana: {item.description} = {item.total_price} EUR')
    
    # 4. Naplata
    receipt.refresh_from_db()
    result = process_payment(receipt, 'CASH', Decimal('5.00'), user)
    print(f'✅ Naplaćeno, kusur: {result.get(\"change\", 0)} EUR')
    print(f'✅ ZKI: {receipt.zki or \"DEMO/NEMA\"}')
    
    # 5. Cleanup - storniraj
    receipt.refresh_from_db()
    print(f'✅ Bon status: {receipt.status}')
    receipt.status = 'cancelled'
    receipt.cancel_reason = 'Test simulacija'
    receipt.save()
    close_session(session, Decimal('201.20'))
    print('✅ Smjena zatvorena')
    print('=== Scenarij A: PASS ===')
except Exception as e:
    import traceback
    print(f'❌ FAIL: {e}')
    traceback.print_exc()
" 2>&1
```

### Scenarij B — Marija uploadira dokument u arhivu
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
from companies.models import Company
from documents.models import ArhivaEntry
from django.utils import timezone

print('=== Scenarij B: Arhiva upload ===')
try:
    marija = User.objects.get(username='marija.brtan')
    konjik = Company.objects.get(name='Konjik d.o.o.')
    
    # Kreiraj arhiva entry
    entry = ArhivaEntry.objects.create(
        company=konjik,
        doc_number='TEST-SIM-001',
        doc_date=timezone.now().date(),
        partner_name='Test Partner d.o.o.',
        total_amount=1250.00,
        currency='EUR',
        source_type='invoice',
        uploaded_by=marija,
    )
    print(f'✅ Dokument kreiran: {entry.doc_number}')
    
    # Provjeri integrity hash
    if hasattr(entry, 'integrity_hash') and entry.integrity_hash:
        print(f'✅ Integrity hash: {entry.integrity_hash[:16]}...')
    
    # Provjeri je li vidljiv
    count = ArhivaEntry.objects.filter(company=konjik, doc_number='TEST-SIM-001').count()
    print(f'✅ Vidljiv u arhivi: {count == 1}')
    
    # Cleanup
    entry.delete()
    print('✅ Cleanup OK')
    print('=== Scenarij B: PASS ===')
except Exception as e:
    import traceback
    print(f'❌ FAIL: {e}')
    traceback.print_exc()
" 2>&1
```

### Scenarij C — Tim Chat send (nova ruta)
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from django.test import RequestFactory, override_settings
from django.contrib.auth.models import User
from pos.models import ImprovementSuggestion
import json

print('=== Scenarij C: Tim Chat ===')
try:
    # Provjeri postoji li tim_chat_send view
    from core.views import tim_chat_send
    print('✅ tim_chat_send view postoji')
    
    # Provjeri URL
    from django.urls import reverse
    url = reverse('tim_chat_send')
    print(f'✅ URL: {url}')
    
    # Simuliraj request
    user = User.objects.filter(is_active=True, is_superuser=False).first()
    if user:
        rf = RequestFactory()
        req = rf.post('/hr/tim-chat/send/', 
            json.dumps({'description': 'Test poruka', 'module': 'tim_chat', 'priority': 2}),
            content_type='application/json')
        req.user = user
        from unittest.mock import patch
        with patch('core.company_utils.get_user_company') as mock_company:
            from companies.models import Company
            mock_company.return_value = Company.objects.filter(is_active=True).first() if hasattr(Company, 'is_active') else Company.objects.first()
            response = tim_chat_send(req)
            data = json.loads(response.content)
            print(f'✅ Response: {data}')
            if data.get(\"ok\"):
                # Cleanup
                ImprovementSuggestion.objects.filter(title__startswith='Tim Chat: Test').delete()
                print('✅ Scenarij C: PASS')
            else:
                print(f'⚠️ Unexpected: {data}')
    else:
        print('⚠️ Nema non-superuser korisnika za test')
except ImportError as e:
    print(f'❌ View ne postoji: {e}')
except Exception as e:
    import traceback
    print(f'❌ FAIL: {e}')
    traceback.print_exc()
" 2>&1
```

### Scenarij D — eRačun validacija
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from eracun.models import ERacun, ERacunConfig
from eracun.services.engine import validate_eracun
from companies.models import Company
from decimal import Decimal

print('=== Scenarij D: eRačun ===')
try:
    company = Company.objects.filter(is_active=True).first() if hasattr(Company, 'is_active') else Company.objects.first()
    
    er = ERacun(
        company=company,
        invoice_number='TEST-ER-SIM-001',
        doc_type='380',
        issue_date='2026-03-20',
        due_date='2026-04-20',
        seller_name='Test Firma d.o.o.',
        seller_oib='12345678901',
        recipient_name='Kupac d.o.o.',
        recipient_oib='98765432109',
        subtotal=Decimal('1000.00'),
        tax_amount=Decimal('250.00'),
        total=Decimal('1250.00'),
        currency='EUR',
        payment_means_code='30',
    )
    
    result = validate_eracun(er)
    print(f'✅ Validacija: valid={result.get(\"valid\")}, errors={result.get(\"errors\", [])}')
    print('=== Scenarij D: PASS ===')
except Exception as e:
    import traceback
    print(f'❌ FAIL: {e}')
    traceback.print_exc()
" 2>&1
```

### Scenarij E — Okrugli stol submit kao non-superuser
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from django.test import RequestFactory
from django.contrib.auth.models import User
import json

print('=== Scenarij E: Okrugli stol access control ===')

# Test 1: superadmin endpoint blokira non-superadmin
rf = RequestFactory()
req = rf.post('/hr/superadmin/ai/api/submit-request/', 
    json.dumps({'description': 'test', 'module': 'tim_chat'}),
    content_type='application/json')

seki = User.objects.get(username='shevqet')
req.user = seki

from superadmin_ai.views import submit_request
resp = submit_request(req)
print(f'Superadmin endpoint za Šekija: HTTP {resp.status_code}')
if resp.status_code in [302, 403]:
    print('✅ Ispravno blokiran')
else:
    print(f'⚠️ Neočekivano: {resp.status_code} {resp.content[:100]}')

# Test 2: tim_chat_send prolazi za non-superadmin
try:
    from core.views import tim_chat_send
    req2 = rf.post('/hr/tim-chat/send/',
        json.dumps({'description': 'test okrugli stol', 'module': 'tim_chat'}),
        content_type='application/json')
    req2.user = seki
    from unittest.mock import patch
    from companies.models import Company
    with patch('core.company_utils.get_user_company', return_value=Company.objects.first()):
        resp2 = tim_chat_send(req2)
        data = json.loads(resp2.content)
        print(f'Tim Chat send za Šekija: HTTP {resp2.status_code} → {data.get(\"ok\")}')
        if data.get('ok'):
            print('✅ Non-superuser može slati')
            from pos.models import ImprovementSuggestion
            ImprovementSuggestion.objects.filter(title__startswith='Tim Chat: test').delete()
        else:
            print(f'❌ FAIL: {data}')
except ImportError:
    print('❌ tim_chat_send ne postoji još')

print('=== Scenarij E: DONE ===')
" 2>&1
```

## KORAK 4 — Spremi izvješće

```bash
cat > /var/www/fina-connect/SIMULACIJA_REPORT.md << 'REPORT'
# Simulacija izvješće — $(date +"%d.%m.%Y %H:%M")

## Test suite rezultati
REPORT

tail -20 /tmp/test_results_full.txt >> /var/www/fina-connect/SIMULACIJA_REPORT.md

echo "" >> /var/www/fina-connect/SIMULACIJA_REPORT.md
echo "## Scenariji" >> /var/www/fina-connect/SIMULACIJA_REPORT.md
echo "Pokrenuto: $(date)" >> /var/www/fina-connect/SIMULACIJA_REPORT.md

echo "Izvješće: /var/www/fina-connect/SIMULACIJA_REPORT.md"
```

## KORAK 5 — Bugovi iz jučer

Jučer pronađeni bugovi (provjeri jesu li popravljeni):
```bash
cd /var/www/fina-connect

# Bug 1: receipt.html default filter
grep "barcode|default:|" templates/pos/receipt.html && echo "BUG POSTOJI" || echo "Bug 1: FIXED"

# Bug 2: weasyprint
venv/bin/python -c "import weasyprint; print('weasyprint OK:', weasyprint.__version__)"

# Bug 3: superadmin endpoint za non-superuser  
grep -n "tim_chat_send" core/urls.py && echo "Fix deployiran" || echo "Fix NEDOSTAJE"
```

## Format javljanja
```
=== SIMULACIJA REZULTATI ===
Test suite: X/Y passed (Z failed)
Scenarij A (Šeki POS): PASS/FAIL
Scenarij B (Arhiva): PASS/FAIL  
Scenarij C (Tim Chat): PASS/FAIL
Scenarij D (eRačun): PASS/FAIL
Scenarij E (Access control): PASS/FAIL

Bugovi pronađeni: [lista]
Bugovi jučer: [fixed/still exists]
```
