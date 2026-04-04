# CC TASK: FENIX INBOX — CENTRALNI DOKUMENTNI ROUTER
Datum: 04.04.2026. | Rok: 10.04.2026.
Prioritet: KRITICAN

PRAVILO: READ svaki fajl PRIJE pisanja. Nikad ne pretpostavljaj field name.
PRAVILO: base.html, .env NE DIRAS bez citanja.
PRAVILO: CompanyManager() na svaki model s company FK — obavezno.
PRAVILO: Nakon svake migracije: venv/bin/python manage.py check 2>&1 | tail -3

---

KORAK 1: Provjeri teren

EXEC: grep -n "app_name\|urlpatterns" /var/www/fina-connect/propter/urls.py | head -5
EXEC: ls /var/www/fina-connect/templates/propter/
EXEC: grep -n "def fetch_invoices_from_email\|def process_staging_batch" /var/www/fina-connect/smart_import/tasks.py
EXEC: grep -n "claude-haiku\|anthropic" /var/www/fina-connect/partners/wizard_views.py | head -5
EXEC: grep -rn "def send_whatsapp" /var/www/fina-connect/core/whatsapp.py | head -3
EXEC: grep -n "MARIJA_WHATSAPP\|CELERY_BEAT_SCHEDULE" /var/www/fina-connect/core/settings.py | head -10
EXEC: grep -n "date_of_issue\|partner_name\|client_name\|^    currency\|^    total " /var/www/fina-connect/invoicing/models.py | head -20

---

KORAK 2: FenixInboxItem model

READ: /var/www/fina-connect/smart_import/models.py (CIJELI — zadnja linija i importse)

Na KRAJ smart_import/models.py dodaj:

class FenixInboxItem(models.Model):
    TIP_CHOICES = [
        ('ura', 'Ulazni racun URA'),
        ('ira', 'Izlazni racun IRA'),
        ('interna', 'Interna isprava'),
        ('nepoznato', 'Nepoznato - pregled'),
    ]
    IZVOR_CHOICES = [
        ('email', 'Email import'),
        ('scan', 'FenixScan upload'),
        ('upload', 'Rucni upload'),
        ('pos', 'POS bon auto'),
        ('invoice', 'Racun auto'),
        ('staging', 'Staging batch'),
    ]
    STATUS_CHOICES = [
        ('novo', 'Novo'),
        ('klasificira', 'AI klasificira'),
        ('ceka', 'Ceka Mariju'),
        ('usmjereno', 'Usmjereno'),
        ('arhivirano', 'Arhivirano'),
        ('greska', 'Greska'),
    ]

    company  = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                  related_name='fenix_inbox', verbose_name='Tvrtka')
    objects  = CompanyManager()
    izvor    = models.CharField(max_length=20, choices=IZVOR_CHOICES)
    tip      = models.CharField(max_length=20, choices=TIP_CHOICES, blank=True)
    status   = models.CharField(max_length=20, choices=STATUS_CHOICES, default='novo')

    arhiva_entry_id = models.IntegerField(null=True, blank=True)
    staging_file_id = models.IntegerField(null=True, blank=True)
    import_batch_id = models.IntegerField(null=True, blank=True)
    invoice_id      = models.IntegerField(null=True, blank=True)
    pos_receipt_id  = models.IntegerField(null=True, blank=True)

    doc_broj        = models.CharField(max_length=200, blank=True)
    partner_naziv   = models.CharField(max_length=200, blank=True)
    iznos           = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    valuta          = models.CharField(max_length=5, default='EUR', blank=True)
    datum_dokumenta = models.DateField(null=True, blank=True)

    ai_tip_confidence = models.FloatField(default=0.0)
    ai_summary        = models.TextField(blank=True)
    ai_prijedlog      = models.JSONField(null=True, blank=True)

    usmjereno_na = models.CharField(max_length=50, blank=True,
                                     help_text='inventory / konto / arhiva / propter')
    usmjereno_at = models.DateTimeField(null=True, blank=True)
    obradjeno_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                      null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fenix Inbox stavka'
        verbose_name_plural = 'Fenix Inbox'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status'], name='fenix_inbox_co_status_idx'),
            models.Index(fields=['company', 'created_at'], name='fenix_inbox_co_date_idx'),
        ]

    def __str__(self):
        return f"[{self.izvor}] {self.partner_naziv or 'Nepoznato'} {self.iznos or ''}"

    @property
    def izvor_url(self):
        if self.invoice_id:
            return f'/invoicing/{self.invoice_id}/'
        if self.pos_receipt_id:
            return f'/pos/receipt/{self.pos_receipt_id}/'
        if self.arhiva_entry_id:
            return f'/documents/arhiva/?entry={self.arhiva_entry_id}'
        return ''

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py makemigrations smart_import --name fenix_inbox_model
EXEC: venv/bin/python manage.py migrate smart_import
EXEC: venv/bin/python manage.py check 2>&1 | tail -3

