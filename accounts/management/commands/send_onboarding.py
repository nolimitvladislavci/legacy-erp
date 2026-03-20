"""
Send onboarding emails to all users of a company who have not logged in yet.

Usage:
    python manage.py send_onboarding <company_uuid>
    python manage.py send_onboarding <company_uuid> --dry-run
    python manage.py send_onboarding <company_uuid> --password CustomPass123!
"""
import secrets
import string

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model

from companies.models import Company
from accounts.models import UserProfile

User = get_user_model()


def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Send onboarding emails to all new users of a company"

    def add_arguments(self, parser):
        parser.add_argument(
            "company_id",
            type=str,
            help="UUID of the company",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Set a specific temporary password for all users (default: auto-generate)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send even to users who have already logged in",
        )

    def handle(self, *args, **options):
        company_id = options["company_id"]
        dry_run = options["dry_run"]
        force = options["force"]
        fixed_password = options.get("password")

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            raise CommandError(f'Company with ID "{company_id}" does not exist.')
        except Exception as e:
            raise CommandError(f"Invalid company ID: {e}")

        self.stdout.write(f"\nCompany: {company.name} (ID: {company.pk})")
        mode_label = "DRY RUN" if dry_run else "LIVE"
        self.stdout.write(f"Mode: {mode_label}\n")

        profiles = UserProfile.objects.filter(
            company=company
        ).select_related("user")

        if not profiles.exists():
            self.stdout.write(self.style.WARNING("No users found for this company."))
            return

        sent_count = 0
        skipped_count = 0

        for profile in profiles:
            user = profile.user

            if user.last_login is not None and not force:
                self.stdout.write(
                    f"  SKIP  {user.username} ({user.email}) -- already logged in ({user.last_login})"
                )
                skipped_count += 1
                continue

            if not user.email:
                self.stdout.write(
                    self.style.WARNING(f"  SKIP  {user.username} -- no email address")
                )
                skipped_count += 1
                continue

            temp_password = fixed_password or generate_temp_password()

            user_name = user.get_full_name() or user.username
            context = {
                "user_name": user_name,
                "username": user.username,
                "company_name": company.name,
                "temp_password": temp_password,
            }

            if dry_run:
                self.stdout.write(
                    f"  WOULD SEND  {user.username} <{user.email}> (pass: {temp_password})"
                )
                sent_count += 1
                continue

            # Set the temporary password
            user.set_password(temp_password)
            user.save(update_fields=["password"])

            # Render HTML email
            html_message = render_to_string(
                "email/welcome_onboarding.html", context
            )
            plain_message = (
                f"Dobrodosli u LIMIT Connect, {user_name}!\n\n"
                f"Tvrtka: {company.name}\n"
                f"Korisnicko ime: {user.username}\n"
                f"Lozinka: {temp_password}\n\n"
                f"Prijava: https://limit-connect.com/accounts/login/\n\n"
                f"Molimo promijenite lozinku nakon prve prijave."
            )

            try:
                send_mail(
                    subject=f"Dobrodosli u LIMIT Connect -- {company.name}",
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  SENT  {user.username} <{user.email}>"
                    )
                )
                sent_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  FAIL  {user.username} <{user.email}> -- {e}"
                    )
                )

        action = "Would send" if dry_run else "Sent"
        self.stdout.write(f"\n{action}: {sent_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\nThis was a dry run. Use without --dry-run to actually send."
            ))
