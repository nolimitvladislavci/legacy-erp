# DeepSeek Analiza Kodebase
**Datum: 14.04.2026.**

---

## core/company_utils.py
*multi-tenant izolacija*

**Analiza Django koda (multi-tenant izolacija):**

1. **N+1 problem u `_is_umbrella_ancestor`**  
   Linije 20-22: `Company.objects.get(pk=current.umbrella_parent_id)` se izvršava u petlji (do 3 puta). Ako se ova funkcija poziva za više `child` objekata, generirat će pojedinačne upite za svaki nivo hijerarhije.  
   **Fix:** Prefetchaj `umbrella_parent` relacije u glavnom upitu ili koristi CTE/recursive query.

2. **Sigurnosna rupa - nedostatak autorizacije u `get_user_company`**  
   Linije 35-38: Superadmin može pristupiti bilo kojoj kompaniji prema `session` podatku bez provjere pripadnosti/dozvole.  
   **Fix:** Dodaj provjeru `request.user.has_perm('companies.view_company', company)` ili barem provjeru da je kompanija aktivna/neobrisana.

3. **Manjkava validacija session podataka**  
   Linije 30, 41: `company_id` i `umbrella_cid` se ne validiraju kao integeri. Session može biti manipuliran (npr. string "abc").  
   **Fix:** Dodaj `try: int(company_id)` ili koristi `get()` s default `None` i provjerom tipa.

4. **Dead code - neiskorišteni import i logika**  
   Linija 4: `logger` je importiran, ali se nigdje ne koristi. Također, linija 48: `umbrella_home_company` i `umbrella_home_name` se brišu, ali nije jasno gdje se postavljaju.  
   **Fix:** Ukloni neiskorišteni `logger` i pročitaj sve session ključeve u jedan dict za čišćenje.

5. **Anti-patern - direktno korištenje `ObjectDoesNotExist` umjesto specifičnog exceptiona**  
   Linije 36 i 44: Hvata se generički `ObjectDoesNotExist` umjesto `Company.DoesNotExist`. Ako drugi model baci isti exception, maskirat će se pravi uzrok.  
   **Fix:** Zamijeni s `except Company.DoesNotExist:` na oba mjesta.

---

## pos/trojstvo_task.py
*AI konsenzus arhitektura*

1. **N+1 upit u petlji** – Linije 58-62: `BookingSignature.objects.filter(user=s.author)` uzima sve zapise, a zatim se u petlji pristupa svakom objektu pojedinačno, što može uzrokovati N+1 problem ako se koriste povezani podaci.
   *Fix:* Dodaj `select_related` ili `prefetch_related` za povezane modele ako su potrebni, ili koristi `values_list` za direktan pristup poljima.

2. **Nedostaje validacija ulaznih podataka** – Linije 25-31: `suggestion_id` se ne provjerava prije korištenja (npr. da li je integer ili postoji u bazi), što može dovesti do iznimki ili sigurnosnih problema.
   *Fix:* Dodaj validaciju na početku funkcije (npr. `if not isinstance(suggestion_id, int): return`) i koristi Django's `get_object_or_404` za sigurno dohvaćanje.

3. **Potencijalni dead code** – Linije 13-14: `AGREED_LOG` i `CONFLICT_LOG` se deklariraju, ali se nigdje ne koriste u kodu, što ukazuje na neiskorištene varijable.
   *Fix:* Ukloni nepotrebne deklaracije ili implementiraj logiranje u te datoteke prema opisu toka.

4. **Sigurnosna rupa – izloženost osjetljivim podacima** – Linije 58-62: Dohvaćanje `BookingSignature` može izložiti osjetljive podatke o korisničkim akcijama bez provjere ovlasti, posebno ako se koristi u drugim kontekstima.
   *Fix:* Dodaj autorizaciju (npr. provjeru da li trenutni korisnik smije pristupiti tim podacima) ili ograniči podatke na javno sigurne informacije.

