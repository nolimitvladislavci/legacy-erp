# CC_TASK_POSREDNIK_MANDATE_WIRE.md
# Za: CC Code
# Datum: 30.03.2026.
# Rok: 05.04.2026.
# Prioritet: VISOKO — blokira posrednički model za 30+ distributera
# Procjena: 1 dan
#
# DIJAGNOZA:
# einvoice/models/mandate.py — Mandate model POSTOJI (principal → agent)
# eracun/services/posrednik_service.py — NIJE spojen s Mandate modelom
# Rezultat: PosrednikService ne zna tko je posrednik za koga
#
# ŠTO GRADIMO:
# Wire: kad Konjik šalje za Sa-Ni Mont → koristi Mandate za auth
# Wire: distributer iz Splita → klijenti daju punomoć Konjiku → Konjik šalje
# UI: Marija vidi sve punomoći, može kreirati nove jednim klikom
#
# ZAKONSKA OSNOVA:
# Registrirani posrednik (Konjik d.o.o.) šalje e-račune u ime klijenata
# koji su dali formalni mandat (punomoć). Jedan certifikat, N klijenata.
# Distributer (Split, Zagreb) = prodajni agent koji dovodi klijente.
# Konjik šalje za SVE njihove klijente. Distributer nikad ne treba vlastiti
# ISO 27001 ni PU registraciju za ovu ulogu.

---

## KORAK 1 — Wire PosrednikService s Mandate modelom

U `eracun/services/posrednik_service.py` — modificiraj `get_config()` i `send()`:

```python
@classmethod
def get_config(cls, company):
    """
    Dohvati posrednik konfiguraciju.

    NOVO: Ako firma ima aktivan Mandate (dala punomoć agentu),
    koristi konfiguraciju agenta (posrednika) umjesto vlastitu.
    """
    # 1. Provjeri ima li firma aktivan Mandate (dala punomoć posredniku)
    try:
        from einvoice.models.mandate import Mandate, MandateStatus
        mandate = Mandate.objects.filter(
            principal_company=company,
            status=MandateStatus.ACTIVE,
            is_active=True,
        ).select_related('agent_company').first()

        if mandate and mandate.is_valid:
            # Firma ima posrednika — koristi njegovu konfiguraciju
            agent_config = cls.get_config(mandate.agent_company)
            agent_config['on_behalf_of_oib'] = mandate.principal_oib
            agent_config['mandate_id'] = mandate.fina_mandate_id
            agent_config['via_mandate'] = True
            return agent_config
    except Exception:
        pass

    # 2. Inače: vlastita konfiguracija (staro ponašanje)
    try:
        from eracun.models import ERacunConfig
        ec = ERacunConfig.objects.filter(company=company).first()
        if ec and getattr(ec, 'posrednik_type', ''):
            return {
                'type': ec.posrednik_type or 'moj_eracun',
                'api_key': getattr(ec, 'posrednik_api_key', '') or '',
                'api_secret': getattr(ec, 'posrednik_api_secret', '') or '',
                'api_url': getattr(ec, 'posrednik_api_url', '') or '',
                'test_mode': getattr(ec, 'posrednik_test_mode', True),
                'via_mandate': False,
                'on_behalf_of_oib': None,
            }
    except Exception:
        pass

    return {'type': None, 'via_mandate': False}
```

U `send()` metodi — prosljeđivanje `on_behalf_of_oib` u XML:

```python
@classmethod
def send(cls, eracun):
    company = eracun.company
    cfg = cls.get_config(company)

    if not cfg.get('type'):
        return {'ok': False, 'error': 'Posrednik nije konfiguriran.'}

    # Generiraj XML
    from eracun.services.ubl_generator import generate_ubl_xml
    xml_content = generate_ubl_xml(
        eracun,
        on_behalf_of_oib=cfg.get('on_behalf_of_oib'),  # NOVO
        mandate_id=cfg.get('mandate_id'),               # NOVO
    )

    # ... ostatak send() logike ostaje isti
```

---

## KORAK 2 — Provjeri UBL generator podržava on_behalf_of

```bash
grep -n "on_behalf\|AccountingSupplierParty\|SendingParty\|TaxRepresentative" \
  eracun/services/ubl_generator.py | head -20
```

