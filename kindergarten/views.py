"""Kindergarten views — dashboard, children, attendance, billing, parent portal."""
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Q, Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import DatabaseError, IntegrityError

from core.company_utils import get_user_company
from .models import (
    KindergartenGroup, Child, Guardian, ChildGuardian,
    Attendance, MonthlyBilling, DailyReport, Announcement,
)


def _company(request):
    return get_user_company(request)


# ── Dashboard ──────────────────────────────────────────────

@login_required
def dashboard(request):
    company = _company(request)
    today = timezone.now().date()

    groups = KindergartenGroup.objects.filter(company=company, is_active=True)
    children_active = Child.objects.filter(company=company, status='active').count()
    children_waitlist = Child.objects.filter(company=company, status='waitlist').count()

    # Danas prisutni
    today_attendance = Attendance.objects.filter(
        child__company=company, date=today, status='present',
    ).count()

    # Danas odsutni
    today_absent = Attendance.objects.filter(
        child__company=company, date=today,
    ).exclude(status='present').count()

    # Neplaćene naplate
    unpaid = MonthlyBilling.objects.filter(
        child__company=company, status__in=['sent', 'overdue'],
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Obavijesti
    announcements = Announcement.objects.filter(
        company=company, is_published=True,
    )[:5]

    return render(request, 'kindergarten/dashboard.html', {
        'groups': groups,
        'children_active': children_active,
        'children_waitlist': children_waitlist,
        'today_present': today_attendance,
        'today_absent': today_absent,
        'unpaid_total': unpaid,
        'announcements': announcements,
        'today': today,
    })


# ── Djeca ──────────────────────────────────────────────────

@login_required
def child_list(request):
    company = _company(request)
    status_filter = request.GET.get('status', 'active')
    group_filter = request.GET.get('group', '')

    qs = Child.objects.filter(company=company).select_related('group')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if group_filter:
        qs = qs.filter(group_id=group_filter)

    groups = KindergartenGroup.objects.filter(company=company, is_active=True)

    return render(request, 'kindergarten/child_list.html', {
        'children': qs,
        'groups': groups,
        'status_filter': status_filter,
        'group_filter': group_filter,
    })


@login_required
def child_detail(request, pk):
    company = _company(request)
    child = get_object_or_404(Child, pk=pk, company=company)
    guardians = child.child_guardians.select_related('guardian').all()
    recent_attendance = child.attendances.order_by('-date')[:30]
    billings = child.billings.order_by('-year', '-month')[:12]

    return render(request, 'kindergarten/child_detail.html', {
        'child': child,
        'guardians': guardians,
        'attendance': recent_attendance,
        'billings': billings,
    })


@login_required
def child_create(request):
    company = _company(request)
    groups = KindergartenGroup.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        d = request.POST
        try:
            child = Child.objects.create(
                company=company,
                group_id=d.get('group') or None,
                first_name=d.get('first_name', '').strip(),
                last_name=d.get('last_name', '').strip(),
                date_of_birth=d.get('date_of_birth'),
                oib=d.get('oib', '').strip(),
                gender=d.get('gender', ''),
                allergies=d.get('allergies', '').strip(),
                dietary_requirements=d.get('dietary_requirements', '').strip(),
                special_needs=d.get('special_needs', '').strip(),
                enrolled_date=d.get('enrolled_date') or timezone.now().date(),
                status=d.get('status', 'active'),
                gdpr_consent=bool(d.get('gdpr_consent')),
                gdpr_consent_date=timezone.now() if d.get('gdpr_consent') else None,
                photo_consent=bool(d.get('photo_consent')),
            )
            messages.success(request, f'Dijete {child} upisano.')
            return redirect('kindergarten:child_detail', pk=child.pk)
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, str(e))

    return render(request, 'kindergarten/child_form.html', {
        'groups': groups, 'mode': 'create',
    })


# ── Evidencija dolazaka ───────────────────────────────────

