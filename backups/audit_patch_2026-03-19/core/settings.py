import os
from pathlib import Path

from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Load .env ─────────────────────────────────────────────────
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _env_line in _env_file.read_text(encoding="utf-8").splitlines():
        _env_line = _env_line.strip()
        if _env_line and not _env_line.startswith("#") and "=" in _env_line:
            _env_idx = _env_line.index("=")
            _env_key = _env_line[:_env_idx].strip()
            _env_val = _env_line[_env_idx+1:].strip().strip('"').strip("'")
            os.environ.setdefault(_env_key, _env_val)

# ── Core ──────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-fallback-change-me")
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    "limit-connect.com", "www.limit-connect.com",
    "viskovic-group.de", "www.viskovic-group.de",
    "85.9.201.204", "37.27.248.86", "fina-connect.online", "www.fina-connect.online", "localhost", "127.0.0.1",
]

CSRF_TRUSTED_ORIGINS = [
    "https://limit-connect.com",
    "https://www.limit-connect.com",
    "https://viskovic-group.de",
    "http://37.27.248.86",
    "https://www.viskovic-group.de",
    "https://fina-connect.online",
    "https://www.fina-connect.online",
]

# ── Security (production only) ────────────────────────────────
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/whatsapp/webhook/$"]  # WAHA internal webhook
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_AGE = 43200           # 12 sati
    SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ── Apps ──────────────────────────────────────────────────────
INSTALLED_APPS = [
    "core",
    "premium_booking",
    "notifications",
    "reports",
    "permissions",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rosetta",
    "modeltranslation",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "import_export",
    "django_celery_beat",
    "django_celery_results",
    "accounts",
    "appointments",
    "companies",
    "documents",
    "finance",
    "fitness",  # GHOST: 0 data but referenced by tests
    "insurance",  # GHOST: 0 data but model loaded
    "inventory",
    "invoicing",
    "partners",
    "rental",
    "webshop",
    "worktime",
    "projects",
    "website",
    "calculator",
    "work_orders",
    "pos",
    "fiscal",
    "synesis",
    "smart_import",
    "payroll",
    "tracking",
    "registration",
    "interventions",
    "fiskalizacija",
    "burza",
    "assessment",
    "branches",
    "outreach",
    "ai_assistant",
    "konto",
    "marketplace",
    "delivery",
    "traceability",
    "gastro_menu",  # GHOST: 0 data, traceability FK
    "payments",
    "eracun",
    "helpdesk",
    "propter",
    "procurement",
    "maintenance",
    "pdv_s",
    "aml",
    "edik",
    "virtual_office",
    "superadmin_ai",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.audit.AuditMiddleware",
    "core.middleware.UserLanguageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "permissions.middleware.RolePermissionMiddleware",
    "core.middleware.CompanyMiddleware",
    "core.middleware.ImpersonationMiddleware",
    "core.middleware.CompanyBranchMiddleware",
    "core.middleware.ForcePasswordChangeMiddleware",
    "registration.middleware.SubscriptionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "permissions.ip_filter.IPFilterMiddleware",
    "core.middleware.api_error_format.ApiErrorFormatMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "template_overrides", BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "companies.context_processors.sidebar_modules",
            "permissions.context_processors.permissions_context",
            "permissions.context_processors.subscription_context",
            "core.context_processors.booking_globals",
                "core.context_processors.company_switcher",
        ],
    },
}]

WSGI_APPLICATION = "core.wsgi.application"

# ── Database ──────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.environ.get("DB_NAME", "postgres"),
        "USER": os.environ.get("DB_USER", "viskovic_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "TEST": {"NAME": "test_fina_connect"},
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# ── Cache (Redis) ─────────────────────────────────────────────
_redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")
try:
    import django_redis  # noqa
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "IGNORE_EXCEPTIONS": True,
            },
            "KEY_PREFIX": "finaconnect",
            "TIMEOUT": 300,
        },
        "sessions": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            },
            "KEY_PREFIX": "finaconnect_sessions",
            "TIMEOUT": 43200,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "sessions"
except ImportError:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# ── Internacionalizacija ──────────────────────────────────────
LANGUAGE_CODE = "hr"
LANGUAGES = [
    ("de", _("Deutsch")),
    ("hr", _("Hrvatski")),
    ("en", _("English")),
    ("tr", _("Türkçe")),
    ("el", _("Ελληνικά")),
]
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 31536000
LOCALE_PATHS = [BASE_DIR / "locale"]
ROSETTA_SHOW_AT_ADMIN_PANEL = True
ROSETTA_MESSAGES_PER_PAGE = 25
TIME_ZONE = "Europe/Zagreb"
USE_TZ = True

# ── Static & Media ────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ── REST Framework ────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": 50,
}

# ── Email ─────────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False").lower() in ("true", "1", "yes")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@limit-connect.com")
ADMINS = [("Admin", os.environ.get("ADMIN_EMAIL", "admin@limit-connect.com"))]

# ── Password validators ───────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
]

# ── Logging ───────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"
try:
    LOGS_DIR.mkdir(exist_ok=True)
