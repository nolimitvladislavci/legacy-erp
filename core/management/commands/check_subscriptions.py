"""
core/management/commands/check_subscriptions.py

Provjera pretplata i računa — šalje WhatsApp podsjetnike.
Pokreće se jednom dnevno preko Celery beat-a.
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from core.notify import notify


# ── Pretplate za praćenje ──
SUBSCRIPTIONS = [
    {
        'name': 'Claude Max (Nikša)',
        'renewal_date': date(2026, 4, 27),
        'remind_days_before': [7, 3, 1],
        'action': 'Produžiti Max paket prije isteka',
        'owner': 'Nikša',
    },
    {
        'name': 'Hetzner server (Marija)',
        'renewal_date': date(2026, 5, 1),
        'remind_days_before': [7, 3, 1],
        'action': 'Marija treba uplatiti server',
        'owner': 'Marija',
    },
    {
        'name': 'Claude Pro (Kruljac)',
        'renewal_date': date(2026, 4, 27),
        'remind_days_before': [7, 3, 1],
        'action': 'Kruljac treba produžiti Pro paket',
        'owner': 'Kruljac',
    },
]


class Command(BaseCommand):
    help = 'Provjeri pretplate i pošalji podsjetnike'

    def handle(self, *args, **options):
        today = date.today()
        alerts = []

        for sub in SUBSCRIPTIONS:
            days_left = (sub['renewal_date'] - today).days

            if days_left < 0:
                alerts.append(
                    f"🔴 *{sub['name']}* — ISTEKLO prije {abs(days_left)} dana!\n"
                    f"   ➜ {sub['action']}"
                )
            elif days_left == 0:
                alerts.append(
                    f"🔴 *{sub['name']}* — ISTIČE DANAS!\n"
                    f"   ➜ {sub['action']}"
                )
            elif days_left in sub['remind_days_before']:
                alerts.append(
                    f"🟡 *{sub['name']}* — još {days_left} dana (istječe {sub['renewal_date'].strftime('%d.%m.')})\n"
                    f"   ➜ {sub['action']}"
                )

        if alerts:
            msg = "📋 *Podsjetnik — pretplate i računi*\n\n" + "\n\n".join(alerts)
            notify('ACTION', msg, urgent=False)
            self.stdout.write(self.style.SUCCESS(f'Poslano {len(alerts)} podsjetnika'))
        else:
            self.stdout.write('Nema podsjetnika za danas')