5. **Anti-patern – ručno upravljanje transakcijama bez obrade iznimki** – Linije 25-31: Transakcija se koristi samo za dohvaćanje i ažuriranje `ImprovementSuggestion`, ali se ne obrađuju sve potencijalne iznimke unutar transakcije, što može dovesti do zaglavljenih lockova.
   *Fix:* Proširi `try-ex

---

## invoicing/models.py
*Invoice model validacije*

**Analiza Django Invoice modela – ključni problemi:**

1. **Sigurnosna rupa – hardkodirani default za `client_token`**  
   `default=__import__("uuid").uuid4` koristi `__import__` unutar default vrijednosti, što može dovesti do neočekivanog ponašanja (npr. import prilikom migracija). Također, token se generira samo jednom prilikom kreiranja klase, umjesto po instanci.  
   **Fix:** Zamijeni s `default=uuid.uuid4` (kao za `uuid` polje).

2. **Manjkava validacija – nedosljedne dužine polja**  
   `client_name` ima `max_lengt` (greška u tipkanju – nedostaje `h`), što će uzrokovati `NameError`. Također, nedostaju definicije za `client_address`, `client_city` itd. (vidljivo iz prekinutog koda).  
   **Fix:** Ispravi u `max_length` i definiraj sva denormalizirana polja klijenta (npr. `max_length=200`).

3. **Potencijalni N+1 problem – nedostaju `select_related`/`prefetch_related` u manageru**  
   `CompanyManager` (naslijeđen) vjerojatno ne optimizira upite za povezane modele (npr. `User` za `created_by`). Ako se Invoice često dohvaća s podacima o korisniku, to će uzrokovati N+1 upite.  
   **Fix:** Dodaj u `CompanyManager.get_queryset()`:  
   ```python
   return super().get_queryset().select_related("created_by")
   ```

4. **Dead code – neiskorišteni `Decimal` import**  
   Import `Decimal` se ne koristi u modelu (nema polja tipa `DecimalField`). Ako nije potreban, predstavlja suvišan kod.  
   **Fix:** Ukloni `from decimal import Decimal` ili dodaj `DecimalField` za iznose (npr. `total_amount`).

5. **Anti-patern – denormalizacija bez mehanizma sinkronizacije**  
   Klijentski podaci (`client_name`, `client_address`, ...) denormalizirani su za PDF, ali nema `save()` metode ili signala koji osigurava da se ažuriraju ako se podaci o

---

## accounts/views.py
*auth i company switch*

**1. N+1 problem u `UserListView.get_queryset()`**  
**Problem:** U `select_related("profile", "profile__company")` nedostaje `"profile__company"` za superadmin upit, ali glavni N+1 je kod `UserProfile.objects.filter(company=company).values_list("user_id", flat=True)` koji izvršava zaseban upit za svakog korisnika umjesto JOIN-a.  
**Fix:** Zamijeni s `User.objects.filter(profile__company=company).select_related("profile", "profile__company")` za oba slučaja (superadmin i company).  

**2. Sigurnosna rupa – autorizacija u `user_edit`**  
**Problem:** `@user_passes_test(lambda u: u.is_superuser)` provjerava samo trenutnog korisnika, ali `target_user` može biti iz druge kompanije (nema provjere `get_user_company`). Superadmin može mijenjati bilo kog korisnika, što krši izolaciju kompanija.  
**Fix:** Dodaj provjeru `get_user_company(request) == target_user.profile.company` ako korisnik nije superadmin, ili eksplicitno ograniči superadmina na korisnike iz iste kompanije ako je to zahtjev.  

**3. Manjkava validacija u `user_edit` POST**  
**Problem:** Koristi `request.POST.get()` bez validacije (npr. `username` može biti dupliciran, email nije validiran). Nema CSRF zaštite u kodu (vjerojatno je u templateu, ali nije eksplicitno).  
**Fix:** Koristi Django `UserForm` ili `UserProfileForm` s `instance=target_user` i `data=request.POST`. Dodaj `@csrf_protect` dekorator.  

**4. Dead code / nepotpuna implementacija**  
**Problem:** U `user_edit` postoje importi (`BookingSignature`, `PasswordResetForm`) koji se ne koriste. Također, funkcija je prekinuta u sredini (`notify_password_change` nije implementirana).  
**Fix:** Ukloni neiskorištene importe. Dovrši implementaciju ili ukloni djelomični kod.  

**5. Anti-patern – ručno upravljanje transakcijama**  
**Problem:** `user_edit` ažurira `User` i `UserProfile` bez transakcije – ako jedan dio uspije, a drugi

---

## permissions/route_registry.py
*pristupna kontrola*

**Analiza Django RouteRegistry koda - sigurnosni problemi i anti-paterni:**

1. **Sigurnosna rupa: Nedefinirane rute imaju COMPANY default**  
   *Problem:* Neregistrirane rute automatski dobivaju `AccessLevel.COMPANY` što je previše permisivno. Ako developer zaboravi registrirati novu rutu, ona će biti dostupna svim korisnicima s company membership.  
   *Fix:* Promijeni default na `AccessLevel.ADMIN` ili `AccessLevel.SUPERADMIN` za "fail secure" pristup:  
   ```python
   def get_access_level(view_name):
       return ROUTE_REGISTRY.get(view_name, AccessLevel.ADMIN)
   ```

2. **Sigurnosna rupa: Nedostaje CSRF zahtjev za AJAX endpointima**  
   *Problem:* `fiscal_status_api` i `notification_api` označeni kao `AUTHENTICATED` ali bez eksplicitne CSRF zaštite. Ako su ovo POST/PUT/DELETE endpointi, ranjivi su na CSRF napade.  
   *Fix:* Dodaj `@csrf_protect` dekorator ili koristi `@ensure_csrf_cookie` za AJAX pozive koji mijenjaju stanje.

3. **Anti-patern: Enum vrijednosti se ne serializiraju za log/debug**  
   *Problem:* `AccessLevel` enum koristi `auto()` što generira nepredvidive vrijednosti. U logovima će se prikazivati kao `AccessLevel.1` umjesto čitljivih stringova.  
   *Fix:* Eksplicitno definiraj vrijednosti ili override `__str__`:  
   ```python
   class AccessLevel(Enum):
       PUBLIC = "PUBLIC"
       AUTHENTICATED = "AUTHENTICATED"
       # ... ostale
   ```

4. **Sigurnosna rupa: API endpointi bez rate limitinga**  
   *Problem:* `notification_api` (AJAX polling) i `panic_button` nemaju rate limiting što omogućava DoS napade ili brute force.  
   *Fix:* Implementiraj Django Ratelimit za osjetljive endpoint-e:  
   ```python
   from django_ratelimit.decorators import ratelimit
   @ratelimit(key='user', rate='10/m')
   ```

5. **Dead code/Nevalidirane rute: Nedostaje validacija view_name mappinga**  
   *Problem:* Nema mehanizma koji provjerava postoje li

---

## notifications/views.py
*notifikacije polling*

1. **N+1 problem u `notification_list`**  
   U `notification_list` viewu se koristi `Notification.objects.filter(recipient=request.user)[:100]`. Ako se u template-u pristupa povezanim objektima (npr. `notification.sender.profile`), može doći do N+1 upita.  
   **Fix:** Dodaj `select_related` ili `prefetch_related` ovisno o potrebama, npr. `.select_related("sender")`.

2. **Sigurnosna rupa: CSRF zaštićen samo `notification_mark_read` i `notification_mark_all_read`**  
   `notification_api` nije zaštićen CSRF tokenom, a koristi se za GET zahtjeve. Iako GET ne bi trebao mijenjati stanje, Django preporučuje CSRF zaštitu za sve autentificirane viewove. Ovdje nije kritično, ali je nedosljedno.  
   **Fix:** Dodaj `@csrf_protect` dekorator ili osiguraj da se ne izvršavaju mutacije preko GET-a (ovdje je samo čitanje, pa je prihvatljivo).

3. **Manjkava validacija: `notification_api` vraća `display_count` s maksimalnom vrijednošću 99 bez objašnjenja**  
   Ograničenje `display_count = min(unread, 99)` može zbuniti klijenta ako ima >99 nepročitanih notifikacija. To je više UX problem, ali može utjecati na funkcionalnost.  
   **Fix:** Dodaj komentar u kodu ili dokumentaciji zašto postoji limit, ili omogući klijentu da vidi točan broj.

4. **Dead code: Import `JsonResponse` unutar funkcije `notification_api`**  
   `from django.http import JsonResponse` je već importiran na vrhu datoteke, pa je ponovni import nepotreban.  
   **Fix:** Ukloni liniju `from django.http import JsonResponse` unutar funkcije.

5. **Anti-patern: Ručna serijalizacija `created_at` u ISO string**  
   U `notification_api`, `created_at` se ručno konvertira u ISO string. To je podložno greškama ako je polje `null`. Bolje je koristiti Django serijalizere ili `json.dumps` s Django encoderom.  
   **Fix:** Koristi `DjangoJSONEncoder` u `Json

