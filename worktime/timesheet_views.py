from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.http import HttpResponse, JsonResponse
from notifications.services import notify
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.tenant import get_current_company

from .models import ActiveTimer, DailyNote, EmployeeProfile, Project, TimeEntry, TimeEntryTemplate
from django.core.exceptions import ObjectDoesNotExist


def _user_company(user):
    """Get company from user profile, or thread-local, or None."""
    try:
        return user.profile.company
    except Exception:
        return get_current_company()


# ═══════════════════════════════════════════════════════════════
# WORKER DASHBOARD
# ═══════════════════════════════════════════════════════════════

@login_required
def worker_dashboard(request):
    from accounts.models import UserProfile as _UP
    _requester = request.user
    _is_manager = _requester.is_superuser or _requester.is_staff or getattr(
        getattr(_requester, 'profile', None), 'role', ''
    ) in ('company_admin', 'project_manager', 'superadmin')

    worker_id = request.GET.get('worker_id')
    if worker_id and _is_manager:
        from django.contrib.auth.models import User as _U
        try:
            user = _U.objects.get(pk=worker_id)
        except _U.DoesNotExist:
            user = _requester
    else:
        user = _requester

    _company_workers = []
    if _is_manager:
        _company = _user_company(_requester)
        if _company:
            _wids = _UP.objects.filter(company=_company).values_list('user_id', flat=True)
            from django.contrib.auth.models import User as _U2
            _company_workers = list(
                _U2.objects.filter(pk__in=_wids, is_active=True)
                .order_by('last_name', 'first_name')
            )

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    hours_today = TimeEntry.objects.filter(
        user=user, date=today
    ).aggregate(s=Sum('duration'))['s'] or Decimal('0')
    hours_week = TimeEntry.objects.filter(
        user=user, date__gte=week_start
    ).aggregate(s=Sum('duration'))['s'] or Decimal('0')
    hours_month = TimeEntry.objects.filter(
        user=user, date__gte=month_start
    ).aggregate(s=Sum('duration'))['s'] or Decimal('0')

    try:
        emp = user.employeeprofile
        rate = emp.hourly_rate
        daily_target = emp.daily_hours
        weekly_target = emp.weekly_hours
    except EmployeeProfile.DoesNotExist:
        rate = Decimal('20.00')
        daily_target = Decimal('8.00')
        weekly_target = Decimal('40.00')

    earnings_month = float(hours_month) * float(rate)

    try:
        active_timer = user.active_timer
    except ActiveTimer.DoesNotExist:
        active_timer = None

    week_days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        h = TimeEntry.objects.filter(user=user, date=d).aggregate(
            s=Sum('duration'))['s'] or Decimal('0')
        week_days.append({
            'date': d,
            'day_name': ['Pon','Uto','Sri','Čet','Pet','Sub','Ned'][i],
            'hours': h,
            'is_today': d == today,
            'percentage': min(100, round(float(h) / float(daily_target) * 100)) if daily_target else 0,
        })

    streak = 0
    check_date = today
    while streak < 365:
        if check_date.weekday() >= 5:
            check_date -= timedelta(days=1)
            continue
        if TimeEntry.objects.filter(user=user, date=check_date).exists():
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    recent = TimeEntry.objects.filter(
        user=user, date__gte=today - timedelta(days=14)
    ).select_related('project').order_by('-date', '-start_time')

    templates = TimeEntryTemplate.objects.filter(
        user=user).select_related('project').order_by('-use_count')[:10]

    frequent_projects = TimeEntry.objects.filter(
        user=user, date__gte=today - timedelta(days=30)
    ).values('project__id','project__name','project__code','project__color').annotate(
        cnt=Count('id')).order_by('-cnt')[:5]

    pending = TimeEntry.objects.filter(user=user, status='PENDING').count()
    daily_note = DailyNote.objects.filter(user=user, date=today).first()
    week_progress = min(100, round(float(hours_week) / float(weekly_target) * 100)) if weekly_target else 0

    from burza.models import ProjectLead as _BPL
    _burza_leads = _BPL.objects.filter(
        status__in=['PREUZETO', 'RIJESENO']
    ).order_by('-created_at')[:50]
    # Overtime warnings: entries > 16h that need correction
    overtime_warnings = TimeEntry.objects.filter(
        user=user, duration__gt=16, status='PENDING',
        date__gte=today - timedelta(days=30),
    ).select_related('project').order_by('-date')

    return render(request, 'worktime/worker_dashboard.html', {
        'company_workers': _company_workers,
        'selected_worker': user if user != _requester else None,
        'is_manager': _is_manager,
        'hours_today': hours_today, 'hours_week': hours_week,
        'hours_month': hours_month, 'earnings_month': earnings_month,
        'hourly_rate': rate, 'daily_target': daily_target,
        'weekly_target': weekly_target, 'week_progress': week_progress,
        'recent_entries': recent[:30],
        'projects': Project.objects.filter(status='ACTIVE').order_by('name'),
        'pending_count': pending, 'today': today,
        'active_timer': active_timer, 'week_days': week_days,
        'streak': streak, 'templates': templates,
        'frequent_projects': frequent_projects,
        'daily_note': daily_note,
        'task_types': TimeEntry.TASK_TYPES,
        'burza_leads': _burza_leads,
        'overtime_warnings': overtime_warnings,
    })


# ═══════════════════════════════════════════════════════════════
# ŠTOPERICA (TIMER)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def timer_start(request):
    _req = request.user
    _is_mgr = _req.is_superuser or _req.is_staff or getattr(
        getattr(_req, 'profile', None), 'role', ''
    ) in ('company_admin', 'project_manager', 'superadmin')
    _wid = request.POST.get('worker_id')
    if _wid and _is_mgr:
        from django.contrib.auth.models import User as _UU
        try:
            user = _UU.objects.get(pk=_wid)
        except _UU.DoesNotExist:
            user = _req
    else:
        user = _req
    if hasattr(user, 'active_timer'):
        try:
            existing = user.active_timer
            if request.POST.get('force') == '1':
                entry = existing.stop_and_save()
                messages.info(request, f'Prethodni timer spremljen ({entry.duration}h)')
            else:
                messages.warning(request, _('Već imate aktivan timer! Zaustavite ga prvo.'))
                return redirect('worktime:ts_worker')
        except ActiveTimer.DoesNotExist:
            pass

    project_id = request.POST.get('project_id') or request.POST.get('project')
    if not project_id:
        messages.error(request, _('Odaberite projekt!'))
        return redirect('worktime:ts_worker')
    try:
        project = Project.objects.get(pk=project_id, status='ACTIVE')
    except Project.DoesNotExist:
        messages.error(request, _('Projekt nije pronađen!'))
        return redirect('worktime:ts_worker')

    _timer_lead_id = request.POST.get('project_lead', '').strip()
    _timer_pl = None
    if _timer_lead_id:
        try:
            from burza.models import ProjectLead as _TPL
            _timer_pl = _TPL.objects.get(pk=_timer_lead_id)
        except ObjectDoesNotExist:
            pass
    timer = ActiveTimer.objects.create(
        company=_user_company(user),
        user=user, project=project,
        description=request.POST.get('description',''),
        task_type=request.POST.get('task_type','DEVELOPMENT'),
        status='RUNNING', started_at=timezone.now(),
        tags=request.POST.get('tags',''),
        project_lead=_timer_pl,
    )
    messages.success(request, f'⏱ Štoperica pokrenuta za {project.name}')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status':'ok','timer_id':timer.pk,'project':project.name,
                             'started_at':timer.started_at.isoformat()})
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def timer_pause(request):
    try:
        timer = request.user.active_timer
        timer.pause()
        messages.info(request, f'⏸ Štoperica pauzirana ({timer.elapsed_display})')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status':'paused','elapsed':timer.elapsed_seconds,
                                 'display':timer.elapsed_display})
    except ActiveTimer.DoesNotExist:
        messages.error(request, _('Nemate aktivan timer.'))
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def timer_resume(request):
    try:
        timer = request.user.active_timer
        timer.resume()
        messages.success(request, _('▶ Štoperica nastavljena'))
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status':'running','started_at':timer.started_at.isoformat(),
                                 'accumulated':timer.accumulated_seconds})
    except ActiveTimer.DoesNotExist:
        messages.error(request, _('Nemate aktivan timer.'))
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def timer_stop(request):
    try:
        timer = request.user.active_timer
        desc = request.POST.get('description','')
        if desc: timer.description = desc
        task_type = request.POST.get('task_type','')
        if task_type: timer.task_type = task_type
        tags = request.POST.get('tags','')
        if tags: timer.tags = tags
        timer.save()

        # Validate timer duration
        elapsed_hours = timer.elapsed_hours
        if elapsed_hours > Decimal('16'):
            messages.warning(request, f'⚠️ Timer lief {elapsed_hours}h - gekürzt auf 16h Maximum')
            # Don't stop, let user decide
            # Actually save but cap at 16h

        entry = timer.stop_and_save()

        # Check daily total
        from django.db.models import Sum
        day_total = TimeEntry.objects.filter(
            user=request.user, date=entry.date
        ).aggregate(s=Sum('duration'))['s'] or Decimal('0')

        msg = f'✓ Štoperica: {entry.duration}h spremljeno za {entry.project.name}'
        if day_total > Decimal('12'):
            msg += f' ⚠️ Ukupno danas: {day_total}h!'
        messages.success(request, msg)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status':'saved','entry_id':entry.pk,
                                 'duration':str(entry.duration),'project':entry.project.name})
    except ActiveTimer.DoesNotExist:
        messages.error(request, _('Nemate aktivan timer.'))
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def timer_discard(request):
    try:
        timer = request.user.active_timer
        project_name = timer.project.name
        elapsed = timer.elapsed_display
        timer.discard()
        messages.warning(request, f'Timer za {project_name} odbačen ({elapsed})')
    except ActiveTimer.DoesNotExist:
        messages.error(request, _('Nemate aktivan timer.'))
    return redirect('worktime:ts_worker')


