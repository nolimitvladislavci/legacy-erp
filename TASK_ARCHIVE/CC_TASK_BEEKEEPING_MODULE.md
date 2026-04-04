# CC_TASK_BEEKEEPING_MODULE — Pčelarski modul (Apiary)
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-25

**Čitaj prvo:** FENIX_STATUS.md, livestock/models.py, livestock/urls.py, livestock/views.py

---

## Kontekst

~11.000 registriranih pčelara u RH. Gotovo svi registrirani kao OPG.
Zakonske obveze: EPP evidencija (Prilog 2 upis + Prilog 3 godišnja dojava),
APPRRR subvencije (zahtjev vezan na R1 račune), fiskalizacija.

LIMIT Connect već pokriva OPG, R1 račune, fiskalizaciju, arhivu.
Nedostaje: evidencija košnica i pčelinjaka, EPP Prilog 3 PDF, sezonski podsjetnici.

Implementirati KAO PROŠIRENJE livestock app-a — ne novi Django app.

---

## ZADATAK 1 — Novi modeli u livestock/models.py

Dodaj NA KRAJ fajla (iza klase `InstitutionalAccessLog`):

```python
# ═══════════════════════════════════════════════════════════════
#  PČELARSKI MODUL — Apiary (Apis mellifera)
#  Zakonska osnova: Pravilnik o držanju pčela (NN), EU 2021/126
# ═══════════════════════════════════════════════════════════════

class Apiary(models.Model):
    """
    Pčelinjak — lokacija s košnicama.
    Jedan pčelar može imati više pčelinjaka (seléće pčelarstvo).
    """
    TIP_CHOICES = [
        ('stacionarni', 'Stacionarni'),
        ('selece',      'Seléće pčelarstvo'),
    ]
    NACIN_CHOICES = [
        ('konvencionalni', 'Konvencionalni'),
        ('ekoloski',       'Ekološki'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='apiaries', verbose_name='OPG / Firma'
    )
    # Identifikacija
    naziv       = models.CharField(max_length=100, verbose_name='Naziv pčelinjaka')
    epp_broj    = models.CharField(max_length=30, blank=True,
                                    verbose_name='EPP broj (iz evidencije pčelara)')
    mibpg       = models.CharField(max_length=20, blank=True,
                                    verbose_name='MIBPG (matični identifikator)')

    # Lokacija
    adresa      = models.CharField(max_length=200, blank=True, verbose_name='Adresa pčelinjaka')
    katastarska_opcina = models.CharField(max_length=100, blank=True, verbose_name='Katastarska općina')
    gps_lat     = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lon     = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Tip i način pčelarenja
    tip         = models.CharField(max_length=20, choices=TIP_CHOICES, default='stacionarni')
    nacin       = models.CharField(max_length=20, choices=NACIN_CHOICES, default='konvencionalni')

    # Ekološki certifikat
    eko_certifikat_broj  = models.CharField(max_length=100, blank=True)
    eko_certifikat_vazi_do = models.DateField(null=True, blank=True)

    # Status
    aktivan     = models.BooleanField(default=True, verbose_name='Aktivan')
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'livestock_apiary'
        ordering  = ['naziv']
        verbose_name = 'Pčelinjak'
        verbose_name_plural = 'Pčelinjaci'

    def __str__(self):
        return f'{self.naziv} ({self.broj_kosnica} košnica)'

    @property
    def broj_kosnica(self):
        return self.hives.filter(status='aktivna').count()

    @property
    def epp_rok_alert(self):
        """True ako je EPP rok unutar 30 dana (rujan–prosinac)."""
        from django.utils import timezone
        today = timezone.now().date()
        return today.month in [9, 10, 11, 12]


class Hive(models.Model):
    """
    Košnica — osnovna jedinica evidencije.
    Nije životinja — pčelinja zajednica se broji po košnici.
    """
    TIP_CHOICES = [
        ('langstroth', 'Langstroth (LR)'),
        ('db',         'Dadant-Blatt (DB)'),
        ('zdr',        'Zdravetz (ZDR)'),
        ('dn',         'Deutsch-Normal (DN)'),
        ('trpanj',     'Trpanjski sanduk'),
        ('ostalo',     'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('aktivna',   'Aktivna'),
        ('prazna',    'Prazna (bez zajednice)'),
        ('prezimila', 'Prezimljava'),
        ('prodana',   'Prodana'),
        ('uginula',   'Zajednica uginula'),
    ]

    apiary      = models.ForeignKey(Apiary, on_delete=models.CASCADE,
                                     related_name='hives', verbose_name='Pčelinjak')
    oznaka      = models.CharField(max_length=20, verbose_name='Oznaka košnice',
                                    help_text='npr. K-001, A-12')
    tip         = models.CharField(max_length=20, choices=TIP_CHOICES, default='langstroth')
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktivna')
    godina_nabave = models.PositiveSmallIntegerField(null=True, blank=True,
                                                      verbose_name='Godina nabave')
    je_matica_markirana = models.BooleanField(default=False, verbose_name='Matica markirana')
    boja_marke  = models.CharField(max_length=20, blank=True,
                                    verbose_name='Boja marke matice',
                                    help_text='bijela/žuta/crvena/zelena/plava (5-god. ciklus)')
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table   = 'livestock_hive'
        ordering   = ['apiary', 'oznaka']
        unique_together = [('apiary', 'oznaka')]
        verbose_name = 'Košnica'
        verbose_name_plural = 'Košnice'

    def __str__(self):
        return f'{self.apiary.naziv} / {self.oznaka}'

    @property
    def zadnji_pregled(self):
        return self.inspections.order_by('-datum').first()


class HiveInspection(models.Model):
    """
    Pregled košnice — zapisnik o stanju zajednice.
    Osnova za EPP godišnju dojavu i praćenje varoe.
    """
    OCJENA_CHOICES = [(i, str(i)) for i in range(1, 6)]

    hive        = models.ForeignKey(Hive, on_delete=models.CASCADE,
                                     related_name='inspections', verbose_name='Košnica')
    datum       = models.DateField(verbose_name='Datum pregleda')
    broj_okvira_legla   = models.PositiveSmallIntegerField(default=0, verbose_name='Okviri legla')
    broj_okvira_meda    = models.PositiveSmallIntegerField(default=0, verbose_name='Okviri meda')
    ima_maticu  = models.BooleanField(default=True, verbose_name='Ima maticu')
    snaga_zajednice = models.PositiveSmallIntegerField(
        choices=OCJENA_CHOICES, default=3,
        verbose_name='Snaga zajednice (1–5)',
        help_text='1=slaba, 5=izvrsna'
    )
    varroa_posip = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        verbose_name='Varroa posip (% invazije)',
        help_text='% varroa/pčela pri uzorkovanju'
    )
    tretman_varroa = models.CharField(max_length=100, blank=True,
                                       verbose_name='Tretman varroa (preparat)')
    napomena    = models.TextField(blank=True)
    inspector   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Pregledao'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'livestock_hive_inspection'
        ordering  = ['-datum']
        verbose_name = 'Pregled košnice'
        verbose_name_plural = 'Pregledi košnica'

    def __str__(self):
        return f'{self.hive} — {self.datum}'


class HoneyHarvest(models.Model):
    """
    Berba meda — po pčelinjaku, po vrsti.
    Osnova za APPRRR evidenciju prihoda i R1 račune.
    """
    VRSTA_MEDA = [
        ('cvjetni',    'Cvjetni med'),
        ('bagremov',   'Bagremov med'),
        ('lipov',      'Lipov med'),
        ('kestenov',   'Kestenov med'),
        ('medljikovac','Medljikovac'),
        ('poliflorni', 'Poliflorni med'),
        ('ostalo',     'Ostalo'),
    ]

    apiary      = models.ForeignKey(Apiary, on_delete=models.CASCADE,
                                     related_name='harvests', verbose_name='Pčelinjak')
    datum       = models.DateField(verbose_name='Datum berbe')
    vrsta       = models.CharField(max_length=20, choices=VRSTA_MEDA, default='cvjetni')
    kolicina_kg = models.DecimalField(max_digits=8, decimal_places=2,
                                       verbose_name='Količina (kg)')
    cijena_kg   = models.DecimalField(max_digits=6, decimal_places=2,
                                       null=True, blank=True, verbose_name='Cijena/kg (EUR)')
    staklenka_serija = models.CharField(max_length=50, blank=True,
                                         verbose_name='Serija staklenki',
                                         help_text='Za nationalnu staklenku meda')
    invoice     = models.ForeignKey(
        'invoicing.Invoice', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='honey_harvests',
        verbose_name='Vezani R1 račun'
    )
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'livestock_honey_harvest'
        ordering  = ['-datum']
        verbose_name = 'Berba meda'
        verbose_name_plural = 'Berbe meda'

    def __str__(self):
        return f'{self.apiary.naziv} — {self.get_vrsta_display()} {self.kolicina_kg}kg ({self.datum})'

    @property
    def ukupna_vrijednost(self):
        if self.cijena_kg:
            return self.kolicina_kg * self.cijena_kg
        return None


class EPPDojava(models.Model):
    """
    EPP Prilog 3 — Godišnja dojava broja pčelinjih zajednica.
    Rok: rujan–prosinac svake godine.
    Zakonska osnova: Pravilnik o držanju pčela i katastru pčelinje paše.
    """
    company     = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='epp_dojave', verbose_name='OPG'
    )
    godina      = models.PositiveSmallIntegerField(verbose_name='Godina dojave')
    datum_dojave = models.DateField(verbose_name='Datum predaje dojave')
    ukupno_zajednica = models.PositiveIntegerField(verbose_name='Ukupno pčelinjih zajednica')
    ukupno_kosnica   = models.PositiveIntegerField(verbose_name='Ukupno košnica')
    povjerenik_ime   = models.CharField(max_length=100, blank=True,
                                         verbose_name='Povjerenik (ime i prezime)')
    povjerenik_opcina = models.CharField(max_length=100, blank=True,
                                          verbose_name='Područje povjerenika')
    pdf_file    = models.FileField(upload_to='epp_dojave/', blank=True,
                                    verbose_name='Generirani Prilog 3 PDF')
    predano     = models.BooleanField(default=False, verbose_name='Predano povjereniku')
    predano_datum = models.DateField(null=True, blank=True)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'livestock_epp_dojava'
        unique_together = [('company', 'godina')]
        ordering        = ['-godina']
        verbose_name = 'EPP dojava'
        verbose_name_plural = 'EPP dojave'

    def __str__(self):
        return f'EPP dojava {self.godina} — {self.company.name} ({self.ukupno_zajednica} zajednica)'
```

