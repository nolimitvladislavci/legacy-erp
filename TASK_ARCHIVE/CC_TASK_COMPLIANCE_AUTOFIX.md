# CC_TASK_COMPLIANCE_AUTOFIX — Automatska korekcija compliance podataka

**Autor:** Sonnet (13.04.2026)
**Prioritet:** Srednje — ne blokira produkciju, ali kazne su realne
**Ovisnosti:** Global Validation Engine mora biti aktivan (core/validation_engine.py ✅)

---

## Pravila izvršavanja

1. **Čitaj modele prije pisanja** — uvijek provjeri field names u models.py
2. **Ne upisuj OIB automatski** — OIB je osjetljiv osobni podatak, samo PREDLOŽI
3. **Ne diraj:** `base.html`, `core/settings.py`, `core/urls.py`, `.env`
4. **Svaki nalaz** → `ImprovementSuggestion(source='system', trojstvo_status='pending')`
5. **WhatsApp obavijest** → samo za priority=1 nalaze, samo između 20-22h (SEKI_KOMUNIKACIJA.md pravilo)

---

## TASK A — Zaposlenici bez OIB-a (8 radnika)

### Korak 1: Pronađi radnike bez OIB-a

```python
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from worktime.models import EmployeeProfile
from companies.models import Company
from django.utils import timezone

missing = EmployeeProfile.objects.filter(
    tax_id='',
    is_terminated=False,
).exclude(
    user__is_active=False
).select_related('user', 'company')

print(f"Radnika bez OIB-a: {missing.count()}")
for emp in missing:
    print(f"  - {emp.user.get_full_name()} | {emp.company.name} | {emp.user.email}")
```

### Korak 2: Pretraži vlastitu bazu (cross-tenant lookup)

Za svakog radnika bez OIB-a — provjeri postoji li isti korisnik negdje drugdje u bazi:

```python
from django.contrib.auth import get_user_model
User = get_user_model()

for emp in missing:
    full_name = emp.user.get_full_name().strip()
    email = emp.user.email.strip()

    # Traži po emailu u drugim profilima
    other_profiles = EmployeeProfile.objects.filter(
        user__email__iexact=email
    ).exclude(
        pk=emp.pk
    ).exclude(tax_id='')

    # Traži po imenu u Synesis importu (partners app)
    try:
        from partners.models import Partner
        name_parts = full_name.split()
        if len(name_parts) >= 2:
            partner_match = Partner.objects.filter(
                name__icontains=name_parts[0],
                name__icontains=name_parts[-1] if len(name_parts) > 1 else name_parts[0],
            ).exclude(oib='').first()
        else:
            partner_match = None
    except Exception:
        partner_match = None

    suggestion = None
    if other_profiles.exists():
        found_oib = other_profiles.first().tax_id
        suggestion = f"PRONAĐEN OIB u drugoj firmi: {found_oib} — POTREBNA RUČNA POTVRDA prije unosa"
        priority = 2
    elif partner_match:
        suggestion = f"MOGUĆI OIB iz Synesis baze: {partner_match.oib} (partner: {partner_match.name}) — POTREBNA RUČNA POTVRDA"
        priority = 2
    else:
        suggestion = "OIB nije pronađen u sustavu — firma mora unijeti ručno"
        priority = 1

    # Kreiraj ImprovementSuggestion
    from pos.models import ImprovementSuggestion
    platform = Company.objects.filter(is_platform_owner=True).first() or Company.objects.first()

    ImprovementSuggestion.objects.get_or_create(
        title=f"[OIB] Radnik bez OIB-a: {full_name} ({emp.company.name})",
        defaults=dict(
            company=emp.company,
            source='system',
            description=(
                f"Radnik: {full_name}\n"
                f"Firma: {emp.company.name}\n"
                f"Email: {email}\n"
                f"Zakon o fiskalizaciji čl. 9 — kazna do 66.000 EUR po radniku.\n\n"
                f"Rezultat pretrage: {suggestion}"
            ),
            category='workflow',
            priority=priority,
            trojstvo_status='pending',
        )
    )
    print(f"  Suggestion kreirana: {full_name} | {suggestion[:60]}")
```