---

## core/deepseek_client.py
*AI router*

**Analiza Django koda (AI router) - 5 ključnih problema:**

1. **Sigurnosna rupa: Hardkodirani AWS kredencijali u memoriji**
   - Problem: `getattr(settings, "AWS_ACCESS_KEY_ID", "")` vraća prazan string ako postavka ne postoji, što može uzrokovati neuspješnu autentikaciju ili neočekivano ponašanje
   - Fix: Dodaj eksplicitnu provjeru i bacanje iznimke:
   ```python
   aws_access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
   if not aws_access_key:
       raise RuntimeError("AWS_ACCESS_KEY_ID nije konfiguriran u postavkama")
   ```

2. **Manjkava validacija: Nedostatak sanitizacije model ID-a**
   - Problem: `model` parametar se prosljeđuje direktno u Bedrock API bez validacije
   - Fix: Dodaj whitelist validaciju:
   ```python
   ALLOWED_MODELS = {"deepseek-v3-2", "deepseek-v3-2-speciale"}
   if model not in ALLOWED_MODELS:
       raise ValueError(f"Nedozvoljeni model: {model}")
   ```

3. **Potencijalni N+1 problem u budućoj implementaciji**
   - Problem: Ako se ova funkcija poziva u petlji za više korisnika/promptova, svaki poziv stvara novi Bedrock klijent
   - Fix: Implementiraj caching klijenta:
   ```python
   from django.core.cache import cache
   
   def _get_bedrock_client():
       client = cache.get('bedrock_client')
       if not client:
           client = boto3.client(...)
           cache.set('bedrock_client', client, timeout=300)
       return client
   ```

