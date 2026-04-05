# CC_TASK_PROD_6_KONTO_REPORTS_MENU.md
# PRODUCTION MODULE — TASK 6: Konto integracija + PDF Print + Sidebar + Pricing page
# Agent: CC Code #6 / Gemini
# ČEKA: Task 1 DONE, Task 2 DONE (views gotove)
# Paralelno s Task 3, 4, 5

---

## CILJ
4 integracije koje nitko drugi ne dira:
1. Konto knjiženje troška pri završetku naloga
2. PDF print naloga (WeasyPrint)
3. Sidebar/menu link za Production
4. Pricing page — dodati "Proizvodnja" u Professional plan feature listu

---

## TASK 6A — Konto knjiženje (production/konto_integration.py)

```python
"""
production/konto_integration.py
Kreira konto knjiženje pri završetku proizvodnog naloga.

Kontni plan (HR standard):
  6000 - Troškovi materijala (duguje)
  6100 - Troškovi plaća — rad (duguje)
  6200 - Opći troškovi — režija (duguje)
  6009 - Obračun troška (potražuje za sve troškove)
  1300 - Zalihe gotovih proizvoda (duguje)
  7001 - Prihodi od prodaje — interna kalkulacija (potražuje)
"""
from decimal import Decimal


def knjizi_trosak_proizvodnje(order):
    """
    Poziva se iz signals.py nakon completion.
    Kreira KontoEntry s više stavki.
    
    Knjiženje:
      D 6000 / K 6009  → materijal
      D 6100 / K 6009  → rad
      D 6200 / K 6009  → režija
      D 1300 / K 7001  → gotov proizvod na zalihama (po troškovnoj cijeni)
    """
    try:
        from konto.models import KontoEntry, KontoLine
    except ImportError:
        return None  # konto app nije instaliran
    
    if not order.cost_total or order.cost_total == 0:
        return None
    
    from django.utils import timezone
    
    # Glavni zapis
    entry = KontoEntry.objects.create(
        company=order.company,
        date=timezone.now().date(),
        document_number=order.order_number,
        description=f'Trošak proizvodnje — {order.product.name} — {order.actual_quantity} {order.bom.yield_unit}',
        is_auto=True,
        source='production',
    )
    
    lines = []
    
    # Materijal: D 6000
    if order.cost_materials and order.cost_materials > 0:
        lines.append(KontoLine(
            entry=entry,
            account='6000',
            description=f'Materijal — {order.order_number}',
            debit=order.cost_materials,
            credit=Decimal('0'),
        ))
        lines.append(KontoLine(
            entry=entry,
            account='6009',
            description=f'Obračun troška materijala — {order.order_number}',
            debit=Decimal('0'),
            credit=order.cost_materials,
        ))
    
    # Rad: D 6100
    if order.cost_labor and order.cost_labor > 0:
        lines.append(KontoLine(
            entry=entry,
            account='6100',
            description=f'Radna snaga — {order.order_number}',
            debit=order.cost_labor,
            credit=Decimal('0'),
        ))
        lines.append(KontoLine(
            entry=entry,
            account='6009',
            description=f'Obračun troška rada — {order.order_number}',
            debit=Decimal('0'),
            credit=order.cost_labor,
        ))
    
    # Režija: D 6200
    if order.cost_overhead and order.cost_overhead > 0:
        lines.append(KontoLine(
            entry=entry,
            account='6200',
            description=f'Opći troškovi — {order.order_number}',
            debit=order.cost_overhead,
            credit=Decimal('0'),
        ))
        lines.append(KontoLine(
            entry=entry,
            account='6009',
            description=f'Obračun općih troškova — {order.order_number}',
            debit=Decimal('0'),
            credit=order.cost_overhead,
        ))
    
    # Gotov proizvod: D 1300 / K 7001
    lines.append(KontoLine(
        entry=entry,
        account='1300',
        description=f'Gotovi proizvod na zalihi — {order.product.name}',
        debit=order.cost_total,
        credit=Decimal('0'),
    ))
    lines.append(KontoLine(
        entry=entry,
        account='7001',
        description=f'Interna kalkulacija gotovih proizvoda — {order.order_number}',
        debit=Decimal('0'),
        credit=order.cost_total,
    ))
    
    KontoLine.objects.bulk_create(lines)
    
    # Spremi referencu na nalog
    order.konto_entry = entry
    order.save(update_fields=['konto_entry'])
    
    return entry


def storniraj_trosak(order):
    """
    Storno knjiženja — poziva se ako se nalog poništi nakon completion.
    Kreira suprotno knjiženje s oznakom STORNO.
    """
    if not order.konto_entry:
        return None
    
    try:
        from konto.models import KontoEntry, KontoLine
    except ImportError:
        return None
    
    from django.utils import timezone
    
    storno = KontoEntry.objects.create(
        company=order.company,
        date=timezone.now().date(),
        document_number=f'STORNO-{order.order_number}',
        description=f'STORNO — Trošak proizvodnje — {order.product.name}',
        is_auto=True,
        source='production',
    )
    
    # Kopiraj linije s obrnutim duguje/potražuje
    for line in order.konto_entry.lines.all():
        KontoLine.objects.create(
            entry=storno,
            account=line.account,
            description=f'STORNO — {line.description}',
            debit=line.credit,   # swap
            credit=line.debit,   # swap
        )
    
    return storno
```