@login_required
def attendance_daily(request):
    company = _company(request)
    date_str = request.GET.get('date', '')
    try:
        att_date = date.fromisoformat(date_str) if date_str else timezone.now().date()
    except ValueError:
        att_date = timezone.now().date()

    group_id = request.GET.get('group', '')
    children_qs = Child.objects.filter(company=company, status='active')
    if group_id:
        children_qs = children_qs.filter(group_id=group_id)

    children = children_qs.select_related('group').order_by('group__name', 'last_name')

    # Existing attendance for this date
    existing = {
        a.child_id: a for a in
        Attendance.objects.filter(child__company=company, date=att_date)
    }

    children_data = []
    for child in children:
        att = existing.get(child.pk)
        children_data.append({
            'child': child,
            'attendance': att,
            'status': att.status if att else '',
        })

    groups = KindergartenGroup.objects.filter(company=company, is_active=True)

    return render(request, 'kindergarten/attendance_daily.html', {
        'children_data': children_data,
        'att_date': att_date,
        'groups': groups,
        'group_filter': group_id,
        'prev_date': (att_date - timedelta(days=1)).isoformat(),
        'next_date': (att_date + timedelta(days=1)).isoformat(),
    })


@login_required
@require_POST
def attendance_save(request):
    company = _company(request)
    att_date = request.POST.get('date', timezone.now().date().isoformat())
    try:
        att_date = date.fromisoformat(att_date)
    except ValueError:
        att_date = timezone.now().date()

    children = Child.objects.filter(company=company, status='active')
    saved = 0
    for child in children:
        status = request.POST.get(f'status_{child.pk}', '')
        if not status:
            continue
        Attendance.objects.update_or_create(
            child=child, date=att_date,
            defaults={
                'status': status,
                'recorded_by': request.user,
            }
        )
        saved += 1

    messages.success(request, f'Evidencija za {att_date} spremljena ({saved} djece).')
    return redirect(f"{reverse('kindergarten:attendance_daily')}?date={att_date.isoformat()}")


# ── Mjesečna naplata ──────────────────────────────────────

@login_required
def billing_list(request):
    company = _company(request)
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    billings = MonthlyBilling.objects.filter(
        child__company=company, year=year, month=month,
    ).select_related('child', 'child__group')

    total = billings.aggregate(s=Sum('total_amount'))['s'] or 0

    return render(request, 'kindergarten/billing_list.html', {
        'billings': billings,
        'year': year,
        'month': month,
        'total': total,
    })


@login_required
@require_POST
def billing_generate(request):
    """Generiraj mjesečne naplate za sve aktivne djece."""
    company = _company(request)
    year = int(request.POST.get('year', timezone.now().year))
    month = int(request.POST.get('month', timezone.now().month))

    children = Child.objects.filter(company=company, status='active', group__isnull=False)
    created = 0
    for child in children.select_related('group'):
        billing, is_new = MonthlyBilling.objects.get_or_create(
            child=child, year=year, month=month,
            defaults={
                'base_amount': child.group.monthly_price,
                'total_amount': child.group.monthly_price,
            }
        )
        billing.calculate()
        # Due date: 15th of next month
        if month == 12:
            billing.due_date = date(year + 1, 1, 15)
        else:
            billing.due_date = date(year, month + 1, 15)
        billing.save()
        if is_new:
            created += 1

    messages.success(request, f'Generirano {created} novih naplata za {month}/{year}.')
    return redirect(f"{reverse('kindergarten:billing_list')}?year={year}&month={month}")


# ── Roditeljski portal ────────────────────────────────────

def parent_portal(request, slug):
    """Javni roditeljski portal — login roditelja."""
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)

    if not request.user.is_authenticated:
        return render(request, 'kindergarten/portal_login.html', {
            'company': company, 'slug': slug,
        })

    # Find children linked to this parent
    guardian = Guardian.objects.filter(
        company=company, user=request.user,
    ).first()

    if not guardian:
        return render(request, 'kindergarten/portal_no_access.html', {
            'company': company,
        })

    children_links = ChildGuardian.objects.filter(
        guardian=guardian,
    ).select_related('child', 'child__group')

    children = [cg.child for cg in children_links]

    # Daily reports for children's groups
    groups = set(c.group_id for c in children if c.group_id)
    reports = DailyReport.objects.filter(
        group_id__in=groups, is_published=True,
    ).order_by('-date')[:10]

    # Announcements
    announcements = Announcement.objects.filter(
        company=company, is_published=True,
    ).filter(
        Q(group__isnull=True) | Q(group_id__in=groups)
    )[:10]

    # Billings
    billings = MonthlyBilling.objects.filter(
        child__in=children,
    ).order_by('-year', '-month')[:12]

    return render(request, 'kindergarten/portal_home.html', {
        'company': company,
        'guardian': guardian,
        'children': children,
        'reports': reports,
        'announcements': announcements,
        'billings': billings,
        'slug': slug,
    })