@login_required
def timer_status(request):
    try:
        timer = request.user.active_timer
        try: rate = float(request.user.employeeprofile.hourly_rate)
        except Exception: rate = float(timer.project.hourly_rate)
        elapsed = timer.elapsed_seconds
        hours = elapsed / 3600
        return JsonResponse({
            'active': True, 'status': timer.status,
            'project_id': timer.project_id, 'project_name': timer.project.name,
            'project_code': timer.project.code, 'project_color': timer.project.color,
            'description': timer.description, 'task_type': timer.task_type,
            'started_at': timer.created_at.isoformat(),
            'elapsed_seconds': elapsed, 'elapsed_display': timer.elapsed_display,
            'elapsed_hours': round(hours, 2), 'earnings': round(hours * rate, 2),
            'accumulated_seconds': timer.accumulated_seconds,
            'timer_started_at': timer.started_at.isoformat(),
        })
    except ActiveTimer.DoesNotExist:
        return JsonResponse({'active': False})


@login_required
@require_POST
def timer_update(request):
    try:
        timer = request.user.active_timer
        desc = request.POST.get('description')
        task_type = request.POST.get('task_type')
        project_id = request.POST.get('project_id') or request.POST.get('project')
        tags = request.POST.get('tags')
        if desc is not None: timer.description = desc
        if task_type: timer.task_type = task_type
        if tags is not None: timer.tags = tags
        if project_id:
            try: timer.project = Project.objects.get(pk=project_id, status='ACTIVE')
            except Exception: pass
        timer.save()
        return JsonResponse({'status': 'updated'})
    except ActiveTimer.DoesNotExist:
        return JsonResponse({'error': 'no timer'}, status=404)


# ═══════════════════════════════════════════════════════════════
# TIME ENTRY CRUD
# ═══════════════════════════════════════════════════════════════

@login_required
def time_entry_add(request):
    if request.method == 'POST':
        try:
            project = Project.objects.get(pk=request.POST.get('project'))
            entry_date = date.fromisoformat(request.POST.get('date', str(date.today())))
            start_str = request.POST.get('start_time','').strip()
            end_str = request.POST.get('end_time','').strip()
            dur_str = request.POST.get('duration','0').replace(',','.')

            start = None; end = None; duration = Decimal('0')
            if start_str:
                start = datetime.strptime(start_str, '%H:%M').time()
            if start_str and end_str:
                end = datetime.strptime(end_str, '%H:%M').time()
                s = datetime.combine(entry_date, start)
                e = datetime.combine(entry_date, end)
                if e < s: e += timedelta(days=1)
                break_minutes = int(request.POST.get('break_minutes','0') or '0')
                diff_seconds = (e - s).total_seconds() - (break_minutes * 60)
                duration = Decimal(str(round(max(0, diff_seconds) / 3600, 2)))
            else:
                duration = Decimal(dur_str) if dur_str else Decimal('0')

            if duration <= 0:
                messages.error(request, _('❌ Trajanje mora biti pozitivno!'))
                return redirect('worktime:ts_worker')

            # ═══ VALIDATION: Max hours per entry ═══
            MAX_SINGLE_ENTRY = Decimal('16')
            if duration > MAX_SINGLE_ENTRY:
                messages.error(request, f'❌ Maksimalno {MAX_SINGLE_ENTRY}h po unosu! Unijeli ste {duration}h.')
                return redirect('worktime:ts_worker')

            # ═══ VALIDATION: Max hours per day ═══
            MAX_DAILY_HOURS = Decimal('24')
            WARN_DAILY_HOURS = Decimal('12')
            existing_hours = TimeEntry.objects.filter(
                user=request.user, date=entry_date
            ).aggregate(s=Sum('duration'))['s'] or Decimal('0')
            total_day = existing_hours + duration

            if total_day > MAX_DAILY_HOURS:
                messages.error(request, f'❌ Ukupno {total_day}h za {entry_date.strftime("%d.%m.%Y")} - nije moguće više od 24h dnevno! Već imate {existing_hours}h.')
                return redirect('worktime:ts_worker')

            # ═══ VALIDATION: Future date ═══
            if entry_date > date.today():
                messages.warning(request, f'⚠️ Unos za budući datum: {entry_date.strftime("%d.%m.%Y")}')

            # ═══ VALIDATION: Very old date ═══
            if entry_date < date.today() - timedelta(days=60):
                messages.error(request, f'❌ Ne možete unijeti sate starije od 60 dana!')
                return redirect('worktime:ts_worker')

            try: rate = request.user.employeeprofile.hourly_rate
            except Exception: rate = project.hourly_rate

            try:
                daily_target = request.user.employeeprofile.daily_hours
                overtime_rate = request.user.employeeprofile.overtime_rate
            except Exception:
                daily_target = Decimal('8.00')
                overtime_rate = rate * Decimal('1.5')

            is_overtime = total_day > daily_target
            if is_overtime:
                billing = duration * overtime_rate if project.is_billable else Decimal('0')
            else:
                billing = duration * rate if project.is_billable else Decimal('0')

            _lead_id = request.POST.get('project_lead', '').strip()
            _pl = None
            if _lead_id:
                try:
                    from burza.models import ProjectLead as _PL
                    _pl = _PL.objects.get(pk=_lead_id)
                except ObjectDoesNotExist:
                    pass
            TimeEntry.objects.create(
                company=_user_company(request.user),
                user=request.user, project=project, date=entry_date,
                start_time=start, end_time=end, duration=duration,
                description=request.POST.get('description',''),
                task_type=request.POST.get('task_type','DEVELOPMENT'),
                status='PENDING', billing_amount=billing,
                is_overtime=is_overtime, tags=request.POST.get('tags',''),
                project_lead=_pl,
                absence_type=request.POST.get('absence_type',''),
                is_night_work=request.POST.get('is_night_work')=='1',
                is_holiday_work=request.POST.get('is_holiday_work')=='1',
                break_minutes=int(request.POST.get('break_minutes','0') or '0'),
                daily_rest_hours=Decimal(request.POST.get('daily_rest_hours','').replace(',','.')) if request.POST.get('daily_rest_hours','').strip() else None,
            )

            msg = f'✓ {duration}h uneseno za {project.name}'
            if is_overtime:
                msg += ' (prekovremeno ⚡)'
            if total_day > WARN_DAILY_HOURS:
                msg += f' ⚠️ Ukupno danas: {total_day}h!'
            messages.success(request, msg)

            if request.POST.get('save_and_new'):
                return redirect('worktime:ts_add')
                return
        except Exception as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
        return redirect('worktime:ts_worker')
    # GET — prikaži formu za unos
    prefill_date = request.GET.get('date', str(date.today()))
    prefill_project = request.GET.get('project', '')
    projects = Project.objects.filter(
        company=_user_company(request.user), status='ACTIVE'
    ).order_by('name')
    last_entry = TimeEntry.objects.filter(user=request.user).first()
    return render(request, 'worktime/ts_add.html', {
        'projects': projects,
        'task_types': TimeEntry.TASK_TYPES,
        'absence_types': TimeEntry.ABSENCE_TYPES,
        'prefill_date': prefill_date,
        'prefill_project': prefill_project,
        'last_entry': last_entry,
        'today': date.today(),
    })


