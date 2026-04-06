"""
Kreira besplatni tenant za azil u LIMIT Connect sustavu.

Usage:
    python manage.py setup_azil_tenant --name="Azil Osijek" --email="info@azil-osijek.hr" --city="Osijek"
    python manage.py setup_azil_tenant --name="Azil Zagreb" --email="azil@zagreb.hr" --city="Zagreb" --oib=12345678901
"""

import uuid

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from accounts.models import UserProfile
from companies.models import Company


class Command(BaseCommand):
    help = "Kreira besplatni tenant (Company + User + Profile) za azil"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Naziv azila/udruge")
        parser.add_argument("--email", required=True, help="Email kontakt osobe")
        parser.add_argument("--city", default="", help="Grad")
        parser.add_argument("--oib", default="", help="OIB (opcijsko — generira se placeholder ako prazno)")
        parser.add_argument("--password", default="Azil2026!", help="Inicijalna lozinka")

    def handle(self, *args, **options):
        name = options["name"].strip()
        email = options["email"].strip().lower()
        city = options["city"].strip()
        oib = options["oib"].strip()
        password = options["password"]

        if not name or not email:
            raise CommandError("--name i --email su obavezni.")

        # OIB placeholder za azile bez registriranog OIB-a
        if not oib:
            oib = f"AZIL-{uuid.uuid4().hex[:8].upper()}"

        # 1. Kreiraj Company
        if Company.objects.filter(oib=oib).exists():
            company = Company.objects.get(oib=oib)
            self.stdout.write(f"Company već postoji: {company.name} ({company.oib})")
        else:
            company = Company.objects.create(
                name=name,
                oib=oib,
                city=city,
                country="HR",
                business_type="udruga",
                currency="EUR",
                fiscal_system="none",
                fiscal_exempt=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Company kreiran: {company.name} ({company.oib})"))

        # 2. Kreiraj User
        username = email.split("@")[0].replace(".", "_")[:30]
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            self.stdout.write(f"User već postoji: {user.username}")
        elif User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            self.stdout.write(f"User već postoji: {user.username}")
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=name[:30],
            )
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"User kreiran: {user.username} / {password}"))

        # 3. Kreiraj ili ažuriraj UserProfile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={"company": company, "role": "company_admin"},
        )
        if not created:
            profile.company = company
            profile.role = "company_admin"
            profile.save()
            self.stdout.write(f"Profile ažuriran → company: {company.name}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Profile kreiran → company: {company.name}"))

        # 4. Označi AzilPrijava kao contacted (ako postoji)
        try:
            from no_limit.models import AzilPrijava
            prijave = AzilPrijava.objects.filter(email=email, contacted=False)
            count = prijave.update(contacted=True)
            if count:
                self.stdout.write(f"Označeno {count} prijava kao contacted.")
        except Exception:
            pass

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== AZIL TENANT SETUP GOTOV ==="))
        self.stdout.write(f"  Firma:    {company.name}")
        self.stdout.write(f"  OIB:      {company.oib}")
        self.stdout.write(f"  Login:    {user.username} / {password}")
        self.stdout.write(f"  URL:      https://limit-connect.com/hr/login/")
        self.stdout.write(f"  POS tema: body.theme-azil (automatski za udruge)")