### Korak 3: WhatsApp obavijest firmama (samo priority=1)

Za firme gdje OIB nije pronađen, pošalji vlasničkoj firmi kratku obavijest:

```python
from core.whatsapp import send_text, is_gateway_healthy
from django.utils import timezone

# Samo između 20-22h!
current_hour = timezone.localtime().hour
if not (20 <= current_hour < 22):
    print("Van radnog vremena za WhatsApp (pravilo: 20-22h) — preskačem")
else:
    if is_gateway_healthy():
        # Grupiraj po firmi — jedna poruka po firmi, ne po radniku
        from django.db.models import Count
        firms_missing = missing.values(
            'company__name', 'company__id'
        ).annotate(count=Count('id'))

        for firm in firms_missing:
            company = Company.objects.get(pk=firm['company__id'])
            # Pronađi admin korisnika firme
            try:
                from accounts.models import UserProfile
                admin = UserProfile.objects.filter(
                    company=company,
                    role__in=['company_admin', 'tenant_admin']
                ).select_related('user').first()
                if admin and hasattr(admin, 'phone') and admin.phone:
                    msg = (
                        f"LIMIT Connect upozorenje:\n"
                        f"{firm['count']} radnik(a) u firmi {company.name} "
                        f"nema uneseni OIB.\n"
                        f"Zakon o fiskalizaciji — kazna do 66.000 EUR po radniku.\n"
                        f"Unesite OIB u: Radnici → Uredi profil."
                    )
                    send_text(admin.phone, msg, company_id=str(company.id))
                    print(f"  WhatsApp poslan: {company.name}")
            except Exception as e:
                print(f"  WhatsApp greška za {company.name}: {e}")
    else:
        print("WhatsApp gateway nije dostupan")
```

---

## TASK B — Negativne zalihe (13 stavki)

### Korak 1: Pronađi sve negativne zalihe

```python
from inventory.models import InventoryItem
from django.db.models import F

negative = InventoryItem.objects.filter(
    quantity__lt=0
).select_related('company')

print(f"Artikala s negativnim zalihama: {negative.count()}")
for item in negative:
    print(f"  - {item.name} | qty: {item.quantity} | {item.company.name}")
```

### Korak 2: Provjeri postoji li otvorena primka

Za svaki negativni artikl provjeri postoji li primka u statusu 'draft' ili 'open' koja pokriva taj artikl:

```python
for item in negative:
    has_open_receipt = False
    receipt_hint = ""

    try:
        from inventory.models import GoodsReceipt, GoodsReceiptItem
        open_receipt = GoodsReceiptItem.objects.filter(
            item=item,
            receipt__status__in=['draft', 'open', 'pending'],
            receipt__company=item.company,
        ).select_related('receipt').first()

        if open_receipt:
            has_open_receipt = True
            receipt_hint = (
                f"Otvorena primka #{open_receipt.receipt.id} "
                f"od {open_receipt.receipt.created_at:%d.%m.%Y} — "
                f"potrebno knjiženje"
            )
    except Exception:
        pass

    # Provjeri i POS prodaje za zadnjih 7 dana (možda je prodano bez primke)
    try:
        from pos.models import POSReceiptItem
        from django.utils import timezone
        from datetime import timedelta
        recent_sales = POSReceiptItem.objects.filter(
            product__name__icontains=item.name,
            receipt__company=item.company,
            receipt__created_at__gte=timezone.now() - timedelta(days=7),
        ).count()
        if recent_sales > 0:
            receipt_hint += f" | {recent_sales} prodaja u zadnjih 7 dana"
    except Exception:
        pass

    from pos.models import ImprovementSuggestion
    from companies.models import Company

    if has_open_receipt:
        description = (
            f"Artikl: {item.name}\n"
            f"Trenutna količina: {item.quantity}\n"
            f"Firma: {item.company.name}\n\n"
            f"UZROK: {receipt_hint}\n\n"
            f"PREPORUČENA AKCIJA: Zatvori/knjiži otvorenu primku."
        )
        priority = 2
    else:
        description = (
            f"Artikl: {item.name}\n"
            f"Trenutna količina: {item.quantity}\n"
            f"Firma: {item.company.name}\n"
            f"{receipt_hint}\n\n"
            f"PREPORUČENA AKCIJA: Napravite inventuru i unesite primku za razliku.\n"
            f"Negativna zaliha blokira buduće POS prodaje."
        )
        priority = 2

    ImprovementSuggestion.objects.get_or_create(
        title=f"[ZALIHE] Negativna zaliha: {item.name} ({item.company.name})",
        defaults=dict(
            company=item.company,
            source='system',
            description=description,
            category='workflow',
            priority=priority,
            trojstvo_status='pending',
        )
    )
    print(f"  Suggestion kreirana: {item.name} (qty: {item.quantity}) | {item.company.name}")
```