@login_required
def time_entry_edit(request, pk):
    te = get_object_or_404(TimeEntry, pk=pk, user=request.user)
    if te.status not in ('DRAFT','PENDING'):
        messages.error(request, _('Možete uređivati samo unose u statusu Skica ili Na čekanju.'))
        return redirect('worktime:ts_worker')
    if request.method == 'POST':
        try:
            te.project = Project.objects.get(pk=request.POST.get('project'))
            te.date = date.fromisoformat(request.POST.get('date', str(te.date)))
            start_str = request.POST.get('start_time','').strip()
            end_str = request.POST.get('end_time','').strip()
            if start_str:
                te.start_time = datetime.strptime(start_str, '%H:%M').time()
            if end_str and te.start_time:
                te.end_time = datetime.strptime(end_str, '%H:%M').time()
                s = datetime.combine(te.date, te.start_time)
                e = datetime.combine(te.date, te.end_time)
                if e < s: e += timedelta(days=1)
                break_min = int(request.POST.get('break_minutes','0') or '0')
                te.duration = Decimal(str(round(
                    max(0, (e-s).total_seconds() - break_min*60) / 3600, 2)))
            else:
                dur_str = request.POST.get('duration','').replace(',','.')
                if dur_str: te.duration = Decimal(dur_str)
            te.description = request.POST.get('description','')
            te.task_type = request.POST.get('task_type', te.task_type)
            te.tags = request.POST.get('tags','')
            # ── Zakonska polja (HR NN 55/24 + DE ArbSchG) ──────────────
            te.absence_type   = request.POST.get('absence_type', '')
            te.is_night_work  = request.POST.get('is_night_work') == '1'
            te.is_holiday_work= request.POST.get('is_holiday_work') == '1'
            te.break_minutes  = int(request.POST.get('break_minutes','0') or '0')
            dr = request.POST.get('daily_rest_hours','').strip().replace(',','.')
            te.daily_rest_hours = Decimal(dr) if dr else None
            try: rate = request.user.employeeprofile.hourly_rate
            except Exception: rate = te.project.hourly_rate
            te.billing_amount = te.duration * rate if te.project.is_billable else Decimal('0')
            _lead_id2 = request.POST.get('project_lead', '').strip()
            if _lead_id2:
                try:
                    from burza.models import ProjectLead as _PL2
                    te.project_lead = _PL2.objects.get(pk=_lead_id2)
                except ObjectDoesNotExist:
                    te.project_lead = None
            elif 'project_lead' in request.POST:
                te.project_lead = None
            te.save()
            messages.success(request, f'✓ Unos ažuriran ({te.duration}h)')
        except ObjectDoesNotExist as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
        return redirect('worktime:ts_worker')
    projects = Project.objects.filter(
        company=_user_company(request.user), status='ACTIVE'
    ).order_by('name')
    return render(request, 'worktime/entry_edit.html', {
        'entry': te, 'projects': projects,
        'task_types': TimeEntry.TASK_TYPES,
        'absence_types': TimeEntry.ABSENCE_TYPES,
    })


@login_required
def time_entry_delete(request, pk):
    te = get_object_or_404(TimeEntry, pk=pk, user=request.user)
    if te.status in ('DRAFT','PENDING'):
        te.delete()
        messages.success(request, _('Unos obrisan.'))
    else:
        messages.error(request, _('Možete brisati samo unose na čekanju.'))
    return redirect('worktime:ts_worker')


@login_required
def time_entry_duplicate(request, pk):
    te = get_object_or_404(TimeEntry, pk=pk, user=request.user)
    try: rate = request.user.employeeprofile.hourly_rate
    except Exception: rate = te.project.hourly_rate
    billing = te.duration * rate if te.project.is_billable else Decimal('0')
    new_entry = TimeEntry.objects.create(
        company=_user_company(request.user),
        user=request.user, project=te.project, date=date.today(),
        start_time=te.start_time, end_time=te.end_time,
        duration=te.duration, description=te.description,
        task_type=te.task_type, status='PENDING',
        billing_amount=billing, tags=te.tags,
    )
    messages.success(request, f'✓ Unos dupliciran za danas ({new_entry.duration}h)')
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def copy_previous_day(request):
    today = date.today()
    prev = today - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    entries = TimeEntry.objects.filter(user=request.user, date=prev)
    if not entries.exists():
        messages.warning(request, f'Nema unosa za {prev.strftime("%d.%m.%Y")}')
        return redirect('worktime:ts_worker')
    count = 0
    for te in entries:
        try: rate = request.user.employeeprofile.hourly_rate
        except Exception: rate = te.project.hourly_rate
        billing = te.duration * rate if te.project.is_billable else Decimal('0')
        TimeEntry.objects.create(
            company=_user_company(request.user),
            user=request.user, project=te.project, date=today,
            start_time=te.start_time, end_time=te.end_time,
            duration=te.duration, description=te.description,
            task_type=te.task_type, status='PENDING',
            billing_amount=billing, tags=te.tags,
        )
        count += 1
    messages.success(request, f'✓ Kopirano {count} unos(a) od {prev.strftime("%d.%m.%Y")}')
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def copy_day(request):
    """Kopiraj unose iz određenog dana na danas ili target_date."""
    source_str = request.POST.get('source_date', '').strip()
    target_str = request.POST.get('target_date', str(date.today())).strip()
    try:
        source = date.fromisoformat(source_str) if source_str else date.today() - timedelta(days=1)
        target = date.fromisoformat(target_str)
    except ValueError:
        messages.error(request, _('Neispravan datum.'))
        return redirect('worktime:ts_worker')
    entries = TimeEntry.objects.filter(user=request.user, date=source)
    if not entries.exists():
        messages.warning(request, f'Nema unosa za {source.strftime("%d.%m.%Y")}')
        return redirect('worktime:ts_worker')
    count = 0
    for te in entries:
        try: rate = request.user.employeeprofile.hourly_rate
        except Exception: rate = te.project.hourly_rate
        billing = te.duration * rate if te.project.is_billable else Decimal('0')
        TimeEntry.objects.create(
            company=_user_company(request.user),
            user=request.user, project=te.project, date=target,
            start_time=te.start_time, end_time=te.end_time,
            duration=te.duration, description=te.description,
            task_type=te.task_type, status='PENDING', billing_amount=billing,
            tags=te.tags, is_night_work=te.is_night_work,
            is_holiday_work=te.is_holiday_work, break_minutes=te.break_minutes,
            absence_type=te.absence_type,
        )
        count += 1
    messages.success(request, f'✓ Kopirano {count} unos(a) od {source.strftime("%d.%m.%Y")} → {target.strftime("%d.%m.%Y")}')
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def copy_week(request):
    """Kopiraj prethodni tjedan na ovaj tjedan (pon–pet)."""
    today = date.today()
    # Ovaj tjedan: ponedjeljak
    this_mon = today - timedelta(days=today.weekday())
    prev_mon = this_mon - timedelta(weeks=1)

    target_offset = int(request.POST.get('target_offset', '0'))  # 0=ovaj, 1=sljedeći
    if target_offset:
        this_mon = this_mon + timedelta(weeks=target_offset)

    entries = TimeEntry.objects.filter(
        user=request.user,
        date__gte=prev_mon,
        date__lt=prev_mon + timedelta(weeks=1)
    )
    if not entries.exists():
        messages.warning(request, f'Nema unosa za prethodni tjedan ({prev_mon.strftime("%d.%m.")}–{(prev_mon+timedelta(days=6)).strftime("%d.%m.%Y")})')
        return redirect('worktime:ts_worker')

    skip_existing = request.POST.get('skip_existing') == '1'
    count = 0
    for te in entries:
        delta = te.date - prev_mon
        new_date = this_mon + delta
        if new_date > date.today() + timedelta(days=365):
            continue
        if skip_existing and TimeEntry.objects.filter(user=request.user, date=new_date, project=te.project).exists():
            continue
        try: rate = request.user.employeeprofile.hourly_rate
        except Exception: rate = te.project.hourly_rate
        billing = te.duration * rate if te.project.is_billable else Decimal('0')
        TimeEntry.objects.create(
            company=_user_company(request.user),
            user=request.user, project=te.project, date=new_date,
            start_time=te.start_time, end_time=te.end_time,
            duration=te.duration, description=te.description,
            task_type=te.task_type, status='PENDING', billing_amount=billing,
            tags=te.tags, is_night_work=te.is_night_work,
            is_holiday_work=te.is_holiday_work, break_minutes=te.break_minutes,
            absence_type=te.absence_type,
        )
        count += 1
    messages.success(request, f'✓ Kopirano {count} unos(a) — tjedan {this_mon.strftime("%d.%m.")}–{(this_mon+timedelta(days=6)).strftime("%d.%m.%Y")}')
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def copy_month(request):
    """Kopiraj prethodni mjesec na ovaj (samo radni dani, bez vikenda)."""
    today = date.today()
    target_year = today.year
    target_month = today.month
    # Prethodni mjesec
    if today.month == 1:
        src_year, src_month = today.year - 1, 12
    else:
        src_year, src_month = today.year, today.month - 1

    import calendar
    entries = TimeEntry.objects.filter(
        user=request.user,
        date__year=src_year, date__month=src_month
    )
    if not entries.exists():
        messages.warning(request, f'Nema unosa za {src_month:02d}/{src_year}')
        return redirect('worktime:ts_worker')

    # Gradi mapping: dan_u_mj → unosi
    src_days = {}
    for te in entries:
        d = te.date.day
        src_days.setdefault(d, []).append(te)

    skip_existing = request.POST.get('skip_existing') == '1'
    count = 0
    _, src_last = calendar.monthrange(src_year, src_month)
    _, tgt_last = calendar.monthrange(target_year, target_month)

    for day_num, day_entries in src_days.items():
        if day_num > tgt_last:
            continue
        new_date = date(target_year, target_month, day_num)
        if new_date.weekday() >= 5:  # skip vikend
            continue
        for te in day_entries:
            if skip_existing and TimeEntry.objects.filter(user=request.user, date=new_date, project=te.project).exists():
                continue
            try: rate = request.user.employeeprofile.hourly_rate
            except Exception: rate = te.project.hourly_rate
            billing = te.duration * rate if te.project.is_billable else Decimal('0')
            TimeEntry.objects.create(
                company=_user_company(request.user),
                user=request.user, project=te.project, date=new_date,
                start_time=te.start_time, end_time=te.end_time,
                duration=te.duration, description=te.description,
                task_type=te.task_type, status='PENDING', billing_amount=billing,
                tags=te.tags, is_night_work=te.is_night_work,
                is_holiday_work=te.is_holiday_work, break_minutes=te.break_minutes,
                absence_type=te.absence_type,
            )
            count += 1
    messages.success(request, f'✓ Kopirano {count} unos(a) iz {src_month:02d}/{src_year} → {target_month:02d}/{target_year}')
    return redirect('worktime:ts_worker')



