# GEMINI TASK: Golubar Modul — Petar Brtan, nulti pacijent
# Agent: Gemini | Prioritet: 🟠 VISOK | Datum: 2026-03-27
# Koordinator: Sonnet | max_steps: 80

## KONTEKST I PRAVILA
Petar Brtan je Ivan Brtanov brat. Solo golubar, invalid rada, pilot korisnik.
Modul se gradi na arhitekturi Lov modula (udruge/models.py) — copy-paste pattern.
App: `udruge` (postojeći) — dodaješ nove modele u postojeći models.py i views.py.

## OBAVEZNO PROČITAJ PRVO
```bash
cat FENIX_STATUS.md | head -30
git log --oneline -5
# Prouči Lov modul kao predložak:
grep -n "class Loviste\|class LovackaIskaznica\|class ZapisnikLova\|class Trofej" udruge/models.py
# Prouči Data Vaulting (is_sealed pattern):
grep -n "is_sealed\|is_vaulted\|integrity_hash\|archive_hash" invoicing/models.py | head -10
```

---

## SPRINT G1 — Temeljni modeli s Genetskim pečatom

### models.py — dodaj na kraj udruge/models.py:

```python
# ═══════════════════════════════════════════════════════════════════
# GOLUBAR MODUL — Petar Brtan pilot (2026-03-27)
# Arhitektura: Lov modul pattern + Data Vaulting (is_sealed)
# ═══════════════════════════════════════════════════════════════════

class Golubinjak(models.Model):
    """Registrirani golubinjak — EU obveza (Uredba 2016/429)."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='golubinjaci')
    naziv = models.CharField(max_length=200)
    adresa = models.CharField(max_length=300)
    gps_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    eu_registracijski_broj = models.CharField(max_length=50, blank=True,
        help_text='HR-XX-YYYY-ZZZZ format (EU 2016/429)')
    kapacitet = models.PositiveIntegerField(default=0)
    aktivan = models.BooleanField(default=True)
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Golubinjak'
        verbose_name_plural = 'Golubinjaci'

    def __str__(self):
        return f'{self.naziv} ({self.eu_registracijski_broj or "bez EU broja"})'


class Golub(models.Model):
    """Individualni golub s punim rodovnikom i genetskim pečatom."""

    SPOL_CHOICES = [('M', 'Mužjak'), ('F', 'Ženka'), ('?', 'Nepoznato')]
    BOJA_CHOICES = [
        ('plav', 'Plav'), ('crvena_siva', 'Crvena/siva'), ('bijel', 'Bijel'),
        ('crn', 'Crn'), ('smedjast', 'Smeđast'), ('karirani', 'Karirani'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='golubovi')
    golubinjak = models.ForeignKey(Golubinjak, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='golubovi')

    # Identifikacija
    prsten_broj = models.CharField(max_length=30, unique=True,
        help_text='LOK/HOG prsten broj, npr. HR-2024-12345')
    naziv = models.CharField(max_length=100, blank=True,
        help_text='Ime goluba (npr. "Strelovit", "Šampion")')
    spol = models.CharField(max_length=1, choices=SPOL_CHOICES, default='?')
    boja = models.CharField(max_length=20, choices=BOJA_CHOICES, default='ostalo')
    datum_izlijeganja = models.DateField(null=True, blank=True)
    fotografija = models.ImageField(upload_to='golubovi/', null=True, blank=True)
    napomena = models.TextField(blank=True)
    aktivan = models.BooleanField(default=True,
        help_text='Isključi za mrtve ili prodane golubove')

    # Rodovnik — direktni roditelji
    otac = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='djeca_otac', verbose_name='Otac')
    majka = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='djeca_majka', verbose_name='Majka')

    # Genetski pečat — Data Vaulting (Dron #3 zaštita)
    is_sealed = models.BooleanField(default=False,
        help_text='Zapečaćen rodovnik — ne može se mijenjati bez audit traga')
    sealed_at = models.DateTimeField(null=True, blank=True)
    sealed_reason = models.CharField(max_length=200, blank=True,
        help_text='Razlog pečaćenja: "prva_nagrada", "aukcija", "prodaja"')
    genetics_hash = models.CharField(max_length=64, blank=True,
        help_text='SHA-256 hash genetskog profila — za offline verifikaciju')

    # Statistika (cache)
    broj_utrka = models.PositiveIntegerField(default=0)
    broj_pobjeda = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Golub'
        verbose_name_plural = 'Golubovi'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.prsten_broj} — {self.naziv or "bez naziva"}'

    def izracunaj_genetics_hash(self):
        """SHA-256 hash genetskog profila za offline verifikaciju rodovnika."""
        import hashlib, json
        data = {
            'prsten': self.prsten_broj,
            'datum': str(self.datum_izlijeganja),
            'otac': self.otac.prsten_broj if self.otac else None,
            'majka': self.majka.prsten_broj if self.majka else None,
            'otac_otac': self.otac.otac.prsten_broj if self.otac and self.otac.otac else None,
            'otac_majka': self.otac.majka.prsten_broj if self.otac and self.otac.majka else None,
            'majka_otac': self.majka.otac.prsten_broj if self.majka and self.majka.otac else None,
            'majka_majka': self.majka.majka.prsten_broj if self.majka and self.majka.majka else None,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def zapecati(self, razlog='aukcija'):
        """Zapečati genetski profil — Dron #3 zaštita."""
        from django.utils import timezone
        if not self.is_sealed:
            self.genetics_hash = self.izracunaj_genetics_hash()
            self.is_sealed = True
            self.sealed_at = timezone.now()
            self.sealed_reason = razlog
            self.save()

    def save(self, *args, **kwargs):
        # Ako je zapečaćen — refresh hash pri svakom save za audit
        if self.is_sealed and not self.genetics_hash:
            self.genetics_hash = self.izracunaj_genetics_hash()
        super().save(*args, **kwargs)


class ParGolubova(models.Model):
    """Uzgojni par — praćenje legla i potomaka."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='parovi_golubova')
    golubinjak = models.ForeignKey(Golubinjak, on_delete=models.CASCADE,
                                    related_name='parovi')
    mužjak = models.ForeignKey(Golub, on_delete=models.CASCADE, related_name='par_kao_mužjak')
    ženka = models.ForeignKey(Golub, on_delete=models.CASCADE, related_name='par_kao_ženka')
    sezona = models.PositiveIntegerField(help_text='Godina uzgojne sezone')
    datum_spajanja = models.DateField(null=True, blank=True)
    datum_razdvajanja = models.DateField(null=True, blank=True)
    napomena = models.TextField(blank=True)
    aktivan = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Par golubova'
        verbose_name_plural = 'Parovi golubova'

    def __str__(self):
        return f'{self.mužjak} × {self.ženka} ({self.sezona})'


class Leglo(models.Model):
    """Jedno leglo (2 jajeta max) — praćenje potomaka."""
    par = models.ForeignKey(ParGolubova, on_delete=models.CASCADE, related_name='legla')
    datum_jaja = models.DateField(null=True, blank=True)
    datum_izlijeganja_1 = models.DateField(null=True, blank=True)
    datum_izlijeganja_2 = models.DateField(null=True, blank=True)
    ptic_1 = models.ForeignKey(Golub, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='leglo_kao_ptic_1')
    ptic_2 = models.ForeignKey(Golub, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='leglo_kao_ptic_2')
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Leglo'
        verbose_name_plural = 'Legla'


class ZdravstveniZapis(models.Model):
    """EU PMV/Newcastle obaveza — zdravstveni dnevnik goluba."""
    VRSTA_CHOICES = [
        ('cjepivo_pmv', 'Cijepljenje PMV (Paramyxovirus)'),
        ('cjepivo_newcastle', 'Cijepljenje Newcastle'),
        ('cjepivo_paratifus', 'Cijepljenje Paratifus'),
        ('antiparazitik', 'Antiparazitik'),
        ('antibiotik', 'Antibiotik'),
        ('vet_pregled', 'Veterinarski pregled'),
        ('ostalo', 'Ostalo'),
    ]
    golub = models.ForeignKey(Golub, on_delete=models.CASCADE,
                               related_name='zdravstveni_zapisi')
    vrsta = models.CharField(max_length=30, choices=VRSTA_CHOICES)
    datum = models.DateField()
    lijek_preparat = models.CharField(max_length=200, blank=True)
    doza = models.CharField(max_length=100, blank=True)
    veterinar = models.CharField(max_length=200, blank=True)
    sljedeci_tretman = models.DateField(null=True, blank=True,
        help_text='Datum sljedećeg tretmana — okida podsjetnik')
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Zdravstveni zapis'
        verbose_name_plural = 'Zdravstveni zapisi'
        ordering = ['-datum']

    def __str__(self):
        return f'{self.golub.prsten_broj} — {self.get_vrsta_display()} ({self.datum})'


class Utrka(models.Model):
    """Utrka — ERP razina, NE timing (Dron #2 zaštita).
    Petar koristi Bricon/ETS sat za timing, ovdje uvozi rezultate."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='utrke_golubovi')
    naziv = models.CharField(max_length=200)
    datum = models.DateField()
    startna_tocka = models.CharField(max_length=200,
        help_text='Npr. "Slavonski Brod", "Đakovo"')
    startna_gps_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    startna_gps_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    udaljenost_km = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    organizator = models.CharField(max_length=200, blank=True,
        help_text='Npr. "HOG Osijek", "Golubarsko društvo Čepin"')
    broj_golubova_natjecanje = models.PositiveIntegerField(null=True, blank=True)
    uvjeti = models.CharField(max_length=200, blank=True,
        help_text='Npr. "Vjetar JZ 20 km/h, oblačno"')
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utrka'
        verbose_name_plural = 'Utrke'
        ordering = ['-datum']

    def __str__(self):
        return f'{self.naziv} ({self.datum})'


class RezultatUtrke(models.Model):
    """Rezultat jednog goluba na jednoj utrci — uvoz iz ETS/Bricon."""
    utrka = models.ForeignKey(Utrka, on_delete=models.CASCADE, related_name='rezultati')
    golub = models.ForeignKey(Golub, on_delete=models.CASCADE, related_name='rezultati_utrka')
    placiranje = models.PositiveIntegerField(null=True, blank=True,
        help_text='Placiranje u kategoriji')
    placiranje_ukupno = models.PositiveIntegerField(null=True, blank=True)
    brzina_mpm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Brzina u metrima po minuti (standardna mjera)')
    vrijeme_dolaska = models.DateTimeField(null=True, blank=True)
    bodovi = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ets_data = models.JSONField(null=True, blank=True,
        help_text='Raw JSON iz ETS clock CSV uvoza')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rezultat utrke'
        verbose_name_plural = 'Rezultati utrka'
        unique_together = [('utrka', 'golub')]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ažuriraj cache statistiku na Golubu
        g = self.golub
        g.broj_utrka = RezultatUtrke.objects.filter(golub=g).count()
        g.broj_pobjeda = RezultatUtrke.objects.filter(golub=g, placiranje=1).count()
        g.save(update_fields=['broj_utrka', 'broj_pobjeda'])
```

