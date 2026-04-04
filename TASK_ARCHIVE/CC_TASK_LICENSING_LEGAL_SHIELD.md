# CC_TASK_LICENSING_LEGAL_SHIELD.md
# Za: CC Code (tehnički dio) + Ivan (pravni dio)
# Datum: 2026-03-30
# Prioritet: VISOKO — mora biti gotovo PRIJE prvog Distributera
# Procjena: CC Code 1 dan | Odvjetnik 2-3 tjedna (paralelno)
#
# KONTEKST — Gemini analiza asimilirana:
# - DPA/Data Processor je zakonska obveza, ne opcija
# - SLA bez cap-a = besplatni helpdesk
# - Update divergence riješen jer smo SaaS (jedan server)
# - JWT heartbeat bolji od LICENSE_ACTIVE flag
# - PyArmor = NE (security theater)
# - Dedicated instance = NE (CompanyManager već daje izolaciju)
#
# OVO JE "PRAVNI OKLOP" koji platforma mora imati PRIJE prvog EU partnera.

---

## DIO A — TECHNIČKI (CC Code)

### A1. LicenseHeartbeat model + check

Geminijev prijedlog JWT heartbeat asimiliran:

```python
# Dodati u permissions/models.py ili novi permissions/license.py

import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import models

class LicenseToken(models.Model):
    """
    JWT-based license check za Distributor i EU Licensee korisnike.
    
    Flow:
      1. Ivan/Sonnet kreira LicenseToken za novu companyu
      2. Token se provjerava svakih 24h iz Distributerovog sustava
         (ili na svakom requestu u "check" modu)
      3. Nema validnog tokena 72h → graceful degradation (read-only mode)
      4. Nema validnog tokena 7 dana → maintenance mode + DB export link
    
    BITNO: Ne brisati podatke. Ne ubijati servis naglo.
    GDPR: Korisnik uvijek može exportati vlastite podatke.
    """
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='license_token'
    )
    
    # Token info
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()
    
    # Renewal tracking
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    heartbeat_count = models.PositiveIntegerField(default=0)
    consecutive_failures = models.PositiveIntegerField(default=0)
    
    # Status
    STATUS = [
        ('active',      'Aktivna'),
        ('grace',       'Grace period (72h)'),
        ('readonly',    'Read-only mod (7 dana)'),
        ('suspended',   'Suspendirano'),
        ('cancelled',   'Otkazano'),
    ]
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    
    # Billing veza
    last_payment_date = models.DateField(null=True, blank=True)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'permissions'
        db_table = 'license_tokens'

    def __str__(self):
        return f'{self.company.name} [{self.status}] valid until {self.valid_until:%Y-%m-%d}'

    @property
    def is_valid(self):
        return self.status == 'active' and timezone.now() < self.valid_until

    @property
    def days_until_expiry(self):
        return (self.valid_until - timezone.now()).days

    def renew(self, months=1):
        """Produži licencu za N mjeseci (poziva se nakon plaćanja)."""
        self.valid_until = timezone.now() + timedelta(days=30 * months)
        self.status = 'active'
        self.consecutive_failures = 0
        self.last_payment_date = timezone.now().date()
        self.save(update_fields=['valid_until', 'status', 'consecutive_failures', 'last_payment_date'])

    def record_heartbeat(self):
        """Beleži uspješan heartbeat."""
        self.last_heartbeat = timezone.now()
        self.heartbeat_count += 1
        self.consecutive_failures = 0
        self.save(update_fields=['last_heartbeat', 'heartbeat_count', 'consecutive_failures'])

    def check_and_degrade(self):
        """
        Provjeri status i degradiraj ako treba.
        Poziva se Celery beatom svakih 6h.
        """
        now = timezone.now()
        
        if self.valid_until > now:
            # Licenca validna — ništa ne radimo
            if self.status != 'active':
                self.status = 'active'
                self.save(update_fields=['status'])
            return self.status
        
        days_expired = (now - self.valid_until).days
        
        if days_expired < 3:  # Grace period
            if self.status != 'grace':
                self.status = 'grace'
                self.save(update_fields=['status'])
                self._notify_grace_period()
        
        elif days_expired < 7:  # Read-only
            if self.status != 'readonly':
                self.status = 'readonly'
                self.save(update_fields=['status'])
                self._notify_readonly()
        
        else:  # Suspendirano
            if self.status != 'suspended':
                self.status = 'suspended'
                self.save(update_fields=['status'])
                self._notify_suspended()
        
        return self.status

    def _notify_grace_period(self):
        try:
            from core.whatsapp import send_text
            send_text(
                phone='+4915771998747',  # Ivan
                message=f'⚠️ LICENSE GRACE PERIOD\n{self.company.name}\nLicenca istekla, 3 dana do read-only moda.'
            )
        except Exception:
            pass

    def _notify_readonly(self):
        try:
            from core.whatsapp import send_text
            send_text(
                phone='+4915771998747',
                message=f'🔒 LICENSE READ-ONLY\n{self.company.name}\nSustav u read-only modu. Kontaktirajte za plaćanje.'
            )
        except Exception:
            pass

    def _notify_suspended(self):
        # Pošalji export link korisniku (GDPR compliant)
        try:
            from core.whatsapp import send_text
            send_text(
                phone='+4915771998747',
                message=f'🚫 LICENSE SUSPENDED\n{self.company.name}\nSustav suspendiran nakon 7 dana. Export podataka aktivan 30 dana.'
            )
        except Exception:
            pass

    @classmethod
    def create_for_company(cls, company, months=12, monthly_fee=0):
        """Factory za kreiranje licence."""
        import hashlib
        token = hashlib.sha256(f'{company.id}{timezone.now().isoformat()}'.encode()).hexdigest()
        return cls.objects.create(
            company=company,
            token_hash=token,
            valid_until=timezone.now() + timedelta(days=30 * months),
            monthly_fee=monthly_fee,
        )
```

