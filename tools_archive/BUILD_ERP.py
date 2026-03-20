#!/usr/bin/env python3
"""
LIMIT CONNECT ERP - KOMPLETNI BUILDER
Ova skripta gradi cijeli ERP sustav iz PostgreSQL baze.
"""
import os, sys, re, subprocess, textwrap

BASE_DIR = "/var/www/fina-connect"
os.chdir(BASE_DIR)
os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"

DB = {
    "NAME": os.environ.get("DB_NAME", "postgres"),
    "USER": os.environ.get("DB_USER", "viskovic_user"),
    "PASS": os.environ.get("DB_PASS", "Viskovic123!"),
    "HOST": os.environ.get("DB_HOST", "localhost"),
    "PORT": os.environ.get("DB_PORT", "5432"),
}
ADMIN = {
    "USER": os.environ.get("ADMIN_USER", "admin"),
    "EMAIL": os.environ.get("ADMIN_EMAIL", "viskovic.bau@gmail.com"),
    "PASS": os.environ.get("ADMIN_PASS", "Viskovic123!"),
}

# ── Mapiranje tablica → moduli (SVE tablice, uključujući prethodno preskočene)
TABLE_MODULE_MAP = {
    # accounts
    "auth_group":                   "accounts",
    "auth_group_permissions":       "accounts",
    "auth_permission":              "accounts",
    "auth_user":                    "accounts",
    "auth_user_groups":             "accounts",
    "auth_user_user_permissions":   "accounts",
    "core_userprofile":             "accounts",
    # appointments
    "appointments_appointment":     "appointments",
    # companies
    "companies_company":            "companies",
    # documents
    "documents_document":           "documents",
    # finance
    "finance_transaction":          "finance",
    "finance_account":              "finance",
    # fitness
    "fitness_member":               "fitness",
    # insurance
    "insurance_policy":             "insurance",
    # inventory
    "inventory_item":               "inventory",
    "inventory_movement":           "inventory",
    # invoicing
    "invoicing_invoice":            "invoicing",
    "invoicing_invoiceitem":        "invoicing",
    # partners
    "partners_partner":             "partners",
    "partners_partnerdocument":     "partners",
    "partners_partnerrecord":       "partners",
    # rental
    "rental_booking":               "rental",
    "rental_equipment":             "rental",
    "rental_property":              "rental",
    # webshop
    "webshop_order":                "webshop",
    "webshop_orderitem":            "webshop",
    "webshop_product":              "webshop",
    # worktime
    "worktime_employeeprofile":     "worktime",
    "worktime_project":             "worktime",
    "worktime_timeentry":           "worktime",
    "worktime_workgroup":           "worktime",
    "worktime_workgroup_members":   "worktime",
}

# Svi moduli
ALL_APPS = sorted(set(TABLE_MODULE_MAP.values()))
# Dodajemo insurance koji možda nije bio u originalnoj listi
if "insurance" not in ALL_APPS:
    ALL_APPS.append("insurance")
ALL_APPS = sorted(set(ALL_APPS))

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(content))

def append(path, content):
    with open(path, "a") as f:
        f.write(textwrap.dedent(content))

# ════════════════════════════════════════════════════════════
# KORAK 1: settings.py
# ════════════════════════════════════════════════════════════
print("  [1/10] Pisanje settings.py...")
write(f"{BASE_DIR}/core/settings.py", f"""
    import os
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent
    SECRET_KEY = 'fina-connect-erp-secret-key-2026-production'
    DEBUG = False
    ALLOWED_HOSTS = ['*']

    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'rest_framework',
        'import_export',
        {", ".join([f"'{a}'" for a in ALL_APPS])},
    ]

    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        'whitenoise.middleware.WhiteNoiseMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

    ROOT_URLCONF = 'core.urls'

    TEMPLATES = [{{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }}]

    WSGI_APPLICATION = 'core.wsgi.application'

    DATABASES = {{
        'default': {{
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': '{DB["NAME"]}',
            'USER': '{DB["USER"]}',
            'PASSWORD': '{DB["PASS"]}',
            'HOST': '{DB["HOST"]}',
            'PORT': '{DB["PORT"]}',
        }}
    }}

    AUTH_PASSWORD_VALIDATORS = []

    LANGUAGE_CODE = 'hr'
    TIME_ZONE = 'Europe/Zagreb'
    USE_I18N = True
    USE_TZ = True

    STATIC_URL = '/static/'
    STATIC_ROOT = BASE_DIR / 'static'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

    DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

    LOGIN_URL = '/login/'
    LOGIN_REDIRECT_URL = '/'
    LOGOUT_REDIRECT_URL = '/login/'

    # Jazzmin nije dostupan na ovom serveru
    REST_FRAMEWORK = {{
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.SessionAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
        'PAGE_SIZE': 50,
    }}
""")

