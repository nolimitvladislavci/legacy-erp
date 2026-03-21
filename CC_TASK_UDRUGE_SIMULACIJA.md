## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Udruge: Test simulacija + PDF dokumenti na WhatsApp

## Misija
Popuni udruge modul test podacima i pošalji sve A4 dokumente Ivanu na WhatsApp.
Broj: 385991908089

## KORAK 1 — Pročitaj stvarna polja (OBAVEZNO prije pisanja koda)
```bash
cat /var/www/fina-connect/udruge/models.py
cat /var/www/fina-connect/core/whatsapp.py
grep -r "WAHA_ENABLED\|WAHA_API_URL\|WAHA_SESSION" /var/www/fina-connect/core/settings.py | head -10
```

## KORAK 2 — Kreiraj test podatke (management command)

Napiši `/var/www/fina-connect/udruge/management/commands/sim_udruge.py`:

```python
# Što treba kreirati:
# 1. Company tipa 'udruga' — "KUD Fenix Test d.d."
# 2. 5 Clan-ova s različitim membership_type i status
#    - Jedan s membership_expires za 3 dana (expiry warning test)
#    - Jedan expired (za grace period test)
#    - Jedan s whatsapp_opt_in=True i whatsapp_phone='385991908089'
# 3. MembershipPlan (godišnji, 50 EUR)
# 4. 3 Clanarina — jedna placena, jedna ceka, jedna kasni
# 5. 2 Donacije — jedna fizička, jedna pravna osoba iznad 10k EUR (AML trigger)
# 6. 5 unosa u KnjigaPrimitaka (3 primici, 2 izdatka)
# 7. MemberSubscription za prvog clana

# Pokretanje:
# venv/bin/python manage.py sim_udruge
# venv/bin/python manage.py sim_udruge --reset  (briše i kreira iznova)
```

## KORAK 3 — Pokreni testove udruge modula
```bash
cd /var/www/fina-connect
venv/bin/python manage.py test udruge --verbosity=2 --keepdb 2>&1 | tee /tmp/udruge_test.txt
grep -E "^(OK|FAIL|ERROR|Ran)" /tmp/udruge_test.txt
```

## KORAK 4 — Generiraj PDF dokumente

Napiši `/var/www/fina-connect/udruge/management/commands/gen_pdf_send_wa.py`:

Za svaki dokument koristi WeasyPrint (već instaliran). Generiraj i pošalji:

### Dokument 1 — Iskaznica člana (A4 landscape)
Polja: ime, prezime, membership_number, tip, status, datum isteka, QR kod s OIB-om
Boja: plava glava (#1a56db), bijeli tekst, logo "KUD FENIX"

### Dokument 2 — Uplatnica za članarinu (A4 portrait)  
HUB-3 uplatnica format: IBAN primaoca, model HR00, poziv na broj, iznos, svrha, platilac
Udruga KUD Fenix Test, IBAN HR1234567890123456789, period 01.01.2026-31.12.2026

### Dokument 3 — Potvrda o donaciji (A4 portrait)
Već postoji HTML template u views.py (download_donatorska_potvrda)
Iskoristi taj isti HTML, renderaj s WeasyPrint u PDF

### Dokument 4 — Knjiga primitaka i izdataka (A4, tabela)
Sve stavke za 2026, totali primici/izdaci/saldo, zaglavlje s udrugom

### Slanje na WhatsApp
```python
from core.whatsapp import send_document  # provjeri postoji li, ako ne -- send_text s linkom

# Ako send_document ne postoji, dodaj u core/whatsapp.py:
def send_document(phone, file_path, caption='', company_id=None):
    """Pošalji PDF dokument via WAHA."""
    # WAHA endpoint: POST /api/sendFile
    # multipart/form-data: file + chatId + caption
    pass

# Pošalji svaki PDF Ivanu
IVAN_PHONE = '385991908089'
for doc_path, caption in docs:
    send_document(phone=IVAN_PHONE, file_path=doc_path, caption=caption)
```

## KORAK 5 — WhatsApp notifikacije za članove

Dodaj Celery task u `/var/www/fina-connect/udruge/tasks.py`:
```python
@app.task
def send_expiry_warnings():
    """Šalje WhatsApp upozorenje članovima kojima istječe za 7 dana."""
    # Koristi Clan.objects.filter(whatsapp_opt_in=True, membership_expires=today+7)
    # Za svakog: core.whatsapp.send_text(phone, message)
    pass

@app.task  
def send_membership_cards():
    """Šalje iskaznicu novim članovima na WhatsApp."""
    pass
```

## KORAK 6 — Javi rezultate

Na kraju pokreni:
```bash
venv/bin/python manage.py sim_udruge --reset
venv/bin/python manage.py gen_pdf_send_wa
```

I napiši u /tmp/udruge_sim_result.txt:
- Broj kreiranih objekata po tipu
- Status svakog poslanog dokumenta (OK/ERROR)
- Greške ako ih ima

## Definicija DONE
- [ ] sim_udruge command kreira podatke bez greške
- [ ] Svi udruge testovi prolaze (12+)
- [ ] 4 PDF dokumenta generirana u /tmp/udruge_docs/
- [ ] Svi dokumenti poslani na 385991908089
- [ ] /tmp/udruge_sim_result.txt postoji s "DONE" na kraju
