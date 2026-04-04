# CC TASK: MEMIO_PET BUG SPRINT
Datum: 04.04.2026. | Rok: 04.04.2026. (danas)
Prioritet: KRITIČNO — 6 aktivnih Sentry grešaka

PRAVILO: READ models.py/views.py PRIJE svakog WRITE.
PRAVILO: Nakon svakog fixa — `venv/bin/python manage.py check 2>&1 | tail -3`
PRAVILO: Na kraju — `systemctl restart gunicorn-fina`

---

## BUG-1: NameError: login_required not defined
Sentry: LIMIT-CONNECT-K (20:39, jučer)
Lokacija: negdje u memio_pet/ (views ili security)

KORAK 1:
EXEC: grep -rn "login_required" /var/www/fina-connect/memio_pet/ --include="*.py" | grep -v "import\|#"

Ako nađeš upotrebu login_required bez importa na vrhu fajla:
KORAK 2:
READ: taj fajl (prvih 20 linija)
WRITE: dodaj `from django.contrib.auth.decorators import login_required` u imports

---

## BUG-2: ProgrammingError: must be owner of table memio_pet_waitlistentry
Sentry: LIMIT-CONNECT-M (20:47, jučer)
Uzrok: tablica kreirana od strane drugog DB usera (nije memio_pets_user)

KORAK 1 — Saznaj tko je owner:
EXEC: psql -h 127.0.0.1 -U memio_pets_user -d fina_connect -c "SELECT tableowner FROM pg_tables WHERE tablename LIKE 'memio_pet%' ORDER BY tablename;" 2>&1

KORAK 2 — Ako owner nije memio_pets_user, pokreni kao postgres:
EXEC: psql -h 127.0.0.1 -d fina_connect -U postgres -c "ALTER TABLE memio_pet_waitlistentry OWNER TO memio_pets_user; GRANT ALL ON memio_pet_waitlistentry TO memio_pets_user;" 2>&1

Ako postgres login ne radi direktno, pronađi connection string iz:
EXEC: grep "MEMIO_PETS_DB" /var/www/fina-connect/.env

KORAK 3 — Provjeri sve memio_pet tablice odjednom:
EXEC: psql -h 127.0.0.1 -d fina_connect -U postgres -c "SELECT 'ALTER TABLE ' || tablename || ' OWNER TO memio_pets_user;' FROM pg_tables WHERE tablename LIKE 'memio_pet%';" 2>&1
Izvedi sve generirane ALTER TABLE naredbe.

---

## BUG-3: IntegrityError: duplicate key breederreview
Sentry: LIMIT-CONNECT-V (07:19, danas)
Lokacija: memio_pet - BreederReview creation
Model: unique_together = [("breeder", "reviewer_name")]

KORAK 1:
READ: /var/www/fina-connect/memio_pet/views.py
Traži sve mjesta gdje se kreira BreederReview (filter: BreederReview.objects.create)

KORAK 2:
Zamijeni `BreederReview.objects.create(...)` s:
`BreederReview.objects.get_or_create(breeder=X, reviewer_name=Y, defaults={...})`

Ili dodaj try/except IntegrityError koji vraća JSON error 409 umjesto 500.

KORAK 3:
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -3

---

## BUG-4: AttributeError: Livestock has no attribute PET_VRSTE
Sentry: LIMIT-CONNECT-J (18:20, jučer)
Lokacija: livestock/models.py linija 28 — PET_VRSTE je tuple, ne class attribute dostupan izvana kako se očekuje

KORAK 1:
READ: /var/www/fina-connect/livestock/models.py (linije 1-50)
READ: grep -rn "Livestock.PET_VRSTE\|livestock.*PET_VRSTE" /var/www/fina-connect/ --include="*.py"

KORAK 2:
Ako se Livestock.PET_VRSTE koristi kao class attribute izvana (npr. u memio_pet):
- U livestock/models.py provjeri je li PET_VRSTE definiran na klasi (ne unutar metode)
- Ako je unutar metode — premjesti na class level kao class attribute

KORAK 3:
EXEC: cd /var/www/fina-connect && venv/bin/python -c "from livestock.models import Livestock; print(Livestock.PET_VRSTE)" 2>&1

---

## BUG-5: TypeError: Http404 object does not support item assignment
Sentry: LIMIT-CONNECT-S (03:00, danas)
Tipičan uzrok: kod radi dict["key"] = value na objektu koji je Http404

KORAK 1:
EXEC: grep -rn "Http404\|\[.*\] = " /var/www/fina-connect/memio_pet/views.py | head -20

Traži pattern gdje se Http404 pohranjuje u varijablu i zatim se radi item assignment na toj varijabli.
Ili: context["key"] = raise Http404(...) pattern.

KORAK 2:
READ: memio_pet/views.py oko linije gdje se greška javlja (stack trace u Sentryju pokazuje liniju)
Fix: razdvoji raise Http404 od dict assignmenta, ili vrati prazan context ako 404.

---

## BUG-6: RuntimeError: ASGI http.response.body
Sentry: LIMIT-CONNECT-N (22:16, jučer)
Uzrok: WSGI/ASGI mismatch — neki view vraća async response ali Gunicorn radi u WSGI modu

KORAK 1:
EXEC: grep -rn "async def\|asyncio\|StreamingHttpResponse\|sync_to_async" /var/www/fina-connect/memio_pet/ --include="*.py" | head -20

KORAK 2:
Ako nađeš `async def` view u memio_pet koji nije wrappan s `sync_to_async`:
- Ili makni `async` prefix (pretvorit u sync view)
- Ili dodaj `from asgiref.sync import sync_to_async` i koristi properly

KORAK 3:
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -3

---

## FINALNI KORAK (obavezno):
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5 && curl -s -o /dev/null -w "HTTP %{http_code}" https://limit-connect.com/
Mora vratiti HTTP 302.

EXEC: cd /var/www/fina-connect && git add -A && git commit -m "fix(memio_pet): 6 Sentry bugova — BUG-1 do BUG-6"

DONE kriterij:
- manage.py check: 0 errors
- gunicorn aktivan
- https://limit-connect.com/ vraća 302
- git commit postoji
