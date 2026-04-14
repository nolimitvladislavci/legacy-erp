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
            _env_val = _env_line[_env_idx + 1 :].strip().strip('"').strip("'")
            os.environ.setdefault(_env_key, _env_val)

# ── Core ──────────────────────────────────────────────────────
SECRET_KEY = os.environ["SECRET_KEY"]
FERNET_KEY = os.environ["FERNET_KEY"]
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    "limit-connect.com",
    "www.limit-connect.com",
    ".limit-connect.com",
    "viskovic-group.de",
    "www.viskovic-group.de",
    "37.27.248.86",
    "fina-connect.online",
    "www.fina-connect.online",
    "localhost",
    "127.0.0.1",
    "testserver",
    "no-limit.world",
    "www.no-limit.world",
    "memio.world",
    "www.memio.world",
    "memio.pet",
    "www.memio.pet",
    "memio.farm",
    "www.memio.farm",
]

SITE_URL = "https://limit-connect.com"
QR_HMAC_SECRET = os.environ.get("QR_HMAC_SECRET", SECRET_KEY)  # Uvijek HTTPS, bez trailing slash

CSRF_TRUSTED_ORIGINS = [
    "https://limit-connect.com",
    "https://www.limit-connect.com",
    "https://viskovic-group.de",
    "http://37.27.248.86",
    "https://www.viskovic-group.de",
    "https://fina-connect.online",
    "https://www.fina-connect.online",
    "https://no-limit.world",
    "https://www.no-limit.world",
    "https://memio.world",
    "https://www.memio.world",
    "https://memio.pet",
    "https://www.memio.pet",
]

# ── Security (production only) ────────────────────────────────
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # Mora biti False da JS moze refreshati token
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
    SESSION_COOKIE_AGE = 43200  # 12 sati
    SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ── Apps ──────────────────────────────────────────────────────
INSTALLED_APPS = [
    "daphne",
    "channels",
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
    "django.contrib.humanize",
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
    # "fitness",  # DEACTIVATED: 0 data, 0 FK refs from live models
    # "insurance",  # DEACTIVATED: 0 data, 0 FK refs from live models
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
    "data_migration",
    "smart_import",
    "payroll",
    "tracking",
    "registration",
    "interventions",
    "fiskalizacija",
    "gov_export",
    "knjiznica",
    "seasonal",
    "notariat",
    "kindergarten",
    "eldercare",
    "push_notifications",
    "library",
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
    "experiences",
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
    "tech_radar",
    "udruge",
    "livestock",
    "lovacki",
    "production",  # Proizvodnja (MRP) — 3 razine
    "sales",  # Posebni cjenici + Narudžbe + Saldakonti
    "utilities",
    "memio_pet",  # Memio.pet
    "memio_world",  # Memio.world — digitalna baština
    "memio_farm",  # Memio.farm — farmske životinje
    "no_limit",  # NO LIMIT udruga
    "intelligence",
    "einvoice",
    "limit_connect_ai",
    "stolarija.apps.StolarijaConfig",
    "tax_wizard",
    "borg_ops",
    "komunalno",
    "vault",
    "honorari",
    "boxgram",  # Pet social network
    "fenix_input",  # Univerzalni ulaz: glas, SMS, BT, email → AI → modul
]

# ── Django Channels (WebSocket) ───────────────────────────────────────
ASGI_APPLICATION = "core.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