# ════════════════════════════════════════════════════════════
# KORAK 2: Kreiranje app direktorija i __init__.py
# ════════════════════════════════════════════════════════════
print("  [2/10] Kreiranje app direktorija...")
for app in ALL_APPS:
    os.makedirs(f"{BASE_DIR}/{app}", exist_ok=True)
    for fname in ["__init__.py"]:
        path = f"{BASE_DIR}/{app}/{fname}"
        if not os.path.exists(path):
            open(path, "w").close()

# ════════════════════════════════════════════════════════════
# KORAK 3: inspectdb → distribucija modela
# ════════════════════════════════════════════════════════════
print("  [3/10] Čitanje strukture baze (inspectdb)...")
venv_py = f"{BASE_DIR}/venv/bin/python3"

# Privremeni settings za inspectdb
tmp_settings = f"""
import os
from pathlib import Path
BASE_DIR = Path('{BASE_DIR}')
SECRET_KEY = 'tmp'
DEBUG = True
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.auth']
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '{DB["NAME"]}',
        'USER': '{DB["USER"]}',
        'PASSWORD': '{DB["PASS"]}',
        'HOST': '{DB["HOST"]}',
        'PORT': '{DB["PORT"]}',
    }}
}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
"""
with open(f"{BASE_DIR}/tmp_settings.py", "w") as f:
    f.write(tmp_settings)

result = subprocess.run(
    [venv_py, "manage.py", "inspectdb", "--settings=tmp_settings"],
    capture_output=True, text=True, cwd=BASE_DIR
)
raw_models = result.stdout
if result.returncode != 0:
    print(f"  ⚠ inspectdb upozorenje: {result.stderr[:200]}")

# Inicijalizacija models.py za svaki app
for app in ALL_APPS:
    write(f"{BASE_DIR}/{app}/models.py",
        "from django.db import models\n"
        "from django.contrib.auth.models import User\n\n"
    )

# Parsiranje i distribucija klasa
classes = re.split(r"(?=^class )", raw_models, flags=re.MULTILINE)
distributed = 0
skipped = []

for cls_block in classes:
    if not cls_block.strip().startswith("class "):
        continue

    # Izvuci ime tablice iz db_table
    table_match = re.search(r"db_table\s*=\s*['\"]([^'\"]+)['\"]", cls_block)
    if not table_match:
        continue
    table_name = table_match.group(1)

    # Fix ForeignKey referenci (bez navodnika → s navodnicima)
    cls_block = re.sub(
        r"models\.(ForeignKey|OneToOneField|ManyToManyField)\(([A-Z][a-zA-Z0-9_]+),",
        r"models.\1('\2',",
        cls_block
    )
    # Dodaj managed = False za tablice koje već postoje u bazi
    if "managed = False" not in cls_block and "class Meta:" in cls_block:
        cls_block = cls_block.replace(
            "class Meta:",
            "class Meta:\n        managed = False"
        )

    target_app = TABLE_MODULE_MAP.get(table_name)
    if target_app:
        append(f"{BASE_DIR}/{target_app}/models.py", cls_block + "\n")
        distributed += 1
        print(f"      → {table_name} ⟶ {target_app}")
    else:
        skipped.append(table_name)

if skipped:
    print(f"  ℹ Preskočeno (Django internali): {', '.join(skipped)}")
print(f"  ✓ Distribuirano {distributed} modela")