Dodati poziv u `production/signals.py` → `handle_order_completion`:
```python
# 4. Konto knjiženje
from production.konto_integration import knjizi_trosak_proizvodnje
knjizi_trosak_proizvodnje(order)
```

---

## TASK 6B — PDF Print (production/pdf_views.py)

```python
"""
production/pdf_views.py — WeasyPrint PDF za proizvodni nalog
URL: /production/nalozi/<pk>/print/  (već definiran u Task 2)
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string


@login_required
def order_print(request, pk):
    """
    Renderira order/print.html i servira kao PDF (WeasyPrint).
    Fallback: ako WeasyPrint nije dostupan, servira HTML.
    """
    from core.company_utils import get_user_company
    company = get_user_company(request)
    from production.models import ProductionOrder
    order = get_object_or_404(ProductionOrder, pk=pk, company=company)
    
    context = {
        'order': order,
        'lines': order.lines.select_related('material').all(),
        'costs': order.costs.all(),
        'company': company,
    }
    
    html_string = render_to_string('production/order/print.html', context, request=request)
    
    try:
        from weasyprint import HTML, CSS
        pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{order.order_number}.pdf"'
        return response
    except ImportError:
        # WeasyPrint nije instaliran — vrati HTML
        return HttpResponse(html_string)
```

---

## TASK 6C — Sidebar menu

Naći `templates/includes/_sidebar.html` ili `templates/base.html` gdje su sidebar linkovi.
Pattern search: `grep -rn "work_orders\|Radni nalozi" templates/ | head -10`

Dodati link za Proizvodnju ODMAH IZA work_orders:

```html
{% if perms.production or user.profile.role in "company_admin,superadmin" %}
<li class="nav-item">
  <a href="{% url 'production:dashboard' %}" 
     class="nav-link {% if 'production' in request.resolver_match.namespace %}active{% endif %}">
    <i class="fas fa-industry me-2"></i>
    <span>Proizvodnja</span>
  </a>
</li>
{% endif %}
```

Ako nema `perms.production`, koristiti isti pattern kao work_orders.

---

## TASK 6D — dynamic_menu modul (ako postoji)

Provjeri: `ls /var/www/fina-connect/dynamic_menu/`
Ako postoji `MenuItem` model — dodati:
```python
MenuItem.objects.get_or_create(
    name='Proizvodnja',
    defaults={
        'url_name': 'production:dashboard',
        'icon': 'fas fa-industry',
        'order': 55,  # između work_orders (50) i reports (60)
        'required_module': 'production',
    }
)
```
To možeš pokrenuti kao management command ili u `production/apps.py` → `ready()`.

---

## TASK 6E — Pricing page update

Naći template s pricing planovima:
```bash
grep -rn "Professional\|professional\|49 EUR\|49€" templates/ | grep -v ".bak" | head -10
```