### A2. License Middleware

Dodati NAKON `WhiteLabelMiddleware` u MIDDLEWARE listu:

```python
class LicenseCheckMiddleware:
    """
    Provjerava status licence za WhiteLabel korisnika.
    Samo za firme s WhiteLabelConfig (Distributeri, EU partneri).
    Obični SaaS korisnici nisu pogođeni.
    """
    # Rute koje uvijek prolaze (export, payment, support)
    ALWAYS_ALLOW = {
        'gdpr_export', 'gdpr_delete', 'health_check',
        'login', 'logout', 'password_reset',
        'license_payment',  # URL za plaćanje (novi)
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        wl = getattr(request, 'white_label', None)
        if not wl:
            return self.get_response(request)  # Obični SaaS, ne diraj

        # Check view name
        view_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')
        if view_name in self.ALWAYS_ALLOW:
            return self.get_response(request)

        try:
            license_token = wl.company.license_token
        except Exception:
            return self.get_response(request)  # Nema license tokena, propusti

        status = license_token.check_and_degrade()

        if status == 'active':
            return self.get_response(request)

        elif status == 'grace':
            # Upozorenje ali prolazi
            request.license_warning = f'Licenca istekla — {license_token.days_until_expiry} dana do read-only moda'
            return self.get_response(request)

        elif status == 'readonly':
            # Dozvoli samo GET requeste
            if request.method == 'GET':
                request.license_warning = 'Sustav u read-only modu. Molimo obnovite licencu.'
                return self.get_response(request)
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Licenca istekla. Sustav je u read-only modu.',
                'payment_url': 'https://limit-connect.com/licenca/plati/',
                'support': '+4915771998747'
            }, status=402)  # 402 Payment Required

        else:  # suspended
            from django.http import HttpResponse
            return HttpResponse(
                '<h1>Sustav privremeno nedostupan</h1>'
                '<p>Vaša licenca je istekla. Kontaktirajte podršku: +4915771998747</p>'
                '<p><a href="/licenca/export/">Preuzmite vaše podatke</a></p>',
                status=503
            )
```

### A3. Celery task za provjeru licenci

```python
# Dodati u core/tasks.py ili permissions/tasks.py

@shared_task(name='permissions.check_licenses')
def check_all_licenses():
    """
    Svakih 6 sati provjerava status svih licenci.
    Poziva check_and_degrade() za sve WhiteLabel korisnike.
    """
    from permissions.license import LicenseToken
    
    tokens = LicenseToken.objects.filter(
        status__in=['active', 'grace', 'readonly']
    ).select_related('company')
    
    degraded = []
    for token in tokens:
        old_status = token.status
        new_status = token.check_and_degrade()
        if old_status != new_status:
            degraded.append(f'{token.company.name}: {old_status} → {new_status}')
    
    if degraded:
        logger.warning(f'License degradations: {degraded}')
    
    return {'checked': tokens.count(), 'degraded': len(degraded)}
```