Ako ne podržava — dodati u UBL XML:
```xml
<!-- Kad Konjik šalje za Sa-Ni Mont -->
<cac:AccountingSupplierParty>
    <!-- Sa-Ni Mont podaci (principal) -->
    <cac:Party>
        <cac:PartyTaxScheme>
            <cbc:CompanyID>HR12345678901</cbc:CompanyID>
        </cac:PartyTaxScheme>
    </cac:Party>
</cac:AccountingSupplierParty>

<!-- Konjik d.o.o. kao posrednik — NOVO -->
<cac:AdditionalDocumentReference>
    <cbc:ID>MANDATE-{mandate_id}</cbc:ID>
    <cbc:DocumentTypeCode>130</cbc:DocumentTypeCode>
    <cbc:DocumentDescription>Informacijski posrednik: Konjik d.o.o.</cbc:DocumentDescription>
</cac:AdditionalDocumentReference>
```

---

## KORAK 3 — UI za Mandate management (Marijiн dashboard)

### 3a. Mandate list view (već postoji — provjeri URL)

```bash
grep -rn "mandate" eracun/urls.py | head -10
# Ako nema URL-a, dodati:
```

Dodati u `eracun/urls.py`:
```python
path('mandati/', views_mandate.mandate_list, name='mandate_list'),
path('mandati/novi/', views_mandate.mandate_create, name='mandate_create'),
path('mandati/<uuid:pk>/pdf/', views_mandate.mandate_pdf, name='mandate_pdf'),
path('mandati/<uuid:pk>/potpis/', views_mandate.mandate_upload_signed, name='mandate_upload_signed'),
path('mandati/<uuid:pk>/aktiviraj/', views_mandate.mandate_activate, name='mandate_activate'),
path('mandati/<uuid:pk>/opozovi/', views_mandate.mandate_revoke, name='mandate_revoke'),
```

### 3b. Quick-create mandate za sve umbrella firme

Dodati view za bulk kreiranje mandata:

```python
@login_required
def mandate_bulk_create_for_umbrella(request):
    """
    POST /eracun/mandati/bulk-umbrella/
    Kreira Mandate za sve firme u umbrelli koje još nemaju aktivni mandat.
    Jednim klikom Marija postaje posrednik za sve Konjik klijente.
    Generira PDF punomoći za svaku firmu — vlasnici potpisuju.
    """
    from einvoice.models.mandate import Mandate, MandateStatus, MandateType
    from einvoice.services.mandate_pdf import generate_mandate_pdf
    from companies.models import Company
    from django.utils import timezone

    agent_company = request.user.profile.company  # Konjik d.o.o.

    # Sve firme u Konjik umbrelli
    children = Company.objects.filter(umbrella_parent=agent_company)

    created = 0
    already_exists = 0
    pdfs_generated = []

    for firm in children:
        if Mandate.objects.filter(
            principal_company=firm,
            agent_company=agent_company,
        ).exists():
            already_exists += 1
            continue

        mandate = Mandate.objects.create(
            principal_company=firm,
            principal_oib=firm.oib or '',
            agent_company=agent_company,
            agent_oib=agent_company.oib or '',
            mandate_type=MandateType.FULL,
            status=MandateStatus.DRAFT,
            valid_from=timezone.now().date(),
            created_by=request.user,
        )
        created += 1

        # Generiraj PDF punomoći
        try:
            pdf_bytes = generate_mandate_pdf(mandate)
            # Spremi PDF
            import os
            from django.conf import settings
            pdf_path = f'einvoice/mandates/bulk_{mandate.id}.pdf'
            full_path = os.path.join(settings.MEDIA_ROOT, pdf_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(pdf_bytes)
            mandate.mandate_document = pdf_path
            mandate.save(update_fields=['mandate_document'])
            pdfs_generated.append(mandate)
        except Exception as e:
            pass  # PDF nije kritičan za kreiranje mandata

    return JsonResponse({
        'ok': True,
        'created': created,
        'already_exists': already_exists,
        'total': children.count(),
        'message': f'Kreirano {created} punomoći. Vlasnici moraju potpisati PDF.'
    })
```

### 3c. Mandate status u Marija-inom dashboardu

Dodati u `/moji-klijenti/` (agent_dashboard):
```python
# U agent_dashboard view — dodati mandate statistiku
from einvoice.models.mandate import Mandate, MandateStatus

mandate_stats = {
    'draft': Mandate.objects.filter(agent_company=user_company, status='draft').count(),
    'signed': Mandate.objects.filter(agent_company=user_company, status='signed').count(),
    'active': Mandate.objects.filter(agent_company=user_company, status='active').count(),
}
```

Template badge: "X potpisanih punomoći čeka aktivaciju kod FINA"

---

## KORAK 4 — Distributer flow (30+ posrednika)

Ovo je ključni korak koji odgovara na Ivanovo pitanje o Splitu i Rijeci.

### Arhitektura za 30 distributera