---

## ZADATAK 2 — Migracija

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations livestock --name="add_apiary_hive_honey_epp"
venv/bin/python manage.py migrate livestock
```

Verifikacija tablica:
```bash
venv/bin/python manage.py shell -c "
from livestock.models import Apiary, Hive, HiveInspection, HoneyHarvest, EPPDojava
print('OK:', Apiary._meta.db_table, Hive._meta.db_table,
      HiveInspection._meta.db_table, HoneyHarvest._meta.db_table, EPPDojava._meta.db_table)
"
```

---

## ZADATAK 3 — Views (livestock/views.py)

Dodaj na kraj fajla, **iza svih postojećih views**:

```python
# ══ APIARY VIEWS ══════════════════════════════════════════════

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

@login_required
def apiary_dashboard(request):
    """
    Pčelarski cockpit — pregled svih pčelinjaka, košnica, upozorenja.
    """
    company = request.user.profile.company
    apiaries = Apiary.objects.filter(company=company, aktivan=True).prefetch_related('hives')

    total_hives = sum(a.broj_kosnica for a in apiaries)
    epp_alert   = any(a.epp_rok_alert for a in apiaries)

    # Zadnje berbe
    from livestock.models import HoneyHarvest
    zadnje_berbe = HoneyHarvest.objects.filter(
        apiary__company=company
    ).select_related('apiary').order_by('-datum')[:5]

    # EPP status za tekuću godinu
    from django.utils import timezone
    from livestock.models import EPPDojava
    epp_ove_godine = EPPDojava.objects.filter(
        company=company, godina=timezone.now().year
    ).first()

    return render(request, 'livestock/apiary_dashboard.html', {
        'apiaries':       apiaries,
        'total_hives':    total_hives,
        'epp_alert':      epp_alert,
        'zadnje_berbe':   zadnje_berbe,
        'epp_ove_godine': epp_ove_godine,
        'company':        company,
    })


