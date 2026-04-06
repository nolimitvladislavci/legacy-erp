# ═══════════════════════════════════════════════════════════════════
# MEMIO.PET — ŽIVOTNI CIKLUS LJUBIMCA
# "Od prvog udisaja do Duginog Mosta"
# 7 Sati | 3 Dijela | 5 Agenata Paralelno
# Datum: 07.04.2026. | Koordinator: Sonnet
# ═══════════════════════════════════════════════════════════════════

## POLAZIŠNA TOČKA (verificirano)

### Što VEĆ postoji i ne treba graditi:
  ✅ AnimalProfile.status = 'uginulo' — postoji
  ✅ LifeEvent model s type='smrt','memorijal' — postoji
  ✅ PetHealthRecord, PetOwnership — postoje
  ✅ Boxgram social_import.py + video_downloader.py — backend gotov
  ✅ PetBoardingReservation (hotel) — model postoji
  ✅ RawFoodListing (BARF) — postoji
  ✅ AddAnimalToken (magic token) — postoji (0008 migracija)
  ✅ /prijava/, /registracija/, /ljubimac/novi/ — žive

### Zadnja migracija: 0008_addanimaltoken.py
### Nginx: sve ključne rute proxirane

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  DIO 1 — TEMELJ (Sat 1–2)                                   ║
# ║  "Životni Trak + Dugini Most osnova"                         ║
# ╚═══════════════════════════════════════════════════════════════╝

## DIO 1 / CC-1: ŽIVOTNI TRAK (timeline UI na profilu ljubimca)

### Što gradimo
Kronološki timeline koji agregira SVE što postoji u bazi i prikazuje
na `/pas/<chip>/` stranici. Ovo je temelj za sve ostalo.

### Korak 1.1 — LifeMilestone model (NOVI)
```bash
# OBVEZNO PRVO: provjeri zadnju migraciju
ls /var/www/fina-connect/memio_pet/migrations/ | sort | tail -3
```

Dodaj u `memio_pet/models.py` (na kraj, PRIJE AddAnimalToken):
```python
class LifeMilestone(models.Model):
    """Ručno dodane prekretnice vlasnika — prva šetnja, nagrada, putovanje..."""
    TYPES = [
        ('first_walk',   '🦮 Prva šetnja'),
        ('first_swim',   '🌊 Prvo kupanje'),
        ('first_friend', '🐾 Novi prijatelj'),
        ('award',        '🏆 Nagrada / titula'),
        ('travel',       '✈️ Putovanje'),
        ('training',     '🎓 Dresura uspjeh'),
        ('custom',       '⭐ Prilagođeno'),
    ]
    animal     = models.ForeignKey(
        AnimalProfile, on_delete=models.CASCADE,
        related_name='milestones'
    )
    type       = models.CharField(max_length=20, choices=TYPES, default='custom')
    title      = models.CharField(max_length=200)
    date       = models.DateField()
    photo      = models.ImageField(upload_to='memio_pet/milestones/', null=True, blank=True)
    note       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        db_table  = 'mp_life_milestone'
        ordering  = ['-date']

    def __str__(self):
        return f'{self.animal.name} — {self.get_type_display()} ({self.date})'
```

Kreiraj i apliciraj migraciju:
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations memio_pet
venv/bin/python manage.py migrate --database=memio_pets
venv/bin/python manage.py check
```

### Korak 1.2 — Životni trak funkcija (views.py)
U `memio_pet/views.py`, `pet_profile_page` view, DODAJ u context:
```python
# Pročitaj TOČNA polja PRIJE nego pišeš:
# PetHealthRecord, PetOwnership, LifeMilestone — grep iz models.py

from memio_pet.models import LifeMilestone

# Agregacija životnog traka
timeline = []

# Rođenje
if animal.date_of_birth:
    timeline.append({
        'date': animal.date_of_birth,
        'type': 'rodenje',
        'icon': '🐾',
        'title': f'Rođen/a {animal.name}',
        'source': 'sistem',
    })

# Vlasništva
for own in ownership_chain:
    timeline.append({
        'date': own.acquired_at,
        'type': 'vlasnistvo',
        'icon': '🏠',
        'title': f'Novi dom — {getattr(own, "owner_name", "")}',
        'source': 'sistem',
    })

# Zdravstveni zapisi
for hr in health_records:
    timeline.append({
        'date': hr.datum,
        'type': 'zdravlje',
        'icon': '💉',
        'title': hr.dijagnoza or hr.tretman or 'Vet pregled',
        'note': getattr(hr, 'napomena', ''),
        'source': 'vet',
    })