---

KORAK 3: Admin registracija

READ: /var/www/fina-connect/smart_import/admin.py (zadnjih 20 linija)

Dodaj na kraj:

from smart_import.models import FenixInboxItem

@admin.register(FenixInboxItem)
class FenixInboxItemAdmin(admin.ModelAdmin):
    list_display = ('created_at','izvor','tip','partner_naziv','iznos','valuta','status','usmjereno_na')
    list_filter = ('izvor','tip','status')
    search_fields = ('partner_naziv','doc_broj','ai_summary')
    readonly_fields = ('created_at','updated_at','ai_summary','ai_prijedlog','ai_tip_confidence')
    date_hierarchy = 'created_at'
    list_per_page = 50

---

KORAK 4: Infuzija signala

READ: /var/www/fina-connect/documents/signals.py (CIJELI)

U _archive_invoice_inner(instance), unutar try bloka NAKON entry.save():

    try:
        from smart_import.models import FenixInboxItem
        _tip_dok = 'ura' if getattr(instance, 'doctype', '') == 'URA' else 'ira'
        FenixInboxItem.objects.create(
            company=instance.company,
            izvor='invoice',
            tip=_tip_dok,
            status='arhivirano',
            invoice_id=instance.pk,
            arhiva_entry_id=entry.pk if entry else None,
            doc_broj=instance.number or '',
            partner_naziv=(getattr(instance,'client_name','') or getattr(instance,'partner_name','') or '')[:200],
            iznos=instance.total,
            valuta=getattr(instance,'currency','EUR') or 'EUR',
            ai_tip_confidence=1.0,
            ai_summary=f'Auto: {instance.number}',
        )
    except Exception as _ie:
        logger.warning('FenixInbox invoice signal: %s', _ie)

NAPOMENA: entry varijabla mora biti dostupna u scope. Provjeri je li definirana iznad ovog bloka.
Ako nije - koristi: ArhivaEntry.objects.filter(source_type='invoice_out',source_id=str(instance.pk)).first()

U _archive_pos_receipt_inner(instance), unutar try bloka NAKON entry.save():

    try:
        from smart_import.models import FenixInboxItem
        _pos_co = None
        try:
            _pos_co = instance.session.terminal.company
        except Exception:
            pass
        if _pos_co:
            FenixInboxItem.objects.create(
                company=_pos_co,
                izvor='pos',
                tip='ira',
                status='arhivirano',
                pos_receipt_id=instance.pk,
                arhiva_entry_id=entry.pk if entry else None,
                doc_broj=f'BON-{instance.receipt_number}',
                partner_naziv=(instance.buyer_name or 'Gotovinski kupac')[:200],
                iznos=instance.total,
                valuta='EUR',
                ai_tip_confidence=1.0,
                ai_summary=f'POS bon #{instance.receipt_number}',
            )
    except Exception as _ie:
        logger.warning('FenixInbox pos signal: %s', _ie)

---

KORAK 5: Haiku Classifier Celery task