MIDDLEWARE = [
    "core.middleware.GracefulErrorMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.WhiteLabelMiddleware",
    "core.middleware.LicenseCheckMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.DomainGateMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.audit.AuditMiddleware",
    "core.middleware.UserLanguageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "permissions.middleware.RolePermissionMiddleware",
    "core.middleware.CompanyMiddleware",
    "core.middleware.ImpersonationMiddleware",
    "core.middleware.CompanyBranchMiddleware",
    "core.middleware.AdminLangRedirectMiddleware",
    "core.middleware.ForcePasswordChangeMiddleware",
    "core.middleware.Force2FAMiddleware",
    "core.middleware.ForceTCMiddleware",
    "registration.middleware.SubscriptionMiddleware",
    "core.middleware.archive_readonly.ArchiveReadonlyMiddleware",
    "core.image_compression.ImageQuotaMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "permissions.ip_filter.IPFilterMiddleware",
    "core.middleware.api_error_format.ApiErrorFormatMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "core.middleware.RateLimitMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "template_overrides", BASE_DIR / "templates"],
        # APP_DIRS je False — koristimo eksplicitne loadere radi kontrole cachiranja
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                # Produkcija: predlošci se kešira u memoriji nakon prvog učitavanja
                # Nakon deploya: gunicorn reload (SIGHUP) prazni cache automatski
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                )
            ]
            if not __import__("os").environ.get("DEBUG", "False").lower() in ("true", "1", "yes")
            else [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.failed_imports_badge",
                "companies.context_processors.sidebar_modules",
                "companies.context_processors.memio_lang_choices",
                "permissions.context_processors.permissions_context",
                "permissions.context_processors.subscription_context",
                "core.context_processors.booking_globals",
                "core.context_processors.company_switcher",
                "core.context_processors.module_context",
                "core.context_processors.pending_claims_badge",
                "core.context_processors.white_label_context",
                "core.context_processors.workspace_context",
                "core.context_processors.umbrella_context",
            ],
        },
    }
]

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
        "CONN_MAX_AGE": 0,  # PgBouncer transaction pooling requires 0
    },
    # ── Memio.pet — zasebna baza, potpuna izolacija od ERP-a ──────────────
    # Direktno na PostgreSQL 5432 (ne kroz PgBouncer), poseban korisnik
    "memio_pets": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("MEMIO_PETS_DB_NAME", "memio_pets"),
        "USER": os.environ.get("MEMIO_PETS_DB_USER", "memio_pets_user"),
        "PASSWORD": os.environ.get("MEMIO_PETS_DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "TEST": {"NAME": "test_memio_pets"},
        "PORT": "5432",  # Direktno, ne PgBouncer (6432)
        "CONN_MAX_AGE": 60,
    },
    # ── Memio.world — zasebna baza, digitalna baština ──────────────
    "memio_farm": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("MEMIO_FARM_DB_NAME", "memio_farm"),
        "USER": os.environ.get("MEMIO_FARM_DB_USER", "memio_farm_user"),
        "PASSWORD": os.environ.get("MEMIO_FARM_DB_PASSWORD", os.environ.get("DB_PASSWORD", "")),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "TEST": {"NAME": "test_memio_farm"},
    },
    "memio_world": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("MEMIO_WORLD_DB_NAME", "memio_world"),
        "USER": os.environ.get("MEMIO_WORLD_DB_USER", "memio_world_user"),
        "PASSWORD": os.environ.get("MEMIO_WORLD_DB_PASSWORD", "mw_2026_L1m1t!"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "TEST": {"NAME": "test_memio_world"},
        "PORT": "5432",
        "CONN_MAX_AGE": 60,
    },
}

DATABASE_ROUTERS = ["core.db_routers.MultiDbRouter"]

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
        },
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
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

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

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
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "1000/hour",
        "vote": "5/hour",
        "import": "20/hour",
    },
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

# ── Email ─────────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False").lower() in ("true", "1", "yes")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@limit-connect.com")
ADMINS = [("Admin", os.environ.get("ADMIN_EMAIL", "admin@limit-connect.com"))]

# ── Password validators ───────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    "core.auth_backends.EmailOrUsernameBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "core.validators.StrongPasswordValidator"},
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
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
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
HITNA_NOTIFY_EMAIL = "viskovic.bau@gmail.com"


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

