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
            has_obrt='has_obrt' in request.POST,
            opg_oib=request.POST.get('opg_oib', ''),
            date_of_birth=request.POST.get('date_of_birth') or None,
            access_card_uid=request.POST.get('access_card_uid', ''),
            whatsapp_phone=request.POST.get('whatsapp_phone', ''),
            whatsapp_opt_in='whatsapp_opt_in' in request.POST,
            notes=request.POST.get('notes', ''),
        )
        sponsor_id = request.POST.get('paying_sponsor')
        if sponsor_id:
            clan.paying_sponsor_id = int(sponsor_id)
        clan.save()
        messages.success(request, 'Clan %s %s dodan.' % (clan.first_name, clan.last_name))
        return redirect('udruge:clan_detail', pk=clan.pk)

    from partners.models import Partner
    sponsors = Partner.objects.filter(company=company)[:50] if company else []
    return render(request, 'udruge/clan_form.html', {
        'membership_choices': Clan.MEMBERSHIP_CHOICES,
        'status_choices': Clan.STATUS_CHOICES,
        'interest_choices': Clan.INTEREST_CHOICES,
        'sponsors': sponsors,
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
            is_material='is_material' in request.POST,
            material_description=request.POST.get('material_description', ''),
            material_fair_value=request.POST.get('material_fair_value') or None,
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
        'aml_statuses': Donacija.AML_STATUS_CHOICES,
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

    # Generate QR code and viral code
    from .qr_utils import generate_donation_qr, generate_viral_code
    qr_base64 = generate_donation_qr(donacija)
    viral_code = generate_viral_code(company.pk, donacija.pk)

    # Generate HTML with QR and viral code -> PDF-ready response
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

    # Inject QR + viral code before </body>
    qr_html = ''
    if qr_base64:
        qr_html += '<div style="margin-top:30px;text-align:center;border-top:1px solid #ccc;padding-top:15px;">'
        qr_html += '<img src="data:image/png;base64,%s" width="120" height="120" />' % qr_base64
        qr_html += '<p style="font-size:11px;color:#666;">Referral: <strong>%s</strong></p>' % viral_code
        qr_html += '<p style="font-size:10px;color:#999;">Skenirajte QR kod za verifikaciju potvrde</p></div>'
    html = html.replace('</body>', qr_html + '</body>')

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



# ══════════════════════════════════════════════════════════════════════════════
# DOGADJAJI (Events)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def dogadjaj_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, "Nema aktivne udruge.")
        return redirect("dashboard")

    from .models import Dogadjaj
    status_f = request.GET.get("status", "")
    type_f = request.GET.get("event_type", "")

    qs = Dogadjaj.objects.filter(company=company)
    if status_f:
        qs = qs.filter(status=status_f)
    if type_f:
        qs = qs.filter(event_type=type_f)

    today = timezone.now()
    stats = {
        "ukupno": Dogadjaj.objects.filter(company=company).count(),
        "predstojeci": Dogadjaj.objects.filter(company=company, start_date__gte=today).exclude(status="cancelled").count(),
        "zavrseni": Dogadjaj.objects.filter(company=company, status="completed").count(),
    }

    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "udruge/dogadjaj_list.html", {
        "page_obj": page,
        "stats": stats,
        "status_f": status_f,
        "type_f": type_f,
        "status_choices": Dogadjaj.STATUS_CHOICES,
        "type_choices": Dogadjaj.TYPE_CHOICES,
    })


@login_required
def dogadjaj_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, "Nema aktivne udruge.")
        return redirect("udruge:dogadjaj_list")

    from .models import Dogadjaj, Kampanja

    if request.method == "POST":
        from decimal import Decimal
        dogadjaj = Dogadjaj(
            company=company,
            name=request.POST.get("name", ""),
            event_type=request.POST.get("event_type", "ostalo"),
            description=request.POST.get("description", ""),
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date") or None,
            location=request.POST.get("location", ""),
            online_url=request.POST.get("online_url", ""),
            max_attendees=int(request.POST.get("max_attendees", 0) or 0),
            registration_required="registration_required" in request.POST,
            registration_deadline=request.POST.get("registration_deadline") or None,
            ticket_price=Decimal(request.POST.get("ticket_price", "0") or "0"),
            is_free="is_free" in request.POST,
            status=request.POST.get("status", "draft"),
            organizer=request.user,
            budget=Decimal(request.POST.get("budget", "0") or "0"),
            notes=request.POST.get("notes", ""),
        )
        kampanja_id = request.POST.get("kampanja")
        if kampanja_id:
            dogadjaj.kampanja_id = int(kampanja_id)
        dogadjaj.save()
        messages.success(request, "Dogadjaj '%s' kreiran." % dogadjaj.name)
        return redirect("udruge:dogadjaj_detail", pk=dogadjaj.pk)

    kampanje = Kampanja.objects.filter(company=company, status__in=["draft", "active"])
    return render(request, "udruge/dogadjaj_form.html", {
        "type_choices": Dogadjaj.TYPE_CHOICES,
        "status_choices": Dogadjaj.STATUS_CHOICES,
        "kampanje": kampanje,
    })


