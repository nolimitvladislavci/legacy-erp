# SONNET_TASK_TAX_WIZARD_F3 — UX + Partner Portal + PDF
## Agent: Sonnet | Prioritet: P1 | Tjedan: 3-4
## Preduvjet: F1 (CC Code) i F2 (Gemini) moraju biti DONE

**Čitaj prvo:** TAX_WIZARD_MASTER_PLAN.md, FENIX_STATUS.md  
**Tvoja misija:** Sve što korisnik i računovođa vide i dodiruju. Ovo je lice proizvoda.

---

## 3 STUBA KOJE GRADIŠ

### STUB 1 — Wizard UI (mobile-first, 5 koraka, 15 minuta)
### STUB 2 — Partner (Marija) Dashboard + White-label
### STUB 3 — PDF Generacija (DOH + ZPP-DOH, WeasyPrint)

---

## STUB 1: WIZARD UI

### Princip dizajna
Taxfix model: progress bar gore, jedno pitanje po ekranu, korisnik ne vidi "obrazac".
Naš plus: pre-popunjeni podaci s izvorom ("Iz tvojih faktura: 28.430€").

### Ključne komponente

**`wizard_base.html`** — master template:
```html
<!-- Progress bar — uvijek vidljiv -->
<div class="tw-progress">
  <div class="tw-step {% if step >= N %}done{% endif %}">1. Uvjeti</div>
  <div class="tw-step {% if step >= N %}done{% endif %}">2. Podaci</div>
  <div class="tw-step {% if step >= N %}done{% endif %}">3. Olakšice</div>
  <div class="tw-step {% if step >= N %}done{% endif %}">4. Pregled</div>
  <div class="tw-step {% if step >= N %}done{% endif %}">5. Potvrda</div>
</div>

<!-- Live kalkulator — uvijek gore desno -->
<div class="tw-live-calc">
  <span class="tw-label">Procijenjeni povrat:</span>
  <span class="tw-amount" id="live-amount">
    {% if session.calculated_return > 0 %}
      <span class="green">+{{ session.calculated_return|floatformat:2 }} €</span>
    {% elif session.calculated_return < 0 %}
      <span class="red">{{ session.calculated_return|floatformat:2 }} €</span>
    {% else %}
      Izračunavam...
    {% endif %}
  </span>
</div>

<!-- Sadržaj koraka -->
<div class="tw-content">
  {% block step_content %}{% endblock %}
</div>

<!-- AI hint zona -->
<div class="tw-ai-hint" id="ai-hint-zone">
  {% if ai_hint %}
  <div class="tw-hint-bubble">
    <span class="tw-hint-icon">💡</span>
    {{ ai_hint }}
  </div>
  {% endif %}
</div>
```

**Korak 3 — "Olakšice skeniranje" je najvažniji korak:**
```html
<!-- Animacija skeniranja -->
<div class="tw-scan-animation" id="scan-progress">
  <div class="tw-scan-spinner"></div>
  <p>Provjeravam {{ total_olaksica }} zakonskih odredbi...</p>
  <div class="tw-scan-items" id="scan-items">
    <!-- JS dodaje stavke jedna po jedna -->
  </div>
</div>

<!-- Rezultat skeniranja -->
<div class="tw-scan-result" id="scan-result" style="display:none">
  {% if high_priority %}
  <div class="tw-high-priority-alert">
    ⚠️ Pronašao sam {{ high_priority|length }} olakšice koje malo tko koristi!
    {% for item in high_priority %}
    <div class="tw-priority-item">
      <strong>{{ item.naziv }}</strong>
      <span class="tw-law">{{ item.zakon }}</span>
      {% if item.savings %}
        <span class="tw-savings">{{ item.savings|floatformat:2 }} € uštede</span>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% endif %}
  
  <div class="tw-total-savings">
    Ukupna potencijalna ušteda: <strong>{{ total_savings|floatformat:2 }} €</strong>
  </div>
</div>
```

### CSS stil (mobile-first, Viskovic boja palette s prilagodbom):
```css
:root {
  --tw-primary: #1e3a5f;    /* navy */
  --tw-accent: #c9a84c;     /* gold */
  --tw-success: #22c55e;
  --tw-danger: #ef4444;
  --tw-bg: #f8fafc;
}

/* Sve max-width: 600px — ovo se otvara na WhatsApp linkovima */
.tw-content { max-width: 600px; margin: 0 auto; padding: 16px; }
.tw-progress { display: flex; justify-content: space-between; 
               padding: 12px 0; border-bottom: 2px solid var(--tw-primary); }
.tw-live-calc { position: sticky; top: 0; background: white; 
                padding: 8px 16px; border-bottom: 1px solid #e2e8f0; }
.tw-amount.green { color: var(--tw-success); font-size: 1.4rem; font-weight: 700; }
```

