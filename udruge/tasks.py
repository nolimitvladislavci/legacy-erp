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


@shared_task
def check_expiring_documents():
    """
    Dnevna provjera — upozori na dozvole koje ističu u sljedećih 30 dana.
    Ribolovna dozvola, lovačka dozvola, oružni list, zdravstvena.
    """
    from datetime import timedelta
    from django.utils import timezone
    from udruge.models import ClanskiDokument

    today = timezone.now().date()
    threshold = today + timedelta(days=30)

    expiring = ClanskiDokument.objects.filter(
        valid_until__lte=threshold,
        valid_until__gte=today,
        clan__status='aktivan',
    ).select_related('clan')

    expired = ClanskiDokument.objects.filter(
        valid_until__lt=today,
        clan__status='aktivan',
    ).select_related('clan')

    logger.info(
        'Document check: %d expiring in 30 days, %d already expired',
        expiring.count(), expired.count(),
    )

    # TODO: slanje notifikacija (push/email/WhatsApp) članovima
    return {
        'expiring_30d': expiring.count(),
        'expired': expired.count(),
    }


@shared_task
def check_vatrogasna_oprema_atesti():
    """
    Dnevno — upozori na vatrogasnu opremu čiji atesti ističu u sljedećih 30 dana.
    Aparati, cijevi, pumpe — sve s atest_vrijedi_do poljem.
    """
    from datetime import timedelta
    from django.utils import timezone as tz
    from udruge.models import VatrogasnaOprema

    today = tz.now().date()
    threshold = today + timedelta(days=30)

    expiring = VatrogasnaOprema.objects.filter(
        atest_vrijedi_do__lte=threshold,
        atest_vrijedi_do__gte=today,
        status='ispravno',
    ).select_related('company')

    expired = VatrogasnaOprema.objects.filter(
        atest_vrijedi_do__lt=today,
        status='ispravno',
    ).select_related('company')

    # Oznaci istekle
    expired_count = expired.update(status='neispravno')

    logger.info(
        'Vatrogasna oprema atest check: %d expiring in 30 days, %d expired (marked neispravan)',
        expiring.count(), expired_count,
    )

    return {
        'expiring_30d': expiring.count(),
        'expired_marked': expired_count,
    }


@shared_task
def check_ribolovne_dozvole():
    """
    Dnevno — upozori na ribolovne dozvole koje ističu u sljedećih 14 dana.
    Šalje WhatsApp/email podsjetnik članu.
    """
    from datetime import timedelta
    from django.utils import timezone as tz
    from udruge.models import RibolovnaDozvola

    today = tz.now().date()
    threshold = today + timedelta(days=14)

    expiring = RibolovnaDozvola.objects.filter(
        valid_until__lte=threshold,
        valid_until__gte=today,
        placena=True,
    ).select_related('clan', 'clan__company')

    notified = 0
    for dozvola in expiring:
        clan = dozvola.clan
        days_left = (dozvola.valid_until - today).days
        phone = clan.whatsapp_phone or clan.phone

        if phone and clan.whatsapp_opt_in:
            try:
                from core.whatsapp import send_text
                msg = (
                    'Poštovani %s, Vaša ribolovna dozvola (%s) ističe za %d dana (%s). '
                    'Obnovite dozvolu u %s.'
                ) % (
                    clan.first_name, dozvola.get_kategorija_display(),
                    days_left, dozvola.valid_until.strftime('%d.%m.%Y.'),
                    clan.company.name,
                )
                send_text(phone=phone, message=msg, company_id=str(clan.company.pk))
                notified += 1
            except Exception as e:
                logger.warning('Ribolovna dozvola WA %s: %s', clan, e)

    logger.info('Ribolovne dozvole check: %d expiring in 14 days, %d notified', expiring.count(), notified)
    return {
        'expiring_14d': expiring.count(),
        'notified': notified,
    }


@shared_task
def check_tretman_kosnica_reminders():
    """
    Dnevno — provjeri trebaju li košnice tretman (varroa sezone: ožujak, srpanj, studeni).
    Upozori pčelare čije košnice nemaju tretman u zadnjih 90 dana.
    """
    from datetime import timedelta
    from django.utils import timezone as tz
    from django.db.models import Max
    from udruge.models import Kosnica, TretmanKosnice

    today = tz.now().date()
    month = today.month

    # Varroa tretman sezone: 3 (ožujak), 7 (srpanj), 11 (studeni) — +/- 1 mjesec
    varroa_months = [2, 3, 4, 7, 8, 11, 12]
    if month not in varroa_months:
        return {'status': 'not_varroa_season', 'month': month}

    threshold = today - timedelta(days=90)

    # Košnice koje su aktivne i nemaju tretman u zadnjih 90 dana
    kosnice_bez_tretmana = Kosnica.objects.filter(
        status='ispravno',
    ).exclude(
        tretmani__datum__gte=threshold,
    ).select_related('pcelinjak', 'pcelinjak__vlasnik', 'pcelinjak__company')

    alerts = []
    for kosnica in kosnice_bez_tretmana:
        last_tretman = TretmanKosnice.objects.filter(
            kosnica=kosnica
        ).aggregate(last=Max('datum'))['last']

        alerts.append({
            'kosnica': str(kosnica),
            'pcelar': str(kosnica.pcelinjak.vlasnik),
            'last_tretman': str(last_tretman) if last_tretman else 'nikad',
        })

    logger.info('Tretman kosnica check: %d kosnica needs treatment', len(alerts))
    return {
        'needs_treatment': len(alerts),
        'alerts': alerts[:50],  # Limit za output
    }