@login_required
def apiary_detail(request, pk):
    """Jedan pčelinjak — sve košnice, pregledi, berbe."""
    company = request.user.profile.company
    apiary = get_object_or_404(Apiary, pk=pk, company=company)
    hives  = apiary.hives.all().order_by('oznaka')

    from livestock.models import HiveInspection, HoneyHarvest
    zadnji_pregledi = HiveInspection.objects.filter(
        hive__apiary=apiary
    ).select_related('hive').order_by('-datum')[:10]

    berbe = HoneyHarvest.objects.filter(apiary=apiary).order_by('-datum')

    return render(request, 'livestock/apiary_detail.html', {
        'apiary':          apiary,
        'hives':           hives,
        'zadnji_pregledi': zadnji_pregledi,
        'berbe':           berbe,
    })


@login_required
def epp_dojava_generate(request, apiary_pk=None):
    """
    Generiraj EPP Prilog 3 PDF za tekuću godinu.
    Broji aktivne košnice + zadnje HiveInspection po zajednici.
    """
    from django.utils import timezone
    from livestock.models import EPPDojava
    import io

    company = request.user.profile.company
    godina  = timezone.now().year

    # Skupi podatke
    if apiary_pk:
        apiaries = Apiary.objects.filter(pk=apiary_pk, company=company)
    else:
        apiaries = Apiary.objects.filter(company=company, aktivan=True)

    ukupno_kosnica   = sum(a.broj_kosnica for a in apiaries)
    ukupno_zajednica = ukupno_kosnica  # 1 košnica = 1 zajednica (standardna aproksimacija)

    # Kreiraj ili ažuriraj EPP zapis
    epp, _ = EPPDojava.objects.get_or_create(
        company=company,
        godina=godina,
        defaults={
            'datum_dojave':       timezone.now().date(),
            'ukupno_zajednica':   ukupno_zajednica,
            'ukupno_kosnica':     ukupno_kosnica,
        }
    )
    epp.ukupno_zajednica = ukupno_zajednica
    epp.ukupno_kosnica   = ukupno_kosnica
    epp.datum_dojave     = timezone.now().date()
    epp.save(update_fields=['ukupno_zajednica', 'ukupno_kosnica', 'datum_dojave'])

    # Generiraj PDF (WeasyPrint)
    from django.template.loader import render_to_string
    from weasyprint import HTML

    html_str = render_to_string('livestock/epp_prilog3_pdf.html', {
        'company':  company,
        'epp':      epp,
        'apiaries': apiaries,
        'godina':   godina,
    })
    pdf_bytes = HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf()

    from django.core.files.base import ContentFile
    fname = f'EPP_Prilog3_{company.oib}_{godina}.pdf'
    epp.pdf_file.save(fname, ContentFile(pdf_bytes), save=True)

    from django.http import HttpResponse
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="{fname}"'
    return response
