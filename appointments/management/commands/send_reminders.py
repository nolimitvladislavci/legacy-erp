"""
Send appointment reminders for tomorrow.
Usage: python manage.py send_reminders
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send email/WhatsApp reminders for appointments tomorrow"

    def handle(self, *args, **options):
        from appointments.tasks import send_appointment_reminders
        result = send_appointment_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {result['email']} email + {result['whatsapp']} WhatsApp "
                f"reminders (of {result['total']} appointments)"
            )
        )
