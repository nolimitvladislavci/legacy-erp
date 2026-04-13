# CC TASK — SIGURNOST + UX 10/10
# Prioritet: 🔴 KRITIČNO | Rok: 07.04.2026.
# Ivan: "kod na razini osnovnoškolca — dižemo na inžinjerski nivo"

## OBVEZNO PRVO: čitaj stvarne modele
```bash
grep -n "^class\|email\|token\|session\|magic" /var/www/fina-connect/memio_pet/models.py | head -30
grep -n "^class\|email\|token" /var/www/fina-connect/accounts/trikey.py | head -20
```

---

## PROBLEM 1 — KRITIČNA SIGURNOSNA RUPA (fix odmah)

`/ljubimac/novi/?breeder=UUID` — JAVNO BEZ AUTH.
Bilo tko tko vidi URL može pisati u tuđi profil.

### Rješenje: Magic Token (email verifikacija)

**Tok:**
1. Korisnik klikne "+ Dodaj ljubimca" na svom profilu
2. Forma traži email
3. Backend provjerava: `BreederProfile.objects.using('memio_pets').filter(email=email_unos).exists()`
4. Ako postoji → šalje se magic link na taj email (token, 30min, jednokratan)
5. Link vodi na `/ljubimac/novi/token/ABC123/` → forma za dodavanje
6. Token se invalidira nakon prvog korištenja

**Model za token** (dodati u memio_pet/models.py):
```python
import secrets as _secrets
class AddAnimalToken(models.Model):
    """Jednokratni token za dodavanje ljubimca — email verifikacija."""
    token = models.CharField(max_length=64, unique=True, db_index=True)
    breeder = models.ForeignKey(BreederProfile, on_delete=models.CASCADE,
                                related_name='add_tokens')
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True)

    class Meta:
        app_label = 'memio_pet'
        db_table = 'mp_add_animal_token'

    @classmethod
    def create_for_breeder(cls, breeder, email, ip=None):
        from django.utils import timezone
        return cls.objects.using('memio_pets').create(
            token=_secrets.token_urlsafe(32),
            breeder=breeder,
            email=email,
            expires_at=timezone.now() + timezone.timedelta(minutes=30),
            ip_address=ip,
        )

    @property
    def is_valid(self):
        from django.utils import timezone
        return self.used_at is None and timezone.now() < self.expires_at

    def consume(self):
        from django.utils import timezone
        self.used_at = timezone.now()
        self.save(using='memio_pets', update_fields=['used_at'])
```

**URLs:**
```python
path("ljubimac/zatrazi/", views.add_animal_request, name="add_animal_request"),
path("ljubimac/token/<str:token>/", views.add_animal_with_token, name="add_animal_token"),
```

**Views:**
- `add_animal_request(request)`: GET→forma (email), POST→validira email→šalje magic link
- `add_animal_with_token(request, token)`: Validira token, prikazuje/procesira formu, invalidira token

**Migriraj:**
```bash
venv/bin/python manage.py makemigrations memio_pet
venv/bin/python manage.py migrate --database=memio_pets
```

**Ukloni staru ranjivu rutu** iz urls.py:
```python
# UKLONI: path("ljubimac/novi/", views.add_animal, ...)
# DODAJ: path("ljubimac/zatrazi/", ...)
#         path("ljubimac/token/<str:token>/", ...)
```

---

## PROBLEM 2 — PIN SNAGA: ljubimac govori

Lokacija: `templates/accounts/trikey_login.html` i `templates/registration/trikey_register.html`

### Lista zabranjenih PIN-ova (kompletna — nadopuni trikey.py)

```python
BANNED_PINS = {
    # Sekvencijalni
    '123456','234567','345678','456789','567890',
    '654321','543210','987654','876543',
    # Ponavljajući
    '111111','222222','333333','444444','555555',
    '666666','777777','888888','999999','000000',
    # Poznate kombinacije
    '112233','998877','121212','010101','202020',
    '131313','141414','151515','161616','171717',
    '181818','191919','102030','142536',
    # Datumi (generički)
    '010101','311299','010100','123123','321321',
    # HR specifično
    '091991','091992','091993','091994','091995',
    '091996','091997','091998','091999','092000',
    # Tipkovnica uzorci
    '147258','258369','369147','159753',
}
```

Dodaj u `trikey.py` `set_pin()` metodu:
```python
from accounts.trikey import BANNED_PINS  # import na vrhu fajla
if raw_pin in BANNED_PINS:
    raise ValueError('PIN_BANNED')
if len(set(raw_pin)) < 3:
    raise ValueError('PIN_TOO_SIMPLE')
```

### Real-time JavaScript validator (ljubimac govori)

U PIN setup template dodaj ISPOD pin input polja:

```html
<!-- Ljubimac govori — sigurnosna poruka -->
<div id="pet-says" style="display:none;margin:12px 0;padding:12px 16px;
  background:rgba(201,168,76,.08);border:1px solid rgba(201,168,76,.2);
  border-radius:12px;font-size:.88rem;line-height:1.6;text-align:left">
  <span style="font-size:1.3rem">🐾</span>
  <span id="pet-message" style="margin-left:8px;color:var(--ink)"></span>
</div>
```