```

---

## ZADATAK 4 — URLs (livestock/urls.py)

Dodaj u `urlpatterns`:

```python
# Apiary (pčelarstvo)
path('apiary/',                   views.apiary_dashboard,      name='apiary_dashboard'),
path('apiary/<int:pk>/',          views.apiary_detail,         name='apiary_detail'),
path('apiary/epp/',               views.epp_dojava_generate,   name='epp_generate'),
path('apiary/<int:apiary_pk>/epp/', views.epp_dojava_generate, name='epp_generate_apiary'),
```

---

## ZADATAK 5 — Template: apiary_dashboard.html

**Fajl:** `livestock/templates/livestock/apiary_dashboard.html`

```html
{% extends 'base.html' %}
{% load i18n %}
{% block title %}Pčelarstvo — LIMIT Connect{% endblock %}
{% block page_title %}🐝 Pčelarski cockpit{% endblock %}
{% block content %}

{% if epp_alert %}
<div class="alert alert-warning d-flex align-items-center gap-2 mb-3">
  <span style="font-size:1.3rem">⚠️</span>
  <div>
    <strong>EPP rok se bliži</strong> — Godišnja dojava broja pčelinjih zajednica
    predaje se povjereniku do 31. prosinca.
    <a href="{% url 'livestock:epp_generate' %}" class="btn btn-sm btn-warning ms-2">Generiraj Prilog 3</a>
  </div>
