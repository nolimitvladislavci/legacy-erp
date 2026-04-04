# CC_TASK: LOVAČKI MODUL — Evidencija divljači + HLS
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P1
# Novi modul. 75.000 lovaca u HR. 1.200+ lovačkih udruga.
# Zakon o lovstvu (NN 99/2018): svaki odstrjel se mora evidentirati.

PRAVILO: READ models.py PRVO. NE diras base.html, .env, settings.py direktno.

---

## KONTEKST

Lovačka udruga = umbrella (već imamo model)
  - udruge/models.py: Clan, Clanarina, Dogadjaj — koristiti direktno
  - Lovac = Clan s tipom 'lovac'
  - Divljač = Livestock model s novim vrstama (dodati)
  - Odstrjel = novi model (HuntRecord)
  - Kvota = godišnji plan odstrjela (HuntingQuota)
  - BARF veza: srna, vepar, zec, divlja patka → RawFoodListing

---

## KORAK 1 — PROVJERI TEREN

```bash
grep -n "^class " udruge/models.py | head -15
grep -n "^class " livestock/models.py | head -10
grep -n "VRSTA_CHOICES" livestock/models.py | head -5
grep -rn "hunting\|lovac\|odstrjel" --include="*.py" | grep -v venv | head -10
ls hunting/ 2>/dev/null || echo "ne postoji — kreiraj"
```

---

## KORAK 2 — LIVESTOCK vrste za divljač

READ: livestock/models.py (VRSTA_CHOICES blok)

DODAJ u VRSTA_CHOICES (bez brisanja):
```python
# Divljač — lovački modul
('srna',        'Srna'),
('jelen',       'Jelen'),
('divlja_svinja','Divlja svinja / Vepar'),
('zec',         'Zec'),
('fazán',       'Fazan'),
('divlja_patka','Divlja patka'),
('lisica',      'Lisica'),
('vuk',         'Vuk'),
('medvjed',     'Medvjed'),
('divokoza',    'Divokoza'),
```

Migracija ako potrebno (choices update — obično nije):
```bash
venv/bin/python manage.py makemigrations livestock --name="add_divljac" 2>&1 | head -5
```

---

## KORAK 3 — HuntRecord model

Kreiraj novi Django app ili dodaj modele u `udruge/` (provjeri što je lakše).
Ako udruge/ ima previše toga — kreiraj: mkdir hunting && touch hunting/__init__.py hunting/apps.py hunting/models.py hunting/views.py hunting/urls.py hunting/admin.py

READ: udruge/models.py (Clan model — koristit ćemo ga za lovca)

U `udruge/models.py` DODAJ (ili hunting/models.py):

```python
class HuntRecord(models.Model):
    """Evidencija odstrjela — zakonska obveza (Zakon o lovstvu NN 99/2018)."""

    DIVLJAC_CHOICES = [
        ('srna',         'Srna'),
        ('jelen',        'Jelen'),
        ('divlja_svinja','Divlja svinja / Vepar'),
        ('zec',          'Zec'),
        ('fazan',        'Fazan'),
        ('divlja_patka', 'Divlja patka'),
        ('lisica',       'Lisica'),
        ('vuk',          'Vuk (posebna dozvola)'),
        ('medvjed',      'Medvjed (posebna dozvola)'),
        ('divokoza',     'Divokoza'),
        ('ostalo',       'Ostalo'),
    ]
    SPOL_CHOICES = [('M','Mužjak'),('F','Ženka'),('N','Nepoznato')]
    NACIN_CHOICES = [
        ('vatrozid',  'Vatrozid / Čeka'),
        ('gon',       'Gon'),
        ('pregon',    'Pregon'),
        ('individualni','Individualni lov'),
    ]

    # Tko, kada, gdje
    company   = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                    related_name='hunt_records', verbose_name='Lovačka udruga')
    lovac     = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True,
                    related_name='hunt_records', verbose_name='Lovac')

    datum     = models.DateField(verbose_name='Datum odstrjela')
    lokacija  = models.CharField(max_length=200, verbose_name='Lovište / Lokacija')
    latitude  = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Divljač
    vrsta     = models.CharField(max_length=20, choices=DIVLJAC_CHOICES)
    spol      = models.CharField(max_length=1, choices=SPOL_CHOICES, default='N')
    starost_god = models.PositiveSmallIntegerField(null=True, blank=True,
                    verbose_name='Procijenjena starost (god)')
    tezina_kg = models.DecimalField(max_digits=6, decimal_places=1,
                    null=True, blank=True, verbose_name='Težina (kg)')
    nacin     = models.CharField(max_length=20, choices=NACIN_CHOICES, default='individualni')

    # Dokumentacija
    dozvola_broj = models.CharField(max_length=50, blank=True,
                    verbose_name='Broj dozvole odstrjela')
    napomena     = models.TextField(blank=True)

    # BARF veza — može li meso ići u marketplace?
    barf_available = models.BooleanField(default=False,
                    verbose_name='Meso dostupno za BARF marketplace')
    barf_listing   = models.ForeignKey('memio_pet.RawFoodListing',
                    null=True, blank=True, on_delete=models.SET_NULL,
                    related_name='hunt_source', verbose_name='BARF oglas')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-datum']
        verbose_name = 'Evidencija odstrjela'
        verbose_name_plural = 'Evidencija odstrjela'

    def __str__(self):
        return f'{self.get_vrsta_display()} — {self.datum} ({self.lovac})'


class HuntingQuota(models.Model):
    """Godišnji plan odstrjela vs realizacija."""
    company    = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                    related_name='hunt_quotas')
    godina     = models.PositiveSmallIntegerField(verbose_name='Godina')
    vrsta      = models.CharField(max_length=20, choices=HuntRecord.DIVLJAC_CHOICES)
    plan_kom   = models.PositiveIntegerField(default=0, verbose_name='Plan (kom)')

    @property
    def realizirano(self):
        return HuntRecord.objects.filter(
            company=self.company,
            datum__year=self.godina,
            vrsta=self.vrsta
        ).count()

    @property
    def postotak(self):
        if self.plan_kom == 0:
            return 0
        return min(100, int(self.realizirano / self.plan_kom * 100))

    class Meta:
        unique_together = ('company', 'godina', 'vrsta')
        verbose_name = 'Kvota odstrjela'
```

