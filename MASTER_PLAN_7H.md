# ═══════════════════════════════════════════════════════════════════
# FENIX MASTER PLAN — 7 SATI, 5 AGENATA, SVE PARALELNO
# Datum: 07.04.2026. | Koordinator: Sonnet | Ekipa: CC(1) CC(2) CC(3) Gemini Ivan
# Cilj: Priča od 7 dana → gotovo za 7 sati
# ═══════════════════════════════════════════════════════════════════

## STANJE POLAZIŠTA (07.04. 09:00)

### Server: ✅ sve aktivno | disk 39% | RAM 4.9/7.6GB
### Django: 0 errors | git HEAD: f484de93
### Go-live: 15.04.2026. | Marija dry-run: 08.04.2026.

### Ocjene sad:
  LIMIT Connect backend:    8.5/10
  LIMIT Connect UI/UX:      8.0/10
  memio.pet journey:        3/10  ← KRITIČNO (forme puknute)
  memio.pet UX/VAU:         5/10  ← ljubimac govori (demo gotov, ne deployano)
  memio.world:              4/10
  NO LIMIT / azil:          5/10
  Sigurnost:                7/10  ← magic token nije implementiran

### Cilj za 16:00:
  LIMIT Connect:            9.5/10
  memio.pet journey:        9/10
  memio.pet UX/VAU:         9/10
  memio.world:              7/10
  NO LIMIT / azil:          8/10
  Sigurnost:                9/10

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  AGENT CC-1 — memio.pet JOURNEY + SIGURNOST                  ║
# ║  Task fajl: CC_TASK_MEMIO_JOURNEY_FIX.md                     ║
# ║  Prioritet: 🔴 KRITIČNO — sve ostalo blokira ovo             ║
# ╚═══════════════════════════════════════════════════════════════╝

## CC-1 / FAZA 1 (sat 1-2): JOURNEY FIX

### M1.1 — Session auth za add_animal (BLOKER)
PROČITAJ PRVO:
```bash
grep -A 80 "class AnimalProfile" /var/www/fina-connect/memio_pet/models.py | grep "= models\."
grep -A 30 "def registracija" /var/www/fina-connect/memio_pet/views.py
```

U `views.py` → `registracija()`, nakon `bp = BreederProfile.objects.using(db).create(...)`:
```python
request.session['memio_breeder_pk'] = str(bp.pk)
request.session['memio_breeder_email'] = bp.email
request.session.set_expiry(86400 * 7)
```

### M1.2 — add_animal view (čisti, bez @login_required)
```python
def add_animal(request):
    db = 'memio_pets'
    breeder_pk = (request.session.get('memio_breeder_pk') or
                  request.GET.get('breeder') or
                  request.POST.get('breeder_id'))
    if not breeder_pk:
        return render(request, 'memio_pet/add_animal_auth.html', {
            'page_title': 'Tko si ti?'
        })
    try:
        import uuid as _u
        breeder = BreederProfile.objects.using(db).get(pk=_u.UUID(str(breeder_pk)))
    except Exception:
        return redirect('memio_pet:registracija')

    if request.method == 'POST':
        # ČITAJ PRAVA POLJA IZ MODELA GORE
        name = request.POST.get('name','').strip()
        vrsta = request.POST.get('vrsta','pas')
        breed = request.POST.get('breed','').strip()
        chip = request.POST.get('chip_number','').strip()
        ear_tag = request.POST.get('ear_tag','').strip()
        spol = request.POST.get('spol','N')
        dob = request.POST.get('date_of_birth') or None
        notes = request.POST.get('notes','').strip()

        if not name:
            return render(request, 'memio_pet/add_animal.html', {
                'breeder': breeder, 'breeder_id': str(breeder.pk),
                'error': 'Ime ljubimca je obavezno.'
            })

        import uuid as _u2
        if not chip and not ear_tag:
            ear_tag = f"{vrsta}-{_u2.uuid4().hex[:8]}"

        animal = AnimalProfile(
            name=name, vrsta=vrsta, breed=breed,
            chip_number=chip, ear_tag=ear_tag, spol=spol,
            date_of_birth=dob, notes=notes,
            breeder=breeder, breeder_name_snapshot=breeder.name,
            status='aktivno',
        )
        if 'photo' in request.FILES:
            animal.photo = request.FILES['photo']
        animal.save(using=db)

        request.session['memio_breeder_pk'] = str(breeder.pk)
        identifier = animal.chip_number or animal.ear_tag
        messages.success(request, f'{name} je dodan!')
        return redirect('memio_pet:pet_profile', chip_or_tag=identifier)

    return render(request, 'memio_pet/add_animal.html', {
        'breeder': breeder,
        'breeder_id': str(breeder.pk),
        'page_title': f'Dodaj ljubimca — {breeder.name}',
    })
```

### M1.3 — URLs (dodaj u urls.py)
```python
path("ljubimac/novi/", views.add_animal, name="add_animal"),
path("ljubimac/zatrazi/", views.add_animal, name="add_animal_zatrazi"),
```

### M1.4 — add_animal.html template
Dizajn: isti CSS kao breeder.html (--gold, --ink, --serif, --bg)
Sadržaj:
- Header: "Dodaješ ljubimca za: [breeder.name]" + link natrag na profil
- Forma fields: ime*, vrsta (select: pas/mačka/konj/ptica/zec/ostalo), pasmina,
  čip broj (placeholder: "opcijsko - ako ga nema, preskočite"),
  spol (radio: m/ž/nepoznato), datum rodjenja (date picker), foto upload, napomene