@shared_task
def generate_trosarina_report(company_id, godina=None):
    """
    Generira godišnji trošarinski obračun iz DestilacijaLog zapisa.
    Računa ukupne litre čistog alkohola i trošarinu za mali/veliki proizvođač.
    """
    from django.utils import timezone as tz
    from django.db.models import Sum, Avg
    from companies.models import Company
    from udruge.models import DestilacijaLog, DestilacijaKotao, TrosarinaPrijava

    if not godina:
        godina = tz.now().year

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}

    # Dohvati sve kotlove firme
    kotao_ids = DestilacijaKotao.objects.filter(company=company).values_list('id', flat=True)

    # Agregiraj destilacije za godinu
    destilacije = DestilacijaLog.objects.filter(
        kotao_id__in=kotao_ids,
        datum__year=godina,
    )

    stats = destilacije.aggregate(
        ukupno_litara=Sum('litara_destilata'),
        ukupno_cistog=Sum('litara_cistog_alkohola'),
        prosjecni_alc=Avg('alkohol_posto'),
    )

    ukupno_litara = stats['ukupno_litara'] or 0
    ukupno_cistog = stats['ukupno_cistog'] or 0
    prosjecni_alc = stats['prosjecni_alc'] or 40

    # Stopa trošarine 2024/2025: 1.047,27 EUR/hL čistog alkohola
    # Mali proizvođač (<=50L č.a.): oslobođen ili snižena stopa
    PUNA_STOPA = 1047.27
    mali = ukupno_cistog <= 50
    stopa = 0 if mali else PUNA_STOPA
    iznos = float(ukupno_cistog) / 100 * stopa

    # Upsert TrosarinaPrijava
    prijava, created = TrosarinaPrijava.objects.update_or_create(
        company=company,
        godina=godina,
        defaults={
            'ukupno_litara_destilata': ukupno_litara,
            'prosjecni_alkohol_posto': prosjecni_alc,
            'ukupno_litara_cistog': ukupno_cistog,
            'stopa_eur_hl': stopa,
        },
    )

    logger.info(
        'Trosarina %s %d: %s L destilata, %s L cistog, mali=%s, trosarina=%s EUR',
        company.name, godina, ukupno_litara, ukupno_cistog, mali, prijava.iznos_trosarine,
    )

    return {
        'company': company.name,
        'godina': godina,
        'ukupno_litara': float(ukupno_litara),
        'ukupno_cistog_alkohola': float(ukupno_cistog),
        'mali_proizvodac': mali,
        'stopa_eur_hl': float(stopa),
        'iznos_trosarine': float(prijava.iznos_trosarine),
        'destilacija_count': destilacije.count(),
        'created': created,
    }


@shared_task(bind=True, soft_time_limit=120)
def generate_azil_monthly_report(self, company_id=None, year=None, month=None):
    """
    1. u mjesecu 06:00 — generira mjesecni izvjestaj azila za JLS.
    Ako company_id=None, generira za sve firme s azil zivotinjama.
    """
    from django.db.models import Sum
    from companies.models import Company
    from .models import Zivotinja, MjesecniIzvjestajAzil, KartonZdravlja

    now = timezone.now()
    if not year:
        prev = now.replace(day=1) - timedelta(days=1)
        year, month = prev.year, prev.month
    if not month:
        month = now.month

    from datetime import date
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        period_end = date(year, month + 1, 1) - timedelta(days=1)

    if company_id:
        companies = Company.objects.filter(pk=company_id)
    else:
        company_ids = Zivotinja.objects.unscoped().values_list(
            'company_id', flat=True).distinct()
        companies = Company.objects.filter(pk__in=company_ids)

    results = []
    for company in companies:
        qs = Zivotinja.objects.unscoped().filter(company=company)

        primljeno = qs.filter(
            datum_ulaska__gte=period_start, datum_ulaska__lte=period_end).count()
        udomljeno = qs.filter(
            status='udomljen',
            updated_at__date__gte=period_start, updated_at__date__lte=period_end).count()
        vraceno = qs.filter(
            status='vrácen',
            updated_at__date__gte=period_start, updated_at__date__lte=period_end).count()
        uginulo = qs.filter(
            status='uginuo',
            updated_at__date__gte=period_start, updated_at__date__lte=period_end).count()
        eutanazirano = qs.filter(
            status='eutanazija',
            updated_at__date__gte=period_start, updated_at__date__lte=period_end).count()
        trenutno = qs.filter(
            status__in=['karantena', 'slobodan', 'rezerviran']).count()

        zdravlje_qs = KartonZdravlja.objects.filter(
            zivotinja__company=company,
            datum__gte=period_start, datum__lte=period_end)
        trosak_vet = zdravlje_qs.aggregate(s=Sum('trosak_eur'))['s'] or 0

        report, created = MjesecniIzvjestajAzil.objects.update_or_create(
            company=company, godina=year, mjesec=month,
            defaults={
                'primljeno': primljeno,
                'udomljeno': udomljeno,
                'vráceno_vlasniku': vraceno,
                'uginulo': uginulo,
                'eutanazirano': eutanazirano,
                'trenutno_stanje': trenutno,
                'trosak_vet_eur': trosak_vet,
            })

        try:
            pdf_bytes = _generate_azil_pdf(report, company, period_start, period_end)
            from django.core.files.base import ContentFile
            filename = 'azil_{}_{:d}_{:02d}.pdf'.format(
                getattr(company, 'slug', company.pk), year, month)
            report.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
            report.pdf_generiran = True
            report.save()
            logger.info('Azil report %s %d/%02d: PDF generated', company.name, year, month)
        except Exception as e:
            logger.error('Azil PDF %s: %s', company.name, e)
            report.save()

        results.append({
            'company': company.name,
            'period': '{:d}/{:02d}'.format(year, month),
            'primljeno': primljeno, 'udomljeno': udomljeno,
            'trenutno': trenutno, 'pdf': report.pdf_generiran,
            'created': created,
        })

    return {'reports': results, 'count': len(results)}