# Čišćenje tmp settings
os.remove(f"{BASE_DIR}/tmp_settings.py")

# ════════════════════════════════════════════════════════════
# KORAK 4: Admin registracija za svaki modul
# ════════════════════════════════════════════════════════════
print("  [4/10] Kreiranje admin.py za sve module...")
for app in ALL_APPS:
    models_path = f"{BASE_DIR}/{app}/models.py"
    with open(models_path, "r") as f:
        content = f.read()
    model_names = re.findall(r"^class\s+([A-Z][a-zA-Z0-9_]+)\(models\.Model\):", content, re.MULTILINE)

    admin_content = (
        "from django.contrib import admin\n"
        "from import_export.admin import ImportExportModelAdmin\n"
        "from import_export import resources\n"
        "from .models import *\n\n"
    )
    for name in model_names:
        admin_content += f"""
class {name}Resource(resources.ModelResource):
    class Meta:
        model = {name}
        skip_unchanged = True
        report_skipped = False

@admin.register({name})
class {name}Admin(ImportExportModelAdmin):
    resource_class = {name}Resource
    list_per_page = 50
    show_full_result_count = False

"""
    write(f"{BASE_DIR}/{app}/admin.py", admin_content)

print(f"  ✓ Admin registracija završena")

# ════════════════════════════════════════════════════════════
# KORAK 5: apps.py za svaki modul
# ════════════════════════════════════════════════════════════
print("  [5/10] Kreiranje apps.py...")
for app in ALL_APPS:
    write(f"{BASE_DIR}/{app}/apps.py", f"""
        from django.apps import AppConfig

        class {app.capitalize()}Config(AppConfig):
            default_auto_field = 'django.db.models.BigAutoField'
            name = '{app}'
            verbose_name = '{app.capitalize()}'
    """)
    write(f"{BASE_DIR}/{app}/__init__.py", f"default_app_config = '{app}.apps.{app.capitalize()}Config'\n")

# ════════════════════════════════════════════════════════════
# KORAK 6: Views + URLs za svaki modul (s API endpointima)
# ════════════════════════════════════════════════════════════
print("  [6/10] Kreiranje views.py i urls.py za sve module...")

for app in ALL_APPS:
    models_path = f"{BASE_DIR}/{app}/models.py"
    with open(models_path, "r") as f:
        content = f.read()
    model_names = re.findall(r"^class\s+([A-Z][a-zA-Z0-9_]+)\(models\.Model\):", content, re.MULTILINE)

    # Generiranje serializers
    serializers_content = (
        "from rest_framework import serializers\n"
        "from .models import *\n\n"
    )
    for name in model_names:
        serializers_content += f"""
class {name}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {name}
        fields = '__all__'
"""
    write(f"{BASE_DIR}/{app}/serializers.py", serializers_content)

    # Generiranje views
    views_content = (
        "from django.shortcuts import render, get_object_or_404\n"
        "from django.contrib.auth.decorators import login_required\n"
        "from django.utils.decorators import method_decorator\n"
        "from rest_framework import viewsets, permissions\n"
        "from rest_framework.response import Response\n"
        "from .models import *\n"
        "from .serializers import *\n\n"
    )
    for name in model_names:
        views_content += f"""
class {name}ViewSet(viewsets.ModelViewSet):
    queryset = {name}.objects.all()
    serializer_class = {name}Serializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = '__all__'
"""
    # Dodajemo HTML index view
    views_content += f"""

@login_required
def index(request):
    context = {{}}
    return render(request, '{app}/index.html', context)
"""
    write(f"{BASE_DIR}/{app}/views.py", views_content)

    # Generiranje urls
    urls_content = (
        "from django.urls import path, include\n"
        "from rest_framework.routers import DefaultRouter\n"
        "from . import views\n\n"
        "router = DefaultRouter()\n"
    )
    for name in model_names:
        urls_content += f"router.register(r'{name.lower()}', views.{name}ViewSet)\n"
    urls_content += (
        "\nurlpatterns = [\n"
        f"    path('', views.index, name='{app}_index'),\n"
        "    path('api/', include(router.urls)),\n"
        "]\n"
    )
    write(f"{BASE_DIR}/{app}/urls.py", urls_content)