U Professional plan feature listi dodati:
```html
<li>✓ Modul Proizvodnje (BOM, nalozi, MRP)</li>
<li>✓ Troškovnik po seriji</li>
<li>✓ Konto knjiženje troška automatski</li>
```

U Enterprise plan:
```html
<li>✓ Napredna Proizvodnja — više radnih mjesta, QC</li>
```

---

## TASK 6F — Django management command za seed podataka

Kreirati `production/management/commands/seed_production_demo.py`:

```python
"""
Seed demo podataka za production modul.
Usage: venv/bin/python manage.py seed_production_demo --company-id=1
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed demo BOM i radnih mjesta za production modul'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)

    def handle(self, *args, **options):
        from companies.models import Company
        from production.models import BillOfMaterials, BOMLine, WorkCenter
        from inventory.models import InventoryItem
        from decimal import Decimal

        company = Company.objects.get(pk=options['company_id'])
        self.stdout.write(f'Seeding za: {company.name}')

        # Radno mjesto
        wc, _ = WorkCenter.objects.get_or_create(
            company=company, code='LA',
            defaults={'name': 'Linija A', 'capacity_hours_per_day': Decimal('8'),
                      'cost_per_hour': Decimal('25')}
        )
        self.stdout.write(f'  WorkCenter: {wc}')

        # Pronađi ili preskoči BOM ako nema materijala
        products = InventoryItem.objects.filter(company=company, category='product')
        materials = InventoryItem.objects.filter(company=company, category='material')

        if not products.exists() or not materials.exists():
            self.stdout.write(self.style.WARNING(
                '  Nema proizvoda ili materijala u inventory. Dodaj ručno ili kroz UI.'
            ))
            return

        product = products.first()
        material = materials.first()

        bom, created = BillOfMaterials.objects.get_or_create(
            company=company, product=product, version='1.0',
            defaults={
                'name': f'{product.name} — osnovna sastavnica',
                'yield_quantity': Decimal('10'),
                'yield_unit': product.unit or 'kom',
                'is_active': True,
            }
        )
        if created:
            BOMLine.objects.create(
                bom=bom, material=material,
                quantity=Decimal('5'), unit=material.unit or 'kg',
                scrap_percent=Decimal('3'),
            )
            self.stdout.write(f'  BOM kreiran: {bom}')
        else:
            self.stdout.write(f'  BOM već postoji: {bom}')

        self.stdout.write(self.style.SUCCESS('Seed završen.'))
```

---

## TASK 6G — ImprovementSuggestion check (prema memory protokolu)

Na početku sesije: provjeri `ImprovementSuggestion.objects.filter(status='new', source='user')`.
Ako postoji neka vezana uz production/work_orders/inventory — procesuiraj.

```bash
cd /var/www/fina-connect && venv/bin/python -c "
import django; django.setup()
# Zamijeni s pravim app name
try:
    from intelligence.models import ImprovementSuggestion
    qs = ImprovementSuggestion.objects.filter(status='new', source='user')
    for s in qs:
        print(s.pk, s.title[:60])
except: print('ImprovementSuggestion ne postoji ili drugi model name')
" 2>/dev/null
```

---

## PROVJERA USPJEHA

```bash
# 1. Konto import radi
venv/bin/python -c "
import django; django.setup()
from production.konto_integration import knjizi_trosak_proizvodnje
print('Konto integration OK')
" 2>/dev/null

# 2. Sidebar link postoji
grep -r "production:dashboard" templates/ | head -3

# 3. Pricing page ažuriran
grep -r "BOM\|Sastavnice\|Troškovnik" templates/ | grep -v production | head -5

# 4. Management command registriran
venv/bin/python manage.py help seed_production_demo 2>/dev/null && echo "OK" || echo "MISSING"
```

Kad završiš: `echo "TASK6_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt`
```

---

## KOORDINACIJA SA OSTALIM TASKOVIMA

- Task 6 NE dira: models.py, views.py, tests.py, templates/ (osim sidebar i pricing)
- Task 6 JEDINI dirá: konto_integration.py, pdf_views.py, dynamic_menu, pricing template, management commands
- Jedina ovisnost: Task 1 (models) i Task 2 (urls za reverse())