# ── Queue routing: POS = brzo/kritično, heavy = bulk/AI/PDF ──────────────
CELERY_TASK_ROUTES = {
    # POS queue — fiskalizacija, hash chain, fiscal deadline
    "pos.retry_fiscalization": {"queue": "pos"},
    "pos.check_fiscal_deadline": {"queue": "pos"},
    "pos.generate_missing_daily_reports": {"queue": "pos"},
    "pos.cleanup_zombie_sessions": {"queue": "pos"},
    "pos.auto_escalate_complaints": {"queue": "pos"},
    "pos.weekly_complaints_digest": {"queue": "pos"},
    # Heavy queue — bulk import, PDF, AI, synesis
    "smart_import.tasks.*": {"queue": "heavy"},
    "synesis.tasks.*": {"queue": "heavy"},
    "udruge.tasks.generate_azil_monthly_report": {"queue": "heavy"},
    "udruge.tasks.send_email_campaign": {"queue": "heavy"},
    "udruge.tasks.ai_search_eu_funds": {"queue": "heavy"},
    "udruge.tasks.generate_trosarina_report": {"queue": "heavy"},
    "einvoice.tasks.outbound_tasks.send_einvoice": {"queue": "heavy"},
    "einvoice.tasks.outbound_tasks.process_retry_queue": {"queue": "heavy"},
    "boxgram.tasks.*": {"queue": "heavy"},
}
CELERY_TASK_DEFAULT_QUEUE = "default"

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "arhiva-morning-brief": {
        "task": "documents.tasks.arhiva_morning_brief",
        "schedule": crontab(hour=6, minute=0),
    },
    "propter-auto-close-billing": {
        "task": "propter.tasks.auto_close_billing_periods",
        "schedule": crontab(hour=6, minute=0, day_of_month=1),
        "options": {"queue": "default"},
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
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),
    },
    "arhiva-ai-monitor-hourly": {
        "task": "documents.tasks.arhiva_ai_monitor",
        "schedule": crontab(minute=0),
    },
    "worktime-anomaly-patrol": {
        "task": "worktime.tasks.worktime_anomaly_patrol",
        "schedule": crontab(hour=2, minute=30),
    },
    "tech-radar-scan-15min": {
        "task": "tech_radar.tasks.tech_radar_scan",
        "schedule": crontab(minute="*/15"),
    },
    "tech-radar-capacity-hourly": {
        "task": "tech_radar.tasks.capacity_check",
        "schedule": crontab(minute=5),
    },
    "tech-radar-cleanup-daily": {
        "task": "tech_radar.tasks.cleanup_signals",
        "schedule": crontab(hour=3, minute=0),
    },
    "udruge-expiry-reminders": {
        "task": "udruge.tasks.send_expiry_reminders",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
    "eracun-fetch-inbox": {
        "task": "eracun.tasks.fetch_posrednik_inbox",
        "schedule": crontab(hour="*/4", minute=15),
    },
    "eracun-retry-unsent": {
        "task": "eracun.tasks.retry_unsent_eracuni",
        "schedule": crontab(minute="*/30"),
    },
    "nightly-owner-zreport": {
        "task": "pos.tasks.nightly_owner_zreport",
        "schedule": crontab(hour=23, minute=55),
    },
    "udruge-evaluate-subscriptions": {
        "task": "udruge.tasks.evaluate_subscriptions",
        "schedule": crontab(hour=2, minute=15),
    },
    "cleanup-stale-migrations": {
        "task": "data_migration.tasks.cleanup_stale_migrations",
        "schedule": 3600,  # svaki sat
    },
    "wizard-cleanup-stale-drafts": {
        "task": "partners.cleanup_stale_wizard_drafts",
        "schedule": crontab(hour=3, minute=0),
    },
    "intelligence-nightly-patrol": {
        "task": "intelligence.tasks.intelligence_nightly_patrol",
        "schedule": crontab(hour=3, minute=30),
    },
    "check-auto-listings": {
        "task": "intelligence.tasks.check_auto_listings",
        "schedule": crontab(hour=7, minute=0),
    },
    # POS: Zakonski alarm za bonove bez JIR-a (čl.11 Zakona o fiskalizaciji)
    "pos-check-fiscal-deadline": {
        "task": "pos.check_fiscal_deadline",
        "schedule": 1800,  # svakih 30 min
    },
    # ── LIMIT Connect AI ──
    "ai-morning-report": {
        "task": "limit_connect_ai.tasks.morning_report_all",
        "schedule": crontab(hour=7, minute=30),
    },
    "ai-fund-check": {
        "task": "limit_connect_ai.tasks.fund_check_all",
        "schedule": crontab(hour=9, minute=0),
    },
    "ai-compliance-check": {
        "task": "limit_connect_ai.tasks.compliance_check_all",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
    "borg-nn-feed-scraper": {
        "task": "limit_connect_ai.fetch_nn_feed",
        "schedule": 21600,  # svakih 6 sati
    },
    "ai-campaign-suggestions": {
        "task": "limit_connect_ai.tasks.campaign_suggestions_all",
        "schedule": crontab(hour=10, minute=0, day_of_week=5),
    },
    # ── Wizard Onboarding ──
    "cleanup-stale-wizard-drafts": {
        "task": "partners.cleanup_stale_wizard_drafts",
        "schedule": crontab(hour=3, minute=0),
    },
    "retroactive-nkd-lookup": {
        "task": "partners.retroactive_nkd_lookup",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # nedjelja 04:00
    },
    # Tax Compliance — supplier risk daily scan
    "scan-supplier-risk": {
        "task": "limit_connect_ai.tasks_risk.scan_supplier_risk",
        "schedule": crontab(hour=4, minute=30),
    },
    # ── Tax Wizard ──
    "tax-check-deadlines": {
        "task": "tax_wizard.tasks.check_tax_deadlines",
        "schedule": crontab(hour=7, minute=0),
    },
    "tax-prefill-quarterly": {
        "task": "tax_wizard.tasks.prefill_quarterly_data",
        "schedule": crontab(day_of_month=1, hour=5, minute=0),
    },
    "tax-cleanup-expired": {
        "task": "tax_wizard.tasks.cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=30),
    },
    "tax-generate-annual-deadlines": {
        "task": "tax_wizard.tasks.generate_annual_deadlines",
        "schedule": crontab(month_of_year=1, day_of_month=1, hour=0, minute=30),
    },
    # ── Rental ──
    "rental-daily-landlord-brief": {
        "task": "rental.tasks.daily_landlord_brief",
        "schedule": crontab(hour=8, minute=0),
    },
    "rental-check-evisitor-pending": {
        "task": "rental.tasks.check_evisitor_pending",
        "schedule": crontab(hour="*/6", minute=15),
    },
    "rental-annual-limit-check": {
        "task": "rental.tasks.annual_limit_check",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
    "rental-gdpr-cleanup-docs": {
        "task": "rental.tasks.gdpr_cleanup_guest_docs",
        "schedule": crontab(hour=4, minute=0),
    },
    # ── Marketplace Ghost Inventory ──
    # ── Agro-Turizam 360 ──
    "experience-reminders": {
        "task": "experiences.tasks.send_experience_reminders",
        "schedule": 21600,  # svakih 6 sati
    },
    "experience-no-shows": {
        "task": "experiences.tasks.mark_no_shows",
        "schedule": crontab(hour=22, minute=0),
    },
    "recall-send-notifications": {
        "task": "experiences.tasks.send_recall_notifications",
        "schedule": 300,  # svakih 5 min (recall je hitan)
    },
    "experience-inventory-depletion": {
        "task": "experiences.tasks.inventory_depletion_check",
        "schedule": 21600,  # svakih 6 sati
    },
    "marketplace-ghost-cleanup": {
        "task": "marketplace.tasks.ghost_inventory_cleanup",
        "schedule": 21600,  # svakih 6 sati
    },
    "marketplace-expiry-reminders": {
        "task": "marketplace.tasks.send_expiry_reminders",
        "schedule": 21600,  # svakih 6 sati
    },
    # ── Auction finalization ──
    "marketplace-auction-finalize": {
        "task": "marketplace.tasks.finalize_ended_auctions",
        "schedule": 300,  # svakih 5 minuta
    },
    # ── Gastro Bridge (Last Call) ──
    "marketplace-gastro-bridge-check": {
        "task": "marketplace.tasks.expiry_gastro_bridge_check",
        "schedule": 7200,  # svakih 2 sata
    },
    # Claude Doktor -- nocni AI scan svih firmi u 03:00
    "claude-doktor-nightly": {
        "task": "limit_connect_ai.tasks_doktor.run_clinic_diagnostics_all",
        "schedule": 10800,
    },
    # Archive Readonly: auto-downgrade isteklih pretplata (daily)
    "downgrade-expired-subs": {
        "task": "registration.tasks.downgrade_expired_subscriptions",
        "schedule": 86400,
    },
    # Growth Engine: Trojstvo dnevni patrol (03:30)
    "growth-patrol-daily": {
        "task": "limit_connect_ai.tasks.growth_patrol",
        "schedule": 86400,
    },
}
# ── VAPID Web Push ──────────────────────────────────────────────────────
import os as _os

VAPID_PUBLIC_KEY = _os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = _os.environ.get("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
VAPID_CLAIMS_EMAIL = _os.environ.get("VAPID_CLAIMS_EMAIL", "admin@limit-connect.com")

# ── WhatsApp (WAHA Gateway) ──────────────────────────────────
WAHA_API_URL = os.environ.get("WAHA_API_URL", "http://127.0.0.1:3000")
WAHA_SESSION_NAME = os.environ.get("WAHA_SESSION_NAME", "default")
WAHA_ENABLED = os.environ.get("WAHA_ENABLED", "True").lower() in ("true", "1", "yes")
WAHA_API_KEY = os.environ.get("WAHA_API_KEY", "")

# ── Claude Doktor ──────────────────────────────────────────────
MARIJA_PHONE = os.environ.get("MARIJA_PHONE", "")

# ── Error Notification Phones ──────────────────────────────────
# WhatsApp brojevi koji primaju 500 error notifikacije
# Dev tim dobiva traceback, ops tim dobiva user-friendly poruku
ERROR_NOTIFY_PHONES = [p.strip() for p in _os.environ.get("ERROR_NOTIFY_PHONES", "").split(",") if p.strip()]
ERROR_NOTIFY_OPS_PHONES = [p.strip() for p in _os.environ.get("ERROR_NOTIFY_OPS_PHONES", "").split(",") if p.strip()]


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
        {"name": "Worktime", "description": "Time tracking, timesheets, payroll"},
        {"name": "Companies", "description": "Company management, branches, umbrella"},
        {"name": "Webshop", "description": "E-commerce — products, orders, cart"},
        {"name": "Boxgram", "description": "Pet profiles, life events, competitions"},
        {"name": "E-Invoice", "description": "PEPPOL AS4, UBL, smart mailbox"},
        {"name": "Fitness", "description": "Gym members, check-ins"},
        {"name": "Insurance", "description": "Insurance policies"},
        {"name": "Fiscal", "description": "HR FINA CIS, DE TSE, AT RKSV"},
        {"name": "Auth", "description": "Authentication, TriKey, device tokens"},
    ],
}

# ── IP Filtering ──────────────────────────────────────────────
IP_FILTER_ENABLED = False  # Set to True to activate
IP_WHITELIST = [
    "127.0.0.1",
    "::1",
    "37.27.248.86",  # Admin IP
    "35.188.35.214",  # Dev API access
]
IP_RESTRICTED_PATHS = [
    "/admin/",
    "/superadmin/",
]

# ── eReporting Safety Pin ─────────────────────────────────────────────────────
# Dok XML generator za Poreznu upravu nije certificiran, blokiraj slanje.
# Postaviti na True tek nakon verifikacije s Poreznom.
ENABLE_E_REPORTING = os.environ.get("ENABLE_E_REPORTING", "False").lower() in ("true", "1")

# Upload limits for MDB files
DATA_UPLOAD_MAX_MEMORY_SIZE = 209715200  # 200MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 209715200  # 200MB

# ── SENTRY — Produkcijski monitoring ──────────────────────────────────
# Aktivira se samo kad postoji SENTRY_DSN u .env
# Besplatan račun: https://sentry.io → Create Django Project → kopiraj DSN
SENTRY_DSN = _os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.0,  # 0% — ne troši kvotu na performance, samo errors
        send_default_pii=False,  # GDPR: ne šalje PII prema Sentryu
        environment="production",
        release="limit-connect@2026.04.13",
        before_send=lambda event, hint: None if event.get("level") not in ("error", "fatal") else event,
    )