READ: /var/www/fina-connect/smart_import/tasks.py (prvih 15 linija — importse)
READ: /var/www/fina-connect/partners/wizard_views.py (linije 371-430 — Haiku API pattern)

Dodaj na kraj smart_import/tasks.py:

@shared_task(bind=True, name='smart_import.classify_inbox_item', max_retries=2)
def classify_inbox_item(self, item_id):
    from smart_import.models import FenixInboxItem
    try:
        item = FenixInboxItem.objects.unscoped().get(pk=item_id)
    except FenixInboxItem.DoesNotExist:
        return
    if item.status == 'arhivirano':
        return

    item.status = 'klasificira'
    item.save(update_fields=['status'])

    ctx = ' '.join(filter(None, [
        item.partner_naziv, item.doc_broj,
        str(item.iznos or ''), item.ai_summary,
    ]))
    if not ctx.strip():
        item.status = 'ceka'
        item.tip = 'nepoznato'
        item.save(update_fields=['status','tip'])
        return

    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=10,
            messages=[{'role':'user','content':(
                'Klasificiraj dokument u jednu kategoriju: ura ira interna nepoznato\n'
                'ura=ulazni racun primamo od dobavljaca\n'
                'ira=izlazni racun saljemo klijentu\n'
                'interna=otpremnica primka CMR interni\n'
                'nepoznato=sve ostalo\n'
                f'Podaci: {ctx}\n'
                'Odgovori SAMO jednom od: ura ira interna nepoznato'
            )}]
        )
        tip_raw = msg.content[0].text.strip().lower()
        tip = tip_raw if tip_raw in {'ura','ira','interna','nepoznato'} else 'nepoznato'
        item.tip = tip
        item.ai_tip_confidence = 0.9 if tip != 'nepoznato' else 0.4
        item.status = 'ceka' if tip in ('ura','nepoznato') else 'arhivirano'
        item.save(update_fields=['tip','ai_tip_confidence','status'])
    except Exception as exc:
        logger.error('classify_inbox_item %s: %s', item_id, exc)
        item.status = 'ceka'
        item.tip = 'nepoznato'
        item.save(update_fields=['status','tip'])

---

KORAK 6: Infuzija u fetch_invoices_from_email

READ: /var/www/fina-connect/smart_import/tasks.py (funkcija fetch_invoices_from_email, sve linije)
Pronađi: batch = ImportBatch.objects.create(...) ili batch.save()
ODMAH NAKON tog poziva dodaj:

    try:
        from smart_import.models import FenixInboxItem
        _inbox = FenixInboxItem.objects.create(
            company=company,
            izvor='email',
            status='novo',
            import_batch_id=batch.pk,
            doc_broj=subject[:200] if subject else '',
            partner_naziv=sender[:200] if sender else '',
            ai_summary=f'Email: {sender} | {subject}',
        )
        classify_inbox_item.delay(_inbox.pk)
    except Exception as _ie:
        logger.warning('FenixInbox email infusion: %s', _ie)

---

KORAK 7: Infuzija u process_staging_batch

READ: /var/www/fina-connect/smart_import/tasks.py (funkcija process_staging_batch, sve linije)
Pronađi: header.save() ili StagingFileHeader.objects.create(...)
ODMAH NAKON dodaj:

    try:
        from smart_import.models import FenixInboxItem, StagingBatch
        _sb = StagingBatch.objects.unscoped().get(pk=staging_batch_id)
        _sf_id = staging_file.pk if 'staging_file' in locals() else None
        _inbox = FenixInboxItem.objects.create(
            company=_sb.company,
            izvor='staging',
            status='novo',
            staging_file_id=_sf_id,
            doc_broj=header.invoice_number or '',
            partner_naziv=header.supplier_name or '',
            iznos=header.total_amount,
            valuta=header.currency or 'EUR',
            datum_dokumenta=header.invoice_date,
            ai_tip_confidence=header.confidence,
            ai_summary=f'OCR: {header.supplier_name} {header.invoice_number}',
        )
        classify_inbox_item.delay(_inbox.pk)
    except Exception as _ie:
        logger.warning('FenixInbox staging infusion: %s', _ie)

