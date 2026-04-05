# CC_TASK_PROD_2_VIEWS.md
# PRODUCTION MODULE — TASK 2: Views + URLs + RouteRegistry
# Agent: CC Code #2
# ČEKA: CC_TASK_PROD_1_MODELS.md mora biti DONE (migracije prošle)

---

## CILJ
Kompletne Django views, URL routing, RouteRegistry. Bez template pisanja (to je Task 3).
Koristi `render()` s placeholder template imenom — templates piše Task 3 paralelno.

---

## TASK 2A — production/urls.py

```python
app_name = 'production'

urlpatterns = [
    # Dashboard
    path('', views.production_dashboard, name='dashboard'),

    # BOM — Sastavnice
    path('bom/',                   views.bom_list,   name='bom_list'),
    path('bom/nova/',              views.bom_create, name='bom_create'),
    path('bom/<int:pk>/',          views.bom_detail, name='bom_detail'),
    path('bom/<int:pk>/uredi/',    views.bom_edit,   name='bom_edit'),
    path('bom/<int:pk>/kloniraj/', views.bom_clone,  name='bom_clone'),

    # Radna mjesta
    path('radna-mjesta/',             views.work_center_list,   name='wc_list'),
    path('radna-mjesta/novo/',        views.work_center_create, name='wc_create'),
    path('radna-mjesta/<int:pk>/',    views.work_center_detail, name='wc_detail'),
    path('radna-mjesta/<int:pk>/uredi/', views.work_center_edit, name='wc_edit'),

    # Proizvodni nalozi
    path('nalozi/',                      views.order_list,     name='order_list'),
    path('nalozi/novi/',                 views.order_create,   name='order_create'),
    path('nalozi/<int:pk>/',             views.order_detail,   name='order_detail'),
    path('nalozi/<int:pk>/uredi/',       views.order_edit,     name='order_edit'),
    path('nalozi/<int:pk>/planiraj/',    views.order_plan,     name='order_plan'),
    path('nalozi/<int:pk>/pokreni/',     views.order_start,    name='order_start'),
    path('nalozi/<int:pk>/pauziraj/',    views.order_pause,    name='order_pause'),
    path('nalozi/<int:pk>/završi/',      views.order_complete, name='order_complete'),
    path('nalozi/<int:pk>/otkaži/',      views.order_cancel,   name='order_cancel'),
    path('nalozi/<int:pk>/qc/',          views.order_qc,       name='order_qc'),
    path('nalozi/<int:pk>/troskovi/',    views.order_costs,    name='order_costs'),
    path('nalozi/<int:pk>/print/',       views.order_print,    name='order_print'),

    # API endpoints (JSON)
    path('api/bom/<int:pk>/linije/',     views.api_bom_lines,        name='api_bom_lines'),
    path('api/nalog/<int:pk>/status/',   views.api_order_status,     name='api_order_status'),
    path('api/nalog/<int:pk>/trosak/',   views.api_add_cost,         name='api_add_cost'),
    path('api/planiranje/',              views.api_mrp_plan,         name='api_mrp_plan'),

    # Izvještaji
    path('izvjestaji/troskovnik/',        views.report_cost_analysis, name='report_costs'),
    path('izvjestaji/serije/',            views.report_batches,       name='report_batches'),
    path('izvjestaji/ucinkovitost/',      views.report_efficiency,    name='report_efficiency'),
]
```

---

## TASK 2B — Uključi u core/urls.py

Naći blok unutar `i18n_patterns()` i dodati:

```python
path('production/', include('production.urls')),
```

Provjeri postoji li `production` u INSTALLED_APPS (Task 1 je to dodao).

---

## TASK 2C — production/views.py (sve views)

### Dashboard
```python
@login_required
def production_dashboard(request):
    """
    KPI kartice: aktivni nalozi, nalozi u tijeku, gotovo danas, ukupni trošak ovaj mj.
    Zadnjih 5 naloga + 5 BOM-ova.
    """
    company = get_user_company(request)
    context = {
        'active_orders': ProductionOrder.objects.filter(
            company=company, status__in=['planned','in_progress','paused']
        ).select_related('product','bom','work_center').count(),
        'completed_this_month': ...,
        'total_cost_this_month': ...,
        'recent_orders': ProductionOrder.objects.filter(company=company)
            .select_related('product','bom')[:5],
        'recent_boms': BillOfMaterials.objects.filter(company=company, is_active=True)[:5],
    }
    return render(request, 'production/dashboard.html', context)
```

### BOM Views
```python
@login_required
def bom_list(request):
    # Filtriranje: ?product=, ?active=1
    # Annotate s brojem naloga koji koriste taj BOM
    # Pagination: 20 per page

@login_required
def bom_create(request):
    # POST: validacija → kreiranje BillOfMaterials + BOMLine formset
    # Koristiti inlineformset_factory za BOMLine
    # Na uspjehu: redirect bom_detail

@login_required
def bom_detail(request, pk):
    # Prikaži BOM s linijama
    # Ukupna cijena materijala po seriji (sum BOMLine × unit_cost iz inventory)
    # Lista naloga koji koriste ovaj BOM

@login_required
def bom_edit(request, pk):
    # Isto kao create, ali s instancom

@login_required
def bom_clone(request, pk):
    # Kloniraj BOM s novom verzijom (v2, v3, ...)
    # Kopiraj sve BOMLine-ove
    # Redirect na edit nove verzije
```

### WorkCenter Views
```python
@login_required
def work_center_list(request): ...
@login_required
def work_center_create(request): ...
@login_required
def work_center_detail(request, pk): ...
@login_required
def work_center_edit(request, pk): ...
```

### ProductionOrder Views — ključne