</div>
{% endif %}

<!-- Stat kartice -->
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3">
    <div class="stat-card text-center">
      <div class="h3 text-warning">{{ apiaries|length }}</div>
      <div class="text-muted small">Pčelinjaka</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="stat-card text-center">
      <div class="h3">{{ total_hives }}</div>
      <div class="text-muted small">Aktivnih košnica</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="stat-card text-center">
      <div class="h3 {% if epp_ove_godine.predano %}text-success{% else %}text-danger{% endif %}">
        {% if epp_ove_godine.predano %}✓{% else %}✗{% endif %}
      </div>
      <div class="text-muted small">EPP {{ epp_ove_godine.godina|default:"ove god." }}</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="stat-card text-center">
      <div class="h3 {% if total_hives >= 30 %}text-success{% else %}text-warning{% endif %}">
        {% if total_hives >= 30 %}DA{% else %}NE{% endif %}
      </div>
      <div class="text-muted small">Pravo na subvencije (≥30)</div>
    </div>
  </div>
</div>

<!-- Pčelinjaci -->
<div class="row g-3 mb-4">
  {% for apiary in apiaries %}
  <div class="col-md-6">
    <a href="{% url 'livestock:apiary_detail' apiary.pk %}" class="text-decoration-none">
      <div class="stat-card h-100">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <div class="fw-bold mb-1">🏡 {{ apiary.naziv }}</div>
            <div class="text-muted small">{{ apiary.adresa|default:"Adresa nije unesena" }}</div>
          </div>
          <span class="badge {% if apiary.nacin == 'ekoloski' %}bg-success{% else %}bg-secondary{% endif %}">
            {{ apiary.get_nacin_display }}
          </span>
        </div>
        <div class="mt-2 d-flex gap-3">
          <span class="text-warning fw-bold">{{ apiary.broj_kosnica }} košnica</span>
          <span class="text-muted small">{{ apiary.get_tip_display }}</span>
          {% if apiary.epp_broj %}<span class="text-muted small">EPP: {{ apiary.epp_broj }}</span>{% endif %}
        </div>
      </div>
    </a>
  </div>
  {% empty %}
  <div class="col-12">
    <div class="stat-card text-center py-5">
      <div style="font-size:3rem" class="mb-3">🐝</div>
      <h5>Nema unesenih pčelinjaka</h5>
      <p class="text-muted">Dodajte prvi pčelinjak kako biste počeli voditi evidenciju.</p>
      <button class="btn btn-warning" onclick="alert('Forma za dodavanje — TODO')">
        + Novi pčelinjak
      </button>
    </div>
  </div>
  {% endfor %}
</div>