# ════════════════════════════════════════════════════════════
# KORAK 7: Core views (dashboard) i core URLs
# ════════════════════════════════════════════════════════════
print("  [7/10] Kreiranje core views i URL konfiguracije...")

# Dashboard view koji dohvaća stvarne podatke
write(f"{BASE_DIR}/core/views.py", """
    from django.shortcuts import render, redirect
    from django.contrib.auth import authenticate, login, logout
    from django.contrib.auth.decorators import login_required
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from django.apps import apps

    def login_view(request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        error = None
        if request.method == 'POST':
            user = authenticate(request,
                username=request.POST.get('username'),
                password=request.POST.get('password'))
            if user:
                login(request, user)
                return redirect(request.GET.get('next', '/'))
            error = 'Pogrešno korisničko ime ili lozinka.'
        return render(request, 'login.html', {'error': error})

    def logout_view(request):
        logout(request)
        return redirect('/login/')

    @login_required
    def dashboard(request):
        ctx = {}

        # Partneri
        try:
            Partner = apps.get_model('partners', 'Partner')
            ctx['broj_partnera'] = Partner.objects.count()
        except Exception:
            ctx['broj_partnera'] = 0

        # Fakture
        try:
            Invoice = apps.get_model('invoicing', 'InvoicingInvoice')
        except Exception:
            try:
                Invoice = apps.get_model('invoicing', 'Invoice')
            except Exception:
                Invoice = None

        if Invoice:
            try:
                ctx['ukupno_fakturirano'] = Invoice.objects.aggregate(
                    s=Sum('total_amount'))['s'] or 0
                ctx['neplaceno'] = Invoice.objects.filter(
                    status='UNPAID').aggregate(s=Sum('total_amount'))['s'] or 0
                ctx['zadnje_fakture'] = Invoice.objects.order_by('-id')[:5]
            except Exception:
                ctx['ukupno_fakturirano'] = 0
                ctx['neplaceno'] = 0
                ctx['zadnje_fakture'] = []
        else:
            ctx['ukupno_fakturirano'] = 0
            ctx['neplaceno'] = 0
            ctx['zadnje_fakture'] = []

        # Worktime
        try:
            TimeEntry = apps.get_model('worktime', 'WorktimeTimeentry')
        except Exception:
            try:
                TimeEntry = apps.get_model('worktime', 'TimeEntry')
            except Exception:
                TimeEntry = None

        if TimeEntry:
            try:
                ctx['sati_ovaj_tjedan'] = TimeEntry.objects.filter(
                    date__gte=timezone.now().date() - timezone.timedelta(days=7)
                ).aggregate(s=Sum('hours'))['s'] or 0
            except Exception:
                ctx['sati_ovaj_tjedan'] = 0
        else:
            ctx['sati_ovaj_tjedan'] = 0

        # Fitness
        try:
            Member = apps.get_model('fitness', 'FitnessMember')
        except Exception:
            try:
                Member = apps.get_model('fitness', 'Member')
            except Exception:
                Member = None
        ctx['fitness_clanova'] = Member.objects.count() if Member else 0

        # Webshop
        try:
            Order = apps.get_model('webshop', 'WebshopOrder')
        except Exception:
            try:
                Order = apps.get_model('webshop', 'Order')
            except Exception:
                Order = None
        ctx['webshop_narudžbi'] = Order.objects.count() if Order else 0

        # Rental
        try:
            Booking = apps.get_model('rental', 'RentalBooking')
        except Exception:
            try:
                Booking = apps.get_model('rental', 'Booking')
            except Exception:
                Booking = None
        ctx['aktivnih_iznajmljivanja'] = Booking.objects.count() if Booking else 0

        return render(request, 'dashboard.html', ctx)
""")

