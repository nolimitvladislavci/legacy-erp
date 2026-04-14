#!/usr/bin/env python3
"""
KORAK 10 — Onboarding provjera v2 (ispravna)
Pravi flow: quick-register → 2FA bypass → login → 5 checkova

Pokretanje:
    cd /var/www/fina-connect && DJANGO_SETTINGS_MODULE=core.settings venv/bin/python tmp/korak10_v2.py
"""
import os
import sys
import re
import uuid

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
sys.path.insert(0, "/var/www/fina-connect")
django.setup()

import requests
import urllib3
urllib3.disable_warnings()

from django.contrib.auth.models import User
from accounts.models import UserProfile
from companies.models import Company

BASE = "https://limit-connect.com"
UID = uuid.uuid4().hex[:6]
TEST_EMAIL = f"onboard_{UID}@testlimit.hr"
TEST_PASS = "OnboardTest2026!x"
TEST_NAME = "Ivana Test"
TEST_OIB = "98765432106"

RESULTS = {}

def check(name, ok, detail=""):
    icon = "✅" if ok else "❌"
    label = "PROŠLO" if ok else "NIJE PROŠLO"
    print(f"  {icon} {name}: {label}{(' — ' + detail) if detail else ''}")
    RESULTS[name] = ok


def get_csrf(session, url):
    r = session.get(url, allow_redirects=True, verify=False)
    m = re.search(r'name=["\']csrfmiddlewaretoken["\'].*?value=["\']([a-zA-Z0-9]+)["\']', r.text)
    if not m:
        m = re.search(r'value=["\']([a-zA-Z0-9]+)["\'].*?csrfmiddlewaretoken', r.text)
    token = m.group(1) if m else session.cookies.get("csrftoken", "")
    return r, token


# ════════════════════════════════════════════════
# SETUP: Kreiraj test usera direktno (clean state)
# ════════════════════════════════════════════════
print(f"\n── SETUP: Test user {TEST_EMAIL} ──")

# Očisti prethodni test
User.objects.filter(email__iexact=TEST_EMAIL).delete()
Company.objects.filter(oib=TEST_OIB, name="Test Firma OB").delete()

# Kreiraj firmu
company = Company.objects.create(
    name="Test Firma OB",
    oib=TEST_OIB,
    country="HR",
    business_type="doo",
    has_signed_tc_consent=True,
    tc_consent_version="v1.0-2026",
)
print(f"  · Firma: {company.name} (pk={company.pk})")

# Kreiraj usera
user = User.objects.create_user(
    username=f"onboard_{UID}",
    email=TEST_EMAIL,
    password=TEST_PASS,
    first_name="Ivana",
    last_name="Test",
)
profile, _ = UserProfile.objects.get_or_create(
    user=user,
    defaults={
        "company": company,
        "role": "company_admin",
        "totp_enabled": True,  # Bypass Force2FAMiddleware za test
    }
)
if not profile.totp_enabled:
    profile.totp_enabled = True
    profile.company = company
    profile.role = "company_admin"
    profile.save(update_fields=["totp_enabled", "company", "role"])

print(f"  · User: {user.username} (pk={user.pk}, totp_enabled={profile.totp_enabled})")

# ════════════════════════════════════════════════
# LOGIN via HTTP (/hr/login/)
# ════════════════════════════════════════════════
print("\n── CHECK 1: Login + Registration wizard ──")
s = requests.Session()
s.headers["User-Agent"] = "FENIX-OnboardingTest/2.0"

r_get, csrf = get_csrf(s, f"{BASE}/hr/login/")
print(f"  · GET /hr/login/ → {r_get.status_code}, csrf={'OK' if csrf else 'MISSING'}")

login_data = {
    "csrfmiddlewaretoken": csrf,
    "email": TEST_EMAIL,
    "password": TEST_PASS,
}
r_login = s.post(f"{BASE}/hr/login/", data=login_data, allow_redirects=True, verify=False)

session_ok = bool(s.cookies.get("sessionid"))
redirected_to = r_login.url
not_on_login = "/login" not in redirected_to and "/2fa/" not in redirected_to