- Hidden: `<input type="hidden" name="breeder_id" value="{{ breeder_id }}">`
- Submit: "Dodaj ljubimca 🐾"
- ZABRANA: nikakav href na limit-connect.com/hr/ bilo što

### M1.5 — add_animal_auth.html (kad nema sessiona)
Jednostavna stranica: "Upiši email koji si koristio pri registraciji"
Email input + submit → GET params search u BreederProfile
Ako pronađen → spremi u session → redirect na add_animal
NIJE magic token (to je faza 2) — samo email lookup

### M1.6 — LINK AUDIT (obavezan korak, ne preskočiti)
```bash
# Mora vratiti 0 rezultata:
grep -rn "limit-connect.com/hr/register\|limit-connect.com/hr/login\|limit-connect.com/pricing\|no-limit.world\|/paketi" \
  /var/www/fina-connect/templates/memio_pet/ \
  /var/www/memio-pet/index.html
echo "MORA BITI PRAZAN OUTPUT GORE"

# HTTP status svih ruta:
for url in \
  "https://memio.pet/ljubimac/novi/" \
  "https://memio.pet/ljubimac/zatrazi/" \
  "https://memio.pet/registracija/" \
  "https://memio.pet/pas/191031000312345/"; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 $url) $url"
done
# SVE mora biti 200
```

COMMIT: `fix(memio-pet): journey fix — session auth, add_animal, link audit`

---

## CC-1 / FAZA 2 (sat 2-3): VAU FEATURE — LJUBIMAC GOVORI S PRAVOM SLIKOM

### M2.1 — PIN setup page: ljubimac govori
Lokacija: `templates/accounts/trikey_login.html` i `templates/registration/trikey_register.html`

PROČITAJ PRVO:
```bash
cat /var/www/fina-connect/templates/accounts/trikey_login.html | head -100
grep -n "pin\|PIN\|submit\|form" /var/www/fina-connect/templates/registration/trikey_register.html | head -20
```

Implementiraj JavaScript+HTML widget koji Sonnet je demonstrirao:

**Backend: dohvati sliku ljubimca za ulogiranog usera**
U PIN setup viewu, dodaj context:
```python
# U trikey_views.py → pin_setup view:
pet_photo = None
pet_name = 'tvoj ljubimac'
try:
    from memio_pet.models import AnimalProfile
    animal = AnimalProfile.objects.using('memio_pets').filter(
        breeder__email=request.user.email
    ).order_by('-created_at').first()
    if animal and animal.photo:
        pet_photo = animal.photo.url
        pet_name = animal.name or 'tvoj ljubimac'
    elif animal:
        pet_name = animal.name or 'tvoj ljubimac'
except Exception:
    pass
context['pet_photo'] = pet_photo
context['pet_name'] = pet_name
```

**Frontend: widget u PIN setup templateu**

Dodaj ISPOD PIN input polja, IZNAD submit gumba:

