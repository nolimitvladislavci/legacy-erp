import json
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.company_utils import get_user_company

logger = logging.getLogger('udruge')


@login_required
def clan_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne udruge.')
        return redirect('dashboard')

    from .models import Clan
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    qs = Clan.objects.filter(company=company)
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                       Q(oib__icontains=q) | Q(phone__icontains=q))
    if status:
        qs = qs.filter(status=status)

    today = timezone.now().date()
    from datetime import timedelta
    stats = {
        'ukupno': Clan.objects.filter(company=company).count(),
        'aktivni': Clan.objects.filter(company=company, status='aktivan').count(),
        'istice_7': Clan.objects.filter(
            company=company, status='aktivan',
            membership_expires__gte=today,
            membership_expires__lte=today + timedelta(days=7)
        ).count(),
        'ima_opg': Clan.objects.filter(company=company, has_opg=True).count(),
        'wa_optin': Clan.objects.filter(company=company, whatsapp_opt_in=True).count(),
    }

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'udruge/clan_list.html', {
        'page_obj': page, 'stats': stats, 'q': q, 'status_f': status,
        'membership_choices': Clan.MEMBERSHIP_CHOICES,
        'status_choices': Clan.STATUS_CHOICES,
    })


@login_required
def clan_detail(request, pk):
    company = get_user_company(request)
    from .models import Clan
    clan = get_object_or_404(Clan, pk=pk, company=company)
    return render(request, 'udruge/clan_detail.html', {
        'clan': clan, 'biljeske': clan.biljeske.all()[:20],
    })