# ═══════════════════════════════════════════════════════════════
# PREDLOŠCI
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def template_save(request):
    try:
        project = Project.objects.get(pk=request.POST.get('project'))
        name = request.POST.get('template_name','').strip()
        if not name: name = f"{project.code} - {request.POST.get('task_type','DEVELOPMENT')}"
        tmpl, created = TimeEntryTemplate.objects.update_or_create(
            user=request.user, name=name,
            defaults={
                'project': project,
                'description': request.POST.get('description',''),
                'task_type': request.POST.get('task_type','DEVELOPMENT'),
                'default_duration': Decimal(request.POST.get('duration','8').replace(',','.')),
                'tags': request.POST.get('tags',''),
            }
        )
        messages.success(request, f'✓ Predložak {"kreiran" if created else "ažuriran"}: {name}')
    except ObjectDoesNotExist as e:
        messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
    return redirect('worktime:ts_worker')


@login_required
@require_POST
def template_use(request, pk):
    tmpl = get_object_or_404(TimeEntryTemplate, pk=pk, user=request.user)
    try: rate = request.user.employeeprofile.hourly_rate
    except Exception: rate = tmpl.project.hourly_rate
    duration = Decimal(request.POST.get('duration', str(tmpl.default_duration)).replace(',','.'))
    billing = duration * rate if tmpl.project.is_billable else Decimal('0')
    TimeEntry.objects.create(
        company=_user_company(request.user),
        user=request.user, project=tmpl.project, date=date.today(),
        start_time=tmpl.default_start, end_time=tmpl.default_end,
        duration=duration, description=tmpl.description,
        task_type=tmpl.task_type, status='PENDING',
        billing_amount=billing, tags=tmpl.tags,
    )
    tmpl.use_count += 1; tmpl.save()
    messages.success(request, f'✓ {duration}h uneseno iz predloška "{tmpl.name}"')
    return redirect('worktime:ts_worker')


@login_required
def template_delete(request, pk):
    tmpl = get_object_or_404(TimeEntryTemplate, pk=pk, user=request.user)
    tmpl.delete()
    messages.success(request, _('Predložak obrisan.'))
    return redirect('worktime:ts_worker')


# ═══════════════════════════════════════════════════════════════
# BILJEŠKE
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def daily_note_save(request):
    note_text = request.POST.get('note','').strip()
    note_date = date.fromisoformat(request.POST.get('date', str(date.today())))
    if note_text:
        DailyNote.objects.update_or_create(
            user=request.user, date=note_date, defaults={'note': note_text})
        messages.success(request, _('✓ Bilješka spremljena'))
    else:
        DailyNote.objects.filter(user=request.user, date=note_date).delete()
        messages.info(request, _('Bilješka obrisana'))
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect('worktime:ts_worker')


# ═══════════════════════════════════════════════════════════════
# TJEDNI UNOS
# ═══════════════════════════════════════════════════════════════

@login_required
def weekly_entry(request):
    today = date.today()
    week_offset = int(request.GET.get('week', 0))
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    days = [week_start + timedelta(days=i) for i in range(7)]
    projects = Project.objects.filter(status='ACTIVE').order_by('name')

    existing = {}
    entries = TimeEntry.objects.filter(
        user=request.user, date__gte=days[0], date__lte=days[6]
    ).select_related('project')
    for e in entries:
        key = f"{e.project_id}_{e.date}"
        if key not in existing:
            existing[key] = {'hours': Decimal('0'), 'entries': []}
        existing[key]['hours'] += e.duration
        existing[key]['entries'].append(e)

    if request.method == 'POST':
        count = 0
        for project in projects:
            for d in days:
                val = request.POST.get(f'hours_{project.id}_{d}','').strip().replace(',','.')
                if not val: continue
                try:
                    hours = Decimal(val)
                    if hours <= 0: continue
                except (InvalidOperation, ValueError): continue
                try: rate = request.user.employeeprofile.hourly_rate
                except Exception: rate = project.hourly_rate
                billing = hours * rate if project.is_billable else Decimal('0')
                TimeEntry.objects.create(
                    company=_user_company(request.user),
                    user=request.user, project=project, date=d,
                    duration=hours, description=request.POST.get(f'desc_{project.id}',''),
                    task_type='DEVELOPMENT', status='PENDING', billing_amount=billing,
                )
                count += 1
        messages.success(request, f'✓ {count} unos(a) spremljeno')
        return redirect('worktime:ts_weekly')

    day_totals = []
    for d in days:
        h = TimeEntry.objects.filter(user=request.user, date=d).aggregate(
            s=Sum('duration'))['s'] or Decimal('0')
        day_totals.append(h)

    return render(request, 'worktime/weekly_entry.html', {
        'days': days, 'projects': projects, 'existing': existing,
        'week_start': week_start, 'week_offset': week_offset,
        'day_totals': day_totals, 'total_week': sum(day_totals),
        'today': today,
    })


