# CC TASK: ARHIVA + EMAIL SIMBIOZA SPRINT 2A + 2C
Datum: 04.04.2026. | Rok: 09.04.2026.
Prioritet: VISOK

PRAVILO: READ svaki fajl PRIJE pisanja. Nikad ne pretpostavljaj field name.
PRAVILO: base.html, .env NE DIRAŠ.
PRAVILO: ai_bookkeeper.py postoji u konto/ CИТАЈ GA prije pisanja proknjizavanja.

---

SPRINT 2A KORAK 1: Provjeri stanje
EXEC: grep -n "email_sent\|email_open\|tracking" /var/www/fina-connect/documents/models.py | head -10
EXEC: cat /var/www/fina-connect/invoicing/services/email_service.py
EXEC: ls /var/www/fina-connect/templates/emails/
EXEC: grep -E "EMAIL_BACKEND|EMAIL_HOST|EMAIL_PORT" /var/www/fina-connect/core/settings.py | head -5

SPRINT 2A KORAK 2: Migracija email tracking polja na ArhivaEntry
READ: /var/www/fina-connect/documents/models.py (klasa ArhivaEntry, oko linija 239)
Dodaj ODMAH ISPOD integrity_hash polja:
  email_sent_at = DateTimeField(null=True, blank=True, verbose_name=Email poslan)
  email_sent_to = CharField(max_length=255, blank=True, verbose_name=Email primatelj)
  email_opened_at = DateTimeField(null=True, blank=True, verbose_name=Email otvoren)
  email_open_count = PositiveSmallIntegerField(default=0, verbose_name=Broj otvaranja)

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py makemigrations documents --name email_tracking
EXEC: venv/bin/python manage.py migrate documents
EXEC: venv/bin/python manage.py check 2>&1 | tail -3

SPRINT 2A KORAK 3: HTML branded email template
WRITE: /var/www/fina-connect/templates/emails/invoice_email.html
Sadrzaj: inline CSS email template, max-width 600px, Arial font
Boje: header #1a1a2e pozadina + zlatni tekst #c9a84c, bijelo body
Sekcije:
  1. HEADER: LIMIT CONNECT logo tekst, zlatno, 24px
  2. HERO: Postovani client_name, doc_label broj invoice_number, iznos total currency (veliki zlatni font), rok date_due
  3. INFO BOX: IBAN issuer_iban, Model HR00, Poziv invoice_number
  4. CTA GUMB zlatni: Pregledaj racun online, href=client_portal_url
  5. TRACKING PIXEL: img src=tracking_pixel_url, 1x1, opacity 0
  6. FOOTER tamni: issuer_name, issuer_address, issuer_email, Automatska obavijest
Template varijable: client_name, invoice_number, total, currency, date_due,
  issuer_iban, issuer_name, issuer_address, issuer_email,
  client_portal_url, tracking_pixel_url, doc_label

SPRINT 2A KORAK 4: Tracking pixel endpoint
READ: /var/www/fina-connect/invoicing/views.py (zadnjih 30 linija)
READ: /var/www/fina-connect/invoicing/urls.py

Dodaj view na kraj invoicing/views.py:
  def email_tracking_pixel(request, entry_b64):
    import base64
    GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    try:
      pk = int(base64.urlsafe_b64decode(entry_b64 + '==').decode())
      from documents.models import ArhivaEntry
      from django.utils import timezone
      entry = ArhivaEntry.objects.filter(pk=pk).first()
      if entry:
        if not entry.email_opened_at:
          entry.email_opened_at = timezone.now()
        entry.email_open_count = (entry.email_open_count or 0) + 1
        entry.save(update_fields=['email_opened_at','email_open_count'])
    except Exception:
      pass
    return HttpResponse(GIF, content_type='image/gif')

Dodaj URL: path('track/<str:entry_b64>/', views.email_tracking_pixel, name='email_tracking_pixel'),

SPRINT 2A KORAK 5: Nadopuni email_service.py za HTML + tracking
READ: /var/www/fina-connect/invoicing/services/email_service.py (CIJELI)
Modificiraj send_invoice_email(invoice):
  1. Generiraj tracking URL:
     import base64
     from documents.models import ArhivaEntry
     entry = ArhivaEntry.objects.filter(source_type='invoice_out', source_id=str(invoice.pk)).first()
     tracking_pixel_url = ''
     if entry:
       b64 = base64.urlsafe_b64encode(str(entry.pk).encode()).decode().rstrip('=')
       base_url = getattr(settings,'SITE_URL','https://limit-connect.com')
       tracking_pixel_url = f"{base_url}/invoicing/track/{b64}/"
  2. client_portal_url = f"{base_url}/invoicing/portal/{invoice.client_token}/"
  3. Renderiraj templates/emails/invoice_email.html s kontekstom
  4. Zamijeni send_email_with_attachment_task.delay() s EmailMultiAlternatives:
     attach HTML, attach PDF, send()
  5. Nakon slanja: entry.email_sent_at = timezone.now(); entry.email_sent_to = invoice.client_email; entry.save(update_fields=[...])

