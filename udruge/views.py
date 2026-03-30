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
from django.views.decorators.csrf import csrf_exempt
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


# ═══════════════════════════════════════════════════════════════
#  QuickAction API — Member lookup (POS iskaznica scan)
# ═══════════════════════════════════════════════════════════════

@login_required
def api_member_lookup(request):
    """Traži člana po broju iskaznice, OIB-u ili imenu."""
    from django.http import JsonResponse
    from udruge.models import Clan

    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'found': False})

    company = get_user_company(request)

    # Traži po card_number, oib, ili imenu
    member = Clan.objects.filter(company=company).filter(
        Q(card_number=code) |
        Q(oib=code) |
        Q(first_name__icontains=code) |
        Q(last_name__icontains=code)
    ).first()

    if not member:
        return JsonResponse({'found': False})

    # Provjeri aktivnost članstva
    from django.utils import timezone
    is_active = True
    valid_until = None
    try:
        sub = member.subscriptions.order_by('-end_date').first()
        if sub:
            valid_until = sub.end_date.strftime('%d.%m.%Y') if sub.end_date else None
            is_active = sub.end_date >= timezone.now().date() if sub.end_date else True
    except Exception:
        pass

    return JsonResponse({
        'found': True,
        'member': {
            'id': member.pk,
            'name': f'{member.first_name} {member.last_name}',
            'oib': getattr(member, 'oib', '') or '',
            'membership_type': getattr(member, 'membership_type', '') or 'Član',
            'valid_until': valid_until,
            'is_active': is_active,
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
# SEKCIJE (Sections — KUD, ribolov, sport)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def sekcija_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Sekcija
    sekcije = Sekcija.objects.filter(company=company)
    return render(request, 'udruge/sekcija_list.html', {'sekcije': sekcije})


@login_required
def sekcija_detail(request, pk):
    company = get_user_company(request)
    from .models import Sekcija
    sekcija = get_object_or_404(Sekcija, pk=pk, company=company)
    members = sekcija.members.select_related('clan').all()
    from .models import Clan
    available_clans = Clan.objects.filter(company=company, status='aktivan').exclude(
        pk__in=members.values_list('clan_id', flat=True)
    )
    return render(request, 'udruge/sekcija_detail.html', {
        'sekcija': sekcija, 'members': members, 'available_clans': available_clans,
    })


@login_required
def sekcija_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    if request.method == 'POST':
        from .models import Sekcija
        Sekcija.objects.create(
            company=company,
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            max_members=int(request.POST.get('max_members', 0) or 0),
        )
        messages.success(request, 'Sekcija kreirana.')
        return redirect('udruge:sekcija_list')
    return render(request, 'udruge/sekcija_form.html', {})


@login_required
@require_POST
def sekcija_add_member(request, pk):
    company = get_user_company(request)
    from .models import Sekcija, ClanSekcija, Clan
    sekcija = get_object_or_404(Sekcija, pk=pk, company=company)
    clan_id = request.POST.get('clan_id')
    role = request.POST.get('role', '')
    if clan_id:
        clan = get_object_or_404(Clan, pk=clan_id)
        ClanSekcija.objects.get_or_create(clan=clan, sekcija=sekcija, defaults={'role': role})
        messages.success(request, '%s dodan u %s.' % (clan, sekcija.name))
    return redirect('udruge:sekcija_detail', pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
# DOKUMENTI / DOZVOLE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def clan_dokumenti(request, pk):
    """Dokumenti jednog clana — dozvole, licence."""
    company = get_user_company(request)
    from .models import Clan, ClanskiDokument
    clan = get_object_or_404(Clan, pk=pk, company=company)
    docs = ClanskiDokument.objects.filter(clan=clan)

    if request.method == 'POST':
        ClanskiDokument.objects.create(
            clan=clan,
            doc_type=request.POST.get('doc_type', 'other'),
            doc_number=request.POST.get('doc_number', ''),
            issued_by=request.POST.get('issued_by', ''),
            issue_date=request.POST.get('issue_date') or None,
            valid_until=request.POST.get('valid_until') or None,
            file=request.FILES.get('file'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Dokument dodan.')
        return redirect('udruge:clan_dokumenti', pk=pk)

    return render(request, 'udruge/clan_dokumenti.html', {
        'clan': clan, 'docs': docs, 'doc_types': ClanskiDokument.DOC_TYPES,
    })


@login_required
def dozvole_pregled(request):
    """Pregled svih dozvola — istekle, uskoro isticu, aktivne."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ClanskiDokument
    from datetime import timedelta

    today = timezone.now().date()
    threshold = today + timedelta(days=30)

    all_docs = ClanskiDokument.objects.filter(clan__company=company).select_related('clan')
    expired = all_docs.filter(valid_until__lt=today)
    expiring = all_docs.filter(valid_until__gte=today, valid_until__lte=threshold)
    valid = all_docs.filter(valid_until__gt=threshold)
    no_expiry = all_docs.filter(valid_until__isnull=True)

    return render(request, 'udruge/dozvole_pregled.html', {
        'expired': expired, 'expiring': expiring, 'valid': valid, 'no_expiry': no_expiry,
        'total': all_docs.count(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# DVD — VATROGASCI
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def dvd_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnaOprema, VatrogasnoVozilo, Intervencija, Vjezba, VatrogasnoZvanje
    from django.db.models import Count, Sum, Avg
    from datetime import timedelta

    today = timezone.now().date()
    oprema = VatrogasnaOprema.objects.filter(company=company)
    vozila = VatrogasnoVozilo.objects.filter(company=company)
    intervencije = Intervencija.objects.filter(company=company)
    vjezbe = Vjezba.objects.filter(company=company)
    zvanja = VatrogasnoZvanje.objects.filter(company=company)

    ctx = {
        'oprema_total': oprema.count(),
        'oprema_neispravno': oprema.filter(status='neispravno').count(),
        'oprema_atest_istekao': oprema.filter(atest_vrijedi_do__lt=today).count(),
        'oprema_atest_istice': oprema.filter(atest_vrijedi_do__gte=today, atest_vrijedi_do__lte=today + timedelta(days=30)).count(),
        'vozila_total': vozila.count(),
        'vozila_aktivna': vozila.filter(status='aktivno').count(),
        'intervencije_total': intervencije.count(),
        'intervencije_godina': intervencije.filter(alarm_primljen__year=today.year).count(),
        'intervencije_steta': intervencije.aggregate(s=Sum('steta_eur'))['s'] or 0,
        'intervencije_spaseno': intervencije.aggregate(s=Sum('spaseno_osoba'))['s'] or 0,
        'vjezbe_total': vjezbe.count(),
        'vjezbe_godina': vjezbe.filter(datum__year=today.year).count(),
        'zvanja_total': zvanja.count(),
    }
    return render(request, 'udruge/dvd_dashboard.html', ctx)


@login_required
def vatrogasna_oprema_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnaOprema
    qs = VatrogasnaOprema.objects.filter(company=company)
    kat = request.GET.get('kategorija', '')
    status = request.GET.get('status', '')
    if kat:
        qs = qs.filter(kategorija=kat)
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/vatrogasna_oprema_list.html', {
        'page_obj': page, 'kategorija': kat, 'status': status,
        'kategorije': VatrogasnaOprema.KATEGORIJA_CHOICES, 'statusi': VatrogasnaOprema.STATUS_CHOICES,
    })


@login_required
def vatrogasna_oprema_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnaOprema
    from decimal import Decimal
    if request.method == 'POST':
        VatrogasnaOprema.objects.create(
            company=company, naziv=request.POST.get('naziv', ''),
            kategorija=request.POST.get('kategorija', 'ostalo'),
            serijski_broj=request.POST.get('serijski_broj', ''),
            proizvodac=request.POST.get('proizvodac', ''),
            godina_nabave=int(request.POST.get('godina_nabave') or 0) or None,
            nabavna_vrijednost=Decimal(request.POST.get('nabavna_vrijednost') or '0'),
            status=request.POST.get('status', 'ispravno'),
            atest_datum=request.POST.get('atest_datum') or None,
            atest_vrijedi_do=request.POST.get('atest_vrijedi_do') or None,
            atest_izdavac=request.POST.get('atest_izdavac', ''),
            sljedeci_servis=request.POST.get('sljedeci_servis') or None,
            lokacija=request.POST.get('lokacija', ''),
            qr_code=request.POST.get('qr_code', ''),
            photo=request.FILES.get('photo'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Oprema dodana.')
        return redirect('udruge:vatrogasna_oprema_list')
    return render(request, 'udruge/vatrogasna_oprema_form.html', {
        'kategorije': VatrogasnaOprema.KATEGORIJA_CHOICES, 'statusi': VatrogasnaOprema.STATUS_CHOICES,
    })


@login_required
def vatrogasna_oprema_detail(request, pk):
    company = get_user_company(request)
    from .models import VatrogasnaOprema
    obj = get_object_or_404(VatrogasnaOprema, pk=pk, company=company)
    return render(request, 'udruge/vatrogasna_oprema_detail.html', {'oprema': obj})


@login_required
def vatrogasno_vozilo_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnoVozilo
    qs = VatrogasnoVozilo.objects.filter(company=company)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/vatrogasno_vozilo_list.html', {'page_obj': page})


@login_required
def vatrogasno_vozilo_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnoVozilo
    if request.method == 'POST':
        VatrogasnoVozilo.objects.create(
            company=company, naziv=request.POST.get('naziv', ''),
            tip=request.POST.get('tip', 'navalno'),
            reg_oznaka=request.POST.get('reg_oznaka', ''),
            marka=request.POST.get('marka', ''),
            godina_proizvodnje=int(request.POST.get('godina_proizvodnje') or 0) or None,
            kapacitet_vode_l=int(request.POST.get('kapacitet_vode_l') or 0),
            reg_vrijedi_do=request.POST.get('reg_vrijedi_do') or None,
            tehnicki_do=request.POST.get('tehnicki_do') or None,
            osiguranje_do=request.POST.get('osiguranje_do') or None,
            status=request.POST.get('status', 'aktivno'),
            photo=request.FILES.get('photo'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Vozilo dodano.')
        return redirect('udruge:vatrogasno_vozilo_list')
    return render(request, 'udruge/vatrogasno_vozilo_form.html', {
        'tipovi': VatrogasnoVozilo.TIP_CHOICES,
    })


@login_required
def vatrogasno_vozilo_detail(request, pk):
    company = get_user_company(request)
    from .models import VatrogasnoVozilo
    obj = get_object_or_404(VatrogasnoVozilo, pk=pk, company=company)
    return render(request, 'udruge/vatrogasno_vozilo_detail.html', {'vozilo': obj})


@login_required
def intervencija_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Intervencija
    qs = Intervencija.objects.filter(company=company).select_related('voditelj')
    tip = request.GET.get('tip', '')
    if tip:
        qs = qs.filter(tip=tip)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/intervencija_list.html', {
        'page_obj': page, 'tip': tip, 'tipovi': Intervencija.TIP_CHOICES,
    })


@login_required
def intervencija_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Intervencija, Clan
    if request.method == 'POST':
        voditelj_id = request.POST.get('voditelj') or None
        Intervencija.objects.create(
            company=company, evidencijski_broj=request.POST.get('evidencijski_broj', ''),
            tip=request.POST.get('tip', 'pozar'),
            opis=request.POST.get('opis', ''),
            alarm_primljen=request.POST.get('alarm_primljen'),
            izlazak=request.POST.get('izlazak') or None,
            dolazak=request.POST.get('dolazak') or None,
            zavrsetak=request.POST.get('zavrsetak') or None,
            povratak=request.POST.get('povratak') or None,
            lokacija=request.POST.get('lokacija', ''),
            voditelj_id=voditelj_id,
            broj_sudionika=int(request.POST.get('broj_sudionika') or 0),
            voda_utrosena_l=int(request.POST.get('voda_utrosena_l') or 0),
            pjena_utrosena_l=int(request.POST.get('pjena_utrosena_l') or 0),
            steta_eur=request.POST.get('steta_eur') or 0,
            spaseno_osoba=int(request.POST.get('spaseno_osoba') or 0),
            spaseno_zivotinja=int(request.POST.get('spaseno_zivotinja') or 0),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        messages.success(request, 'Intervencija evidentirana.')
        return redirect('udruge:intervencija_list')
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/intervencija_form.html', {
        'tipovi': Intervencija.TIP_CHOICES, 'clanovi': clanovi,
    })


@login_required
def intervencija_detail(request, pk):
    company = get_user_company(request)
    from .models import Intervencija
    obj = get_object_or_404(Intervencija, pk=pk, company=company)
    return render(request, 'udruge/intervencija_detail.html', {'intervencija': obj})


@login_required
def vjezba_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Vjezba
    qs = Vjezba.objects.filter(company=company).select_related('voditelj')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/vjezba_list.html', {'page_obj': page})


@login_required
def vjezba_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Vjezba, Clan
    from decimal import Decimal
    if request.method == 'POST':
        Vjezba.objects.create(
            company=company, naziv=request.POST.get('naziv', ''),
            tip=request.POST.get('tip', 'prakticna'),
            datum=request.POST.get('datum'),
            trajanje_sati=Decimal(request.POST.get('trajanje_sati') or '2'),
            lokacija=request.POST.get('lokacija', ''),
            voditelj_id=request.POST.get('voditelj') or None,
            opis=request.POST.get('opis', ''),
            ocjena=request.POST.get('ocjena', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Vježba evidentirana.')
        return redirect('udruge:vjezba_list')
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/vjezba_form.html', {
        'tipovi': Vjezba.TIP_CHOICES, 'clanovi': clanovi,
    })


@login_required
def vjezba_detail(request, pk):
    company = get_user_company(request)
    from .models import Vjezba
    obj = get_object_or_404(Vjezba, pk=pk, company=company)
    return render(request, 'udruge/vjezba_detail.html', {'vjezba': obj})


@login_required
def vatrogasno_zvanje_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnoZvanje
    qs = VatrogasnoZvanje.objects.filter(company=company).select_related('clan')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/vatrogasno_zvanje_list.html', {'page_obj': page})


@login_required
def vatrogasno_zvanje_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import VatrogasnoZvanje, Clan
    if request.method == 'POST':
        VatrogasnoZvanje.objects.create(
            company=company,
            clan_id=request.POST.get('clan'),
            zvanje=request.POST.get('zvanje', ''),
            datum_stjecanja=request.POST.get('datum_stjecanja') or None,
            certifikat_broj=request.POST.get('certifikat_broj', ''),
            izdavac=request.POST.get('izdavac', ''),
            vrijedi_do=request.POST.get('vrijedi_do') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Zvanje dodano.')
        return redirect('udruge:vatrogasno_zvanje_list')
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/vatrogasno_zvanje_form.html', {'clanovi': clanovi})


@login_required
def vatrogasno_zvanje_detail(request, pk):
    company = get_user_company(request)
    from .models import VatrogasnoZvanje
    obj = get_object_or_404(VatrogasnoZvanje, pk=pk, company=company)
    return render(request, 'udruge/vatrogasno_zvanje_detail.html', {'zvanje': obj})


# ══════════════════════════════════════════════════════════════════════════════
# KUD — KULTURNO-UMJETNIČKO DRUŠTVO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def kud_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Repertoar, ProbaLog, Kostim, NastupPlan, Dogadjaj
    from django.db.models import Count, Sum

    today = timezone.now().date()
    repertoar = Repertoar.objects.filter(company=company)
    probe = ProbaLog.objects.filter(company=company)
    kostimi = Kostim.objects.filter(company=company)
    nastupi = NastupPlan.objects.filter(dogadjaj__company=company)

    ctx = {
        'repertoar_total': repertoar.count(),
        'repertoar_aktivan': repertoar.filter(is_active=True).count(),
        'probe_total': probe.count(),
        'probe_godina': probe.filter(datum__year=today.year).count(),
        'kostimi_total': kostimi.count(),
        'kostimi_dobri': kostimi.filter(stanje__in=['novo', 'dobro']).count(),
        'kostimi_popravak': kostimi.filter(stanje='popravak').count(),
        'kostimi_vrijednost': kostimi.aggregate(s=Sum('nabavna_cijena'))['s'] or 0,
        'nastupi_total': nastupi.count(),
        'nadolazeci_nastupi': NastupPlan.objects.filter(
            dogadjaj__company=company, dogadjaj__date__gte=today
        ).select_related('dogadjaj')[:5],
    }
    return render(request, 'udruge/kud_dashboard.html', ctx)


@login_required
def repertoar_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Repertoar
    qs = Repertoar.objects.filter(company=company)
    tip = request.GET.get('tip', '')
    if tip:
        qs = qs.filter(tip=tip)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/repertoar_list.html', {
        'page_obj': page, 'tip': tip, 'tipovi': Repertoar.TIP_CHOICES,
    })


@login_required
def repertoar_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Repertoar, Sekcija
    if request.method == 'POST':
        Repertoar.objects.create(
            company=company, naziv=request.POST.get('naziv', ''),
            tip=request.POST.get('tip', 'pjesma'),
            sekcija_id=request.POST.get('sekcija') or None,
            autor=request.POST.get('autor', ''),
            trajanje_min=int(request.POST.get('trajanje_min') or 0) or None,
            region=request.POST.get('region', ''),
            opis=request.POST.get('opis', ''),
            note_file=request.FILES.get('note_file'),
            audio_file=request.FILES.get('audio_file'),
            video_url=request.POST.get('video_url', ''),
            koreografija_file=request.FILES.get('koreografija_file'),
        )
        messages.success(request, 'Repertoar dodan.')
        return redirect('udruge:repertoar_list')
    sekcije = Sekcija.objects.filter(company=company)
    return render(request, 'udruge/repertoar_form.html', {
        'tipovi': Repertoar.TIP_CHOICES, 'sekcije': sekcije,
    })


@login_required
def repertoar_detail(request, pk):
    company = get_user_company(request)
    from .models import Repertoar
    obj = get_object_or_404(Repertoar, pk=pk, company=company)
    return render(request, 'udruge/repertoar_detail.html', {'repertoar': obj})


@login_required
def proba_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ProbaLog
    qs = ProbaLog.objects.filter(company=company).select_related('sekcija', 'voditelj')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/proba_list.html', {'page_obj': page})


@login_required
def proba_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ProbaLog, Sekcija, Clan
    if request.method == 'POST':
        ProbaLog.objects.create(
            company=company,
            sekcija_id=request.POST.get('sekcija'),
            datum=request.POST.get('datum'),
            pocetak=request.POST.get('pocetak') or None,
            kraj=request.POST.get('kraj') or None,
            lokacija=request.POST.get('lokacija', ''),
            voditelj_id=request.POST.get('voditelj') or None,
            biljeska=request.POST.get('biljeska', ''),
        )
        messages.success(request, 'Proba evidentirana.')
        return redirect('udruge:proba_list')
    sekcije = Sekcija.objects.filter(company=company)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/proba_form.html', {'sekcije': sekcije, 'clanovi': clanovi})


@login_required
def proba_detail(request, pk):
    company = get_user_company(request)
    from .models import ProbaLog
    obj = get_object_or_404(ProbaLog, pk=pk, company=company)
    return render(request, 'udruge/proba_detail.html', {'proba': obj})


@login_required
def kostim_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Kostim
    qs = Kostim.objects.filter(company=company).select_related('sekcija', 'dodijeljen_clanu')
    stanje = request.GET.get('stanje', '')
    if stanje:
        qs = qs.filter(stanje=stanje)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/kostim_list.html', {
        'page_obj': page, 'stanje': stanje, 'stanja': Kostim.STANJE_CHOICES,
    })


@login_required
def kostim_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Kostim, Sekcija, Clan
    from decimal import Decimal
    if request.method == 'POST':
        Kostim.objects.create(
            company=company, naziv=request.POST.get('naziv', ''),
            sekcija_id=request.POST.get('sekcija') or None,
            region=request.POST.get('region', ''),
            spol=request.POST.get('spol', 'U'),
            velicina=request.POST.get('velicina', ''),
            inventarni_broj=request.POST.get('inventarni_broj', ''),
            dodijeljen_clanu_id=request.POST.get('dodijeljen_clanu') or None,
            dodijeljen_od=request.POST.get('dodijeljen_od') or None,
            stanje=request.POST.get('stanje', 'dobro'),
            nabavna_cijena=Decimal(request.POST.get('nabavna_cijena') or '0'),
            photo=request.FILES.get('photo'),
            opis_dijelova=request.POST.get('opis_dijelova', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Kostim dodan.')
        return redirect('udruge:kostim_list')
    sekcije = Sekcija.objects.filter(company=company)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/kostim_form.html', {
        'stanja': Kostim.STANJE_CHOICES, 'sekcije': sekcije, 'clanovi': clanovi,
    })


@login_required
def kostim_detail(request, pk):
    company = get_user_company(request)
    from .models import Kostim
    obj = get_object_or_404(Kostim, pk=pk, company=company)
    return render(request, 'udruge/kostim_detail.html', {'kostim': obj})


@login_required
def nastup_plan_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import NastupPlan
    qs = NastupPlan.objects.filter(dogadjaj__company=company).select_related('dogadjaj')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/nastup_plan_list.html', {'page_obj': page})


@login_required
def nastup_plan_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import NastupPlan, Dogadjaj
    from decimal import Decimal
    if request.method == 'POST':
        NastupPlan.objects.create(
            dogadjaj_id=request.POST.get('dogadjaj'),
            raspored_dolaska=request.POST.get('raspored_dolaska') or None,
            proba_prije_nastupa=request.POST.get('proba_prije_nastupa') == 'on',
            garderoba=request.POST.get('garderoba', ''),
            prijevoz=request.POST.get('prijevoz', ''),
            smjestaj=request.POST.get('smjestaj', ''),
            troskovi=Decimal(request.POST.get('troskovi') or '0'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Plan nastupa kreiran.')
        return redirect('udruge:nastup_plan_list')
    dogadjaji = Dogadjaj.objects.filter(company=company)
    return render(request, 'udruge/nastup_plan_form.html', {'dogadjaji': dogadjaji})


@login_required
def nastup_plan_detail(request, pk):
    company = get_user_company(request)
    from .models import NastupPlan
    obj = get_object_or_404(NastupPlan, pk=pk, dogadjaj__company=company)
    return render(request, 'udruge/nastup_plan_detail.html', {'nastup': obj})


# ══════════════════════════════════════════════════════════════════════════════
# RIBARI — ŠPORTSKI RIBOLOV
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def ribari_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Revir, RibolovnaDozvola, UlovEvidencija, Poribljavanje, CuvarskaStraza
    from django.db.models import Sum, Count

    today = timezone.now().date()
    reviri = Revir.objects.filter(company=company)
    dozvole = RibolovnaDozvola.objects.filter(company=company)
    ulovi = UlovEvidencija.objects.filter(revir__company=company)
    poribljavanje = Poribljavanje.objects.filter(revir__company=company)
    straze = CuvarskaStraza.objects.filter(company=company)

    ctx = {
        'reviri_total': reviri.count(),
        'reviri_aktivni': reviri.filter(is_active=True).count(),
        'reviri_zabrana': reviri.filter(zabrana_ribolova=True).count(),
        'dozvole_total': dozvole.count(),
        'dozvole_aktivne': dozvole.filter(valid_until__gte=today).count(),
        'dozvole_prihod': dozvole.aggregate(s=Sum('cijena'))['s'] or 0,
        'ulovi_total': ulovi.count(),
        'ulovi_godina': ulovi.filter(datum__year=today.year).count(),
        'ulovi_kg': ulovi.aggregate(s=Sum('tezina_kg'))['s'] or 0,
        'poribljavanje_total': poribljavanje.count(),
        'poribljavanje_kg': poribljavanje.aggregate(s=Sum('kolicina_kg'))['s'] or 0,
        'straze_total': straze.count(),
        'straze_godina': straze.filter(datum__year=today.year).count(),
    }
    return render(request, 'udruge/ribari_dashboard.html', ctx)


@login_required
def revir_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Revir
    qs = Revir.objects.filter(company=company)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/revir_list.html', {'page_obj': page})


@login_required
def revir_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Revir
    from decimal import Decimal
    if request.method == 'POST':
        Revir.objects.create(
            company=company, naziv=request.POST.get('naziv', ''),
            tip=request.POST.get('tip', 'rijeka'),
            lokacija=request.POST.get('lokacija', ''),
            povrsina_ha=Decimal(request.POST.get('povrsina_ha') or '0') or None,
            duljina_km=Decimal(request.POST.get('duljina_km') or '0') or None,
            max_dnevni_ulov_kg=Decimal(request.POST.get('max_dnevni_ulov_kg') or '5'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Revir dodan.')
        return redirect('udruge:revir_list')
    return render(request, 'udruge/revir_form.html', {'tipovi': Revir.TIP_CHOICES})


@login_required
def revir_detail(request, pk):
    company = get_user_company(request)
    from .models import Revir
    obj = get_object_or_404(Revir, pk=pk, company=company)
    return render(request, 'udruge/revir_detail.html', {'revir': obj})


@login_required
def ribolovna_dozvola_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import RibolovnaDozvola
    qs = RibolovnaDozvola.objects.filter(company=company).select_related('clan')
    kat = request.GET.get('kategorija', '')
    if kat:
        qs = qs.filter(kategorija=kat)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/ribolovna_dozvola_list.html', {
        'page_obj': page, 'kategorija': kat, 'kategorije': RibolovnaDozvola.KATEGORIJA_CHOICES,
    })


@login_required
def ribolovna_dozvola_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import RibolovnaDozvola, Clan, Revir
    from decimal import Decimal
    if request.method == 'POST':
        doz = RibolovnaDozvola.objects.create(
            company=company,
            clan_id=request.POST.get('clan'),
            kategorija=request.POST.get('kategorija', 'A'),
            broj_dozvole=request.POST.get('broj_dozvole', ''),
            valid_from=request.POST.get('valid_from'),
            valid_until=request.POST.get('valid_until'),
            cijena=Decimal(request.POST.get('cijena') or '0'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Dozvola izdana.')
        return redirect('udruge:ribolovna_dozvola_list')
    clanovi = Clan.objects.filter(company=company)
    reviri = Revir.objects.filter(company=company, is_active=True)
    return render(request, 'udruge/ribolovna_dozvola_form.html', {
        'kategorije': RibolovnaDozvola.KATEGORIJA_CHOICES, 'clanovi': clanovi, 'reviri': reviri,
    })


@login_required
def ribolovna_dozvola_detail(request, pk):
    company = get_user_company(request)
    from .models import RibolovnaDozvola
    obj = get_object_or_404(RibolovnaDozvola, pk=pk, company=company)
    return render(request, 'udruge/ribolovna_dozvola_detail.html', {'dozvola': obj})


@login_required
def ulov_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import UlovEvidencija
    qs = UlovEvidencija.objects.filter(company=company).select_related('revir', 'clan')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/ulov_list.html', {'page_obj': page})


@login_required
def ulov_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import UlovEvidencija, Revir, Clan
    from decimal import Decimal
    if request.method == 'POST':
        UlovEvidencija.objects.create(
            company=company,
            revir_id=request.POST.get('revir'),
            clan_id=request.POST.get('clan'),
            datum=request.POST.get('datum'),
            vrsta_ribe=request.POST.get('vrsta_ribe', ''),
            tezina_kg=Decimal(request.POST.get('tezina_kg') or '0'),
            duzina_cm=int(request.POST.get('duzina_cm') or 0) or None,
            catch_and_release=request.POST.get('catch_and_release') == 'on',
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Ulov evidentiran.')
        return redirect('udruge:ulov_list')
    reviri = Revir.objects.filter(company=company, is_active=True)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/ulov_form.html', {'reviri': reviri, 'clanovi': clanovi})


@login_required
def ulov_detail(request, pk):
    company = get_user_company(request)
    from .models import UlovEvidencija
    obj = get_object_or_404(UlovEvidencija, pk=pk, company=company)
    return render(request, 'udruge/ulov_detail.html', {'ulov': obj})


@login_required
def poribljavanje_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Poribljavanje
    qs = Poribljavanje.objects.filter(company=company).select_related('revir')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/poribljavanje_list.html', {'page_obj': page})


@login_required
def poribljavanje_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Poribljavanje, Revir
    from decimal import Decimal
    if request.method == 'POST':
        Poribljavanje.objects.create(
            company=company,
            revir_id=request.POST.get('revir'),
            datum=request.POST.get('datum'),
            vrsta_ribe=request.POST.get('vrsta_ribe', ''),
            kolicina_kg=Decimal(request.POST.get('kolicina_kg') or '0'),
            komada=int(request.POST.get('komada') or 0),
            dobavljac=request.POST.get('dobavljac', ''),
            cijena_eur=Decimal(request.POST.get('cijena_eur') or '0'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Poribljavanje evidentirano.')
        return redirect('udruge:poribljavanje_list')
    reviri = Revir.objects.filter(company=company, is_active=True)
    return render(request, 'udruge/poribljavanje_form.html', {'reviri': reviri})


@login_required
def poribljavanje_detail(request, pk):
    company = get_user_company(request)
    from .models import Poribljavanje
    obj = get_object_or_404(Poribljavanje, pk=pk, company=company)
    return render(request, 'udruge/poribljavanje_detail.html', {'poribljavanje': obj})


@login_required
def cuvarska_straza_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import CuvarskaStraza
    qs = CuvarskaStraza.objects.filter(company=company).select_related('cuvar', 'revir')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/cuvarska_straza_list.html', {'page_obj': page})


@login_required
def cuvarska_straza_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import CuvarskaStraza, Clan, Revir
    if request.method == 'POST':
        CuvarskaStraza.objects.create(
            company=company,
            cuvar_id=request.POST.get('cuvar'),
            revir_id=request.POST.get('revir'),
            datum_od=request.POST.get('datum_od'),
            datum_do=request.POST.get('datum_do'),
            prekrsaji=int(request.POST.get('prekrsaji') or 0),
            zapisnik=request.POST.get('zapisnik', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Čuvarska straža evidentirana.')
        return redirect('udruge:cuvarska_straza_list')
    clanovi = Clan.objects.filter(company=company)
    reviri = Revir.objects.filter(company=company, is_active=True)
    return render(request, 'udruge/cuvarska_straza_form.html', {'clanovi': clanovi, 'reviri': reviri})


@login_required
def cuvarska_straza_detail(request, pk):
    company = get_user_company(request)
    from .models import CuvarskaStraza
    obj = get_object_or_404(CuvarskaStraza, pk=pk, company=company)
    return render(request, 'udruge/cuvarska_straza_detail.html', {'straza': obj})


# ══════════════════════════════════════════════════════════════════════════════
# PČELARI
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def pcelari_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Pcelinjak, Kosnica, TretmanKosnice, MedProizvodnja, SelidbaLog
    from django.db.models import Sum, Count

    today = timezone.now().date()
    pcelinjaci = Pcelinjak.objects.filter(company=company)
    kosnice = Kosnica.objects.filter(pcelinjak__company=company)
    tretmani = TretmanKosnice.objects.filter(kosnica__pcelinjak__company=company)
    med = MedProizvodnja.objects.filter(pcelinjak__company=company)
    selidbe = SelidbaLog.objects.filter(pcelinjak__company=company)

    ctx = {
        'pcelinjaci_total': pcelinjaci.count(),
        'kosnice_total': kosnice.count(),
        'kosnice_aktivne': kosnice.filter(status='aktivna').count(),
        'kosnice_bolesne': kosnice.filter(status='bolesna').count(),
        'kosnice_uginule': kosnice.filter(status='uginula').count(),
        'tretmani_total': tretmani.count(),
        'tretmani_godina': tretmani.filter(datum__year=today.year).count(),
        'karencija_aktivna': tretmani.filter(karencija_do__gte=today).count(),
        'med_total_kg': med.aggregate(s=Sum('kolicina_kg'))['s'] or 0,
        'med_godina_kg': med.filter(datum_vrcanja__year=today.year).aggregate(s=Sum('kolicina_kg'))['s'] or 0,
        'selidbe_total': selidbe.count(),
    }
    return render(request, 'udruge/pcelari_dashboard.html', ctx)


@login_required
def pcelinjak_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Pcelinjak
    qs = Pcelinjak.objects.filter(company=company).select_related('vlasnik')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/pcelinjak_list.html', {'page_obj': page})


@login_required
def pcelinjak_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Pcelinjak, Clan
    if request.method == 'POST':
        Pcelinjak.objects.create(
            company=company,
            vlasnik_id=request.POST.get('vlasnik'),
            naziv=request.POST.get('naziv', ''),
            lokacija=request.POST.get('lokacija', ''),
            katastarska_cestica=request.POST.get('katastarska_cestica', ''),
            jrdz_broj=request.POST.get('jrdz_broj', ''),
            stacionarni=request.POST.get('stacionarni') != 'off',
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Pčelinjak dodan.')
        return redirect('udruge:pcelinjak_list')
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/pcelinjak_form.html', {'clanovi': clanovi})


@login_required
def pcelinjak_detail(request, pk):
    company = get_user_company(request)
    from .models import Pcelinjak
    obj = get_object_or_404(Pcelinjak, pk=pk, company=company)
    kosnice = obj.kosnice.all()
    return render(request, 'udruge/pcelinjak_detail.html', {'pcelinjak': obj, 'kosnice': kosnice})


@login_required
def kosnica_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Kosnica
    qs = Kosnica.objects.filter(pcelinjak__company=company).select_related('pcelinjak')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/kosnica_list.html', {
        'page_obj': page, 'status': status, 'statusi': Kosnica.STATUS_CHOICES,
    })


@login_required
def kosnica_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Kosnica, Pcelinjak
    if request.method == 'POST':
        Kosnica.objects.create(
            pcelinjak_id=request.POST.get('pcelinjak'),
            oznaka=request.POST.get('oznaka', ''),
            tip=request.POST.get('tip', 'lr'),
            status=request.POST.get('status', 'aktivna'),
            godina_matice=int(request.POST.get('godina_matice') or 0) or None,
            boja_matice=request.POST.get('boja_matice', ''),
            snaga_zajednice=int(request.POST.get('snaga_zajednice') or 0) or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Košnica dodana.')
        return redirect('udruge:kosnica_list')
    pcelinjaci = Pcelinjak.objects.filter(company=company)
    return render(request, 'udruge/kosnica_form.html', {
        'pcelinjaci': pcelinjaci, 'tipovi': Kosnica.TIP_CHOICES, 'statusi': Kosnica.STATUS_CHOICES,
    })


@login_required
def kosnica_detail(request, pk):
    company = get_user_company(request)
    from .models import Kosnica
    obj = get_object_or_404(Kosnica, pk=pk, pcelinjak__company=company)
    tretmani = obj.tretmani.all()[:10]
    return render(request, 'udruge/kosnica_detail.html', {'kosnica': obj, 'tretmani': tretmani})


@login_required
def tretman_kosnice_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import TretmanKosnice
    qs = TretmanKosnice.objects.filter(kosnica__pcelinjak__company=company).select_related('kosnica', 'kosnica__pcelinjak')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/tretman_kosnice_list.html', {'page_obj': page})


@login_required
def tretman_kosnice_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import TretmanKosnice, Kosnica
    if request.method == 'POST':
        TretmanKosnice.objects.create(
            kosnica_id=request.POST.get('kosnica'),
            datum=request.POST.get('datum'),
            tip=request.POST.get('tip', 'varroa'),
            lijek=request.POST.get('lijek', ''),
            doza=request.POST.get('doza', ''),
            veterinar=request.POST.get('veterinar', ''),
            karencija_do=request.POST.get('karencija_do') or None,
            rezultat=request.POST.get('rezultat', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Tretman evidentiran.')
        return redirect('udruge:tretman_kosnice_list')
    kosnice = Kosnica.objects.filter(pcelinjak__company=company).select_related('pcelinjak')
    return render(request, 'udruge/tretman_kosnice_form.html', {
        'kosnice': kosnice, 'tipovi': TretmanKosnice.TIP_CHOICES,
    })


@login_required
def tretman_kosnice_detail(request, pk):
    company = get_user_company(request)
    from .models import TretmanKosnice
    obj = get_object_or_404(TretmanKosnice, pk=pk, kosnica__pcelinjak__company=company)
    return render(request, 'udruge/tretman_kosnice_detail.html', {'tretman': obj})


@login_required
def med_proizvodnja_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import MedProizvodnja
    qs = MedProizvodnja.objects.filter(pcelinjak__company=company).select_related('pcelinjak')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/med_proizvodnja_list.html', {'page_obj': page})


@login_required
def med_proizvodnja_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import MedProizvodnja, Pcelinjak
    from decimal import Decimal
    if request.method == 'POST':
        MedProizvodnja.objects.create(
            pcelinjak_id=request.POST.get('pcelinjak'),
            datum_vrcanja=request.POST.get('datum_vrcanja'),
            vrsta=request.POST.get('vrsta', 'livada'),
            kolicina_kg=Decimal(request.POST.get('kolicina_kg') or '0'),
            vlaga_posto=Decimal(request.POST.get('vlaga_posto') or '0') or None,
            broj_kosnica_vrcano=int(request.POST.get('broj_kosnica_vrcano') or 0),
            za_prodaju=request.POST.get('za_prodaju') == 'on',
            cijena_eur_kg=Decimal(request.POST.get('cijena_eur_kg') or '0') or None,
            serija=request.POST.get('serija', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Proizvodnja meda evidentirana.')
        return redirect('udruge:med_proizvodnja_list')
    pcelinjaci = Pcelinjak.objects.filter(company=company)
    return render(request, 'udruge/med_proizvodnja_form.html', {
        'pcelinjaci': pcelinjaci, 'vrste': MedProizvodnja.VRSTA_CHOICES,
    })


@login_required
def med_proizvodnja_detail(request, pk):
    company = get_user_company(request)
    from .models import MedProizvodnja
    obj = get_object_or_404(MedProizvodnja, pk=pk, pcelinjak__company=company)
    return render(request, 'udruge/med_proizvodnja_detail.html', {'med': obj})


@login_required
def selidba_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import SelidbaLog
    qs = SelidbaLog.objects.filter(pcelinjak__company=company).select_related('pcelinjak')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/selidba_list.html', {'page_obj': page})


@login_required
def selidba_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import SelidbaLog, Pcelinjak
    if request.method == 'POST':
        SelidbaLog.objects.create(
            pcelinjak_id=request.POST.get('pcelinjak'),
            datum=request.POST.get('datum'),
            odrediste=request.POST.get('odrediste', ''),
            broj_kosnica=int(request.POST.get('broj_kosnica') or 0),
            razlog=request.POST.get('razlog', ''),
            prijavljeno_veterinaru=request.POST.get('prijavljeno_veterinaru') == 'on',
            vracanje_datum=request.POST.get('vracanje_datum') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Selidba evidentirana.')
        return redirect('udruge:selidba_list')
    pcelinjaci = Pcelinjak.objects.filter(company=company)
    return render(request, 'udruge/selidba_form.html', {'pcelinjaci': pcelinjaci})


@login_required
def selidba_detail(request, pk):
    company = get_user_company(request)
    from .models import SelidbaLog
    obj = get_object_or_404(SelidbaLog, pk=pk, pcelinjak__company=company)
    return render(request, 'udruge/selidba_detail.html', {'selidba': obj})


# ══════════════════════════════════════════════════════════════════════════════
# RAKIJA — DESTILACIJA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def rakija_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DestilacijaKotao, DestilacijaLog, RakijaProizvodnja, TrosarinaPrijava
    from django.db.models import Sum, Count

    today = timezone.now().date()
    kotlovi = DestilacijaKotao.objects.filter(company=company)
    destilacije = DestilacijaLog.objects.filter(kotao__company=company)
    rakije = RakijaProizvodnja.objects.filter(company=company)
    trosarine = TrosarinaPrijava.objects.filter(company=company)

    ctx = {
        'kotlovi_total': kotlovi.count(),
        'kotlovi_aktivni': kotlovi.filter(is_active=True).count(),
        'destilacije_total': destilacije.count(),
        'destilacije_godina': destilacije.filter(datum__year=today.year).count(),
        'destilacije_litara': destilacije.aggregate(s=Sum('litara_destilata'))['s'] or 0,
        'rakije_total': rakije.count(),
        'rakije_litara': rakije.aggregate(s=Sum('litara'))['s'] or 0,
        'rakije_za_prodaju': rakije.filter(za_prodaju=True).count(),
        'trosarine_total': trosarine.count(),
        'trosarina_zadnja': trosarine.first(),
    }
    return render(request, 'udruge/rakija_dashboard.html', ctx)


@login_required
def destilacija_kotao_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DestilacijaKotao
    qs = DestilacijaKotao.objects.filter(company=company).select_related('vlasnik')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/destilacija_kotao_list.html', {'page_obj': page})


@login_required
def destilacija_kotao_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DestilacijaKotao, Clan
    if request.method == 'POST':
        DestilacijaKotao.objects.create(
            company=company,
            vlasnik_id=request.POST.get('vlasnik') or None,
            registarski_broj=request.POST.get('registarski_broj', ''),
            volumen_litara=int(request.POST.get('volumen_litara') or 0),
            tip=request.POST.get('tip', ''),
            lokacija=request.POST.get('lokacija', ''),
            carinski_ured=request.POST.get('carinski_ured', ''),
            registriran_od=request.POST.get('registriran_od') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Kotao registriran.')
        return redirect('udruge:destilacija_kotao_list')
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/destilacija_kotao_form.html', {'clanovi': clanovi})


@login_required
def destilacija_kotao_detail(request, pk):
    company = get_user_company(request)
    from .models import DestilacijaKotao
    obj = get_object_or_404(DestilacijaKotao, pk=pk, company=company)
    destilacije = obj.destilacije.all()[:10]
    return render(request, 'udruge/destilacija_kotao_detail.html', {'kotao': obj, 'destilacije': destilacije})


@login_required
def destilacija_log_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DestilacijaLog
    qs = DestilacijaLog.objects.filter(kotao__company=company).select_related('kotao')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/destilacija_log_list.html', {'page_obj': page})


@login_required
def destilacija_log_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DestilacijaLog, DestilacijaKotao
    from decimal import Decimal
    if request.method == 'POST':
        DestilacijaLog.objects.create(
            kotao_id=request.POST.get('kotao'),
            datum=request.POST.get('datum'),
            sirovina=request.POST.get('sirovina', 'sljiva'),
            kg_sirovina=Decimal(request.POST.get('kg_sirovina') or '0'),
            litara_komine=Decimal(request.POST.get('litara_komine') or '0') or None,
            litara_destilata=Decimal(request.POST.get('litara_destilata') or '0'),
            alkohol_posto=Decimal(request.POST.get('alkohol_posto') or '0'),
            temperatura_c=Decimal(request.POST.get('temperatura_c') or '0') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Destilacija evidentirana.')
        return redirect('udruge:destilacija_log_list')
    kotlovi = DestilacijaKotao.objects.filter(company=company, is_active=True)
    return render(request, 'udruge/destilacija_log_form.html', {
        'kotlovi': kotlovi, 'sirovine': DestilacijaLog.SIROVINA_CHOICES,
    })


@login_required
def destilacija_log_detail(request, pk):
    company = get_user_company(request)
    from .models import DestilacijaLog
    obj = get_object_or_404(DestilacijaLog, pk=pk, kotao__company=company)
    return render(request, 'udruge/destilacija_log_detail.html', {'destilacija': obj})


@login_required
def rakija_proizvodnja_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import RakijaProizvodnja
    qs = RakijaProizvodnja.objects.filter(company=company)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/rakija_proizvodnja_list.html', {'page_obj': page})


@login_required
def rakija_proizvodnja_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import RakijaProizvodnja, DestilacijaLog
    from decimal import Decimal
    if request.method == 'POST':
        RakijaProizvodnja.objects.create(
            company=company,
            destilacija_id=request.POST.get('destilacija') or None,
            naziv=request.POST.get('naziv', ''),
            tip_rakije=request.POST.get('tip_rakije', ''),
            litara=Decimal(request.POST.get('litara') or '0'),
            alkohol_posto=Decimal(request.POST.get('alkohol_posto') or '40'),
            serija=request.POST.get('serija', ''),
            godina=int(request.POST.get('godina') or today.year),
            za_prodaju=request.POST.get('za_prodaju') == 'on',
            cijena_eur_l=Decimal(request.POST.get('cijena_eur_l') or '0') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Rakija evidentirana.')
        return redirect('udruge:rakija_proizvodnja_list')
    destilacije = DestilacijaLog.objects.filter(kotao__company=company)[:50]
    today = timezone.now().date()
    return render(request, 'udruge/rakija_proizvodnja_form.html', {'destilacije': destilacije})


@login_required
def rakija_proizvodnja_detail(request, pk):
    company = get_user_company(request)
    from .models import RakijaProizvodnja
    obj = get_object_or_404(RakijaProizvodnja, pk=pk, company=company)
    return render(request, 'udruge/rakija_proizvodnja_detail.html', {'rakija': obj})


@login_required
def trosarina_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import TrosarinaPrijava
    qs = TrosarinaPrijava.objects.filter(company=company)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/trosarina_list.html', {'page_obj': page})


@login_required
def trosarina_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import TrosarinaPrijava
    from decimal import Decimal
    if request.method == 'POST':
        TrosarinaPrijava.objects.create(
            company=company,
            godina=int(request.POST.get('godina') or timezone.now().year),
            ukupno_litara_destilata=Decimal(request.POST.get('ukupno_litara_destilata') or '0'),
            prosjecni_alkohol_posto=Decimal(request.POST.get('prosjecni_alkohol_posto') or '40'),
            ukupno_litara_cistog=Decimal(request.POST.get('ukupno_litara_cistog') or '0'),
            stopa_eur_hl=Decimal(request.POST.get('stopa_eur_hl') or '0'),
            status=request.POST.get('status', 'draft'),
            datum_prijave=request.POST.get('datum_prijave') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Trošarinska prijava kreirana.')
        return redirect('udruge:trosarina_list')
    return render(request, 'udruge/trosarina_form.html', {
        'statusi': TrosarinaPrijava.STATUS_CHOICES,
    })


@login_required
def trosarina_detail(request, pk):
    company = get_user_company(request)
    from .models import TrosarinaPrijava
    obj = get_object_or_404(TrosarinaPrijava, pk=pk, company=company)
    return render(request, 'udruge/trosarina_detail.html', {'trosarina': obj})


# ══════════════════════════════════════════════════════════════════════════════
# VOĆARI
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def vocari_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Vocnjak, BerbaLog, TretmanVocnjaka
    from django.db.models import Sum, Count

    today = timezone.now().date()
    vocnjaci = Vocnjak.objects.filter(company=company)
    berbe = BerbaLog.objects.filter(vocnjak__company=company)
    tretmani = TretmanVocnjaka.objects.filter(vocnjak__company=company)

    ctx = {
        'vocnjaci_total': vocnjaci.count(),
        'ukupno_stabala': vocnjaci.aggregate(s=Sum('broj_stabala'))['s'] or 0,
        'ukupno_ha': vocnjaci.aggregate(s=Sum('povrsina_ha'))['s'] or 0,
        'eko_vocnjaci': vocnjaci.filter(is_organic=True).count(),
        'berbe_total': berbe.count(),
        'berbe_godina': berbe.filter(datum__year=today.year).count(),
        'berbe_kg_godina': berbe.filter(datum__year=today.year).aggregate(s=Sum('kolicina_kg'))['s'] or 0,
        'berbe_kg_total': berbe.aggregate(s=Sum('kolicina_kg'))['s'] or 0,
        'tretmani_total': tretmani.count(),
        'tretmani_godina': tretmani.filter(datum__year=today.year).count(),
        'karencija_aktivna': tretmani.filter(karencija_do__gte=today).count(),
        'vrste': vocnjaci.values('vrsta').annotate(cnt=Count('id')).order_by('-cnt')[:10],
    }
    return render(request, 'udruge/vocari_dashboard.html', ctx)


@login_required
def vocnjak_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Vocnjak
    qs = Vocnjak.objects.filter(company=company).select_related('vlasnik')
    vrsta = request.GET.get('vrsta', '')
    if vrsta:
        qs = qs.filter(vrsta=vrsta)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/vocnjak_list.html', {
        'page_obj': page, 'vrsta': vrsta, 'vrste': Vocnjak.VRSTA_CHOICES,
    })


@login_required
def vocnjak_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Vocnjak, Clan
    from decimal import Decimal
    if request.method == 'POST':
        Vocnjak.objects.create(
            company=company,
            vlasnik_id=request.POST.get('vlasnik') or None,
            naziv=request.POST.get('naziv', ''),
            vrsta=request.POST.get('vrsta', 'jabuka'),
            sorta=request.POST.get('sorta', ''),
            podloga=request.POST.get('podloga', ''),
            sustav_uzgoja=request.POST.get('sustav_uzgoja', 'spalir'),
            broj_stabala=int(request.POST.get('broj_stabala') or 0),
            godina_sadnje=int(request.POST.get('godina_sadnje') or 0) or None,
            povrsina_ha=Decimal(request.POST.get('povrsina_ha') or '0') or None,
            is_organic=request.POST.get('is_organic') == 'on',
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Voćnjak dodan.')
        return redirect('udruge:vocnjak_list')
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/vocnjak_form.html', {
        'vrste': Vocnjak.VRSTA_CHOICES, 'sustavi': Vocnjak.SUSTAV_CHOICES, 'clanovi': clanovi,
    })


@login_required
def vocnjak_detail(request, pk):
    company = get_user_company(request)
    from .models import Vocnjak
    obj = get_object_or_404(Vocnjak, pk=pk, company=company)
    berbe = obj.berbe.all()[:10]
    tretmani = obj.tretmani.all()[:10]
    return render(request, 'udruge/vocnjak_detail.html', {
        'vocnjak': obj, 'berbe': berbe, 'tretmani': tretmani,
    })


@login_required
def berba_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import BerbaLog
    qs = BerbaLog.objects.filter(vocnjak__company=company).select_related('vocnjak')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/berba_list.html', {'page_obj': page})


@login_required
def berba_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import BerbaLog, Vocnjak
    from decimal import Decimal
    if request.method == 'POST':
        BerbaLog.objects.create(
            vocnjak_id=request.POST.get('vocnjak'),
            datum=request.POST.get('datum'),
            kolicina_kg=Decimal(request.POST.get('kolicina_kg') or '0'),
            kvaliteta=request.POST.get('kvaliteta', 'I'),
            broj_radnika=int(request.POST.get('broj_radnika') or 1),
            sati_berbe=Decimal(request.POST.get('sati_berbe') or '0'),
            za_prodaju=request.POST.get('za_prodaju') == 'on',
            za_preradu=request.POST.get('za_preradu') == 'on',
            cijena_eur_kg=Decimal(request.POST.get('cijena_eur_kg') or '0') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Berba evidentirana.')
        return redirect('udruge:berba_list')
    vocnjaci = Vocnjak.objects.filter(company=company)
    return render(request, 'udruge/berba_form.html', {'vocnjaci': vocnjaci})


@login_required
def berba_detail(request, pk):
    company = get_user_company(request)
    from .models import BerbaLog
    obj = get_object_or_404(BerbaLog, pk=pk, vocnjak__company=company)
    return render(request, 'udruge/berba_detail.html', {'berba': obj})


@login_required
def tretman_vocnjaka_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import TretmanVocnjaka
    qs = TretmanVocnjaka.objects.filter(vocnjak__company=company).select_related('vocnjak')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/tretman_vocnjaka_list.html', {'page_obj': page})


@login_required
def tretman_vocnjaka_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import TretmanVocnjaka, Vocnjak
    if request.method == 'POST':
        TretmanVocnjaka.objects.create(
            vocnjak_id=request.POST.get('vocnjak'),
            datum=request.POST.get('datum'),
            tip=request.POST.get('tip', 'fungicid'),
            sredstvo=request.POST.get('sredstvo', ''),
            doza=request.POST.get('doza', ''),
            kolicina_ukupno=request.POST.get('kolicina_ukupno', ''),
            karencija_dana=int(request.POST.get('karencija_dana') or 0),
            karencija_do=request.POST.get('karencija_do') or None,
            tretirao=request.POST.get('tretirao', ''),
            vremenske_prilike=request.POST.get('vremenske_prilike', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Tretman evidentiran.')
        return redirect('udruge:tretman_vocnjaka_list')
    vocnjaci = Vocnjak.objects.filter(company=company)
    return render(request, 'udruge/tretman_vocnjaka_form.html', {
        'vocnjaci': vocnjaci, 'tipovi': TretmanVocnjaka.TIP_CHOICES,
    })


@login_required
def tretman_vocnjaka_detail(request, pk):
    company = get_user_company(request)
    from .models import TretmanVocnjaka
    obj = get_object_or_404(TretmanVocnjaka, pk=pk, vocnjak__company=company)
    return render(request, 'udruge/tretman_vocnjaka_detail.html', {'tretman': obj})


# ══════════════════════════════════════════════════════════════════════════════
# EDIT VIEWS — DVD oprema, intervencije, KUD kostimi
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def vatrogasna_oprema_edit(request, pk):
    company = get_user_company(request)
    from .models import VatrogasnaOprema
    from decimal import Decimal
    obj = get_object_or_404(VatrogasnaOprema, pk=pk, company=company)
    if request.method == 'POST':
        obj.naziv = request.POST.get('naziv', obj.naziv)
        obj.kategorija = request.POST.get('kategorija', obj.kategorija)
        obj.serijski_broj = request.POST.get('serijski_broj', obj.serijski_broj)
        obj.proizvodac = request.POST.get('proizvodac', obj.proizvodac)
        obj.godina_nabave = int(request.POST.get('godina_nabave') or 0) or obj.godina_nabave
        obj.nabavna_vrijednost = Decimal(request.POST.get('nabavna_vrijednost') or '0')
        obj.status = request.POST.get('status', obj.status)
        obj.atest_datum = request.POST.get('atest_datum') or obj.atest_datum
        obj.atest_vrijedi_do = request.POST.get('atest_vrijedi_do') or obj.atest_vrijedi_do
        obj.atest_izdavac = request.POST.get('atest_izdavac', obj.atest_izdavac)
        obj.sljedeci_servis = request.POST.get('sljedeci_servis') or obj.sljedeci_servis
        obj.lokacija = request.POST.get('lokacija', obj.lokacija)
        obj.notes = request.POST.get('notes', obj.notes)
        if request.FILES.get('photo'):
            obj.photo = request.FILES['photo']
        obj.save()
        messages.success(request, 'Oprema azurirana.')
        return redirect('udruge:vatrogasna_oprema_list')
    return render(request, 'udruge/vatrogasna_oprema_form.html', {
        'oprema': obj, 'edit': True,
        'kategorije': VatrogasnaOprema.KATEGORIJA_CHOICES,
        'statusi': VatrogasnaOprema.STATUS_CHOICES,
    })


@login_required
def intervencija_edit(request, pk):
    company = get_user_company(request)
    from .models import Intervencija, Clan
    obj = get_object_or_404(Intervencija, pk=pk, company=company)
    if request.method == 'POST':
        obj.evidencijski_broj = request.POST.get('evidencijski_broj', obj.evidencijski_broj)
        obj.tip = request.POST.get('tip', obj.tip)
        obj.opis = request.POST.get('opis', obj.opis)
        obj.alarm_primljen = request.POST.get('alarm_primljen') or obj.alarm_primljen
        obj.izlazak = request.POST.get('izlazak') or obj.izlazak
        obj.dolazak = request.POST.get('dolazak') or obj.dolazak
        obj.zavrsetak = request.POST.get('zavrsetak') or obj.zavrsetak
        obj.povratak = request.POST.get('povratak') or obj.povratak
        obj.lokacija = request.POST.get('lokacija', obj.lokacija)
        voditelj_id = request.POST.get('voditelj') or None
        obj.voditelj_id = voditelj_id
        obj.broj_sudionika = int(request.POST.get('broj_sudionika') or 0)
        obj.voda_utrosena_l = int(request.POST.get('voda_utrosena_l') or 0)
        obj.pjena_utrosena_l = int(request.POST.get('pjena_utrosena_l') or 0)
        obj.steta_eur = request.POST.get('steta_eur') or 0
        obj.spaseno_osoba = int(request.POST.get('spaseno_osoba') or 0)
        obj.spaseno_zivotinja = int(request.POST.get('spaseno_zivotinja') or 0)
        obj.notes = request.POST.get('notes', obj.notes)
        obj.save()
        messages.success(request, 'Intervencija azurirana.')
        return redirect('udruge:intervencija_detail', pk=obj.pk)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/intervencija_form.html', {
        'intervencija': obj, 'edit': True,
        'tipovi': Intervencija.TIP_CHOICES, 'clanovi': clanovi,
    })


@login_required
def kostim_edit(request, pk):
    company = get_user_company(request)
    from .models import Kostim, Sekcija, Clan
    from decimal import Decimal
    obj = get_object_or_404(Kostim, pk=pk, company=company)
    if request.method == 'POST':
        obj.naziv = request.POST.get('naziv', obj.naziv)
        obj.sekcija_id = request.POST.get('sekcija') or obj.sekcija_id
        obj.region = request.POST.get('region', obj.region)
        obj.spol = request.POST.get('spol', obj.spol)
        obj.velicina = request.POST.get('velicina', obj.velicina)
        obj.inventarni_broj = request.POST.get('inventarni_broj', obj.inventarni_broj)
        obj.dodijeljen_clanu_id = request.POST.get('dodijeljen_clanu') or obj.dodijeljen_clanu_id
        obj.dodijeljen_od = request.POST.get('dodijeljen_od') or obj.dodijeljen_od
        obj.stanje = request.POST.get('stanje', obj.stanje)
        obj.nabavna_cijena = Decimal(request.POST.get('nabavna_cijena') or '0')
        obj.opis_dijelova = request.POST.get('opis_dijelova', obj.opis_dijelova)
        obj.notes = request.POST.get('notes', obj.notes)
        if request.FILES.get('photo'):
            obj.photo = request.FILES['photo']
        obj.save()
        messages.success(request, 'Kostim azuriran.')
        return redirect('udruge:kostim_list')
    sekcije = Sekcija.objects.filter(company=company)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/kostim_form.html', {
        'kostim': obj, 'edit': True,
        'stanja': Kostim.STANJE_CHOICES, 'sekcije': sekcije, 'clanovi': clanovi,
    })


# ═══════════════════════════════════════════════════════════════════
# BRANITELJI — udruge branitelja
# ═══════════════════════════════════════════════════════════════════

@login_required
def branitelji_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import StatusBranitelja
    qs = StatusBranitelja.objects.filter(clan__company=company).select_related('clan')
    stats = {
        'ukupno': qs.count(),
        'hrvi': qs.filter(vrsta_statusa__startswith='hrvi_').count(),
        'dragovoljci': qs.filter(vrsta_statusa='dragovoljac').count(),
        'borbeni_sektor': qs.filter(borbeni_sektor=True).count(),
        's_odlikovanjem': qs.filter(clan__odlikovanja_bran__isnull=False).distinct().count(),
    }
    vrsta_f = request.GET.get('vrsta', '')
    if vrsta_f:
        qs = qs.filter(vrsta_statusa=vrsta_f)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/branitelji_dashboard.html', {
        'page_obj': page, 'stats': stats, 'vrsta_f': vrsta_f,
        'vrsta_choices': StatusBranitelja.VRSTA_STATUSA,
    })


@login_required
def branitelj_status_create(request, clan_pk):
    company = get_user_company(request)
    from .models import Clan, StatusBranitelja
    clan = get_object_or_404(Clan, pk=clan_pk, company=company)
    if hasattr(clan, 'status_branitelja'):
        messages.info(request, 'Član već ima status branitelja.')
        return redirect('udruge:branitelji_dashboard')
    if request.method == 'POST':
        d = request.POST
        StatusBranitelja.objects.create(
            clan=clan,
            vrsta_statusa=d.get('vrsta_statusa', 'branitelj'),
            postrojba=d.get('postrojba', ''),
            naziv_postrojbe=d.get('naziv_postrojbe', ''),
            od_datuma=d.get('od_datuma') or None,
            do_datuma=d.get('do_datuma') or None,
            dana_sudjelovanja=int(d.get('dana_sudjelovanja') or 0),
            borbeni_sektor='borbeni_sektor' in d,
            broj_potvrde_ministarstva=d.get('broj_potvrde_ministarstva', ''),
            datum_potvrde=d.get('datum_potvrde') or None,
            postotak_invalidnosti=int(d.get('postotak_invalidnosti') or 0) or None,
            odlikovanja=d.get('odlikovanja', ''),
            napomena=d.get('napomena', ''),
        )
        messages.success(request, 'Status branitelja dodan za %s.' % clan)
        return redirect('udruge:branitelji_dashboard')
    return render(request, 'udruge/branitelj_status_form.html', {
        'clan': clan,
        'vrsta_choices': StatusBranitelja.VRSTA_STATUSA,
        'postrojba_choices': StatusBranitelja.POSTROJBA_CHOICES,
    })


# ═══════════════════════════════════════════════════════════════════
# LOV — lovačka društva
# ═══════════════════════════════════════════════════════════════════

@login_required
def lov_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import LovackaIskaznica, ZapisnikLova, Trofej, Loviste
    iskaznice = LovackaIskaznica.objects.filter(company=company)
    stats = {
        'lovaca': iskaznice.count(),
        'aktivne_iskaznice': sum(1 for i in iskaznice if i.je_aktivna),
        'treba_markicu': sum(1 for i in iskaznice if i.treba_markicu),
        'odstrjel_ukupno': ZapisnikLova.objects.filter(company=company).count(),
        'trofeji_medalja': Trofej.objects.filter(company=company).exclude(medalja='').count(),
        'lovista': Loviste.objects.filter(company=company, is_active=True).count(),
    }
    zapisnici = ZapisnikLova.objects.filter(company=company).select_related('clan', 'loviste')[:10]
    return render(request, 'udruge/lov_dashboard.html', {'stats': stats, 'zapisnici': zapisnici})


@login_required
def lov_iskaznice_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import LovackaIskaznica
    qs = LovackaIskaznica.objects.filter(company=company).select_related('clan')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/lov_iskaznice_list.html', {'page_obj': page})


@login_required
def lov_dopustenja_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DopustenjeLova
    qs = DopustenjeLova.objects.filter(company=company).select_related('clan', 'loviste')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/lov_dopustenja_list.html', {'page_obj': page})


@login_required
def lov_dopustenje_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import DopustenjeLova, Loviste, Clan
    if request.method == 'POST':
        DopustenjeLova.objects.create(
            company=company,
            loviste_id=request.POST.get('loviste'),
            clan_id=request.POST.get('clan'),
            broj_dopustenja=request.POST.get('broj_dopustenja', ''),
            datum_lova=request.POST.get('datum_lova'),
            vrsta_divljaci=request.POST.get('vrsta_divljaci', ''),
            broj_komada=int(request.POST.get('broj_komada') or 1),
            sle_evidencija_br=request.POST.get('sle_evidencija_br', ''),
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Dopuštenje kreirano.')
        return redirect('udruge:lov_dopustenja_list')
    lovista = Loviste.objects.filter(company=company, is_active=True)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/lov_dopustenje_form.html', {'lovista': lovista, 'clanovi': clanovi})


@login_required
def lov_zapisnici_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ZapisnikLova
    qs = ZapisnikLova.objects.filter(company=company).select_related('clan', 'loviste')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/lov_zapisnici_list.html', {'page_obj': page})


@login_required
def lov_zapisnik_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ZapisnikLova, Loviste, Clan
    if request.method == 'POST':
        ZapisnikLova.objects.create(
            company=company,
            loviste_id=request.POST.get('loviste'),
            clan_id=request.POST.get('clan'),
            dopustenje_id=request.POST.get('dopustenje') or None,
            datum=request.POST.get('datum'),
            nacin_lova=request.POST.get('nacin_lova', 'pojedinacni'),
            vrsta_divljaci=request.POST.get('vrsta_divljaci', ''),
            spol=request.POST.get('spol', ''),
            masa_kg=request.POST.get('masa_kg') or None,
            lokalitet=request.POST.get('lokalitet', ''),
            sle_broj=request.POST.get('sle_broj', ''),
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Zapisnik kreiran.')
        return redirect('udruge:lov_zapisnici_list')
    from .models import DopustenjeLova
    lovista = Loviste.objects.filter(company=company, is_active=True)
    clanovi = Clan.objects.filter(company=company)
    dopustenja = DopustenjeLova.objects.filter(company=company).order_by('-datum_lova')[:20]
    return render(request, 'udruge/lov_zapisnik_form.html', {
        'lovista': lovista, 'clanovi': clanovi, 'dopustenja': dopustenja,
        'nacin_choices': ZapisnikLova.NACIN_LOVA,
    })


@login_required
def lov_trofeji_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Trofej
    qs = Trofej.objects.filter(company=company).select_related('clan', 'zapisnik')
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/lov_trofeji_list.html', {'page_obj': page})


# ═══════════════════════════════════════════════════════════════════
# EDIT VIEWS — Branitelji, Lov
# ═══════════════════════════════════════════════════════════════════

@login_required
def branitelj_status_edit(request, pk):
    company = get_user_company(request)
    from .models import StatusBranitelja
    obj = get_object_or_404(StatusBranitelja, pk=pk, clan__company=company)
    if request.method == 'POST':
        d = request.POST
        obj.vrsta_statusa = d.get('vrsta_statusa', obj.vrsta_statusa)
        obj.postrojba = d.get('postrojba', obj.postrojba)
        obj.naziv_postrojbe = d.get('naziv_postrojbe', obj.naziv_postrojbe)
        obj.od_datuma = d.get('od_datuma') or obj.od_datuma
        obj.do_datuma = d.get('do_datuma') or obj.do_datuma
        obj.dana_sudjelovanja = int(d.get('dana_sudjelovanja') or 0)
        obj.borbeni_sektor = 'borbeni_sektor' in d
        obj.broj_potvrde_ministarstva = d.get('broj_potvrde_ministarstva', obj.broj_potvrde_ministarstva)
        obj.datum_potvrde = d.get('datum_potvrde') or obj.datum_potvrde
        obj.postotak_invalidnosti = int(d.get('postotak_invalidnosti') or 0) or None
        obj.odlikovanja = d.get('odlikovanja', obj.odlikovanja)
        obj.napomena = d.get('napomena', obj.napomena)
        obj.save()
        messages.success(request, 'Status branitelja ažuriran.')
        return redirect('udruge:branitelji_dashboard')
    return render(request, 'udruge/branitelj_status_form.html', {
        'clan': obj.clan, 'obj': obj, 'edit': True,
        'vrsta_choices': StatusBranitelja.VRSTA_STATUSA,
        'postrojba_choices': StatusBranitelja.POSTROJBA_CHOICES,
    })


@login_required
def lov_dopustenje_edit(request, pk):
    company = get_user_company(request)
    from .models import DopustenjeLova, Loviste, Clan
    obj = get_object_or_404(DopustenjeLova, pk=pk, company=company)
    if request.method == 'POST':
        obj.loviste_id = request.POST.get('loviste', obj.loviste_id)
        obj.clan_id = request.POST.get('clan', obj.clan_id)
        obj.broj_dopustenja = request.POST.get('broj_dopustenja', obj.broj_dopustenja)
        obj.datum_lova = request.POST.get('datum_lova') or obj.datum_lova
        obj.vrsta_divljaci = request.POST.get('vrsta_divljaci', obj.vrsta_divljaci)
        obj.broj_komada = int(request.POST.get('broj_komada') or 1)
        obj.sle_evidencija_br = request.POST.get('sle_evidencija_br', obj.sle_evidencija_br)
        obj.napomena = request.POST.get('napomena', obj.napomena)
        obj.save()
        messages.success(request, 'Dopuštenje ažurirano.')
        return redirect('udruge:lov_dopustenja_list')
    lovista = Loviste.objects.filter(company=company, is_active=True)
    clanovi = Clan.objects.filter(company=company)
    return render(request, 'udruge/lov_dopustenje_form.html', {
        'obj': obj, 'edit': True, 'lovista': lovista, 'clanovi': clanovi,
    })


@login_required
def lov_zapisnik_edit(request, pk):
    company = get_user_company(request)
    from .models import ZapisnikLova, Loviste, Clan, DopustenjeLova
    obj = get_object_or_404(ZapisnikLova, pk=pk, company=company)
    if request.method == 'POST':
        obj.loviste_id = request.POST.get('loviste', obj.loviste_id)
        obj.clan_id = request.POST.get('clan', obj.clan_id)
        obj.dopustenje_id = request.POST.get('dopustenje') or obj.dopustenje_id
        obj.datum = request.POST.get('datum') or obj.datum
        obj.nacin_lova = request.POST.get('nacin_lova', obj.nacin_lova)
        obj.vrsta_divljaci = request.POST.get('vrsta_divljaci', obj.vrsta_divljaci)
        obj.spol = request.POST.get('spol', obj.spol)
        obj.masa_kg = request.POST.get('masa_kg') or obj.masa_kg
        obj.lokalitet = request.POST.get('lokalitet', obj.lokalitet)
        obj.sle_broj = request.POST.get('sle_broj', obj.sle_broj)
        obj.napomena = request.POST.get('napomena', obj.napomena)
        obj.save()
        messages.success(request, 'Zapisnik ažuriran.')
        return redirect('udruge:lov_zapisnici_list')
    lovista = Loviste.objects.filter(company=company, is_active=True)
    clanovi = Clan.objects.filter(company=company)
    dopustenja = DopustenjeLova.objects.filter(company=company).order_by('-datum_lova')[:20]
    return render(request, 'udruge/lov_zapisnik_form.html', {
        'obj': obj, 'edit': True, 'lovista': lovista, 'clanovi': clanovi,
        'dopustenja': dopustenja, 'nacin_choices': ZapisnikLova.NACIN_LOVA,
    })


@login_required
def loviste_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Loviste
    qs = Loviste.objects.filter(company=company)
    return render(request, 'udruge/loviste_list.html', {'lovista': qs})


@login_required
def loviste_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Loviste
    from decimal import Decimal
    if request.method == 'POST':
        Loviste.objects.create(
            company=company,
            naziv=request.POST.get('naziv', ''),
            broj_lovista=request.POST.get('broj_lovista', ''),
            povrsina_ha=Decimal(request.POST.get('povrsina_ha') or '0'),
            vrsta=request.POST.get('vrsta', 'zajednicko'),
            lovoovlastenik=request.POST.get('lovoovlastenik', ''),
            zakup_od=request.POST.get('zakup_od') or None,
            zakup_do=request.POST.get('zakup_do') or None,
            opis_granica=request.POST.get('opis_granica', ''),
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Lovište dodano.')
        return redirect('udruge:loviste_list')
    return render(request, 'udruge/loviste_form.html', {
        'vrsta_choices': [('zajednicko','Zajedničko'),('privatno','Privatno'),('uzgajaliste','Uzgajalište')],
    })


@login_required
def loviste_edit(request, pk):
    company = get_user_company(request)
    from .models import Loviste
    from decimal import Decimal
    obj = get_object_or_404(Loviste, pk=pk, company=company)
    if request.method == 'POST':
        obj.naziv = request.POST.get('naziv', obj.naziv)
        obj.broj_lovista = request.POST.get('broj_lovista', obj.broj_lovista)
        obj.povrsina_ha = Decimal(request.POST.get('povrsina_ha') or '0')
        obj.vrsta = request.POST.get('vrsta', obj.vrsta)
        obj.lovoovlastenik = request.POST.get('lovoovlastenik', obj.lovoovlastenik)
        obj.zakup_od = request.POST.get('zakup_od') or obj.zakup_od
        obj.zakup_do = request.POST.get('zakup_do') or obj.zakup_do
        obj.opis_granica = request.POST.get('opis_granica', obj.opis_granica)
        obj.napomena = request.POST.get('napomena', obj.napomena)
        obj.save()
        messages.success(request, 'Lovište ažurirano.')
        return redirect('udruge:loviste_list')
    return render(request, 'udruge/loviste_form.html', {
        'obj': obj, 'edit': True,
        'vrsta_choices': [('zajednicko','Zajedničko'),('privatno','Privatno'),('uzgajaliste','Uzgajalište')],
    })


@login_required
def trofej_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Trofej, Clan, ZapisnikLova
    from decimal import Decimal
    if request.method == 'POST':
        Trofej.objects.create(
            company=company,
            clan_id=request.POST.get('clan'),
            zapisnik_id=request.POST.get('zapisnik') or None,
            vrsta=request.POST.get('vrsta', 'ostalo'),
            rok_lista=Decimal(request.POST.get('rok_lista') or '0') or None,
            teza_kg=Decimal(request.POST.get('teza_kg') or '0') or None,
            cis_tockova=Decimal(request.POST.get('cis_tockova') or '0') or None,
            medalja=request.POST.get('medalja', ''),
            datum_vrjednovanja=request.POST.get('datum_vrjednovanja') or None,
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Trofej dodan.')
        return redirect('udruge:lov_trofeji_list')
    clanovi = Clan.objects.filter(company=company)
    zapisnici = ZapisnikLova.objects.filter(company=company).order_by('-datum')[:30]
    return render(request, 'udruge/trofej_form.html', {
        'clanovi': clanovi, 'zapisnici': zapisnici,
        'vrsta_choices': Trofej.VRSTA_TROFEJA,
        'medalja_choices': [('','Bez medalje'),('zlato','Zlato'),('srebro','Srebro'),('bronca','Bronca')],
    })


# ═══════════════════════════════════════════════════════════════════
# ZADRUGE
# ═══════════════════════════════════════════════════════════════════

@login_required
def zadruge_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Zadrugar, ZadruznRevizija
    from django.db.models import Sum
    zadrugari = Zadrugar.objects.filter(company=company, status='aktivan')
    ukupni_ulozi = zadrugari.aggregate(s=Sum('clanski_ulog_eur'))['s'] or 0
    zadnja_revizija = ZadruznRevizija.objects.filter(company=company).first()
    stats = {
        'ukupno': zadrugari.count(),
        'osnivaci': zadrugari.filter(uloga='osnivac').count(),
        'ukupni_ulozi': ukupni_ulozi,
        'revizija': zadnja_revizija,
    }
    return render(request, 'udruge/zadruge_dashboard.html', {
        'zadrugari': zadrugari.order_by('-udjeli_postotak'),
        'stats': stats,
    })


@login_required
def zadrugar_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Zadrugar
    from decimal import Decimal
    if request.method == 'POST':
        Zadrugar.objects.create(
            company=company,
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            oib=request.POST.get('oib', ''),
            adresa=request.POST.get('adresa', ''),
            datum_pristupanja=request.POST.get('datum_pristupanja'),
            uloga=request.POST.get('uloga', 'redovni'),
            clanski_ulog_eur=Decimal(request.POST.get('clanski_ulog_eur') or '0'),
            udjeli_postotak=Decimal(request.POST.get('udjeli_postotak') or '0'),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Zadrugar dodan.')
        return redirect('udruge:zadruge_dashboard')
    return render(request, 'udruge/zadrugar_form.html', {
        'uloga_choices': Zadrugar.ULOGA_CHOICES,
    })


@login_required
def revizija_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ZadruznRevizija
    if request.method == 'POST':
        ZadruznRevizija.objects.create(
            company=company,
            godina=int(request.POST.get('godina') or timezone.now().year),
            revizor_ime=request.POST.get('revizor_ime', ''),
            revizor_firma=request.POST.get('revizor_firma', ''),
            datum_pocetak=request.POST.get('datum_pocetak'),
            datum_zavrsetak=request.POST.get('datum_zavrsetak') or None,
            nalaz=request.POST.get('nalaz', ''),
            ocjena=request.POST.get('ocjena', ''),
        )
        messages.success(request, 'Revizija evidentirana.')
        return redirect('udruge:zadruge_dashboard')
    return render(request, 'udruge/revizija_form.html', {
        'ocjena_choices': [('uredna','Uredna'),('napomene','S napomenama'),('neuredna','Neuredna')],
    })


# ══════════════════════════════════════════════════════════════════════════════
# GOLUBAR MODUL
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def golubar_dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golubinjak, Golub, ParGolubova, Utrka, ZdravstveniZapisGolub
    stats = {
        'golubinjaka': Golubinjak.objects.filter(company=company).count(),
        'golubova': Golub.objects.filter(company=company).count(),
        'aktivnih': Golub.objects.filter(company=company, aktivan=True).count(),
        'parova': ParGolubova.objects.filter(company=company).count(),
        'utrka': Utrka.objects.filter(company=company).count(),
        'zdravstvenih_zapisa': ZdravstveniZapisGolub.objects.filter(golub__company=company).count(),
    }
    utrke = Utrka.objects.filter(company=company)[:10]
    return render(request, 'udruge/golubar_dashboard.html', {'stats': stats, 'utrke': utrke})


@login_required
def golubinjak_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golubinjak
    qs = Golubinjak.objects.filter(company=company)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/golubar_golubinjak_list.html', {'page_obj': page})


@login_required
def golubinjak_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golubinjak
    from decimal import Decimal
    if request.method == 'POST':
        g = Golubinjak.objects.create(
            company=company,
            naziv=request.POST.get('naziv', ''),
            adresa=request.POST.get('adresa', ''),
            gps_lat=Decimal(request.POST.get('gps_lat')) if request.POST.get('gps_lat') else None,
            gps_lng=Decimal(request.POST.get('gps_lng')) if request.POST.get('gps_lng') else None,
            eu_reg_broj=request.POST.get('eu_reg_broj', ''),
            kapacitet=int(request.POST.get('kapacitet') or 0),
            napomena=request.POST.get('napomena', ''),
            aktivan='aktivan' in request.POST,
        )
        if request.FILES.get('fotografija'):
            g.fotografija = request.FILES['fotografija']
            g.save(update_fields=['fotografija'])
        messages.success(request, 'Golubinjak kreiran.')
        return redirect('udruge:golubinjak_detail', pk=g.pk)
    return render(request, 'udruge/golubar_golubinjak_form.html', {})


@login_required
def golubinjak_detail(request, pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golubinjak
    golubinjak = get_object_or_404(Golubinjak, pk=pk, company=company)
    golubovi = golubinjak.golubovi.all()
    return render(request, 'udruge/golubar_golubinjak_detail.html', {
        'golubinjak': golubinjak, 'golubovi': golubovi,
    })


@login_required
def golub_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golub
    qs = Golub.objects.filter(company=company).select_related('golubinjak')
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(Q(prsten_broj__icontains=q) | Q(naziv__icontains=q))
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/golubar_golub_list.html', {'page_obj': page, 'q': q})


@login_required
def golub_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golub, Golubinjak
    if request.method == 'POST':
        golub = Golub.objects.create(
            company=company,
            golubinjak_id=request.POST.get('golubinjak') or None,
            prsten_broj=request.POST.get('prsten_broj', ''),
            naziv=request.POST.get('naziv', ''),
            spol=request.POST.get('spol', '?'),
            boja=request.POST.get('boja', 'ostalo'),
            datum_izlijeganja=request.POST.get('datum_izlijeganja') or None,
            otac_id=request.POST.get('otac') or None,
            majka_id=request.POST.get('majka') or None,
            napomena=request.POST.get('napomena', ''),
        )
        if request.FILES.get('fotografija'):
            golub.fotografija = request.FILES['fotografija']
            golub.save()
        messages.success(request, 'Golub %s kreiran.' % golub.prsten_broj)
        return redirect('udruge:golub_detail', pk=golub.pk)
    golubinjaci = Golubinjak.objects.filter(company=company)
    golubovi = Golub.objects.filter(company=company)
    return render(request, 'udruge/golubar_golub_form.html', {
        'golubinjaci': golubinjaci,
        'muzjaci': golubovi.filter(spol='M'),
        'zenke': golubovi.filter(spol='F'),
        'spol_choices': Golub.SPOL,
        'boja_choices': Golub.BOJA,
    })


@login_required
def golub_detail(request, pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golub
    golub = get_object_or_404(Golub, pk=pk, company=company)
    # Rodovnik: otac/majka + djedovi/bake
    rodovnik = {
        'otac': golub.otac,
        'majka': golub.majka,
        'djed_oc': golub.otac.otac if golub.otac else None,
        'baka_oc': golub.otac.majka if golub.otac else None,
        'djed_maj': golub.majka.otac if golub.majka else None,
        'baka_maj': golub.majka.majka if golub.majka else None,
    }
    zdravstveni_zapisi = golub.zdravstveni_zapisi.all()
    rezultati_utrka = golub.rezultati_utrka.select_related('utrka').all()
    return render(request, 'udruge/golubar_golub_detail.html', {
        'golub': golub,
        'rodovnik': rodovnik,
        'zdravstveni_zapisi': zdravstveni_zapisi,
        'rezultati_utrka': rezultati_utrka,
    })


@login_required
def golub_edit(request, pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golub, Golubinjak
    golub = get_object_or_404(Golub, pk=pk, company=company)
    if request.method == 'POST':
        golub.golubinjak_id = request.POST.get('golubinjak') or None
        golub.prsten_broj = request.POST.get('prsten_broj', golub.prsten_broj)
        golub.naziv = request.POST.get('naziv', '')
        golub.spol = request.POST.get('spol', '?')
        golub.boja = request.POST.get('boja', 'ostalo')
        golub.datum_izlijeganja = request.POST.get('datum_izlijeganja') or None
        golub.otac_id = request.POST.get('otac') or None
        golub.majka_id = request.POST.get('majka') or None
        golub.napomena = request.POST.get('napomena', '')
        if request.FILES.get('fotografija'):
            golub.fotografija = request.FILES['fotografija']
        golub.save()
        messages.success(request, 'Golub %s azuriran.' % golub.prsten_broj)
        return redirect('udruge:golub_detail', pk=golub.pk)
    golubinjaci = Golubinjak.objects.filter(company=company)
    golubovi = Golub.objects.filter(company=company).exclude(pk=golub.pk)
    return render(request, 'udruge/golubar_golub_form.html', {
        'golub': golub,
        'golubinjaci': golubinjaci,
        'muzjaci': golubovi.filter(spol='M'),
        'zenke': golubovi.filter(spol='F'),
        'spol_choices': Golub.SPOL,
        'boja_choices': Golub.BOJA,
    })


@login_required
def par_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ParGolubova
    from django.db.models import Count
    qs = ParGolubova.objects.filter(company=company).select_related('muzjak', 'zenka').annotate(
        legla_count=Count('legla'),
    )
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/golubar_par_list.html', {'page_obj': page})


@login_required
def par_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ParGolubova, Golub, Golubinjak
    if request.method == 'POST':
        par = ParGolubova.objects.create(
            company=company,
            golubinjak_id=request.POST.get('golubinjak') or Golub.objects.filter(
                pk=request.POST.get('muzjak')).values_list('golubinjak_id', flat=True).first(),
            muzjak_id=request.POST.get('muzjak'),
            zenka_id=request.POST.get('zenka'),
            sezona=int(request.POST.get('sezona') or timezone.now().year),
            datum_spajanja=request.POST.get('datum_spajanja') or None,
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Par kreiran.')
        return redirect('udruge:par_list')
    muzjaci = Golub.objects.filter(company=company, spol='M', aktivan=True)
    zenke = Golub.objects.filter(company=company, spol='F', aktivan=True)
    return render(request, 'udruge/golubar_par_form.html', {
        'muzjaci': muzjaci,
        'zenke': zenke,
        'current_year': timezone.now().year,
    })


@login_required
def leglo_create(request, par_pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import ParGolubova, Leglo, Golub
    par = get_object_or_404(ParGolubova, pk=par_pk, company=company)
    if request.method == 'POST':
        Leglo.objects.create(
            par=par,
            datum_jaja=request.POST.get('datum_jaja') or None,
            datum_izlijeganja_1=request.POST.get('datum_izlijeganja_1') or None,
            datum_izlijeganja_2=request.POST.get('datum_izlijeganja_2') or None,
            ptic_1_id=request.POST.get('ptic_1') or None,
            ptic_2_id=request.POST.get('ptic_2') or None,
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Leglo evidentirano.')
        return redirect('udruge:par_list')
    golubovi = Golub.objects.filter(company=company)
    return render(request, 'udruge/golubar_leglo_form.html', {
        'par': par, 'golubovi': golubovi,
    })


@login_required
def zdravstveni_create(request, golub_pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golub, ZdravstveniZapisGolub
    golub = get_object_or_404(Golub, pk=golub_pk, company=company)
    if request.method == 'POST':
        ZdravstveniZapisGolub.objects.create(
            golub=golub,
            vrsta=request.POST.get('vrsta', 'ostalo'),
            datum=request.POST.get('datum'),
            lijek_preparat=request.POST.get('lijek_preparat', ''),
            doza=request.POST.get('doza', ''),
            veterinar=request.POST.get('veterinar', ''),
            sljedeci_tretman=request.POST.get('sljedeci_tretman') or None,
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Zdravstveni zapis kreiran.')
        return redirect('udruge:golub_detail', pk=golub.pk)
    return render(request, 'udruge/golubar_zdravstveni_form.html', {
        'golub': golub,
        'vrsta_choices': ZdravstveniZapisGolub.VRSTA,
    })


@login_required
def utrka_list(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Utrka
    qs = Utrka.objects.filter(company=company)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'udruge/golubar_utrka_list.html', {'page_obj': page})


@login_required
def utrka_create(request):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Utrka
    from decimal import Decimal
    if request.method == 'POST':
        utrka = Utrka.objects.create(
            company=company,
            naziv=request.POST.get('naziv', ''),
            datum=request.POST.get('datum'),
            startna_tocka=request.POST.get('startna_tocka', ''),
            startna_lat=Decimal(request.POST.get('startna_lat')) if request.POST.get('startna_lat') else None,
            startna_lng=Decimal(request.POST.get('startna_lng')) if request.POST.get('startna_lng') else None,
            udaljenost_km=Decimal(request.POST.get('udaljenost_km')) if request.POST.get('udaljenost_km') else None,
            organizator=request.POST.get('organizator', ''),
            broj_natjecatelja=int(request.POST.get('broj_natjecatelja')) if request.POST.get('broj_natjecatelja') else None,
            uvjeti=request.POST.get('uvjeti', ''),
            napomena=request.POST.get('napomena', ''),
        )
        messages.success(request, 'Utrka "%s" kreirana.' % utrka.naziv)
        return redirect('udruge:utrka_detail', pk=utrka.pk)
    return render(request, 'udruge/golubar_utrka_form.html', {})


@login_required
def utrka_detail(request, pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Utrka
    utrka = get_object_or_404(Utrka, pk=pk, company=company)
    rezultati = utrka.rezultati.select_related('golub').all()
    return render(request, 'udruge/golubar_utrka_detail.html', {
        'utrka': utrka, 'rezultati': rezultati,
    })


@login_required
def rezultat_create(request, utrka_pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Utrka, RezultatUtrke, Golub
    from decimal import Decimal
    utrka = get_object_or_404(Utrka, pk=utrka_pk, company=company)
    if request.method == 'POST':
        RezultatUtrke.objects.create(
            utrka=utrka,
            golub_id=request.POST.get('golub'),
            placiranje=int(request.POST.get('placiranje')) if request.POST.get('placiranje') else None,
            placiranje_ukupno=int(request.POST.get('placiranje_ukupno')) if request.POST.get('placiranje_ukupno') else None,
            brzina_mpm=Decimal(request.POST.get('brzina_mpm')) if request.POST.get('brzina_mpm') else None,
            vrijeme_dolaska=request.POST.get('vrijeme_dolaska') or None,
            bodovi=Decimal(request.POST.get('bodovi')) if request.POST.get('bodovi') else None,
            ets_data={'napomena': request.POST.get('napomena', '')},
        )
        messages.success(request, 'Rezultat dodan.')
        return redirect('udruge:utrka_detail', pk=utrka.pk)
    golubovi = Golub.objects.filter(company=company, aktivan=True)
    return render(request, 'udruge/golubar_rezultat_form.html', {
        'utrka': utrka, 'golubovi': golubovi,
    })


@login_required
@require_POST
def golub_seal(request, pk):
    company = get_user_company(request)
    if not company:
        return redirect('/')
    from .models import Golub
    golub = get_object_or_404(Golub, pk=pk, company=company)
    golub.zapecati()
    messages.success(request, 'Golub %s zapecacen. Hash: %s' % (golub.prsten_broj, golub.genetics_hash[:16]))
    return redirect('udruge:golub_detail', pk=golub.pk)



# ═══════════════════════════════════════════════════════════════════
# PERAD — JATA (Flock) CRUD
# ═══════════════════════════════════════════════════════════════════

@login_required
def flock_list(request):
    from .models import Flock
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('dashboard')

    qs = Flock.objects.filter(company=company)

    # Search
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(
            Q(naziv__icontains=q) |
            Q(pasmina__icontains=q) |
            Q(objekt__icontains=q)
        )

    # Filter po vrsti
    vrsta = request.GET.get('vrsta', '')
    if vrsta:
        qs = qs.filter(vrsta=vrsta)

    # Statistike
    stats = {
        'ukupno_jata': qs.count(),
        'ukupno_aktivnih': qs.filter(aktivan=True).count(),
        'ukupno_komada': sum(f.aktivnih_komada for f in qs.filter(aktivan=True)),
    }

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'udruge/flock_list.html', {
        'page': page, 'q': q, 'vrsta': vrsta, 'stats': stats,
        'vrsta_choices': Flock.VRSTA_CHOICES,
    })


@login_required
def flock_create(request):
    from .models import Flock
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('dashboard')

    if request.method == 'POST':
        flock = Flock(
            company=company,
            naziv=request.POST.get('naziv', ''),
            vrsta=request.POST.get('vrsta', 'kokos'),
            pasmina=request.POST.get('pasmina', ''),
            broj_komada=int(request.POST.get('broj_komada', 0)),
            datum_nabave=request.POST.get('datum_nabave'),
            tip_uzgoja=request.POST.get('tip_uzgoja', 'slobodni'),
            objekt=request.POST.get('objekt', ''),
            napomena=request.POST.get('napomena', ''),
        )
        flock.save()
        messages.success(request, f'Jato "{flock.naziv}" kreirano.')
        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/flock_form.html', {
        'vrsta_choices': Flock.VRSTA_CHOICES,
        'tip_uzgoja_choices': Flock.TIP_UZGOJA_CHOICES,
    })


@login_required
def flock_detail(request, pk):
    from .models import Flock
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=pk, company=company)

    egg_records = flock.egg_records.all()[:30]
    health_records = flock.zdravstveni_zapisi.all()[:20]
    mortalities = flock.mortaliteti.all()[:20]

    # Statistika jaja (zadnjih 30 dana)
    from datetime import timedelta
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    from django.db.models import Sum
    egg_stats = flock.egg_records.filter(datum__gte=thirty_days_ago).aggregate(
        ukupno_jaja=Sum('broj_jaja'),
        ukupno_polomljenih=Sum('broken'),
        ukupno_prodanih=Sum('sold'),
    )

    return render(request, 'udruge/flock_detail.html', {
        'flock': flock,
        'egg_records': egg_records,
        'health_records': health_records,
        'mortalities': mortalities,
        'egg_stats': egg_stats,
    })


@login_required
def flock_edit(request, pk):
    from .models import Flock
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=pk, company=company)

    if request.method == 'POST':
        flock.naziv = request.POST.get('naziv', flock.naziv)
        flock.vrsta = request.POST.get('vrsta', flock.vrsta)
        flock.pasmina = request.POST.get('pasmina', flock.pasmina)
        flock.broj_komada = int(request.POST.get('broj_komada', flock.broj_komada))
        flock.tip_uzgoja = request.POST.get('tip_uzgoja', flock.tip_uzgoja)
        flock.objekt = request.POST.get('objekt', flock.objekt)
        flock.napomena = request.POST.get('napomena', flock.napomena)
        flock.aktivan = request.POST.get('aktivan') == 'on'
        flock.save()
        messages.success(request, f'Jato "{flock.naziv}" ažurirano.')
        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/flock_form.html', {
        'flock': flock,
        'vrsta_choices': Flock.VRSTA_CHOICES,
        'tip_uzgoja_choices': Flock.TIP_UZGOJA_CHOICES,
        'edit': True,
    })


@login_required
def egg_record_create(request, flock_pk):
    from .models import Flock, EggRecord
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = EggRecord(
            flock=flock,
            datum=request.POST.get('datum'),
            broj_jaja=int(request.POST.get('broj_jaja', 0)),
            broken=int(request.POST.get('broken', 0)),
            sold=int(request.POST.get('sold', 0)),
            za_prodaju=request.POST.get('za_prodaju') == 'on',
            cijena_eur=request.POST.get('cijena_eur') or None,
            notes=request.POST.get('notes', ''),
        )
        record.save()
        messages.success(request, f'{record.broj_jaja} jaja zapisano za {record.datum}.')
        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/egg_record_form.html', {'flock': flock})


@login_required
def flock_health_create(request, flock_pk):
    from .models import Flock, FlockHealthRecord
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = FlockHealthRecord(
            flock=flock,
            vrsta_tretmana=request.POST.get('vrsta_tretmana', 'ostalo'),
            datum=request.POST.get('datum'),
            lijek=request.POST.get('lijek', ''),
            doza=request.POST.get('doza', ''),
            veterinar=request.POST.get('veterinar', ''),
            karenca_dana=request.POST.get('karenca_dana') or None,
            napomena=request.POST.get('napomena', ''),
        )
        record.save()

        # Auto-pull: deaktiviraj marketplace oglase za jaja ovog jata ako ima karencu
        if record.karenca_dana and record.karenca_aktivna:
            try:
                from marketplace.models import MarketplaceProduct
                pulled = MarketplaceProduct.objects.filter(
                    source_model='EggRecord',
                    source_id__in=flock.egg_records.values_list('pk', flat=True),
                    is_available=True,
                ).update(is_available=False)
                if pulled:
                    messages.warning(
                        request,
                        f'KARENCA: {pulled} oglas(a) jaja automatski povucen(o) s trznice. '
                        f'Karenca istice {record.datum + __import__("datetime").timedelta(days=record.karenca_dana):%d.%m.%Y}.'
                    )
            except Exception:
                pass

        messages.success(request, f'Zdravstveni zapis dodan za {flock.naziv}.')

        # Upozori o POS blokadi ako postoje linked InventoryItems
        if record.karenca_dana and record.karenca_aktivna:
            try:
                linked_items = flock.inventory_products.filter(
                    is_active=True
                ).values_list('name', flat=True)
                if linked_items:
                    from datetime import timedelta
                    end_date = record.datum + timedelta(days=record.karenca_dana)
                    messages.warning(
                        request,
                        f'POS BLOKADA AKTIVNA: {len(linked_items)} artikl(a) '
                        f'({", ".join(linked_items)}) blokirano za prodaju do '
                        f'{end_date:%d.%m.%Y}. Karenca: {record.karenca_dana} dana.'
                    )
                else:
                    messages.info(
                        request,
                        f'Karenca aktivna ({record.karenca_dana} dana), ali nema '
                        f'povezanih artikala u inventaru. Povežite artikle s jatom '
                        f'u Admin → Inventar → Artikl → Izvorno jato.'
                    )
            except Exception:
                pass

        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/flock_health_form.html', {
        'flock': flock,
        'vrsta_choices': FlockHealthRecord.VRSTA_TRETMANA,
    })


@login_required
def flock_mortality_create(request, flock_pk):
    from .models import Flock, FlockMortality
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = FlockMortality(
            flock=flock,
            datum=request.POST.get('datum'),
            broj_uginulih=int(request.POST.get('broj_uginulih', 0)),
            razlog=request.POST.get('razlog', ''),
            napomena=request.POST.get('napomena', ''),
        )
        record.save()
        messages.success(request, f'Uginuće: {record.broj_uginulih} zapisano.')
        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/flock_mortality_form.html', {'flock': flock})


@login_required
def bridge_publish(request):
    """Ponudi proizvod na tržnicu — univerzalni bridge endpoint."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('dashboard')

    if request.method == 'POST':
        from marketplace.services.marketplace_bridge import publish_to_marketplace

        source_model = request.POST.get('source_model', '')
        source_id = request.POST.get('source_id', '')
        price = request.POST.get('price', '0')
        qty = request.POST.get('qty', '0')
        opg_number = request.POST.get('opg_number', '')

        # Karenca enforcement: blokada prodaje jaja pod aktivnom karencom
        if source_model == 'EggRecord':
            try:
                from .models import EggRecord
                egg = EggRecord.objects.select_related('flock').get(pk=int(source_id))
                if egg.flock.has_active_karenca:
                    karenca_end = egg.flock.karenca_end_date
                    messages.error(
                        request,
                        'ZABRANJENO: Jato "%s" pod aktivnom karencom do %s. '
                        'Prodaja jaja nije dozvoljena za vrijeme zdravstvenog tretmana.' % (
                            egg.flock.naziv,
                            karenca_end.strftime('%d.%m.%Y') if karenca_end else '?',
                        )
                    )
                    return redirect(request.META.get('HTTP_REFERER', 'udruge:flock_list'))
            except EggRecord.DoesNotExist:
                pass

        # Validacija: OPG broj obavezan za hranu
        food_models = {'EggRecord', 'BerbaLog', 'MedProizvodnja', 'RakijaProizvodnja'}
        if source_model in food_models and not opg_number:
            messages.error(request, 'OPG broj je obavezan za prehrambene proizvode (Zakon o OPG čl.12).')
            return redirect(request.META.get('HTTP_REFERER', 'udruge:flock_list'))

        try:
            product = publish_to_marketplace(
                source_model=source_model,
                source_id=int(source_id),
                price=price,
                qty=qty,
                opg_number=opg_number,
            )
            messages.success(request, f'"{product.name}" objavljeno na tržnici! Ističe: {product.expires_at}.')

            # Auto-link: kreira/ažurira StockBatch s source_flock za LOT slijedivost
            if source_model == 'EggRecord':
                try:
                    from .models import EggRecord as ER
                    from inventory.models import InventoryItem, StockBatch
                    egg = ER.objects.select_related('flock').get(pk=int(source_id))
                    flock = egg.flock
                    # Nađi InventoryItem za jaja u istoj firmi (source_flock linked)
                    egg_items = InventoryItem.objects.filter(
                        company=company, source_flock=flock
                    )
                    for item in egg_items:
                        lot_num = f'FLOCK-{flock.pk}-{egg.datum.strftime("%y%m%d")}'
                        batch, created = StockBatch.objects.update_or_create(
                            company=company,
                            item=item,
                            batch_number=lot_num,
                            defaults={
                                'source_flock': flock,
                                'quantity': egg.broj_jaja - egg.broken,
                                'expiry_date': egg.datum + __import__('datetime').timedelta(days=28),
                            }
                        )
                        if created:
                            messages.info(
                                request,
                                f'LOT {lot_num} kreiran za "{item.name}" — '
                                f'{batch.quantity} kom, rok: {batch.expiry_date:%d.%m.%Y}.'
                            )
                except Exception:
                    pass
        except Exception as e:
            messages.error(request, f'Greška pri objavljivanju: {e}')

        return redirect(request.META.get('HTTP_REFERER', 'udruge:flock_list'))

    return redirect('udruge:flock_list')


# ── Golubar AI: generiraj ime goluba iz slike ─────────────────────────────
@require_POST
@csrf_exempt
def golubar_ai_ime(request):
    """
    POST /udruge/golubar/ai-ime/
    Body JSON: { "image_b64": "<base64 jpeg>" }
    Returns:   { "ime": "Vihor", "opis_boje": "siv s bijelim krilima", "confidence": 0.9 }
    """
    import json, os, logging
    logger = logging.getLogger("borg.golubar")

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Prijava potrebna"}, status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Neispravan JSON"}, status=400)

    b64 = data.get("image_b64", "").strip()
    if not b64:
        return JsonResponse({"error": "Nedostaje slika"}, status=400)

    # Provjera veličine — Anthropic limit ~5MB, sigurno < 3.5MB
    import re
    size_bytes = len(b64) * 3 // 4
    if size_bytes > 3_600_000:
        return JsonResponse({"error": "Slika je prevelika (%d KB). Smanji rezoluciju." % (size_bytes//1024)}, status=400)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Ovo je fotografija goluba trkača (racing pigeon). "
                            "Na temelju izgleda predloži: "
                            "1) Kratko ime (snažno, za trkačke golubove, na hrvatskom: Vihor, Munja, Oluja, Srebrni, Planinar, Stijela, Zorko, Grom, Sjever, Zora) "
                            "2) Kratak opis boje perja "
                            "3) Kod boje — SAMO jedan od: siv, bijel, crn, smed, plav, crven, zut, sareno, ostalo "
                            "Odgovori ISKLJUČIVO JSON, bez ikakvog drugog teksta:\n"
                            '{"ime":"...","opis_boje":"...","boja_kod":"siv","confidence":0.9}'
                        ),
                    },
                ],
            }],
        )
        raw = response.content[0].text.strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group(0))
            return JsonResponse(result)
        return JsonResponse({"error": "AI nije vratio valjani JSON", "raw": raw[:200]}, status=500)
    except Exception as e:
        logger.error("golubar_ai_ime error: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)[:200]}, status=500)


# ── Golubar AI: čitanje broja prstena iz slike ───────────────────────────
@require_POST
@csrf_exempt
def golubar_ai_prsten(request):
    """
    POST /udruge/golubar/ai-prsten/
    Body JSON: { "images": ["<b64>", "<b64>", ...] }  # 1-3 slike prstena
    Returns:   { "prsten_broj": "HR-2026-12345", "godina": "2026", "confidence": 0.92 }
    """
    import json, os, re, base64, logging
    logger = logging.getLogger("borg.golubar")

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Prijava potrebna"}, status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Neispravan JSON"}, status=400)

    images = data.get("images", [])
    if not images:
        return JsonResponse({"error": "Nedostaje slika prstena"}, status=400)

    # Provjera veličine — max 3.5MB base64 po slici
    validated = []
    for b64 in images[:3]:
        b64 = b64.strip()
        if not b64:
            continue
        size_bytes = len(b64) * 3 // 4
        if size_bytes > 3_600_000:
            # Slika prevelika — preskočimo je (frontend bi trebao resizati)
            logger.warning("golubar_ai_prsten: slika %d bytes, preskačem", size_bytes)
            continue
        validated.append(b64)

    if not validated:
        return JsonResponse({"error": "Slike su prevelike. Pokušajte s manjom rezolucijom."}, status=400)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

        # Gradi content — jedna ili više slika
        content = []
        for b64 in validated:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })

        if len(validated) > 1:
            prompt = (
                "Prikazano je {} fotografija prstena goluba. "
                "Pogledi sve fotografije i pokuša pročitati broj prstena. "
                "Broj prstena je obično u formatu: HR-YYYY-NNNNN, CRO YYYY NNNNN, "
                "HOG YYYY NNNNN ili slično. "
                "Odgovori ISKLJUČIVO u JSON formatu bez ikakvog drugog teksta:\n"
                '{{"prsten_broj":"...","godina":"...","confidence":0.9}}'
            ).format(len(validated))
        else:
            prompt = (
                "Ovo je fotografija prstena goluba. "
                "Pročitaj broj prstena (ring number). "
                "Format je obično: HR-YYYY-NNNNN, CRO YYYY NNNNN, HOG YYYY NNNNN ili slično. "
                "Ako ne možeš pročitati, vrati confidence manji od 0.3. "
                "Odgovori ISKLJUČIVO u JSON formatu bez ikakvog drugog teksta:\n"
                '{{"prsten_broj":"...","godina":"...","confidence":0.9}}'
            )

        content.append({"type": "text", "text": prompt})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group(0))
            # Ako confidence < 0.4 — prsten_broj vrati prazan
            if float(result.get("confidence", 0)) < 0.4:
                result["prsten_broj"] = ""
            return JsonResponse(result)
        return JsonResponse({"error": "AI nije vratio valjani JSON", "raw": raw[:100]}, status=500)

    except Exception as e:
        logger.error("golubar_ai_prsten error: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)[:200]}, status=500)
