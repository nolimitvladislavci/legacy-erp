"""
Test settings — bypass PgBouncer, connect directly to PostgreSQL on port 5432.
"""

import os

os.environ["DB_PORT"] = "5432"

from core.settings import *  # noqa: F401, F403

# Override databases to use port 5432 directly (bypass PgBouncer)
for db_key in DATABASES:
    DATABASES[db_key]["PORT"] = "5432"
    DATABASES[db_key]["CONN_MAX_AGE"] = 0

# Disable Sentry in tests
SENTRY_DSN = None
if "sentry_sdk" in INSTALLED_APPS:
    pass  # Keep it, just won't send

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable SSL redirect
SECURE_SSL_REDIRECT = False

# Use console email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