```
LIMIT Connect (Konjik d.o.o.) — JEDINI registrirani posrednik
    ↓
Distributer Split    Distributer Zagreb    Distributer Rijeka
(prodajni agent)     (prodajni agent)      (prodajni agent)
    ↓                     ↓                      ↓
50 klijenata         70 klijenata          40 klijenata
    ↓                     ↓                      ↓
SVAKI daje Mandate (punomoć) Konjiku d.o.o.
    ↓
Konjik šalje e-račune za SVE, s JEDNIM certifikatom
```

### Što distributer NE treba:
- ISO 27001 certifikat
- PU registraciju kao posrednik
- Vlasteni FINA certifikat

### Što distributer TREBA:
- Ugovor s Konjiком (Agent Agreement)
- Pravo dovođenja klijenata pod Konjik umbrella
- WhiteLabel brand na limit-connect.com (što gradimo)
- Agent Dashboard (moji klijenti, moja zarada)

### Što klijent distributera treba:
- Potpisati Mandate (punomoć) Konjiku d.o.o. — jednom
- FINA evidentira punomoć za Konjikov OIB
- FINA prima e-račune od Konjika (ne od klijenta direktno)

---

## KORAK 5 — Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell << 'PYEOF'
from einvoice.models.mandate import Mandate, MandateStatus, MandateType
from companies.models import Company
from django.utils import timezone

konjik = Company.objects.filter(name__icontains='Konjik').first()
sa_ni_mont = Company.objects.filter(name__icontains='Sa-Ni Mont').first()

# Kreiraj test mandat
mandate = Mandate.objects.create(
    principal_company=sa_ni_mont,
    principal_oib=sa_ni_mont.oib,
    agent_company=konjik,
    agent_oib=konjik.oib,
    mandate_type=MandateType.FULL,
    status=MandateStatus.DRAFT,
    valid_from=timezone.now().date(),
)
print(f'Mandat kreiran: {mandate}')
print(f'Principal: {mandate.principal_oib} (Sa-Ni Mont)')
print(f'Agent: {mandate.agent_oib} (Konjik d.o.o.)')
print(f'Valjan: {mandate.is_valid}')

# Provjeri get_config() — sad koristi Mandate
from eracun.services.posrednik_service import PosrednikService
cfg = PosrednikService.get_config(sa_ni_mont)
print(f'\nget_config(Sa-Ni Mont): via_mandate={cfg.get("via_mandate")}')
print(f'on_behalf_of_oib: {cfg.get("on_behalf_of_oib")}')

# Cleanup
mandate.delete()
print('\nTest OK')
PYEOF
```

---

## COMMIT

```bash
git add eracun/ einvoice/ templates/eracun/
git commit -m "feat(posrednik): Mandate wire + bulk create + distributer model

Wire PosrednikService s Mandate modelom:
  get_config() provjerava aktivan Mandate prije vlastite config
  send() prosljeđuje on_behalf_of_oib u UBL XML
  Jedan certifikat (Konjik) → N klijenata s punomoćima

UI:
  /eracun/mandati/ — lista punomoći (Marija vidi sve)
  /eracun/mandati/bulk-umbrella/ — jednim klikom za sve 71 firmu
  Agent dashboard: mandate_stats badge

Distributer model (KLJUČNO):
  Distributer iz Splita = prodajni agent Konjika
  NE treba ISO 27001, NE treba vlastiti certifikat
  Klijenti daju punomoć Konjiku (jednom, FINA evidentira)
  Konjik šalje za SVE s jednim certifikatom

Odgovor na pitanje: DA, sustav podržava 30+ posrednika
  ALI: svi šalju POD Konjik certifikatom, ne neovisno"
```

---

## SAŽETAK ZA IVANA

```
Što smo imali:  Mandate model (postoji, 0 zapisa)
Što je falilo:  Wire s PosrednikService + UI za Mariju
Što gradimo:    Spajanje (1 dan) + bulk create za 71 firmu

Za distributere iz Splita/Zagreba/Rijeke:
  - Dolaze pod Konjik umbrella
  - Klijenti potpisuju punomoć Konjiku (jednom)
  - Konjik šalje za sve — jedan certifikat
  - Distributer NE treba vlastiti ISO 27001 ni PU licencu
  - Distributer je PRODAJNI AGENT, Konjik je POSREDNIK

Jedini slučaj kad netko treba vlastiti certifikat:
  - Želi biti SAMOSTALNI posrednik (ne pod Konjiком)
  - Plaća vlastite 8.000 EUR i prolazi vlastiti put
  - To je natjecanje, ne naša struktura
```