```javascript
const BANNED = new Set([
  '123456','654321','111111','222222','333333','444444','555555',
  '666666','777777','888888','999999','000000','112233','998877',
  '121212','147258','258369','010101','131313','123123'
]);

const PET_MESSAGES = {
  too_short:   "Čekam još... treba mi 6 znamenki! 🐾",
  sequential:  "Hm, to mi miriše na 1-2-3... a ja sam pas, ne računalo. Odaberi nešto originalnije! 🐕",
  repeating:   "Sve isti broj? Pa i moj rep se vrti u krug, ali PIN ti ne bi smio! Probaj kombinaciju. 🐾",
  banned:      "Ovo koriste svi! Mene su naučili da lošu lozinku nanjušim na 100 metara. Smisli bolji PIN! 🐶",
  too_simple:  "Premalo različitih znamenki. Čak i moj štenac zna više trikova od ovoga! 🐾",
  good:        "Super! Ovaj PIN ima 6 različitih mirisa — čak i ja ne bih pogodio! ✅ 🐕",
  great:       "Odlično! Ovaj PIN bi i štene zaštitio. Nitko ga neće nanjušiti! 🏆 🐾",
};

function checkPin(pin) {
  const box = document.getElementById('pet-says');
  const msg = document.getElementById('pet-message');
  if (!box || !msg) return;

  if (pin.length < 6) {
    box.style.display = 'block';
    box.style.borderColor = 'rgba(201,168,76,.3)';
    msg.textContent = PET_MESSAGES.too_short;
    return false;
  }

  const unique = new Set(pin).size;
  const isSeq = ['012345','123456','234567','345678','456789',
                  '987654','876543','765432','654321'].includes(pin);
  const isRep = unique === 1;
  const isBanned = BANNED.has(pin);

  let msgKey = 'good';
  let color = 'rgba(76,175,125,.2)';
  let valid = true;

  if (isSeq)        { msgKey = 'sequential'; color = 'rgba(224,82,82,.15)'; valid = false; }
  else if (isRep)   { msgKey = 'repeating';  color = 'rgba(224,82,82,.15)'; valid = false; }
  else if (isBanned){ msgKey = 'banned';     color = 'rgba(224,82,82,.15)'; valid = false; }
  else if (unique < 3){ msgKey = 'too_simple'; color = 'rgba(255,165,0,.15)'; valid = false; }
  else if (unique >= 5){ msgKey = 'great'; }

  box.style.display = 'block';
  box.style.borderColor = valid ? 'rgba(76,175,125,.3)' : 'rgba(224,82,82,.3)';
  box.style.background = color;
  msg.textContent = PET_MESSAGES[msgKey];
  return valid;
}

// Hookaj na PIN input event
document.addEventListener('DOMContentLoaded', function() {
  const pinHidden = document.getElementById('pin-hidden');
  if (!pinHidden) return;

  const observer = new MutationObserver(function() {
    checkPin(pinHidden.value);
  });
  observer.observe(pinHidden, { attributes: true, attributeFilter: ['value'] });

  // Direktni input event ako postoji
  const pinBoxes = document.querySelectorAll('#pin-boxes input');
  pinBoxes.forEach(function(box) {
    box.addEventListener('input', function() {
      const pin = Array.from(pinBoxes).map(b => b.value).join('');
      if (pinHidden) pinHidden.value = pin;
      checkPin(pin);
    });
  });
});
```

---

## PROBLEM 3 — FOOTER LINKOVI (jednostavno, ali netočno je netočno)

U `breeder.html`, `profile.html`, `registracija.html`, `index.html` (footer):

```html
<!-- ISPRAVNO: -->
<a href="https://limit-connect.com">Konjik d.o.o.</a>
<a href="https://limit-connect.com/no-limit/">NO LIMIT udruga</a>
<!-- NE: no-limit.world ili no-limit.world/azili/ -->
```

Provjeri i popravi u SVIM template fajlovima:
```bash
grep -rn "no-limit.world\|Konjik d.o.o" /var/www/fina-connect/templates/memio_pet/
grep -rn "no-limit.world\|Konjik d.o.o" /var/www/memio-pet/index.html
```

---

## PROBLEM 4 — LOZINKA (LIMIT Connect login)

U `templates/registration/login.html` dodaj real-time strength meter:

Isti pristup — pas govori, ali za lozinku:
```javascript
const BANNED_PASSWORDS = [
  'password','lozinka','123456','qwerty','admin','hrvatska',
  'zagreb','limit','connect','welcome','letmein','monkey',
  '111111','abc123','iloveyou','sunshine','master','dragon'
];

function checkPassword(pw) {
  // Pas govori o jakosti lozinke
  // Kriteriji: min 8 znakova, velika+mala+broj+specijalni
  // 4/4 kriterija = "Ovu lozinku ni pas tragač ne bi nanjušio!"
}
```

---

## COMMITOVI

Format: `security(memio-pet): [opis]`

Minimalno 4 commita:
1. `security(memio-pet): magic token auth za dodavanje ljubimaca`
2. `security(trikey): proširena lista zabranjenih PIN-ova`  
3. `feat(ux): ljubimac govori — PIN/lozinka strength indicator`
4. `fix(memio-pet): footer linkovi Konjik + NO LIMIT ispravni`

## VERIFIKACIJA

```bash
# 1. Stara ruta mora biti 404
curl -s -o /dev/null -w "%{http_code}" "https://memio.pet/ljubimac/novi/?breeder=UUID"
# Mora biti 404

# 2. Nova ruta radi
curl -s -o /dev/null -w "%{http_code}" "https://memio.pet/ljubimac/zatrazi/"
# Mora biti 200

# 3. Token invalidan → 404
curl -s -o /dev/null -w "%{http_code}" "https://memio.pet/ljubimac/token/LAZNITOKEN/"
# Mora biti 404 ili 400, NIKAD 500

# 4. Django check 0 errors
venv/bin/python manage.py check
```