# Core URLs
urls_content = (
    "from django.contrib import admin\n"
    "from django.urls import path, include\n"
    "from django.conf import settings\n"
    "from django.conf.urls.static import static\n"
    "from . import views\n\n"
    "urlpatterns = [\n"
    "    path('admin/', admin.site.urls),\n"
    "    path('login/', views.login_view, name='login'),\n"
    "    path('logout/', views.logout_view, name='logout'),\n"
    "    path('', views.dashboard, name='dashboard'),\n"
)
for app in ALL_APPS:
    urls_content += f"    path('{app}/', include('{app}.urls')),\n"
urls_content += (
    "] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)\n"
)
write(f"{BASE_DIR}/core/urls.py", urls_content)

# ════════════════════════════════════════════════════════════
# KORAK 8: Templates
# ════════════════════════════════════════════════════════════
print("  [8/10] Kreiranje HTML predložaka...")
os.makedirs(f"{BASE_DIR}/templates", exist_ok=True)

# base.html
write(f"{BASE_DIR}/templates/base.html", """
<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}LIMIT CONNECT ERP{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --sidebar-bg: #0f172a;
            --sidebar-hover: #1e293b;
            --accent: #3b82f6;
            --accent-light: #dbeafe;
        }
        body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #f1f5f9; display: flex; min-height: 100vh; }
        /* Sidebar */
        .sidebar {
            width: 260px; min-height: 100vh; background: var(--sidebar-bg);
            color: #cbd5e1; display: flex; flex-direction: column; flex-shrink: 0;
            position: sticky; top: 0; height: 100vh; overflow-y: auto;
        }
        .sidebar-brand {
            padding: 24px 20px 16px; border-bottom: 1px solid #1e293b;
            font-size: 1.2rem; font-weight: 700; color: white; letter-spacing: 0.5px;
        }
        .sidebar-brand span { color: var(--accent); }
        .sidebar-section { padding: 8px 12px; font-size: 0.7rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1.5px; color: #475569; margin-top: 8px; }
        .sidebar a {
            display: flex; align-items: center; gap: 10px;
            padding: 10px 16px; color: #94a3b8; text-decoration: none;
            border-radius: 8px; margin: 2px 8px; font-size: 0.875rem; transition: all 0.15s;
        }
        .sidebar a:hover, .sidebar a.active {
            background: var(--sidebar-hover); color: white;
        }
        .sidebar a i { width: 18px; text-align: center; }
        .sidebar-footer { margin-top: auto; padding: 16px; border-top: 1px solid #1e293b; }
        /* Main */
        .main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
        .topbar {
            background: white; border-bottom: 1px solid #e2e8f0;
            padding: 12px 24px; display: flex; align-items: center;
            justify-content: space-between; position: sticky; top: 0; z-index: 100;
        }
        .topbar-title { font-weight: 600; color: #0f172a; font-size: 1.1rem; }
        .content { padding: 28px; flex: 1; }
        /* Cards */
        .stat-card {
            background: white; border-radius: 12px; padding: 20px 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
        }
        .stat-card .label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
            letter-spacing: 1px; color: #64748b; margin-bottom: 8px; }
        .stat-card .value { font-size: 2rem; font-weight: 700; color: #0f172a; }
        .stat-card .icon { width: 48px; height: 48px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center; font-size: 1.3rem; }
        /* Alerts */
        .messages-wrap { position: fixed; top: 70px; right: 20px; z-index: 9999; width: 340px; }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
<div class="sidebar">
    <div class="sidebar-brand">FINA-<span>CONNECT</span></div>
    <div class="sidebar-section">Glavni izbornik</div>
    <a href="/" class="{% if request.path == '/' %}active{% endif %}">
        <i class="fas fa-chart-pie"></i> Dashboard
    </a>
    <div class="sidebar-section">Poslovanje</div>
    <a href="/partners/" class="{% if '/partners/' in request.path %}active{% endif %}">
        <i class="fas fa-handshake"></i> Partneri
    </a>
    <a href="/invoicing/" class="{% if '/invoicing/' in request.path %}active{% endif %}">
        <i class="fas fa-file-invoice-dollar"></i> Fakturiranje
    </a>
    <a href="/documents/" class="{% if '/documents/' in request.path %}active{% endif %}">
        <i class="fas fa-folder-open"></i> Dokumenti
    </a>
    <a href="/companies/" class="{% if '/companies/' in request.path %}active{% endif %}">
        <i class="fas fa-building"></i> Tvrtke
    </a>
    <div class="sidebar-section">Operacije</div>
    <a href="/worktime/" class="{% if '/worktime/' in request.path %}active{% endif %}">
        <i class="fas fa-clock"></i> Radno Vrijeme
    </a>
    <a href="/appointments/" class="{% if '/appointments/' in request.path %}active{% endif %}">
        <i class="fas fa-calendar-check"></i> Termini
    </a>
    <a href="/inventory/" class="{% if '/inventory/' in request.path %}active{% endif %}">
        <i class="fas fa-boxes"></i> Skladište
    </a>
    <div class="sidebar-section">Specijalni moduli</div>
    <a href="/webshop/" class="{% if '/webshop/' in request.path %}active{% endif %}">
        <i class="fas fa-shopping-cart"></i> Webshop
    </a>
    <a href="/rental/" class="{% if '/rental/' in request.path %}active{% endif %}">
        <i class="fas fa-key"></i> Najam
    </a>
    <a href="/fitness/" class="{% if '/fitness/' in request.path %}active{% endif %}">
        <i class="fas fa-dumbbell"></i> Fitness
    </a>
    <a href="/finance/" class="{% if '/finance/' in request.path %}active{% endif %}">
        <i class="fas fa-chart-line"></i> Financije
    </a>
    <a href="/insurance/" class="{% if '/insurance/' in request.path %}active{% endif %}">
        <i class="fas fa-shield-alt"></i> Osiguranje
    </a>
    <div class="sidebar-footer">
        <a href="/admin/" target="_blank">
            <i class="fas fa-tools"></i> Admin Panel
        </a>
        <a href="/logout/">
            <i class="fas fa-sign-out-alt"></i> Odjava
        </a>
    </div>
</div>
<div class="main">
    <div class="topbar">
        <span class="topbar-title">{% block page_title %}LIMIT CONNECT ERP{% endblock %}</span>
        <div class="d-flex align-items-center gap-3">
            <span class="text-muted small">{{ request.user.get_full_name|default:request.user.username }}</span>
            <i class="fas fa-user-circle text-secondary fs-5"></i>
        </div>
    </div>
    <div class="content">
        {% if messages %}
        <div class="messages-wrap">
            {% for msg in messages %}
            <div class="alert alert-{{ msg.tags }} alert-dismissible fade show shadow-sm" role="alert">
                {{ msg }} <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        {% block content %}{% endblock %}
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
{% block extra_js %}{% endblock %}
</body>
</html>
""")

