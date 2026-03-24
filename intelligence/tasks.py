"""
intelligence/tasks.py
Autonomni nocni patrol -- pokrece se svako jutro u 03:30.
"""
import logging
from celery import shared_task

logger = logging.getLogger('intelligence')


@shared_task(bind=True, soft_time_limit=600, max_retries=0)
def intelligence_nightly_patrol(self):
    """Pokrece se u 03:30 svako jutro."""
    from intelligence.models import IntelligenceJob
    from intelligence.services import run_intelligence_job
    from core.notify import notify

    jobs = IntelligenceJob.objects.filter(aktivan=True).select_related('company')
    total_results = 0
    total_sent = 0

    for job in jobs:
        try:
            results, sent = run_intelligence_job(job)
            total_results += results
            total_sent += sent
            logger.info('Intelligence job %s: %d rezultata, %d poslano', job.company.name, results, sent)
        except Exception as e:
            logger.error('Intelligence job failed %s: %s', job.company.name, e)

    notify('INFO', f'Inteligencija patrol zavrsen -- {total_results} pronalazaka, {total_sent} obavijesti poslano')
    return {'results': total_results, 'sent': total_sent}


@shared_task(bind=True, soft_time_limit=120)
def check_auto_listings(self):
    """
    Pokrece se svako jutro u 07:00.
    Ako CropPlan.auto_listing_ready -> kreira FuturesListing na Burzi.
    Ako Livestock krava u karenciji -> upozorava.
    """
    import datetime
    from livestock.models import CropPlan, Livestock
    from django.utils import timezone

    today = timezone.now().date()

    # Auto-listing za visak usjeva
    ready = CropPlan.objects.filter(
        za_prodaju=True,
        status__in=('berba', 'zavrseno'),
        procijenjeni_visak_t__gt=0,
    ).select_related('company')

    listed = 0
    for plan in ready:
        try:
            from intelligence.services import create_futures_listing_from_crop
            created = create_futures_listing_from_crop(plan)
            if created:
                listed += 1
        except Exception as e:
            logger.error('Auto-listing failed %s: %s', plan, e)

    # Upozorenje za krave koje tele uskoro
    grla = Livestock.objects.filter(
        expected_calving__range=(today, today + datetime.timedelta(days=21)),
        status='gravidno',
    ).select_related('company')

    for grlo in grla:
        try:
            from core.whatsapp import send_text
            from accounts.models import UserProfile
            admin = UserProfile.objects.filter(company=grlo.company, role='company_admin').first()
            if admin and admin.user:
                phone = getattr(admin.user, 'phone', '') or ''
                if phone:
                    days = (grlo.expected_calving - today).days
                    send_text(phone, f'Krava {grlo.ear_tag} ({grlo.name or "bez imena"}) teli za {days} dana!')
        except Exception as e:
            logger.error('Calving alert failed: %s', e)

    logger.info('Auto-listings: %d novih listinga, %d upozorenja za teljenje', listed, grla.count())