@login_required
def clan_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne udruge.')
        return redirect('udruge:clan_list')

    from .models import Clan
    if request.method == 'POST':
        clan = Clan(
            company=company,
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            oib=request.POST.get('oib', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            city=request.POST.get('city', ''),
            membership_type=request.POST.get('membership_type', 'redovni'),
            date_joined=request.POST.get('date_joined') or timezone.now().date(),
            membership_number=request.POST.get('membership_number', ''),
            membership_expires=request.POST.get('membership_expires') or None,
            business_interest=request.POST.get('business_interest', ''),
            has_opg='has_opg' in request.POST,
            whatsapp_phone=request.POST.get('whatsapp_phone', ''),
            whatsapp_opt_in='whatsapp_opt_in' in request.POST,
            notes=request.POST.get('notes', ''),
        )
        clan.save()
        messages.success(request, 'Clan %s %s dodan.' % (clan.first_name, clan.last_name))
        return redirect('udruge:clan_detail', pk=clan.pk)

    return render(request, 'udruge/clan_form.html', {
        'membership_choices': Clan.MEMBERSHIP_CHOICES,
        'interest_choices': Clan.INTEREST_CHOICES,
    })


@login_required
@require_POST
def oib_lookup(request, pk):
    company = get_user_company(request)
    from .models import Clan
    clan = get_object_or_404(Clan, pk=pk, company=company)

    if not clan.oib:
        return JsonResponse({'error': 'Nema OIB-a'}, status=400)

    from .oib_service import lookup_oib
    result = lookup_oib(clan.oib)

    clan.oib_lookup_result = result
    clan.oib_last_checked = timezone.now()
    clan.save(update_fields=['oib_lookup_result', 'oib_last_checked'])

    return JsonResponse({'ok': True, 'result': result})


@login_required
@require_POST
def ai_analyze(request, pk):
    company = get_user_company(request)
    from .models import Clan, ClanBiljeska
    clan = get_object_or_404(Clan, pk=pk, company=company)

    try:
        import os, anthropic
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

        context = json.dumps({
            'ime': clan.full_name,
            'tip': clan.membership_type,
            'interes': clan.business_interest,
            'opg': clan.has_opg,
            'obrt': clan.has_obrt,
            'oib_info': clan.oib_lookup_result.get('name', ''),
        }, ensure_ascii=False)

        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{
                'role': 'user',
                'content': 'Analiziraj clana udruge i predlozi kako mu pomoci s poslovanjem. '
                           'Odgovori HR JSON: {"profil":"...", "preporuka":"...", "modul":"...", "prioritet":"visoki/srednji/niski"}\n\n' + context,
            }]
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0]
        ai_data = json.loads(text)

        clan.ai_profile = ai_data
        clan.ai_last_analyzed = timezone.now()
        clan.save(update_fields=['ai_profile', 'ai_last_analyzed'])

        ClanBiljeska.objects.create(
            clan=clan, text='AI: %s' % ai_data.get('preporuka', ''),
            tip='ai', created_by=request.user,
        )
        return JsonResponse({'ok': True, 'ai_profile': ai_data})
    except Exception as e:
        logger.error('AI analyze clan %s: %s', pk, e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def send_whatsapp(request, pk):
    company = get_user_company(request)
    from .models import Clan
    clan = get_object_or_404(Clan, pk=pk, company=company)

    phone = clan.whatsapp_phone or clan.phone
    if not phone:
        return JsonResponse({'error': 'Nema telefona'}, status=400)
    if not clan.whatsapp_opt_in:
        return JsonResponse({'error': 'Nema pristanka za WhatsApp'}, status=400)

    msg_type = request.POST.get('type', 'custom')
    if msg_type == 'expiry':
        days = clan.days_until_expiry
        msg = 'Postovani %s, clanstvo u %s istice za %s dan(a). Kontaktirajte nas za obnovu.' % (clan.first_name, company.name, days)
    elif msg_type == 'welcome':
        msg = 'Dobrodosli u %s, %s! Clanski broj: %s' % (company.name, clan.first_name, clan.membership_number or clan.pk)
    else:
        msg = request.POST.get('message', '')

    if not msg:
        return JsonResponse({'error': 'Nema poruke'}, status=400)

    try:
        from core.whatsapp import send_text
        result = send_text(phone=phone, message=msg, company_id=str(company.pk))
        from .models import ClanBiljeska
        ClanBiljeska.objects.create(clan=clan, text='WhatsApp (%s): %s' % (msg_type, msg[:100]), tip='sistem', created_by=request.user)
        return JsonResponse({'ok': True, 'sent_to': phone})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# ── CLANARINE ─────────────────────────────────────────────────────────────────

@login_required
def clanarina_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from .models import Clanarina
    status_f = request.GET.get('status', '')
    qs = Clanarina.objects.filter(company=company).select_related('clan')
    if status_f:
        qs = qs.filter(status=status_f)

    from django.db.models import Sum
    stats = {
        'ukupno': qs.count(),
        'placene': qs.filter(status='placena').aggregate(s=Sum('amount'))['s'] or 0,
        'ceka': qs.filter(status='ceka').count(),
        'kasni': qs.filter(status='kasni').count(),
    }

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/clanarina_list.html', {
        'page_obj': page, 'stats': stats, 'status_f': status_f,
    })


@login_required
@require_POST
def clanarina_pay(request, pk):
    company = get_user_company(request)
    from .models import Clanarina
    clanarina = get_object_or_404(Clanarina, pk=pk, company=company)

    method = request.POST.get('method', 'gotovina')
    clanarina.mark_paid(method=method)

    # Auto-zapis u Knjigu primitaka
    from .models import KnjigaPrimitaka
    last = KnjigaPrimitaka.objects.filter(company=company).order_by('-redni_broj').first()
    rb = (last.redni_broj + 1) if last else 1
    KnjigaPrimitaka.objects.create(
        company=company,
        redni_broj=rb,
        datum=timezone.now().date(),
        opis="Clanarina: %s (%s - %s)" % (clanarina.clan, clanarina.period_start, clanarina.period_end),
        vrsta='primitak',
        izvor='clanarina',
        iznos=clanarina.amount,
        clanarina=clanarina,
    )

    messages.success(request, "Clanarina placena: %s EUR" % clanarina.amount)
    return redirect('udruge:clanarina_list')


