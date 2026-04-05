# BOXGRAM — Arhitektura Review

**Datum:** 05.04.2026.  
**Status:** Review celokupne strukture modela i API dizajna  
**Prioritet:** VISOK

---

## A1. PetProfile.slug — Strategija generiranja

### Analiza
Trenutni model koristi `SlugField(max_length=120, unique=True)` bez eksplicitne strategije.

### Preporuka: `{name}-{species}-{uuid4[:8]}`

```python
# U PetProfile.save()
import uuid as uuid_module

def save(self, *args, **kwargs):
    if not self.slug:
        base = f"{self.name}-{self.get_species_display()}".lower()
        base = base.replace(' ', '-').replace('č', 'c').replace('š', 's').replace('ž', 'z')
        # Ukloni znakove koji nisu alfanumerički i crtica
        base = ''.join(c for c in base if c.isalnum() or c == '-')
        suffix = str(uuid_module.uuid4())[:8]
        self.slug = f"{base}-{suffix}"
        
        # Osiguraj unique
        counter = 1
        original_slug = self.slug
        while PetProfile.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = f"{original_slug}-{counter}"
            counter += 1
    
    if self.death_date:
        self.is_memorial = True
    if not self.sha256_seal:
        self.sha256_seal = self._generate_seal()
    super().save(*args, **kwargs)
```

### Primjeri
- Pas "Rex" → `rex-pas-a1b2c3d4`
- Košnica "Košnica #1" → `kosnica-1-pcela-e5f6g7h8`
- Kolodrač "Ljubeta" → `ljubeta-konj-i9j0k1l2`

### Benefiti
- Ljudski čitljiv URL: `/memio.pet/ljubimac/rex-pas-a1b2c3d4/`
- Globalna unikalnost bez kolizija
- SEO-friendly
- Pokazuje vrstu u slugu

---

## A2. CompetitionVote — unique_together BUG

### Problem
```python
class CompetitionVote(models.Model):
    entry = models.ForeignKey(CompetitionEntry, on_delete=models.CASCADE)
    voter_ip = models.GenericIPAddressField()
    
    class Meta:
        unique_together = ['entry__competition', 'voter_ip']  # ❌ GREŠKA
```

`entry__competition` nije validno — Django ne podržava relationship traversal u `unique_together`.

### Rješenje: Dodaj direktan FK na Competition

```python
class CompetitionVote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(CompetitionEntry, on_delete=models.CASCADE, related_name='vote_records')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='votes')
    voter_ip = models.GenericIPAddressField()
    voter_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['competition', 'voter_ip']]  # ✅ ISPRAVAK
        
    def save(self, *args, **kwargs):
        # Osiguraj da je competition ista kao entry.competition
        if self.entry and self.entry.competition != self.competition:
            self.competition = self.entry.competition
        super().save(*args, **kwargs)
```

### Migracijska strategija
```bash
python manage.py makemigrations boxgram
python manage.py migrate
```

---

## A3. EventHeart — IP vs. User vs. Per-Event

### Analiza zadatka
```python
class EventHeart(models.Model):
    event = models.ForeignKey(LifeEvent, on_delete=models.CASCADE)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField()
    
    class Meta:
        unique_together = ['event', 'ip']
```

### Preporuka: Hybrid pristup — User OR IP

Ako je user uključen, koristiti user-based limit. Inače, IP-based.

```python
class EventHeart(models.Model):
    event = models.ForeignKey(LifeEvent, on_delete=models.CASCADE, related_name='hearts')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Registrirani korisnici: 1 glas/user/event
            models.UniqueConstraint(
                fields=['event', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_heart_per_user_per_event'
            ),
            # Anonimni: 1 glas/IP/event
            models.UniqueConstraint(
                fields=['event', 'ip'],
                condition=models.Q(user__isnull=True),
                name='unique_heart_per_ip_per_event'
            ),
        ]
```

---

## A4. SocialImport → LifeEvent — OneToOne vs. ForeignKey

### Problem
Trenutno: `mapped_to = models.OneToOneField(LifeEvent, ...)`

Mogućnost: Može li jedan LifeEvent biti mapiran na više SocialImporta?

### Preporuka: ForeignKey

```python
class SocialImport(models.Model):
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name='imports')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    source_url = models.URLField()
    source_id = models.CharField(max_length=200, blank=True)
    
    # OneToOne → ForeignKey
    mapped_to = models.ForeignKey(
        LifeEvent, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='social_imports'
    )
    
    class Meta:
        unique_together = [['pet', 'platform', 'source_id']]  # Sprječava duplikate
```

**Benefiti:**
- Korisnik može spojiti više importa u jedan event
- Reverse lookup: `event.social_imports.all()`
- Lakši batch import

---

## A5. Tenant izolacija — Feed architekturat

### Zadatak
U CC_TASK koristi se "Tenant", ali u fina-connect to je `companies.Company`.

### Preporuka: Per-Tenant Feed (per-Company)

```python
class FeedQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant, is_public=True)

class PetProfile(models.Model):
    tenant = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='pets')
    # ... ostalo ...
    objects = models.Manager.from_queryset(FeedQuerySet)()
```

**Aplikacija:**
- Svaka tvrtka vidi samo vlastite ljubimce
- GDPR-compliant
- Mogućnost "javnog marketplace" kao opt-in feature

---

## A6. Memorial Mode — EventHeart i CompetitionEntry

### Ključne odluke

1. **Hearts:** ✅ Nastavljaju se dodavati (počast mrtvomu ljubimcu)
2. **Takmičenja:** ❌ Mrtvi ljubimci NE SMO sudjelovati u normalnim takmičenjima
   - Opcija: Posebna "Memorial Competition" kategorija

```python
class CompetitionEntry(models.Model):
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    
    def clean(self):
        if self.pet.is_memorial:
            if not self.competition.is_memorial:
                raise ValidationError("Mrtvi ljubimci mogu biti samo u memorial takmičenjima")

class Competition(models.Model):
    is_memorial = models.BooleanField(
        default=False,
        help_text="Takmičenje samo za mrtve ljubimce"
    )
```

---

## A7. Qrcode Library — Verifikacija

### Status

```
qrcode==8.2  # ✅ Već u requirements.txt
```

Verzija 8.2 je stabilna, sadrži sve potrebne feature-e:
- PNG/SVG generiranje
- Pillow integracija
- Unicode podrška

Koristi zadane postavke za QR generiranje.

---

## A8. Zaključne preporuke

### Hitni popravci (MUSTHAVE)
1. **CompetitionVote:** Dodaj `competition` FK i ispravit unique_together
2. **Tenant izolacija:** Per-Company feed (GDPR-compliant)
3. **Slug generator:** UUID suffix za globalnu unikalnost

### Fleksibilnost (SHOULD)
1. **SocialImport:** ForeignKey umjesto OneToOne
2. **EventHeart:** UniqueConstraint za User OR IP logic
3. **Memorial mode:** Separacija u takmičenjima

### Nice-to-have (NICE)
1. **QRcode:** Već dostupno, koristiti u Celery task-u

### Testing: Min 80% coverage
- uniqueness constraints
- competition voting
- memorial flags
- social import mapping
