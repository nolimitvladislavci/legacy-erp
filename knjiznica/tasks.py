"""
Knjižnica — Celery tasks.

1. daily_overdue_check: 08:00 — tranzicija u overdue + expired rezervacije
2. membership_expiry_check: ponedjeljak 09:00 — WhatsApp upozorenje 7 dana pred istek
3. weekly_reading_digest: nedjelja 18:00 — roditelju tjedni pregled djece
4. expire_challenges: ponoć — istekli izazovi
"""
from celery import shared_task


@shared_task(name='knjiznica.daily_overdue_check')
def daily_overdue_check():
    """Svaki dan u 08:00 — provjeri prekoračene rokove i pošalji podsjetnik."""
    from django.utils import timezone
    from .models import BookLoan, BookReservation

    today = timezone.localdate()
    overdue = BookLoan.objects.filter(
        status='borrowed', due_date__lt=today
    ).select_related('member__partner', 'item')

    count = 0
    for loan in overdue:
        loan.transition_to('overdue')
        count += 1

    # Expired rezervacije
    expired = BookReservation.objects.filter(
        status='notified', expires_at__lt=today
    )
    expired_count = expired.count()
    expired.update(status='expired')

    return {
        'transitioned_to_overdue': count,
        'expired_reservations': expired_count,
    }


@shared_task(name='knjiznica.membership_expiry_check')
def membership_expiry_check():
    """Ponedjeljak 09:00 — upozorenje za članove kojima ističe iskaznica za 7 dana."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import LibraryMember

    today = timezone.localdate()
    warn_date = today + timedelta(days=7)

    expiring = LibraryMember.objects.filter(
        status__in=['active', 'junior'],
        membership_until__lte=warn_date,
        membership_until__gte=today,
    ).select_related('partner')

    count = 0
    for member in expiring:
        try:
            from core.whatsapp import send_text
            phone = member.partner.phone
            if phone:
                send_text(phone=phone, message=(
                    f'Knjiznica — istek clanarine\n'
                    f'Vasa iskaznica {member.member_number} istice {member.membership_until}.\n'
                    f'Molimo obnovite clanarinu u knjiznici.'
                ))
                count += 1
        except Exception:
            pass

    return f'{count} expiry warnings sent'


@shared_task(name='knjiznica.weekly_reading_digest')
def weekly_reading_digest():
    """Nedjelja 18:00 — roditelju šalje tjedni pregled čitanja djece."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import LibraryMember, ChildReader, ReadingLog

    today = timezone.localdate()
    week_ago = today - timedelta(days=7)

    count = 0
    for member in LibraryMember.objects.filter(
        status__in=['active', 'junior'],
    ).select_related('partner'):
        children = ChildReader.objects.filter(parent=member)
        if not children.exists():
            continue

        lines = [f'Tjedni pregled citanja ({week_ago} - {today})\n']
        has_activity = False

        for child in children:
            logs = ReadingLog.objects.filter(
                child=child, read_date__gte=week_ago
            )
            if logs.exists():
                has_activity = True
                lines.append(f'{child.first_name}: {logs.count()} knjiga, '
                             f'{child.total_points} bodova, level: {child.level}')
            else:
                lines.append(f'{child.first_name}: bez aktivnosti ovaj tjedan')

        if not has_activity:
            continue

        try:
            from core.whatsapp import send_text
            phone = member.partner.phone
            if phone:
                send_text(phone=phone, message='\n'.join(lines))
                count += 1
        except Exception:
            pass

    return f'{count} weekly digests sent'


@shared_task(name='knjiznica.expire_challenges')
def expire_challenges():
    """Ponoć — označi istekle FamilyChallenge."""
    from django.utils import timezone
    from .models import FamilyChallenge

    today = timezone.localdate()
    expired = FamilyChallenge.objects.filter(
        status='active', ends_at__lt=today
    )
    count = expired.count()
    expired.update(status='expired')
    return f'{count} challenges expired'