# ═══════════════════════════════════════════════════════════════
# PROFIL
# ═══════════════════════════════════════════════════════════════

@login_required
def worker_profile(request):
    user = request.user
    try:
        emp = user.employeeprofile
    except EmployeeProfile.DoesNotExist:
        emp = EmployeeProfile.objects.create(
            user=user, company=_user_company(user),
            hourly_rate=Decimal('20.00'), overtime_rate=Decimal('30.00'),
            daily_hours=Decimal('8.00'), weekly_hours=Decimal('40.00'),
        )
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.email = request.POST.get('email', user.email)
            user.save()
            if not emp:
                emp = EmployeeProfile.objects.create(user=user, company=_user_company(user))
            emp.phone = request.POST.get('phone', emp.phone or '')
            emp.address = request.POST.get('address', emp.address or '')
            emp.bank_account = request.POST.get('bank_account', emp.bank_account or '')
            tax_id = request.POST.get('tax_id', '').strip()
            if tax_id:
                emp.tax_id = tax_id
            emp.save()
            messages.success(request, _('✓ Profil ažuriran!'))
        elif action == 'update_rate':
            if not emp:
                emp = EmployeeProfile.objects.create(user=user, company=_user_company(user))
            try:
                new_rate = request.POST.get('hourly_rate', '')
                new_overtime = request.POST.get('overtime_rate', '')
                new_daily = request.POST.get('daily_hours', '')
                new_weekly = request.POST.get('weekly_hours', '')
                if new_rate: emp.hourly_rate = Decimal(str(new_rate).replace(',','.'))
                if new_overtime: emp.overtime_rate = Decimal(str(new_overtime).replace(',','.'))
                if new_daily: emp.daily_hours = Decimal(str(new_daily).replace(',','.'))
                if new_weekly: emp.weekly_hours = Decimal(str(new_weekly).replace(',','.'))
                emp.save()
                messages.success(request, f'✓ Satnica ažurirana: €{emp.hourly_rate}/h (prekovremeno: €{emp.overtime_rate}/h)')
            except (ValueError, TypeError) as e:
                messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
            return redirect('worktime:ts_profile')
        # change_password action removed — use /accounts/password/
        return redirect('worktime:ts_profile')
    total_hours = TimeEntry.objects.filter(user=user).aggregate(s=Sum('duration'))['s'] or 0
    total_earnings = TimeEntry.objects.filter(user=user).aggregate(s=Sum('billing_amount'))['s'] or 0
    month_hours = TimeEntry.objects.filter(
        user=user, date__gte=date.today().replace(day=1)
    ).aggregate(s=Sum('duration'))['s'] or 0
    return render(request, 'worktime/worker_profile.html', {
        'emp': emp, 'total_hours': total_hours,
        'total_earnings': total_earnings, 'month_hours': month_hours,
    })


# ═══════════════════════════════════════════════════════════════
# MANAGER TIMESHEET
# ═══════════════════════════════════════════════════════════════

@login_required
def manager_timesheet(request):
    today = date.today()
    month_start = today.replace(day=1)
    date_from_str = request.GET.get('date_from', str(month_start))
    date_to_str = request.GET.get('date_to', str(today))
    project_id = request.GET.get('project','')
    worker_ids = request.GET.getlist('workers')
    status_filter = request.GET.get('status','')
    try:
        date_from = date.fromisoformat(date_from_str)
        date_to = date.fromisoformat(date_to_str)
    except Exception:
        date_from, date_to = month_start, today

    # Filtriraj po firmi prijavljenog usera
    company = _user_company(request.user)
    company_user_ids = None
    if company and not request.user.is_superuser:
        from accounts.models import UserProfile
        company_user_ids = list(
            UserProfile.objects.filter(company=company).values_list('user_id', flat=True)
        )

    qs = TimeEntry.objects.select_related('user','project')
    qs = qs.filter(date__gte=date_from, date__lte=date_to)
    if company_user_ids is not None:
        qs = qs.filter(user_id__in=company_user_ids)
    if project_id: qs = qs.filter(project_id=project_id)
    if worker_ids: qs = qs.filter(user_id__in=worker_ids)
    if status_filter: qs = qs.filter(status=status_filter)
    qs = qs.order_by('user__last_name','user__first_name','-date')

    workers_data = {}
    for te in qs:
        uid = te.user_id
        if uid not in workers_data:
            try: rate = te.user.employeeprofile.hourly_rate
            except Exception: rate = te.project.hourly_rate
            workers_data[uid] = {
                'user': te.user, 'entries': [],
                'total_hours': Decimal('0'), 'total_amount': Decimal('0'),
                'hourly_rate': rate,
                'emp': getattr(te.user, 'employeeprofile', None),
                'overtime_hours': Decimal('0'),
            }
        workers_data[uid]['entries'].append(te)
        workers_data[uid]['total_hours'] += te.duration
        workers_data[uid]['total_amount'] += te.billing_amount
        if te.is_overtime:
            workers_data[uid]['overtime_hours'] += te.duration

    active_timers = ActiveTimer.objects.select_related('user','project').all()
    if company_user_ids is not None:
        active_timers = active_timers.filter(user_id__in=company_user_ids)

    all_projects = Project.objects.filter(status='ACTIVE').order_by('name')

    # all_workers — samo radnici iste firme
    if company_user_ids is not None:
        all_workers = User.objects.filter(
            pk__in=company_user_ids, is_active=True
        ).order_by('last_name','first_name')
    else:
        all_workers = User.objects.filter(
            time_entries__date__gte=date_from, time_entries__date__lte=date_to,
        ).distinct().order_by('last_name','first_name')

    return render(request, 'worktime/manager_timesheet.html', {
        'workers_data': workers_data,
        'total_hours': sum(w['total_hours'] for w in workers_data.values()),
        'total_amount': sum(w['total_amount'] for w in workers_data.values()),
        'all_projects': all_projects, 'all_workers': all_workers,
        'selected_project': project_id, 'selected_workers': worker_ids,
        'date_from': date_from_str, 'date_to': date_to_str,
        'status_filter': status_filter,
        'pending_count': TimeEntry.objects.filter(
            status='PENDING',
            **(({'user_id__in': company_user_ids}) if company_user_ids is not None else {})
        ).count(),
        'entries_count': qs.count(), 'active_timers': active_timers,
    })


@login_required
def approve_entries(request):
    if request.method == 'POST':
        ids = request.POST.getlist('entry_ids')
        action = request.POST.get('action','approve')
        if ids:
            if action == 'approve':
                entries_qs = TimeEntry.objects.filter(pk__in=ids, status='PENDING').select_related('user', 'project')
                users_to_notify = {}
                for e in entries_qs:
                    users_to_notify.setdefault(e.user_id, {'user': e.user, 'count': 0, 'hours': 0})
                    users_to_notify[e.user_id]['count'] += 1
                    users_to_notify[e.user_id]['hours'] += float(e.duration) if e.duration else 0
                mark_ot = request.POST.get('mark_overtime') == '1'
                if mark_ot:
                    for entry in entries_qs:
                        entry.is_overtime = True
                        entry.overtime_hours = entry.duration
                        entry.status = 'APPROVED'
                        entry.approved_by = request.user
                        entry.approved_at = timezone.now()
                        entry.save()
                else:
                    TimeEntry.objects.filter(pk__in=ids, status='PENDING').update(
                        status='APPROVED', approved_by=request.user, approved_at=timezone.now())
                ot_label = ' (prekovremeno)' if mark_ot else ''
                messages.success(request, f'✓ {len(ids)} unosa odobreno{ot_label}.')
                # Push notify workers
                for uid, info in users_to_notify.items():
                    try:
                        notify(
                            info['user'], 'timesheet_approved',
                            'Sati odobreni ✓',
                            f'{info["count"]} unosa · {info["hours"]:.1f}h odobreno',
                            url='/worktime/',
                            sender=request.user,
                        )
                    except Exception:
                        pass
            elif action == 'reject':
                reason = request.POST.get('rejection_reason', '').strip()
                reject_entries = TimeEntry.objects.filter(pk__in=ids).select_related('user')
                users_reject = {}
                for e in reject_entries:
                    users_reject.setdefault(e.user_id, e.user)
                TimeEntry.objects.filter(pk__in=ids).update(
                    status='REJECTED',
                    rejection_reason=reason,
                )
                messages.warning(request, f'{len(ids)} unosa odbijeno.' + (f' Razlog: {reason}' if reason else ''))
                # Push notify workers about rejection
                for uid, user in users_reject.items():
                    try:
                        notify(
                            user, 'timesheet_rejected',
                            'Sati odbijeni ✗',
                            f'{len(ids)} unosa odbijeno' + (f': {reason}' if reason else ''),
                            url='/worktime/',
                            sender=request.user,
                        )
                    except Exception:
                        pass
        return redirect('worktime:ts_manager')

    # GET logika: Prikaz unosa koji čekaju odobrenje
    pending_entries = TimeEntry.objects.filter(status='PENDING').select_related('user', 'project')
    return render(request, 'worktime/approve_list.html', {'entries': pending_entries})