# ── Grupe ─────────────────────────────────────────────────

@login_required
def group_list(request):
    company = _company(request)
    groups = KindergartenGroup.objects.filter(company=company)
    return render(request, 'kindergarten/group_list.html', {
        'groups': groups,
    })


# ── Obavijesti ────────────────────────────────────────────

@login_required
def announcement_create(request):
    company = _company(request)
    groups = KindergartenGroup.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        d = request.POST
        Announcement.objects.create(
            company=company,
            group_id=d.get('group') or None,
            title=d.get('title', '').strip(),
            content=d.get('content', '').strip(),
            priority=d.get('priority', 'normal'),
            author=request.user,
        )
        messages.success(request, _('Obavijest objavljena.'))
        return redirect('kindergarten:dashboard')

    return render(request, 'kindergarten/announcement_form.html', {
        'groups': groups,
    })


# ── Dnevni izvještaj ──────────────────────────────────────

@login_required
def daily_report_create(request):
    company = _company(request)
    groups = KindergartenGroup.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        d = request.POST
        report, created = DailyReport.objects.update_or_create(
            group_id=d.get('group'),
            date=d.get('date', timezone.now().date()),
            defaults={
                'content': d.get('content', '').strip(),
                'educator': request.user,
                'is_published': bool(d.get('is_published')),
            }
        )
        messages.success(request, f'Izvještaj za {report.group} — {report.date} spremljen.')
        return redirect('kindergarten:dashboard')

    return render(request, 'kindergarten/daily_report_form.html', {
        'groups': groups, 'today': timezone.now().date(),
    })



# ── Bulk CSV Import ────────────────────────────────────────────────────────

@login_required
def bulk_import_children(request):
    """CSV import djece + roditelja. Auto-create User za portal pristup."""
    import csv
    import io
    import secrets
    from django.contrib.auth import get_user_model
    from kindergarten.forms import BulkChildImportForm

    User = get_user_model()
    company = _company(request)

    if request.method == 'POST':
        form = BulkChildImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            send_invites = form.cleaned_data.get('send_portal_invites', True)

            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded), delimiter=';')

            created_children = 0
            created_guardians = 0
            errors = []

            for row_num, row in enumerate(reader, 2):
                try:
                    # Parse child
                    first_name = row.get('ime', '').strip()
                    last_name = row.get('prezime', '').strip()
                    dob_str = row.get('datum_rodenja', '').strip()
                    oib = row.get('oib', '').strip()

                    if not first_name or not last_name:
                        errors.append(f'Red {row_num}: ime/prezime prazno')
                        continue

                    # Parse date
                    from datetime import datetime
                    try:
                        dob = datetime.strptime(dob_str, '%d.%m.%Y').date()
                    except (ValueError, TypeError):
                        try:
                            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            errors.append(f'Red {row_num}: neispravan datum "{dob_str}"')
                            continue

                    # Find group
                    group_name = row.get('grupa', '').strip()
                    group = None
                    if group_name:
                        group = KindergartenGroup.objects.filter(
                            company=company, name__iexact=group_name
                        ).first()

                    # Create child
                    child, child_created = Child.objects.get_or_create(
                        company=company,
                        first_name=first_name,
                        last_name=last_name,
                        date_of_birth=dob,
                        defaults={
                            'oib': oib,
                            'group': group,
                            'status': 'active',
                            'gdpr_consent': True,
                            'gdpr_consent_date': timezone.now(),
                            'enrolled_date': timezone.now().date(),
                        },
                    )
                    if child_created:
                        created_children += 1

                    # Parse guardian
                    g_first = row.get('roditelj_ime', '').strip()
                    g_last = row.get('roditelj_prezime', '').strip()
                    g_email = row.get('roditelj_email', '').strip()
                    g_phone = row.get('roditelj_telefon', '').strip()

                    if g_first and g_last:
                        guardian, g_created = Guardian.objects.get_or_create(
                            company=company,
                            first_name=g_first,
                            last_name=g_last,
                            defaults={
                                'email': g_email,
                                'phone': g_phone,
                            },
                        )
                        if g_created:
                            created_guardians += 1

                            # Create User for portal access
                            if g_email:
                                password = secrets.token_urlsafe(12)
                                user = User.objects.create_user(
                                    username=g_email,
                                    email=g_email,
                                    password=password,
                                    first_name=g_first,
                                    last_name=g_last,
                                )
                                guardian.user = user
                                guardian.save(update_fields=['user'])

                                # Send portal invite
                                if send_invites and g_phone:
                                    try:
                                        from core.whatsapp import send_text
                                        portal_url = request.build_absolute_uri(
                                            f'/vrtic/{company.booking_slug or company.pk}/portal/'
                                        )
                                        msg = (
                                            f'Postovani {g_first},\n\n'
                                            f'Pristup roditeljskom portalu vrtica:\n'
                                            f'{portal_url}\n\n'
                                            f'Email: {g_email}\n'
                                            f'Lozinka: {password}\n\n'
                                            f'Molimo promijenite lozinku nakon prvog pristupa.'
                                        )
                                        send_text(phone=g_phone, message=msg,
                                                  company_id=str(company.pk))
                                    except ImportError:
                                        pass

                        # Link child to guardian
                        ChildGuardian.objects.get_or_create(
                            child=child,
                            guardian=guardian,
                            defaults={
                                'is_primary': True,
                                'is_billing_contact': True,
                            },
                        )

                except DatabaseError as e:
                    errors.append(f'Red {row_num}: {str(e)[:100]}')

            messages.success(
                request,
                f'Import zavrsen: {created_children} djece, {created_guardians} roditelja. '
                f'{len(errors)} gresaka.'
            )
            if errors:
                for err in errors[:10]:
                    messages.warning(request, err)

            return redirect('kindergarten:child_list')
    else:
        form = BulkChildImportForm()

    return render(request, 'kindergarten/bulk_import.html', {'form': form})


