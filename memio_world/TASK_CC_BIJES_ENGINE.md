# TASK ZA CLAUDE CODE: Rage Engine — Upravljanje bijesom

## KONTEKST
PLAY.EU je dječja edukativna platforma (Django app: memio_world, baza: memio_world).
Svi modeli koriste .using("memio_world"). UUID primary keys. Nema FK na auth_user.
Projekt je na /var/www/fina-connect, venv u /var/www/fina-connect/venv.
Gunicorn: sudo systemctl restart gunicorn-fina

## PROČITAJ PLAN
Pročitaj: memio_world/PLAN_BIJES_ENGINE.md — sadrži kompletnu pedagošku strategiju.

## ŠTO TREBAŠ NAPRAVITI

### 1. Model: EmotionCheckIn (u comfort_models.py)
```python
class EmotionCheckIn(models.Model):
    """Dnevni check-in emocija djeteta — Rage Engine."""
    EMOTION_CHOICES = [
        ('furious', 'Jako ljut 😡'),
        ('angry', 'Ljut 😤'),
        ('frustrated', 'Frustriran 😣'),
        ('neutral', 'Ok 😐'),
        ('happy', 'Veseo 🙂'),
        ('very_happy', 'Jako veseo 😊'),
        ('ecstatic', 'Presretan 😄'),
    ]
    TRIGGER_CHOICES = [
        ('sibling', 'Svađa s bratom/sestrom'),
        ('school', 'Škola / zadaća'),
        ('friend', 'Prijatelj'),
        ('tired', 'Umor'),
        ('hungry', 'Glad'),
        ('unfair', 'Nepravda'),
        ('lost_game', 'Izgubio igru'),
        ('other', 'Nešto drugo'),
    ]
    ACTION_CHOICES = [
        ('breathing', 'Disao/la'),
        ('counting', 'Brojao/la do 10'),
        ('walked_away', 'Odšetao/la se'),
        ('talked', 'Pričao/la'),
        ('cried', 'Plakao/la'),
        ('yelled', 'Vikao/la'),
        ('hit', 'Udario/la'),
        ('pillow', 'Stisnuo/la jastuk'),
        ('drew', 'Nacrtao/la bijes'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey('memio_world.ChildProfile', on_delete=models.CASCADE, related_name='emotion_checkins')
    emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES)
    trigger = models.CharField(max_length=30, choices=TRIGGER_CHOICES, blank=True)
    action_taken = models.CharField(max_length=30, choices=ACTION_CHOICES, blank=True)
    reflection_text = models.TextField(blank=True)
    reflection_audio = models.FileField(upload_to='play_eu/emotions/', blank=True)
    calming_technique_used = models.CharField(max_length=30, blank=True)
    felt_better_after = models.BooleanField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)

    class Meta:
        app_label = 'memio_world'
        db_table = 'play_emotion_checkin'
        ordering = ['-created_at']
```

### 2. Model: CalmingExercise (u comfort_models.py)
```python
class CalmingExercise(models.Model):
    """Tehnika smirivanja — disanje, brojanje, vizualizacija."""
    TECHNIQUE_CHOICES = [
        ('breathing', 'Duboko disanje'),
        ('counting', 'Brojanje unatrag'),
        ('volcano', 'Vulkan vježba'),
        ('balloon', 'Balon se napuhuje'),
        ('jellyfish', 'Meduza plutanje'),
        ('turtle', 'Kornjačina ljuska'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technique = models.CharField(max_length=30, choices=TECHNIQUE_CHOICES)
    title = models.CharField(max_length=200)
    title_de = models.CharField(max_length=200, blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    instruction_text = models.TextField()
    instruction_text_de = models.TextField(blank=True)
    instruction_text_en = models.TextField(blank=True)
    grandma_voice = models.TextField(blank=True, help_text="Bakine riječi za ovu vježbu")
    duration_seconds = models.PositiveSmallIntegerField(default=60)
    animation_data = models.JSONField(default=dict, blank=True, help_text="CSS animation config")
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=12)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_world'
        db_table = 'play_calming_exercise'
```

### 3. Migracija
Kreiraj migraciju: 0013_rage_engine_emotion_calming.py

### 4. View: emotion_checkin (u views_play.py)
- GET: prikaži semafor emocija
- POST: spremi check-in, ako je furious/angry → redirect na calming exercise
- URL: play/emotions/ (name='emotion_checkin')

### 5. View: calming_exercise (u views_play.py)
- Prikaži animiranu vježbu disanja
- URL: play/calm/<technique>/ (name='calming_exercise')

### 6. Template: emotion_checkin.html
- Lijepi emoji gumbi u krugu
- "Kako se danas osjećaš?" naslov (Uncial Antiqua font)
- Kad odabere ljut → fade in trigger pitanje → fade in calming vježba
- Animirani balon koji se napuhuje (CSS animation)
- Bakin glas (TTS): "Dušo, sve će biti dobro. Hajde da zajedno dišemo."

### 7. Template: calming_exercise.html
- Puni ekran, topla boja (#FFF8E7)
- Animirani balon/vulkan (CSS keyframes)
- Brojač udaha (4 sec udah, 4 sec izdah)
- "Udahni... 1... 2... 3... 4... Izdahni... 1... 2... 3... 4..."
- Bakin glas TTS
- Na kraju: "Osjećaš li se bolje?" [Da] [Još jednom]

### 8. Seed: 6 vježbi smirivanja
- Duboko disanje (balon animacija)
- Brojanje unatrag od 10
- Vulkan vježba (lava se hladi)
- Meduza plutanje (opusti svaki mišić)
- Kornjačina ljuska (uvuci se, dišemo, izađi)
- Semafor (crveno STOJ, žuto DIŠI, zeleno IDI)

### 9. Seed: 3 bajke o bijesu (ParallelStory)
Kreiraj 3 nove priče (HR/DE/EN tekst, 15+ paragrafa svaka):
1. "Zmaj koji je naučio disati" (slug: zmaj-koji-je-naucio-disati)
2. "Kraljević koji je vikao" (slug: kraljevic-koji-je-vikao)
3. "Baka i čarobna kutija" (slug: baka-i-carobna-kutija)
story_type='fairy_tale', source='original', is_published=True

### 10. Dodaj u navigaciju
U base_play.html bottom nav ili u play_home.html — dodaj link na emotion_checkin

### 11. URL routing
Dodaj u memio_world/urls.py:
- path('play/emotions/', views_play.emotion_checkin, name='emotion_checkin'),
- path('play/calm/<str:technique>/', views_play.calming_exercise, name='calming_exercise'),

## PRAVILA
- Svi upiti na bazu: .using('memio_world')
- UUID PK na svim modelima
- Nema FK na auth_user (memio_world je odvojena baza)
- Template koristi base_play.html
- Font: MedievalSharp za tekst, Uncial Antiqua za naslove
- Boje: var(--parchment), var(--gold), var(--ink)
- Restart: sudo systemctl restart gunicorn-fina
- Log: /var/log/fina-connect/

## DISCLAIMER
Na SVAKOM ekranu koji se tiče emocija:
"Ova platforma ne zamjenjuje stručnu pomoć. Ako primjećujete ponavljajuće
ili intenzivne ispade bijesa, razgovarajte s pedijatrom ili dječjim psihologom."
