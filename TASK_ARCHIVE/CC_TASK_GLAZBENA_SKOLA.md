# CC_TASK_GLAZBENA_SKOLA — Glazbena škola segment
# Dodjeljeno: CC Code
# Prioritet: 🟢 Bez pravnih mina, gotova infrastruktura
# Datum: 02.04.2026
#
# GEMINI DRONI (prihvaćeni):
#   Dron #1: ZAMP nema API → generiramo XML/PDF obrazac, ne API pozive
#   Dron #2: BendSplit nije platna platforma → generator ugovora samo
#   Dron #3: Streaming agregacija → Celery worker sa zbirnom temeljnicom
#
# Glazbena škola = extension KUD modula (ne nova app)
# Pilot: KUD Dukat Vladislavci (u bazi, company postoji)

---

## KONTEKST — Teren (izmjereno)

```
udruge/models.py:
  - KUD segment: Repertoar, ProbaLog, Kostim, NastupPlan ← GOTOVO
  - Clan model: postoji s clanarina, dokumenti, detalji ← GOTOVO
  - Dogadjaj model: postoji s datumom, lokacijom ← GOTOVO

appointments/models.py:
  - BookingService: naziv, trajanje, cijena, slot_duration_minutes ← GOTOVO
  - Appointment: resource, service, client, datetime ← GOTOVO
  - ClientDossier: postoji ← GOTOVO

seasonal/models.py:
  - SeasonalContract tip 'autorski' ← GOTOVO
  - SeasonalPayment s HZMO prijavom ← GOTOVO

invoicing/: eRačun, PDF, fiskalizacija ← GOTOVO
```

Glazbena škola = 3 nova modela + hook u postojeće + 2 view funkcije + 3 template.

---

## ZADATAK G1 — 3 nova modela u udruge/models.py

Dodati na kraj udruge/models.py (iza ZadruznRevizija sekcije):