# ── Vrtić → KUD pipeline ──────────────────────────────────────────

@login_required
@require_POST
def preporuci_u_kud(request):
    """
    Odgajateljica preporuči dijete za KUD glazbenu školu.
    Kreira GlazbeniUcenik s vezom na Child + WhatsApp roditelju.
    """
    from kindergarten.models import Child
    from udruge.models import GlazbeniUcenik

    company = _company(request)
    child_id = request.POST.get('child_id')
    instrument = request.POST.get('instrument', 'Tambura (prim)')
    napomena = request.POST.get('napomena', '')

    child = get_object_or_404(Child, pk=child_id, company=company)

    # Check if already recommended
    if GlazbeniUcenik.objects.filter(child=child).exists():
        messages.warning(request, f'{child} je već preporučen/a za KUD.')
        return redirect('kindergarten:child_detail', pk=child.pk)

    # Find KUD company in same umbrella or same location
    from companies.models import Company
    kud = Company.objects.filter(name__icontains='KUD', city=company.city).first()
    if not kud:
        kud = Company.objects.filter(name__icontains='KUD').first()
    if not kud:
        messages.error(request, _('KUD nije pronađen u sustavu.'))
        return redirect('kindergarten:child_detail', pk=child.pk)

    # Create GlazbeniUcenik
    guardian = child.primary_guardian
    ucenik = GlazbeniUcenik.objects.create(
        company=kud,
        child=child,
        ime=child.first_name,
        prezime=child.last_name,
        datum_rodenja=child.date_of_birth,
        instrument=instrument,
        razina='pripremni',
        kontakt_roditelj=f'{guardian.first_name} {guardian.last_name}' if guardian else '',
        telefon=guardian.phone if guardian else '',
        email=guardian.email if guardian else '',
        je_aktivan=True,
        napomene=f'Preporuka iz vrtića: {napomena}' if napomena else 'Preporuka iz vrtića',
    )

    # WhatsApp roditelju
    if guardian and guardian.phone:
        try:
            from core.whatsapp import send_text
            send_text(
                phone=guardian.phone,
                message=(
                    f'Postovani {guardian.first_name},\n\n'
                    f'Odgajateljica je preporucila {child.first_name} za '
                    f'glazbenu skolu pri KUD-u {kud.name}.\n\n'
                    f'Instrument: {instrument}\n'
                    f'Besplatna proba — javite se na +385 91 391 2621.\n\n'
                    f'Srdacan pozdrav!'
                ),
                company_id=str(company.pk),
            )
        except ImportError:
            pass

    messages.success(request, f'{child} preporučen/a za KUD {kud.name} — {instrument}')
    return redirect('kindergarten:child_detail', pk=child.pk)
