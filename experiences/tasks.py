"""
experiences/tasks.py — Celery taskovi za Agro-Turizam 360
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('experiences')


@shared_task(bind=True, soft_time_limit=120)
def send_experience_reminders(self):
    """
    Svakih 6h — WhatsApp podsjetnik gostima za sutrašnje aktivnosti.
    18h prije + 2h prije.
    """
    from .models import ExperienceBooking, ExperienceSchedule
    from datetime import datetime

    now = timezone.now()
    tomorrow = now + timedelta(hours=18)

    # Nađi schedule-ove u sljedećih 18h
    upcoming = ExperienceSchedule.objects.filter(
        status='open',
        date__lte=(now + timedelta(hours=18)).date(),
        date__gte=now.date(),
    )

    notified = 0
    for sched in upcoming:
        sched_dt = timezone.make_aware(datetime.combine(sched.date, sched.time_from))
        hours_until = (sched_dt - now).total_seconds() / 3600

        # Šalji na 18h ili 2h prije
        if not (17 < hours_until < 19 or 1.5 < hours_until < 2.5):
            continue

        bookings = sched.bookings.filter(status='confirmed')
        for booking in bookings:
            phone = booking.guest_phone
            if not phone:
                continue
            try:
                from core.whatsapp import send_text
                msg = (
                    f'Podsjetnik: {sched.experience.name} sutra u {sched.time_from:%H:%M}. '
                    f'Lokacija: {sched.experience.meeting_point or "OPG"}. '
                    f'{sched.experience.what_to_bring or ""}'
                )
                send_text(
                    phone=phone,
                    message=msg,
                    company_id=str(sched.experience.company_id),
                )
                notified += 1
            except ImportError as e:
                logger.warning('Experience reminder %s: %s', booking.pk, e)

    return {'notified': notified}


@shared_task(bind=True, soft_time_limit=120)
def mark_no_shows(self):
    """
    Dnevno u 22:00 — označi no-show za nepojavljene goste.
    Depozit se automatski zadržava.
    """
    from .models import ExperienceBooking, ExperienceSchedule

    today = timezone.now().date()
    past_schedules = ExperienceSchedule.objects.filter(
        date=today,
        status='open',
    )

    marked = 0
    for sched in past_schedules:
        # Nađi potvrđene bookinge koji se nisu pojavili
        no_shows = sched.bookings.filter(status='confirmed')
        for booking in no_shows:
            booking.mark_no_show()
            marked += 1

        # Označi schedule kao završen
        sched.status = 'completed'
        sched.save(update_fields=['status'])

    return {'no_shows_marked': marked}


@shared_task(bind=True, soft_time_limit=60)
def send_recall_notifications(self):
    """Pošalji pending recall notifikacije."""
    from .models import RecallNotification

    pending = RecallNotification.objects.filter(status='pending')
    sent = 0
    failed = 0

    for notif in pending[:100]:  # Batch od 100
        try:
            if notif.channel == 'whatsapp' and notif.recipient_contact:
                from core.whatsapp import send_text
                send_text(
                    phone=notif.recipient_contact,
                    message=notif.message,
                    company_id=str(notif.recall.company_id),
                )
            elif notif.channel == 'email' and '@' in notif.recipient_contact:
                from django.core.mail import send_mail
                send_mail(
                    subject=f'RECALL: {notif.recall.title}',
                    message=notif.message,
                    from_email=None,
                    recipient_list=[notif.recipient_contact],
                    fail_silently=False,
                )

            notif.status = 'sent'
            notif.sent_at = timezone.now()
            sent += 1
        except Exception as e:
            notif.status = 'failed'
            notif.error_message = str(e)[:500]
            failed += 1

        notif.save()

    return {'sent': sent, 'failed': failed}


@shared_task(bind=True, soft_time_limit=120)
def inventory_depletion_check(self):
    """
    Svakih 6h — provjeri hoće li zalihe izdržati za sutrašnje aktivnosti.
    Upozorava: "Ako prodaš još 5 paketa, nećeš imati dovoljno jagoda za doručak."
    """
    from .models import Experience, ExperienceSchedule, ExperienceInclusion
    from inventory.models import InventoryItem

    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    # Nađi sutrašnje schedule-ove
    tomorrow_schedules = ExperienceSchedule.objects.filter(
        date=tomorrow, status='open',
    ).select_related('experience')

    alerts = []
    for sched in tomorrow_schedules:
        inclusions = ExperienceInclusion.objects.filter(
            experience=sched.experience,
            inventory_item__isnull=False,
        ).select_related('inventory_item')

        for incl in inclusions:
            needed = float(incl.quantity_per_person) * sched.booked_pax
            available = float(incl.inventory_item.quantity)

            if needed > available:
                alerts.append({
                    'experience': sched.experience.name,
                    'item': incl.inventory_item.name,
                    'needed': needed,
                    'available': available,
                    'shortage': needed - available,
                })

    if alerts:
        logger.warning('Inventory depletion alerts: %s', alerts)

    return {'alerts': alerts}
