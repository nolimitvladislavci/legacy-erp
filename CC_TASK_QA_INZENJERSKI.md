# CC TASK — QA INŽINJERSKI TESTOVI
# Prioritet: 🔥 ODMAH | Rok: 07.04.2026. (prije Marija dry-run 08.04.)
# Assignee: Claude Code
# Cilj: Logičke simulacije + edge cases za sve nove module

## OBVEZNO PRIJE POČETKA
```bash
cd /var/www/fina-connect
git log --oneline -5  # potvrdi si na HEAD
venv/bin/python manage.py check  # mora biti 0 errors
```

---

## BLOK A — memio.pet REGISTRACIJA (logički tok)

### A1: Happy path registracija
```python
# tests/test_memio_registracija.py
from django.test import TestCase, Client
from memio_pet.models import BreederProfile

class RegistracijaTest(TestCase):
    databases = ['default', 'memio_pets']

    def setUp(self):
        self.client = Client(SERVER_NAME='memio.pet')

    def test_get_registracija(self):
        """Forma se prikazuje."""
        r = self.client.get('/registracija/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'BESPLATNO')
        self.assertNotContains(r, 'limit-connect.com/hr/register')  # NIKAD ova veza!

    def test_post_kreira_profil(self):
        """POST kreira BreederProfile i redirecta na uzgajivač stranicu."""
        r = self.client.post('/registracija/', {
            'ime': 'Ljubeta Test',
            'email': 'ljubeta@test.hr',
            'grad': 'Zagreb',
            'account_type': 'breeder',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/uzgajivac/'))
        bp = BreederProfile.objects.using('memio_pets').get(email='ljubeta@test.hr')
        self.assertEqual(bp.name, 'Ljubeta Test')

    def test_duplicate_email_redirecta(self):
        """Dupli email → redirect na postojeći profil, ne greška."""
        BreederProfile.objects.using('memio_pets').create(
            name='Stari', email='isti@test.hr', account_type='owner'
        )
        r = self.client.post('/registracija/', {
            'ime': 'Novi', 'email': 'isti@test.hr',
            'grad': 'Split', 'account_type': 'owner',
        })
        self.assertEqual(r.status_code, 302)

    def test_bez_emaila_vraca_grešku(self):
        """Prazno email polje → forma s greškom, ne 500."""
        r = self.client.post('/registracija/', {'ime': 'Test'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'obavezni')
```

### A2: memio.pet landing ne sadrži LIMIT Connect register link
```bash
# Shell test — kritičan!
curl -s https://memio.pet/ | grep -o "limit-connect.com/hr/register" | wc -l
# MORA biti 0. Ako nije → BUG, commit fix odmah.
curl -s https://memio.pet/ | grep -o "/registracija/" | wc -l  
# MORA biti >= 1
```

---

## BLOK B — BOXGRAM (signal + bridge logika)

### B1: Signal — novi AnimalProfile → auto Boxgram PetProfile
```python
class BoxgramSignalTest(TestCase):
    databases = ['default', 'memio_pets']

    def test_animal_kreira_boxgram_profil(self):
        """Svaki novi AnimalProfile automatski dobiva Boxgram PetProfile."""
        from memio_pet.models import AnimalProfile, BreederProfile
        from boxgram.models import PetProfile

        breeder = BreederProfile.objects.using('memio_pets').create(
            name='Test Uzgajivač', email='signal@test.hr', account_type='breeder'
        )
        animal = AnimalProfile.objects.using('memio_pets').create(
            name='Signal Pas', vrsta='pas', breed='Labrador',
            chip_number='TEST001SIGNAL', breeder=breeder,
            breeder_name_snapshot='Test Uzgajivač'
        )
        # Signal mora kreirati PetProfile
        pp = PetProfile.objects.filter(chip_number='TEST001SIGNAL').first()
        self.assertIsNotNone(pp, "Signal nije kreirao PetProfile!")
        self.assertEqual(pp.name, 'Signal Pas')

    def test_dupli_chip_ne_kreira_dupli_profil(self):
        """Signal ne smije kreirati duplikat ako profil već postoji."""
        from boxgram.models import PetProfile
        count_before = PetProfile.objects.count()
        # Kreiraj pa opet okida signal
        from memio_pet.models import AnimalProfile
        AnimalProfile.objects.using('memio_pets').create(
            name='Dupli Pas', vrsta='pas', chip_number='DUPLI001',
            breeder_name_snapshot='Test'
        )
        AnimalProfile.objects.using('memio_pets').create(
            name='Dupli Pas 2', vrsta='pas', chip_number='DUPLI001',  # isti chip
            breeder_name_snapshot='Test'
        )
        count_after = PetProfile.objects.filter(chip_number='DUPLI001').count()
        self.assertEqual(count_after, 1, "Dupli chip = dupli PetProfile!")
```

