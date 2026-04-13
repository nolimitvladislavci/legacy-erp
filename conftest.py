"""
Root conftest for Fenix tests.
"""

import django
from django.conf import settings


def pytest_configure(config):
    """Ensure Django is fully set up before test collection."""
    if not settings.configured:
        import os

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    django.setup()


import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@test.com",
    )


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_superuser(
        username="admin",
        password="adminpass123",
        email="admin@test.com",
    )


@pytest.fixture
def auth_client(client, user):
    client.login(username="testuser", password="testpass123")
    return client