# ── Komunalno — e-ONTO + Kvota ──────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "komunalno-onto-nightly": {
            "task": "komunalno.tasks.nightly_onto_export",
            "schedule": crontab(hour=2, minute=0),
        },
        "komunalno-quota-warnings": {
            "task": "komunalno.tasks.check_quota_warnings",
            "schedule": crontab(hour=7, minute=30),
        },
    }
)


# ── Knjižnica — overdue + membership + digest + challenges ──────────
CELERY_BEAT_SCHEDULE.update(
    {
        "knjiznica-membership-expiry": {
            "task": "knjiznica.membership_expiry_check",
            "schedule": crontab(hour=9, minute=0, day_of_week=1),
        },
        "knjiznica-weekly-digest": {
            "task": "knjiznica.weekly_reading_digest",
            "schedule": crontab(hour=18, minute=0, day_of_week=0),
        },
        "knjiznica-expire-challenges": {
            "task": "knjiznica.expire_challenges",
            "schedule": crontab(hour=0, minute=15),
        },
    }
)

# --- CI/CD TEST OVERRIDE ---
import sys

if "test" in sys.argv:
    print("\n--- TEST MODE: In-Memory SQLite + LocMemCache + MD5 hash + Celery eager ---")
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    _locmem = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    CACHES = {"default": _locmem, "sessions": _locmem}
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_STORE_EAGER_RESULT = True
    # Disable force middlewares in test mode to prevent redirect loops
    APPEND_SLASH = False  # Prevent 301 redirects in tests
    MIDDLEWARE = [
        m
        for m in MIDDLEWARE
        if m
        not in (
            "core.middleware.Force2FAMiddleware",
            "core.middleware.ForceTCMiddleware",
            "core.middleware.ForcePasswordChangeMiddleware",
        )
    ]
    # Suppress SQLite FK constraint checks in test teardown
    from django.db.backends.sqlite3.base import DatabaseWrapper as _SQLiteDB

    _orig_check = _SQLiteDB.check_constraints

    def _noop_check(self, table_names=None):
        pass

    _SQLiteDB.check_constraints = _noop_check

    # Skip PostgreSQL-specific RunSQL migrations on SQLite
    from django.db.migrations.operations.special import RunSQL as _OrigRunSQL

    _orig_forwards = _OrigRunSQL.database_forwards

    def _safe_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "sqlite":
            return  # Skip raw SQL on SQLite
        return _orig_forwards(self, app_label, schema_editor, from_state, to_state)

    _OrigRunSQL.database_forwards = _safe_forwards


