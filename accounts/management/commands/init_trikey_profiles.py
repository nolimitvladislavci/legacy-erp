"""
Management komanda: Kreira TriKeyProfile za sve postojeće korisnike koji ga nemaju.
Pokretanje: python manage.py init_trikey_profiles
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.trikey import TriKeyProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Kreira TriKeyProfile za sve korisnike koji ga nemaju"

    def handle(self, *args, **options):
        existing_user_ids = set(TriKeyProfile.objects.values_list("user_id", flat=True))
        users_without = User.objects.exclude(pk__in=existing_user_ids)
        count = users_without.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Svi korisnici već imaju TriKeyProfile."))
            return

        profiles = [TriKeyProfile(user=user) for user in users_without]
        TriKeyProfile.objects.bulk_create(profiles)

        self.stdout.write(self.style.SUCCESS(f"Kreirano {count} TriKeyProfile profila."))