---

KORAK 8: WhatsApp batch digest

READ: /var/www/fina-connect/core/whatsapp.py (send_whatsapp signature)

Dodaj na kraj smart_import/tasks.py:

@shared_task(name='smart_import.fenix_inbox_digest')
def fenix_inbox_digest():
    from smart_import.models import FenixInboxItem
    from django.utils import timezone
    import os

    marija = os.environ.get('MARIJA_WHATSAPP', '')
    if not marija:
        logger.info('fenix_inbox_digest: MARIJA_WHATSAPP nije u .env')
        return

    since = timezone.now() - timezone.timedelta(minutes=30)
    nove = list(
        FenixInboxItem.objects.unscoped()
        .filter(status__in=['ceka','novo'], created_at__gte=since)
        .select_related('company')
    )
    if not nove:
        return

    by_company = {}
    for item in nove:
        k = item.company.name
        by_company.setdefault(k, []).append(item)

    for co_name, items in by_company.items():
        ura_n = sum(1 for i in items if i.tip == 'ura')
        unk_n = sum(1 for i in items if i.tip in ('nepoznato',''))
        eur   = sum(float(i.iznos or 0) for i in items)
        lines = [f'FENIX INBOX - {co_name}']
        if ura_n:
            lines.append(f'{ura_n} nova URA (~{eur:.0f} EUR)')
        if unk_n:
            lines.append(f'{unk_n} nepoznatih - provjeri')
        lines.append('limit-connect.com/propter/inbox/')
        try:
            from core.whatsapp import send_whatsapp
            send_whatsapp(marija, '\n'.join(lines))
        except Exception as wa_e:
            logger.warning('fenix_inbox_digest WA: %s', wa_e)

---

KORAK 9: Celery Beat registracija

READ: /var/www/fina-connect/core/settings.py (grep CELERY_BEAT_SCHEDULE)
ILI READ: /var/www/fina-connect/core/celery.py

Pronađi CELERY_BEAT_SCHEDULE dict i dodaj:

    'fenix-inbox-digest': {
        'task': 'smart_import.fenix_inbox_digest',
        'schedule': 1800,
    },

NAPOMENA: 1800 = sekunde (30 min). Ne koristiti crontab objekt.

---

KORAK 10: Propter Inbox view + URL

READ: /var/www/fina-connect/propter/views.py (prvih 30 linija — importse i _company helper)
READ: /var/www/fina-connect/propter/urls.py (CIJELI)

Dodaj na kraj propter/views.py:

def fenix_inbox(request):
    company = _company(request)
    if not company:
        messages.error(request, 'Nema tvrtke.')
        return redirect('/dashboard/')

    from smart_import.models import FenixInboxItem
    from django.core.paginator import Paginator
    from django.db.models import Sum

    status_f = request.GET.get('status', '')
    tip_f    = request.GET.get('tip', '')
    izvor_f  = request.GET.get('izvor', '')

    qs = FenixInboxItem.objects.filter(company=company).order_by('-created_at')
    if status_f: qs = qs.filter(status=status_f)
    if tip_f:    qs = qs.filter(tip=tip_f)
    if izvor_f:  qs = qs.filter(izvor=izvor_f)

    ukupno  = FenixInboxItem.objects.filter(company=company).count()
    ceka    = FenixInboxItem.objects.filter(company=company, status__in=['ceka','novo']).count()
    arhiv   = FenixInboxItem.objects.filter(company=company, status='arhivirano').count()
    ura_eur = (FenixInboxItem.objects.filter(company=company, tip='ura', iznos__isnull=False)
               .aggregate(s=Sum('iznos'))['s'] or 0)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'propter/inbox.html', {
        'items': page, 'ukupno': ukupno, 'ceka': ceka,
        'arhiv': arhiv, 'ura_eur': ura_eur,
        'status_filter': status_f, 'tip_filter': tip_f, 'izvor_filter': izvor_f,
        'status_choices': FenixInboxItem.STATUS_CHOICES,
        'tip_choices': FenixInboxItem.TIP_CHOICES,
        'izvor_choices': FenixInboxItem.IZVOR_CHOICES,
        'page_title': 'Fenix Inbox',
    })