4. **Dead code/neiskorišteni parametar**
   - Problem: `system` parametar se dodaje u `kwargs` ali se ne koristi u `messages` strukturi
   - Fix: Ispravno implementiraj system prompt:
   ```python
   messages = []
   if system:
       messages.append({"role": "system", "content": [{"text": system}]})
   messages.append({"role": "user", "content": [{"text": prompt}]})
   ```

5. **Anti-patern: Direktno uvoženje boto3 unutar funkcije**
   - Problem: `import boto3` unutar `_get_bedrock_client()` uzrokuje overhead pri svakom pozivu


---

## inventory/prediction_tasks.py
*Celery zadaci*

**Analiza Django/Celery koda - glavni problemi:**

1. **N+1 problem u petlji** (linije 28-45)  
   Svaki `item` zasebno poziva `predict_reorder()` i pristupa `item.supplier.name`.  
   **Fix:** Koristi `select_related('supplier')` i bulk operacije:
   ```python
   items = InventoryItem.objects.filter(...).select_related('supplier')
   predictions = predict_reorder_bulk(items)  # Bulk verzija
   ```

2. **Nepouzdana validacija float konverzije** (linije 39-42)  
   `float(item.quantity)` može baciti `ValueError` ako `quantity` nije numerički tip.  
   **Fix:** Koristi `Decimal` ili provjeri tip:
   ```python
   current_qty = float(item.quantity) if item.quantity else 0.0
   ```

3. **Potencijalna SQL injekcija kroz dinamičke parametre**  
   `predict_reorder()` možda koristi nesanitizirane podatke iz baze u raw SQL upitima.  
   **Fix:** Provjeri da `predict_reorder` koristi Django ORM/parametrizirane upite.

4. **Prekid transakcije pri izuzecima** (linije 26-27)  
   `Company.objects.filter(...).distinct()` može vratiti veliki broj kompanija - svaka greška u jednoj prekida cijeli zadatak.  
   **Fix:** Dodaj `transaction.atomic()` po kompaniji i bolje hendlovanje grešaka:
   ```python
   from django.db import transaction
   with transaction.atomic():
       # proces po kompaniji
   ```

5. **Dead code/neiskorišćeni podaci**  
   `po_ids` se generišu (linija 48) ali se nigdje ne koriste.  
   **Fix:** Izbaci varijablu ili dodaj logiku za praćenje generisanih PO.

---

## core/settings.py
*konfiguracija sigurnosti*

**Analiza Django sigurnosne konfiguracije – kritični problemi:**

1. **Nesigurno učitavanje .env datoteke**  
   Linije 11-20: Ručno parsiranje .env bez validacije ključeva ili vrijednosti.  
   **Fix:** Koristi `python-dotenv` ili `django-environ` s proper escapingom.

2. **CSRF_TRUSTED_ORIGINS sadrži HTTP izvore**  
   Linija 64: `http://37.27.248.86` i `http://127.0.0.1:8000` omogućuju CSRF napade ako se koriste u produkciji bez HTTPS.  
   **Fix:** Ukloni HTTP izvore ili ograniči na DEBUG mode:  
   ```python
   CSRF_TRUSTED_ORIGINS = [
       origin for origin in CSRF_TRUSTED_ORIGINS 
       if DEBUG or origin.startswith("https://")
   ]
   ```

3. **QR_HMAC_SECRET fallback na SECRET_KEY**  
   Linija 55: Ako `QR_HMAC_SECRET` nije postavljen, koristi `SECRET_KEY`, što narušava princip izolacije ključeva.  
   **Fix:** Zahtijevaj eksplicitnu vrijednost ili generiraj dedicated key:  
   ```python
   QR_HMAC_SECRET = os.environ["QR_HMAC_SECRET"]  # Bez fallbacka
   ```

4. **Preširoki ALLOWED_HOSTS**  
   Linije 24-41: `.limit-connect.com` dopušta sve subdomene (npr. `attacker.limit-connect.com`).  
   **Fix:** Eksplicitno navedi samo potrebne domene ili koristi wildcard samo za specifične slučajeve s dodatnom validacijom.

5. **DEBUG podešen preko env varijable bez type castinga**  
   Linija 22: `DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")` – može ostati aktiviran ako env sadrži npr. `"True "` (s razmakom).  
   **Fix:** Koristi stroži parser:  
   ```python
   DEBUG = os.getenv("DEBUG", "false").strip().lower() == "true"
   ```

---