Dodati u CELERY_BEAT_SCHEDULE (settings.py):
```python
'check-licenses': {
    'task': 'permissions.check_licenses',
    'schedule': crontab(minute=0, hour='*/6'),
},
```

### A4. Migracija i seed

```bash
venv/bin/python manage.py makemigrations permissions --name license_token
venv/bin/python manage.py migrate

# Kreiraj licence za postojeće WhiteLabel firme
venv/bin/python manage.py shell -c "
from permissions.license import LicenseToken
from companies.models import Company

# Konjik (Marija) - besplatno za sada
konjik = Company.objects.get(name__icontains='Konjik')
lt, c = LicenseToken.create_for_company(konjik, months=12, monthly_fee=0)
print(f'Konjik licenca: {lt.valid_until.date()} (besplatno - interni)') if c else print('Već postoji')
"
```

### A5. Sidebar warning za license

U `base.html`, na vrh `.sidebar-content`:
```html
{% if license_warning %}
<div class="license-warning-banner" style="
  background: rgba(255,180,0,0.12);
  border: 1px solid rgba(255,180,0,0.4);
  border-radius: 8px; padding: 10px 14px;
  margin-bottom: 12px; font-size: .82rem; color: #f1c40f;">
  ⚠️ {{ license_warning }}
  <a href="/licenca/plati/" style="color:#c9a84c;font-weight:700">→ Obnovi</a>
</div>
{% endif %}
```

---

## DIO B — PRAVNI OKLOP (Ivan rješava, paralelno s CC Code)

### B1. DPA (Data Processing Agreement) template

Potrebno za svaki Distributor i EU Partner. Odvjetnik piše, ali ključne točke:

```
1. LIMIT Connect = Data Processor (tehnički obrađuje podatke)
2. Distributer = Data Controller (odgovoran za podatke svojih klijenata)
3. Distributerovi klijenti = Data Subjects

DPA mora sadržavati:
- Predmet i trajanje obrade
- Priroda i svrha obrade  
- Tip osobnih podataka (OIB, email, financijski podaci)
- Obveze i prava Data Controllera
- Obveza LIMIT Connect: ne koristiti podatke za vlastite svrhe
- Pravo inspekcije: Distributer može auditirati
- Sub-procesori: Hetzner (hosting), WAHA (WhatsApp), email provideri
- Sigurnosne mjere: enkripcija, pristupna kontrola (FAL), audit log
- Breach notification: 72h od saznanja (GDPR čl. 33)
- Brisanje podataka: 30 dana od raskida ugovora
- Primjenjivo pravo: HR ili EU pravo (za EU partnere)
```

### B2. SLA template (Service Level Agreement)

```
RAZINA USLUGE:
- Uptime: 99.5% mjesečno (dopušta ~3.5h downtime/mj)
- Planned maintenance: uz 48h najave, ne u radnom vremenu
- Response time API: < 2s za 95% requesta
- Bug fix (critical): 4h response time, 24h resolution
- Bug fix (high): 24h response time, 72h resolution
- Feature requests: bez SLA (product roadmap)

PODRŠKA:
- Uključeno: 5 sati/mj (email + WhatsApp)
- Prekoračenje: 80 EUR/h (fakturira se sljedeći mj)
- Dostupnost: radnim danom 08-18h CET
- Emergency: +4915771998747 (za produkcijske incidente)

MANDATORY UPDATES:
- Svi Distributori moraju biti na latest stable unutar 30 dana
- Ivan najavljuje update s 14 dana unaprijed
- Ako Distributer odbije update → suspenzija SLA (ne produkt)

OGRANIČENJE ODGOVORNOSTI:
- LIMIT Connect nije odgovoran za: pogrešne podatke koje Distributer unese
- LIMIT Connect nije odgovoran za: zakonske kazne zbog netočnih poreznih prijava
- Maksimalna odgovornost = 3× mjesečna licencna naknada
```

### B3. Event of Default (precizna definicija)