```html
<!-- LJUBIMAC GOVORI — VAU feature -->
<div id="pet-speaks" style="margin:16px 0;display:flex;flex-direction:column;align-items:center;gap:12px">

  <!-- Foto ili SVG fallback -->
  <div id="pet-avatar" style="position:relative;width:80px;height:80px">
    {% if pet_photo %}
    <img id="pet-img"
         src="{{ pet_photo }}"
         alt="{{ pet_name }}"
         style="width:80px;height:80px;border-radius:50%;object-fit:cover;
                border:3px solid #1a1a2e;box-shadow:3px 3px 0 #1a1a2e;
                transition:transform .3s cubic-bezier(.34,1.56,.64,1)">
    {% else %}
    <!-- SVG pas (fallback) -->
    <svg id="pet-img" viewBox="0 0 80 80" width="80" height="80"
         style="filter:drop-shadow(3px 3px 0 #1a1a2e);
                transition:transform .3s cubic-bezier(.34,1.56,.64,1)">
      <ellipse cx="40" cy="52" rx="22" ry="18" fill="#c9a84c"/>
      <ellipse cx="18" cy="24" rx="8" ry="11" fill="#a07830" transform="rotate(-15 18 24)"/>
      <ellipse cx="62" cy="24" rx="8" ry="11" fill="#a07830" transform="rotate(15 62 24)"/>
      <circle cx="40" cy="30" r="18" fill="#c9a84c"/>
      <ellipse cx="40" cy="36" rx="8" ry="6" fill="#e8c46a"/>
      <ellipse id="svgNose" cx="40" cy="33" rx="4" ry="2.8" fill="#3d2b1a"/>
      <circle cx="32" cy="26" r="4" fill="white"/>
      <circle cx="48" cy="26" r="4" fill="white"/>
      <circle id="svgPL" cx="33" cy="26" r="2.5" fill="#2d1a0a"/>
      <circle id="svgPR" cx="49" cy="26" r="2.5" fill="#2d1a0a"/>
      <circle cx="34" cy="25" r="1" fill="white"/>
      <circle cx="50" cy="25" r="1" fill="white"/>
      <path id="svgMouth" d="M36 40 Q40 45 44 40" stroke="#3d2b1a" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path id="svgTail" d="M62 52 Q72 40 68 33" stroke="#a07830" stroke-width="4" fill="none" stroke-linecap="round"/>
    </svg>
    {% endif %}
    <div id="pet-emote" style="position:absolute;top:-4px;right:-4px;width:26px;height:26px;
         border-radius:50%;background:white;border:2px solid #1a1a2e;
         display:flex;align-items:center;justify-content:center;font-size:13px;
         transform:scale(0);opacity:0;transition:all .3s cubic-bezier(.34,1.56,.64,1)">
    </div>
  </div>

  <!-- Speech bubble — comic strip stil -->
  <div id="pet-bubble" style="position:relative;background:white;
       border:2.5px solid #1a1a2e;border-radius:18px;padding:11px 15px;
       max-width:260px;min-height:44px;
       box-shadow:3px 3px 0 #1a1a2e;
       opacity:0;transform:scale(.8) translateY(6px);
       transform-origin:top center;
       transition:opacity .2s,transform .28s cubic-bezier(.34,1.56,.64,1)">
    <div style="position:absolute;top:-13px;left:50%;transform:translateX(-50%);
         width:0;height:0;border-left:9px solid transparent;
         border-right:9px solid transparent;border-bottom:13px solid #1a1a2e"></div>
    <div style="position:absolute;top:-8px;left:50%;transform:translateX(-50%);
         width:0;height:0;border-left:7px solid transparent;
         border-right:7px solid transparent;border-bottom:9px solid white"></div>
    <span id="pet-bubble-text" style="font-size:13px;line-height:1.55;color:#1a1a2e;font-family:system-ui,sans-serif"></span>
    <span id="pet-cursor" style="display:inline-block;width:2px;height:1em;
          background:#1a1a2e;margin-left:2px;vertical-align:middle;
          animation:blink .8s step-end infinite"></span>
  </div>

  <!-- Snaga bara -->
  <div style="width:100%;max-width:260px">
    <div style="height:5px;border-radius:3px;background:rgba(0,0,0,.1);overflow:hidden">
      <div id="pet-bar" style="height:100%;border-radius:3px;width:0;transition:width .4s,background .3s"></div>
    </div>
    <div id="pet-bar-label" style="font-size:11px;text-align:right;margin-top:4px;min-height:16px;font-family:system-ui,sans-serif"></div>
  </div>

  <!-- Zvuk toggle -->
  <button type="button" id="pet-sound-btn"
          style="background:none;border:1px solid rgba(0,0,0,.2);border-radius:20px;
                 padding:5px 14px;font-size:11px;cursor:pointer;color:rgba(0,0,0,.5);
                 font-family:system-ui,sans-serif;transition:all .15s"
          onclick="petToggleSound()">🔇 Zvuk</button>
</div>

<style>
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
@keyframes petbounce{0%{transform:scale(1) rotate(0)}35%{transform:scale(1.15) rotate(-6deg)}65%{transform:scale(.94) rotate(3deg)}100%{transform:scale(1) rotate(0)}}
@keyframes petshake{0%,100%{transform:rotate(0)}20%{transform:rotate(-8deg)}40%{transform:rotate(8deg)}60%{transform:rotate(-5deg)}80%{transform:rotate(5deg)}}
@keyframes petnod{0%,100%{transform:translateY(0)}35%{transform:translateY(-7px)}65%{transform:translateY(2px)}}
</style>

<script>
(function(){
const PET_NAME = "{{ pet_name|escapejs }}";
const BANNED = new Set(['123456','654321','111111','222222','333333','444444',
  '555555','666666','777777','888888','999999','000000','112233','998877',
  '121212','147258','258369','010101','131313','123123','321321',
  '234567','345678','456789','567890','987654','876543','765432',
  '159753','102030','192837','142536']);

let soundOn = false, typeTimer = null;
const synth = window.speechSynthesis;
const img = document.getElementById('pet-img');
const bubble = document.getElementById('pet-bubble');
const bubbleText = document.getElementById('pet-bubble-text');
const cursor = document.getElementById('pet-cursor');
const emote = document.getElementById('pet-emote');
const bar = document.getElementById('pet-bar');
const barLabel = document.getElementById('pet-bar-label');
const pinHidden = document.getElementById('pin-hidden') ||
                  document.querySelector('input[name="pin"]');

const msgs = {
  idle:  [`Hej! Ja sam ${PET_NAME}! Upiši PIN koji samo ti i ja znamo! 🐾`],
  typing:[`Slušam... 👂`, `Upisuješ...`, `Čekam...`],
  banned:[`Hej! 😤 Ovo PIN znaju čak i mačke iz susjedstva!`,
          `Ma daj! Ovo svi koriste — smisli nešto samo naše!`,
          `Ovaj PIN je kao "sjedni" — svak ga zna. Probaj drugačije!`],
  seq:   [`Ozbiljno? 1-2-3? 😂 Moje buve znaju bolje kombinacije!`,
          `Trag u snijegu — svak može slijediti. Smisli nešto originalnije!`],
  simple:[`Hmmm... 🤔 Premalo različitih znamenki. Čak štene zna više!`,
          `Probaj kombinirati različite brojeve — ja čuvam samo jake PIN-ove!`],
  ok:    [`Već bolje! 👍 Još malo i nitko nas ne nanjuši!`,
          `To mi se sviđa! Još korak do savršenog PIN-a!`],
  great: [`Savršeno! 🏆 Ni pas tragač s diplomom ne bi ga nanjušio!`,
          `Odlično! Samo ti i ja znamo ovu tajnu. Tako se čuva ${PET_NAME}!`,
          `Wow! 🎉 Ti si šef sigurnosti! Čuvamo zajedno!`],
};
const emotes={idle:'😊',typing:'👂',banned:'😤',seq:'😂',simple:'🤔',ok:'👍',great:'🏆'};
const colors={idle:'',typing:'#888',banned:'#E24B4A',seq:'#E24B4A',simple:'#EF9F27',ok:'#EF9F27',great:'#1D9E75'};
const strengths={idle:0,typing:10,banned:4,seq:7,simple:20,ok:55,great:100};
const anims={idle:'petbounce',typing:'petnod',banned:'petshake',seq:'petshake',simple:'petnod',ok:'petbounce',great:'petbounce'};
const labels={idle:'',typing:'',banned:'Jako slab PIN — svi ga znaju',seq:'Prepoznatljiv uzorak',simple:'Slab PIN',ok:'Srednji PIN',great:'Odličan PIN!'};

function rnd(arr){return arr[Math.floor(Math.random()*arr.length)];}

function show(state){
  const msg = rnd(msgs[state]||msgs.idle);
  const emo = emotes[state]||'😊';
  const col = colors[state]||'';
  const str = strengths[state]||0;
  const anim = anims[state]||'petbounce';
  const lbl = labels[state]||'';

  // Emote
  emote.textContent = emo;
  emote.style.transform='scale(1)'; emote.style.opacity='1';

  // Animacija lika
  if(img){
    img.style.animation='';
    void img.offsetWidth;
    img.style.animation=`${anim} .5s cubic-bezier(.34,1.56,.64,1)`;
  }

  // SVG emocije (samo za SVG pas)
  const svgMouth=document.getElementById('svgMouth');
  const svgTail=document.getElementById('svgTail');
  if(svgMouth){
    if(state==='great'||state==='ok'||state==='idle')
      svgMouth.setAttribute('d','M35 40 Q40 46 45 40');
    else if(state==='banned'||state==='seq')
      svgMouth.setAttribute('d','M36 42 Q40 38 44 42');
    else svgMouth.setAttribute('d','M36 40 Q40 44 44 40');
  }
  if(svgTail){
    if(state==='great') svgTail.setAttribute('d','M62 50 Q76 36 72 27');
    else if(state==='banned'||state==='seq') svgTail.setAttribute('d','M62 55 Q68 64 65 70');
    else svgTail.setAttribute('d','M62 52 Q73 40 69 33');
  }

  // Bubble + typewriter
  if(typeTimer) clearInterval(typeTimer);
  bubbleText.textContent='';
  bubble.style.opacity='1';
  bubble.style.transform='scale(1) translateY(0)';
  cursor.style.display='inline-block';

  let i=0;
  typeTimer=setInterval(()=>{
    if(i<msg.length){ bubbleText.textContent+=msg[i]; i++; }
    else{
      clearInterval(typeTimer);
      cursor.style.display='none';
      if(soundOn && synth && state!=='typing' && state!=='idle'){
        const u=new SpeechSynthesisUtterance(msg.replace(/[🐾👂😤😂🤔👍🏆🎉]/g,''));
        u.lang='hr-HR'; u.rate=1.1; u.pitch=1.3;
        const vs=synth.getVoices();
        const hr=vs.find(v=>v.lang.startsWith('hr'));
        if(hr) u.voice=hr;
        synth.cancel(); synth.speak(u);
      }
    }
  }, 24);

  // Bar
  bar.style.width=str+'%';
  bar.style.background=col||'transparent';
  barLabel.style.color=col;
  barLabel.textContent=lbl;
}

function evaluate(pin){
  if(!pin||pin.length===0){show('idle');return;}
  if(pin.length<6){show('typing');return;}
  const u=new Set(pin).size;
  const seqs=['012345','123456','234567','345678','456789','567890',
               '987654','876543','765432','654321','543210'];
  if(BANNED.has(pin)||u===1){show('banned');return;}
  if(seqs.includes(pin)){show('seq');return;}
  if(u<3){show('simple');return;}
  if(u>=5){show('great');return;}
  show('ok');
}

// Hook na PIN hidden input
function hookPin(){
  if(!pinHidden) return;
  const obs=new MutationObserver(()=>evaluate(pinHidden.value));
  obs.observe(pinHidden,{attributes:true,attributeFilter:['value']});
  // Direktni input
  const boxes=document.querySelectorAll('#pin-boxes input, .pin-input input, input[data-idx]');
  boxes.forEach(b=>{
    b.addEventListener('input',()=>{
      const val=Array.from(boxes).map(x=>x.value).join('');
      if(pinHidden) pinHidden.value=val;
      evaluate(val);
    });
  });
}

window.petToggleSound=function(){
  soundOn=!soundOn;
  const btn=document.getElementById('pet-sound-btn');
  if(btn){btn.textContent=soundOn?'🔊 Zvuk':'🔇 Zvuk';
          btn.style.color=soundOn?'#c9a84c':'rgba(0,0,0,.5)';
          btn.style.borderColor=soundOn?'#c9a84c':'rgba(0,0,0,.2)';}
  if(soundOn&&synth) synth.getVoices();
};

document.addEventListener('DOMContentLoaded',()=>{
  hookPin();
  setTimeout(()=>show('idle'),600);
});
})();
</script>
```