# login.html
write(f"{BASE_DIR}/templates/login.html", """
<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LIMIT CONNECT - Prijava</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0f172a; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .login-box {
            background: white; border-radius: 16px; padding: 40px; width: 100%; max-width: 420px;
            box-shadow: 0 25px 60px rgba(0,0,0,0.4);
        }
        .brand { font-size: 1.8rem; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
        .brand span { color: #3b82f6; }
        .subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 28px; }
        .form-control { padding: 12px 16px; border-radius: 10px; border: 1.5px solid #e2e8f0; }
        .form-control:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }
        .btn-login {
            background: #3b82f6; color: white; border: none;
            padding: 13px; border-radius: 10px; width: 100%; font-weight: 600;
        }
        .btn-login:hover { background: #2563eb; color: white; }
        label { font-size: 0.85rem; font-weight: 600; color: #374151; margin-bottom: 6px; }
    </style>
</head>
<body>
<div class="login-box">
    <div class="brand">FINA-<span>CONNECT</span></div>
    <div class="subtitle">ERP Sustav upravljanja poslovanjem</div>
    {% if error %}
    <div class="alert alert-danger">{{ error }}</div>
    {% endif %}
    <form method="post">
        {% csrf_token %}
        <div class="mb-3">
            <label>Korisničko ime</label>
            <input type="text" name="username" class="form-control" required autofocus>
        </div>
        <div class="mb-4">
            <label>Lozinka</label>
            <input type="password" name="password" class="form-control" required>
        </div>
        <button type="submit" class="btn btn-login">Prijava &rarr;</button>
    </form>
</div>
</body>
</html>
""")

