# BOXGRAM — Risk Report & Adversarial Analysis

**Datum:** 05.04.2026.  
**Threat Level:** MEDIUM-HIGH  
**Status:** Sve rizike trebam mitigirati prije GA (General Availability)

---

## R1. Fake glasovi — IP Spoofing & VPN Abuse

### Opis rizika
Korisnik/bot glasa više puta za istu stavku koristeći različite IP adrese (VPN, proxy, datacenter).

**Scenario:**
```
Uzgajivač Ljubeta želi osvojiti "Najbolji kennel" takmičenje.
Koristi Cloudflare WARP, ExpressVPN, i bot na 50 IPv4 adresa iz AWS-a.
Njegov pas "Rex" odjednom ima 5000 glasova od sinoć.
```

### Mitigation slojevi

#### 1A. Geometric rate limiting (IP-based)
```python
from django.core.cache import cache
from django.http import JsonResponse
import time

def vote_competition(request, competition_id, pet_id):
    ip = get_client_ip(request)
    cache_key = f"vote_limit:{competition_id}:{ip}"
    
    # 3 glasa po IP po satu max
    votes_this_hour = cache.get(cache_key, 0)
    if votes_this_hour >= 3:
        return JsonResponse(
            {'error': 'Dosegao si limit glasanja. Pokušaj kasnije.'},
            status=429
        )
    
    # Vote logika...
    
    cache.set(cache_key, votes_this_hour + 1, timeout=3600)
    return JsonResponse({'success': True})
```

#### 1B. Fingerprinting (Device + IP hybrid)
```python
import hashlib

def get_device_fingerprint(request):
    """Spravi hash od User-Agent + Accept-Language + IP."""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    ip = get_client_ip(request)
    
    fingerprint = f"{user_agent}|{lang}|{ip}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

# U modelu:
class CompetitionVote(models.Model):
    # ... (polja) ...
    device_fingerprint = models.CharField(max_length=16, db_index=True)
    
# U view-u:
def vote_competition(request, competition_id, pet_id):
    fp = get_device_fingerprint(request)
    
    # 5 glasova po deviceu po danu
    fp_votes_today = CompetitionVote.objects.filter(
        competition_id=competition_id,
        device_fingerprint=fp,
        voted_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    if fp_votes_today >= 5:
        return JsonResponse({'error': '5 glasova po uređaju po danu'}, status=429)
```

#### 1C. Cloudflare Turnstile (CAPTCHA zaštita)
```python
# settings.py
TURNSTILE_SITE_KEY = "..."  # Javna ključ
TURNSTILE_SECRET_KEY = "..." # Privatna ključ (env var)

# template (prije gumba za glasanje):
<form method="POST">
    <!-- Obavezna CAPTCHA -->
    <div class="cf-turnstile" data-sitekey="{{ turnstile_site_key }}"></div>
    <button type="submit">Glasaj</button>
</form>

<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" defer></script>

# views.py
def vote_competition(request, competition_id, pet_id):
    token = request.POST.get('cf-turnstile-response')
    
    # Provjeri token na Cloudflare serveru
    r = requests.post(
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
        json={'secret': settings.TURNSTILE_SECRET_KEY, 'response': token}
    )
    result = r.json()
    
    if not result.get('success'):
        return JsonResponse({'error': 'CAPTCHA failed'}, status=400)
    
    # Nastavi sa glasanjem...
```

#### 1D. Honeypot polje
```html
<!-- template (hidden) -->
<form method="POST">
    <input type="text" name="website" style="display:none" />
    <!-- Samo bot-i će popuniti -->
    {% csrf_token %}
    <!-- Pravi polja -->
    <div class="cf-turnstile" ...></div>
    <button type="submit">Glasaj</button>
</form>

# views.py
def vote_competition(request):
    honeypot = request.POST.get('website', '')
    if honeypot:
        # Automatski odbij (bot)
        logging.warning(f"Honeypot hit from {get_client_ip(request)}")
        return JsonResponse({'error': 'Greška'}, status=400)
```

#### 1E. Elasticsaerch/Redis za analizu
```python
# Nakon svakog glasa
vote = CompetitionVote.objects.create(...)

# Log u Redis za analizu
redis_client.lpush(
    f'votes:{competition_id}',
    json.dumps({
        'pet_id': str(pet.id),
        'ip': get_client_ip(request),
        'fp': get_device_fingerprint(request),
        'timestamp': timezone.now().isoformat(),
    })
)

# Anomaly detection
votes_redis = redis_client.lrange(f'votes:{competition_id}', 0, -1)
# Analiza: Ako 100 glasova za istu IP u 10 minut → flag kao suspicious
```

