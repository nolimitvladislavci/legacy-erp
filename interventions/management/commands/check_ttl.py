"""
Management command: check_ttl
Checks DODIJELJENO interventions whose TTL has expired.
Reassigns to next available worker or resets to NOVO.

Add to crontab:
  * * * * * /var/www/fina-connect/venv/bin/python /var/www/fina-connect/manage.py check_ttl >> /var/log/fina-ttl.log 2>&1
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Check TTL for DODIJELJENO interventions and reassign or reset to NOVO'

    def handle(self, *args, **options):
        from django.contrib.auth.models import User

        from accounts.models import UserProfile
        from interventions.models import HitnaIntervencija

        expired = list(HitnaIntervencija.objects.unscoped().filter(
            status=HitnaIntervencija.Status.DODIJELJENO,
            ttl_expires_at__lt=timezone.now(),
        ))

        if not expired:
            self.stdout.write('TTL check: 0 expired interventions.')
            return

        processed = 0
        for interv in expired:
            try:
                with transaction.atomic():
                    # Re-read with lock
                    interv = HitnaIntervencija.objects.unscoped().select_for_update().get(pk=interv.pk)
                    if interv.status != HitnaIntervencija.Status.DODIJELJENO:
                        continue  # Already changed by concurrent request

                    # Find busy user IDs in this company
                    busy_ids = set(HitnaIntervencija.objects.unscoped().filter(
                        company=interv.company,
                        status__in=[
                            HitnaIntervencija.Status.DODIJELJENO,
                            HitnaIntervencija.Status.NA_PUTU,
                            HitnaIntervencija.Status.NA_LOKACIJI,
                        ]
                    ).exclude(pk=interv.pk).values_list('assigned_to_id', flat=True))

                    # Company users
                    company_user_ids = UserProfile.objects.filter(
                        company=interv.company
                    ).values_list('user_id', flat=True)

                    # Find available worker (not busy, not current, active)
                    available = User.objects.filter(
                        id__in=company_user_ids,
                        is_active=True,
                    ).exclude(id__in=busy_ids).exclude(id=interv.assigned_to_id).first()

                    if available:
                        old_name = interv.assigned_to.username if interv.assigned_to else '–'
                        interv.assigned_to = available
                        interv.assigned_at = timezone.now()
                        interv.ttl_expires_at = timezone.now() + timedelta(minutes=3)
                        interv.save(update_fields=['assigned_to', 'assigned_at', 'ttl_expires_at'])
                        self.stdout.write(
                            f'  #{interv.pk} "{interv.title}": reassigned {old_name} → {available.username}'
                        )
                        # Push notifikacija novom radniku
                        try:
                            from push_notifications.push import send_push_to_user
                            send_push_to_user(
                                available,
                                title='Intervencija dodijeljena',
                                body=f'{interv.title} – {interv.address or interv.client_name}',
                                url=f'/interventions/{interv.pk}/field/',
                            )
                        except Exception as _pe:
                            self.stderr.write(f'  Push error: {_pe}')
                        # WhatsApp notification
                        try:
                            from core.whatsapp_tasks import send_intervention_assignment_whatsapp
                            send_intervention_assignment_whatsapp.delay(interv.pk, available.pk)
                        except Exception:
                            pass
                    else:
                        # No available worker – reset to NOVO
                        interv.status = HitnaIntervencija.Status.NOVO
                        interv.assigned_to = None
                        interv.assigned_at = None
                        interv.ttl_expires_at = None
                        interv.save(update_fields=['status', 'assigned_to', 'assigned_at', 'ttl_expires_at'])
                        self.stdout.write(
                            f'  #{interv.pk} "{interv.title}": reset to NOVO (no workers available)'
                        )
                    processed += 1

            except Exception as e:
                self.stderr.write(f'  ERROR #{interv.pk}: {e}')

        self.stdout.write(f'TTL check: {processed} intervention(s) processed at {timezone.now():%Y-%m-%d %H:%M:%S}')