# ── Sandbox / Simulation Mode ──────────────────────────────────────
# Podaci iz 2025 i ranije su Synesis importi (vježba), ne produkcijski.
# Ovo utišava alarme za fiskalizaciju/eRačun na legacy podacima.
FISCAL_SANDBOX_BEFORE = int(os.environ.get("FISCAL_SANDBOX_BEFORE", "2026"))
IS_SANDBOX_MODE = os.environ.get("IS_SANDBOX_MODE", "False").lower() in ("true", "1")

# ── e-Invoice (PROPTER AS4/Peppol) ─────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "einvoice-poll-inbox-30s": {
            "task": "einvoice.tasks.inbound_tasks.poll_inbox",
            "schedule": 30.0,
        },
        "einvoice-check-delivery-60s": {
            "task": "einvoice.tasks.status_tasks.check_delivery_statuses",
            "schedule": 60.0,
        },
        "einvoice-process-retry-queue-60s": {
            "task": "einvoice.tasks.outbound_tasks.process_retry_queue",
            "schedule": 60.0,
        },
    }
)

# FINA Posrednik settings (Phase 1)
FINA_POSREDNIK_BASE_URL = os.environ.get("FINA_POSREDNIK_BASE_URL", "https://api.einvoice.hr/v1")
FINA_POSREDNIK_API_KEY = os.environ.get("FINA_POSREDNIK_API_KEY", "")
FINA_POSREDNIK_CLIENT_CERT = os.environ.get("FINA_POSREDNIK_CLIENT_CERT", "")
FINA_POSREDNIK_CLIENT_KEY = os.environ.get("FINA_POSREDNIK_CLIENT_KEY", "")
FINA_POSREDNIK_SANDBOX = os.environ.get("FINA_POSREDNIK_SANDBOX", "True").lower() in ("true", "1")