# ═══════════════════════════════════════════════════════════════
# PDF EXPORT
# ═══════════════════════════════════════════════════════════════

@login_required
def timesheet_pdf(request):
    today = date.today()
    date_from = date.fromisoformat(request.GET.get('date_from', str(today.replace(day=1))))
    date_to = date.fromisoformat(request.GET.get('date_to', str(today)))
    project_id = request.GET.get('project','')
    worker_ids = request.GET.getlist('workers')
    mode = request.GET.get('mode','detailed')

    # ── Company scope ─────────────────────────────────────────
    _pdf_company = _user_company(request.user)
    qs = TimeEntry.objects.select_related('user','project')
    qs = qs.filter(date__gte=date_from, date__lte=date_to)
    if _pdf_company:
        from accounts.models import UserProfile as _UP
        _company_uids = list(_UP.objects.filter(company=_pdf_company).values_list('user_id', flat=True))
        qs = qs.filter(user_id__in=_company_uids)
    if project_id: qs = qs.filter(project_id=project_id)
    if worker_ids: qs = qs.filter(user_id__in=worker_ids)
    qs = qs.order_by('user__last_name','date')

    workers_data = {}
    for te in qs:
        uid = te.user_id
        if uid not in workers_data:
            try: rate = te.user.employeeprofile.hourly_rate
            except Exception: rate = te.project.hourly_rate
            workers_data[uid] = {
                'user': te.user, 'entries': [], 'hourly_rate': rate,
                'emp': getattr(te.user,'employeeprofile', None),
                'oib': getattr(getattr(te.user,'employeeprofile',None),'tax_id',''),
                'iban': getattr(getattr(te.user,'employeeprofile',None),'bank_account',''),
                'total_hours': Decimal('0'), 'total_amount': Decimal('0'),
            }
        workers_data[uid]['entries'].append(te)
        workers_data[uid]['total_hours'] += te.duration
        workers_data[uid]['total_amount'] += te.billing_amount

    # Company-scoped header za PDF
    config = None  # Više ne koristimo FiscalConfig singleton
    project_obj = None
    if project_id:
        try: project_obj = Project.objects.get(pk=project_id)
        except Exception: pass

    _country = getattr(_pdf_company, 'country', 'HR') or 'HR'
    html = render_to_string('worktime/timesheet_pdf.html', {
        'workers_data': workers_data, 'date_from': date_from, 'date_to': date_to,
        'mode': mode, 'company': _pdf_company, 'generated_at': timezone.now(),
        'project': project_obj, 'request': request,
        'total_hours': sum(w['total_hours'] for w in workers_data.values()),
        'total_amount': sum(w['total_amount'] for w in workers_data.values()),
        'is_de': _country == 'DE',
        'country': _country,
    })
    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="sati_{date_from}_{date_to}.pdf"'
        return resp
    except Exception:
        return HttpResponse(html)


# ═══════════════════════════════════════════════════════════════
# BILLING
# ═══════════════════════════════════════════════════════════════

@login_required
def bill_entries(request):
    if request.method != 'POST': return redirect('worktime:ts_manager')
    entry_ids = request.POST.getlist('entry_ids')
    bill_mode = request.POST.get('bill_mode','detailed')
    worker_ids_b = request.POST.getlist('bill_workers')
    date_from_str = request.POST.get('date_from', str(date.today().replace(day=1)))
    date_to_str = request.POST.get('date_to', str(date.today()))
    project_id = request.POST.get('project','')

    qs = TimeEntry.objects.select_related('user','project')
    if entry_ids:
        qs = qs.filter(pk__in=entry_ids, status='APPROVED', is_billed=False)
    elif worker_ids_b:
        try:
            df = date.fromisoformat(date_from_str)
            dt = date.fromisoformat(date_to_str)
        except Exception:
            df, dt = date.today().replace(day=1), date.today()
        qs = qs.filter(user_id__in=worker_ids_b, date__gte=df, date__lte=dt,
                       status='APPROVED', is_billed=False)
        if project_id: qs = qs.filter(project_id=project_id)

    if not qs.exists():
        messages.warning(request, _('Nema odobrenih nefakturiranih sati.'))
        return redirect('worktime:ts_manager')

    from invoicing.models import Invoice, InvoiceItem
    today_d = date.today()
    try:
        from invoicing.fiscal_models import FiscalConfig
        cfg = FiscalConfig.get()
        issuer_name = cfg.company_name; issuer_oib = cfg.oib
        issuer_addr = cfg.address; issuer_iban = cfg.default_iban
        prefix = cfg.invoice_prefix_hr; next_num = cfg.next_invoice_number
    except Exception:
        issuer_name='LIMIT Connect'; issuer_oib=''
        issuer_addr='Kralja Tomislava 1a, Čepin'; issuer_iban=''
        prefix='KNJ'; next_num=Invoice.objects.count()+1

    inv = Invoice.objects.create(
        doctype='R', country='HR',
        number=f"{prefix}-{today_d.year}-{next_num:04d}",
        date_issued=timezone.now(), date_due=today_d+timedelta(days=15),
        client_name='', payment_method='TRANSAKCIJSKI', currency='EUR',
        issuer_name=issuer_name, issuer_oib=issuer_oib,
        issuer_address=issuer_addr, issuer_iban=issuer_iban,
        status='DRAFT', created_by=request.user,
        note='Radni sati prema evidenciji',
    )

    if bill_mode == 'summary':
        groups = {}
        for te in qs:
            key = f"{te.user_id}_{te.project_id}"
            if key not in groups:
                try: rate = te.user.employeeprofile.hourly_rate
                except Exception: rate = te.project.hourly_rate
                groups[key] = {'desc': f"{te.user.get_full_name() or te.user.username} – {te.project.name}",
                               'hours': Decimal('0'), 'rate': rate}
            groups[key]['hours'] += te.duration
        for g in groups.values():
            InvoiceItem.objects.create(invoice=inv, description=g['desc'],
                quantity=g['hours'], unit='h', unit_price=g['rate'],
                total_price=g['hours']*g['rate'], tax_rate=25)
    else:
        for te in qs:
            try: rate = te.user.employeeprofile.hourly_rate
            except Exception: rate = te.project.hourly_rate
            name = te.user.get_full_name() or te.user.username
            InvoiceItem.objects.create(invoice=inv,
                description=f"{name} | {te.project.name} | {te.date.strftime('%d.%m.%Y')} | {te.description[:40]}",
                quantity=te.duration, unit='h', unit_price=rate,
                total_price=te.duration*rate, tax_rate=25)

    qs.update(is_billed=True, invoice=inv)
    inv.recalculate(); inv.save()
    try: cfg.next_invoice_number = next_num+1; cfg.save()
    except Exception: pass
    messages.success(request, f'✓ Faktura {inv.number} kreirana! Ukupno: {inv.total} EUR')
    return redirect(f'/invoicing/{inv.pk}/edit/')