---

## STUB 2: PARTNER DASHBOARD

Marija se prijavi u LIMIT Connect i vidi:

```
┌─────────────────────────────────────────────────────────┐
│  Konjik Tax Assistant  [promijeni brand]                 │
│                                                          │
│  Moj referalni link:                                     │
│  limit-connect.com/hr/tax/ref/KONJIK3A9F/               │
│  [Kopiraj] [Pošalji WhatsApp] [QR kod]                   │
│                                                          │
│  Statistike 2025.:                                       │
│  Poslano:    47 klijenata                                │
│  Završilo:   31 (66%)                                    │
│  Zaradio:    268,20 € (komisija 30%)                     │
│                                                          │
│  Klijenti:                                               │
│  ┌────────────────┬──────────┬──────────┬────────────┐   │
│  │ Ime            │ Status   │ Povrat   │ Komisija   │   │
│  │ Ana Horvat     │ ✅ Done  │ +847€    │ +8,70€     │   │
│  │ Pero Perić     │ ⏳ Korak3│ -        │ -          │   │
│  │ Marko Marković │ ✅ Done  │ +312€    │ +8,70€     │   │
│  └────────────────┴──────────┴──────────┴────────────┘   │
│                                                          │
│  [Isplata komisije na IBAN] (min. 50€)                   │
└─────────────────────────────────────────────────────────┘
```

### Views za partner dashboard:

```python
# views.py

def partner_dashboard(request):
    """Marija vidi sve svoje klijente i zarade."""
    partner = PartnerTaxAccount.objects.get(company=request.user.company)
    sessions = TaxWizardSession.objects.filter(
        partner_referral=partner
    ).select_related('company').order_by('-created_at')
    
    total_earned = sessions.filter(
        status='submitted'
    ).aggregate(e=Sum('calculated_return'))['e'] or 0  # 30% od payment
    
    return render(request, 'tax_wizard/partner_dashboard.html', {
        'partner': partner,
        'sessions': sessions,
        'total_earned': total_earned,
        'referral_url': f"/hr/tax/ref/{partner.referral_code}/",
    })


def wizard_referral(request, code):
    """
    Korisnik otvara Marijin link.
    Prikazuje Marijin brand (white-label), ne LIMIT Connect brand.
    """
    partner = get_object_or_404(PartnerTaxAccount, referral_code=code, is_active=True)
    
    # Kreiraj novu sesiju vezanu za ovog partnera
    session = TaxWizardSession.objects.create(
        partner_referral=partner,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    
    return render(request, 'tax_wizard/wizard_intro.html', {
        'partner': partner,
        'session': session,
        'white_label': True,
        # Korisnik vidi "Konjik Tax Assistant", ne "LIMIT Connect"
        'brand_name': partner.brand_name,
        'brand_logo': partner.brand_logo,
        'brand_color': partner.brand_color,
    })


def partner_send_whatsapp(request, partner_id):
    """
    Marija jednim klikom šalje poruku klijentu.
    """
    partner = get_object_or_404(PartnerTaxAccount, id=partner_id, company=request.user.company)
    client_phone = request.POST.get('phone')
    
    ref_url = f"https://limit-connect.com/hr/tax/ref/{partner.referral_code}/"
    message = (
        f"Poštovani,\n\n"
        f"Koristite naš besplatni kalkulator za provjeru poreznih olakšica za 2025. godinu.\n"
        f"Cijeli postupak traje 15 minuta, a moguće je vratiti do 1.000€+.\n\n"
        f"🔗 {ref_url}\n\n"
        f"S poštovanjem,\n{partner.brand_name}"
    )
    
    wa_url = f"https://wa.me/{client_phone}?text={urllib.parse.quote(message)}"
    return JsonResponse({'wa_url': wa_url})
```

---

## STUB 3: PDF GENERACIJA

Generiraj **dva tipa PDF-a** koristeći isti WeasyPrint engine kao invoicing:

### 1. Korisnički sažetak (za arhivu)
Nije DOH obrazac — nego naš PDF koji korisnik potpisuje i čuva kao dokaz.

