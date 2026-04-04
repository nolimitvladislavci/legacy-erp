# CC_TASK_VATROGASCI_MODUL — DVD/JVP modul
# Agent: CC Code
# Prioritet: SREDNJI-VISOK — 1.800 potencijalnih klijenata
# Datum: 2026-03-25

---

## Što već radi (NE DIRAJ)
- POS udruga bypass fiskalizacije ✅
- TravelOrder (putni nalozi) ✅ — čekaju templates
- Volonterska evidencija (is_volunteer, volunteer_annual_limit) ✅
- NKD 84.25 ✅ — upravo dodano

## Što treba kreirati

### 1. Model: `FireIntervention` — u `worktime/models.py` ili novi app

```python
class FireIntervention(models.Model):
    """Dnevnik intervencija — zakonska obveza (Zakon o vatrogastvu čl. 37)"""
    
    INTERVENTION_TYPES = [
        ('fire', 'Požar'),
        ('rescue', 'Tehničko spašavanje'),
        ('flood', 'Poplava'),
        ('haz_mat', 'Opasne tvari'),
        ('accident', 'Prometna nesreća'),
        ('drill', 'Vježba'),
        ('other', 'Ostalo'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='fire_interventions')
    objects = CompanyManager()
    
    intervention_number = models.CharField(max_length=20)  # INT-2026-0001
    intervention_type = models.CharField(max_length=20, choices=INTERVENTION_TYPES)
    
    alarm_at = models.DateTimeField(verbose_name='Dojava')
    arrived_at = models.DateTimeField(null=True, blank=True, verbose_name='Dolazak')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Završetak')
    
    location = models.CharField(max_length=255, verbose_name='Mjesto intervencije')
    description = models.TextField(verbose_name='Opis intervencije')
    
    firefighters = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='fire_interventions',
        verbose_name='Angažirani vatrogasci'
    )
    vehicles_used = models.TextField(blank=True, verbose_name='Korištena vozila/oprema')
    
    damage_estimate = models.DecimalField(max_digits=12, decimal_places=2, 
                                          null=True, blank=True,
                                          verbose_name='Procijenjena šteta (EUR)')
    casualties = models.PositiveSmallIntegerField(default=0, verbose_name='Ozlijeđeni')
    fatalities = models.PositiveSmallIntegerField(default=0, verbose_name='Poginuli')
    
    reported_to_mup = models.BooleanField(default=False, verbose_name='Prijavljeno MUP-u')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name='created_interventions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-alarm_at']
        unique_together = [['company', 'intervention_number']]
        verbose_name = 'Intervencija'
        verbose_name_plural = 'Dnevnik intervencija'

    def duration_minutes(self):
        if self.arrived_at and self.finished_at:
            return int((self.finished_at - self.arrived_at).total_seconds() / 60)
        return None
```

### 2. InventoryItem extend — 3 polja (migracija)

```python
# Dodaj u inventory/models.py, klasa InventoryItem:
atest_expiry = models.DateField(null=True, blank=True,
    verbose_name='Rok valjanosti atesta',
    help_text='Aparati za gašenje, OZO, crijeva')
serial_number = models.CharField(max_length=100, blank=True,
    verbose_name='Serijski broj')
is_mup_property = models.BooleanField(default=False,
    verbose_name='Vlasništvo MUP-a',
    help_text='Oprema zaprimljena od MUP-a/Vatrogasne zajednice')
```

### 3. Celery task — Atest alarm

```python
# inventory/tasks.py — dodaj:
@shared_task
def check_atest_expiry():
    """Svaki dan u 08:00 — alarm za opremu čiji atest ističe za 30 dana."""
    from inventory.models import InventoryItem
    from django.utils import timezone
    from datetime import timedelta
    
    threshold = timezone.now().date() + timedelta(days=30)
    expiring = InventoryItem.objects.filter(
        atest_expiry__lte=threshold,
        atest_expiry__gte=timezone.now().date(),
        is_active=True
    ).select_related('company')
    
    for item in expiring:
        # Kreiraj ImprovementSuggestion kao alarm
        from pos.models import ImprovementSuggestion
        ImprovementSuggestion.objects.get_or_create(
            company=item.company,
            title=f'Atest ističe: {item.name}',
            defaults={
                'description': f'Artikl {item.name} (SN: {item.serial_number}) ima atest koji ističe {item.atest_expiry}.',
                'category': 'safety',
                'priority': 1,
                'source': 'system',
            }
        )
```

Dodaj u Celery beat: `'check-atest-expiry': {'task': '...check_atest_expiry', 'schedule': crontab(hour=8, minute=0)}`

### 4. Views + URLs + Templates

Novi app ili dodaj u `worktime`:

```
GET  /vatrogasci/intervencije/           — lista
GET  /vatrogasci/intervencije/nova/      — forma
POST /vatrogasci/intervencije/nova/      — spremi
GET  /vatrogasci/intervencije/<pk>/      — detalj + PDF
GET  /vatrogasci/oprema/                 — oprema s atest_expiry filterom
```

Template lista: tablica s tipom, mjestom, trajanjem, statusom MUP prijave.
Template forma: mobile-first, 5 klikova do završene intervencije.
PDF: A4 izvještaj o intervenciji s potpisom zapovjednika.

### 5. NKD — pricing paket

U `companies/module_registry.py` dodaj vatrogasci konfig:
```python
'vatrogasci': {
    'name': 'DVD/JVP modul',
    'nkd_codes': ['84.25', '94.99'],
    'includes': ['worktime', 'travel_orders', 'inventory', 'fire_interventions'],
    'price': 9.99,
}
```

---

## Definition of Done

- [ ] Migracija FireIntervention + InventoryItem extend
- [ ] CRUD views + 3 templates
- [ ] PDF izvještaj intervencije
- [ ] Atest expiry Celery task
- [ ] Admin registracija
- [ ] Test: DVD klijent kreira intervenciju, vidi u listi, exporta PDF
- [ ] Commit: `feat: vatrogasci modul — dnevnik intervencija + atest alarm`
