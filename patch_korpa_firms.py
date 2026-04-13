"""
patch_korpa_firms.py
Ažurira podatke Korpa klijenata iz Synesis arhive:
- Popunjava Company polja (email, phone, address, zip, iban)
- Kreira korisnike za firme koje nemaju nijednog
- Dodaje email Marijinoj adresi (konjik_admin nadzire ove firme)
"""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
sys.path.insert(0, "/var/www/fina-connect")
django.setup()

from django.contrib.auth.models import User
from django.db import transaction

from accounts.models import UserProfile
from companies.models import Company

# ─── PODACI IZ SYNESIS ARHIVE ─────────────────────────────────────────────────
# Marija Brtan je odgovorna osoba / računovotkinja za sve ove firme
# Koristimo @limit-connect.com email format ako nema vlastitog

FIRMS = [
    {
        "oib": "92922919857",
        "name": "Korpaš d.o.o.",
        "address": "Kr. Tomislava 291",
        "city": "Vladislavci",
        "zip_code": "31404",
        "phone": "",
        "email": "korpas.doo@gmail.com",  # već ima vlastiti
        "iban": "HR8324020061100660250",
        "contact": "Katarina Furdi",
        "username": "katarina.furdi",  # user već postoji
        "user_email": "katarina.furdi@limit-connect.com",
    },
    {
        "oib": "12817544866",
        "name": "KUD Dukat Vladislavci",
        "address": "Erne Kiša 3",
        "city": "Vladislavci",
        "zip_code": "31404",
        "phone": "031391098",
        "email": "kud.dukat@limit-connect.com",
        "iban": "HR6423900011101266976",
        "contact": "Katarina Furdi",
        "username": "kud.dukat",
        "user_email": "kud.dukat@limit-connect.com",
    },
    {
        "oib": "41439993573",
        "name": "O.P.G. Kruljac Slađana",
        "address": "Kr. Tomislava 291",
        "city": "Vladislavci",
        "zip_code": "31404",
        "phone": "",
        "email": "opg.kruljac@limit-connect.com",
        "iban": "HR4224020061140216521",
        "contact": "Slađana Kruljac",
        "username": "opg_kruljac",  # user već postoji, samo ažuriramo email
        "user_email": "opg.kruljac@limit-connect.com",
    },
    {
        "oib": "88069902084",
        "name": "Furdi, obrt za građevinske radove",
        "address": "Lipovac Hrastinski 19 A",
        "city": "Lipovac Hrastinski",
        "zip_code": "31403",
        "phone": "",
        "email": "furdi.obrt@limit-connect.com",
        "iban": "HR8325000091101579260",
        "contact": "Marko Furdi",
        "username": "furdi.obrt",
        "user_email": "furdi.obrt@limit-connect.com",
    },
    {
        "oib": "69824516722",
        "name": "Dubinsko Čišćenje Čizo",
        "address": "Kr. Tomislava 220",
        "city": "Vladislavci",
        "zip_code": "31404",
        "phone": "",
        "email": "cizo.ciscenje@limit-connect.com",
        "iban": "HR6224070001100232010",
        "contact": "",
        "username": "cizo.ciscenje",
        "user_email": "cizo.ciscenje@limit-connect.com",
    },
]

print("=== PATCH KORPA FIRMI ===\n")

with transaction.atomic():
    for f in FIRMS:
        c = Company.objects.filter(oib=f["oib"]).first()
        if not c:
            print(f"  ⚠️  FIRMA NIJE PRONAĐENA: {f['name']} ({f['oib']}) — preskačem")
            continue

        # ── 1. Ažuriraj Company polja ──────────────────────────────────────
        changed = []
        if not c.email and f["email"]:
            c.email = f["email"]
            changed.append(f"email={f['email']}")
        if not c.address and f["address"]:
            c.address = f["address"]
            changed.append(f"address={f['address']}")
        if not c.city and f["city"]:
            c.city = f["city"]
            changed.append(f"city={f['city']}")
        if not c.zip_code and f["zip_code"]:
            c.zip_code = f["zip_code"]
            changed.append(f"zip={f['zip_code']}")
        if not c.phone and f["phone"]:
            c.phone = f["phone"]
            changed.append(f"phone={f['phone']}")
        # IBAN — provjeri postoji li polje
        if hasattr(c, "iban") and not c.iban and f["iban"]:
            c.iban = f["iban"]
            changed.append(f"iban={f['iban'][:10]}...")

        c.save()
        print(f"  ✅ {c.name} ({f['oib']})")
        if changed:
            for ch in changed:
                print(f"     + {ch}")
        else:
            print("     (sva polja već popunjena)")

        # ── 2. User: kreiraj ili ažuriraj ─────────────────────────────────
        existing_user = User.objects.filter(username=f["username"]).first()

        if existing_user:
            # Ažuriraj email ako ga nema
            if not existing_user.email and f["user_email"]:
                existing_user.email = f["user_email"]
                existing_user.save()
                print(f"     User '{f['username']}' → email ažuriran: {f['user_email']}")
            else:
                print(f"     User '{f['username']}' već postoji (email: {existing_user.email or 'NEMA'})")

            # Provjeri UserProfile — company link
            try:
                profile = existing_user.profile
                if profile.company != c:
                    profile.company = c
                    profile.save()
                    print(f"     UserProfile → company linkan na {c.name}")
            except (IntegrityError, DatabaseError):
                pass

        else:
            # Kreiraj novog usera
            import secrets

            password = secrets.token_urlsafe(12)
            new_user = User.objects.create_user(
                username=f["username"],
                email=f["user_email"],
                password=password,
                first_name=f["contact"].split()[0] if f["contact"] else "",
                last_name=" ".join(f["contact"].split()[1:]) if f["contact"] else "",
                is_active=True,
            )
            # UserProfile
            try:
                profile = new_user.profile
            except AttributeError:
                profile = UserProfile(user=new_user)

            profile.company = c
            profile.role = "company_admin"
            profile.save()

            print(f"     ✨ User KREIRAN: {f['username']} / {f['user_email']}")
            print(f"     🔑 Password: {password}  ← ZABILJEŽI OVO!")

print()
print("=== ZAVRŠENO ===")