```python
# ═══════════════════════════════════════════════════════════════════════════
# GLAZBENA ŠKOLA
# ═══════════════════════════════════════════════════════════════════════════

class GlazbenaSkola(models.Model):
    """Konfiguracija glazbene škole unutar udruge/kompanije."""
    VRSTA_CHOICES = [
        ('privatna',  'Privatna glazbena škola'),
        ('udruga',    'Glazbena škola pri udruzi (KUD)'),
        ('opcinska',  'Općinska / gradska škola'),
        ('studij',    'Privatni studio / instruktor'),
    ]
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='glazbena_skola'
    )
    vrsta = models.CharField(max_length=20, choices=VRSTA_CHOICES, default='udruga')
    naziv_skole = models.CharField(max_length=200, blank=True)
    # Dostupni instrumenti/predmeti
    instrumenti = models.JSONField(
        default=list, blank=True,
        help_text='["Klavir", "Gitara", "Violina", "Pjevanje", "Solfeggio"]'
    )
    # Akademska godina
    skolska_godina_start = models.DateField(null=True, blank=True)
    skolska_godina_end = models.DateField(null=True, blank=True)
    # Fakturiranje
    fakturira_roditelje = models.BooleanField(default=True)
    pdv_na_nastavu = models.BooleanField(
        default=False,
        help_text='Glazbeno obrazovanje je PDV oslobođeno (čl.40 ZPDV) ako je u registru'
    )
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Glazbena škola'

    def __str__(self):
        return f"{self.company.name} — glazbena škola"


class GlazbeniUcenik(models.Model):
    """Učenik glazbene škole — može biti i Clan udruge."""
    RAZINA_CHOICES = [
        ('pripremni',    'Pripremni tečaj'),
        ('osnovna_1_3',  'Osnovna razina (1-3 god.)'),
        ('srednja_4_6',  'Srednja razina (4-6 god.)'),
        ('napredna',     'Napredna razina'),
        ('odrasli',      'Odrasli polaznik'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='glazbeni_ucenici'
    )
    # Veza na postojeći Clan model ako je član udruge
    clan = models.OneToOneField(
        Clan, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='glazbeni_ucenik'
    )
    # Ili standalone profil
    ime = models.CharField(max_length=100)
    prezime = models.CharField(max_length=100)
    datum_rodenja = models.DateField(null=True, blank=True)
    oib_roditelja = models.CharField(max_length=11, blank=True)
    kontakt_roditelj = models.CharField(max_length=200, blank=True)
    telefon = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    instrument = models.CharField(
        max_length=100, blank=True,
        help_text='Primarni instrument / predmet'
    )
    razina = models.CharField(
        max_length=20, choices=RAZINA_CHOICES, default='osnovna_1_3'
    )
    # Instruktor (iz Clan ili User modela)
    instruktor = models.ForeignKey(
        Clan, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ucenici'
    )
    datum_upisa = models.DateField(auto_now_add=True)
    je_aktivan = models.BooleanField(default=True)
    napomene = models.TextField(blank=True)

    objects = CompanyManager()

    class Meta:
        db_table = 'udruge_glazbeni_ucenik'
        ordering = ['prezime', 'ime']
        verbose_name = 'Glazbeni učenik'
        verbose_name_plural = 'Glazbeni učenici'

    def __str__(self):
        return f"{self.prezime} {self.ime} ({self.instrument or '—'})"

    @property
    def puno_ime(self):
        return f"{self.ime} {self.prezime}"


class SatGlazbene(models.Model):
    """Evidencija održanih sati — napredak + prisutnost."""
    VRSTA_SATA = [
        ('individualni', 'Individualni sat'),
        ('grupni',       'Grupna nastava'),
        ('nastup',       'Nastup / Ispit'),
        ('proba',        'Proba ansambla'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='sati_glazbene'
    )
    ucenik = models.ForeignKey(
        GlazbeniUcenik, on_delete=models.CASCADE,
        related_name='sati'
    )
    instruktor = models.ForeignKey(
        Clan, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='odrzani_sati'
    )
    datum = models.DateField()
    pocetak = models.TimeField()
    trajanje_min = models.PositiveSmallIntegerField(default=45)
    vrsta = models.CharField(max_length=20, choices=VRSTA_SATA, default='individualni')
    je_odrzan = models.BooleanField(default=True)
    razlog_izostanka = models.CharField(max_length=200, blank=True)

    # Pedagoška bilješka
    gradivo = models.CharField(
        max_length=500, blank=True,
        help_text='Što je rađeno: ljestvice, komad, tehnika...'
    )
    biljeska_instruktora = models.TextField(blank=True)
    ocjena = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='1-5, opcjonalno'
    )

    # Veza na fakturirani sat
    fakturiran = models.BooleanField(default=False)
    invoice_item = models.ForeignKey(
        'invoicing.InvoiceItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='glazbeni_sati'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyManager()

    class Meta:
        db_table = 'udruge_sat_glazbene'
        ordering = ['-datum', '-pocetak']
        verbose_name = 'Sat glazbene škole'
        verbose_name_plural = 'Sati glazbene škole'

    def __str__(self):
        return (
            f"{self.ucenik.puno_ime} — {self.datum} "
            f"({self.trajanje_min}min, {self.get_vrsta_display()})"
        )
```

---

## ZADATAK G2 — Migracija

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations udruge --name="glazbena_skola_modeli"
venv/bin/python manage.py migrate udruge
```

---

## ZADATAK G3 — View: glazbena škola dashboard

Dodati u udruge/views.py:

```python
@login_required
def glazbena_skola_dashboard(request):
    company = get_user_company(request)
    from .models import GlazbenaSkola, GlazbeniUcenik, SatGlazbene
    from django.db.models import Count, Q
    from django.utils import timezone
    today = timezone.now().date()

    try:
        skola = GlazbenaSkola.objects.get(company=company)
    except GlazbenaSkola.DoesNotExist:
        # Auto-kreiraj za KUD-ove koji nemaju setup
        skola = GlazbenaSkola.objects.create(company=company)

    ucenici = GlazbeniUcenik.objects.filter(company=company, je_aktivan=True)
    sati_ovaj_tjedan = SatGlazbene.objects.filter(
        company=company,
        datum__gte=today - timezone.timedelta(days=7),
        je_odrzan=True
    )
    sati_nefakturirani = SatGlazbene.objects.filter(
        company=company, je_odrzan=True, fakturiran=False
    )

    ctx = {
        'skola': skola,
        'ucenici_count': ucenici.count(),
        'ucenici_po_instrumentu': ucenici.values('instrument').annotate(
            n=Count('id')
        ).order_by('-n')[:8],
        'sati_tjedan': sati_ovaj_tjedan.count(),
        'sati_nefakturirani': sati_nefakturirani.count(),
        'vrijednost_nefakturirana': sati_nefakturirani.count() * 15,  # default 15€/sat
        'ucenici_lista': ucenici.select_related('instruktor')[:20],
        'nedavni_sati': SatGlazbene.objects.filter(
            company=company
        ).select_related('ucenik', 'instruktor').order_by('-datum', '-pocetak')[:10],
    }
    return render(request, 'udruge/glazbena_skola_dashboard.html', ctx)