---

## SPRINT G2 — Migracije i admin

```bash
cd /var/www/fina-connect
/var/www/fina-connect/venv/bin/python manage.py makemigrations udruge --name="golubar_modul"
/var/www/fina-connect/venv/bin/python manage.py migrate udruge
/var/www/fina-connect/venv/bin/python manage.py check
```

Dodaj u udruge/admin.py:
```python
from .models import Golubinjak, Golub, ParGolubova, Leglo, ZdravstveniZapis, Utrka, RezultatUtrke
admin.site.register([Golubinjak, Golub, ParGolubova, Leglo, ZdravstveniZapis, Utrka, RezultatUtrke])
```

Commit: `feat(G1): golubar modul — Golub, Pedigre, GenetskiPecat, Zdravlje, Utrka`

---

## SPRINT G3 — Views i URLs

Kreiraj `udruge/golubar_views.py`:

- `golubar_dashboard(request)` → `/hr/udruge/golubar/` — pregled golubinjaka
- `golub_list(request)` → lista golubova s filtrom po golubinjaku
- `golub_detail(request, pk)` → kartica goluba — rodovnik 3 generacije, zdravlje, utrke
- `golub_create(request)` → forma za novog goluba
- `golub_seal(request, pk)` → POST — zapečati genetski profil (potvrda modal)
- `zdravlje_create(request, golub_pk)` → unos zdravstvenog zapisa
- `utrka_create(request)` → nova utrka
- `rezultat_create(request, utrka_pk)` → unos/uvoz rezultata