SPRINT 2A KORAK 6: Email badge u arhiva_list.html drawer
READ: /var/www/fina-connect/templates/documents/arhiva_list.html (linije 680-760)
U JavaScript buildDrawer/renderDrawer funkciji, dodaj email status sekciju:
  Ako d.email_sent_at: badge zeleni "Poslano DATUM"
    Ako d.email_opened_at: badge plavi "Otvoreno DATUM (Nx)"
    Inace: badge zuti "Nije otvoreno"
  Ako ne email_sent_at i source_type='invoice_out': badge sivi "Nije poslano"
CSS klase: .email-badge, .email-sent (zelena), .email-opened (plava), .email-pending (zuta), .email-not-sent (siva)
Arhiva API JSON mora ukljucivati: email_sent_at, email_opened_at, email_open_count (dodaj u documents/views.py serializer)

---

SPRINT 2C KORAK 7: Provjeri ai_bookkeeper
EXEC: cd /var/www/fina-connect && grep -n "def " konto/ai_bookkeeper.py
EXEC: grep -n "process_archive_entry\|auto_commit" konto/ai_bookkeeper.py | head -10

SPRINT 2C KORAK 8: Proknjizi endpoint
READ: /var/www/fina-connect/documents/views.py (CIJELI - provjeri importse)
READ: /var/www/fina-connect/documents/urls.py

Dodaj view na kraj documents/views.py:
  @require_POST
  @login_required
  def arhiva_proknjizi(request, pk):
    Provjeri ArhivaEntry po pk i company
    Ako is_booked: return JsonResponse({'error':'Vec proknjizeno'}, status=409)
    from konto.ai_bookkeeper import process_archive_entry
    result = process_archive_entry(pk, auto_commit=True)
    Ako uspjeh: WhatsApp Mariji + return JsonResponse({'ok':True})
    Ako greska: return JsonResponse({'error':str(result)}, status=400)

Dodaj URL u documents/urls.py:
  path('entry/<int:pk>/proknjizi/', views.arhiva_proknjizi, name='arhiva_proknjizi'),

SPRINT 2C KORAK 9: AI Bookkeeper panel u arhiva_list.html drawer
READ: /var/www/fina-connect/templates/documents/arhiva_list.html (drawer JS generacija)
Na kraju drawer HTML-a dodaj:
  Ako d.ai_proposal i NOT d.is_booked: panel s prijedlogom knjizenja
    Header: "Prijedlog knjizenja" + confidence posto
    Retci: account_code, account_name, debit EUR D, credit EUR C
    Gumb "Proknjiri" (data-entry-id, data-doc)
    fetch POST /documents/entry/ID/proknjizi/ s CSRF tokenem
  Ako d.is_booked: badge "Proknjizeno"

CSS: .ai-bookkeeper-panel (zelena bordura), .ai-booking-line (grid 4 kolone),
  .abl-code (zlatno), .abl-d (zeleno), .abl-c (ruzicasto)

SPRINT 2C KORAK 10: Deep links u arhiva_list drawer
READ: /var/www/fina-connect/templates/documents/arhiva_list.html (akcijski gumbi area)
Dodaj link gumbe na temelju source_type:
  source_type='invoice_out': link na /invoicing/SOURCE_ID/
  source_type='pos_receipt': link na /pos/receipt/SOURCE_ID/
  source_type='eracun': link na /einvoice/message/SOURCE_ID/
Arhiva API JSON mora sadrzavati source_id (dodaj u documents/views.py)

SPRINT 2B KORAK 11: source_type nadopuna + Gmail placeholder
READ: /var/www/fina-connect/documents/models.py (SOURCE_TYPES)
Dodaj: ('email_in', 'Ulazni email URA auto-import'), ('email_in_pending', 'Email import ceka pregled')
EXEC: venv/bin/python manage.py makemigrations documents --name email_in_source_type
EXEC: venv/bin/python manage.py migrate documents

READ: /var/www/fina-connect/documents/tasks.py (kraj fajla)
Dodaj shared_task gmail_ura_import:
  Provjeri GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN u os.environ
  Ako nisu: logger.info('Gmail credentials nisu konfigurirani') + return skipped
  Inace: logger.info('TODO: implementirati kad Ivan postavi OAuth') + return pending_setup

NAPOMENA ZA IVANA: Gmail OAuth setup na https://console.cloud.google.com/
Scope: https://www.googleapis.com/auth/gmail.modify
U .env dodati: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_IMPORT_EMAIL, MARIJA_WHATSAPP

FINALNI KORAK:
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5 && curl -s -o /dev/null -w "HTTP %{http_code}" https://limit-connect.com/
EXEC: git add -A && git commit -m "feat(arhiva-s2): email tracking + HTML email + AI proknjizi UI + deep links trokut"

DONE kriterij:
- ArhivaEntry ima 4 nova email polja, migracija OK
- /invoicing/track/BASE64/ vraca 1x1 GIF
- Invoice email salje HTML s tracking pixelom i PDF-om
- Arhiva drawer: email badge zeleni/plavi/sivi
- Arhiva drawer: AI Bookkeeper panel s Proknjiri gumbom
- /documents/entry/PK/proknjizi/ radi POST
- Arhiva drawer: deep links invoice/pos/eracun
- gmail_ura_import task registriran
- manage.py check: 0 errors
