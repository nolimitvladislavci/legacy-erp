# CC TASK F3 — memio.world Arhitektura + Temelj
# Prioritet: 🔥 ODMAH | Rok: 08.04.2026.
# Assignee: Claude Code
# Pokretač: Marija Čačić (knjižničar) — čeka potvrdu, ali kod mora biti spreman

## VIZIJA (Ivan)
"Priča koja će doći do Bruxellesa i postati broj 1 u digitalizaciji djetinjstva.
Isporučivati će se budućoj djeci."

Konkretno: digitalni portfolio djetinjstva koji roditelji grade za dijete,
a dijete ga naslijedi kao odrasla osoba. Čuvanje sjećanja, postignuća, dokumenata,
Svaka stranica = pogl. iz knjige života.

## ZADACI

### 1. Django app — memio_world
```bash
cd /var/www/fina-connect
python manage.py startapp memio_world
```

Registriraj u settings.py INSTALLED_APPS.
Dodaj 'memio_world' DB u DATABASES (odvojena baza kao memio_pets):
```python
'memio_world': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'memio_world',
    'USER': os.environ.get('DB_USER'),
    'PASSWORD': os.environ.get('DB_PASSWORD'),
    'HOST': 'localhost',
    'PORT': '5432',
}
```
Kreiraj bazu:
```bash
sudo -u postgres createdb memio_world
```

### 2. Modeli (memio_world/models.py)

```python
class ChildProfile(models.Model):
    """Svako dijete = jedan digitalni pasoš."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    birth_city = models.CharField(max_length=100, blank=True)
    birth_country = models.CharField(max_length=2, default='HR')
    photo = models.ImageField(upload_to='children/', null=True, blank=True)
    # Roditelji/skrbnici koji upravljaju profilom
    guardians = models.ManyToManyField('accounts.CustomUser', related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)
    # Privatnost: PRIVATE (samo obitelj), FAMILY (šira obitelj), PUBLIC
    visibility = models.CharField(max_length=10, choices=[
        ('private','Samo obitelj'), ('family','Šira obitelj'), ('public','Javno')
    ], default='private')
    
    class Meta:
        app_label = 'memio_world'
        db_table = 'mw_child_profile'

class MemoryEntry(models.Model):
    """Jedan zapis u knjizi sjećanja."""
    ENTRY_TYPES = [
        ('photo','Fotografija'), ('video','Video'), ('text','Priča/tekst'),
        ('milestone','Postignuće'), ('document','Dokument'), ('drawing','Crtež'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='memories')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    media_file = models.FileField(upload_to='memories/', null=True, blank=True)
    entry_date = models.DateField()  # Datum sjećanja (ne upload)
    age_at_entry = models.PositiveSmallIntegerField(null=True)  # Automatski izračun
    created_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_featured = models.BooleanField(default=False)
    tags = models.CharField(max_length=500, blank=True)  # CSV tagovi
    
    class Meta:
        app_label = 'memio_world'
        db_table = 'mw_memory_entry'
        ordering = ['entry_date']

class Milestone(models.Model):
    """Prekretnice — 1. korak, 1. riječ, 1. dan škole..."""
    MILESTONE_TYPES = [
        ('first_word','Prva riječ'), ('first_step','Prvi korak'),
        ('school_start','Polazak u školu'), ('graduation','Završetak obrazovanja'),
        ('sport','Sportski uspjeh'), ('art','Umjetnički uspjeh'), ('other','Ostalo'),
    ]
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='milestones')
    milestone_type = models.CharField(max_length=30, choices=MILESTONE_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    achieved_date = models.DateField()
    photo = models.ImageField(upload_to='milestones/', null=True, blank=True)
    
    class Meta:
        app_label = 'memio_world'
        db_table = 'mw_milestone'
```

### 3. Migracije
```bash
python manage.py makemigrations memio_world
python manage.py migrate --database=memio_world
```

### 4. Router za memio_world DB
U settings.py DATABASE_ROUTERS dodaj MemioWorldRouter (kao što postoji za memio_pets).
```python
class MemioWorldRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'memio_world':
            return 'memio_world'
        return None
    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'memio_world':
            return 'memio_world'
        return None
    def allow_migrate(self, db, app_label, **hints):
        if app_label == 'memio_world':
            return db == 'memio_world'
        if db == 'memio_world':
            return False
        return None
```

### 5. Landing page memio.world
URL: `/` (na memio.world domeni)
Template: `templates/memio_world/landing.html`

Design vizija:
- Tamna, elegantna paleta (navy + zlatna + bijela)
- Hero: "Svako dijete zaslužuje svoju knjigu." 
- Sub: "Digitalni portal sjećanja koji raste zajedno s vašim djetetom."
- CTA: "Počnite besplatno" (vodi na /registracija/)
- 3 sekcije: Fotografije & priče / Prekretnice / Za cijeli život
- Footer: memio.world | Projekt udruge NO LIMIT | Bruxelles ready

### 6. Placeholder stranice (za Mariju Čačić)
- `/registracija/` → "Uskoro dostupno. Pridružite se listi čekanja." + email forma
- `/o-projektu/` → kratki opis vizije (5 paragrafa)

## COMMITI
Format: `feat(memio-world): [opis]`
Minimalno: models, migration, router, landing, waitlist = 5 commitova

## NAPOMENA
memio.world je projekt koji čeka institucionalnog partnera (knjižnica).
Kod mora biti spreman kad Marija Čačić da zeleno. Ne improvizirati logiku —
samo čvrsti temelj koji se može nadograditi.