@login_required
def glazbena_skola_fakturiraj(request):
    """
    Bulk fakturiranje nefakturiranih sati za odabrane učenike.
    Generira Invoice po roditelju/učeniku za odabrani period.
    """
    company = get_user_company(request)
    from .models import GlazbeniUcenik, SatGlazbene
    from invoicing.models import Invoice, InvoiceItem

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    ucenik_id = request.POST.get('ucenik_id')
    cijena_po_satu = float(request.POST.get('cijena', 15))

    ucenik = get_object_or_404(GlazbeniUcenik, id=ucenik_id, company=company)
    sati = SatGlazbene.objects.filter(
        company=company, ucenik=ucenik,
        je_odrzan=True, fakturiran=False
    )

    if not sati.exists():
        return JsonResponse({'ok': False, 'msg': 'Nema nefakturiranih sati'})

    # Kreiraj fakturu
    from django.utils import timezone
    invoice = Invoice.objects.create(
        company=company,
        client_name=ucenik.kontakt_roditelj or ucenik.puno_ime,
        client_oib=ucenik.oib_roditelja or '',
        date_issued=timezone.now(),
        date_due=timezone.now() + timezone.timedelta(days=15),
        status='DRAFT',
        doctype='R',
        note=f'Nastava glazbe — {ucenik.puno_ime}, {sati.count()} sati',
    )

    for sat in sati:
        item = InvoiceItem.objects.create(
            invoice=invoice,
            description=f'Sat glazbene nastave — {sat.datum} ({sat.trajanje_min}min)',
            quantity=1,
            unit_price=cijena_po_satu,
            tax_rate=0 if not ucenik.company.glazbena_skola.pdv_na_nastavu else 25,
        )
        sat.fakturiran = True
        sat.invoice_item = item
        sat.save(update_fields=['fakturiran', 'invoice_item'])

    invoice.recalculate_totals()
    invoice.save()

    return JsonResponse({
        'ok': True,
        'invoice_id': invoice.id,
        'invoice_number': invoice.number,
        'total': float(invoice.total),
        'sati_count': sati.count(),
    })
```

---

## ZADATAK G4 — ZAMP XML generator (bez API ovisnosti — Gemini Dron #1 fix)

Kreirati `udruge/zamp_export.py`:

```python
"""
ZAMP obrazac za prijavu izvođenih glazbenih djela.
Ne koristi ZAMP API (ne postoji). Generira strukturirani XML/PDF.
Koristi XAdES infrastrukturu koja već postoji u eracun/.

Rezultat: digitalno potpisan XML koji organizator šalje na prijavadj@zamp.hr
"""
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from datetime import date