except Exception:
    pass

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {asctime} {message}", "style": "{"},
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "django.log"),
            "maxBytes": 10 * 1024 * 1024,   # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "delay": True,
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
        },
    },
    "root": {"handlers": ["console", "file"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "django.request": {
            "handlers": ["file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "gunicorn.error": {"handlers": ["file"], "level": "WARNING", "propagate": False},
        "whatsapp": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}
HITNA_NOTIFY_EMAIL = 'viskovic.bau@gmail.com'


# ── Celery ────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/3")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 600

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    'arhiva-morning-brief': {
        'task': 'documents.tasks.arhiva_morning_brief',
        'schedule': crontab(hour=6, minute=0),
    },
    'propter-auto-close-billing': {
        'task': 'propter.tasks.auto_close_billing_periods',
        'schedule': crontab(hour=6, minute=0, day_of_month=1),
        'options': {'queue': 'default'},
    },
    "check-overdue-invoices": {
        "task": "invoicing.tasks.check_overdue_invoices",
        "schedule": crontab(hour=7, minute=0),
    },
    "send-appointment-reminders": {
        "task": "appointments.tasks.send_appointment_reminders",
        "schedule": crontab(hour="8,18", minute=0),
    },
    "check-intervention-ttl": {
        "task": "interventions.tasks.check_intervention_ttl",
        "schedule": 60.0,
    },
    "check-whatsapp-health": {
        "task": "core.whatsapp_tasks.check_whatsapp_gateway_health",
        "schedule": crontab(minute="*/15"),
    },
    "predictive-reorder-check": {
        "task": "inventory.tasks.predictive_reorder_check",
        "schedule": crontab(hour=5, minute=0),
    },
    "check-predictive-stockouts": {
        "task": "inventory.prediction_tasks.check_predictive_stockouts",
        "schedule": crontab(hour=6, minute=30),
    },
    "detect-stale-batches": {
        "task": "smart_import.tasks.detect_stale_batches",
        "schedule": crontab(minute="*/10"),
    },
    "fetch-invoices-from-email": {
        "task": "smart_import.tasks.fetch_invoices_from_email",
        "schedule": 300.0,
    },
    "run-dunning-cycle": {
        "task": "invoicing.tasks.run_dunning_cycle",
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),
    },
    "monthly-depreciation": {
        "task": "maintenance.tasks.monthly_depreciation_task",
        "schedule": crontab(day_of_month=1, hour=2, minute=30),
    },
    "monthly-vat-calculation": {
        "task": "konto.tasks.monthly_vat_calculation",
        "schedule": crontab(day_of_month=1, hour=3, minute=0),
    },
    "ai-midnight-patrol": {
        "task": "ai_assistant.tasks.ai_midnight_patrol",
        "schedule": crontab(hour=2, minute=0),
    },
    # POS: Automatski retry nefiskaliziranih računa (svake 2 min)
    "pos-retry-fiscalization": {
        "task": "pos.retry_fiscalization",
        "schedule": 120,  # svake 2 minute
    },
    # POS: Generiraj POSDailyReport za propuštene sesije (svakih 30 min)
    "pos-missing-daily-reports": {
        "task": "pos.generate_missing_daily_reports",
        "schedule": 1800,
    },
    # POS: Auto-cleanup zombie sesija starijih od 16h (svaki sat)
    "pos-cleanup-zombies": {
        "task": "pos.cleanup_zombie_sessions",
        "schedule": 3600,
    },
    "ai-inbox-daily-email": {
        "task": "documents.tasks.send_ai_inbox_summary_email",
        "schedule": crontab(hour=8, minute=0, day_of_week='1-5'),
    },
    "arhiva-ai-monitor-hourly": {
        "task": "documents.tasks.arhiva_ai_monitor",
        "schedule": crontab(minute=0),
    },
}
# ── VAPID Web Push ──────────────────────────────────────────────────────
import os as _os

VAPID_PUBLIC_KEY   = _os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY  = _os.environ.get('VAPID_PRIVATE_KEY', '').replace('\\n', '\n')
VAPID_CLAIMS_EMAIL = _os.environ.get('VAPID_CLAIMS_EMAIL', 'admin@limit-connect.com')

# ── WhatsApp (WAHA Gateway) ──────────────────────────────────
WAHA_API_URL = os.environ.get('WAHA_API_URL', 'http://127.0.0.1:3000')
WAHA_SESSION_NAME = os.environ.get('WAHA_SESSION_NAME', 'default')
WAHA_ENABLED = os.environ.get('WAHA_ENABLED', 'True').lower() in ('true', '1', 'yes')
WAHA_API_KEY = os.environ.get('WAHA_API_KEY', '')

# ── API Documentation ────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "LIMIT Connect API",
    "DESCRIPTION": "Multi-tenant Business Management Platform — REST API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Invoicing", "description": "Invoice CRUD, PDF generation, fiscalization"},
        {"name": "POS", "description": "Point of Sale — sessions, receipts, payments"},
        {"name": "Appointments", "description": "Booking, slots, calendar"},
        {"name": "Inventory", "description": "Stock management, movements"},
        {"name": "Partners", "description": "Client & supplier management"},
        {"name": "Projects", "description": "Project tracking & budgets"},
        {"name": "Worktime", "description": "Time tracking & timesheets"},
    ],
}

# ── IP Filtering ──────────────────────────────────────────────
IP_FILTER_ENABLED = False  # Set to True to activate
IP_WHITELIST = [
    '127.0.0.1',
    '::1',
    '85.9.201.204',    # Admin IP
    '35.188.35.214',   # Dev API access
]
IP_RESTRICTED_PATHS = [
    '/admin/',
    '/superadmin/',
]

# Upload limits for MDB files
DATA_UPLOAD_MAX_MEMORY_SIZE = 209715200  # 200MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 209715200  # 200MB

# ── SENTRY — Produkcijski monitoring ──────────────────────────────────
# Aktivira se samo kad postoji SENTRY_DSN u .env
# Besplatan račun: https://sentry.io → Create Django Project → kopiraj DSN
SENTRY_DSN = _os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.2,       # 20% transakcija za performance monitoring
        send_default_pii=True,         # Šalje user ID za kontekst greške
        environment='production',
        release=f'limit-connect@2026.03.18',
    )

