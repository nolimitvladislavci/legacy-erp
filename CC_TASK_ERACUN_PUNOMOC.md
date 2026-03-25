# CC_TASK_ERACUN_PUNOMOC — e-Račun punomoć za računovođe
# Agent: CC Code
# Prioritet: VISOK — showstopper za računovođe (Marija Brtan use case)
# Datum: 2026-03-25
# Verificirano: Sonnet direktno na serveru

---

## Što postoji (NE DIRAJ)
- ✅ `eracun/models.py` → `ERacunConfig`: cert_path, use_test_env, api_key, auto_send
- ✅ `eracun/services/posrednik_service.py`: PosrednikService.send(), _send_moj_eracun(), mTLS
- ✅ `eracun/services/ubl_generator.py`: UBL XML generator
- ✅ `eracun/views_posrednik.py`: views za posrednika
- ✅ Sandbox/production switch: `use_test_env` flag na ERacunConfig

## Što ne postoji — 0%

Nema **nijednog** modela, viewa, templatea za:
- Punomoć/ovlast računovođe da šalje e-račune u ime klijenta
- Registracija posrednika na FINA/Moj-eRacun
- Multi-klijent workflow (Marija šalje za 78 firmi)

---

## Što treba kreirati

### 1. Model: `ERacunMandate` (punomoć)

```python
# eracun/models.py — dodaj na kraj

class ERacunMandate(models.Model):
    """
    Punomoć: računovođa (mandatar) ovlašten slati e-račune u ime klijenta (mandant).
    
    Marija Brtan (Konjik d.o.o.) = mandatar za 78 firmi.
    Svaka firma potpisuje punomoć → Marija može slati bez daljnjih odobrenja.
    """
    class Status(models.TextChoices):
        PENDING  = 'pending',  'Čeka potpis klijenta'
        ACTIVE   = 'active',   'Aktivna'
        REVOKED  = 'revoked',  'Opozvana'
        EXPIRED  = 'expired',  'Istekla'

    # Mandatar (računovođa)
    mandatar = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='given_eracun_mandates',
        verbose_name='Računovođa (mandatar)',
    )
    # Mandant (klijent čija se firma zastupa)
    mandant = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='received_eracun_mandates',
        verbose_name='Klijent (mandant)',
    )
    
    status = models.CharField(max_length=10, choices=Status.choices, default='pending')
    
    # Ovlasti
    can_send_outbound = models.BooleanField(default=True, verbose_name='Može slati izlazne e-račune')
    can_receive_inbox = models.BooleanField(default=True, verbose_name='Može čitati ulazne e-račune')
    can_configure     = models.BooleanField(default=False, verbose_name='Može mijenjati konfiguraciju')
    
    # Vremenski okvir
    valid_from = models.DateField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True, verbose_name='Vrijedi do (prazno=trajno)')
    
    # Dokument punomoći
    mandate_pdf = models.FileField(
        upload_to='eracun_mandates/%Y/',
        null=True, blank=True,
        verbose_name='Potpisana punomoć (PDF)',
    )
    mandate_signed_at = models.DateTimeField(null=True, blank=True)
    mandate_signed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='signed_mandates',
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['mandatar', 'mandant']]
        verbose_name = 'e-Račun punomoć'
        verbose_name_plural = 'e-Račun punomoći'

    def is_valid(self):
        from django.utils import timezone
        if self.status != 'active':
            return False
        if self.valid_until and self.valid_until < timezone.now().date():
            return False
        return True
```

### 2. PosrednikService — provjera punomoći

`eracun/services/posrednik_service.py` — u `send()` metodi dodaj:

```python
@classmethod
def send(cls, eracun, acting_as_company=None):
    """
    acting_as_company: ako računovođa šalje u ime klijenta,
    proslijedi klijentovu Company — provjerit će se punomoć.
    """
    if acting_as_company:
        from eracun.models import ERacunMandate
        mandate = ERacunMandate.objects.filter(
            mandatar=acting_as_company,
            mandant=eracun.company,
            status='active',
        ).first()
        if not mandate or not mandate.is_valid():
            raise PermissionError(
                f'Nema aktivne punomoći za slanje e-računa u ime {eracun.company.name}'
            )
        if not mandate.can_send_outbound:
            raise PermissionError('Punomoć ne uključuje slanje izlaznih e-računa')
    
    # ... ostatak send() nepromjenjen
```

### 3. Views — 3 endpointa

```python
# eracun/views_mandate.py (novi fajl)

@login_required
def mandate_list(request):
    """Računovođa vidi sve klijente kojima može slati."""
    company = get_user_company(request)
    mandates = ERacunMandate.objects.filter(mandatar=company, status='active')
    return render(request, 'eracun/mandate_list.html', {'mandates': mandates})

@login_required  
def mandate_create(request):
    """Pozovi klijenta na punomoć — šalje email s linkom za potpisivanje."""
    # POST: mandant_company_id, can_send_outbound, can_receive_inbox, valid_until
    ...

@login_required
def mandate_sign(request, token):
    """Klijent klikne link iz emaila → potvrdi punomoć."""
    # Token je JWT s mandant company_id i expiry
    # Klijent vidi detalje i klikne "Potpisujem"
    ...
```

URL: 
```python
path('eracun/mandates/', views_mandate.mandate_list, name='mandate_list'),
path('eracun/mandates/create/', views_mandate.mandate_create, name='mandate_create'),
path('eracun/mandates/sign/<str:token>/', views_mandate.mandate_sign, name='mandate_sign'),
```

### 4. Template: mandate_list.html

Tablica: Klijent | Status | Ovlasti | Vrijedi do | Akcije (opozovi)
Gumb "Pozovi novog klijenta" → mandate_create

### 5. PDF punomoći — auto-generacija

Pri aktivaciji punomoći, generiraj PDF s:
- Podaci mandatara (računovođa)
- Podaci mandanta (klijent)  
- Ovlasti
- Datum, potpis (checkbox = elektronski potpis)

Koristiti `weasyprint` (već instaliran) ili `reportlab`.

---

## Marija Brtan seed (odmah nakon deploy)

```python
# management command ili fixture:
# Kreiraj ERacunMandate za Marija → svaki od 78 klijenata
# Status: pending (klijenti moraju potvrditi)
# can_send_outbound: True
# can_receive_inbox: True
```

---

## Definition of Done

- [ ] Migracija `ERacunMandate` modela
- [ ] PosrednikService.send() provjerava punomoć
- [ ] 3 views (list, create, sign)
- [ ] 2 templates (list, sign)
- [ ] PDF punomoći generacija
- [ ] Admin registracija
- [ ] Test: Marija može poslati e-račun za Konjik klijenta, bez punomoći dobiva PermissionError
- [ ] Commit: `feat: eracun punomoć — ERacunMandate model, mandate workflow, Marija multi-klijent`

---

## Zakonska osnova
- Zakon o obveznim odnosima (NN 35/05) — punomoć, zastupanje
- e-Račun standardi (CEN EN 16931) — ne zahtijeva eksplicitnu punomoć u XMLu
- GDPR: mandant mora znati da računovođa pristupa njegovim računima