def generiraj_zamp_obrazac(company, dogadjaj, set_lista: list) -> bytes:
    """
    set_lista = [
        {"naslov": "Lijepa naša", "izvodjac": "KUD Dukat", "autor": "Josip Runjanin",
         "trajanje_min": 4, "broj_izvedbi": 1, "vrsta": "folk"},
        ...
    ]
    Vraća UTF-8 XML bytes koji se sprema kao dokument i šalje ZAMP-u.
    """
    root = Element("ZAMPPrijava")
    root.set("verzija", "1.0")
    root.set("datum", date.today().isoformat())

    org = SubElement(root, "Organizator")
    SubElement(org, "Naziv").text = company.name
    SubElement(org, "OIB").text = company.oib
    SubElement(org, "Adresa").text = getattr(company, 'address', '')

    ev = SubElement(root, "Dogadjaj")
    SubElement(ev, "Naziv").text = dogadjaj.name if dogadjaj else "Nastup"
    SubElement(ev, "Datum").text = (
        dogadjaj.date.isoformat() if dogadjaj and dogadjaj.date else date.today().isoformat()
    )
    SubElement(ev, "Lokacija").text = getattr(dogadjaj, 'location', '') if dogadjaj else ''

    djela = SubElement(root, "IzvodjenaDjela")
    for i, stavka in enumerate(set_lista, 1):
        djelo = SubElement(djela, "Djelo")
        djelo.set("rbr", str(i))
        SubElement(djelo, "Naslov").text = stavka.get("naslov", "")
        SubElement(djelo, "Izvodjac").text = stavka.get("izvodjac", "")
        SubElement(djelo, "Autor").text = stavka.get("autor", "")
        SubElement(djelo, "TrajanjeSekundi").text = str(
            stavka.get("trajanje_min", 0) * 60
        )
        SubElement(djelo, "BrojIzvedbi").text = str(stavka.get("broj_izvedbi", 1))
        SubElement(djelo, "VrstaDjela").text = stavka.get("vrsta", "glazba")

    raw = tostring(root, encoding="utf-8", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ", encoding="utf-8")
```

---

## ZADATAK G5 — URL i sidebar

Dodati u `udruge/urls.py`:
```python
path('glazbena-skola/', views.glazbena_skola_dashboard, name='glazbena_skola_dashboard'),
path('glazbena-skola/fakturiraj/', views.glazbena_skola_fakturiraj, name='glazbena_fakturiraj'),
```

Dodati u sidebar (base.html ili udruge_dashboard) link na glazbena_skola_dashboard
kad je aktivan segment 'kud' ili 'glazbena_skola'.

---

## ZADATAK G6 — Template: glazbena_skola_dashboard.html

```
templates/udruge/glazbena_skola_dashboard.html
```

Sekcije:
1. 4 stat kartice: učenici ukupno, sati ovaj tjedan, nefakturirani sati, vrijed. nefakturirano
2. Učenici po instrumentu (mini bar chart ili badge lista)
3. Tablica učenika s kolonama: ime, instrument, razina, instruktor, [Dodaj sat] gumb
4. Zadnjih 10 sati s HTMX inline fakturiranjem
5. Gumb "Fakturiraj sve nefakturirane sate" → bulk fakturiranje

---

## NAPOMENE (Gemini Dron #2 fix):

BendSplit:
- NE implementirati platni split
- NE primati novac za više entiteta
- Generator ugovora: ako bend nastupa, sustav generira N zasebnih ugovora o djelu
  (jedan po članu) prema organizatoru — svaki za svoju naknadu
- Organizator plaća direktno na žiro/IBAN člana
- LIMIT Connect vodi samo evidenciju za poreznu analitiku

Streaming import (Gemini Dron #3 fix):
- Celery task `aggregate_streaming_csv`:
  - Čita Spotify/Apple Music CSV
  - Zbroji u memoriji po platformi/periodu
  - Upiše JEDNU zbirnu temeljnicu
  - Orignal CSV spremi na medij kao arhivski dokument (DocumentBlob)

---

## PROVJERA:

```bash
venv/bin/python manage.py migrate --check
venv/bin/python manage.py shell -c "
from udruge.models import GlazbenaSkola, GlazbeniUcenik, SatGlazbene
print('Modeli OK:', GlazbenaSkola, GlazbeniUcenik, SatGlazbene)
"
```

## GIT:
```bash
git add udruge/models.py udruge/views.py udruge/urls.py \
        udruge/zamp_export.py \
        templates/udruge/glazbena_skola_dashboard.html
git commit -m "feat(udruge): glazbena škola — učenici, sati, fakturiranje, ZAMP XML"
```