# S3/MinIO Archive
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "limitconnect")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "LimitConnect2026S3Archive")
S3_REGION = os.environ.get("S3_REGION", "eu-central-1")
S3_ARCHIVE_BUCKET = os.environ.get("S3_ARCHIVE_BUCKET", "propter-einvoice-archive")

# phase4 AP (Phase 3 — disabled by default)
PHASE4_AP_ENABLED = os.environ.get("PHASE4_AP_ENABLED", "False").lower() in ("true", "1")

# ── VIES Batch Validacija ──────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "vies-batch-validate-daily": {
            "task": "partners.tasks.vies_batch_validate",
            "schedule": 86400.0,  # 1x dnevno
            "kwargs": {"batch_size": 500},
        },
    }
)

# ── BORG Signal Patrol ──────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "borg-signal-patrol-30min": {
            "task": "limit_connect_ai.tasks_signal.signal_patrol",
            "schedule": 1800,  # 30 min
        },
        "borg-signal-daily-digest": {
            "task": "limit_connect_ai.tasks_signal.daily_signal_digest",
            "schedule": crontab(hour=7, minute=0),
        },
    }
)

# ── Notification Digest — tjedni izvještaj za udruge ───────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "weekly-notification-digest": {
            "task": "core.notification_digest.send_weekly_digest",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),  # Ponedjeljak 08:00
        },
    }
)

# ── Knjiga prigovora — auto-eskalacija + weekly digest ──────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "complaints-auto-escalate": {
            "task": "pos.auto_escalate_complaints",
            "schedule": crontab(hour=9, minute=0),  # Svaki dan 09:00
        },
        "complaints-weekly-digest": {
            "task": "pos.weekly_complaints_digest",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),  # Ponedjeljak 08:00
        },
    }
)

# ── Propter — Sammelrechnung (zbirni racun) ──────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "propter-monthly-sammelrechnung": {
            "task": "propter.generate_monthly_sammelrechnung",
            "schedule": crontab(day_of_month="1", hour="6", minute="0"),
        },
    }
)

# ── FENIX System Test — nočni autonomni test (02:00) ──────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "fenix-nightly-system-test": {
            "task": "core.run_system_test_task",
            "schedule": crontab(hour=2, minute=0),  # Svaku noć 02:00
            "kwargs": {"phone": "+4915771998747", "quick": False},
        },
        "fenix-quick-morning-check": {
            "task": "core.run_system_test_task",
            "schedule": crontab(hour=7, minute=30),  # Jutarnji quick check 07:30
            "kwargs": {"phone": "+4915771998747", "quick": True},
        },
    }
)

# ── SONNET AGENT — Vođa projekta, svaka 2 sata ────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "sonnet-project-lead-cycle": {
            "task": "core.sonnet_cycle",
            "schedule": crontab(minute=0, hour="*/2"),  # Svaka 2 sata
        },
    }
)

# ── AI Infrastruktura — API Ključevi ──────────────────────────────────────────
# KRITIČNO: Ovi ključevi su obavezni za Gemini agent i Sonnet agent.
# Ako nedostaju — AI infrastruktura pada, BORG ne funkcionira.
GEMINI_API_KEY = _os.environ.get("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = _os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = _os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
HAIKU_MODEL = _os.environ.get("HAIKU_MODEL", "claude-haiku-4-5-20251001")

# ── AI Health Check — svaki sat ───────────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "ai-health-check-hourly": {
            "task": "core.ai_health_check",
            "schedule": crontab(minute=15),  # svaki sat u :15 (ne u :00 s ostalima)
        },
    }
)