# Osobne prekretnice
milestones = list(
    LifeMilestone.objects.using(db)
    .filter(animal=animal)
    .order_by('date')
)
for m in milestones:
    timeline.append({
        'date': m.date,
        'type': m.type,
        'icon': m.get_type_display().split(' ')[0],  # emoji
        'title': m.title,
        'note': m.note,
        'photo': m.photo.url if m.photo else None,
        'source': 'vlasnik',
    })

# Sortiraj kronološki
timeline.sort(key=lambda x: x['date'])
context['timeline'] = timeline
context['milestones'] = milestones
```

### Korak 1.3 — Životni trak UI u profile.html
Dodaj ISPOD postojećeg sadržaja profila, IZNAD footera:

```html
{% if timeline %}
<div class="card" style="margin-top:20px">
  <div class="card-body">
    <h2 class="section-title" style="margin-bottom:24px">
      🕰️ Životni trak
    </h2>

    <div class="timeline">
      {% for event in timeline %}
      <div class="tl-item tl-{{ event.type }}">
        <div class="tl-dot">{{ event.icon }}</div>
        <div class="tl-content">
          <div class="tl-date">{{ event.date|date:"d.m.Y." }}</div>
          <div class="tl-title">{{ event.title }}</div>
          {% if event.note %}<div class="tl-note">{{ event.note }}</div>{% endif %}
          {% if event.photo %}
          <img src="{{ event.photo }}" class="tl-photo" alt="{{ event.title }}">
          {% endif %}
        </div>
      </div>
      {% endfor %}
    </div>

    <!-- Dodaj prekretnicu (session auth) -->
    <div style="margin-top:20px;text-align:center">
      <a href="/ljubimac/milestone/novi/?animal={{ identifier }}"
         class="btn-outline" style="font-size:.85rem">
        + Dodaj prekretnicu
      </a>
    </div>
  </div>
</div>
{% endif %}
```

CSS (dodaj u `<style>` blok profile.html):
```css
.timeline{position:relative;padding-left:32px}
.timeline::before{content:'';position:absolute;left:12px;top:0;bottom:0;
  width:2px;background:var(--line)}
.tl-item{position:relative;margin-bottom:20px;display:flex;gap:14px}
.tl-dot{position:absolute;left:-32px;width:26px;height:26px;border-radius:50%;
  background:var(--surface);border:2px solid var(--line);
  display:flex;align-items:center;justify-content:center;font-size:14px;
  flex-shrink:0;z-index:1}
.tl-content{flex:1;padding:10px 14px;background:var(--bg);
  border-radius:10px;border:1px solid var(--line)}
.tl-date{font-size:.72rem;color:var(--dim);letter-spacing:.06em;
  text-transform:uppercase;margin-bottom:3px}
.tl-title{font-weight:500;font-size:.92rem;color:var(--ink)}
.tl-note{font-size:.82rem;color:var(--ink2);margin-top:4px;line-height:1.5}
.tl-photo{width:100%;max-width:200px;border-radius:8px;margin-top:8px;
  object-fit:cover;max-height:120px}
.tl-rodenje .tl-dot{background:rgba(201,168,76,.15);border-color:var(--gold)}
.tl-zdravlje .tl-dot{background:rgba(29,158,117,.1);border-color:var(--green)}
```

### Korak 1.4 — "Dodaj prekretnicu" view + URL + template

URL: `path("ljubimac/milestone/novi/", views.add_milestone, name="add_milestone")`
Nginx: dodaj `location /ljubimac/milestone/` proxy blok

View (session auth — isti mehanizam kao add_animal):
```python
def add_milestone(request):
    db = 'memio_pets'
    # Provjeri session / GET param za animal
    chip = request.GET.get('animal') or request.POST.get('chip')
    animal = _find_animal(chip) if chip else None
    if not animal:
        return redirect('memio_pet:landing')

    if request.method == 'POST':
        m = LifeMilestone.objects.using(db).create(
            animal=animal,
            type=request.POST.get('type','custom'),
            title=request.POST.get('title',''),
            date=request.POST.get('date'),
            note=request.POST.get('note',''),
        )
        if 'photo' in request.FILES:
            m.photo = request.FILES['photo']
            m.save(using=db)
        return redirect('memio_pet:pet_profile', chip_or_tag=chip)

    from memio_pet.models import LifeMilestone as LM
    return render(request, 'memio_pet/add_milestone.html', {
        'animal': animal, 'chip': chip,
        'milestone_types': LM.TYPES,
    })