<!-- Zadnje berbe -->
{% if zadnje_berbe %}
<h6 class="text-muted mb-2">Zadnje berbe meda</h6>
<div class="stat-card p-0">
  <table class="table table-sm mb-0">
    <thead><tr>
      <th class="ps-3">Pčelinjak</th><th>Vrsta</th><th>Datum</th>
      <th class="text-end">Količina</th><th class="text-end pe-3">R1 račun</th>
    </tr></thead>
    <tbody>
    {% for b in zadnje_berbe %}
    <tr>
      <td class="ps-3">{{ b.apiary.naziv }}</td>
      <td>{{ b.get_vrsta_display }}</td>
      <td>{{ b.datum|date:"d.m.Y" }}</td>
      <td class="text-end">{{ b.kolicina_kg }} kg</td>
      <td class="text-end pe-3">
        {% if b.invoice %}
          <a href="/invoicing/{{ b.invoice.pk }}/" class="text-warning">{{ b.invoice.number }}</a>
        {% else %}<span class="text-muted">—</span>{% endif %}
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{% endblock %}
```

---

## ZADATAK 6 — EPP Prilog 3 PDF template

**Fajl:** `livestock/templates/livestock/epp_prilog3_pdf.html`

```html
<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<style>
  @page { margin: 20mm 15mm; size: A4; }
  body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; }
  h2 { font-size:13pt; text-align:center; margin-bottom:4pt; }
  h3 { font-size:11pt; text-align:center; color:#555; margin-bottom:16pt; }
  .box { border: 1pt solid #333; padding: 8pt 10pt; margin-bottom: 10pt; }
  .row { display:flex; gap:20pt; margin-bottom: 6pt; }
  .lbl { color:#555; font-size:9pt; min-width:160pt; }
  .val { font-weight:bold; font-size:10pt; }
  .sign-line { border-top: 1pt solid #333; margin-top:40pt; padding-top:4pt;
               font-size:8pt; color:#555; }
  .footer { font-size:8pt; color:#777; text-align:center; margin-top:20pt; }
  table { width:100%; border-collapse:collapse; margin-top:8pt; }
  th,td { border:0.5pt solid #aaa; padding:4pt 6pt; font-size:9pt; }
  th { background:#f0f0f0; font-weight:bold; }
</style>
</head>
<body>

<h2>PRILOG 3</h2>
<h3>Godišnja dojava broja pčelinjih zajednica za {{ godina }}. godinu</h3>
<p style="font-size:8.5pt; color:#555; margin-bottom:12pt; text-align:center">
  Temeljem Pravilnika o držanju pčela i katastru pčelinje paše (NN) i EU Uredbe 2021/126
</p>

<div class="box">
  <div style="font-weight:bold; margin-bottom:8pt; font-size:10.5pt">Podaci o pčelaru</div>
  <div class="row"><span class="lbl">Ime i prezime / naziv OPG-a:</span><span class="val">{{ company.name }}</span></div>
  <div class="row"><span class="lbl">OIB:</span><span class="val">{{ company.oib }}</span></div>
  <div class="row"><span class="lbl">MIBPG:</span><span class="val">{{ apiaries.0.mibpg|default:"____________" }}</span></div>
  <div class="row"><span class="lbl">Adresa:</span><span class="val">{{ company.address }}</span></div>
  <div class="row"><span class="lbl">Datum dojave:</span><span class="val">{{ epp.datum_dojave|date:"d. m. Y." }}</span></div>
</div>

<div class="box">
  <div style="font-weight:bold; margin-bottom:8pt; font-size:10.5pt">Podaci o pčelinjacima</div>
  <table>
    <thead>
      <tr>
        <th>Naziv pčelinjaka</th>
        <th>Adresa / lokacija</th>
        <th>EPP broj</th>
        <th>Tip</th>
        <th style="text-align:center">Broj košnica</th>
      </tr>
    </thead>
    <tbody>
    {% for a in apiaries %}
    <tr>
      <td>{{ a.naziv }}</td>
      <td>{{ a.adresa }}</td>
      <td>{{ a.epp_broj|default:"—" }}</td>
      <td>{{ a.get_tip_display }}</td>
      <td style="text-align:center; font-weight:bold">{{ a.broj_kosnica }}</td>
    </tr>
    {% endfor %}
    <tr style="background:#f5f5f5">
      <td colspan="4" style="font-weight:bold; text-align:right">UKUPNO:</td>
      <td style="text-align:center; font-weight:bold; font-size:11pt">{{ epp.ukupno_kosnica }}</td>
    </tr>
    </tbody>
  </table>
</div>

<div class="box">
  <div class="row">
    <span class="lbl">Ukupno pčelinjih zajednica:</span>
    <span class="val" style="font-size:14pt; color:#c9a84c">{{ epp.ukupno_zajednica }}</span>
  </div>
  <div style="font-size:8pt; color:#777; margin-top:4pt">
    * Broj zajednica spreman za prezimljavanje u trenutku dojave
  </div>
</div>

<div class="box">
  <div style="font-weight:bold; margin-bottom:8pt">Povjerenik</div>
  <div class="row"><span class="lbl">Ime i prezime povjerenika:</span>
    <span class="val">{{ epp.povjerenik_ime|default:"____________________________________________" }}</span></div>
  <div class="row"><span class="lbl">Područje nadležnosti:</span>
    <span class="val">{{ epp.povjerenik_opcina|default:"____________________________________________" }}</span></div>
</div>

<div style="display:flex; gap:40pt; margin-top:30pt">
  <div style="flex:1">
    <div class="sign-line">Potpis pčelara</div>
  </div>
  <div style="flex:1">
    <div class="sign-line">Potpis povjerenika (potvrda primitka)</div>
  </div>
</div>

<div class="footer">
  Generirano: LIMIT Connect · limit-connect.com · {{ epp.datum_dojave|date:"d.m.Y" }}
  <br>Kopija za arhivu pčelara — original ostaje u arhivi udruge/povjerenika
</div>

</body>
</html>
```

---

## ZADATAK 7 — Admin

**Fajl:** `livestock/admin.py` — dodaj na kraj:

```python
from livestock.models import Apiary, Hive, HiveInspection, HoneyHarvest, EPPDojava

class HiveInline(admin.TabularInline):
    model = Hive
    extra = 0
    fields = ['oznaka', 'tip', 'status', 'je_matica_markirana', 'boja_marke']

@admin.register(Apiary)
class ApiaryAdmin(admin.ModelAdmin):
    list_display = ['naziv', 'company', 'broj_kosnica', 'tip', 'nacin', 'epp_broj', 'aktivan']
    list_filter  = ['nacin', 'tip', 'aktivan']
    search_fields = ['naziv', 'company__name', 'epp_broj']
    inlines      = [HiveInline]

@admin.register(Hive)
class HiveAdmin(admin.ModelAdmin):
    list_display = ['oznaka', 'apiary', 'tip', 'status', 'je_matica_markirana']
    list_filter  = ['status', 'tip']
    search_fields = ['oznaka', 'apiary__naziv']

@admin.register(HiveInspection)
class HiveInspectionAdmin(admin.ModelAdmin):
    list_display = ['hive', 'datum', 'snaga_zajednice', 'varroa_posip', 'tretman_varroa']
    list_filter  = ['datum']

@admin.register(HoneyHarvest)
class HoneyHarvestAdmin(admin.ModelAdmin):
    list_display = ['apiary', 'datum', 'vrsta', 'kolicina_kg', 'cijena_kg', 'invoice']
    list_filter  = ['vrsta', 'datum']

@admin.register(EPPDojava)
class EPPDojavaAdmin(admin.ModelAdmin):
    list_display = ['company', 'godina', 'ukupno_zajednica', 'ukupno_kosnica', 'predano', 'datum_dojave']
    list_filter  = ['predano', 'godina']
    actions      = ['oznaci_predano']

    def oznaci_predano(self, request, queryset):
        from django.utils import timezone
        queryset.update(predano=True, predano_datum=timezone.now().date())
        self.message_user(request, f'{queryset.count()} dojava označeno kao predano.')
    oznaci_predano.short_description = 'Označi kao predano povjereniku'
```

---

## ZADATAK 8 — Sezonski Celery reminder

**Fajl:** `livestock/tasks.py` — dodaj:

```python
@app.task(name='livestock.epp_season_reminder')
def epp_season_reminder():
    """
    Pokreće se 1. rujna svake godine (Celery Beat).
    Šalje WhatsApp/notifikaciju svim OPG pčelarima.
    """
    from django.utils import timezone
    from livestock.models import Apiary, EPPDojava

    godina = timezone.now().year
    companies_s_pcelnjakom = Apiary.objects.filter(
        aktivan=True
    ).values_list('company_id', flat=True).distinct()

    # Firme koje još NISU predali dojavu ove godine
    predali = EPPDojava.objects.filter(
        godina=godina, predano=True
    ).values_list('company_id', flat=True)

    za_podsjetiti = set(companies_s_pcelnjakom) - set(predali)

    from notifications.models import Notification
    from companies.models import Company

    for company_id in za_podsjetiti:
        try:
            company = Company.objects.get(pk=company_id)
            Notification.objects.create(
                company=company,
                type='epp_reminder',
                title='EPP rok se bliži',
                message=f'Godišnja dojava broja pčelinjih zajednica za {godina}. godinu '
                         f'predaje se povjereniku do 31. prosinca. '
                         f'Generirajte Prilog 3 na: /livestock/apiary/epp/',
            )
        except Exception:
            pass

    return f'EPP reminder: {len(za_podsjetiti)} tvrtki obaviješteno'
```

Dodaj u Celery Beat schedule (core/celery_beat.py ili settings):
```python
'epp-season-reminder': {
    'task': 'livestock.epp_season_reminder',
    'schedule': crontab(month_of_year='9', day_of_month='1', hour='8', minute='0'),
},
```

---

## ZADATAK 9 — Navigation link

U `templates/base.html` ili `templates/includes/_nav.html`, u OPG/Livestock sekciju menija:
```html
{% if company.has_apiary %}
<li><a href="{% url 'livestock:apiary_dashboard' %}">🐝 Pčelarstvo</a></li>
{% endif %}
```

Dodaj property na Company model (companies/models.py):
```python
@property
def has_apiary(self):
    return self.apiaries.filter(aktivan=True).exists()
```

---

## ZADATAK 10 — Čišćenje: print() u synesis/bulk_import.py

Dok si tu, zamijeni svih 21 `print(...)` u `/var/www/fina-connect/synesis/bulk_import.py`
s `logger.info(...)`. Na vrhu fajla dodaj ako ne postoji:
```python
import logging
logger = logging.getLogger(__name__)
```

Zatim: `sed -i 's/^\(\s*\)print(/\1logger.info(/g' synesis/bulk_import.py`

---

## DONE kriterij

- [ ] 5 novih modela: Apiary, Hive, HiveInspection, HoneyHarvest, EPPDojava
- [ ] Migracija aplicirana, tablice postoje u bazi
- [ ] `apiary_dashboard`, `apiary_detail`, `epp_dojava_generate` views rade
- [ ] 4 nove URL rute u livestock/urls.py
- [ ] Template `apiary_dashboard.html` — prikazuje pčelinjake, košnice, EPP alert
- [ ] EPP Prilog 3 PDF — generira se, sadrži točne podatke, sprema u epp.pdf_file
- [ ] Admin: sve 5 modela registrirano, `oznaci_predano` akcija radi
- [ ] Celery Beat: `epp_season_reminder` task registriran (1. rujna)
- [ ] Nav link vidljiv za OPG s pčelinjacima
- [ ] synesis/bulk_import.py: print() → logger.info()
- [ ] Commit: "feat(livestock): Apiary modul — pčelari, EPP Prilog 3, berba meda, sezonski reminder"