```python
@login_required
def order_create(request):
    """
    Odabir BOM-a → auto-popuni ProductionOrderLine iz BOM linija.
    planned_quantity × BOMLine.quantity_with_scrap = planned_quantity po liniji.
    """
    if request.method == 'POST':
        bom = get_object_or_404(BillOfMaterials, pk=request.POST['bom'], company=company)
        order = ProductionOrder(company=company, bom=bom, product=bom.product, ...)
        order.order_number = order.generate_order_number()
        order.save()
        # Auto-kreiraj ProductionOrderLine za svaku BOMLine
        for bom_line in bom.lines.all():
            planned_qty = bom_line.quantity_with_scrap * order.planned_quantity / bom.yield_quantity
            ProductionOrderLine.objects.create(
                order=order,
                material=bom_line.material,
                bom_line=bom_line,
                planned_quantity=planned_qty,
                unit=bom_line.unit,
                unit_cost=bom_line.material.purchase_price or 0,
            )
        return redirect('production:order_detail', pk=order.pk)

@login_required
def order_complete(request, pk):
    """
    FSM transition: in_progress → completed.
    Pokreće signal za inventory deduction (Task 4 piše signal).
    Kalkulira troškove.
    """
    order = get_object_or_404(ProductionOrder, pk=pk, company=company)
    if request.method == 'POST':
        actual_qty = Decimal(request.POST.get('actual_quantity', order.planned_quantity))
        order.actual_quantity = actual_qty
        order.actual_end = timezone.now()
        order.save(update_fields=['actual_quantity','actual_end'])
        order.transition_to('completed', user=request.user, save=True)
        # Signal production_order_completed se okida iz signals.py (Task 4)
        messages.success(request, f'Nalog {order.order_number} završen. Inventar razdužen.')
        return redirect('production:order_detail', pk=pk)
    return render(request, 'production/order_complete_confirm.html', {'order': order})

@login_required
def order_qc(request, pk):
    """QC forma — POST kreira ProductionQualityCheck."""

@login_required
def order_costs(request, pk):
    """Dodaj ručni trošak (rad, režija, ostalo)."""
```

### API Views (JSON)
```python
@login_required
def api_bom_lines(request, pk):
    """
    GET: Vraća JSON linije BOM-a — za AJAX u order_create formi.
    [{"material_id": 1, "material_name": "Jabuka", "quantity": 5.0, "unit": "kg", "unit_cost": 1.20}, ...]
    """

@login_required
def api_mrp_plan(request):
    """
    POST: {"orders": [{"product_id": 1, "quantity": 100}, ...]}
    Vraća: {"material_requirements": [...], "shortages": [...]}
    Brzi MRP izračun — ne kreira naloge, samo simulira potrebe.
    """
```

### Izvještaji
```python
@login_required
def report_cost_analysis(request):
    """
    Troškovnik: po nalozima za period (default: ovaj mj).
    Agregiraj: materijal, rad, režija, ukupno, po komadu.
    Eksport CSV.
    """

@login_required
def report_efficiency(request):
    """
    Ucinkovitost: planned_quantity vs actual_quantity, planirano vs stvarno vrijeme.
    """
```

---

## TASK 2D — RouteRegistry (permissions/route_registry.py)

Dodati u ROUTE_REGISTRY dict:
```python
# Production MRP
'production:dashboard':      AccessLevel.COMPANY,
'production:bom_list':       AccessLevel.COMPANY,
'production:bom_create':     AccessLevel.COMPANY,
'production:bom_detail':     AccessLevel.COMPANY,
'production:bom_edit':       AccessLevel.COMPANY,
'production:bom_clone':      AccessLevel.COMPANY,
'production:wc_list':        AccessLevel.COMPANY,
'production:wc_create':      AccessLevel.COMPANY,
'production:wc_detail':      AccessLevel.COMPANY,
'production:wc_edit':        AccessLevel.COMPANY,
'production:order_list':     AccessLevel.COMPANY,
'production:order_create':   AccessLevel.COMPANY,
'production:order_detail':   AccessLevel.COMPANY,
'production:order_edit':     AccessLevel.COMPANY,
'production:order_plan':     AccessLevel.COMPANY,
'production:order_start':    AccessLevel.COMPANY,
'production:order_pause':    AccessLevel.COMPANY,
'production:order_complete': AccessLevel.COMPANY,
'production:order_cancel':   AccessLevel.COMPANY,
'production:order_qc':       AccessLevel.COMPANY,
'production:order_costs':    AccessLevel.COMPANY,
'production:order_print':    AccessLevel.COMPANY,
'production:api_bom_lines':  AccessLevel.COMPANY,
'production:api_order_status': AccessLevel.COMPANY,
'production:api_add_cost':   AccessLevel.COMPANY,
'production:api_mrp_plan':   AccessLevel.COMPANY,
'production:report_costs':   AccessLevel.COMPANY,
'production:report_batches': AccessLevel.COMPANY,
'production:report_efficiency': AccessLevel.COMPANY,
```

---

## TASK 2E — Sidebar menu (dynamic_menu ili base.html)

Naći gdje se buildaju sidebar linkovi (grep 'work_orders' u templates/base.html ili dynamic_menu).
Dodati production link u isti pattern:
```html
<a href="{% url 'production:dashboard' %}">
  <i class="fas fa-industry"></i> Proizvodnja
</a>
```

---

## PROVJERA USPJEHA

```bash
venv/bin/python manage.py check  # 0 errors
# Test URL resolve
venv/bin/python -c "
import django; django.setup()
from django.urls import reverse
print(reverse('production:dashboard'))
print(reverse('production:order_create'))
print(reverse('production:bom_list'))
print('URLs OK')
"
```

Kad završiš: `echo "TASK2_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt`