# ── Amortizacija podsjetnik — 1. u mjesecu 06:00 ─────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "depreciation-monthly-reminder": {
            "task": "inventory.tasks.depreciation_monthly_check",
            "schedule": crontab(day_of_month="1", hour="6", minute="0"),
        },
    }
)

# ── BORG SLA Check — svakih 10 min ──────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "borg-check-sla-10min": {
            "task": "borg_ops.check_sla",
            "schedule": 600.0,
        },
        "borg-archive-old-activity-monthly": {
            "task": "borg_ops.archive_old_activity",
            "schedule": crontab(day_of_month="1", hour="3", minute="30"),
        },
    }
)

CSRF_FAILURE_VIEW = "core.csrf_handler.csrf_failure_view"

# ── BORG Sentineli ──────────────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "borg-schema-drift-weekly": {
            "task": "borg_ops.tasks.schema_drift_check",
            "schedule": crontab(day_of_week="sunday", hour="3", minute="0"),
        },
        "borg-orphan-data-weekly": {
            "task": "borg_ops.tasks.orphan_data_check",
            "schedule": crontab(day_of_week="sunday", hour="3", minute="30"),
        },
    }
)

# ── Database Backup — svaki dan 02:00 ────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "database-daily-backup": {
            "task": "core.database_backup",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "default"},
        },
    }
)

# ── Arhiva Integrity Check — svake nedjelje 03:15 ────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "arhiva-integrity-weekly": {
            "task": "documents.verify_arhiva_integrity",
            "schedule": crontab(day_of_week="sunday", hour="3", minute="15"),
        },
    }
)

# ── AI Auto-Book High Confidence — svaki dan 06:00 ──────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "ai-auto-book-high-confidence-daily": {
            "task": "documents.auto_book_high_confidence",
            "schedule": crontab(hour=6, minute=0),
        },
    }
)

# ── Subscription Tracker — pretplate i računi ──────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "check-subscriptions-daily": {
            "task": "core.check_subscriptions",
            "schedule": crontab(hour=9, minute=0),
        },
    }
)

# ── Data Quality — nightly patrol ──────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "nightly-data-quality": {
            "task": "companies.nightly_data_quality",
            "schedule": crontab(hour=4, minute=15),
        },
    }
)

# ── BORG FENIX Autonomous Tasks ──────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        # Self-heal: every 15 min
        "borg-self-heal": {
            "task": "borg_ops.self_heal.health_check_and_heal",
            "schedule": crontab(minute="*/15"),
        },
        # Signal dedup + auto-resolve: every hour
        "borg-signal-cleanup": {
            "task": "limit_connect_ai.tasks_signal.signal_dedup_and_resolve",
            "schedule": crontab(minute=5),  # XX:05
        },
        # Ops task sync: every 6 hours
        "borg-ops-sync": {
            "task": "borg_ops.connector.sync_ops_tasks",
            "schedule": crontab(hour="*/6", minute=10),
        },
        # Opportunity digest: weekly Monday 07:00
        "borg-opportunity-digest": {
            "task": "limit_connect_ai.tasks_opportunity.opportunity_digest",
            "schedule": crontab(hour=7, minute=0, day_of_week=1),
        },
        # Anomaly scan: daily at 04:00
        "borg-anomaly-scan": {
            "task": "core.anomaly_detector.detect_cross_company_anomalies",
            "schedule": crontab(hour=4, minute=0),
        },
        # Knowledge from patrols: daily at 05:00
        "borg-kb-from-patrols": {
            "task": "ai_assistant.quick_actions.generate_knowledge_from_patrols",
            "schedule": crontab(hour=5, minute=0),
        },
    }
)


# ── BORG Proactive Engine — beat schedule ──────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "borg-morning-briefing": {
            "task": "borg_ops.morning_briefing",
            "schedule": crontab(hour=7, minute=45),
        },
    }
)

CELERY_BEAT_SCHEDULE.update(
    {
        "borg-nn-classify": {
            "task": "limit_connect_ai.classify_nn_updates",
            "schedule": crontab(hour="*/6", minute=30),
        },
    }
)

CELERY_BEAT_SCHEDULE.update(
    {
        "borg-trust-decay-check": {
            "task": "borg_ops.check_trust_decay_all",
            "schedule": crontab(hour=23, minute=0),
        },
    }
)

CELERY_BEAT_SCHEDULE.update(
    {
        "borg-aggregate-signals": {
            "task": "borg_ops.aggregate_signals",
            "schedule": crontab(hour=4, minute=0),
        },
    }
)