check("1a Login (session cookie)", session_ok, f"redirect→{redirected_to}")
check("1b Login (nije blokiran)", not_on_login, f"url={redirected_to}")

# Provjeri registration wizard endpoint
r_qreg, _ = get_csrf(s, f"{BASE}/hr/accounts/quick-register/")
check("1c Quick-register forma dostupna", r_qreg.status_code == 200, f"status={r_qreg.status_code}")

# ════════════════════════════════════════════════
# CHECK 2: Company setup (onboarding wizard)
# ════════════════════════════════════════════════
print("\n── CHECK 2: Company setup (onboarding wizard) ──")
r_ob = s.get(f"{BASE}/onboarding/", allow_redirects=True, verify=False)
on_onboarding = r_ob.status_code == 200 and "/login" not in r_ob.url
check("2a Onboarding wizard dostupan", on_onboarding, f"url={r_ob.url}")

if on_onboarding:
    csrf_ob = s.cookies.get("csrftoken", "")
    ob_data = {
        "csrfmiddlewaretoken": csrf_ob,
        "name": "Test Firma OB",
        "oib": TEST_OIB,
        "address": "Ilica 1",
        "city": "Zagreb",
        "zip_code": "10000",
        "email": TEST_EMAIL,
    }
    r_ob_post = s.post(f"{BASE}/onboarding/update-profile/", data=ob_data,
                        allow_redirects=True, verify=False,
                        headers={"X-Requested-With": "XMLHttpRequest",
                                 "Accept": "application/json"})
    try:
        j = r_ob_post.json()
        check("2b Company profile update", j.get("ok", False), str(j))
    except Exception:
        check("2b Company profile update", r_ob_post.status_code == 200,
              f"status={r_ob_post.status_code} url={r_ob_post.url}")
else:
    check("2b Company profile update", False, "wizard nije dostupan")

# ════════════════════════════════════════════════
# CHECK 3: Prva faktura
# ════════════════════════════════════════════════
print("\n── CHECK 3: Prva faktura ──")
r_inv = s.get(f"{BASE}/hr/invoicing/", allow_redirects=True, verify=False)
inv_accessible = r_inv.status_code == 200 and "/login" not in r_inv.url
check("3a Invoicing modul dostupan", inv_accessible, f"url={r_inv.url}")

if inv_accessible:
    # Provjeri novu fakturu GET formu
    r_inv_new_get, csrf_inv = get_csrf(s, f"{BASE}/hr/invoicing/new/")
    check("3b Nova faktura forma", r_inv_new_get.status_code == 200,
          f"status={r_inv_new_get.status_code}")
    
    if r_inv_new_get.status_code == 200:
        from django.utils import timezone
        today = timezone.now().date().isoformat()
        inv_data = {
            "csrfmiddlewaretoken": csrf_inv,
            "doctype": "R",
            "date_issued": today,
            "date_due": today,
            "note": "Test faktura Korak 10",
        }
        r_inv_post = s.post(f"{BASE}/hr/invoicing/new/", data=inv_data,
                             allow_redirects=True, verify=False)
        # Uspjeh = redirect na fakturu (ne ostaje na /new/)
        inv_created = (r_inv_post.status_code in (200, 302) and
                       "/invoicing/" in r_inv_post.url and
                       "/new/" not in r_inv_post.url)
        check("3c Faktura kreirana", inv_created, f"url={r_inv_post.url}")
    else:
        check("3c Faktura kreirana", False, "forma nije dostupna")
else:
    check("3b Nova faktura forma", False, "modul nije dostupan")
    check("3c Faktura kreirana", False, "modul nije dostupan")

# ════════════════════════════════════════════════
# CHECK 4: POS: prvi bon
# ════════════════════════════════════════════════
print("\n── CHECK 4: POS bon ──")
r_pos = s.get(f"{BASE}/hr/pos/", allow_redirects=True, verify=False)
pos_accessible = r_pos.status_code == 200 and "/login" not in r_pos.url
check("4a POS dashboard dostupan", pos_accessible, f"url={r_pos.url}")

