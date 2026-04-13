"""
Account Deactivation — "Zapečaćena Arhiva" (Data Vaulting) paradigma.

Pravna osnova: GDPR čl. 17(3)(b) + Zakon o računovodstvu (ZOR) + Opći porezni zakon (OPZ).
Poslovni podaci u POS-u (artikli, cijene, OIB, računi) su poslovne knjige.
Ne brišu se, ne anonimiziraju se — zapečate se (vault).

Workflow:
1. Korisnik stisne "Deaktiviraj i Zapečati Arhivu"
2. Potvrdi pravni checkbox (čl.17(3) GDPR + ZOR 11 godina)
3. Data export (GDPR čl.20) — preuzme ZIP/JSON
4. 30 dana grace period (read-only, može poništiti)
5. Nakon 30 dana: is_active=False, is_vaulted=True — login disabled, baza netaknuta
6. Reaktivacija moguća jednim klikom (upsell)
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.utils import timezone as tz
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

logger = logging.getLogger('accounts')

GRACE_PERIOD_DAYS = 30


# ── Views ────────────────────────────────────────────────────────────────────


@login_required
@require_POST
def request_deactivation(request):
    """
    Korisnik zahtijeva deaktivaciju — pokreće Vaulting workflow.
    Stavlja firmu u grace period (30 dana read-only).
    """
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Nije moguće odrediti tvrtku.'))
        return redirect('/')

    if getattr(company, 'is_vaulted', False):
        messages.error(request, _('Račun je već zapečaćen u arhivu.'))
        return redirect('/')

    if company.deactivation_requested_at:
        messages.warning(request, _('Deaktivacija je već zatražena.'))
        return redirect('accounts:deactivation_status')

    # Postavi deactivation pending
    reason = request.POST.get('reason', '').strip()[:500]
    company.deactivation_requested_at = tz.now()
    company.deactivation_reason = reason
    company.save(update_fields=['deactivation_requested_at', 'deactivation_reason'])

    # Audit trail
    try:
        from worktime.tracker import track
        expiry = (tz.now() + timedelta(days=GRACE_PERIOD_DAYS)).strftime('%d.%m.%Y')
        track(
            request.user, 'ACCOUNTS', 'VAULT_REQUESTED',
            ref=str(company.pk),
            detail='Deaktivacija zatražena. Razlog: %s. Grace period do: %s' % (
                reason or '(bez razloga)', expiry),
            company=company,
        )
    except ImportError:
        logger.exception('Audit trail failed for vault request')

    # Confirmation email
    try:
        expiry_date = (tz.now() + timedelta(days=GRACE_PERIOD_DAYS)).strftime('%d.%m.%Y')
        send_mail(
            subject='LIMIT Connect — Zahtjev za deaktivaciju (%s)' % company.name,
            message=(
                'Poštovani,\n\n'
                'Primili smo Vaš zahtjev za deaktivaciju računa tvrtke %s.\n\n'
                'Vaš račun bit će u read-only načinu sljedećih %d dana.\n'
                'Datum zapečaćenja arhive: %s\n\n'
                'Tijekom grace perioda možete:\n'
                '- Preuzeti sve podatke (GDPR čl. 20)\n'
                '- Poništiti zahtjev za deaktivacijom\n\n'
                'VAŽNO: Sukladno čl. 17. st. 3. GDPR-a, Zakonu o računovodstvu\n'
                'i Općem poreznom zakonu, Vaši poslovni podaci čuvaju se kao\n'
                'nepromjenjiva arhiva u trajanju od 11 godina.\n\n'
                'S poštovanjem,\nLIMIT Connect tim'
            ) % (company.name, GRACE_PERIOD_DAYS, expiry_date),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@limit-connect.com'),
            recipient_list=[request.user.email] if request.user.email else [],
            fail_silently=True,
        )
    except (ValueError, TypeError):
        logger.exception('Failed to send deactivation email')

    messages.success(
        request,
        'Zahtjev primljen. Imate %d dana za preuzimanje podataka ili poništenje.' % GRACE_PERIOD_DAYS
    )
    return redirect('accounts:deactivation_status')


@login_required
def deactivation_status(request):
    """Prikaži status deaktivacije — countdown, mogućnost poništenja."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    is_vaulted = getattr(company, 'is_vaulted', False)
    if not company.deactivation_requested_at and not is_vaulted:
        return redirect('/')

    days_remaining = 0
    expiry_date = None
    if company.deactivation_requested_at and not is_vaulted:
        expiry_dt = company.deactivation_requested_at + timedelta(days=GRACE_PERIOD_DAYS)
        expiry_date = expiry_dt
        days_remaining = max(0, (expiry_dt - tz.now()).days)

    return render(request, 'accounts/deactivation.html', {
        'company': company,
        'days_remaining': days_remaining,
        'expiry_date': expiry_date,
        'is_pending': bool(company.deactivation_requested_at and not is_vaulted),
        'is_vaulted': is_vaulted,
        'grace_period_days': GRACE_PERIOD_DAYS,
    })


