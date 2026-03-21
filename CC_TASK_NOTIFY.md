## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — WhatsApp notifikacije za koordinatora

## Zadatak: 2 male stvari

### 1. Dodaj u core/settings.py (na kraj, ispred zadnjeg bloka)
```python
# Superadmin WhatsApp notifikacije
SUPERADMIN_WHATSAPP = '+4915771998747'
```

### 2. Hookaj notify() na 3 postojeća mjesta

**A) Health monitor** — kad restartuje servis
Fajl: pronađi cron skriptu koja restartuje gunicorn
```bash
grep -rn "restart\|gunicorn" /var/www/fina-connect/maintenance/ /etc/cron.d/ /var/www/fina-connect/server_audit.sh 2>/dev/null | head -20
```
Nakon restarta dodaj poziv:
```python
from core.notify import notify
notify("ALERT", f"Auto-restart: {service_name} restartovan u {timestamp}", urgent=True)
```

**B) bulk_invite** — kad završi slanje
U `core/management/commands/bulk_invite.py`, na kraju handle():
```python
from core.notify import notify
notify("DEPLOY", f"Bulk invite završen — {total_invited} korisnika pozvano, {total_no_email} bez emaila")
```

**C) Novi POS bon** — kad Šeki izda prvi bon
U `pos/services/checkout.py`, u `process_receipt()` nakon što je bon plaćen:
```python
# Samo za prvih 10 bonova po kompaniji — da Ivan zna da radi
receipt_count = POSReceipt.objects.filter(
    session__terminal__company=company,
    status='paid'
).count()
if receipt_count <= 10:
    from core.notify import notify
    notify("POS", f"🥐 {company.name} — bon #{receipt.receipt_number} — {receipt.total} EUR")
```

### 3. Test
```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from core.notify import notify
notify('INFO', 'Test notifikacija — sustav radi', urgent=True)
print('Sent')
"
```

## Pravila
- Ne diraj checkout.py logiku naplate — samo dodaj notify() poziv NAKON što je bon kreiran
- Uvijek u try/except — notify() nikad ne smije blokirati glavnu funkciju
- Provjeri django check nakon svake promjene
