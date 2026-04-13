"""
core/management/commands/bulk_invite.py

Bulk welcome invite za sve korisnike koji se nikad nisu prijavili.
Koordinator: Claude Sonnet | Executor: Claude Code | Reviewer: Gemini

Pokretanje:
  venv/bin/python manage.py bulk_invite --dry-run
  venv/bin/python manage.py bulk_invite --company "Konjik"
  venv/bin/python manage.py bulk_invite
"""

import secrets
import string

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = "Pošalji welcome invite svim korisnicima koji se nikad nisu prijavili"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Samo prikaži što bi se desilo, ne šalji emailove")
        parser.add_argument("--company", type=str, default=None, help="Filter po nazivu kompanije (parcijalni match)")
        parser.add_argument(
            "--force", action="store_true", help="Pošalji i korisnicima koji već imaju must_change_password=True"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        company_filter = options["company"]
        force = options["force"]

        from core.email_tasks import send_html_email_task
        from registration.models import CompanySubscription

        if dry_run:
            self.stdout.write(self.style.WARNING("═══ DRY RUN — ništa se ne šalje ═══\n"))

        # Dohvati aktivne pretplate
        subs = CompanySubscription.objects.filter(is_active=True).select_related("company").order_by("company__name")

        if company_filter:
            subs = subs.filter(company__name__icontains=company_filter)

        total_invited = 0
        total_no_email = 0
        total_skipped = 0
        no_email_list = []

        for sub in subs:
            company = sub.company

            # Korisnici koji NIKAD nisu ušli, imaju profil s ovom kompanijom
            qs = User.objects.filter(
                profile__company=company,
                last_login__isnull=True,
                is_active=True,
            ).select_related("profile")

            # Idempotentnost: preskoči one koji su već dobili invite
            # osim ako --force
            if not force:
                qs = qs.filter(profile__must_change_password=False)

            users = list(qs)
            if not users:
                continue

            self.stdout.write(f"\nKompanija: {self.style.SUCCESS(company.name)} — {len(users)} korisnika")

            for user in users:
                # Generiraj temp lozinku
                chars = string.ascii_letters + string.digits
                temp_pass = "".join(secrets.choice(chars) for _ in range(12))

                has_email = bool(user.email and user.email.strip())

                if dry_run:
                    status = f"({user.email})" if has_email else self.style.WARNING("(BEZ EMAILA)")
                    self.stdout.write(f"  [DRY RUN] {user.username} {status}")
                    if not has_email:
                        no_email_list.append((company.name, user.username))
                        total_no_email += 1
                    total_invited += 1
                    continue

                # --- Pravo slanje ---

                # 1. Postavi lozinku
                user.set_password(temp_pass)
                user.save(update_fields=["password"])

                # 2. Postavi must_change_password
                profile = user.profile
                profile.must_change_password = True
                profile.save(update_fields=["must_change_password"])

                # 3. Email — samo ako ima adresu
                if has_email:
                    try:
                        html_body = render_to_string(
                            "email/welcome_onboarding.html",
                            {
                                "user_name": user.get_full_name() or user.username,
                                "company_name": company.name,
                                "username": user.username,
                                "temp_password": temp_pass,
                                "login_url": "https://limit-connect.com/hr/accounts/login/",
                            },
                        )
                        text_body = (
                            f"Dobrodošli u LIMIT Connect!\n\n"
                            f"Tvrtka: {company.name}\n"
                            f"Korisničko ime: {user.username}\n"
                            f"Privremena lozinka: {temp_pass}\n\n"
                            f"Prijava: https://limit-connect.com/hr/accounts/login/\n\n"
                            f"Lozinku promijeni odmah pri prvom loginu."
                        )
                        send_html_email_task.delay(
                            subject=f"Dobrodošli u LIMIT Connect — {company.name}",
                            text_body=text_body,
                            html_body=html_body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email],
                        )
                        self.stdout.write(self.style.SUCCESS(f"  ✅ {user.username} ({user.email})"))
                        total_invited += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  ❌ {user.username} — email greška: {e}"))
                        total_skipped += 1
                else:
                    # Nema emaila — lozinka postavljena, ručna predaja
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠️  {user.username} — lozinka: {temp_pass} (ručna predaja, nema emaila)")
                    )
                    no_email_list.append((company.name, user.username, temp_pass))
                    total_no_email += 1
                    total_invited += 1

        # Finalni report
        self.stdout.write("\n" + "═" * 50)
        prefix = "[DRY RUN] " if dry_run else ""

        self.stdout.write(self.style.SUCCESS(f"{prefix}✅ Invited: {total_invited}"))
        if total_no_email:
            self.stdout.write(self.style.WARNING(f"{prefix}⚠️  Bez emaila (ručna predaja): {total_no_email}"))
        if total_skipped:
            self.stdout.write(self.style.ERROR(f"{prefix}❌ Greške: {total_skipped}"))

        if no_email_list and not dry_run:
            self.stdout.write("\n" + self.style.WARNING("KORISNICI BEZ EMAILA — ručno predaj lozinke:"))
            for item in no_email_list:
                if len(item) == 3:
                    self.stdout.write(f"  {item[0]} | {item[1]} | lozinka: {item[2]}")