COMMIT: `feat(ux): ljubimac govori — PIN strength widget s pravom slikom`

---

## CC-1 / FAZA 3 (sat 3-4): MAGIC TOKEN (sigurnost)

### M3.1 — AddAnimalToken model
PROVJERI ima li već migracija u memio_pet:
```bash
ls /var/www/fina-connect/memio_pet/migrations/ | tail -5
```

Dodaj u `memio_pet/models.py`:
```python
import secrets as _sec

class AddAnimalToken(models.Model):
    token     = models.CharField(max_length=64, unique=True, db_index=True,
                                  default=lambda: _sec.token_urlsafe(32))
    breeder   = models.ForeignKey(BreederProfile, on_delete=models.CASCADE,
                                   related_name='add_tokens')
    email     = models.EmailField()
    created_at= models.DateTimeField(auto_now_add=True)
    used_at   = models.DateTimeField(null=True, blank=True)
    expires_at= models.DateTimeField()
    ip        = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label='memio_pet'
        db_table='mp_add_animal_token'

    @classmethod
    def create(cls, breeder, email, ip=None):
        from django.utils import timezone
        return cls.objects.using('memio_pets').create(
            breeder=breeder, email=email, ip=ip,
            expires_at=timezone.now()+timezone.timedelta(minutes=30))

    @property
    def is_valid(self):
        from django.utils import timezone
        return not self.used_at and timezone.now() < self.expires_at

    def consume(self):
        from django.utils import timezone
        self.used_at=timezone.now()
        self.save(using='memio_pets', update_fields=['used_at'])
```