---

## KORAK 4 — VIEWS

```python
# udruge/views.py ili hunting/views.py — dodaj:

@login_required
def hunt_record_list(request):
    """Lista odstrjela za lovačku udrugu."""
    from udruge.models import HuntRecord
    from core.company_utils import get_user_company
    company = get_user_company(request)
    records = HuntRecord.objects.filter(company=company).select_related('lovac')
    quota   = {}  # TODO: HuntingQuota agregacija
    return render(request, 'udruge/hunt_records.html', {
        'records': records[:100],
        'page_title': 'Evidencija odstrjela',
    })

@login_required
def hunt_record_create(request):
    """Unos novog odstrjela."""
    from udruge.models import HuntRecord
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if request.method == 'POST':
        rec = HuntRecord(
            company  = company,
            lovac    = request.user,
            datum    = request.POST.get('datum'),
            lokacija = request.POST.get('lokacija',''),
            vrsta    = request.POST.get('vrsta','ostalo'),
            spol     = request.POST.get('spol','N'),
            tezina_kg= request.POST.get('tezina_kg') or None,
            nacin    = request.POST.get('nacin','individualni'),
            dozvola_broj = request.POST.get('dozvola_broj',''),
            napomena = request.POST.get('napomena',''),
            barf_available = 'barf_available' in request.POST,
        )
        rec.save()
        # Auto-kreiraj BARF listing ako je označeno
        if rec.barf_available and rec.tezina_kg:
            from memio_pet.models import RawFoodListing
            barf_map = {
                'srna':'divljac','jelen':'divljac',
                'divlja_svinja':'divljac','zec':'divljac',
                'divlja_patka':'divljac',
            }
            product = barf_map.get(rec.vrsta, 'ostalo')
            listing = RawFoodListing.objects.create(
                company=company,
                product_type=product,
                quantity_kg=float(rec.tezina_kg or 0),
                price_eur_kg=3.50,
                description=f'Divljač — {rec.get_vrsta_display()}, {rec.datum}. Odstrjel: {rec.lokacija}.',
                is_antibiotic_free=True,
                is_free_range=True,
            )
            rec.barf_listing = listing
            rec.save(update_fields=['barf_listing'])
        messages.success(request, f'Odstrjel evidentiran: {rec}')
        return redirect('udruge:hunt_record_list')
    return render(request, 'udruge/hunt_record_create.html', {
        'divljac_choices': HuntRecord.DIVLJAC_CHOICES,
        'nacin_choices': HuntRecord.NACIN_CHOICES,
        'page_title': 'Novi odstrjel',
    })
```

---

## KORAK 5 — TEMPLATES (10/10)