# ── Kindergarten Vertikala — beat schedule ─────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "kindergarten-absence-alert": {
            "task": "kindergarten.send_absence_alert",
            "schedule": crontab(hour=10, minute=0, day_of_week="1-5"),
        },
        "kindergarten-billing-reminder": {
            "task": "kindergarten.send_billing_reminder",
            "schedule": crontab(hour=8, minute=0),
        },
        "kindergarten-monthly-billing": {
            "task": "kindergarten.generate_monthly_billings",
            "schedule": crontab(hour=6, minute=0, day_of_month=1),
        },
    }
)


# ── Audit Cleanup — beat schedule ──────────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "cleanup-audit-logs": {
            "task": "core.tasks.audit_cleanup.cleanup_old_audit_logs",
            "schedule": crontab(hour=3, minute=0),
        },
    }
)

# ── Memio.pet Trust Score refresh (svaka 24h) ──────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "memio-trust-score-refresh": {
            "task": "memio_pet.trust_score_refresh",
            "schedule": 86400,  # 24h
            "options": {"queue": "default"},
        },
    }
)

# Fenix Inbox digest (Sprint Fenix)
CELERY_BEAT_SCHEDULE.update(
    {
        "fenix-inbox-digest": {
            "task": "smart_import.fenix_inbox_digest",
            "schedule": 1800,
        },
    }
)

# Tax deadline notifier (Sprint Udruge-Konto)
CELERY_BEAT_SCHEDULE.update(
    {
        "tax-deadline-notifier": {
            "task": "konto.tax_deadline_notifier",
            "schedule": 86400,
        },
    }
)

# Cache warming after restart (Sprint Synesis-B)
CELERY_BEAT_SCHEDULE.update(
    {
        "warm-cache-hourly": {
            "task": "core.management.commands.warm_cache",
            "schedule": 3600,
        },
    }
)

# ── License Token Check (6h) ──────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "license-token-check-6h": {
            "task": "companies.check_license_tokens",
            "schedule": 21600,  # 6h
        },
    }
)

CELERY_BEAT_SCHEDULE.update(
    {
        "fenix-domain-expiry-check": {
            "task": "borg_ops.tasks.check_domain_expiry",
            "schedule": 86400,  # Jednom dnevno (24h u sekundama)
        },
    }
)


# ── Boxgram Social Import ───────────────────────────────────────
INSTAGRAM_OEMBED_TOKEN = os.environ.get("INSTAGRAM_OEMBED_TOKEN", "")

# ── Stolarija Service Reminders ────────────────────────────────────
CELERY_BEAT_SCHEDULE.update(
    {
        "photo-ai-tagging": {
            "task": "documents.tasks.ai_tag_photos",
            "schedule": 1800,  # every 30 min
        },
        "stolarija-service-reminders-daily": {
            "task": "stolarija.tasks.check_service_reminders",
            "schedule": 86400.0,  # 1x dnevno
        },
        "stolarija-warranty-annual-check": {
            "task": "stolarija.tasks.check_expired_warranties",
            "schedule": 604800.0,  # 1x tjedno
        },
        "stolarija-risk-recalculate-weekly": {
            "task": "stolarija.tasks.recalculate_risk_profiles",
            "schedule": 604800.0,  # 1x tjedno
        },
        "stolarija-ai-process-messages": {
            "task": "stolarija.tasks.process_pending_messages",
            "schedule": 300.0,  # svakih 5 min
        },
        "stolarija-ai-send-approved": {
            "task": "stolarija.tasks.send_approved_messages",
            "schedule": 300.0,  # svakih 5 min
        },
    }
)

CELERY_BEAT_SCHEDULE["worktime-iban-vault-check"] = {
    "task": "worktime.tasks.iban_vault_check",
    "schedule": 86400,  # daily
}

CELERY_BEAT_SCHEDULE["notifications-purge-old"] = {
    "task": "notifications.tasks.purge_old_notifications",
    "schedule": 604800.0,  # 1x tjedno (nedjelja)
}

# ── DJANGO SILK — Performance profiling (samo za DEBUG) ──────────────────────
# Aktivira se kad DEBUG=True (staging/local).
# Produkcija: DEBUG=False → silk se NE učitava.
# UI: /silk/ (admin pristup)
if DEBUG:
    INSTALLED_APPS = list(INSTALLED_APPS) + ["silk"]
    MIDDLEWARE = ["silk.middleware.SilkyMiddleware"] + list(MIDDLEWARE)
    SILKY_PYTHON_PROFILER = True
    SILKY_MAX_RECORDED_REQUESTS = 100
    SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10