@login_required
def dogadjaj_detail(request, pk):
    company = get_user_company(request)
    from .models import Dogadjaj, EventPrijava, Clan

    dogadjaj = get_object_or_404(Dogadjaj, pk=pk, company=company)
    prijave = dogadjaj.prijave.select_related("clan").all()

    user_clan = Clan.objects.filter(company=company, email=request.user.email).first()
    user_registered = False
    if user_clan:
        user_registered = prijave.filter(clan=user_clan).exists()

    return render(request, "udruge/dogadjaj_detail.html", {
        "dogadjaj": dogadjaj,
        "prijave": prijave,
        "user_clan": user_clan,
        "user_registered": user_registered,
    })


@login_required
@require_POST
def dogadjaj_register(request, pk):
    company = get_user_company(request)
    from .models import Dogadjaj, EventPrijava, Clan

    dogadjaj = get_object_or_404(Dogadjaj, pk=pk, company=company)

    clan = Clan.objects.filter(company=company, email=request.user.email).first()
    if not clan:
        messages.error(request, "Nemate clan profil u ovoj udruzi.")
        return redirect("udruge:dogadjaj_detail", pk=pk)

    if dogadjaj.is_full:
        messages.error(request, "Nema slobodnih mjesta.")
        return redirect("udruge:dogadjaj_detail", pk=pk)

    prijava, created = EventPrijava.objects.get_or_create(
        dogadjaj=dogadjaj, clan=clan,
        defaults={"status": "confirmed"},
    )
    if created:
        messages.success(request, "Prijava uspjesna!")
    else:
        messages.info(request, "Vec ste prijavljeni.")

    return redirect("udruge:dogadjaj_detail", pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
# KAMPANJE (Campaigns)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def kampanja_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, "Nema aktivne udruge.")
        return redirect("dashboard")

    from .models import Kampanja
    type_f = request.GET.get("type", "")
    status_f = request.GET.get("status", "")

    qs = Kampanja.objects.filter(company=company)
    if type_f:
        qs = qs.filter(campaign_type=type_f)
    if status_f:
        qs = qs.filter(status=status_f)

    from django.db.models import Sum
    stats = {
        "ukupno": Kampanja.objects.filter(company=company).count(),
        "aktivne": Kampanja.objects.filter(company=company, status="active").count(),
        "prikupljeno": Kampanja.objects.filter(company=company).aggregate(s=Sum("raised_amount"))["s"] or 0,
    }

    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "udruge/kampanja_list.html", {
        "page_obj": page,
        "stats": stats,
        "type_f": type_f,
        "status_f": status_f,
        "type_choices": Kampanja.TYPE_CHOICES,
        "status_choices": Kampanja.STATUS_CHOICES,
    })


@login_required
def kampanja_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, "Nema aktivne udruge.")
        return redirect("udruge:kampanja_list")

    from .models import Kampanja
    from decimal import Decimal

    if request.method == "POST":
        kampanja = Kampanja(
            company=company,
            name=request.POST.get("name", ""),
            campaign_type=request.POST.get("campaign_type", "fundraising"),
            description=request.POST.get("description", ""),
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date") or None,
            goal_amount=Decimal(request.POST.get("goal_amount", "0") or "0"),
            goal_members=int(request.POST.get("goal_members", "0") or 0),
            status=request.POST.get("status", "draft"),
            responsible=request.user,
            eu_project_code=request.POST.get("eu_project_code", ""),
            eu_program=request.POST.get("eu_program", ""),
            notes=request.POST.get("notes", ""),
        )
        kampanja.save()
        messages.success(request, "Kampanja '%s' kreirana." % kampanja.name)
        return redirect("udruge:kampanja_detail", pk=kampanja.pk)

    return render(request, "udruge/kampanja_form.html", {
        "type_choices": Kampanja.TYPE_CHOICES,
        "status_choices": Kampanja.STATUS_CHOICES,
    })


