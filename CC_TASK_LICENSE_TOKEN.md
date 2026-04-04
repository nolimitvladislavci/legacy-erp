# CC_TASK: LICENSE TOKEN + HEARTBEAT
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P1
# Pretpostavka: WhiteLabelConfig postoji (CC_TASK_WHITELABEL_ENGINE.md)

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: python manage.py check + migrate 2>&1 | tail -5

---

## CILJ

Svaki distributer (WhiteLabel) ima licencu.
Ne plati → grace period (7 dana) → read-only → suspended.
Ivan dobiva WhatsApp alert. GDPR: export uvijek dostupan.

---

## KORAK 1: Provjeri teren

```bash
grep -rn "LicenseToken\|license" --include="*.py" | grep -v venv | head -10
grep -n "WhiteLabelConfig" companies/models.py | head -5
grep -rn "beat_schedule\|CELERY" config/settings.py | head -10
cat core/middleware/__init__.py | grep -n "class\|def " | head -20
```

## KORAK 2: LicenseToken model

READ: `companies/models.py` (zadnjih 30 linija, WhiteLabelConfig class)

DODAJ u `companies/models.py`:

```python
class LicenseToken(models.Model):
    STATUS_CHOICES = [
        ('active',    'Aktivna'),
        ('grace',     'Grace period (kasni plaćanje)'),
        ('suspended', 'Suspendirano'),
        ('cancelled', 'Otkazano'),
    ]

    white_label = models.OneToOneField(
        'WhiteLabelConfig',
        on_delete=models.CASCADE,
        related_name='license_token',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    valid_until = models.DateTimeField()
    grace_until = models.DateTimeField(null=True, blank=True)  # valid_until + 7 dana
    last_heartbeat = models.DateTimeField(auto_now=True)
    
    # Billing info (bez bankovnih podataka — samo meta)
    monthly_amount_eur = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Licencni token'
        verbose_name_plural = 'Licencni tokeni'

    def __str__(self):
        return f'{self.white_label.brand_name} — {self.status} (do {self.valid_until.date()})'

    def is_usable(self):
        """Radi li sustav normalno?"""
        from django.utils import timezone
        now = timezone.now()
        if self.status == 'active' and now <= self.valid_until:
            return True
        if self.status == 'grace' and self.grace_until and now <= self.grace_until:
            return True
        return False

    def days_until_expiry(self):
        from django.utils import timezone
        delta = self.valid_until - timezone.now()
        return max(0, delta.days)

    def enter_grace(self):
        """Pokreni grace period (7 dana)."""
        from django.utils import timezone
        import datetime
        self.status = 'grace'
        self.grace_until = timezone.now() + datetime.timedelta(days=7)
        self.save(update_fields=['status', 'grace_until', 'updated_at'])

    def suspend(self):
        self.status = 'suspended'
        self.save(update_fields=['status', 'updated_at'])

    def renew(self, months=1):
        """Obnovi licencu za N mjeseci od danas."""
        from django.utils import timezone
        import datetime
        base = max(self.valid_until, timezone.now())
        self.valid_until = base + datetime.timedelta(days=30 * months)
        self.status = 'active'
        self.grace_until = None
        self.save(update_fields=['status', 'valid_until', 'grace_until', 'updated_at'])
```

```bash
python venv/bin/python manage.py makemigrations companies --name="add_license_token"
python venv/bin/python manage.py migrate 2>&1 | tail -5
```

## KORAK 3: LicenseCheckMiddleware

READ: `core/middleware/__init__.py` — gdje je WhiteLabelMiddleware

DODAJ odmah iza WhiteLabelMiddleware:

```python
class LicenseCheckMiddleware:
    """
    Blokira pristup za suspendirane distributere.
    Ignorira: /admin/, /static/, /pocni/, /hr/gdpr/, export URLove.
    """
    BYPASS_PATHS = ['/admin/', '/static/', '/media/', '/pocni/', '/hr/gdpr/',
                    '/hr/export/', '/hr/invoice/export/', '/mcp/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        wl = getattr(request, 'white_label', None)
        if wl:
            try:
                token = wl.license_token
                path = request.path
                
                # Bypass za kritične URLove
                if any(path.startswith(p) for p in self.BYPASS_PATHS):
                    pass
                elif not token.is_usable():
                    from django.shortcuts import render
                    return render(request, 'license/suspended.html', {
                        'wl': wl,
                        'token': token,
                        'status': token.status,
                    }, status=402)
                    
                # Sidebar warning ako < 7 dana
                elif token.days_until_expiry() < 7:
                    request.license_warning = True
                    request.license_days = token.days_until_expiry()
                    
            except Exception:
                pass  # Nema tokena = preskačemo (nije WL)
        
        return self.get_response(request)
```

DODAJ u settings MIDDLEWARE (iza WhiteLabelMiddleware):
```bash
sed -i "s/'core.middleware.WhiteLabelMiddleware',/'core.middleware.WhiteLabelMiddleware',\n    'core.middleware.LicenseCheckMiddleware',/" config/settings.py
python venv/bin/python manage.py check 2>&1 | tail -3
```

## KORAK 4: Suspended template

KREIRAJ: `templates/license/suspended.html`

```html
{% extends "base.html" %}
{% block title %}Licenca istekla — {{ wl.brand_name }}{% endblock %}
{% block content %}
<div style="min-height:70vh;display:flex;align-items:center;justify-content:center;text-align:center;padding:2rem;">
  <div>
    <div style="font-size:4rem;margin-bottom:1rem;">🔒</div>
    <h1 style="font-size:2rem;font-weight:800;margin-bottom:.75rem;">Licenca je istekla</h1>
    {% if token.status == 'grace' %}
    <p style="color:var(--text-secondary);max-width:440px;margin:0 auto 2rem;">
      Vaša licenca je u grace periodu. Nemate više pristup od <strong>{{ token.grace_until|date:"d.m.Y." }}</strong>.
      Obnovite licencu da nastavite rad.
    </p>
    {% else %}
    <p style="color:var(--text-secondary);max-width:440px;margin:0 auto 2rem;">
      Vaša licenca je suspendirana. Kontaktirajte LIMIT Connect za obnovu.
    </p>
    {% endif %}
    <p style="margin-bottom:.5rem;"><strong>Vaši podaci su sigurni.</strong> Export je uvijek dostupan.</p>
    <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;margin-top:1.5rem;">
      <a href="/hr/export/" style="background:var(--gold);color:#000;font-weight:700;padding:.75rem 1.5rem;border-radius:8px;">Izvezi podatke</a>
      <a href="mailto:info@limit-connect.com?subject=Obnova licence {{ wl.brand_name }}" 
         style="border:1px solid var(--border);color:var(--text-primary);padding:.75rem 1.5rem;border-radius:8px;">Kontaktiraj podršku</a>
    </div>
  </div>
</div>
{% endblock %}
```

## KORAK 5: Celery beat task — provjera licenci svakih 6h

READ: gdje su def