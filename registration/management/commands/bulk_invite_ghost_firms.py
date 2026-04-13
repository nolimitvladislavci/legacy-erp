"""
Bulk invite za ghost firme (firme bez korisnika) u umbrelli.
Kreira invite tokene, ispisuje CSV za Mariju (WhatsApp/email slanje).

Koristi:
    python manage.py bulk_invite_ghost_firms --umbrella "Konjik"
    python manage.py bulk_invite_ghost_firms --umbrella "Konjik" --dry-run
    python manage.py bulk_invite_ghost_firms --umbrella "Konjik" > invites.csv
"""

import csv
import sys

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Bulk invite za ghost firme u umbrelli"

    def add_arguments(self, parser):
        parser.add_argument("--umbrella", type=str, required=True, help="Naziv umbrella firme")
        parser.add_argument("--dry-run", action="store_true", help="Samo prikaži, ne kreiraj")

    def handle(self, *args, **options):
        from accounts.models import UserProfile
        from companies.models import Company
        from registration.models import CompanyClaimRequest

        umbrella = Company.objects.filter(name__icontains=options["umbrella"]).first()
        if not umbrella:
            self.stderr.write(self.style.ERROR(f"Umbrella firma nije pronađena: {options['umbrella']}"))
            return

        # Ghost firme = u umbrelli, bez UserProfile-a
        all_children = Company.objects.filter(umbrella_parent=umbrella)
        ghost_ids = []
        for c in all_children:
            if not UserProfile.objects.filter(company=c).exists():
                ghost_ids.append(c.pk)

        children = Company.objects.filter(pk__in=ghost_ids).order_by("name")

        self.stderr.write(f"Umbrella: {umbrella.name} (OIB: {umbrella.oib})")
        self.stderr.write(f"Ghost firme: {children.count()} od {all_children.count()} ukupno")

        if options["dry_run"]:
            for c in children:
                self.stderr.write(f"  {c.name} | OIB: {c.oib}")
            return

        writer = csv.writer(sys.stdout)
        writer.writerow(["Firma", "OIB", "Invite URL", "WhatsApp poruka"])

        created = 0
        skipped = 0
        for firm in children:
            if CompanyClaimRequest.objects.filter(company=firm, status="pending").exists():
                skipped += 1
                continue

            claim = CompanyClaimRequest.objects.create(
                company=firm,
                email=f"vlasnik@{firm.oib}.pending",
                first_name="Vlasnik",
                oib_confirmed=True,
                role_claimed="company_admin",
                token_expires=timezone.now() + timezone.timedelta(days=30),
            )

            invite_url = f"https://limit-connect.com/firma/aktiviraj/{claim.verify_token}/"
            wa_msg = f"Pozdrav! Vasa firma *{firm.name}* je u LIMIT Connect sustavu. Aktivirajte pristup: {invite_url}"
            writer.writerow([firm.name, firm.oib, invite_url, wa_msg])
            created += 1

        self.stderr.write(self.style.SUCCESS(f"\nKreirano: {created} invite tokena, preskočeno: {skipped}"))
