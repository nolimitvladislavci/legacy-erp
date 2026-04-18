# CC TASK — FENIX V3 KICKOFF
**Agent: Claude Code (CC) | Koordinator: Sonnet | Odobrio: Ivan Brtan**
**Prioritet: KRITIČAN — Nova gradnja, paralelno sa starim**
**Stari sustav: /var/www/fina-connect/ — NE DIRAMO, samo referenca**
**Novi sustav: /var/www/fenix-v3/ — GRADIMO OVDJE**

---

## MISIJA

Novi Fenix. Ista baza znanja — nova arhitektura.
Cilj: 10x čišći kod, 10x brži UI, AI u svakom modulu.
Stack: Django 5.x + HTMX + Alpine.js + Tailwind + FastAPI AI sloj.

**Što prenosimo:** Poslovna logika, modeli, integracije, UI znanje.
**Što NE prenosimo:** Implementaciju, complexity 215, 568 templatea.

---

## KORAK 1 — Pripremi server (čitaj prvo, napravi sve)

```bash
# Provjeri slobodan prostor
df -h /var/www/

# Kreiraj novi projekt
mkdir -p /var/www/fenix-v3
cd /var/www/fenix-v3

# Python virtualenv
python3 -m venv venv
source venv/bin/activate

# Instaliraj core pakete
pip install django==5.1.* \
  psycopg2-binary \
  celery[redis] \
  gunicorn \
  whitenoise \
  django-htmx \
  pillow \
  python-dotenv \
  weasyprint \
  httpx \
  pydantic

# Provjeri verzije
python -m django --version
```

---

## KORAK 2 — Django projekt struktura

```bash
cd /var/www/fenix-v3
django-admin startproject config .

# Kreiraj strukturu
mkdir -p core/templates/components
mkdir -p core/static/css
mkdir -p core/static/js
mkdir -p modules
mkdir -p templates
mkdir -p tests
mkdir -p static

# App-ovi koje startamo odmah
python manage.py startapp accounts
python manage.py startapp companies
python manage.py startapp invoicing
python manage.py startapp arhiva
python manage.py startapp stolarija
python manage.py startapp pos
```

---

## KORAK 3 — BaseModel (piši jednom, koristiš zauvijek)

Kreiraj `/var/www/fenix-v3/core/base_model.py`:

```python
"""
Fenix v3 — BaseModel
Sve što svaki model treba. Piše se jednom.
"""
import uuid
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Nasljeđuju SVI modeli u Fenix v3.
    Nikad ne instancirati direktno.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])

    @classmethod
    def active(cls):
        return cls.objects.filter(is_deleted=False)


class TenantModel(BaseModel):
    """
    Za sve što pripada firmi (Company).
    Tenant isolation — uvijek filtriraj po company.
    """
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(app_label)s_%(class)ss"
    )

    class Meta:
        abstract = True

    @classmethod
    def for_company(cls, company):
        return cls.active().filter(company=company)
```

---

## KORAK 4 — BaseView (AI u svakom viewu automatski)

Kreiraj `/var/www/fenix-v3/core/base_view.py`:

```python
"""
Fenix v3 — BaseView
Nasljeđuju SVI viewovi. HTMX detekcija + AI endpoint + permisije.
"""
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404


class FenixView(LoginRequiredMixin, View):
    """
    Baza za sve viewove u Fenix v3.
    Automatski: HTMX detekcija, company scope, AI endpoint.
    """
    template_name = None
    htmx_template_name = None  # partial za HTMX swap

    def get_company(self):
        """Trenutna firma iz sessije."""
        from companies.models import Company
        company_id = self.request.session.get("active_company_id")
        if not company_id:
            return None
        return get_object_or_404(Company, id=company_id)

    def is_htmx(self):
        return bool(self.request.headers.get("HX-Request"))

    def render(self, request, context=None, template=None):
        """Smart render — vraća partial ako je HTMX, full page ako nije."""
        from django.shortcuts import render as django_render
        context = context or {}
        context["company"] = self.get_company()
        context["is_htmx"] = self.is_htmx()

        if self.is_htmx() and self.htmx_template_name:
            return django_render(request, self.htmx_template_name, context)
        return django_render(request, template or self.template_name, context)

    def json_ok(self, data=None):
        return JsonResponse({"status": "ok", **(data or {})})

    def json_error(self, message, status=400):
        return JsonResponse({"status": "error", "message": message}, status=status)


class PublicView(View):
    """Za javne stranice — bez login checka."""
    template_name = None

    def is_htmx(self):
        return bool(self.request.headers.get("HX-Request"))
```

---

## KORAK 5 — Settings (čist, bez legacy bagaža)

Kreiraj `/var/www/fenix-v3/config/settings.py`:

```python
"""
Fenix v3 — Settings
Čist start. Nema legacy nasljeđa.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Fenix v3
    "core",
    "accounts",
    "companies",
    "invoicing",
    "arhiva",
    "stolarija",
    "pos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "fenix_v3"),
        "USER": os.environ.get("DB_USER", "fenix_v3_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "hr"
TIME_ZONE = "Europe/Zagreb"
USE_I18N = True
USE_TZ = True
```

---

## KORAK 6 — Base template (200 linija, ne 568)