def _generate_azil_pdf(report, company, period_start, period_end):
    """WeasyPrint PDF za mjesecni azil izvjestaj."""
    from weasyprint import HTML

    ukupno_trosak = float(
        report.trosak_hrana_eur + report.trosak_vet_eur + report.trosak_ostalo_eur)

    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body{{font-family:Arial,sans-serif;font-size:11pt;color:#222;margin:2cm}}
  h1{{font-size:16pt;color:#1a1a1a;border-bottom:2px solid #c9a84c;padding-bottom:8px}}
  h2{{font-size:13pt;color:#333;margin-top:1.5em}}
  table{{width:100%;border-collapse:collapse;margin:1em 0}}
  th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left}}
  th{{background:#f5f0e0;font-weight:600}}
  .num{{text-align:right;font-family:monospace}}
  .footer{{margin-top:3em;font-size:9pt;color:#888;border-top:1px solid #ddd;padding-top:8px}}
  .highlight{{background:#fff8e1}}
</style>
</head><body>
  <h1>Mjesecni izvjestaj sklonista za zivotinje</h1>
  <table>
    <tr><th>Ustanova</th><td>{company_name}</td></tr>
    <tr><th>OIB</th><td>{oib}</td></tr>
    <tr><th>Razdoblje</th><td>{ps} &mdash; {pe}</td></tr>
  </table>

  <h2>Stanje zivotinja</h2>
  <table>
    <tr><th>Kategorija</th><th class="num">Broj</th></tr>
    <tr><td>Primljeno u razdoblju</td><td class="num">{primljeno}</td></tr>
    <tr><td>Udomljeno</td><td class="num">{udomljeno}</td></tr>
    <tr><td>Vraceno vlasniku</td><td class="num">{vraceno}</td></tr>
    <tr><td>Uginulo (prirodno)</td><td class="num">{uginulo}</td></tr>
    <tr><td>Eutanazirano (vet. odluka)</td><td class="num">{eutanazirano}</td></tr>
    <tr class="highlight"><td><strong>Trenutno stanje</strong></td><td class="num"><strong>{trenutno}</strong></td></tr>
  </table>

  <h2>Troskovi</h2>
  <table>
    <tr><th>Kategorija</th><th class="num">EUR</th></tr>
    <tr><td>Hrana i oprema</td><td class="num">{hrana:.2f}</td></tr>
    <tr><td>Veterinarski troskovi</td><td class="num">{vet:.2f}</td></tr>
    <tr><td>Ostalo</td><td class="num">{ostalo:.2f}</td></tr>
    <tr class="highlight"><td><strong>Ukupno</strong></td><td class="num"><strong>{ukupno:.2f}</strong></td></tr>
  </table>

  <div class="footer">
    Generirano: {generated} | LIMIT Connect &mdash; limit-connect.com<br>
    Izvjestaj u skladu sa Zakonom o zastiti zivotinja (NN 102/17, cl. 62)
  </div>
</body></html>""".format(
        company_name=company.name,
        oib=getattr(company, 'oib', '-'),
        ps=period_start.strftime('%d.%m.%Y.'),
        pe=period_end.strftime('%d.%m.%Y.'),
        primljeno=report.primljeno,
        udomljeno=report.udomljeno,
        vraceno=report.vráceno_vlasniku,
        uginulo=report.uginulo,
        eutanazirano=report.eutanazirano,
        trenutno=report.trenutno_stanje,
        hrana=float(report.trosak_hrana_eur),
        vet=float(report.trosak_vet_eur),
        ostalo=float(report.trosak_ostalo_eur),
        ukupno=ukupno_trosak,
        generated=timezone.now().strftime('%d.%m.%Y. %H:%M'),
    )

    return HTML(string=html).write_pdf()