@login_required
@require_POST
def cancel_deactivation(request):
    """Poništi zahtjev za deaktivacijom unutar grace perioda."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    is_vaulted = getattr(company, 'is_vaulted', False)
    if not company.deactivation_requested_at or is_vaulted:
        messages.error(request, _('Nema aktivnog zahtjeva za deaktivaciju.'))
        return redirect('/')

    expiry_dt = company.deactivation_requested_at + timedelta(days=GRACE_PERIOD_DAYS)
    if tz.now() > expiry_dt:
        messages.error(request, _('Grace period je istekao.'))
        return redirect('accounts:deactivation_status')

    old_dt = company.deactivation_requested_at
    company.deactivation_requested_at = None
    company.deactivation_reason = ''
    company.save(update_fields=['deactivation_requested_at', 'deactivation_reason'])

    try:
        from worktime.tracker import track
        track(
            request.user, 'ACCOUNTS', 'VAULT_CANCELLED',
            ref=str(company.pk),
            detail='Deaktivacija poništena. Originalni zahtjev: %s' % old_dt.strftime('%d.%m.%Y %H:%M'),
            company=company,
        )
    except ImportError:
        pass

    messages.success(request, _('Zahtjev poništen. Račun je ponovo potpuno aktivan.'))
    return redirect('/')


# ── Reaktivacija (superadmin) ────────────────────────────────────────────────


@login_required
@require_POST
def reactivate_company(request, company_id):
    """
    Superadmin reaktivira zapečaćenu firmu — jedan klik, sve se vraća.
    Upsell: korisnik se vratio jer mu je novi program smeće.
    """
    if not request.user.is_superuser:
        messages.error(request, _('Samo superadmin može reaktivirati.'))
        return redirect('/')

    from companies.models import Company
    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        messages.error(request, _('Tvrtka nije pronađena.'))
        return redirect('/')

    company.is_vaulted = False
    company.is_deactivated = False
    company.deactivation_requested_at = None
    company.deactivation_reason = ''
    company.save(update_fields=[
        'is_vaulted', 'is_deactivated',
        'deactivation_requested_at', 'deactivation_reason',
    ])

    # Reactivate all users
    from accounts.models import CompanyMembership
    user_ids = CompanyMembership.objects.filter(
        company=company
    ).values_list('user_id', flat=True)
    from django.contrib.auth.models import User
    User.objects.filter(pk__in=user_ids).update(is_active=True)

    try:
        from worktime.tracker import track
        track(
            request.user, 'ACCOUNTS', 'VAULT_REACTIVATED',
            ref=str(company.pk),
            detail='Firma reaktivirana: %s. Svi korisnici ponovo aktivni.' % company.name,
            company=company,
        )
    except ImportError:
        pass

    messages.success(request, _('Firma %s reaktivirana! Svi podaci netaknuti.') % company.name)
    return redirect('/')


# ── Celery Task: Vaulting ────────────────────────────────────────────────────


@shared_task(name='accounts.process_vaulting')
def process_vaulting():
    """
    Dnevni task: zapečati firme kojima je istekao grace period.

    NE BRIŠE NIŠTA. NE ANONIMIZIRA NIŠTA.
    Samo: is_vaulted=True, is_active=False na userima, login disabled.
    Baza ostaje netaknuta — čista za Poreznu i za reaktivaciju.

    Pravna osnova:
    - GDPR čl. 17(3)(b): pravna obveza čuvanja
    - Zakon o računovodstvu (ZOR): poslovne knjige 11 godina
    - Opći porezni zakon (OPZ): porezna dokumentacija 11 godina
    - Zakon o fiskalizaciji (NN 133/12): fiskalni zapisi
    """
    from django.contrib.auth.models import User

    from accounts.models import CompanyMembership
    from companies.models import Company

    cutoff = tz.now() - timedelta(days=GRACE_PERIOD_DAYS)
    pending = Company.objects.filter(
        deactivation_requested_at__isnull=False,
        deactivation_requested_at__lte=cutoff,
        is_vaulted=False,
    )

    results = {'vaulted': 0, 'errors': 0}

    for company in pending:
        try:
            logger.info('[VAULT] Sealing company: %s (pk=%s)', company.name, company.pk)

            # 1. Disable all user logins
            user_ids = CompanyMembership.objects.filter(
                company=company
            ).values_list('user_id', flat=True)
            users_disabled = User.objects.filter(pk__in=user_ids).update(is_active=False)

            # 2. Seal the company — NE BRIŠI NIŠTA
            company.is_vaulted = True
            company.is_deactivated = True
            company.save(update_fields=['is_vaulted', 'is_deactivated'])

            # 3. Audit trail
            try:
                from worktime.tracker import track
                admin = User.objects.filter(is_superuser=True, is_active=True).first()
                if admin:
                    track(
                        admin, 'ACCOUNTS', 'VAULT_SEALED',
                        ref=str(company.pk),
                        detail=(
                            'Arhiva zapečaćena: %s. '
                            'Korisnika deaktivirano: %d. '
                            'Baza NETAKNUTA — čl.17(3) GDPR + ZOR + OPZ. '
                            'Reaktivacija moguća.'
                        ) % (company.name, users_disabled),
                        company=company,
                    )
            except DatabaseError:
                pass

            # 4. Notifikacija superadminu
            try:
                from superadmin_ai.tasks import _notify_superadmins
                _notify_superadmins(
                    title='Arhiva zapečaćena: %s' % company.name,
                    message=(
                        'Firma %s je zapečaćena u arhivu.\n'
                        'Korisnika deaktivirano: %d\n'
                        'Podaci ostaju netaknuti 11 godina.\n'
                        'Reaktivacija: /superadmin/ → Reactivate'
                    ) % (company.name, users_disabled),
                    notification_type='system',
                )
            except ImportError:
                pass

            logger.info('[VAULT] Sealed: %s — %d users disabled, 0 data modified',
                        company.name, users_disabled)
            results['vaulted'] += 1

        except DatabaseError:
            logger.exception('[VAULT] Error sealing company pk=%s', company.pk)
            results['errors'] += 1

    return results
