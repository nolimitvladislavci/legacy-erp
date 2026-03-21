# CC Task — Transport: migracije + views + fleet dashboard

## OBAVEZNO PRVO
cat /var/www/fina-connect/FENIX_STATUS.md
git log --oneline -5

## Što je napravljeno (NE DIRAJ)
TransportOrder, VehicleDocument, DriverDocument, TachographEntry, FuelEntry
— sve u delivery/models.py linija 1225-1700. Modeli su kompletni.

## Što nedostaje

### 1. Provjeri migracije
```bash
cd /var/www/fina-connect
venv/bin/python manage.py showmigrations delivery | tail -5
venv/bin/python manage.py makemigrations delivery
venv/bin/python manage.py migrate delivery
venv/bin/python manage.py check
```

### 2. Views za TransportOrder
Pročitaj delivery/views.py pa dodaj na kraju:

```python
@login_required
def transport_order_list(request):
    company = get_user_company(request)
    qs = TransportOrder.objects.filter(company=company).select_related('vehicle','driver').order_by('-planned_departure')
    # filter po status i transport_type iz GET
    return render(request, 'delivery/transport_order_list.html', {'orders': qs})

@login_required  
def transport_order_create(request):
    # POST: kreira TransportOrder, poziva verify_documents(), vraća issues
    pass

@login_required
def transport_order_detail(request, pk):
    company = get_user_company(request)
    order = get_object_or_404(TransportOrder, pk=pk, company=company)
    issues = order.verify_documents()
    return render(request, 'delivery/transport_order_detail.html', {'order': order, 'issues': issues})

@login_required
def fleet_dashboard(request):
    company = get_user_company(request)
    from django.utils import timezone
    today = timezone.now().date()
    vehicles = Vehicle.objects.filter(company=company, is_active=True).prefetch_related('documents','transport_orders')
    # Grupiraj: vozila s isteklim dokumentima (ATP, reg, osiguranje)
    # Vozači s isteklim dokumentima
    # Aktivni TransportOrder-i
    return render(request, 'delivery/fleet_dashboard.html', {
        'vehicles': vehicles,
        'active_orders': TransportOrder.objects.filter(company=company, status__in=['in_transit','loading','border_crossing']),
        'expiring_docs': VehicleDocument.objects.filter(vehicle__company=company, valid_until__lte=today+timezone.timedelta(days=30)).order_by('valid_until'),
    })
```

### 3. URLs — dodaj u delivery/urls.py
```python
path('transport/', views.transport_order_list, name='transport_list'),
path('transport/new/', views.transport_order_create, name='transport_create'),
path('transport/<int:pk>/', views.transport_order_detail, name='transport_detail'),
path('fleet/', views.fleet_dashboard, name='fleet_dashboard'),
```

### 4. Templates — minimalni, funkcionalni

**delivery/transport_order_list.html** — tabela: broj naloga, tip, vozilo, vozač, ruta, status, planned_departure

**delivery/transport_order_detail.html** — sve detalje + issues lista (crveno ako verify_documents() vrati probleme)

**delivery/fleet_dashboard.html** — 3 sekcije:
- Vozila s isteklim/near-expiry dokumentima (ATP, reg, osiguranje) — crveno/žuto
- Aktivni transport nalozi (karta statusa)
- Vozači s isteklim dokumentima

### 5. Update FENIX_STATUS.md
Pomakni iz ČEKA u DONE kad završiš.

## Definicija DONE
- [ ] makemigrations + migrate bez greške
- [ ] django check: 0 grešaka
- [ ] transport_order_list view radi (200)
- [ ] fleet_dashboard view radi (200)
- [ ] Napiši /tmp/transport_done.txt