Dodaj u udruge/urls.py:
```python
path('golubar/', views.golubar_dashboard, name='golubar_dashboard'),
path('golubar/golubovi/', views.golub_list, name='golub_list'),
path('golubar/golubovi/<int:pk>/', views.golub_detail, name='golub_detail'),
path('golubar/golubovi/novi/', views.golub_create, name='golub_create'),
path('golubar/golubovi/<int:pk>/zapecati/', views.golub_seal, name='golub_seal'),
path('golubar/utrke/', views.utrka_list, name='utrka_list'),
path('golubar/utrke/<int:pk>/', views.utrka_detail, name='utrka_detail'),
```

Commit: `feat(G2): golubar views + URLs`

---

## SPRINT G4 — PDF Rodovnik (WOW moment za Petra)

Kreiraj `udruge/golubar_pdf.py`:

```python
def generate_rodovnik_pdf(golub_pk):
    """
    Generira A4 PDF Digitalni Rodovnik s:
    - Podaci goluba (prsten, boja, spol, datum izlijeganja)
    - Rodovnik 3 generacije (vizualno stablo)
    - QR kod (na A4 papiru, čitljiv 30x30mm) → URL golub_detail
    - SHA-256 hash za offline verifikaciju
    - Zadnjih 5 utrka s rezultatima
    - Zadnjih 3 zdravstvena zapisa
    - Footer: "Verificirano LIMIT Connect | limit-connect.com"

    Koristi WeasyPrint (već instaliran).
    Sprema u media/golubovi/rodovnici/{prsten_broj}.pdf
    """
```