```bash
venv/bin/python manage.py makemigrations memio_pet
venv/bin/python manage.py migrate --database=memio_pets
```

### M3.2 — Email token view
Dodaj `add_animal_request(request)`:
- GET → forma (email input + submit)
- POST → nađi BreederProfile po emailu → pošalji magic link na email → "Provjeri email"
  Email: "Klikni da dodaš ljubimca: https://memio.pet/ljubimac/token/TOKEN/"

Dodaj `add_animal_with_token(request, token)`:
- Dohvati AddAnimalToken, provjeri is_valid
- Ako nije valid → "Link je istekao. Zatraži novi."
- Ako jest → token.consume() → prikaži/procesira add_animal formu

### M3.3 — URL
```python
path("ljubimac/token/<str:token>/", views.add_animal_with_token, name="add_animal_token"),
path("ljubimac/zatrazi/", views.add_animal_request, name="add_animal_zatrazi"),
```

COMMIT: `security(memio-pet): magic token auth za dodavanje ljubimaca`

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  AGENT CC-2 — LIMIT CONNECT FINAL PREP + MARIJA             ║
# ║  Task: marija dry-run + fiscal sos + TriKey password UX      ║
# ╚═══════════════════════════════════════════════════════════════╝

## CC-2 / FAZA 1 (sat 1-2): FISCAL + TRIKEY PASSWORD

### L1.1 — Password strength (login stranica)
Lokacija: `templates/registration/login.html`

PROČITAJ PRVO:
```bash
grep -n "password\|lozinka\|input\|submit" /var/www/fina-connect/templates/registration/login.html | head -20
```

Dodaj ISPOD password polja (isti princip kao PIN widget, ali za lozinku):
```javascript
const BANNED_PASSWORDS = new Set([
  'password','lozinka','123456','qwerty','admin','hrvatska',
  'zagreb','limit','connect','welcome','letmein','monkey',
  '111111','abc123','iloveyou','sunshine','master','dragon',
  'admin123','pass123','test123','demo123','user123',
]);

function checkPassword(pw) {
  if (!pw || pw.length < 3) return;
  const score = [
    pw.length >= 8,
    /[A-Z]/.test(pw),
    /[a-z]/.test(pw),
    /[0-9]/.test(pw),
    /[^A-Za-z0-9]/.test(pw),
    !BANNED_PASSWORDS.has(pw.toLowerCase()),
    pw.length >= 12,
  ].filter(Boolean).length;

  const msgs = [
    null,
    'Ovu lozinku svi znaju. Dodaj velika slova i brojeve! 🐾',
    'Bolje, ali još uvijek slabo. Dodaj specijalne znakove! 🤔',
    'Srednje jaka. Još malo i bit ćemo sigurni! 👍',
    'Dobra lozinka! Skoro savršeno! 😊',
    'Odlična lozinka! Ni pas tragač je ne bi nanjušio! 🏆',
    'Savršena zaštita! Ti si pravi čuvar sigurnosti! 🎉',
    'Neprobojna! Čak i moji preci vučjaci bi se sklonili! 🔐',
  ];
  // Prikaži poruku + strength bar (isti dizajn kao PIN widget)
}
```

### L1.2 — TriKey PIN setup — provjeri template
```bash
cat /var/www/fina-connect/templates/registration/trikey_register.html | grep -n "pin\|PIN\|submit" | head -20
```
Ako PIN setup ne postoji kao zasebna stranica → kreiraj `templates/accounts/pin_setup.html`
koji koristi isti PIN widget s ljubimcem (CC-1 faza 2 kod).

### L1.3 — LIMIT Connect UI final polish
Preostalo za 9/10:
a) Faktura preview (HTML preview modal) — provjeri:
   ```bash
   grep -rn "preview\|predpregled" /var/www/fina-connect/templates/documents/ | head -5
   ```
b) Dark/light mode audit — svaka stranica mora imati `data-theme` support:
   ```bash
   grep -rL "data-theme\|prefers-color-scheme" /var/www/fina-connect/templates/pos/*.html | head -5
   ```
c) Mobile nav — provjeri hamburger menu radi na svim modulima

COMMIT: `feat(ui): password strength widget + TriKey PIN UX + UI polish`