# ═══════════════════════════════════════════════════════════════
# ANALITIKA
# ═══════════════════════════════════════════════════════════

@login_required
def timesheet_analytics(request):
    """Worktime analytics — daily hours chart, project distribution, task breakdown, top workers."""
    import json
    import calendar
    from django.db.models import Avg, F, Q
    from django.db.models.functions import TruncDate, TruncWeek

    company = _user_company(request.user)
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month_start = today.replace(day=1)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    # Company-scoped user IDs
    from accounts.models import UserProfile as _UP
    if company:
        company_uids = list(_UP.objects.filter(company=company).values_list('user_id', flat=True))
    else:
        company_uids = [request.user.pk]

    base_qs = TimeEntry.objects.filter(user_id__in=company_uids)

    # ── YTD totals ─────────────────────────────────────────────
    ytd_agg = base_qs.filter(
        date__gte=year_start, date__lte=today
    ).aggregate(
        total_hours=Sum('duration'),
        total_amount=Sum('billing_amount'),
    )
    ytd_hours = ytd_agg['total_hours'] or Decimal('0')
    ytd_amount = ytd_agg['total_amount'] or Decimal('0')

    # ── By project (YTD) ──────────────────────────────────────
    by_project = list(base_qs.filter(
        date__gte=year_start, date__lte=today
    ).values(
        'project__name', 'project__code', 'project__color'
    ).annotate(
        total_hours=Sum('duration'),
        total_amount=Sum('billing_amount'),
        entry_count=Count('id'),
    ).order_by('-total_hours')[:15])

    # ── By worker (current month) ─────────────────────────────
    by_worker = list(base_qs.filter(
        date__gte=month_start, date__lte=today
    ).values(
        'user__first_name', 'user__last_name', 'user__username'
    ).annotate(
        total_hours=Sum('duration'),
        total_amount=Sum('billing_amount'),
    ).order_by('-total_hours')[:10])

    # ── Project budget tracking ───────────────────────────────
    projects_budget = []
    for proj in Project.objects.filter(company=company, status='ACTIVE', budget_hours__isnull=False):
        if proj.budget_hours and proj.budget_hours > 0:
            hours_used = base_qs.filter(project=proj).aggregate(s=Sum('duration'))['s'] or Decimal('0')
            projects_budget.append({
                'project': proj,
                'hours_used': hours_used,
                'budget_hours': proj.budget_hours,
                'percentage': min(100, round(float(hours_used) / float(proj.budget_hours) * 100)),
            })

    # ── Weekly trend (last 12 weeks) ──────────────────────────
    weekly = []
    for i in range(11, -1, -1):
        w_start = today - timedelta(weeks=i, days=today.weekday())
        w_end = w_start + timedelta(days=6)
        w_hours = base_qs.filter(
            date__gte=w_start, date__lte=w_end
        ).aggregate(s=Sum('duration'))['s'] or Decimal('0')
        weekly.append({
            'week': f"{w_start.strftime('%d.%m')}",
            'hours': float(w_hours),
        })

    return render(request, 'worktime/analytics.html', {
        'year': year,
        'ytd_hours': ytd_hours,
        'ytd_amount': ytd_amount,
        'by_project': by_project,
        'by_worker': by_worker,
        'projects_budget': projects_budget,
        'weekly': weekly,
    })



@login_required
def billable_hours(request):
    """Billable hours overview — approved, unbilled entries grouped by project."""
    company = _user_company(request.user)
    today = date.today()

    # Company-scoped user IDs
    from accounts.models import UserProfile as _UP
    if company:
        company_uids = list(_UP.objects.filter(company=company).values_list('user_id', flat=True))
    else:
        company_uids = [request.user.pk]

    # Filters
    date_from = request.GET.get('date_from', str(today.replace(day=1)))
    date_to = request.GET.get('date_to', str(today))
    selected_worker = request.GET.get('worker', '')

    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except (ValueError, TypeError):
        df, dt = today.replace(day=1), today

    qs = TimeEntry.objects.filter(
        user_id__in=company_uids,
        status='APPROVED',
        is_billed=False,
        date__gte=df, date__lte=dt,
    ).select_related('user', 'project')

    if selected_worker:
        qs = qs.filter(user_id=selected_worker)

    # POST: bulk mark as billed
    if request.method == 'POST':
        mark_ids = request.POST.getlist('entry_ids')
        if mark_ids:
            marked = TimeEntry.objects.filter(
                pk__in=mark_ids, status='APPROVED', is_billed=False
            ).update(is_billed=True)
            messages.success(request, f'\u2713 {marked} unosa oznaceno kao naplaceno.')
        return redirect('worktime:billable')

    # Group by project
    groups = []
    project_map = {}
    for entry in qs.order_by('project__name', 'date'):
        pid = entry.project_id
        if pid not in project_map:
            try:
                rate = entry.user.employeeprofile.hourly_rate
            except Exception:
                rate = entry.project.hourly_rate
            project_map[pid] = {
                'project_name': entry.project.name,
                'client_name': getattr(entry.project, 'client_name', ''),
                'entries': [],
                'entry_ids': [],
                'total_hours': Decimal('0'),
                'total_amount': Decimal('0'),
                'entry_count': 0,
            }
        g = project_map[pid]
        try:
            rate = entry.user.employeeprofile.hourly_rate
        except Exception:
            rate = entry.project.hourly_rate
        amount = entry.billing_amount if entry.billing_amount else entry.duration * rate
        entry.rate = rate
        entry.amount = amount
        g['entries'].append(entry)
        g['entry_ids'].append(entry.pk)
        g['total_hours'] += entry.duration
        g['total_amount'] += amount
        g['entry_count'] += 1

    groups = sorted(project_map.values(), key=lambda x: x['total_hours'], reverse=True)

    total_hours = sum(g['total_hours'] for g in groups)
    total_amount = sum(g['total_amount'] for g in groups)
    total_entries = sum(g['entry_count'] for g in groups)
    total_projects = len(groups)

    all_workers = User.objects.filter(pk__in=company_uids, is_active=True).order_by('last_name', 'first_name')

    return render(request, 'worktime/billable_hours.html', {
        'groups': groups,
        'total_hours': total_hours,
        'total_amount': total_amount,
        'total_entries': total_entries,
        'total_projects': total_projects,
        'all_workers': all_workers,
        'date_from': date_from,
        'date_to': date_to,
        'selected_worker': selected_worker,
    })