### Provjera prije GA
- [ ] Turnstile integracija aktivna
- [ ] Rate limiting na svim endpointima
- [ ] Device fingerprinting na CompetitionVote model
- [ ] Monitoring alerta za anomalije (> 10 glasova/min)
- [ ] Weekly review glasa sa angarnih IPA / bot servera

---

## R2. GDPR brisanje — Vlasnik traži "pravo na zaboravljanje"

### Opis rizika
Korisnik (vlasnik ljubimca) traži brisanje svih svojih podataka. Što se dešava sa:
1. **PetProfile** — vrati se u archiv ili briši?
2. **LifeEvent** — briši li se ili anonimizira?
3. **EventHeart** — glasove od ostalih korisnika?
4. **CompetitionEntry** — pobjedanke u takmičenjima?

### GDPR pravilo
> Vlasnik ima pravo na brisanje ("pravo na zaboravljanje") osim ako podaci nisu potrebni za:
> - Adheartence sa zakonom (retencija)
> - Izvršavanje ugovora
> - Legalni razlogi (npr. tužba)

### Strategija: Anonymization umjesto brisanja

```python
from django.db import models

class PetProfile(models.Model):
    # ... (polja) ...
    is_anonymized = models.BooleanField(default=False)
    anonymized_at = models.DateTimeField(null=True, blank=True)

class DeletionRequest(models.Model):
    """GDPR Article 17 deletion request."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()  # "Više ne koristim", itd.

# Management command:
# python manage.py gdpr_delete_pet <pet_id>

from django.core.management.base import BaseCommand
from django.utils import timezone

class Command(BaseCommand):
    def handle(self, *args, **options):
        pet_id = options['pet_id']
        pet = PetProfile.objects.get(id=pet_id)
        
        # 1. Anonimizacija
        pet.owner = None
        pet.name = f"[Anonimni ljubimac #{pet.id[:8]}]"
        pet.bio = "[Obrisano po GDPR zahtjevu]"
        pet.avatar = None
        pet.cover_photo = None
        pet.is_anonymized = True
        pet.anonymized_at = timezone.now()
        pet.save()
        
        # 2. Briši osjetljive FK
        PetFollower.objects.filter(pet=pet).delete()
        # EventHeart ostaju (nisu personalni podaci od vlasnika)
        
        # 3. Anonymizacija events
        for event in pet.events.all():
            event.title = "[Obrisano]"
            event.description = ""
            event.location = ""
            event.is_public = False
            event.save()
            
        # 4. Medije briši
        for media in event.media.all():
            if media.file:
                media.file.delete()
            media.delete()
        
        # 5. Socijalni importi
        SocialImport.objects.filter(pet=pet).delete()
        
        # 6. Takmičenja
        for entry in pet.competition_entries.all():
            entry.delete()
        
        # 7. Log akciju
        DeletionRequest.objects.create(
            user=pet.owner,
            pet=pet,
            reason="GDPR brisanje",
            processed_at=timezone.now()
        )
        
        self.stdout.write(f"✓ Pet {pet.id} anonymized")
```

### Što se ne briše
- **EventHeart od ostalih korisnika** — Nisu personalni podaci vlasnika (to su dojmovi ostalih)
- **CompetitionVote** — Glasovi su anonimni (ili vezani na drugog korisnika)
- **Arhivski podaci** — Za forenziku i audit trail

### GDPR dokumentacija
- [ ] Privacy Policy: https://memio.pet/privacy
- [ ] Terms of Service: https://memio.pet/terms
- [ ] Data Processing Agreement (DPA) za prave osobe (vlasnici)
- [ ] Response template na GDPR zahtjeve (max 30 dana)

---

## R3. Privatnost mrtvih ljubimaca — Tko editira memorial?

### Scenario
```
Ljubeta je umro krajem 2023.
Njegov vlasnik (Marko) je editirao "Memorijal" event godinu dana.
Sada Marko proda kuću drugoj obitelji.
Nova obitelj želi editirati Ljubetin profil jer žive u kući.
Ima li prava?
```

### Rizik
- **Transfer vlasništva:** Tko je novi vlasnik Ljubetinog profila?
- **Konkurentni editiranja:** Dva vlasnika = konflikt
- **Zaštita memorijala:** Originalni vlasnik ne želi da drugi editing