# dashboard.html
write(f"{BASE_DIR}/templates/dashboard.html", """
{% extends 'base.html' %}
{% block title %}Dashboard - LIMIT CONNECT{% endblock %}
{% block page_title %}Operativni Centar{% endblock %}
{% block content %}

<div class="row g-3 mb-4">
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Ukupno fakturirano</div>
                <div class="value">{{ ukupno_fakturirano|floatformat:2 }} €</div>
            </div>
            <div class="icon" style="background:#dbeafe;color:#3b82f6"><i class="fas fa-file-invoice-dollar"></i></div>
        </div>
    </div>
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Neplaćeno</div>
                <div class="value text-danger">{{ neplaceno|floatformat:2 }} €</div>
            </div>
            <div class="icon" style="background:#fee2e2;color:#ef4444"><i class="fas fa-exclamation-triangle"></i></div>
        </div>
    </div>
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Partneri</div>
                <div class="value">{{ broj_partnera }}</div>
            </div>
            <div class="icon" style="background:#dcfce7;color:#22c55e"><i class="fas fa-handshake"></i></div>
        </div>
    </div>
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Sati (7 dana)</div>
                <div class="value">{{ sati_ovaj_tjedan|floatformat:1 }} h</div>
            </div>
            <div class="icon" style="background:#fef3c7;color:#f59e0b"><i class="fas fa-clock"></i></div>
        </div>
    </div>
</div>

<div class="row g-3 mb-4">
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Fitness članova</div>
                <div class="value">{{ fitness_clanova }}</div>
            </div>
            <div class="icon" style="background:#ede9fe;color:#8b5cf6"><i class="fas fa-dumbbell"></i></div>
        </div>
    </div>
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Webshop narudžbi</div>
                <div class="value">{{ webshop_narudžbi }}</div>
            </div>
            <div class="icon" style="background:#ffedd5;color:#f97316"><i class="fas fa-shopping-cart"></i></div>
        </div>
    </div>
    <div class="col-xl-3 col-md-6">
        <div class="stat-card d-flex justify-content-between align-items-start">
            <div>
                <div class="label">Aktivna iznajmljivanja</div>
                <div class="value">{{ aktivnih_iznajmljivanja }}</div>
            </div>
            <div class="icon" style="background:#cffafe;color:#06b6d4"><i class="fas fa-key"></i></div>
        </div>
    </div>
    <div class="col-xl-3 col-md-6">
        <a href="/admin/" target="_blank" class="stat-card d-flex justify-content-between align-items-start text-decoration-none" style="background:#0f172a">
            <div>
                <div class="label text-slate-400" style="color:#94a3b8">Admin Panel</div>
                <div class="value" style="color:white;font-size:1.2rem">Upravljanje</div>
            </div>
            <div class="icon" style="background:#1e293b;color:#3b82f6"><i class="fas fa-tools"></i></div>
        </a>
    </div>
</div>

<div class="row g-3">
    <div class="col-lg-8">
        <div class="stat-card">
            <h6 class="fw-bold mb-3">Brzi pristup modulima</h6>
            <div class="row g-2">
                {% for module, icon, color in modules_list %}
                <div class="col-4 col-md-3">
                    <a href="/{{ module }}/" class="btn btn-light w-100 d-flex flex-column align-items-center py-3 text-decoration-none border">
                        <i class="{{ icon }} mb-1" style="color:{{ color }}"></i>
                        <small>{{ module|capfirst }}</small>
                    </a>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    <div class="col-lg-4">
        <div class="stat-card">
            <h6 class="fw-bold mb-3">Brze akcije</h6>
            <div class="d-grid gap-2">
                <a href="/admin/invoicing/invoicinginvoice/add/" class="btn btn-outline-primary btn-sm">
                    <i class="fas fa-plus me-2"></i>Nova faktura
                </a>
                <a href="/admin/partners/partnerspartner/add/" class="btn btn-outline-success btn-sm">
                    <i class="fas fa-plus me-2"></i>Novi partner
                </a>
                <a href="/admin/worktime/worktimetimeentry/add/" class="btn btn-outline-warning btn-sm">
                    <i class="fas fa-plus me-2"></i>Unos radnog vremena
                </a>
                <a href="/admin/appointments/appointmentsappointment/add/" class="btn btn-outline-info btn-sm">
                    <i class="fas fa-plus me-2"></i>Novi termin
                </a>
                <a href="/admin/webshop/webshoporder/add/" class="btn btn-outline-secondary btn-sm">
                    <i class="fas fa-plus me-2"></i>Nova narudžba
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
""")