@login_required
def kampanja_detail(request, pk):
    company = get_user_company(request)
    from .models import Kampanja, Donacija

    kampanja = get_object_or_404(Kampanja, pk=pk, company=company)
    events = kampanja.dogadjaji.all()

    donacije = Donacija.objects.filter(company=company)
    if kampanja.start_date and kampanja.end_date:
        donacije = donacije.filter(date__gte=kampanja.start_date, date__lte=kampanja.end_date)
    else:
        donacije = donacije.none()

    return render(request, "udruge/kampanja_detail.html", {
        "kampanja": kampanja,
        "events": events,
        "donacije": donacije,
    })


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL KAMPANJE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def email_kampanja_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, "Nema aktivne udruge.")
        return redirect("dashboard")

    from .models import EmailKampanja
    qs = EmailKampanja.objects.filter(company=company)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "udruge/email_kampanja_list.html", {
        "page_obj": page,
    })


@login_required
def email_kampanja_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, "Nema aktivne udruge.")
        return redirect("udruge:email_kampanja_list")

    from .models import EmailKampanja, Kampanja, Dogadjaj, Clan

    if request.method == "POST":
        ek = EmailKampanja(
            company=company,
            name=request.POST.get("name", ""),
            email_type=request.POST.get("email_type", "newsletter"),
            subject=request.POST.get("subject", ""),
            body_html=request.POST.get("body_html", ""),
            body_text=request.POST.get("body_text", ""),
            target_all_members="target_all_members" in request.POST,
            created_by=request.user,
            status="draft",
        )

        if "ai_generate" in request.POST:
            try:
                import os, anthropic
                client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                ai_prompt = "Napisi email za udrugu '%s'. Tip: %s. Predmet: %s. Jezik: hrvatski. Vrati samo HTML body." % (
                    company.name,
                    ek.get_email_type_display(),
                    ek.subject or ek.name,
                )
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": ai_prompt}],
                )
                ek.body_html = response.content[0].text.strip()
                ek.ai_generated = True
                ek.ai_prompt = ai_prompt
            except Exception as e:
                logger.error("AI email generate: %s", e)
                messages.warning(request, "AI generiranje nije uspjelo: %s" % str(e))

        target_kampanja_id = request.POST.get("target_kampanja")
        if target_kampanja_id:
            ek.target_kampanja_id = int(target_kampanja_id)
        target_dogadjaj_id = request.POST.get("target_dogadjaj")
        if target_dogadjaj_id:
            ek.target_dogadjaj_id = int(target_dogadjaj_id)

        ek.save()
        messages.success(request, "Email kampanja '%s' kreirana." % ek.name)
        return redirect("udruge:email_kampanja_list")

    kampanje = Kampanja.objects.filter(company=company)
    dogadjaji = Dogadjaj.objects.filter(company=company)
    member_count = Clan.objects.filter(company=company, status="aktivan").exclude(email="").count()

    return render(request, "udruge/email_kampanja_create.html", {
        "type_choices": EmailKampanja.TYPE_CHOICES,
        "kampanje": kampanje,
        "dogadjaji": dogadjaji,
        "member_count": member_count,
    })


@login_required
@require_POST
def email_kampanja_send(request, pk):
    company = get_user_company(request)
    from .models import EmailKampanja

    kampanja = get_object_or_404(EmailKampanja, pk=pk, company=company)

    if kampanja.status not in ("draft", "scheduled"):
        messages.error(request, "Kampanja se ne moze poslati (status: %s)." % kampanja.get_status_display())
        return redirect("udruge:email_kampanja_list")

    kampanja.status = "scheduled"
    kampanja.scheduled_at = timezone.now()
    kampanja.save(update_fields=["status", "scheduled_at"])

    from .tasks import send_email_campaign
    send_email_campaign.delay(kampanja.pk)

    messages.success(request, "Email kampanja '%s' zakazana za slanje!" % kampanja.name)
    return redirect("udruge:email_kampanja_list")


# ── CLAN EDIT ──────────────────────────────────────────────────────────────