```
Događaj koji daje pravo na suspenziju (uz 7 dana najave):
  ✓ Neplaćanje licence > 30 dana po dospijeću
  ✓ Kršenje DPA (dijeljenje podataka trećim stranama)
  ✓ Neimplementacija obaveznog security patcha > 30 dana
  ✓ Insolventnost ili stečaj Distributera

Događaj koji daje pravo na trenutnu suspenziju (bez najave):
  ✓ Aktivan sigurnosni incident koji ugrožava podatke
  ✓ Kriminalna aktivnost utvrđena presudom
  ✓ Pokušaj reverse-engineeringa ili krađe koda

Što NIJE Event of Default:
  ✗ "Prestanak poslovanja" bez precizne definicije (izbjegavaj ovu frazu)
  ✗ "Nezadovoljstvo uslugom" (to je klauzula za raskid s otkaznim rokom)
```

### B4. Mandatory update klauzula

```
Distributer se obvezuje primijeniti sve obavezne updateove unutar 30 dana
od obavijesti. Update je "obavezan" ako:
  (a) sadržava security patch za CVE s CVSS > 7.0
  (b) sadržava zakonski obaveznu promjenu (nova verzija eRačun standarda, 
      promjena CIS API, izmjena Zakona o fiskalizaciji)
  (c) LIMIT Connect ga klasificira kao "MANDATORY" u release notesima

Neimplementacija obaveznog updatea unutar 30 dana:
  → LIMIT Connect suspendira SLA
  → Nakon 60 dana → Event of Default
```

---

## DIO C — REDOSLIJED (paralelno, ne sekvencijalno)

Gemini je rekao "zaboravi Ansible tjedan dana" — ne slažem se.
Paralelni rad je jedini ispravan pristup za 2-person tim:

```
TJEDAN 1 (31.03 - 06.04):
  Ivan: Kontaktira odvjetnika, šalje mu DPA + SLA outline
  CC Code: LicenseToken model + middleware + Celery task

TJEDAN 2 (07.04 - 13.04):
  Ivan: Pregled prvog nacrta DPA s odvjetnikom
  CC Code: Claim Your Business (71 ghost firma)

TJEDAN 3 (14.04 - 20.04):
  Ivan: Potpisuje DPA s prvim Distributerom (Marija)
  CC Code: WhiteLabel + SmartEntry deployment

TJEDAN 4 (21.04 - 30.04):
  Ivan: Outreach za 2-3 HR Distributera
  CC Code: Bulk invite pokretanje + praćenje konverzije
```

---

## COMMIT

```bash
git add permissions/ core/middleware/__init__.py core/settings.py
git commit -m "feat(license): JWT heartbeat + SLA enforcement + legal framework

LicenseToken model:
  status: active/grace/readonly/suspended
  check_and_degrade(): automatska degradacija po expiry
  renew(): produži licencu nakon plaćanja
  GDPR compliant: podaci uvijek dostupni za export

LicenseCheckMiddleware:
  Samo za WhiteLabel firme (Distributeri, EU partneri)
  GET read-only dozvoljeno, POST/PUT/DELETE blocked
  402 Payment Required umjesto 403 Forbidden
  Uvijek dozvoljava: export, login, payment URL

Celery beat: check-licenses svakih 6h
WhatsApp alerting: grace/readonly/suspended events

Pravni oklop (za Ivana):
  DPA template ključne točke
  SLA: 5h/mj + 80 EUR/h, 99.5% uptime
  Event of Default precizna definicija
  Mandatory update klauzula (30 dana)"
```

---

## ZAKLJUČAK — Dedicated instance ili ne?

**NE treba dedicated instance.** Evo zašto:

1. CompanyManager (core/managers.py) već filtrira sve querysete po company_id
   → 242 modela, thread-local isolation → Korpaš ne vidi Konjik podatke
   
2. WhiteLabelConfig daje branding izolaciju (logo, boje, domena)

3. LicenseToken daje billing/enforcement izolaciju

4. FAL daje permissions izolaciju

5. Audit log bilježi sve akcije po company_id

**Što dedicated instance daje VIŠE:**
- Fizička separacija podataka (GDPR "pravo na zaborav" je lakše)
- Može ići na njihov hardware
- Nema update ovisnosti

**Kad ima smisla:**
- EU Partner koji plaća 500+ EUR/mj
- Eksplicitno regulatorni zahtjev (osiguravajuća društva, banke)
- Klijent koji inzistira i spreman je platiti setup fee

**Za sve ostale:** SaaS + WhiteLabel + LicenseToken = 95% funkcionalnosti, 10% kompleksnosti.
