import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('udruge')


@shared_task(bind=True, soft_time_limit=120)
def send_expiry_reminders(self):
    """Pon 09:00 — WhatsApp podsjetnici za istjecanje clanstva."""
    from .models import Clan
    from core.whatsapp import send_text

    today = timezone.now().date()
    expiring = Clan.objects.filter(
        status='aktivan',
        whatsapp_opt_in=True,
        membership_expires__gte=today,
        membership_expires__lte=today + timedelta(days=7),
    ).select_related('company')

    sent = 0
    for clan in expiring:
        phone = clan.whatsapp_phone or clan.phone
        if not phone:
            continue
        days = clan.days_until_expiry
        msg = 'Postovani %s, clanstvo u %s istice za %s dan(a). Kontaktirajte nas za obnovu.' % (
            clan.first_name, clan.company.name, days)
        try:
            result = send_text(phone=phone, message=msg, company_id=str(clan.company.pk))
            if result.get('ok'):
                sent += 1
        except Exception as e:
            logger.warning('WA expiry %s: %s', clan, e)

    return {'sent': sent}


@shared_task(bind=True, soft_time_limit=300)
def evaluate_subscriptions(self):
    """
    Svake noci u 02:00 — state machine za sve pretplate.
    active -> grace -> suspended
    + auto-renew za aktivne planove
    + dunning email za grace period
    """
    from .models import MemberSubscription, MembershipPlan, Clanarina

    today = timezone.now().date()
    processed = {'active': 0, 'grace': 0, 'suspended': 0, 'renewed': 0, 'reminded': 0}

    # Sve pretplate koje nisu cancelled/draft
    subs = MemberSubscription.objects.filter(
        status__in=['active', 'grace'],
    ).select_related('clan', 'plan', 'clan__company')

    for sub in subs:
        old_status = sub.status
        new_status = sub.evaluate_status()

        if new_status != old_status:
            processed[new_status] = processed.get(new_status, 0) + 1

        # Auto-renew: ako je active i istice za <= 3 dana
        if (new_status == 'active'
                and sub.plan.auto_renew
                and sub.valid_until
                and sub.days_remaining is not None
                and sub.days_remaining <= 3):
            # Kreiraj novu clanarinu
            try:
                new_until = sub.valid_until + timedelta(days=sub.plan.duration_days)
                existing = MemberSubscription.objects.filter(
                    clan=sub.clan, plan=sub.plan,
                    valid_from=sub.valid_until + timedelta(days=1),
                ).exists()
                if not existing:
                    clanarina = Clanarina.objects.create(
                        company=sub.clan.company,
                        clan=sub.clan,
                        period_start=sub.valid_until + timedelta(days=1),
                        period_end=new_until,
                        amount=sub.plan.price,
                        status='ceka',
                    )
                    MemberSubscription.objects.create(
                        company=sub.clan.company,
                        clan=sub.clan,
                        plan=sub.plan,
                        valid_from=sub.valid_until + timedelta(days=1),
                        valid_until=new_until,
                        status='draft',
                        clanarina=clanarina,
                    )
                    processed['renewed'] += 1
            except Exception as e:
                logger.warning('Auto-renew %s: %s', sub, e)

        # Dunning: ako je grace i reminder nije poslan danas
        if new_status == 'grace' and (
            not sub.reminder_sent_at
            or sub.reminder_sent_at.date() < today
        ):
            try:
                _send_dunning_reminder(sub)
                sub.reminder_sent_at = timezone.now()
                sub.reminders_count += 1
                sub.save(update_fields=['reminder_sent_at', 'reminders_count'])
                processed['reminded'] += 1
            except Exception as e:
                logger.warning('Dunning %s: %s', sub, e)

    logger.info('evaluate_subscriptions: %s', processed)
    return processed


def _send_dunning_reminder(sub):
    """Posalji email/WhatsApp podsjetnik za neplacenu clanarinu."""
    clan = sub.clan
    target = clan.billing_target

    # Pokusaj email
    if hasattr(target, 'email') and target.email:
        from django.core.mail import send_mail
        send_mail(
            subject='Podsjetnik: clanarina %s' % sub.plan.name,
            message=(
                'Postovani,\n\n'
                'Clanarina za %s (%s) je istekla %s.\n'
                'Molimo uplatite %s EUR u roku od %d dana.\n\n'
                'Hvala,\n%s'
            ) % (
                clan.full_name, sub.plan.name, sub.valid_until,
                sub.plan.price, sub.plan.grace_period_days,
                clan.company.name,
            ),
            from_email=None,
            recipient_list=[target.email],
            fail_silently=True,
        )

    # Pokusaj WhatsApp
    phone = getattr(clan, 'whatsapp_phone', '') or getattr(clan, 'phone', '')
    if phone and getattr(clan, 'whatsapp_opt_in', False):
        try:
            from core.whatsapp import send_text
            send_text(
                phone=phone,
                message='Podsjetnik: clanarina %s istekla %s. Molimo uplatite %s EUR. Hvala!' % (
                    sub.plan.name, sub.valid_until, sub.plan.price,
                ),
                company_id=str(clan.company.pk),
            )
        except Exception:
            pass


@shared_task(bind=True, soft_time_limit=60)
def check_access_card(self, card_uid, company_id):
    """
    IoT bridge: provjeri smije li kartica otvoriti vrata.
    Vraca {'allowed': bool, 'member': str, 'plan': str}
    """
    from .models import Clan, MemberSubscription

    try:
        clan = Clan.objects.get(
            access_card_uid=card_uid,
            company_id=company_id,
            status='aktivan',
        )
    except Clan.DoesNotExist:
        return {'allowed': False, 'reason': 'Kartica nije registrirana'}

    # Provjeri ima li aktivnu pretplatu
    active_sub = MemberSubscription.objects.filter(
        clan=clan,
        status__in=['active', 'grace'],
    ).select_related('plan').first()

    if not active_sub:
        return {'allowed': False, 'reason': 'Nema aktivnu clanarinu', 'member': clan.full_name}

    return {
        'allowed': True,
        'member': clan.full_name,
        'plan': active_sub.plan.name,
        'status': active_sub.status,
        'expires': str(active_sub.valid_until),
    }



@shared_task(bind=True, soft_time_limit=300)
def send_email_campaign(self, campaign_id):
    """Send email campaign to all recipients."""
    from .models import EmailKampanja, EmailLog
    from django.core.mail import send_mail
    from django.utils import timezone as tz

    campaign = EmailKampanja.objects.get(pk=campaign_id)
    if campaign.status != 'scheduled':
        return {'error': 'Not scheduled'}

    campaign.status = 'sending'
    campaign.save(update_fields=['status'])

    recipients = campaign.get_recipients()
    campaign.total_recipients = recipients.count()
    sent = 0

    for clan in recipients:
        try:
            send_mail(
                subject=campaign.subject,
                message=campaign.body_text or campaign.subject,
                html_message=campaign.body_html,
                from_email=None,
                recipient_list=[clan.email],
                fail_silently=True,
            )
            EmailLog.objects.create(
                kampanja=campaign, clan=clan, email=clan.email,
                status='sent', sent_at=tz.now(),
            )
            sent += 1
        except Exception as e:
            EmailLog.objects.create(
                kampanja=campaign, clan=clan, email=clan.email,
                status='error', error_message=str(e)[:255],
            )

    campaign.total_sent = sent
    campaign.status = 'sent'
    campaign.sent_at = tz.now()
    campaign.save()

    return {'sent': sent, 'total': campaign.total_recipients}