### B2: Javni profil — edge cases
```python
    def test_profil_bez_cipa_koristi_ear_tag(self):
        """Životinja bez chipa mora raditi s ear_tag."""
        from memio_pet.models import AnimalProfile
        AnimalProfile.objects.using('memio_pets').create(
            name='Ovca', vrsta='ovca', ear_tag='HR001-2024',
            breeder_name_snapshot='OPG Test'
        )
        r = self.client.get('/pas/HR001-2024/')
        self.assertEqual(r.status_code, 200)

    def test_nepostojeci_chip_vraca_404_ne_500(self):
        r = self.client.get('/pas/NIKADNIJEPOSTOJAO123/')
        self.assertEqual(r.status_code, 404)
        # Ne smije biti 500 Server Error
```

---

## BLOK C — TRIKEY (sigurnosna logika)

### C1: PIN validacija
```python
class TriKeyTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from accounts.trikey import TriKeyProfile
        self.user = User.objects.create_user('testuser_tk', 'tk@test.hr', 'old_pw')
        self.profile = TriKeyProfile.objects.create(user=self.user)

    def test_pin_mora_biti_6_znamenki(self):
        from accounts.trikey import TriKeyProfile
        with self.assertRaises(ValueError):
            self.profile.set_pin('123')   # prekratak
        with self.assertRaises(ValueError):
            self.profile.set_pin('12345678')  # predugačak
        with self.assertRaises(ValueError):
            self.profile.set_pin('abcdef')  # nije broj

    def test_trivijalni_pin_odbijen(self):
        from accounts.trikey import TriKeyProfile
        with self.assertRaises(Exception):
            self.profile.set_pin('123456')  # trivijaln

    def test_ispravan_pin_radi(self):
        self.profile.set_pin('847291')
        self.assertTrue(self.profile.verify_pin('847291'))
        self.assertFalse(self.profile.verify_pin('000000'))

    def test_lockout_nakon_5_pokusaja(self):
        self.profile.set_pin('847291')
        for _ in range(5):
            try:
                self.profile.verify_pin('000000')
            except:
                pass
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.pin_locked_until)
        with self.assertRaises(PermissionError):
            self.profile.verify_pin('847291')  # čak i točan PIN → locked

    def test_350_profila_postoji(self):
        from accounts.trikey import TriKeyProfile
        self.assertGreaterEqual(TriKeyProfile.objects.count(), 350)
```

---

## BLOK D — POS FISKALIZACIJA (kritičan poslovni tok)

### D1: Bon bez ZKI ne smije imati JIR
```python
class FiskalizacijaTest(TestCase):
    def test_novi_bon_nema_jir_bez_zki(self):
        """Bon koji nije prošao fiskalizaciju ne smije imati JIR."""
        from pos.models import POSReceipt
        # Provjeri da nijedan bon u bazi nema JIR bez ZKI
        invalid = POSReceipt.objects.filter(
            jir__isnull=False
        ).exclude(zki__isnull=False)
        self.assertEqual(invalid.count(), 0, 
            f"{invalid.count()} bonova ima JIR bez ZKI — fiskalizacijska greška!")

    def test_nema_bonova_bez_jir(self):
        """Po čišćenju testnih podataka, 0 bonova bez JIR."""
        from pos.models import POSReceipt
        bez_jir = POSReceipt.objects.filter(jir__isnull=True, is_training=False)
        self.assertEqual(bez_jir.count(), 0,
            f"{bez_jir.count()} nefiskaliziranih bonova u produkciji!")
```

