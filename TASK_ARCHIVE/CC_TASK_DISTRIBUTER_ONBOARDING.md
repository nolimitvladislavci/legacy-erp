# CC_TASK: DISTRIBUTER ONBOARDING — forma + cockpit approve
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P1
# Cilj: Netko iz Splita vidi stranicu → prijavi se → Ivan odobri → subdomene live

PRAVILO: READ models.py PRVO. base.html, .env NE DIRAS.

## KORAK 1 — PROVJERI
```bash
grep -n "class WhiteLabelConfig\|class LicenseToken" companies/models.py | head -5
grep -n "postani.distributer\|distributer" core/urls.py registration/urls.py 2>/dev/null | head -5
grep -rn "def distributer\|distributer_onboard" --include="*.py" | grep -v venv | head -5
grep -n "DistributerApplication\|DistributerRequest" companies/models.py registration/models.py 2>/dev/null | head -5
```

## KORAK 2 — DistributerApplication model

READ: companies/models.py (zadnjih 30 linija, WhiteLabelConfig + LicenseToken)

DODAJ u companies/models.py:
```python
class DistributerApplication(models.Model):
    """Prijava za distributere / partnere."""
    STATUS_CHOICES = [
        ('pending',   'Na čekanju'),
        ('approved',  'Odobreno'),
        ('rejected',  'Odbijeno'),
        ('active',    'Aktivan'),
    ]
    # Podaci podnositelja
    name          = models.CharField(max_length=150, verbose_name='Ime i prezime')
    company_name  = models.CharField(max_length=200, verbose_name='Naziv tvrtke/obrta')
    oib           = models.CharField(max_length=11, blank=True)
    email         = models.EmailField()
    phone         = models.CharField(max_length=30, blank=True)
    city          = models.CharField(max_length=100, verbose_name='Grad')
    region        = models.CharField(max_length=100, blank=True, verbose_name='Regija/Županija')

    # Plan i namjera
    target_clients = models.PositiveIntegerField(
        default=10, verbose_name='Planirani broj klijenata (procjena)')
    business_type  = models.CharField(max_length=200, blank=True,
                     verbose_name='Tip klijenata (npr. ugostiteljstvo, OPG, obrti)')
    motivation     = models.TextField(blank=True, verbose_name='Zašto postati distributer?')
    has_accounting = models.BooleanField(default=False,
                     verbose_name='Imam računovodstveno znanje')

    # Željeni subdomain
    requested_subdomain = models.SlugField(max_length=30, blank=True,
                          verbose_name='Željeni subdomain (npr. split, osijek)')

    # Status
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    reviewed_by   = models.ForeignKey('auth.User', null=True, blank=True,
                    on_delete=models.SET_NULL, related_name='reviewed_applications')
    review_note   = models.TextField(blank=True)

    # Auto-setup (popunjava se pri approve)
    white_label   = models.OneToOneField('WhiteLabelConfig', null=True, blank=True,
                    on_delete=models.SET_NULL, related_name='application')

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Distributer prijava'
        verbose_name_plural = 'Distributer prijave'

    def __str__(self):
        return f'{self.company_name} / {self.city} ({self.get_status_display()})'
```

Migracija:
```bash
venv/bin/python manage.py makemigrations companies --name="add_distributer_application"
venv/bin/python manage.py migrate 2>&1 | tail -5
```

## KORAK 3 — LANDING STRANICA /postani-distributer/

KREIRAJ: templates/website/distributer_landing.html

Design: standalone (ne extends base), Space Grotesk, dark + gold.
Sekcije:
1. Hero: "Postanite distributer LIMIT Connect-a u vašem gradu"
   Tagline: "Slobodna područja: Split, Rijeka, Varaždin, Dubrovnik, Karlovac..."
   CTA: "Prijavite se — besplatno"

2. Kako funkcionira (3 koraka):
   → Prijavite se → Ivan odobrava (48h) → Dobivate branded link i dashboard

3. Zarada kalkulator (pure JS):
   Slider: broj klijenata (5-200)
   Izračun: klijenti × 29 EUR × 15% = vaša komisija/mj
   Live update

4. Forma za prijavu (svi fieldi iz modela)

5. Footer: "Slobodna područja su ograničena. Brži osvaja grad."