---

## CC-2 / FAZA 2 (sat 2-4): MARIJA DRY-RUN PREP

### L2.1 — Marija testni pristup
```bash
# Provjeri login za Marija
venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.filter(username__icontains='marija').first()
if u:
    print('Username:', u.username, '| Email:', u.email)
    u.set_password('Konjik2026!')
    u.save()
    print('Lozinka resetirana: Konjik2026!')
else:
    print('Nema Marija korisnika — kreiraj')
"
```

### L2.2 — Test scenario za Marija
Kreiraj `MARIJA_TEST_SCENARIO.md`:
```
MARIJA DRY-RUN 08.04.2026.
Login: [email] / Konjik2026!
URL: https://limit-connect.com/hr/login/

PROVJERI REDOM:
1. Konto → Knjiga prihoda i rashoda → filtriraj po datumu
2. Fakture → Nova faktura → unesi test kupca → preview → PDF download
3. PDV → PDV-S za test tvrtku → usporedi s Synesis izvodom
4. POS → Terminal 51 (Široki Šor) → test narudžba → fiskalizacija
5. Honorari → nova isplata → JOPPD pregled
6. Backup provjera: zadnji backup datum?

ZABILJEŽI SVE što ne odgovara očekivanjima.
```

### L2.3 — Saldakonti provjera
```bash
venv/bin/python manage.py shell -c "
from partners.models import Partner
from konto.models import JournalEntry
# Provjeri balanse za test firme
print('Partnera:', Partner.objects.count())
print('Knjižnih stavki:', JournalEntry.objects.count())
"
```

### L2.4 — Faktura PDF fix (ako nije popravljen od pdf/CSS)
```bash
# Provjeri da faktura PDF ne crasha
curl -s -o /dev/null -w '%{http_code}' \
  'https://limit-connect.com/hr/documents/arhiva/1/pdf/'
# Mora biti 200, ne 500
```

COMMIT: `feat(marija): dry-run prep — testni pristup, test scenario, faktura fix`

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  AGENT CC-3 — memio.world + NO LIMIT/AZIL + BOXGRAM        ║
# ║  Task fajlovi: CC_TASK_F3, CC_TASK_F5_NO_LIMIT_AZIL        ║
# ╚═══════════════════════════════════════════════════════════════╝

## CC-3 / FAZA 1 (sat 1-3): memio.world LANDING + REGISTRACIJA

### W1.1 — Pročitaj što postoji
```bash
grep -n "^class" /var/www/fina-connect/memio_world/models.py
cat /var/www/fina-connect/memio_world/urls.py
cat /var/www/fina-connect/memio_world/views.py
ls /var/www/fina-connect/templates/memio_world/
```

### W1.2 — Landing page (memio.world/)
PROČITAJ nginx config za memio.world:
```bash
cat /etc/nginx/sites-enabled/memio-world
```