@login_required
@require_POST
def clanarina_bulk_create(request):
    """Generira clanarine za sve aktivne clanove za zadani period."""
    company = get_user_company(request)
    from .models import Clan, Clanarina

    amount = request.POST.get('amount', '0')
    period_start = request.POST.get('period_start')
    period_end = request.POST.get('period_end')

    if not all([amount, period_start, period_end]):
        messages.error(request, 'Sva polja su obavezna.')
        return redirect('udruge:clanarina_list')

    from decimal import Decimal
    amount = Decimal(amount)
    aktivni = Clan.objects.filter(company=company, status='aktivan')
    created = 0
    for clan in aktivni:
        if not Clanarina.objects.filter(
            company=company, clan=clan,
            period_start=period_start, period_end=period_end,
        ).exists():
            Clanarina.objects.create(
                company=company, clan=clan,
                period_start=period_start, period_end=period_end,
                amount=amount,
            )
            created += 1

    messages.success(request, "Kreirano %d clanarina po %s EUR." % (created, amount))
    return redirect('udruge:clanarina_list')


# ── DONACIJE ──────────────────────────────────────────────────────────────────

@login_required
def donacija_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from .models import Donacija
    from django.db.models import Sum
    qs = Donacija.objects.filter(company=company)

    year = request.GET.get('year', str(timezone.now().year))
    qs = qs.filter(date__year=year)

    stats = {
        'ukupno_donacija': qs.aggregate(s=Sum('amount'))['s'] or 0,
        'broj_donatora': qs.values('donor_oib').distinct().count(),
        'bez_potvrde': qs.filter(potvrda_issued=False).count(),
    }

    return render(request, 'udruge/donacija_list.html', {
        'donacije': qs, 'stats': stats, 'year': year,
    })


@login_required
def donacija_create(request):
    company = get_user_company(request)
    from .models import Donacija, KnjigaPrimitaka

    if request.method == 'POST':
        from decimal import Decimal
        donacija = Donacija.objects.create(
            company=company,
            donor_name=request.POST.get('donor_name', ''),
            donor_oib=request.POST.get('donor_oib', ''),
            donor_type=request.POST.get('donor_type', 'fizicka'),
            donor_address=request.POST.get('donor_address', ''),
            amount=Decimal(request.POST.get('amount', '0')),
            purpose=request.POST.get('purpose', ''),
            date=request.POST.get('date') or timezone.now().date(),
            note=request.POST.get('note', ''),
        )

        # Auto-zapis u Knjigu primitaka
        last = KnjigaPrimitaka.objects.filter(company=company).order_by('-redni_broj').first()
        rb = (last.redni_broj + 1) if last else 1
        KnjigaPrimitaka.objects.create(
            company=company,
            redni_broj=rb,
            datum=donacija.date,
            opis="Donacija: %s — %s" % (donacija.donor_name, donacija.purpose or "opca"),
            vrsta='primitak',
            izvor='donacija',
            iznos=donacija.amount,
            donacija=donacija,
        )

        # AML Guard provjera
        try:
            from udruge.aml_guard import AMLGuard
            aml_status, aml_msg = AMLGuard.check_donation(donacija)
            donacija.save(update_fields=['aml_status', 'aml_flag_reason', 'aml_flagged_at'])
            if aml_status == 'kyc_pending':
                messages.warning(request, 'AML UPOZORENJE: %s — Potrebna dubinska analiza (KYC)!' % aml_msg)
            elif aml_status == 'review':
                messages.warning(request, 'AML: Donacija oznacena za pregled — %s' % aml_msg)
            else:
                messages.success(request, "Donacija %s EUR od %s evidentirana." % (donacija.amount, donacija.donor_name))
        except Exception:
            messages.success(request, "Donacija %s EUR od %s evidentirana." % (donacija.amount, donacija.donor_name))
        return redirect('udruge:donacija_list')

    return render(request, 'udruge/donacija_form.html', {
        'donor_types': Donacija.DONOR_TYPE_CHOICES,
    })


# ── KNJIGA PRIMITAKA I IZDATAKA ──────────────────────────────────────────────