### Rješenje: Inheritance model

```python
class PetProfileOwnershipHistory(models.Model):
    """Lanac vlasništva — tko je imao psa i kada."""
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name='ownership_history')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    acquired_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-acquired_at']

# U PetProfile:
class PetProfile(models.Model):
    # ... (polja) ...
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pets')
    
    @property
    def previous_owners(self):
        return [oh.owner for oh in self.ownership_history.filter(is_current=False) if oh.owner]
    
    def can_edit_memorial(self, user):
        """Može li korisnik editirati memorial?"""
        if user == self.owner:
            return True  # Trenutni vlasnik
        if user in self.previous_owners:
            return True  # Bivši vlasnik (ako je memorial)
        if self.owner and user in self.owner.profile.memorial_editors.all():
            return True  # Delegirano pravo
        return False

class MemorialEditor(models.Model):
    """Delegirane dozvole za editiranje memorijala."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memorial_editors')
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

**UI za transfer vlasništva (admin):**
```
Vlasnik: Marko Horvat

[Promijeni vlasnika]
 ↓
Modal:
├─ Novi vlasnik (email): [pedja@gmail.com]
├─ Pristup memorijalu: ☑ Dozvoli bivšem vlasniku da editira
├─ Notifikacija: ☑ Pošalji email novom vlasniku
└─ [Potvrdi transfer]
```

### Audit trail
```python
# U LifeEvent.save():
if changed_fields:
    MemorialEditLog.objects.create(
        event=self,
        editor=user,
        changes=changed_fields,
        timestamp=timezone.now()
    )
```

---

## R4. FB/IG API nestabilnost — oEmbed kao fallback

### Opis rizika
Meta (Facebook/Instagram) često mijenja API, zahtjeve autentifikaciju, ili gase staare verzije.

**Timeline problema:**
- 2024: Graph API v18 je standard
- 2025: Meta zahtjeva app review za pristup private posts
- 2026: ? (API instability trend continues)

### Strategija: Graceful degradation

#### Tier 1: Pokušaj oEmbed (bez kredencijala)
```python
@shared_task
def fetch_social_import(import_id):
    imp = SocialImport.objects.get(id=import_id)
    
    oembed_providers = {
        'instagram.com': 'https://graph.facebook.com/v18.0/instagram_oembed',
        'facebook.com': 'https://www.facebook.com/plugins/post/oembed.json',
        'tiktok.com': 'https://www.tiktok.com/oembed',
    }
    
    for domain, endpoint in oembed_providers.items():
        if domain in imp.source_url:
            try:
                r = requests.get(
                    endpoint,
                    params={'url': imp.source_url},
                    timeout=5
                )
                if r.status_code == 200:
                    data = r.json()
                    imp.thumbnail_url = data.get('thumbnail_url')
                    imp.caption = data.get('title')
                    imp.raw_data = data
                    imp.save()
                    return  # Success!
            except Exception as e:
                logging.warning(f"oEmbed failed: {e}")
```

#### Tier 2: Fallback na beautifulsoup (scrape public metadata)
```python
# Ako oEmbed ne radi
try:
    r = requests.get(imp.source_url, timeout=5)
    soup = BeautifulSoup(r.content, 'html.parser')
    
    # Pretraži og:title, og:image, og:description
    title = soup.find('meta', property='og:title')
    image = soup.find('meta', property='og:image')
    description = soup.find('meta', property='og:description')
    
    if title:
        imp.caption = title['content']
    if image:
        imp.thumbnail_url = image['content']
    if description:
        imp.raw_data['description'] = description['content']
    
    imp.save()
    return  # Success!
except Exception as e:
    logging.warning(f"Scrape failed: {e}")
```

#### Tier 3: Fallback na user manual entry
```
SocialImport status: pending
Display to user:
┌─────────────────────┐
│ Učitavanje nije    │
│ uspjelo. Molim te  │
│ ručno unesi:       │
│                     │
│ Naslov (caption):  │
│ [____________]     │
│                     │
│ Datum objave:      │
│ [____________]     │
│                     │
│ Thumbnail URL:     │
│ [____________]     │
│                     │
│ [Spremi]           │
└─────────────────────┘
```

### Monitoring
```python
# tasks.py
@shared_task
def monitor_oEmbed_health():
    """Dnevna provjera stanja oEmbed providera."""
    providers = {
        'instagram.com': 'https://graph.facebook.com/v18.0/instagram_oembed',
        'facebook.com': 'https://www.facebook.com/plugins/post/oembed.json',
        'tiktok.com': 'https://www.tiktok.com/oembed',
    }
    
    for domain, endpoint in providers.items():
        try:
            r = requests.head(endpoint, timeout=5)
            status = 'OK' if r.status_code < 500 else 'DEGRADED'
        except Exception:
            status = 'DOWN'
        
        Alert.objects.create(
            service=f'oembed_{domain}',
            status=status,
            timestamp=timezone.now()
        )