@login_required
def export_timesheet_excel(request):
    """Export timesheet to Excel (.xlsx) via openpyxl."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    company = _user_company(request.user)
    today = date.today()

    # Parse params
    start_str = request.GET.get('start_date', str(today.replace(day=1)))
    end_str = request.GET.get('end_date', str(today))
    user_id = request.GET.get('user_id', '')

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except (ValueError, TypeError):
        start_date, end_date = today.replace(day=1), today

    # Company-scoped
    from accounts.models import UserProfile as _UP
    if company:
        company_uids = list(_UP.objects.filter(company=company).values_list('user_id', flat=True))
    else:
        company_uids = [request.user.pk]

    qs = TimeEntry.objects.filter(
        user_id__in=company_uids,
        date__gte=start_date, date__lte=end_date,
    ).select_related('user', 'project').order_by('date', 'user__last_name', 'start_time')

    if user_id:
        qs = qs.filter(user_id=user_id)

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Timesheet {start_date.strftime('%d.%m')}-{end_date.strftime('%d.%m.%Y')}"

    # Header style
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='1e293b', end_color='1e293b', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    headers = ['Datum', 'Radnik', 'Projekt', 'Vrsta posla', 'Sati', 'Pocetak', 'Kraj', 'Status', 'Iznos (EUR)']
    col_widths = [12, 22, 20, 16, 8, 8, 8, 12, 12]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data rows
    total_hours = Decimal('0')
    total_amount = Decimal('0')
    for row_idx, entry in enumerate(qs, 2):
        task_label = dict(TimeEntry.TASK_TYPES).get(entry.task_type, entry.task_type)
        status_label = dict(TimeEntry.STATUS_CHOICES).get(entry.status, entry.status)
        values = [
            entry.date.strftime('%d.%m.%Y'),
            entry.user.get_full_name() or entry.user.username,
            entry.project.name,
            task_label,
            float(entry.duration),
            entry.start_time.strftime('%H:%M') if entry.start_time else '',
            entry.end_time.strftime('%H:%M') if entry.end_time else '',
            status_label,
            float(entry.billing_amount),
        ]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border
            if col_idx in (5, 9):
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right')
        total_hours += entry.duration
        total_amount += entry.billing_amount

    # Summary row
    sum_row = qs.count() + 2
    ws.cell(row=sum_row, column=1, value='UKUPNO').font = Font(bold=True)
    ws.cell(row=sum_row, column=5, value=float(total_hours)).font = Font(bold=True)
    ws.cell(row=sum_row, column=5).number_format = '#,##0.00'
    ws.cell(row=sum_row, column=9, value=float(total_amount)).font = Font(bold=True)
    ws.cell(row=sum_row, column=9).number_format = '#,##0.00'

    # Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"timesheet_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def inspector_print(request):
    """Inspector print view."""
    return render(request, 'worktime/worker_dashboard.html', _empty_ctx())


@login_required
def payroll_summary(request):
    """Payroll summary — per-employee hours breakdown and gross pay calculation."""
    company = _user_company(request.user)
    today = date.today()

    # Month/year from GET
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    import calendar
    _, last_day = calendar.monthrange(year, month)
    period_start = date(year, month, 1)
    period_end = date(year, month, last_day)

    # Company-scoped user IDs
    from accounts.models import UserProfile as _UP
    if company:
        company_uids = list(_UP.objects.filter(company=company).values_list('user_id', flat=True))
    else:
        company_uids = [request.user.pk]

    employees = EmployeeProfile.objects.filter(
        user_id__in=company_uids, user__is_active=True
    ).select_related('user')

    payroll_data = []
    grand_total = Decimal('0')

    for emp in employees:
        entries = TimeEntry.objects.filter(
            user=emp.user,
            date__gte=period_start, date__lte=period_end,
        )

        total_hours = entries.aggregate(s=Sum('duration'))['s'] or Decimal('0')
        regular = entries.aggregate(s=Sum('regular_hours'))['s'] or Decimal('0')
        overtime = entries.aggregate(s=Sum('overtime_hours'))['s'] or Decimal('0')
        night = entries.aggregate(s=Sum('night_hours'))['s'] or Decimal('0')

        # If regular_hours field was not populated, estimate from duration
        if regular == 0 and total_hours > 0:
            regular = total_hours - overtime - night

        # Absence days
        absence_days = entries.exclude(absence_type='').exclude(absence_type__isnull=True).values('date').distinct().count()

        # Gross pay calculation
        base_rate = emp.hourly_rate or Decimal('20.00')
        ot_rate = emp.overtime_rate or (base_rate * Decimal('1.5'))
        night_bonus = base_rate * Decimal('0.25')  # 25% night supplement (HR ZOR)

        cost = (regular * base_rate) + (overtime * ot_rate) + (night * night_bonus)

        # Warnings: daily > 10h (ArbZG), weekly > 48h
        has_warnings = False
        daily_max = entries.values('date').annotate(
            day_total=Sum('duration')
        ).order_by('-day_total').first()
        if daily_max and daily_max['day_total'] > Decimal('10'):
            has_warnings = True

        payroll_data.append({
            'worker': emp.user,
            'employee': emp,
            'hours': total_hours,
            'regular': regular,
            'overtime': overtime,
            'night': night,
            'absence_days': absence_days,
            'rate': base_rate,
            'ot_rate': ot_rate,
            'cost': cost,
            'has_warnings': has_warnings,
        })
        grand_total += cost

    # Sort by total hours descending
    payroll_data.sort(key=lambda x: x['hours'], reverse=True)

    return render(request, 'worktime/payroll_summary.html', {
        'payroll_data': payroll_data,
        'grand_total': grand_total,
        'month': month,
        'year': year,
        'period_start': period_start,
        'period_end': period_end,
    })


def _empty_ctx():
    from datetime import date
    return {
        'hours_today': 0, 'hours_week': 0, 'hours_month': 0,
        'earnings_month': 0, 'hourly_rate': 0, 'daily_target': 8,
        'weekly_target': 40, 'week_progress': 0,
        'recent_entries': [], 'projects': [],
        'pending_count': 0, 'today': date.today(),
        'active_timer': None, 'week_days': [],
        'streak': 0, 'templates': [],
        'frequent_projects': [], 'daily_note': None,
        'task_types': [], 'burza_leads': [],
        'overtime_warnings': [],
    }


@login_required
def worker_mine(request):
    """
    /worktime/mine/ — mobilna stranica za radnika.
    Prikazuje vlastite sate. Nema satnica, nema financija.
    Zakon: ZOR + ArbZG §16.
    """
    from worktime.models import TimeEntry, EmployeeProfile
    from datetime import timedelta
    from decimal import Decimal

    company = _user_company(request.user)
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)

    week_entries = TimeEntry.objects.filter(
        user=request.user, company=company,
        date__range=(week_start, week_end),
    ).order_by('-date', 'start_time')

    month_entries = TimeEntry.objects.filter(
        user=request.user, company=company,
        date__range=(month_start, today),
    ).order_by('-date')

    week_hours = sum((e.duration or Decimal('0')) for e in week_entries)
    month_hours = sum((e.duration or Decimal('0')) for e in month_entries)

    try:
        ep = EmployeeProfile.objects.get(user=request.user, company=company)
        weekly_target = getattr(ep, 'weekly_hours', None) or Decimal('40')
    except EmployeeProfile.DoesNotExist:
        weekly_target = Decimal('40')
    monthly_target = weekly_target * 4

    return render(request, 'worktime/worker_mine.html', {
        'week_entries': week_entries,
        'month_entries': month_entries,
        'week_hours': week_hours,
        'month_hours': month_hours,
        'weekly_target': weekly_target,
        'monthly_target': monthly_target,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
    })


# ═══════════════════════════════════════════════════════════════
# CLOCK IN/OUT PAGE (mobile-first)
# ═══════════════════════════════════════════════════════════════

@login_required
def clock_inout(request):
    from worktime.models import TimeLog
    open_shift = TimeLog.objects.filter(user=request.user, status='OPEN').first()
    today_shifts = TimeLog.objects.filter(user=request.user, date=date.today()).order_by('-start_time')
    return render(request, 'worktime/clock_inout.html', {
        'open_shift': open_shift,
        'today_shifts': today_shifts,
    })


# ═══════════════════════════════════════════════════════════════
# DISPUTE — Radnik prijavljuje neslaganje s izmjenom sata
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def dispute_revision(request, revision_id):
    """Radnik prijavljuje neslaganje s izmjenom sata."""
    from worktime.models import TimeLogRevision
    from django.utils import timezone
    from django.http import JsonResponse

    rev = get_object_or_404(
        TimeLogRevision,
        pk=revision_id,
        time_entry__user=request.user  # samo SVOJE revizije
    )
    if rev.disputed_by:
        return JsonResponse({'error': _('Već prijavljeno.')}, status=400)

    rev.disputed_by = request.user
    rev.disputed_at = timezone.now()
    rev.dispute_note = request.POST.get('note', '').strip()
    # Bypass append-only za dispute polja (ovo je jedini dozvoljen update)
    TimeLogRevision.objects.filter(pk=rev.pk).update(
        disputed_by=request.user,
        disputed_at=timezone.now(),
        dispute_note=rev.dispute_note,
    )

    # Notifikacija manageru
    try:
        from notifications.services import notify
        manager = rev.changed_by
        if manager:
            notify(
                manager,
                f'Prigovor na izmjenu sata: {request.user.get_full_name()} ne slaže se s izmjenom {rev.field_name}',
                url=f'/hr/worktime/ts/manager/',
            )
    except Exception:
        pass

    # Audit
    try:
        from core.models import BookingSignature
        BookingSignature.log(
            request, 'update',
            target_model='TimeLogRevision',
            target_id=str(rev.pk),
            target_repr=f'Dispute: {request.user.get_full_name()} — {rev.field_name}',
        )
    except Exception:
        pass

    return JsonResponse({
        'ok': True,
        'msg': _('Prigovor zabilježen. Voditelj je obaviješten.'),
    })
