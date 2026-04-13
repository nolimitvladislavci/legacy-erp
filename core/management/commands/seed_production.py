"""
python manage.py seed_production

Pokreni JEDNOM na praznoj bazi. Kreira minimalni production dataset
za funkcionalan sustav:
  1. Superadmin korisnik
  2. Firma VISKOVIC NIKSA, Herrenberg DE
  3. BusinessProfile s enterprise modulima
  4. Enterprise pretplata
  5. Žiro račun (Commerzbank)
  6. Kontni plan (via seed_chart_of_accounts ako postoji)
  7. Pricing planovi (via seed_pricing_plans)
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Seed minimal production data (run once on empty DB)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even if superadmin already exists",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options.get("force", False)

        # ── 1. Superadmin ────────────────────────────────────────────────────
        if not force and User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING(
                "⚠  Superadmin already exists. Use --force to re-run."
            ))
        else:
            admin, created = User.objects.get_or_create(
                username="ivan.medija@gmail.com",
                defaults={
                    "email": "ivan.medija@gmail.com",
                    "first_name": "Ivan",
                    "last_name": "Medija",
                    "is_superuser": True,
                    "is_staff": True,
                },
            )
            if created:
                admin.set_password("s5Jtkn66!")
                admin.save()
            else:
                admin.is_superuser = True
                admin.is_staff = True
                admin.save()

            from accounts.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(
                user=admin,
                defaults={"role": "company_admin"},
            )
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])

            self.stdout.write(self.style.SUCCESS(
                "✅ Superadmin: ivan.medija@gmail.com  (mora promijeniti lozinku)"
            ))

        # ── 2. Firma VISKOVIC NIKSA ──────────────────────────────────────────
        from companies.models import BusinessProfile, Company
        company, created = Company.objects.get_or_create(
            name="VISKOVIC NIKSA",
            defaults={
                "address": "Bongert 13",
                "city": "Herrenberg",
                "zip_code": "71083",
                "country": Company.Country.DE,
                "oib": "56447/32919",
                "iban": "DE10603400710803121300",
                "currency": Company.Currency.EUR,
                "is_vat_registered": False,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                "✅ Firma: VISKOVIC NIKSA, Herrenberg DE"
            ))
        else:
            self.stdout.write(self.style.WARNING("⚠  Firma VISKOVIC NIKSA already exists"))

        # ── 3. Poveži admina s firmom ─────────────────────────────────────────
        admin = User.objects.filter(is_superuser=True).order_by("id").first()
        if admin:
            from accounts.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=admin)
            if not profile.company:
                profile.company = company
                profile.role = "company_admin"
                profile.save(update_fields=["company", "role"])
                self.stdout.write(self.style.SUCCESS("✅ Admin povezan s firmom"))

        # ── 4. BusinessProfile s enterprise modulima ─────────────────────────
        bp, created = BusinessProfile.objects.get_or_create(
            company=company,
            defaults={
                "profile_type": BusinessProfile.ProfileType.CUSTOM,
                "module_invoicing": True,
                "module_pos": True,
                "module_inventory": True,
                "module_appointments": True,
                "module_projects": True,
                "module_worktime": True,
                "module_finance": True,
                "module_partners": True,
                "module_documents": True,
                "module_webshop": False,
                "module_rental": False,
                "module_fitness": False,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("✅ BusinessProfile kreiran (construction profile)"))

        # ── 5. Pricing planovi ────────────────────────────────────────────────
        try:
            from django.core.management import call_command
            call_command("seed_pricing_plans", verbosity=0)
            self.stdout.write(self.style.SUCCESS("✅ Pricing planovi kreirani"))
        except ImportError as e:
            self.stdout.write(self.style.WARNING(f"⚠  seed_pricing_plans: {e}"))

        # ── 6. Enterprise pretplata ───────────────────────────────────────────
        try:
            from registration.models import CompanySubscription, PricingPlan
            enterprise = PricingPlan.objects.filter(slug="enterprise").first()
            if enterprise:
                sub, created = CompanySubscription.objects.get_or_create(
                    company=company,
                    defaults={
                        "plan": "enterprise",
                        "pricing_plan": enterprise,
                        "is_active": True,
                    },
                )
                if not created and not sub.is_active:
                    sub.is_active = True
                    sub.save(update_fields=["is_active"])
                self.stdout.write(self.style.SUCCESS("✅ Enterprise pretplata aktivna"))
            else:
                self.stdout.write(self.style.WARNING("⚠  Enterprise pricing plan nije pronađen"))
        except DatabaseError as e:
            self.stdout.write(self.style.WARNING(f"⚠  Pretplata: {e}"))

        # ── 7. Žiro račun (Commerzbank) ────────────────────────────────────────
        try:
            from konto.models import BankAccount
            ba, created = BankAccount.objects.get_or_create(
                company=company,
                iban="DE10603400710803121300",
                defaults={
                    "name": "Commerzbank Hauptkonto",
                    "bank_name": "Commerzbank",
                    "swift": "COBADEFFXXX",
                    "currency": "EUR",
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS("✅ Žiro račun: Commerzbank DE10 6034 0071 0803 1213 00"))
        except DatabaseError as e:
            self.stdout.write(self.style.WARNING(f"⚠  BankAccount: {e}"))

        # ── 8. Kontni plan ────────────────────────────────────────────────────
        try:
            from django.core.management import call_command
            call_command("seed_chart_of_accounts", verbosity=0)
            self.stdout.write(self.style.SUCCESS("✅ Kontni plan kreiran"))
        except ImportError as e:
            self.stdout.write(self.style.WARNING(f"⚠  seed_chart_of_accounts: {e}"))

        self.stdout.write("\n" + self.style.SUCCESS(
            "🎉 Production seed završen! "
            "Prijavi se na /login/ s: ivan.medija@gmail.com / s5Jtkn66!"
        ))