@require_POST
@login_required
def fenix_inbox_action(request, item_id):
    company = _company(request)
    from smart_import.models import FenixInboxItem
    try:
        item = FenixInboxItem.objects.get(pk=item_id, company=company)
    except FenixInboxItem.DoesNotExist:
        return JsonResponse({'error': 'Nije pronadjeno'}, status=404)

    action = request.POST.get('action', '')

    if action == 'arhiviraj':
        item.status = 'arhivirano'
        item.obradjeno_by = request.user
        item.save(update_fields=['status','obradjeno_by','updated_at'])
        return JsonResponse({'ok': True})

    if action == 'set_tip':
        novi = request.POST.get('tip', '')
        valid_tips = [c[0] for c in FenixInboxItem.TIP_CHOICES]
        if novi in valid_tips:
            item.tip = novi
            item.status = 'ceka'
            item.obradjeno_by = request.user
            item.save(update_fields=['tip','status','obradjeno_by','updated_at'])
            return JsonResponse({'ok': True, 'tip': novi})

    if action == 'usmjeri':
        dest = request.POST.get('odrediste', '')
        if dest in ('inventory','konto','arhiva','propter'):
            from django.utils import timezone as tz
            item.status = 'usmjereno'
            item.usmjereno_na = dest
            item.usmjereno_at = tz.now()
            item.obradjeno_by = request.user
            item.save(update_fields=['status','usmjereno_na','usmjereno_at','obradjeno_by','updated_at'])
            return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Nepoznata akcija'}, status=400)

Dodaj u propter/urls.py (APPEND na kraj urlpatterns liste):
    path('inbox/', views.fenix_inbox, name='fenix_inbox'),
    path('inbox/<int:item_id>/action/', views.fenix_inbox_action, name='fenix_inbox_action'),

---

KORAK 11: Propter Inbox template

WRITE: /var/www/fina-connect/templates/propter/inbox.html

Template extenda base.html. Sadrzaj block content:

4 stat kartice (CSS grid, 4 kolone, gap 1rem, margin-bottom 1.5rem):
  Zlatna: vrijednost="{{ ceka }}" label="Ceka Mariju"
  Plava: vrijednost="{{ ukupno }}" label="Svi dokumenti"
  Zelena: vrijednost="{{ arhiv }}" label="Obradjeno"
  Narancasta: vrijednost="{{ ura_eur|floatformat:2 }} EUR" label="URA ulaznih racuna"

Filter forma (GET, inline, margin-bottom 1rem):
  Select name=status: option prazni + za svaki par u status_choices
  Select name=tip: option prazni + za svaki par u tip_choices
  Select name=izvor: option prazni + za svaki par u izvor_choices
  Submit "Filtriraj"
  Anchor href="/propter/inbox/" "Resetiraj"

Tablica (width 100%, border-collapse collapse):
  Zaglavlje: Datum | Izvor | Tip | Partner i iznos | Status | Akcije
  Za svaki item in items:
    td Datum: item.created_at|date:"d.m.Y H:i"
    td Izvor: span class="bi bi-IZVOR" gdje IZVOR=item.izvor — tekst item.get_izvor_display
    td Tip: span class="bi bi-TIP" gdje TIP=item.tip — tekst item.get_tip_display
            ako item.ai_tip_confidence > 0: small class=muted "(ai_tip_confidence|floatformat:0)%"
    td Partner: item.partner_naziv|default:"-"
               ako item.iznos: div small "item.iznos|floatformat:2 item.valuta"
    td Status: span class="bi bi-STATUS" gdje STATUS=item.status — tekst item.get_status_display
    td Akcije: dropdown gumbi
      Gumb "Arhiviraj" onclick inboxAction(item.pk,'arhiviraj')
      Gumb "URA" onclick inboxAction(item.pk,'set_tip','ura')
      Gumb "IRA" onclick inboxAction(item.pk,'set_tip','ira')
      Ako item.izvor_url: anchor href=item.izvor_url target=_blank "Otvori dokument"