@login_required
def clan_edit(request, pk):
    company = get_user_company(request)
    from .models import Clan
    clan = get_object_or_404(Clan, pk=pk, company=company)

    if request.method == 'POST':
        for field in ['first_name', 'last_name', 'oib', 'email', 'phone',
                       'address', 'city', 'membership_type', 'membership_number',
                       'business_interest', 'whatsapp_phone', 'notes', 'opg_oib', 'access_card_uid']:
            val = request.POST.get(field)
            if val is not None:
                setattr(clan, field, val)
        for bf in ['has_opg', 'has_obrt', 'whatsapp_opt_in']:
            setattr(clan, bf, bf in request.POST)
        for df in ['date_of_birth', 'membership_expires', 'date_joined']:
            setattr(clan, df, request.POST.get(df) or None)
        status = request.POST.get('status')
        if status:
            clan.status = status
        sponsor_id = request.POST.get('paying_sponsor')
        clan.paying_sponsor_id = int(sponsor_id) if sponsor_id else None
        clan.save()
        messages.success(request, 'Clan %s azuriran.' % clan.full_name)
        return redirect('udruge:clan_detail', pk=clan.pk)

    from partners.models import Partner
    sponsors = Partner.objects.filter(company=company)[:50] if company else []
    return render(request, 'udruge/clan_form.html', {
        'clan': clan, 'membership_choices': Clan.MEMBERSHIP_CHOICES,
        'status_choices': Clan.STATUS_CHOICES, 'interest_choices': Clan.INTEREST_CHOICES,
        'sponsors': sponsors, 'edit_mode': True,
    })


# ── VOLONTERSKE AKTIVNOSTI ──────────────────────────────────────────────────

@login_required
def volunteer_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')
    from .models import VolunteerActivity
    from django.db.models import Sum
    year = request.GET.get('year', str(timezone.now().year))
    clan_id = request.GET.get('clan')
    category = request.GET.get('category')
    qs = VolunteerActivity.objects.filter(company=company, date__year=year).select_related('clan', 'dogadjaj')
    if clan_id:
        qs = qs.filter(clan_id=clan_id)
    if category:
        qs = qs.filter(category=category)
    stats = {
        'ukupno': qs.count(),
        'sati': qs.aggregate(s=Sum('hours'))['s'] or 0,
        'volonteri': qs.values('clan').distinct().count(),
        'inkind': sum(a.inkind_value for a in qs),
    }
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/volunteer_list.html', {
        'page_obj': page, 'stats': stats, 'year': year,
        'category_choices': VolunteerActivity.CATEGORY_CHOICES, 'category_f': category,
    })


@login_required
def volunteer_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('udruge:volunteer_list')
    from .models import VolunteerActivity, Clan, Dogadjaj, Kampanja
    from decimal import Decimal
    if request.method == 'POST':
        VolunteerActivity.objects.create(
            company=company, clan_id=int(request.POST.get('clan')),
            title=request.POST.get('title', ''), description=request.POST.get('description', ''),
            category=request.POST.get('category', 'other'),
            date=request.POST.get('date') or timezone.now().date(),
            hours=Decimal(request.POST.get('hours', '0')),
            location=request.POST.get('location', ''), status=request.POST.get('status', 'planned'),
            eu_project_code=request.POST.get('eu_project_code', ''),
            inkind_rate_eur=Decimal(request.POST.get('inkind_rate_eur', '0') or '0'),
            dogadjaj_id=request.POST.get('dogadjaj') or None,
            kampanja_id=request.POST.get('kampanja') or None, notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Volonterska aktivnost evidentirana.')
        return redirect('udruge:volunteer_list')
    return render(request, 'udruge/volunteer_form.html', {
        'clanovi': Clan.objects.filter(company=company, status='aktivan'),
        'category_choices': VolunteerActivity.CATEGORY_CHOICES,
        'status_choices': VolunteerActivity.STATUS_CHOICES,
        'dogadjaji': Dogadjaj.objects.filter(company=company)[:20],
        'kampanje': Kampanja.objects.filter(company=company)[:20],
    })


# ── EU FOND AI SEARCH ──────────────────────────────────────────────────────

@login_required
@require_POST
def eu_fund_search(request):
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema aktivne udruge'}, status=400)
    from .tasks import ai_search_eu_funds
    ai_search_eu_funds.delay(company.pk)
    messages.success(request, 'AI pretraga EU fondova pokrenuta. Rezultati u Kampanjama.')
    return redirect('udruge:kampanja_list')
