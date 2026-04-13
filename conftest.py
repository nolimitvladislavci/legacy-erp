"""
Pytest fixtures for Grossmarkt tests.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@test.com",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        password="adminpass123",
        email="admin@test.com",
    )


@pytest.fixture
def auth_client(client, user):
    client.login(username="testuser", password="testpass123")
    return client
