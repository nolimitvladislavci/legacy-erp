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
    """
    Send email campaign with rate limiting.
    Batch: 50 emails, 2s pause between batches.
    Prevents SMTP blacklisting and spam flags.
    """
    import time
    from .models import EmailKampanja, EmailLog
    from django.core.mail import send_mail
    from django.utils import timezone as tz

    BATCH_SIZE = 50
    BATCH_DELAY = 2  # seconds between batches

    campaign = EmailKampanja.objects.get(pk=campaign_id)
    if campaign.status != 'scheduled':
        return {'error': 'Not scheduled'}

    campaign.status = 'sending'
    campaign.save(update_fields=['status'])

    recipients = list(campaign.get_recipients())
    campaign.total_recipients = len(recipients)
    campaign.save(update_fields=['total_recipients'])

    sent = 0
    errors = 0
    bounced_emails = set()

    # Load previously bounced emails (don't resend)
    bounced_emails = set(
        EmailLog.objects.filter(
            kampanja__company=campaign.company, status='bounced',
        ).values_list('email', flat=True).distinct()
    )

    for i, clan in enumerate(recipients):
        # Skip bounced
        if clan.email.lower() in bounced_emails:
            EmailLog.objects.create(
                kampanja=campaign, clan=clan, email=clan.email,
                status='bounced', error_message='Previously bounced — skipped',
            )
            continue

        try:
            send_mail(
                subject=campaign.subject,
                message=campaign.body_text or campaign.subject,
                html_message=campaign.body_html,
                from_email=None,
                recipient_list=[clan.email],
                fail_silently=False,
            )
            EmailLog.objects.create(
                kampanja=campaign, clan=clan, email=clan.email,
                status='sent', sent_at=tz.now(),
            )
            sent += 1
        except Exception as e:
            err_msg = str(e)[:255]
            status = 'bounced' if 'bounce' in err_msg.lower() or '550' in err_msg else 'error'
            EmailLog.objects.create(
                kampanja=campaign, clan=clan, email=clan.email,
                status=status, error_message=err_msg,
            )
            errors += 1

        # Rate limit: pause every BATCH_SIZE emails
        if (i + 1) % BATCH_SIZE == 0 and i < len(recipients) - 1:
            # Update progress mid-campaign
            campaign.total_sent = sent
            campaign.save(update_fields=['total_sent'])
            time.sleep(BATCH_DELAY)

    campaign.total_sent = sent
    campaign.total_bounced = errors
    campaign.status = 'sent'
    campaign.sent_at = tz.now()
    campaign.save()

    logger.info('Email campaign %s: sent=%d, errors=%d, total=%d',
                campaign.name, sent, errors, len(recipients))

    return {'sent': sent, 'errors': errors, 'total': len(recipients)}


@shared_task(bind=True, soft_time_limit=120)
def ai_search_eu_funds(self, company_id):
    """AI pretraga EU fondova — pronalazi relevantne natjecaje za udrugu."""
    import os, json
    from django.db.models import Sum
    from companies.models import Company
    from .models import Clan, Kampanja, Donacija

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}

    member_count = Clan.objects.filter(company=company, status='aktivan').count()
    annual_budget = Donacija.objects.filter(
        company=company, date__year=timezone.now().year,
    ).aggregate(s=Sum('amount'))['s'] or 0
    existing_eu = list(Kampanja.objects.filter(
        company=company, campaign_type='eu_fond',
    ).values_list('eu_program', 'eu_project_code', 'name'))

    profile = json.dumps({
        'name': company.name,
        'type': getattr(company, 'business_type', 'udruga'),
        'city': getattr(company, 'city', ''),
        'members': member_count,
        'annual_budget_eur': float(annual_budget),
        'existing_eu_projects': [{'program': p, 'code': c, 'name': n} for p, c, n in existing_eu],
    }, ensure_ascii=False)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        prompt = (
            'Analiziraj profil hrvatske udruge i predlozi 3-5 relevantnih EU fondova/natjecaja.\n'
            'Fokus: ESF+, ERDF, Erasmus+, CERV, Horizon Europe, Creative Europe.\n'
            'PROFIL:\n%s\n\n'
            'Odgovori ISKLJUCIVO kao JSON array:\n'
            '[{"program":"ESF+","name":"Naziv","amount_range":"50000-150000",'
            '"deadline":"2026-06-30","relevance":"Opis","priority":"high"}]'
        ) % profile

        response = client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}])
        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0]
        suggestions = json.loads(text)
        created = 0
        for s in suggestions:
            if not s.get('name'):
                continue
            exists = Kampanja.objects.filter(
                company=company, campaign_type='eu_fond',
                eu_program=s.get('program', ''),
                name__icontains=s.get('name', '')[:50]).exists()
            if exists:
                continue
            deadline = None
            try:
                from datetime import datetime as dt
                deadline = dt.strptime(s.get('deadline', ''), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
            amount = 0
            amt = str(s.get('amount_range', '0'))
            if '-' in amt:
                try:
                    amount = int(amt.split('-')[-1])
                except ValueError:
                    pass
            Kampanja.objects.create(
                company=company, name=s['name'][:200], campaign_type='eu_fond',
                description='AI preporuka: %s' % s.get('relevance', ''),
                start_date=timezone.now().date(), end_date=deadline,
                goal_amount=amount, eu_program=s.get('program', '')[:200],
                eu_status='preparing', status='draft',
                notes='AI generirao %s. Prioritet: %s.' % (
                    timezone.now().strftime('%d.%m.%Y.'), s.get('priority', 'medium')))
            created += 1
        logger.info('AI EU fund search %s: %d suggestions, %d created', company.name, len(suggestions), created)
        return {'suggestions': len(suggestions), 'created': created}
    except Exception as e:
        logger.error('AI EU fund search %s: %s', company.name, e)
        return {'error': str(e)}


@shared_task(bind=True, soft_time_limit=60)
def generate_volunteer_summary(self, company_id, year=None):
    """Sumarni izvjestaj volonterskih aktivnosti za godinu."""
    from .models import VolunteerActivity
    from django.db.models import Sum, Count
    from companies.models import Company
    if not year:
        year = timezone.now().year
    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}
    activities = VolunteerActivity.objects.filter(company=company, date__year=year, status='completed')
    return {
        'year': year, 'company': company.name,
        'total_activities': activities.count(),
        'total_hours': float(activities.aggregate(s=Sum('hours'))['s'] or 0),
        'total_inkind_eur': float(sum(a.inkind_value for a in activities)),
        'unique_volunteers': activities.values('clan').distinct().count(),
        'by_category': list(activities.values('category').annotate(count=Count('id'), hours=Sum('hours')).order_by('-hours')),
    }