@login_required
def knjiga_primitaka(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from .models import KnjigaPrimitaka
    from django.db.models import Sum

    year = request.GET.get('year', str(timezone.now().year))
    qs = KnjigaPrimitaka.objects.filter(company=company, datum__year=year)

    primici = qs.filter(vrsta='primitak').aggregate(s=Sum('iznos'))['s'] or 0
    izdaci = qs.filter(vrsta='izdatak').aggregate(s=Sum('iznos'))['s'] or 0

    stats = {
        'primici': primici,
        'izdaci': izdaci,
        'saldo': primici - izdaci,
        'unosa': qs.count(),
    }

    return render(request, 'udruge/knjiga_primitaka.html', {
        'stavke': qs, 'stats': stats, 'year': year,
    })


@login_required
def knjiga_primitaka_create(request):
    company = get_user_company(request)
    from .models import KnjigaPrimitaka

    if request.method == 'POST':
        from decimal import Decimal
        last = KnjigaPrimitaka.objects.filter(company=company).order_by('-redni_broj').first()
        rb = (last.redni_broj + 1) if last else 1

        KnjigaPrimitaka.objects.create(
            company=company,
            redni_broj=rb,
            datum=request.POST.get('datum') or timezone.now().date(),
            opis=request.POST.get('opis', ''),
            vrsta=request.POST.get('vrsta', 'primitak'),
            izvor=request.POST.get('izvor', 'ostalo'),
            iznos=Decimal(request.POST.get('iznos', '0')),
            dokument=request.POST.get('dokument', ''),
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Stavka dodana u Knjigu primitaka i izdataka.')
        return redirect('udruge:knjiga_primitaka')

    return render(request, 'udruge/knjiga_primitaka_form.html', {
        'vrsta_choices': KnjigaPrimitaka.VRSTA_CHOICES,
        'izvor_choices': KnjigaPrimitaka.IZVOR_CHOICES,
    })



# ── FINA IZVJESTAJI ──────────────────────────────────────────────────────────

@login_required
def fina_reports(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    current_year = timezone.now().year
    years = list(range(current_year, current_year - 5, -1))
    return render(request, 'udruge/fina_reports.html', {
        'years': years, 'current_year': current_year,
        'is_simplified': company.requires_simplified_accounting,
    })


@login_required
def download_prras_npf(request):
    from django.http import HttpResponse
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    year = int(request.GET.get('year', timezone.now().year))
    period = request.GET.get('period', 'yearly')

    from .fina_reports import generate_prras_npf
    xlsx_bytes = generate_prras_npf(company, year=year, period=period)

    filename = 'PR-RAS-NPF_%s_%d.xlsx' % (company.oib, year)
    response = HttpResponse(
        xlsx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@login_required
def download_gpriznpf(request):
    from django.http import HttpResponse
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    year = int(request.GET.get('year', timezone.now().year))

    from .fina_reports import generate_gpriznpf
    xlsx_bytes = generate_gpriznpf(company, year=year)

    filename = 'G-PR-IZ-NPF_%s_%d.xlsx' % (company.oib, year)
    response = HttpResponse(
        xlsx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@login_required
def download_donatorska_potvrda(request, pk):
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    company = get_user_company(request)

    from .models import Donacija
    donacija = get_object_or_404(Donacija, pk=pk, company=company)

    # Mark as issued
    if not donacija.potvrda_issued:
        from .models import Donacija as D
        last = D.objects.filter(company=company, potvrda_issued=True).count()
        donacija.potvrda_number = 'POT-%d/%d' % (last + 1, donacija.date.year)
        donacija.potvrda_issued = True
        donacija.potvrda_issued_at = timezone.now()
        donacija.save(update_fields=['potvrda_number', 'potvrda_issued', 'potvrda_issued_at'])

    # Generate simple HTML -> PDF-ready response
    html = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Potvrda o donaciji</title>
<style>
body { font-family: Arial, sans-serif; margin: 40px; }
h1 { text-align: center; font-size: 18px; }
.info { margin: 20px 0; }
.info td { padding: 5px 15px; }
.footer { margin-top: 60px; }
.signature { border-top: 1px solid #000; width: 200px; text-align: center; padding-top: 5px; }
</style></head><body>
<h1>POTVRDA O PRIMITKU DONACIJE</h1>
<p style="text-align:center">Broj: %s</p>
<div class="info">
<p><strong>%s</strong> (OIB: %s)</p>
<p>%s, %s %s</p>
<p>potvrdjuje primitak donacije:</p>
<table>
<tr><td>Donator:</td><td><strong>%s</strong></td></tr>
<tr><td>OIB donatora:</td><td>%s</td></tr>
<tr><td>Iznos:</td><td><strong>%s EUR</strong></td></tr>
<tr><td>Datum:</td><td>%s</td></tr>
<tr><td>Namjena:</td><td>%s</td></tr>
</table>
</div>
<p>Ova potvrda izdaje se u svrhu ostvarivanja porezne olaksice sukladno clanku 36. Zakona o porezu na dohodak.</p>
<div class="footer">
<p>U %s, %s</p>
<br><br>
<table><tr>
<td class="signature">Ovlastena osoba</td>
<td style="width:100px"></td>
<td class="signature">Pecat</td>
</tr></table>
</div>
</body></html>''' % (
        donacija.potvrda_number,
        company.name, company.oib,
        company.address, company.zip_code, company.city,
        donacija.donor_name, donacija.donor_oib or '-',
        donacija.amount, donacija.date.strftime('%d.%m.%Y.'),
        donacija.purpose or 'Opca namjena',
        company.city, timezone.now().strftime('%d.%m.%Y.'),
    )

    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="potvrda_%s.html"' % donacija.potvrda_number
    return response



@login_required
def download_bil_npf(request):
    from django.http import HttpResponse
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')
    year = int(request.GET.get('year', timezone.now().year))
    from .fina_reports import generate_bil_npf
    xlsx_bytes = generate_bil_npf(company, year=year)
    filename = 'BIL-NPF_%s_%d.xlsx' % (company.oib, year)
    response = HttpResponse(xlsx_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response



# ── EU FONDOVI / VOLONTERSKI IZVJESTAJI ──────────────────────────────────────

@login_required
def eu_reports(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    from worktime.models import EmployeeProfile
    volunteers = EmployeeProfile.objects.filter(company=company, is_volunteer=True)
    current_year = timezone.now().year

    return render(request, 'udruge/eu_reports.html', {
        'volunteers': volunteers,
        'years': list(range(current_year, current_year - 3, -1)),
        'current_year': current_year,
    })


@login_required
def download_volunteer_timesheet(request):
    from django.http import HttpResponse
    from django.contrib.auth.models import User
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    user_id = request.GET.get('user_id')
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    project = request.GET.get('project', '')

    user = get_object_or_404(User, pk=user_id)

    from worktime.services.eu_reports import generate_volunteer_timesheet
    xlsx = generate_volunteer_timesheet(company, user, month, year, project)

    filename = 'Timesheet_%s_%02d_%d.xlsx' % (user.get_full_name().replace(' ', '_'), month, year)
    response = HttpResponse(xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@login_required
def download_inkind_report(request):
    from django.http import HttpResponse
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    year = int(request.GET.get('year', timezone.now().year))
    quarter = request.GET.get('quarter')
    quarter = int(quarter) if quarter else None

    from worktime.services.eu_reports import generate_inkind_report
    xlsx = generate_inkind_report(company, year, quarter)

    q_label = 'Q%d' % quarter if quarter else 'Full'
    filename = 'InKind_Report_%s_%s_%d.xlsx' % (company.oib, q_label, year)
    response = HttpResponse(xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@login_required
def download_annual_volunteer_report(request):
    from django.http import HttpResponse
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    year = int(request.GET.get('year', timezone.now().year))

    from worktime.services.eu_reports import generate_annual_volunteer_report
    xlsx = generate_annual_volunteer_report(company, year)

    filename = 'Godisnje_volontiranje_%s_%d.xlsx' % (company.oib, year)
    response = HttpResponse(xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response