URL: `GET /hr/udruge/golubar/golubovi/<pk>/rodovnik.pdf/`

Commit: `feat(G3): PDF rodovnik s QR — WOW moment za Petra`

---

## SPRINT G5 — Celery podsjetnici (EU PMV compliance)

U `udruge/tasks.py` dodaj:

```python
@shared_task
def provjeri_golubar_zdravlje():
    """
    Svaki dan 08:00 — provjeri golubove kojima uskoro ističe PMV cjepivo.
    Šalje WhatsApp korisniku ako je sljedeci_tretman za 7 ili manje dana.
    Samo na WHITELIST (TEST_MODE) dok je platforma u fazi testiranja.
    """
```

Dodaj u settings.py CELERY_BEAT_SCHEDULE:
```python
"golubar-zdravlje-check": {
    "task": "udruge.provjeri_golubar_zdravlje",
    "schedule": crontab(hour=8, minute=0),
}
```

Commit: `feat(G4): Celery PMV podsjetnik — EU compliance auto-alert`

---

## SPRINT G6 — Testovi

Kreiraj `udruge/tests/test_golubar.py`:

```python
class GolubModelTest(TestCase):
    def test_genetics_hash_konzistentnost(self)  # isti rodovnik = isti hash
    def test_zapecati_blokira_promjenu_roditelja(self)  # is_sealed = True
    def test_rezultat_utrke_ažurira_statistiku(self)  # broj_utrka, broj_pobjeda
    def test_zdrav_zapis_trigger(self)  # sljedeci_tretman generira notifikaciju
    def test_rodovnik_pdf_generira(self)  # PDF postoji i nije prazan
```

```bash
/var/www/fina-connect/venv/bin/python manage.py test udruge.tests.test_golubar -v 2
```

Commit: `test(golubar): 5 testova zelenih`

---

## KRAJ TASKA

1. `python manage.py run_system_test --quick` — mora biti 0 kritičnih
2. Ažuriraj FENIX_STATUS.md — golubar modul DONE
3. WhatsApp report na +491723006985:
```
🐦 GOLUBAR MODUL LIVE

✅ Golub + GenetskiPecat
✅ Zdravstveni dnevnik (EU PMV)
✅ Utrke (ERP razina, bez timing)
✅ PDF Rodovnik s QR
✅ Celery PMV podsjetnik
✅ 5 testova zelenih

Petar može početi unositi golubove:
https://limit-connect.com/hr/udruge/golubar/
```