# Template za svaki modul
for app in ALL_APPS:
    os.makedirs(f"{BASE_DIR}/{app}/templates/{app}", exist_ok=True)
    write(f"{BASE_DIR}/{app}/templates/{app}/index.html", f"""
{{% extends 'base.html' %}}
{{% block title %}}{ app.capitalize() } - LIMIT CONNECT{{% endblock %}}
{{% block page_title %}}Modul: { app.capitalize() }{{% endblock %}}
{{% block content %}}
<div class="d-flex justify-content-between align-items-center mb-4">
    <div>
        <h4 class="mb-1 fw-bold">{ app.capitalize() }</h4>
        <p class="text-muted mb-0">Pregled i upravljanje - { app }</p>
    </div>
    <a href="/admin/{ app }/" class="btn btn-primary">
        <i class="fas fa-cog me-2"></i>Otvori u Adminu
    </a>
</div>
<div class="stat-card">
    <div class="text-center py-5">
        <i class="fas fa-database fa-3x text-muted mb-3"></i>
        <h5>{ app.capitalize() } Modul</h5>
        <p class="text-muted">Koristite Admin panel za upravljanje podacima<br>ili API endpoint: <code>/{ app }/api/</code></p>
        <a href="/{ app }/api/" class="btn btn-outline-secondary btn-sm me-2">
            <i class="fas fa-code me-1"></i>API Endpoint
        </a>
        <a href="/admin/{ app }/" class="btn btn-primary btn-sm">
            <i class="fas fa-list me-1"></i>Pregled podataka
        </a>
    </div>
</div>
{{% endblock %}}
""")

print("  ✓ Templates kreirani")

# ════════════════════════════════════════════════════════════
# KORAK 9: migrate + superuser + collectstatic
# ════════════════════════════════════════════════════════════
print("  [9/10] Pokretanje migracija...")
venv_py = f"{BASE_DIR}/venv/bin/python3"
manage = f"{BASE_DIR}/manage.py"

# Migrate
result = subprocess.run(
    [venv_py, manage, "migrate", "--run-syncdb"],
    capture_output=True, text=True, cwd=BASE_DIR
)
if result.returncode != 0:
    print(f"  ⚠ Migrate upozorenje:\n{result.stderr[-500:]}")
else:
    print("  ✓ Migracije završene")

# Collectstatic
result = subprocess.run(
    [venv_py, manage, "collectstatic", "--noinput"],
    capture_output=True, text=True, cwd=BASE_DIR
)
print("  ✓ Static files prikupljeni")

# Superuser kroz shell
print("  [10/10] Kreiranje superusera...")
superuser_script = f"""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
u, created = User.objects.get_or_create(username='{ADMIN["USER"]}')
u.email = '{ADMIN["EMAIL"]}'
u.set_password('{ADMIN["PASS"]}')
u.is_staff = True
u.is_superuser = True
u.save()
print('Superuser OK:', '{ADMIN["USER"]}')
"""
result = subprocess.run(
    [venv_py, "-c", superuser_script],
    capture_output=True, text=True, cwd=BASE_DIR
)
if "Superuser OK" in result.stdout:
    print(f"  ✓ Superuser '{ADMIN['USER']}' spreman")
else:
    print(f"  ⚠ {result.stderr[-200:]}")

print("\n  ════════════════════════════════")
print("  ✅ BUILD ZAVRŠEN USPJEŠNO!")
print("  ════════════════════════════════\n")