```

COMMIT: `feat(memio-pet): Životni trak — timeline + LifeMilestone model + add milestone`

---

## DIO 1 / CC-2: DUGINI MOST — MODEL I SIGNAL

### Korak 1.5 — MemorialProfile model
Dodaj u `memio_pet/models.py` (na kraju):
```python
class MemorialProfile(models.Model):
    """Dugini Most — aktivira se automatski kad status = uginulo."""
    animal         = models.OneToOneField(
        AnimalProfile, on_delete=models.CASCADE,
        related_name='memorial'
    )
    epitaph        = models.TextField(blank=True, help_text='Posmrtna poruka vlasnika')
    date_of_death  = models.DateField(null=True, blank=True)
    cause_note     = models.CharField(max_length=200, blank=True)  # nije javno
    cremated       = models.BooleanField(default=False)
    urn_description= models.CharField(max_length=200, blank=True)
    candle_count   = models.PositiveIntegerField(default=0)
    donation_target= models.ForeignKey(
        BreederProfile, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='memorial_donations',
        limit_choices_to={'account_type': 'shelter'}
    )
    total_donated  = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    activated_at   = models.DateTimeField(auto_now_add=True)
    anniversary_notified = models.BooleanField(default=False)

    class Meta:
        app_label = 'memio_pet'
        db_table  = 'mp_memorial_profile'

    def __str__(self):
        return f'Memorijal — {self.animal.name}'
```

### Korak 1.6 — Signal: uginulo → auto memorial

U `memio_pet/signals.py` (provjeri postoji li, ako da — ČITAJ ga cijelog):
```bash
cat /var/www/fina-connect/memio_pet/signals.py
```

Dodaj ili proširi:
```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=AnimalProfile)
def on_animal_status_change(sender, instance, **kwargs):
    """Kad status = uginulo → kreiraj MemorialProfile automatski."""
    if instance.status == 'uginulo':
        db = 'memio_pets'
        memorial, created = MemorialProfile.objects.using(db).get_or_create(
            animal=instance,
            defaults={
                'date_of_death': instance.updated_at.date()
                    if hasattr(instance, 'updated_at') and instance.updated_at
                    else None,
            }
        )
        if created:
            # Pošalji email vlasniku (ako ima email u BreederProfile)
            try:
                from django.core.mail import send_mail
                breeder = instance.breeder
                if breeder and breeder.email:
                    send_mail(
                        subject=f'Memorijal za {instance.name} — Memio.pet',
                        message=(
                            f'Dragi {breeder.name},\n\n'
                            f'Stranica sjećanja za {instance.name} je kreirana:\n'
                            f'https://memio.pet/pas/{instance.chip_number or instance.ear_tag}/\n\n'
                            f'Možete dodati posmrtnu poruku i urediti memorijal.\n\n'
                            f'Naše najdublje sućuti.\n'
                            f'— Memio.pet tim'
                        ),
                        from_email='noreply@memio.pet',
                        recipient_list=[breeder.email],
                        fail_silently=True,
                    )
            except Exception:
                pass  # Nikad ne ruši flow zbog emaila
```

### Korak 1.7 — Migracija + verifikacija
```bash
venv/bin/python manage.py makemigrations memio_pet
venv/bin/python manage.py migrate --database=memio_pets
venv/bin/python manage.py check
```

COMMIT: `feat(memio-pet): MemorialProfile model + signal uginulo→auto-memorial`

---

## DIO 1 / CC-3: UDOMLJAVANJE STRANICA (najmanji effort, najveći impact)

### Korak 1.8 — View + Template
```bash
# PROČITAJ polja PRVO
grep -A 30 "class AnimalProfile" /var/www/fina-connect/memio_pet/models.py | grep "= models\."
```

URL: `path("udomljavanje/", views.udomljavanje_lista, name="udomljavanje")`
Nginx: `location /udomljavanje/` proxy blok

View:
```python
def udomljavanje_lista(request):
    db = 'memio_pets'
    vrsta_filter = request.GET.get('vrsta', '')
    grad_filter = request.GET.get('grad', '')

    qs = AnimalProfile.objects.using(db).filter(
        status='u_azilu'
    ).select_related('breeder').order_by('-created_at')

    if vrsta_filter:
        qs = qs.filter(vrsta=vrsta_filter)
    if grad_filter:
        qs = qs.filter(breeder__city__icontains=grad_filter)

    return render(request, 'memio_pet/udomljavanje.html', {
        'animals': list(qs[:50]),
        'vrsta_filter': vrsta_filter,
        'grad_filter': grad_filter,
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES,
        'page_title': 'Udomljavanje — Memio.pet',
        'total': qs.count(),
    })