Paginacija ispod tablice: standardna Django paginacija.

JavaScript inline (kraj body):
function inboxAction(id, action, extra) {
    var fd = new FormData();
    fd.append('action', action);
    if (extra) fd.append('tip', extra);
    var csrf = (document.cookie.match(/csrftoken=([^;]+)/)||[])[1]||'';
    fetch('/propter/inbox/'+id+'/action/', {
        method:'POST', body:fd,
        headers:{'X-CSRFToken':csrf}
    }).then(function(r){return r.json();}).then(function(d){
        if(d.ok) location.reload(); else alert(d.error||'Greska');
    });
}

CSS inline (u style bloku):
.inbox-stat-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1.25rem;}
.inbox-stat-val{font-size:2rem;font-weight:800;}
.inbox-stat-lbl{font-size:.78rem;color:var(--muted);}
.bi{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.72rem;font-weight:600;}
.bi-email{background:rgba(33,150,243,.15);color:#2196f3;}
.bi-pos{background:rgba(76,175,125,.15);color:#4caf7d;}
.bi-invoice{background:rgba(100,100,100,.15);color:#888;}
.bi-staging{background:rgba(156,39,176,.15);color:#9c27b0;}
.bi-scan{background:rgba(201,168,76,.15);color:#c9a84c;}
.bi-ura{background:rgba(255,152,0,.15);color:#ff9800;}
.bi-ira{background:rgba(76,175,125,.15);color:#4caf7d;}
.bi-nepoznato{background:rgba(244,67,54,.15);color:#f44336;}
.bi-ceka{background:rgba(255,193,7,.15);color:#ffc107;border:1px solid #ca8a04;}
.bi-arhivirano{background:rgba(76,175,125,.1);color:#4caf7d;}
.bi-novo{background:rgba(33,150,243,.1);color:#2196f3;}

---

KORAK 12: Provjeri sidebar (SAMO CITAJ, NE PISI base.html)

EXEC: grep -n "propter\|Propter\|soba\|inbox" /var/www/fina-connect/templates/base.html | head -15
Javi Ivanu tocnu liniju gdje treba dodati Inbox link u sidebaru. Ne pisi base.html.

---

KORAK 13: Finalna provjera i commit

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 6 && curl -s -o /dev/null -w "limit-connect: %{http_code}\n" https://limit-connect.com/
EXEC: curl -s -o /dev/null -w "propter inbox: %{http_code}\n" https://limit-connect.com/propter/inbox/ -L
EXEC: cd /var/www/fina-connect && git add -A && git commit -m "feat(fenix-inbox): centralni dokumentni router, Haiku classifier, WhatsApp digest, Propter Inbox UI"

DONE kriterij:
- FenixInboxItem model i migracija OK
- /propter/inbox/ vraca 200
- /propter/inbox/{id}/action/ prima POST i vraca JSON
- classify_inbox_item Celery task registriran
- fenix_inbox_digest Celery task (schedule 1800s) registriran
- documents/signals.py kreira FenixInboxItem za Invoice i POSReceipt
- fetch_invoices_from_email kreira FenixInboxItem za svaki email attachment
- process_staging_batch kreira FenixInboxItem za svaki obradjeni staging file
- manage.py check: 0 errors
- git commit postoji

NAPOMENA ZA IVANA:
1. U .env dodati: MARIJA_WHATSAPP=+385XXXXXXXXX
2. base.html sidebar — CC Code prijavi tocnu liniju — Ivan rucno dodaje link
3. /propter/soba.html — dodati gumb ili link koji vodi na /propter/inbox/