### Korak 3: Pokretanje Trojstvo analize za sve nove sugestije

```python
from pos.models import ImprovementSuggestion
from pos.trojstvo_task import trojstvo_rijesi

# Pokreni Trojstvo za sve nove sugestije iz ovog taska
new_suggestions = ImprovementSuggestion.objects.filter(
    source='system',
    trojstvo_status='pending',
    title__startswith='[OIB]',
).union(
    ImprovementSuggestion.objects.filter(
        source='system',
        trojstvo_status='pending',
        title__startswith='[ZALIHE]',
    )
)

count = 0
for s in new_suggestions:
    trojstvo_rijesi.delay(s.pk)
    count += 1

print(f"Trojstvo analiza pokrenuta za {count} sugestija")
```

---

## Korak 4: Napiši rezultate u PORTAL_AUDIT_REZULTATI.md

Na kraju dodaj sekciju u postojeći audit dokument:

```python
import os
from django.utils import timezone

result_path = '/var/www/fina-connect/PORTAL_AUDIT_REZULTATI.md'
existing = open(result_path).read() if os.path.exists(result_path) else ''

addition = f"""

---

## Compliance Autofix — {timezone.now():%d.%m.%Y %H:%M}

### OIB radnika
- Pronađeno radnika bez OIB-a: {missing.count()}
- OIB pronađen u bazi (predložen): X
- OIB nije pronađen (firma mora unijeti): Y
- ImprovementSuggestion kreiran za svakoga: ✅
- WhatsApp obavijest firmama: ✅ (ako 20-22h) / ⏳ (čeka večer)

### Negativne zalihe
- Pronađeno artikala s negativnom zalihom: {negative.count()}
- S otvorenom primkom: X
- Bez primke (inventura potrebna): Y
- ImprovementSuggestion kreiran za svaki artikl: ✅

### Trojstvo
- Analize pokrenute: {count}
- Rezultati dostupni u: /admin/pos/improvementsuggestion/
"""

with open(result_path, 'a') as f:
    f.write(addition)

print("Rezultati zapisani u PORTAL_AUDIT_REZULTATI.md")
```

---

## Napomene

- **OIB se NIKADA ne upisuje automatski** — Trojstvo može predložiti, ali unos potvrđuje čovjek
- **WhatsApp samo 20-22h** — pravilo iz SEKI_KOMUNIKACIJA.md vrijedi za sve poslovne kontakte
- Ako nema `GoodsReceipt` modela u inventory app — preskočiti korak primke, samo kreirati suggestion
- Provjeri `EmployeeProfile` field names prije pokretanja: `tax_id` ili `oib` (čitaj models.py!)
- Provjeri `InventoryItem` field names: `quantity` ili `stock_quantity` (čitaj models.py!)