```html
<!-- tax_wizard/templates/tax_wizard/audit_summary.html -->
<div class="audit-header">
  <h1>Porezni obračun {{ session.tax_year }}</h1>
  <p>Generirano: {{ now }} | UUID: {{ session.id }} | Hash: {{ session.integrity_chain }}</p>
</div>

<div class="audit-declaration">
  <strong>Izjavljujem da su svi uneseni podaci točni i potpuni.</strong>
  <p>Odgovornost za točnost i zakonitost isključivo je na poreznom obvezniku.
  Ovaj dokument generiran je kalkulatorom i ne predstavlja porezni savjet.</p>
</div>

<div class="audit-data">
  <h3>Uneseni podaci ({{ session.tax_year }})</h3>
  {% for key, val in session.step_data.items %}
  <div class="data-row">
    <span>{{ key }}</span><span>{{ val }}</span>
  </div>
  {% endfor %}
</div>

<div class="audit-deductions">
  <h3>Pronađene olakšice</h3>
  {% for d in session.deductions_found %}
  <div class="deduction-item">
    <strong>{{ d.naziv }}</strong>
    <span class="law">{{ d.zakon }}</span>
    {% if d.savings %}<span class="savings">{{ d.savings }} €</span>{% endif %}
  </div>
  {% endfor %}
</div>

<div class="audit-result">
  <strong>Procijenjeni povrat: {{ session.calculated_return }} €</strong>
</div>
```

### 2. DOH predložak (za ePorezna)
Popunjen DOH obrazac koji korisnik **ručno prenosi** u ePoreznu (dok nemamo API).
Isti layout kao službeni obrazac, sva polja popunjena.

```python
def generate_audit_pdf(session: TaxWizardSession) -> bytes:
    """Generira audit PDF koji se sprema u session.audit_pdf"""
    from weasyprint import HTML
    from django.template.loader import render_to_string
    from django.utils import timezone
    
    html = render_to_string('tax_wizard/audit_summary.html', {
        'session': session,
        'now': timezone.now(),
    })
    return HTML(string=html).write_pdf()


def generate_doh_prefill_pdf(session: TaxWizardSession) -> bytes:
    """
    Generira DOH-like PDF s popunjenim podacima.
    Korisnik ga koristi kao vodič pri unosu u ePoreznu.
    NAPOMENA u PDF-u: 'Ovo nije službeni obrazac. Unesite podatke na ePorezna.gov.hr'
    """
    html = render_to_string('tax_wizard/doh_prefill.html', {'session': session})
    return HTML(string=html).write_pdf()
```

---

## STUB 4: STRIPE SPLIT PAYMENT

Kad korisnik plati (29€ za DOH), Stripe automatski dijeli:

```python
def process_wizard_payment(session: TaxWizardSession, payment_method_id: str) -> dict:
    import stripe
    
    partner = session.partner_referral
    amount = 2900  # 29€ u centima
    
    if partner and partner.stripe_connect_id:
        # Split payment: 30% partneru, 70% nama
        commission = int(amount * float(partner.commission_rate))
        
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='eur',
            payment_method=payment_method_id,
            confirm=True,
            transfer_data={
                'amount': commission,
                'destination': partner.stripe_connect_id,
            },
            metadata={
                'session_id': str(session.id),
                'taxpayer_type': session.taxpayer_type,
                'partner_code': partner.referral_code,
            }
        )
        
        # Ažuriraj statistike partnera
        partner.total_earned += Decimal(commission) / 100
        partner.clients_completed += 1
        partner.save(update_fields=['total_earned', 'clients_completed'])
        
    else:
        # Bez partnera — cijelo ide nama
        payment_intent = stripe.PaymentIntent.create(
            amount=amount, currency='eur',
            payment_method=payment_method_id, confirm=True,
        )
    
    return {'status': 'success', 'payment_intent_id': payment_intent.id}
```

---

## NOTIFIKACIJE (WhatsApp + Email)

Trebaj kreirati **3 tipa notifikacija**:

```python
NOTIFICATION_TRIGGERS = {
    'wizard_completed': {
        # Korisniku — potvrda
        'user_whatsapp': 'Vaš porezni obračun za {year} je spreman. Sažetak: {url}',
        'user_email': 'wizard_completed_user.html',
        # Mariji — klijent završio
        'partner_whatsapp': 'Klijent {name} je završio porezni obračun. Komisija: {amount}€',
    },
    'deadline_reminder_7d': {
        # 7 dana pred rok (25. siječnja svake godine)
        'user_whatsapp': '⚠️ Rok za DOH prijavu je za 7 dana (2. veljače). Imate nedovršeni obračun. Nastavite: {url}',
    },
    'deadline_reminder_1d': {
        # Dan pred rok
        'user_whatsapp': '🚨 SUTRA je rok! Vaš DOH još nije predan. 15 minuta dovoljno: {url}',
    },
}
```

---

## DONE kriterij

```
1. curl https://limit-connect.com/hr/tax/ → 200 OK (wizard home)
2. curl https://limit-connect.com/hr/tax/ref/KONJIK3A9F/ → 200 OK (white-label)
3. curl https://limit-connect.com/hr/tax/partner/ → 200 OK (partner dashboard)
4. PDF generacija: TaxWizardSession → PDF → nije prazan
5. Stripe mock payment prolazi bez greške
```

Ažuriraj FENIX_STATUS.md kad si gotov.