```

Template `udomljavanje.html`:
- Hero: "Svaki ljubimac zaslužuje dom."
- Filter forma: vrsta (select) + grad (text) + "Filtriraj"
- Grid kartica: foto (ili placeholder), ime, pasmina, vrsta, azil naziv+grad
- Svaka kartica → link na /pas/CHIP/
- Na profilu ljubimca koji je u_azilu → gumb "Želim udomiti" → mailto azilu ili WhatsApp
- Footer: NO LIMIT udruga | link

COMMIT: `feat(memio-pet): udomljavanje lista — javna stranica za azilske životinje`

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  DIO 2 — MEMORIJAL + KOORDINACIJA (Sat 3–5)                 ║
# ║  "Dugini Most — puni UI + krematorij"                       ║
# ╚═══════════════════════════════════════════════════════════════╝

## DIO 2 / CC-1: DUGINI MOST — VIZUALNI TRANSFORMACIJA PROFILA

### Korak 2.1 — Memorijalni profil stranica
Kada `animal.status == 'uginulo'`, `pet_profile_page` view:
```python
# Dodaj u context:
is_memorial = (animal.status == 'uginulo')
try:
    memorial = MemorialProfile.objects.using(db).get(animal=animal)
except MemorialProfile.DoesNotExist:
    memorial = None
context['is_memorial'] = is_memorial
context['memorial'] = memorial
```

U `profile.html` — conditional CSS na `<html>` tagu:
```html
<html lang="hr" data-theme="{% if is_memorial %}memorial{% else %}light{% endif %}">
```

Memorial CSS tema (dodaj u style blok):
```css
[data-theme="memorial"] {
  --bg: #0f0e0c;
  --surface: #1a1814;
  --ink: #e8e0d0;
  --ink2: #a09080;
  --gold: #e8c46a;
  --line: #2a2520;
  --dim: #6a6058;
}