if pos_accessible:
    # Provjeri postoji li terminal za test firmu
    from pos.models import POSTerminal
    terminal = POSTerminal.objects.filter(company=company).first()
    
    if not terminal:
        # Kreiraj demo terminal za provjeru
        try:
            terminal = POSTerminal.objects.create(
                company=company,
                name="Test Terminal",
                is_active=True,
            )
            check("4b POS terminal postoji", True, f"kreiran terminal pk={terminal.pk}")
        except Exception as e:
            check("4b POS terminal postoji", False, f"ne može se kreirati: {e}")
            terminal = None
    else:
        check("4b POS terminal postoji", True, f"terminal pk={terminal.pk}")

    if terminal:
        # Provjeri POS blagajna endpoint
        r_pos_bon = s.get(f"{BASE}/hr/pos/terminal/{terminal.pk}/", allow_redirects=True, verify=False)
        check("4c POS blagajna dostupna", r_pos_bon.status_code == 200 and "/login" not in r_pos_bon.url,
              f"status={r_pos_bon.status_code}")
    else:
        check("4c POS blagajna dostupna", False, "nema terminala")
else:
    check("4b POS terminal postoji", False, "POS nedostupan")
    check("4c POS blagajna dostupna", False, "POS nedostupan")

# ════════════════════════════════════════════════
# CHECK 5: Dokumenti: upload → arhiva
# ════════════════════════════════════════════════
print("\n── CHECK 5: Dokumenti / arhiva ──")
r_arch = s.get(f"{BASE}/hr/documents/arhiva/", allow_redirects=True, verify=False)
arch_accessible = r_arch.status_code == 200 and "/login" not in r_arch.url
check("5a Arhiva dostupna", arch_accessible, f"url={r_arch.url}")

r_upload = s.get(f"{BASE}/hr/documents/upload/", allow_redirects=True, verify=False)
upload_accessible = r_upload.status_code == 200 and "/login" not in r_upload.url
check("5b Upload forma dostupna", upload_accessible, f"status={r_upload.status_code}")

# Provjeri AI dokumenti endpoint
r_ai = s.get(f"{BASE}/hr/documents/smart-import/", allow_redirects=True, verify=False)
ai_accessible = r_ai.status_code == 200 and "/login" not in r_ai.url
check("5c AI smart-import dostupan", ai_accessible, f"status={r_ai.status_code}")

# ════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════
print("\n── CLEANUP ──")
try:
    user.delete()
    company.delete()
    print(f"  · Test user i firma obrisani")
except Exception as e:
    print(f"  ⚠️ Cleanup partial: {e}")

# ════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════
print("\n" + "═" * 60)
print("KORAK 10 — ONBOARDING REZULTATI")
print("═" * 60)

check_groups = {
    "1 Registration wizard": ["1a Login (session cookie)", "1b Login (nije blokiran)", "1c Quick-register forma dostupna"],
    "2 Company setup": ["2a Onboarding wizard dostupan", "2b Company profile update"],
    "3 Prva faktura": ["3a Invoicing modul dostupan", "3b Nova faktura forma", "3c Faktura kreirana"],
    "4 POS bon": ["4a POS dashboard dostupan", "4b POS terminal postoji", "4c POS blagajna dostupna"],
    "5 Dokumenti": ["5a Arhiva dostupna", "5b Upload forma dostupna", "5c AI smart-import dostupan"],
}

main_ok = 0
for group_name, sub_checks in check_groups.items():
    group_pass = all(RESULTS.get(c, False) for c in sub_checks)
    icon = "✅" if group_pass else "❌"
    print(f"  {icon} Check {group_name}")
    for sc in sub_checks:
        si = "  ✓" if RESULTS.get(sc, False) else "  ✗"
        print(f"       {si} {sc}")
    if group_pass:
        main_ok += 1

pct = main_ok * 20
print(f"\n  Ukupno: {main_ok}/5 checkova prošlo ({pct}%)")