Template: `templates/memio_world/landing.html`
Design: tamna, elegantna paleta (navy #0a0e1a + zlatna #c9a84c + bijela)

Sekcije (redom):
1. NAV: logo "Memio.world" + CTA "Pridruži se listi čekanja"
2. HERO:
   - Eyebrow: "Projekt NO LIMIT udruge · U razvoju"
   - H1: "Svako dijete zaslužuje svoju knjigu."
   - Sub: "Digitalni portal sjećanja koji raste zajedno s vašim djetetom — od prvog koraka do diplome."
   - CTA: "Prijavi me — čekam na otvaranje" (→ /waitlist/)
3. VIZIJA (3 kartice):
   - 📷 "Fotografije i priče" — svaki trenutak, zauvijek sačuvan
   - 🏆 "Prekretnice" — prvi korak, prva riječ, polazak u školu
   - 📚 "Za cijeli život" — dijete naslijedi portal kad odraste
4. INSTITUCIJE sekcija:
   - "Projekt podupire Hrvatska knjižnica" (placeholder za Mariju Čačić)
   - "Na putu prema Bruxellesu — digitalizacija djetinjstva"
5. WAITLIST forma:
   - Email + ime + broj djece → POST na /api/memio-world/waitlist/
   - "Bit ćete prvi obaviješteni"
6. FOOTER: NO LIMIT udruga | link na limit-connect.com/no-limit/

### W1.3 — Waitlist view (provjeri postoji li)
```bash
cat /var/www/fina-connect/memio_world/views.py
```
Ako nedostaje waitlist_signup view koji prima POST sa forme:
```python
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
@require_POST
def waitlist_signup(request):
    try:
        data = json.loads(request.body)
    except:
        data = request.POST
    email = data.get('email','').strip().lower()
    if not email or '@' not in email:
        return JsonResponse({'error':'Email obavezan'}, status=400)
    from memio_world.models import WaitlistEntry
    obj, created = WaitlistEntry.objects.using('memio_world').get_or_create(
        email=email,
        defaults={'name': data.get('ime',''), 'num_children': data.get('djeca',0)}
    )
    return JsonResponse({'ok': True, 'created': created})
```

### W1.4 — NGINX za memio.world
```bash
cat /etc/nginx/sites-enabled/memio-world
```
Provjeri da root index.html postoji ili da su Django rute proxirane.
Ako postoji statički index.html → zamijeni s Django proxy:
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

COMMIT: `feat(memio-world): landing + waitlist + nginx fix`

---

## CC-3 / FAZA 2 (sat 3-5): NO LIMIT AZIL — KOMPLETNO

### A1.1 — Pročitaj što postoji
```bash
cat /var/www/fina-connect/no_limit/views.py
cat /var/www/fina-connect/no_limit/urls.py
ls /var/www/fina-connect/templates/no_limit/
ls /var/www/fina-connect/templates/udruge/azil/
```

### A1.2 — Azil public landing (/) u no-limit kontekstu
URL: `https://limit-connect.com/no-limit/`
Template: `templates/no_limit/azil_landing.html` (provjeri postoji li)

Mora sadržavati:
- Hero: "Vaš azil zaslužuje digitalni alat. Besplatno. Zauvijek."
- Što dobivaju: POS na mobitelu / Fiskalizacija / Evidencija životinja / Usvajanje
- Jedino što trebaju: Bluetooth čitač čipova (~30€, Amazon)
- Prijava forma → POST na /no-limit/azili/prijava/
- CTA: "Pridruži se — besplatno za sve azile u HR"
- Footer: NO LIMIT udruga | Predsjednik: Ivan Brtan

### A1.3 — Azil prijava forma (iza logina → LIMIT Connect)
URL: `https://limit-connect.com/no-limit/azili/prijava/`
PROVJERI koji model se koristi:
```bash
grep -n "^class\|AzilPrijava\|no_limit" /var/www/fina-connect/no_limit/models.py
```
Forma: Naziv azila, OIB, kontakt ime, email, telefon, grad, broj životinja, poruka
Nakon submita → admin notifikacija + "Kontaktirat ćemo vas u 24h"

### A1.4 — Mobile POS skin za azile (CSS)
Provjeri:
```bash
ls /var/www/fina-connect/static/css/apps/pos-azil.css
curl -s -o /dev/null -w '%{http_code}' https://limit-connect.com/static/css/apps/pos-azil.css
```
Ako 404 → kreiraj:
- Topla boja shema (amber #f59e0b umjesto plave)
- 4 default artikla: "Usvajanje psa / mačke", "Donacija", "Medicinska naknada"
- Big buttons (min 60px) — dizajn za volontere
- Šapa ikona umjesto F loga u headeru

### A1.5 — Azil tenant setup komanda
```bash
grep -n "setup_azil\|azil_tenant" /var/www/fina-connect/no_limit/management/commands/ 2>/dev/null
```
Ako ne postoji, kreiraj `management/commands/setup_azil_tenant.py`:
```python
# Kreira besplatni tenant za azil
# python manage.py setup_azil_tenant --name="Azil Osijek" --email="osijek@azil.hr"
```

COMMIT: `feat(azil): no-limit landing + prijava forma + POS skin + setup komanda`

---

## CC-3 / FAZA 3 (sat 5-6): BOXGRAM ONBOARDING

### B1.1 — Provjeri što radi
```bash
curl -s -o /dev/null -w '%{http_code}' https://memio.pet/boxgram/feed/
curl -s -o /dev/null -w '%{http_code}' https://memio.pet/boxgram/ljubimac/rex-pas-232d99f5/
```

### B1.2 — Boxgram landing page
URL: `https://memio.pet/boxgram/`
Jednostavna stranica:
- "Boxgram — digitalni život tvog ljubimca"
- Feed najnovijih javnih profila
- Link: "Poveži svog ljubimca" → /registracija/

### B1.3 — Share gumbi na profilu ljubimca
`templates/memio_pet/profile.html` — dodaj:
```html
<div class="share-row">
  <button onclick="copyLink()">🔗 Kopiraj link</button>
  <a href="https://wa.me/?text=..." target="_blank">💬 WhatsApp</a>
  <a href="/pas/CHIP/qr/" target="_blank">📷 QR kod</a>
</div>
```

COMMIT: `feat(boxgram): landing + share gumbi na profilu`

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  AGENT GEMINI — QA + SIGURNOST + MONITORING                 ║
# ║  Task: GEMINI_TASK_F6_QA_AUDIT.md                           ║
# ╚═══════════════════════════════════════════════════════════════╝

## GEMINI ZADACI (sat 1-7, kontinuirano):

### G1 — HTTP audit svake rute svake 30 min
Prati: 200/302 = OK | 404/500 = ALARM → odmah kreira CC_TASK_FIX_*.md

### G2 — Django logs monitoring
```bash
tail -f /var/log/gunicorn/error.log | grep "ERROR\|500\|Exception"
```
Svaka nova ERROR linija → CC_TASK_FIX_*.md s detaljem

### G3 — Zabranjena odredišta (svaka ura)
```bash
grep -rn "limit-connect.com/hr/register\|limit-connect.com/pricing\|no-limit.world" \
  /var/www/fina-connect/templates/memio_pet/ \
  /var/www/memio-pet/index.html
# Mora biti 0 rezultata
```

### G4 — Sigurnosni audit (jednom)
```bash
# Admin URL ne smije biti /admin/
curl -s -o /dev/null -w '%{http_code}' https://limit-connect.com/admin/
# Mora biti 404

# Debug=False
curl -s https://limit-connect.com/hr/NEPOSTOJI9999/ | grep -i "traceback\|debug"
# Mora biti prazan output

# Headers
curl -sI https://limit-connect.com/ | grep -i "x-powered\|server:"
# Ne smije pokazati Django verziju
```

### G5 — Performance benchmark
```bash
for url in \
  "https://memio.pet/" \
  "https://memio.pet/registracija/" \
  "https://memio.pet/pas/191031000312345/" \
  "https://limit-connect.com/hr/login/"; do
  t=$(curl -s -o /dev/null -w "%{time_total}" --max-time 10 "$url")
  echo "$t $url"
done
# Alarm ako > 2.0s
```

### G6 — Na kraju: FINAL_QA_REPORT_07_04.md
Sve rezultate u jedan fajl. Format:
```
BLOK | PROVJERA | REZULTAT | NAPOMENA
```
Commitaj: `audit(gemini): FINAL_QA_REPORT_07_04.md`

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  IVAN — TESTIRANJE + ODLUKE (cijeli dan)                    ║
# ╚═══════════════════════════════════════════════════════════════╝

## IVAN CHECKLIST:

### Sat 1-2: memio.pet pilot test
- [ ] Registriraj se na https://memio.pet/registracija/ (kao Ljubeta)
- [ ] Dodaj Vučka kroz formu (ne ručno u bazi)
- [ ] Provjeri profil — izgleda li profesionalno?
- [ ] Klikni svaki gumb, svaki link — je li živ?
- [ ] Pošalji Ljubeti link kad prođe test

### Sat 2-3: PIN/lozinka widget
- [ ] Testiraj PIN widget (upiši 123456, upiši jak PIN)
- [ ] Uključi zvuk — radi HR glas?
- [ ] Pokreni trikey setup: /accounts/trikey/pin/setup/

### Sat 3-4: POS test (Šeki/Kruljac)
- [ ] Login: rizo / Frisko2026!
- [ ] T51 — otvori stol, dodaj artikle, zatvori račun
- [ ] T58 Korpaš — isti flow
- [ ] Bilježi što ne radi → Sonnet → CC task

### Sat 4-5: Poslovne odluke (Sonnet priprema materijale)
- [ ] Konjik: Scenarij A (639€/mj) — razgovor s Marijom
- [ ] Pricing: Micro 9€ ili 10€?
- [ ] memio.hr domena — registracija
- [ ] EUIPO MEMIO trademark prijava

### Sat 5-6: Marija brief
- [ ] Pošalji MARIJA_BRIEF_08_04.md Mariji emailom
- [ ] Dogovori login + testnu firmu za 08.04.

### Sat 6-7: GO/NO-GO odluka
- [ ] Pregled FINAL_QA_REPORT_07_04.md
- [ ] Je li sve zeleno za 15.04. produkciju?
- [ ] Ako da → load test 12.04. (CCX33 server)

---

# ╔═══════════════════════════════════════════════════════════════╗
# ║  SONNET — KOORDINACIJA + DIRECT FIXES (cijeli dan)          ║
# ╚═══════════════════════════════════════════════════════════════╝

## SONNET STALNI ZADACI:
1. Prati izvještaje svakog agenta
2. Ako CC stane → odmah kreiraj novi WAKE task
3. Ako Gemini nađe bug → kreiraj CC_TASK_FIX_*.md za pravi agent
4. Sve textualne ispravke (landing page tekst, email tekst) → direktno
5. Prati FENIX_STATUS.md — update svakih 2 sata
6. Odluke koje CC ne može sam → Ivan → natrag CC

---

# ═══════════════════════════════════════════════════════════════
# VREMENSKI PLAN (target)
# ═══════════════════════════════════════════════════════════════

  09:00  Svi agenti startaju s ovim planom
  10:00  CC-1: memio.pet journey fix LIVE (M1.1-M1.6)
  11:00  CC-2: Marija testni pristup spreman + password widget
  11:00  CC-3: memio.world landing LIVE
  12:00  CC-1: ljubimac govori LIVE na PIN stranici
  12:00  CC-3: NO LIMIT azil landing LIVE
  13:00  Ivan: pilot test memio.pet (sam prolazi sve korake)
  13:30  Ivan: šalje Ljubeti link
  14:00  CC-1: magic token implementiran
  14:00  CC-2: LIMIT Connect UI 9/10 (faktura preview, dark/light)
  15:00  CC-3: Boxgram onboarding + share gumbi
  15:00  Gemini: FINAL_QA_REPORT generiran
  16:00  Sonnet: FENIX_STATUS.md finalni update
  16:00  Ivan: GO/NO-GO pregled

# ═══════════════════════════════════════════════════════════════
# PRAVILA ZA SVE AGENTE
# ═══════════════════════════════════════════════════════════════

1. ČITAJ MODELE PRIJE PISANJA — uvijek, bez iznimke
2. COMMIT SVAKI ZAVRŠENI ZADATAK — ne čekaj fazu
3. DJANGO CHECK 0 ERRORS — before every commit
4. NEMA LIMIT-CONNECT.COM/HR/ NA MEMIO.PET — nigdje, nikad
5. NEMA IMPROVIZACIJE U SIGURNOSTI — prati plan točno
6. AKO NEŠTO NE RADI — napiši u FENIX_STATUS.md odmah
7. KRAJ SESIJE — git log + FENIX_STATUS.md update

# ═══════════════════════════════════════════════════════════════
# CILJANE OCJENE (16:00)
# ═══════════════════════════════════════════════════════════════

  LIMIT Connect UI/UX:      9.5/10
  memio.pet journey:         9/10
  memio.pet UX/VAU:          9/10  (ljubimac s pravom slikom)
  memio.world:               7/10
  NO LIMIT / azil:           8/10
  Sigurnost:                 9/10
  Server:                    9.5/10

  UKUPNA OCJENA SUSTAVA:     9/10

