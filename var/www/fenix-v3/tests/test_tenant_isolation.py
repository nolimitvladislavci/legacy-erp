"""
BLOK 0 — CI zaštita od regresije
Osigurava da nijedan view ne čita company direktno iz sessiona.
Svi viewovi moraju koristiti self.company (TenantView) ili _get_company().

Pokretanje: venv/bin/python -m pytest tests/test_tenant_isolation.py -v
"""

import re
import pathlib
import pytest

# Puta koja su LEGITIMA (session piše, ne čita company)
SESSION_WRITE_PATTERN = re.compile(r"request\.session\s*\[.*(active_company_id|company_id).*\]\s*=")

# Čitanja koja su ZABRANJENA u viewovima
SESSION_READ_PATTERN = re.compile(r'(?:self\.)?request\.session\.get\s*\(\s*["\'](?:active_)?company_id["\']')

# Direktoriji koji su IZUZETI (test/conftest, session write u accounts/companies/pos)
EXEMPT_FILES = {
    "conftest.py",
    "accounts/views.py",  # login — legitimno piše session
    "companies/views.py",  # switch company — legitimno piše session
    "pos/views_onboarding.py",  # onboarding wizard — legitimno piše session
    "core/base_view.py",  # get_company() — jedina legitimna točka čitanja
    "core/context_processors.py",  # template context
    "core/middleware.py",  # billing middleware
    "core/billing_middleware.py",
    "sentinel/views.py",  # _get_company() wrapper — plan=Blok 13 refaktor
}

# Testni direktoriji — session se smije koristiti u testovima
TEST_DIRS = {"tests", "conftest"}

BASE = pathlib.Path("/var/www/fenix-v3")


def _is_exempt(path: pathlib.Path) -> bool:
    """Provjeri je li putanja izuzeta iz pravila."""
    # Testni fajlovi
    for part in path.parts:
        if part in TEST_DIRS:
            return True
    # Izuzeti fajlovi (relativna putanja)
    try:
        rel = str(path.relative_to(BASE))
    except ValueError:
        return False
    return any(rel.endswith(exempt) for exempt in EXEMPT_FILES)


def test_no_direct_session_company_reads():
    """
    Nijedan view ne smije čitati company_id direktno iz sessiona.
    Ispravno: self.company (TenantView) ili _get_company() za funkcijske viewove.
    """
    violations = []
    for path in BASE.rglob("views*.py"):
        if "__pycache__" in str(path):
            continue
        if _is_exempt(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if SESSION_READ_PATTERN.search(line):
                rel = path.relative_to(BASE)
                violations.append(f"{rel}:{i}: {line.strip()}")

    if violations:
        msg = (
            "BLOK 0 KRŠENJE — direktno čitanje company iz session:\n"
            + "\n".join(violations)
            + "\n\nFix: koristiti self.company (TenantView) ili _get_company()."
        )
        pytest.fail(msg)


def test_no_active_company_attribute():
    """
    request.user.active_company ne postoji — nikad ga ne koristiti.
    """
    violations = []
    for path in BASE.rglob("*.py"):
        if "__pycache__" in str(path) or _is_exempt(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "active_company" in line and "getattr" in line:
                rel = path.relative_to(BASE)
                violations.append(f"{rel}:{i}: {line.strip()}")

    if violations:
        msg = "request.user.active_company ne postoji — uvijek None:\n" + "\n".join(violations)
        pytest.fail(msg)