KREIRAJ: templates/udruge/hunt_records.html
```html
{% extends "base.html" %}
{% block title %}Evidencija odstrjela{% endblock %}
{% block content %}
<div style="max-width:1000px;margin:0 auto;padding:1.5rem 1rem;">

  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;margin-bottom:2rem;">
    <div>
      <h1 style="font-size:1.5rem;font-weight:800;">🦌 Evidencija odstrjela</h1>
      <p style="color:var(--text-secondary);font-size:.85rem;">Zakon o lovstvu NN 99/2018 — digitalna evidencija</p>
    </div>
    <a href="{% url 'udruge:hunt_record_create' %}" class="btn-gold">+ Novi odstrjel</a>
  </div>

  <!-- Statistike -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin-bottom:2rem;">
    {% regroup records by vrsta as by_vrsta %}
    <div class="kpi-card">
      <strong style="font-size:1.75rem;color:var(--gold);">{{ records|length }}</strong>
      <span style="color:var(--text-secondary);font-size:.8rem;">Ukupno ove sezone</span>
    </div>
  </div>

  <!-- Tablica -->
  <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:.88rem;">
      <thead>
        <tr style="border-bottom:1px solid var(--border);">
          <th style="text-align:left;padding:.75rem 1rem;color:var(--text-secondary);font-size:.75rem;text-transform:uppercase;">Datum</th>
          <th style="text-align:left;padding:.75rem 1rem;color:var(--text-secondary);font-size:.75rem;text-transform:uppercase;">Vrsta</th>
          <th style="text-align:left;padding:.75rem 1rem;color:var(--text-secondary);font-size:.75rem;text-transform:uppercase;">Lokacija</th>
          <th style="text-align:left;padding:.75rem 1rem;color:var(--text-secondary);font-size:.75rem;text-transform:uppercase;">Lovac</th>
          <th style="text-align:left;padding:.75rem 1rem;color:var(--text-secondary);font-size:.75rem;text-transform:uppercase;">Težina</th>
          <th style="text-align:left;padding:.75rem 1rem;color:var(--text-secondary);font-size:.75rem;text-transform:uppercase;">BARF</th>
        </tr>
      </thead>
      <tbody>
        {% for r in records %}
        <tr style="border-bottom:1px solid rgba(255,255,255,.04);">
          <td style="padding:.75rem 1rem;">{{ r.datum|date:"d.m.Y." }}</td>
          <td style="padding:.75rem 1rem;font-weight:600;">
            {% if r.vrsta == 'srna' %}🦌{% elif r.vrsta == 'divlja_svinja' %}🐗{% elif r.vrsta == 'zec' %}🐇{% elif r.vrsta == 'fazan' %}🐦{% else %}🎯{% endif %}
            {{ r.get_vrsta_display }}
          </td>
          <td style="padding:.75rem 1rem;color:var(--text-secondary);">{{ r.lokacija|truncatechars:30 }}</td>
          <td style="padding:.75rem 1rem;">{{ r.lovac.get_full_name|default:r.lovac.username }}</td>
          <td style="padding:.75rem 1rem;">{% if r.tezina_kg %}{{ r.tezina_kg }} kg{% else %}—{% endif %}</td>
          <td style="padding:.75rem 1rem;">
            {% if r.barf_listing %}
              <span style="color:#10b981;font-size:.8rem;">✓ na burzi</span>
            {% elif r.barf_available %}
              <span style="color:var(--gold);font-size:.8rem;">🥩 dostupno</span>
            {% endif %}
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="6" style="padding:2rem;text-align:center;color:var(--text-secondary);">
          Nema evidencije. <a href="{% url 'udruge:hunt_record_create' %}" style="color:var(--gold);">Dodajte prvi odstrjel →</a>
        </td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

KREIRAJ: templates/udruge/hunt_record_create.html — forma za unos (analog barf_create, 10/10 dizajn)

---

## KORAK 6 — URLS + ADMIN + MIGRACIJA

READ: udruge/urls.py — dodaj:
```python
path('odstrjel/', views.hunt_record_list, name='hunt_record_list'),
path('odstrjel/novi/', views.hunt_record_create, name='hunt_record_create'),
```

READ: udruge/admin.py — dodaj HuntRecord i HuntingQuota u admin.

Migracija:
```bash
venv/bin/python manage.py makemigrations udruge --name="add_hunt_records"
venv/bin/python manage.py migrate 2>&1 | tail -5
venv/bin/python manage.py check 2>&1 | tail -3
git add -A && git commit -m "feat(lovci): HuntRecord, HuntingQuota, BARF auto-listing, divljač evidencija"
```

DONE: [ ] HuntRecord model [ ] HuntingQuota model [ ] Views [ ] Templates 10/10 [ ] BARF auto-listing [ ] Admin [ ] Migracija
