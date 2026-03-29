from celery import shared_task


@shared_task(name='knjiznica.daily_overdue_check')
def daily_overdue_check():
    """
    Svaki dan u 08:00 — provjeri prekoračene rokove i pošalji podsjetnik.
    """
    from django.utils import timezone
    from .models import BookLoan

    today = timezone.localdate()
    overdue = BookLoan.objects.filter(
        status='borrowed', due_date__lt=today
    ).select_related('member__partner', 'item')

    count = 0
    for loan in overdue:
        loan.transition_to('overdue')
        count += 1

    # Također: expired rezervacije
    from .models import BookReservation
    expired = BookReservation.objects.filter(
        status='notified', expires_at__lt=today
    )
    expired_count = expired.count()
    expired.update(status='expired')

    return {
        'transitioned_to_overdue': count,
        'expired_reservations': expired_count,
    }