```

---

## R5. Zabranjeni sadržaj — Okrutnost, ilegalni uzgoj, zaštićene vrste

### Kategorije rizika

| Sadržaj | Rizik | Akcija |
|---------|-------|--------|
| Okrutnost prema životinjama | HIGH | Briši event, suspenzija računa |
| Ilegalni uzgoj (npr. pit bulls u zabrani) | LEGAL | Briši, report policiji ako je namjeran |
| Zaštićene vrste (npr. orao kao ljubimac) | LEGAL | Briši, kontaktiraj DZZP |
| Neslužbeni veterinar | MEDIUM | Flag, tražiti provjeru |
| Gore slike ili videos | HIGH | Briši, provjeri ako je ID korisnika ← bot |

### Implementation — Report system

```python
class ContentReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ('cruelty', 'Okrutnost prema životinjama'),
        ('illegal_breed', 'Ilegalni uzgoj'),
        ('protected_species', 'Zaštićena vrsta'),
        ('abuse', 'Zlostavljanje / Nasilje'),
        ('gore', 'Grafički sadržaj (gore)'),
        ('spam', 'Spam / Fake'),
        ('other', 'Ostalo'),
    ]
    
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(LifeEvent, on_delete=models.CASCADE, null=True, blank=True)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, null=True, blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    description = models.TextField()
    screenshot_url = models.URLField(blank=True)
    
    STATUS_CHOICES = [
        ('pending', 'Na čekanju'),
        ('reviewing', 'U pregledu'),
        ('resolved', 'Riješeno'),
        ('dismissed', 'Odbijeno'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reviewed_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    action_taken = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# View za report
def report_content(request):
    form = ContentReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.reported_by = request.user
        report.save()
        
        # Notify moderators (async)
        notify_moderation_team.delay(report.id)
        
        return JsonResponse({'status': 'reported'})
```

### Moderation workflow

```
1. Report prima → status='pending'
2. Moderator: POST /admin/contentreport/{id}/review/
   - Otvori listu sa sve evicence
   - Opcije: [Briši] [Suspenzija] [Kontakt DZZP] [Odbij]
3. Ako [Briši]:
   - LifeEvent.is_public = False (soft delete)
   - ContentReport.status = 'resolved'
   - ContentReport.action_taken = 'Event hidden'
   - Email vlasniku: "Tvoj event je uklonjen jer je prekršio ToS"
4. Ako [Suspenzija]:
   - User.is_active = False (temp ban)
   - Send temp ban email (24h - 30 dana)
5. Ako [Kontakt DZZP]:
   - Generiraj report PDF sa detaljima
   - Email na dzzp@mzo.hr sa screenshot-ovima
   - Log slanje
```

### Automatska detektacija (future)
- OpenAI Vision API: Analiza slike za znakove okrutnosti
- Text classifier: NLP za tekst sa okrutnostima
- Threshold: Ako confidence > 0.8 → Flag za moderaciju

---

## R6. Pčele regulativa — HAPIH registracija košnica

### Opis
U Hrvatskoj, професионални pčelari moraju biti registrirani kod **HAPIH** (Hrvatska Agencija za Poljoprivredu).

**Scenarij Pera Laplisa:**
```
Pero ima 5 košnica za uzgoj pčela.
Trebao bi:
1. HAPIH registraciju
2. Veterinarsku certifikaciju košnice
3. "Izvezeni med" dokumentaciju za prodaju
```

### Implementacija u Boxgram

```python
class BeeHive(models.Model):
    """Poseban model za košnice (umjesto generičkog PetProfile za pcele)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bee_hives')
    
    # Identifikacija
    hive_number = models.CharField(max_length=50, unique=True)  # Npr. "HR-PERO-001"
    location_address = models.CharField(max_length=200)
    location_latitude = models.FloatField()
    location_longitude = models.FloatField()
    
    # HAPIH
    hapih_registration_number = models.CharField(max_length=50, blank=True, unique=True)
    hapih_registered_at = models.DateField(null=True, blank=True)
    hapih_expires_at = models.DateField(null=True, blank=True)
    
    # Zdravlje
    vet_certification_number = models.CharField(max_length=100, blank=True)
    vet_checked_at = models.DateField(null=True, blank=True)
    disease_free = models.BooleanField(default=True)
    last_inspection = models.DateField(null=True, blank=True)
    
    # Inventar
    estimated_population = models.PositiveIntegerField(default=50000)  # Broj pčela
    queen_birth_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Pčelinja košnica'
        verbose_name_plural = 'Pčelinjaske košnice'
    
    def __str__(self):
        return f"Košnica {self.hive_number}"

# Special events za pčele
# U SPECIES_CHOICES već je ('pcela', 'Pčelinja zajednica')
# U EVENT_TYPE_CHOICES trebam dodati pčele-specifične:
# ('rojenje', 'Rojenje / Skupljanje roja')
# ('med_berba', 'Berba meda')
# ('zimovanje', 'Zimovanje')
# ('zagrada', 'Zagrada')

class BeeHiveEvent(models.Model):
    """Životni događaji u košnici (specijalizacija LifeEvent-a)."""
    BEE_EVENT_TYPES = [
        ('rojenje', 'Rojenje'),
        ('med_berba', 'Berba meda'),
        ('zimovanje', 'Zimovanje'),
        ('zagrada', 'Zagrada (biljka)'),
        ('bolest', 'Bolest / Tretman'),
        ('matrice_zamjena', 'Zamjena matice'),
        ('inspeksija', 'Inspeksija / Pregled'),
    ]
    
    hive = models.ForeignKey(BeeHive, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=BEE_EVENT_TYPES)
    date = models.DateField()
    description = models.TextField(blank=True)
    # Metrike specifične za pčele
    population_estimate = models.PositiveIntegerField(null=True, blank=True)
    honey_harvest_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pollen_harvest_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

# Admin akcije

class BeeHiveAdmin(admin.ModelAdmin):
    actions = ['export_for_hapih', 'export_for_vet']
    
    def export_for_hapih(self, request, queryset):
        """Generiraj CSV za HAPIH registraciju."""
        csv_data = "Hive Number,Address,Registration #,Expires\n"
        for hive in queryset:
            csv_data += f"{hive.hive_number},{hive.location_address},{hive.hapih_registration_number},{hive.hapih_expires_at}\n"
        
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="hapih_export.csv"'
        return response
    export_for_hapih.short_description = "Izvezi za HAPIH registraciju"
    
    def export_for_vet(self, request, queryset):
        """Generiraj listu za veterinarsku inspekciju."""
        pdf = generate_vet_report(queryset)  # Helper funkcija
        return HttpResponse(pdf, content_type='application/pdf')
    export_for_vet.short_description = "Izvezi za veterinara"
```

### UI za pčelarsku registraciju

```
PetProfile kreiranja (za vrstu 'pcela'):
┌──────────────────────────────┐
│ "Tvoja pčelinja zajednica"   │
│                              │
│ Ime/Oznaka košnice:          │
│ [HR-PERO-001]                │
│                              │
│ Lokacija (lat/lng):          │
│ [43.5231, 16.4401] 🗺       │
│                              │
│ HAPIH registracija (opciono):│
│ [Broj registracije]          │
│ [Datum registracije]         │
│ [Vidljivost HAPIH baze] ☐    │
│                              │
│ Veterinarska certifikacija:  │
│ [Broj certifikata] [Datum]   │
│ [Je li zdravo] ☑             │
│                              │
│ [Spremi]                     │
└──────────────────────────────┘
```

---

## Zaključne preporuke

### MUSTHAVE prije GA
1. **R1:** Turnstile + rate limiting + device fingerprint
2. **R2:** GDPR anonymization workflow + DPA dokumentacija
3. **R3:** Ownership transfer model + memorial editor permissions
4. **R4:** oEmbed + BeautifulSoup fallback za import
5. **R5:** ContentReport model + moderation workflow
6. **R6:** BeeHive model + HAPIH export za Pera

### SHOULD (tijekom razvoja)
- Automated content detection (Vision API za slike)
- GeoIP blocking za problematične regije (optional)
- SMS 2FA za pčelarsku registraciju

### Monitoring
- [ ] Daily alerts za anomalne glasove (> 10/min po comp)
- [ ] Weekly report na GDPR zahtjeve
- [ ] Monthly content moderation review
- [ ] Real-time alerts za API failures (FB, IG, TikTok)