[data-theme="memorial"] body::before {
  content: '';
  position: fixed;
  inset: 0;
  background: radial-gradient(
    ellipse 60% 40% at 50% 20%,
    rgba(232,196,106,.04) 0%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 0;
}
```

### Korak 2.2 — Memorial header na profilu
Ako `is_memorial`, prikaži UMJESTO normalnog headera:
```html
{% if is_memorial %}
<div class="memorial-header" style="
  text-align:center;padding:40px 20px 24px;
  border-bottom:1px solid var(--line)">

  <!-- Plutajuće svjetlosne čestice -->
  <div id="particles" style="position:absolute;inset:0;pointer-events:none;overflow:hidden"></div>

  <div style="font-size:2.5rem;margin-bottom:12px">🌈</div>
  <h1 style="font-family:var(--serif);font-size:2rem;font-weight:700;margin-bottom:6px">
    U sjećanju
  </h1>
  <p style="font-size:1.1rem;color:var(--gold);font-family:var(--serif);font-style:italic">
    {{ animal.name }}
    {% if animal.date_of_birth %} ({{ animal.date_of_birth|date:"Y." }}–{% endif %}
    {% if memorial.date_of_death %}{{ memorial.date_of_death|date:"Y." }}){% endif %}
  </p>

  {% if memorial.epitaph %}
  <blockquote style="
    margin:20px auto 0;max-width:400px;
    font-family:var(--serif);font-size:1.05rem;font-style:italic;
    color:var(--ink2);line-height:1.8;
    border-left:3px solid var(--gold);padding-left:16px;text-align:left">
    "{{ memorial.epitaph }}"
  </blockquote>
  {% endif %}

  <!-- Upali svjećicu -->
  <button id="candle-btn" onclick="paliSvjecicu()"
    style="margin-top:20px;background:none;border:1px solid rgba(232,196,106,.4);
    border-radius:20px;padding:10px 24px;color:var(--gold);cursor:pointer;
    font-family:var(--sans);font-size:.9rem;transition:all .2s">
    🕯️ Upali svjećicu
    <span id="candle-count">({{ memorial.candle_count }})</span>
  </button>
</div>

<script>
function paliSvjecicu() {
  const btn = document.getElementById('candle-btn');
  const count = document.getElementById('candle-count');
  btn.disabled = true;
  btn.style.opacity = '.5';
  fetch('/api/memorial/{{ animal.chip_number|default:animal.ear_tag }}/candle/', {
    method: 'POST',
    headers: {'X-CSRFToken': '{{ csrf_token }}'}
  }).then(r => r.json()).then(d => {
    btn.innerHTML = '🕯️ Svjećica upaljena (' + d.total + ')';
    btn.style.opacity = '1';
    spawnCandle();
  });
}
function spawnCandle() {
  const p = document.getElementById('particles');
  if (!p) return;
  for (let i = 0; i < 5; i++) {
    const c = document.createElement('div');
    c.style.cssText = `position:absolute;width:4px;height:4px;border-radius:50%;
      background:rgba(232,196,106,${Math.random()*.8+.2});
      left:${Math.random()*100}%;top:${Math.random()*100}%;
      animation:float-up ${Math.random()*3+2}s ease-out forwards`;
    p.appendChild(c);
    setTimeout(() => c.remove(), 5000);
  }
}
</script>
<style>
@keyframes float-up {
  0% { transform:translateY(0) scale(1); opacity:1; }
  100% { transform:translateY(-120px) scale(0); opacity:0; }
}
</style>
{% endif %}
```

### Korak 2.3 — Memorial API endpoint

URL: `path("api/memorial/<str:chip_or_tag>/candle/", views.memorial_candle_api)`

```python
from django.views.decorators.http import require_POST
from django.http import JsonResponse

@require_POST
def memorial_candle_api(request, chip_or_tag):
    db = 'memio_pets'
    animal = _find_animal(chip_or_tag)
    if not animal or animal.status != 'uginulo':
        return JsonResponse({'error': 'not found'}, status=404)
    try:
        memorial = MemorialProfile.objects.using(db).get(animal=animal)
        memorial.candle_count += 1
        memorial.save(using=db, update_fields=['candle_count'])
        return JsonResponse({'total': memorial.candle_count})
    except MemorialProfile.DoesNotExist:
        return JsonResponse({'error': 'no memorial'}, status=404)
```

Nginx: `location /api/memorial/` proxy

### Korak 2.4 — "Uredi memorijal" forma (session auth)

URL: `path("memorijal/<str:chip_or_tag>/uredi/", views.memorial_edit)`

Prikazuje se samo ako breeder session odgovara vlasniku:
- Polje za epitaf (textarea, max 500 znakova)
- Datum smrti (date picker)
- Odabir azila za donacije (select, filter account_type='shelter')
- Submit → save MemorialProfile

COMMIT: `feat(memio-pet): Dugini Most — memorial UI, svjećica API, uredi forma`

---

## DIO 2 / CC-2: "ŠTO SADA?" — KOORDINACIJSKI WIZARD

### Korak 2.5 — Krematorij account_type

Dodaj 'krematorij' u BreederProfile account_type choices:
```python
# ČITAJ PRVO:
grep -A 20 "ACCOUNT_TYPE" /var/www/fina-connect/memio_pet/models.py
```

Dodaj u listu:
```python
('krematorij', '⚱️ Krematorij'),
```

### Korak 2.6 — Krematorij direktorij

URL: `path("krematoriji/", views.krematoriji_lista, name="krematoriji")`

View:
```python
def krematoriji_lista(request):
    db = 'memio_pets'
    grad = request.GET.get('grad', '')
    qs = BreederProfile.objects.using(db).filter(
        account_type='krematorij'
    ).order_by('city', 'name')
    if grad:
        qs = qs.filter(city__icontains=grad)

    return render(request, 'memio_pet/krematoriji.html', {
        'krematoriji': list(qs),
        'grad_filter': grad,
        'page_title': 'Krematoriji za kućne ljubimce — Memio.pet',
    })
```

Template: listing kartica s imenom, gradom, kontaktom.
Seed: Pet4ever (Varaždin) kao prvi unos. Unesi ručno kroz shell.

### Korak 2.7 — "Što sada?" sekcija na memorijalu

Dodaj na memorijalni profil ispod epitafa, AKO nema MemorialProfile.cremated:
```html
{% if is_memorial and not memorial.cremated %}
<div class="card" style="margin-top:16px;border:1px solid rgba(232,196,106,.25)">
  <div class="card-body">
    <h3 style="font-family:var(--serif);font-size:1.2rem;margin-bottom:16px">
      Što sada?
    </h3>
    <div style="display:flex;flex-direction:column;gap:10px">
      <a href="/krematoriji/" class="what-now-btn">
        ⚱️ Krematorij — pronađi u blizini
      </a>
      <a href="https://e-uprava.gov.hr" target="_blank" class="what-now-btn">
        📋 Odjava iz Upisnika (zakonska obveza — 14 dana)
      </a>
      <a href="/memorijal/{{ identifier }}/uredi/" class="what-now-btn">
        ✏️ Uredi stranicu sjećanja
      </a>
      <a href="/udomljavanje/" class="what-now-btn">
        🐾 Pomozi drugom ljubimcu
      </a>
    </div>
    <p style="font-size:.75rem;color:var(--dim);margin-top:12px;line-height:1.6">
      Zakon o veterinarstvu (NN 82/13) — vlasnik je obvezan odjaviti
      ljubimca iz Upisnika u roku 14 dana od uginuća.
    </p>
  </div>
</div>
{% endif %}
```

### Korak 2.8 — Odjava podsjetnik (Celery task)

U `memio_pet/tasks.py` (provjeri postoji li):
```python
from celery import shared_task

@shared_task
def send_odjava_reminder(animal_pk):
    """Šalje podsjetnik za zakonsku odjavu — 10 dana nakon uginuća."""
    try:
        from memio_pet.models import AnimalProfile
        animal = AnimalProfile.objects.using('memio_pets').get(pk=animal_pk)
        if animal.status != 'uginulo':
            return  # Ne treba više

        breeder = animal.breeder
        if not breeder or not breeder.email:
            return

        from django.core.mail import send_mail
        send_mail(
            subject=f'Podsjetnik — odjava {animal.name} iz Upisnika',
            message=(
                f'Dragi {breeder.name},\n\n'
                f'Podsjećamo da ste zakonski obvezni odjaviti {animal.name} '
                f'iz Upisnika kućnih ljubimaca u roku 14 dana od uginuća.\n\n'
                f'Odjava: https://e-uprava.gov.hr\n\n'
                f'Memorijal {animal.name}: '
                f'https://memio.pet/pas/{animal.chip_number or animal.ear_tag}/\n\n'
                f'S poštovanjem,\nMemio.pet tim'
            ),
            from_email='noreply@memio.pet',
            recipient_list=[breeder.email],
            fail_silently=True,
        )
    except Exception:
        pass
```

U signalu `on_animal_status_change`, kad se kreira memorial:
```python
# Zakaži podsjetnik za 10 dana
from memio_pet.tasks import send_odjava_reminder
send_odjava_reminder.apply_async(
    args=[str(instance.pk)],
    countdown=10 * 24 * 3600  # 10 dana u sekundama
)
```

COMMIT: `feat(memio-pet): koordinacijski wizard — krematoriji, odjava, što-sada`

---

## DIO 2 / CC-3: SOCIAL IMPORT UI + OPG→AZIL MATCH

### Korak 2.9 — Social Import wizard UI

Backend postoji: `boxgram/services/social_import.py` + `views_social.py`
Treba: UI na memio.pet profilu ljubimca

Na `profile.html`, dodaj gumb u životni trak sekciju:
```html
<a href="/boxgram/import/?animal={{ identifier }}"
   class="btn-outline" style="font-size:.85rem">
  📱 Uvezi s društvenih mreža
</a>
```

Nova stranica `/boxgram/import/`:
PROČITAJ `boxgram/views_social.py` CIJELOG PRIJE PISANJA:
```bash
cat /var/www/fina-connect/boxgram/views_social.py
```

Kreiraj jednostavan 3-korak wizard:
- Korak 1: Unesi link (FB post, IG post, TikTok, YT video)
- Korak 2: Preview (oEmbed thumbnail + tekst) — backend radi!
- Korak 3: Potvrdi → LifeEvent kreira, pojavljuje se na timeline-u

Session auth: provjeri da je `request.session.get('memio_breeder_pk')` vlasnik animala.

### Korak 2.10 — OPG→Azil match na BARF marketplaceu

U `barf_listings.html` i na azil dashboardu dodaj:

Na BARF listingu — nova oznaka:
```html
{% if listing.donates_to_shelters %}
<span style="background:rgba(76,175,125,.15);color:var(--green);
  font-size:.7rem;padding:3px 10px;border-radius:20px;font-weight:600">
  🐾 Donira azilima
</span>
{% endif %}
```

U `RawFoodListing` modelu — dodaj polje:
```python
donates_to_shelters = models.BooleanField(
    default=False,
    help_text='Ponuđač donira azilima po povlaštenoj cijeni ili besplatno'
)
shelter_radius_km = models.PositiveIntegerField(
    default=50,
    help_text='Radius isporuke za azile (km)'
)
```

Azil dashboard sekcija "Dostupna hrana":
```python
# U azil dashboard viewu:
from memio_pet.models import RawFoodListing
azil_hrana = RawFoodListing.objects.using('memio_pets').filter(
    status='available',
    donates_to_shelters=True,
).order_by('-created_at')[:10]
```

COMMIT: `feat(memio-pet): social import UI wizard + OPG→azil match`

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  DIO 3 — MONETIZACIJA + POLISH (Sat 5–7)                   ║
# ║  "Knjiga sjećanja + Pet Hotel + Donacije + QA"              ║
# ╚═══════════════════════════════════════════════════════════════╝

## DIO 3 / CC-1: PDF "KNJIGA SJEĆANJA" (direktan prihod)

### Korak 3.1 — PDF generiranje

PROČITAJ SKILL za PDF PRVO:
```bash
cat /mnt/skills/public/pdf/SKILL.md
```

URL: `path("pas/<str:chip_or_tag>/knjiga/", views.knjiga_sjecanja_pdf)`

View:
```python
def knjiga_sjecanja_pdf(request, chip_or_tag):
    db = 'memio_pets'
    animal = _find_animal(chip_or_tag)
    if not animal:
        return redirect('memio_pet:landing')

    # Dohvati sve podatke
    health_records = list(PetHealthRecord.objects.using(db).filter(animal=animal).order_by('datum'))
    ownership_chain = list(PetOwnership.objects.using(db).filter(animal=animal).order_by('acquired_at'))
    milestones = list(LifeMilestone.objects.using(db).filter(animal=animal).order_by('date'))
    try:
        memorial = MemorialProfile.objects.using(db).get(animal=animal)
    except:
        memorial = None

    context = {
        'animal': animal,
        'health_records': health_records,
        'ownership_chain': ownership_chain,
        'milestones': milestones,
        'memorial': memorial,
        'generated_at': timezone.now(),
    }

    # Generiraj PDF s WeasyPrint
    import weasyprint
    from django.template.loader import render_to_string
    html_string = render_to_string('memio_pet/knjiga_pdf.html', context, request=request)
    pdf = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    safe_name = (animal.name or 'ljubimac').replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="memio-{safe_name}-knjiga.pdf"'
    return response
```

Template `knjiga_pdf.html` (PDF dizajn — BEZ CSS varijabli, inline boje):
- Naslovna: velika fotografija, ime, godine
- Stranica 1: Životni podaci (vrsta, pasmina, čip, datum rodjenja)
- Stranica 2+: Životni trak — kronološki, svaki event s datumom
- Galerija: sve fotografije iz milestones
- Epilog (ako memorial): epitaf, datum
- Footer svake stranice: memio.pet logotip + URL profila

### Korak 3.2 — Gumb na profilu i memorijalu

Na `profile.html` dodaj:
```html
<a href="/pas/{{ identifier }}/knjiga/"
   class="share-btn" target="_blank">
  📖 Knjiga sjećanja (PDF)
</a>
```

COMMIT: `feat(memio-pet): PDF Knjiga sjećanja — WeasyPrint generiranje`

---

## DIO 3 / CC-2: PET HOTEL NA MEMIO.PET + DONACIJE

### Korak 3.3 — Pet Hotel direktorij na memio.pet

Postoji: `PetBoardingReservation` model + `/hotel/` view.
Problem: extends LIMIT Connect base.html, nije na memio.pet vizualu.

Provjeri:
```bash
cat /var/www/fina-connect/templates/memio_pet/pet_hotel_booking.html | head -20
grep "extends\|base" /var/www/fina-connect/templates/memio_pet/pet_hotel_booking.html
```

Ako koristi LIMIT Connect base → zamijeni s memio.pet CSS-om.

Dodaj hoteli direktorij na `/hoteli/` (odvojen od bookinga):
```python
def hoteli_lista(request):
    db = 'memio_pets'
    grad = request.GET.get('grad', '')
    hoteli = BreederProfile.objects.using(db).filter(
        account_type='hotel'
    ).order_by('city', 'name')
    if grad:
        hoteli = hoteli.filter(city__icontains=grad)
    return render(request, 'memio_pet/hoteli_lista.html', {
        'hoteli': list(hoteli),
        'page_title': 'Pet Hoteli — Memio.pet',
    })
```

URL: `path("hoteli/", views.hoteli_lista, name="hoteli_lista")`
Nginx: `location /hoteli/` proxy

### Korak 3.4 — Donacije mehanizam (NO PROFIT, samo routing)

memio.pet NE naplaćuje donacije — samo spaja vlasnika s azilom.

Na memorijalu:
```html
{% if memorial.donation_target %}
<div class="card" style="margin-top:16px;border:1px solid rgba(76,175,125,.2)">
  <div class="card-body" style="text-align:center">
    <p style="font-size:.9rem;color:var(--ink2);margin-bottom:12px">
      U ime {{ animal.name }}, vlasnik predlaže donaciju azilu
      <strong>{{ memorial.donation_target.name }}</strong>
    </p>
    {% if memorial.donation_target.website %}
    <a href="{{ memorial.donation_target.website }}" target="_blank"
       class="btn-gold" style="text-decoration:none">
      🐾 Doniraj azilu
    </a>
    {% elif memorial.donation_target.email %}
    <a href="mailto:{{ memorial.donation_target.email }}"
       class="btn-gold" style="text-decoration:none">
      ✉️ Kontaktiraj azil
    </a>
    {% endif %}
  </div>
</div>
{% endif %}
```

COMMIT: `feat(memio-pet): pet hotel direktorij + donacije routing na memorijalu`

---

## DIO 3 / GEMINI: QA + VERIFIKACIJA SVEGA

### Korak 3.5 — Full HTTP audit svih novih ruta

```bash
for url in \
  "https://memio.pet/udomljavanje/" \
  "https://memio.pet/krematoriji/" \
  "https://memio.pet/hoteli/" \
  "https://memio.pet/pas/191031000312345/" \
  "https://memio.pet/ljubimac/milestone/novi/?animal=191031000312345"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url")
  echo "$code $url"
done
# Sve mora biti 200 ili 302 (ne 404, ne 500)
```

### Korak 3.6 — Test Dugini Most signala

```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from memio_pet.models import AnimalProfile, MemorialProfile
# Test: promijeni status Vučka na uginulo
animal = AnimalProfile.objects.using('memio_pets').get(chip_number='191031000312345')
print('Status prije:', animal.status)
# NE RADI OVO U PRODUKCIJI — samo u test env!
# animal.status = 'uginulo'
# animal.save(using='memio_pets')
# Provjeri postoji li signal registriran
from django.db.models.signals import post_save
receivers = post_save.receivers
print('Signal receiveri:', len(receivers))
" 2>&1 | grep -v "Warning\|urllib3\|chardet"
```

### Korak 3.7 — Nema zabranjenih linkova (obvezna provjera)

```bash
grep -rn "limit-connect.com/hr/register\|no-limit.world\|/pricing" \
  /var/www/fina-connect/templates/memio_pet/ \
  /var/www/memio-pet/index.html
# Mora biti PRAZNO
```

### Korak 3.8 — FINAL_QA_ZIVOTNI_CIKLUS.md

Format:
```
| Stavka | HTTP | Signal | UI | Pravno | Status |
```

---

## DIO 3 / SONNET: FENIX_STATUS + LANDING PAGE UPDATE

### Korak 3.9 — memio.pet landing update

Dodaj u index.html nove sekcije (ispod BARF, iznad Azil):

**Udomljavanje sekcija:**
```html
<section>
  <div class="container">
    <span class="tag">Udomljavanje</span>
    <h2>Svaki ljubimac zaslužuje dom.</h2>
    <p class="lead">Životinje u azilima čekaju. Pronađi svog novog prijatelja.</p>
    <a href="/udomljavanje/" class="btn-gold" style="...">
      Pogledaj ljubimce →
    </a>
  </div>
</section>
```

**Dugini Most sekcija:**
```html
<section class="bg-dark-section">
  <div class="container">
    <span class="tag">Sjećanja</span>
    <h2>Svaki trenutak — zauvijek.</h2>
    <p class="lead">
      Digitalni profil tvog ljubimca ne nestaje.
      Transformira se u memorijal koji ostaje — za tebe, za tvoju obitelj, zauvijek.
    </p>
    <a href="/pas/191031000312345/" style="...">
      Pogledaj primjer memorijala →
    </a>
  </div>
</section>
```

---

## NGINX — NOVE RUTE (sve odjednom)

Dodaj u `/etc/nginx/sites-enabled/memio-pet`:
```nginx
location /udomljavanje/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /krematoriji/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /hoteli/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /memorijal/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /api/memorial/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Nakon svakog dodavanja: `nginx -t && systemctl reload nginx`

---

## COMMITI SUMMARY (12 commitova ukupno)

Dio 1:
  1. `feat(memio-pet): LifeMilestone model + migracija`
  2. `feat(memio-pet): Životni trak — timeline UI na profilu`
  3. `feat(memio-pet): add_milestone view + template`
  4. `feat(memio-pet): MemorialProfile model + signal uginulo`
  5. `feat(memio-pet): udomljavanje lista`

Dio 2:
  6. `feat(memio-pet): Dugini Most — memorial UI + svjećica API`
  7. `feat(memio-pet): uredi memorijal + što-sada coordinator`
  8. `feat(memio-pet): krematorij direktorij + Celery odjava`
  9. `feat(memio-pet): social import UI wizard`
  10. `feat(memio-pet): OPG→azil match`

Dio 3:
  11. `feat(memio-pet): PDF Knjiga sjećanja`
  12. `feat(memio-pet): hoteli lista + donacije routing + landing update`

---

## CILJANE OCJENE (po završetku)

  memio.pet journey:        9/10  → 9.5/10
  memio.pet UX/VAU:         8/10  → 10/10   ← Dugini Most je 10
  Životni ciklus pokrivenost: 0%  → 95%
  Monetizacija:              0€   → PDF 9.90€/kom, hoteli 12%, krematoriji 15%
  Pravna usklađenost:        5/10 → 8/10 (cookie/OUK CC-LEGAL task)

## UKUPNA OCJENA SUSTAVA NAKON: 9.5/10