### D2: POS terminal pristup — token auth
```bash
# Token mora davati pristup, bez tokena → redirect
curl -s -o /dev/null -w "%{http_code}" \
  "https://limit-connect.com/hr/pos/terminal/51/?token=uz1aKVyRlBp5zfpQoaFI9UwPyS4"
# Očekivano: 200

curl -s -o /dev/null -w "%{http_code}" \
  "https://limit-connect.com/hr/pos/terminal/51/?token=POGRESANTOKEN"
# Očekivano: 302 ili 403, NIKAD 200
```

---

## BLOK E — memio.world (integritet modela)

### E1: ChildProfile validacija
```python
class MemioWorldTest(TestCase):
    databases = ['default', 'memio_world']

    def test_child_profile_zahtijeva_ime_i_datum(self):
        from memio_world.models import ChildProfile
        from django.core.exceptions import ValidationError
        # Bez imena → greška
        child = ChildProfile(date_of_birth='2020-01-01')
        with self.assertRaises(Exception):
            child.full_clean()

    def test_waitlist_signup_api(self):
        """POST na waitlist API sprema email."""
        import json
        r = self.client.post(
            '/api/memio-world/waitlist/',
            data=json.dumps({'email': 'test@memio.world', 'ime': 'Test'}),
            content_type='application/json'
        )
        self.assertIn(r.status_code, [200, 201])

    def test_waitlist_dupli_email(self):
        """Dupli email na waitlisti ne smije baciti 500."""
        import json
        data = json.dumps({'email': 'dupli@memio.world'})
        self.client.post('/api/memio-world/waitlist/', data=data, content_type='application/json')
        r = self.client.post('/api/memio-world/waitlist/', data=data, content_type='application/json')
        self.assertNotEqual(r.status_code, 500)
```

---

## BLOK F — NO LIMIT AZIL (end-to-end)

### F1: Azil prijava forma
```python
class AzilTest(TestCase):
    def test_get_azil_landing(self):
        r = self.client.get('/no-limit/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'BESPLATNO')
        self.assertContains(r, 'azil')

    def test_prijava_azila_zahtijeva_login(self):
        """Prijava azila je iza logina — redirect, ne 200."""
        r = self.client.get('/no-limit/azili/prijava/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r['Location'])
```

### F2: POS Azil skin — provjeri CSS load
```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://limit-connect.com/static/css/apps/pos-azil.css
# Mora biti 200, ne 404
```

---

## BLOK G — PERFORMANCE (response time)

```bash
# Svaka stranica mora odgovoriti < 2s
for url in \
  "https://memio.pet/" \
  "https://memio.pet/registracija/" \
  "https://memio.pet/pas/191031000312345/" \
  "https://limit-connect.com/hr/login/" \
  "https://limit-connect.com/no-limit/"; do
  time=$(curl -s -o /dev/null -w "%{time_total}" "$url")
  echo "$time $url"
done
# Alarm ako > 2.0s
```

---

## BLOK H — SIGURNOST (ne smiješ preskočiti)

```bash
# 1. Admin URL nije /admin/ (randomiziran)
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/admin/
# Mora biti 404, NIKAD 200 ili 302

# 2. Debug=False
curl -s https://limit-connect.com/hr/NEPOSTOJI/ | grep -i "debug\|traceback\|django"
# Mora biti PRAZNO — ne smije curiti stack trace

# 3. Sensitive headers ne curiju
curl -sI https://limit-connect.com/ | grep -i "server\|x-powered"
# Ne smije pokazati "Python" ili "Django" verziju
```

---

## IZVRŠAVANJE

```bash
cd /var/www/fina-connect

# Pokreni sve testove
venv/bin/python manage.py test \
  memio_pet.tests \
  boxgram.tests \
  accounts.tests \
  pos.tests \
  --verbosity=2 \
  --keepdb \
  2>&1 | tee /tmp/qa_results.txt

# Shell testovi (curl blokovi gore)
# Performance test
# Sigurnosni test

# Na kraju: napiši QA_REPORT_07_04.md s rezultatima
# Format: PASS/FAIL po bloku + ukupna ocjena
```

---

## OUTPUT

Napiši `/var/www/fina-connect/QA_REPORT_07_04.md` sa:
- Rezultat svakog bloka (A-H): PASS / FAIL / WARN
- Broj testova: X/Y prošlo
- Kritični bugovi (FAIL) → odmah kreiraj CC_TASK_FIX_*.md
- Ukupna ocjena: X/10

Commitaj: `test(qa): inžinjerski QA report 07.04.2026.`