VIEW:
```python
def distributer_landing(request):
    from companies.models import DistributerApplication
    if request.method == 'POST':
        app = DistributerApplication(
            name              = request.POST.get('name','').strip(),
            company_name      = request.POST.get('company_name','').strip(),
            email             = request.POST.get('email','').strip(),
            phone             = request.POST.get('phone','').strip(),
            city              = request.POST.get('city','').strip(),
            region            = request.POST.get('region','').strip(),
            target_clients    = request.POST.get('target_clients',10),
            business_type     = request.POST.get('business_type','').strip(),
            motivation        = request.POST.get('motivation','').strip(),
            has_accounting    = 'has_accounting' in request.POST,
            requested_subdomain = request.POST.get('requested_subdomain','').strip(),
        )
        app.save()
        # WhatsApp Ivan
        try:
            from notifications.whatsapp import send_whatsapp
            send_whatsapp('+4915771998747',
                f'🏢 NOVI DISTRIBUTER!\n{app.company_name}\n'
                f'{app.city} | {app.email}\n'
                f'Klijenti: {app.target_clients} | Sub: {app.requested_subdomain}\n'
                f'/superadmin/distributer/{app.pk}/approve/')
        except: pass
        return render(request, 'website/distributer_hvala.html', {'app': app})
    return render(request, 'website/distributer_landing.html', {
        'page_title': 'Postanite distributer'
    })
```

## KORAK 4 — COCKPIT APPROVE (superadmin)

READ: superadmin_ai/ ili core/ — gdje su superadmin views?

DODAJ view za pregled i odobravanje:
```python
@staff_member_required
def distributer_applications(request):
    from companies.models import DistributerApplication
    apps = DistributerApplication.objects.order_by('-created_at')
    return render(request, 'superadmin/distributer_applications.html', {'apps': apps})

@staff_member_required
@require_POST
def distributer_approve(request, pk):
    """Odobi + auto-setup WhiteLabel."""
    from companies.models import DistributerApplication, WhiteLabelConfig, LicenseToken
    from django.contrib.auth.models import User
    from django.utils import timezone
    import datetime

    app = DistributerApplication.objects.get(pk=pk)

    # Pronađi ili kreiraj user za distributora
    user, created = User.objects.get_or_create(
        email=app.email,
        defaults={'username': app.requested_subdomain or app.email.split('@')[0],
                  'first_name': app.name.split()[0] if app.name else ''}
    )

    # Kreiraj WhiteLabel
    wl, _ = WhiteLabelConfig.objects.get_or_create(
        subdomain=app.requested_subdomain or app.city.lower().replace(' ','-'),
        defaults={
            'owner': user,
            'brand_name': app.company_name,
            'primary_color': '#c9a84c',
            'fiscal_system': 'HR',
            'tagline': f'Vaš LIMIT Connect partner u {app.city}',
        }
    )

    # Kreiraj LicenseToken (1 godina)
    LicenseToken.objects.get_or_create(
        white_label=wl,
        defaults={
            'status': 'active',
            'valid_until': timezone.now() + datetime.timedelta(days=365),
            'monthly_amount_eur': 0,
        }
    )

    app.status = 'approved'
    app.white_label = wl
    app.reviewed_by = request.user
    app.save()

    # WhatsApp distributoru
    try:
        from notifications.whatsapp import send_whatsapp
        send_whatsapp(app.phone,
            f'✅ Čestitamo! Vaša prijava za LIMIT Connect distributora je odobrena.\n'
            f'Vaš portal: https://{wl.subdomain}.limit-connect.com\n'
            f'Kontakt: info@limit-connect.com')
    except: pass

    messages.success(request, f'Distributer odobren: {app.company_name}')
    return redirect('distributer_applications')
```

## KORAK 5 — URLS + TEMPLATE (superadmin lista)

URL:
```python
path('postani-distributer/', views.distributer_landing, name='distributer_landing'),
path('superadmin/distributori/', views.distributer_applications, name='distributer_applications'),
path('superadmin/distributori/<int:pk>/approve/', views.distributer_approve, name='distributer_approve'),
```

Superadmin template: distributer_applications.html — tablica s Name/City/Klijenti/Status + Approve gumb

## KORAK 6 — COMMIT
```bash
venv/bin/python manage.py check 2>&1 | tail -3
git add -A && git commit -m "feat(distributer): onboarding landing, forma, cockpit approve, auto WhiteLabel setup"
```

DONE: [ ] Model + migracija [ ] Landing /postani-distributer/ [ ] Zarada kalkulator JS [ ] Cockpit approve [ ] Auto WhiteLabel setup [ ] WhatsApp notifikacija