Kreiraj `/var/www/fenix-v3/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="hr" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Fenix{% endblock %} — LIMIT Connect</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
  {% block extra_head %}{% endblock %}
</head>
<body class="h-full bg-gray-50 dark:bg-gray-900"
      hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>

  <!-- Sidebar -->
  <div x-data="{ open: false }" class="flex h-full">
    <aside :class="open ? 'w-64' : 'w-16'"
           class="bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 flex flex-col">

      <!-- Logo -->
      <div class="flex items-center h-16 px-4 border-b border-gray-200 dark:border-gray-700">
        <span class="font-bold text-indigo-600 dark:text-indigo-400 text-lg" x-show="open">Fenix</span>
        <span class="font-bold text-indigo-600 dark:text-indigo-400 text-lg" x-show="!open">F</span>
      </div>

      <!-- Nav -->
      <nav class="flex-1 py-4 space-y-1 px-2">
        {% block sidebar_nav %}
        <a href="/dashboard/"
           class="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
          <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7h18M3 12h18M3 17h18"/>
          </svg>
          <span x-show="open">Dashboard</span>
        </a>
        {% endblock %}
      </nav>

      <!-- Toggle -->
      <button @click="open = !open"
              class="p-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors border-t border-gray-200 dark:border-gray-700">
        <svg class="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
    </aside>

    <!-- Main -->
    <div class="flex-1 flex flex-col overflow-hidden">

      <!-- Topbar -->
      <header class="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
        <div>
          {% if company %}
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ company.name }}</span>
          {% endif %}
        </div>
        <div class="flex items-center gap-4">
          <!-- AI Status -->
          <div id="ai-status" class="hidden">
            <div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
          </div>
          <!-- User -->
          <span class="text-sm text-gray-600 dark:text-gray-400">{{ request.user.get_full_name }}</span>
        </div>
      </header>

      <!-- Content -->
      <main class="flex-1 overflow-auto p-6">
        <!-- Toast poruke -->
        {% if messages %}
        <div id="messages" class="mb-4 space-y-2">
          {% for message in messages %}
          <div class="px-4 py-3 rounded-lg text-sm
            {% if message.tags == 'error' %}bg-red-50 text-red-700 border border-red-200
            {% elif message.tags == 'success' %}bg-green-50 text-green-700 border border-green-200
            {% else %}bg-blue-50 text-blue-700 border border-blue-200{% endif %}"
               x-data x-init="setTimeout(() => $el.remove(), 4000)">
            {{ message }}
          </div>
          {% endfor %}
        </div>
        {% endif %}

        {% block content %}{% endblock %}
      </main>
    </div>
  </div>

  {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## KORAK 7 — Baza podataka

```bash
# Kreiraj novu PostgreSQL bazu
sudo -u postgres psql -c "CREATE DATABASE fenix_v3;"
sudo -u postgres psql -c "CREATE USER fenix_v3_user WITH PASSWORD 'fenix_v3_secure_2026';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE fenix_v3 TO fenix_v3_user;"

# .env file
cat > /var/www/fenix-v3/.env << 'EOF'
DJANGO_SECRET_KEY=fenix-v3-secret-key-change-in-production-$(openssl rand -hex 32)
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,limit-connect.com
DB_NAME=fenix_v3
DB_USER=fenix_v3_user
DB_PASSWORD=fenix_v3_secure_2026
DB_HOST=localhost
DB_PORT=5432
EOF

# Migracije
cd /var/www/fenix-v3
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser --username admin --email admin@limit-connect.com --noinput
```

---

## KORAK 8 — Smoke test

```bash
# Pokretanje dev servera
cd /var/www/fenix-v3
source venv/bin/activate
python manage.py runserver 0.0.0.0:8001

# U drugom terminalu — provjeri da radi
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/
# Očekujemo: 302 (redirect na login) ili 200
```

---

## KORAK 9 — Nginx config za v3 (na posebnom portu, stari netaknut)

Kreiraj `/etc/nginx/sites-available/fenix-v3`:

```nginx
server {
    listen 8080;
    server_name limit-connect.com;

    location /static/ {
        alias /var/www/fenix-v3/staticfiles/;
    }
    location /media/ {
        alias /var/www/fenix-v3/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/fenix-v3 /etc/nginx/sites-enabled/
nginx -t && nginx -s reload
```

---

## KORAK 10 — Izvještaj

Napiši `/var/www/fenix-v3/FENIX_V3_STATUS.md`:

```markdown
# FENIX V3 — STATUS

## Datum pokretanja: [danas]
## Commit hash: [git log --oneline -1]

## Što radi
- [ ] Django projekt kreiran
- [ ] BaseModel implementiran
- [ ] BaseView implementiran
- [ ] Settings čist
- [ ] Base template radi
- [ ] Baza kreirana + migracije
- [ ] Dev server radi na portu 8001
- [ ] Nginx proxy na portu 8080

## Što slijedi (Rezervoar 2)
- Auth + Login flow (Antonio može ući)
- Dashboard (jedna stranica, čisti Tailwind)
- Company model (tenant isolation)

## Arhitekturne odluke
- Stack: Django 5.x + HTMX + Alpine + Tailwind
- BaseModel: UUID PK, soft delete, timestamps
- BaseView: HTMX detekcija, company scope, AI endpoint
- Templates: max 80 ukupno (ne 568)
- Modules: svaki max 300 linija
```

---

## ŠTO NE RADIŠ

- ❌ Ne mijenjaš /var/www/fina-connect/ (stari sustav)
- ❌ Ne kopiraš stari kod direktno — prepisuješ logiku čišće
- ❌ Ne dodaješ feature koji nije u ovom tasku
- ❌ Ne commitaš bez da server radi (smoke test mora proći)

---

## DEFINICIJA DONE

- [ ] `/var/www/fenix-v3/` postoji
- [ ] `python manage.py check` → 0 grešaka
- [ ] `python manage.py runserver` → radi
- [ ] BaseModel i BaseView kreiran i importiran
- [ ] Base template učitava Tailwind + HTMX + Alpine
- [ ] FENIX_V3_STATUS.md napisan
- [ ] Port 8001 odgovara

**Kad je sve zeleno — javi Sonetu: "Fenix v3 foundation ready."**
