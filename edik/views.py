"""EDIK — e-Porezna views."""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.company_utils import get_user_company


@login_required
def edik_dashboard(request):
    """Dashboard — pregled predaja i rokovi."""
    company = get_user_company(request)
    from edik.models import TaxCalendar, TaxSubmission

    today = date.today()

    # Upcoming deadlines (next 30 days)
    upcoming = TaxCalendar.objects.filter(
        company=company,
        deadline__gte=today,
        deadline__lte=today + timedelta(days=30),
        is_completed=False,
    ).select_related("form_type")

    # Overdue
    overdue = TaxCalendar.objects.filter(
        company=company,
        deadline__lt=today,
        is_completed=False,
    ).select_related("form_type")

    # Recent submissions
    submissions = (
        TaxSubmission.objects.filter(
            company=company,
            period_year=today.year,
        )
        .select_related("form_type")
        .order_by("-period_month", "form_type__code")
    )

    # Stats
    stats = {
        "total": submissions.count(),
        "accepted": submissions.filter(status="accepted").count(),
        "submitted": submissions.filter(status="submitted").count(),
        "rejected": submissions.filter(status="rejected").count(),
        "pending": submissions.filter(status__in=["draft", "ready"]).count(),
        "overdue": overdue.count(),
    }

    return render(
        request,
        "edik/dashboard.html",
        {
            "company": company,
            "upcoming": upcoming,
            "overdue": overdue,
            "submissions": submissions,
            "stats": stats,
            "today": today,
        },
    )


@login_required
def edik_submission_detail(request, pk):
    """Detalj predaje obrasca."""
    company = get_user_company(request)
    from edik.models import TaxSubmission

    sub = get_object_or_404(TaxSubmission, pk=pk, company=company)
    return render(
        request,
        "edik/submission_detail.html",
        {
            "submission": sub,
            "company": company,
        },
    )


@login_required
def edik_submission_create(request):
    """Kreiranje nove predaje."""
    company = get_user_company(request)
    from edik.models import TaxFormType, TaxSubmission

    if request.method == "POST":
        form_type = get_object_or_404(TaxFormType, pk=request.POST.get("form_type"))
        year = int(request.POST.get("period_year", timezone.now().year))
        month = request.POST.get("period_month")
        month = int(month) if month else None

        # Calculate deadline
        if month:
            deadline_month = month + 1 if month < 12 else 1
            deadline_year = year if month < 12 else year + 1
        else:
            deadline_month = form_type.deadline_day
            deadline_year = year + 1
        try:
            dl = date(deadline_year, deadline_month, min(form_type.deadline_day, 28))
        except ValueError:
            dl = date(deadline_year, deadline_month, 28)

        sub, created = TaxSubmission.objects.get_or_create(
            company=company,
            form_type=form_type,
            period_year=year,
            period_month=month,
            defaults={
                "deadline_date": dl,
                "status": "draft",
                "notes": request.POST.get("notes", ""),
            },
        )

        if request.FILES.get("xml_file"):
            sub.xml_file = request.FILES["xml_file"]
            sub.status = "ready"
            sub.prepared_date = timezone.now()
            sub.save()

        if created:
            messages.success(request, f"{form_type.code} kreiran za {month or ''}/{year}")
        else:
            messages.info(request, f"{form_type.code} vec postoji za taj period.")

        return redirect("edik:detail", pk=sub.pk)

    form_types = TaxFormType.objects.all()
    now = timezone.now()
    return render(
        request,
        "edik/submission_form.html",
        {
            "company": company,
            "form_types": form_types,
            "current_year": now.year,
            "years": range(now.year, now.year - 3, -1),
            "months": range(1, 13),
        },
    )


@login_required
def edik_submission_update_status(request, pk):
    """Azuriranje statusa predaje."""
    company = get_user_company(request)
    from edik.models import TaxSubmission

    sub = get_object_or_404(TaxSubmission, pk=pk, company=company)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(TaxSubmission.STATUS_CHOICES):
            sub.status = new_status

            if new_status == "submitted":
                sub.submitted_date = timezone.now()
                sub.submitted_by = request.user
                sub.reference_number = request.POST.get("reference_number", "")
            elif new_status == "accepted":
                sub.response_date = timezone.now()
            elif new_status == "rejected":
                sub.response_date = timezone.now()
                sub.rejection_reason = request.POST.get("rejection_reason", "")

            if request.FILES.get("response_xml"):
                sub.response_xml = request.FILES["response_xml"]

            sub.save()
            messages.success(request, f"Status azuriran: {sub.get_status_display()}")

            # Mark calendar entry as completed if accepted
            if new_status == "accepted":
                from edik.models import TaxCalendar

                TaxCalendar.objects.filter(
                    company=company,
                    form_type=sub.form_type,
                    period_year=sub.period_year,
                    period_month=sub.period_month,
                ).update(is_completed=True, submission=sub)

    return redirect("edik:detail", pk=pk)


@login_required
def edik_calendar(request):
    """Porezni kalendar — godisnji pregled."""
    company = get_user_company(request)
    from edik.models import TaxCalendar

    year = int(request.GET.get("year", date.today().year))

    entries = (
        TaxCalendar.objects.filter(
            company=company,
            period_year=year,
        )
        .select_related("form_type", "submission")
        .order_by("deadline")
    )

    # Group by month
    by_month = {}
    for e in entries:
        m = e.deadline.month
        by_month.setdefault(m, []).append(e)

    return render(
        request,
        "edik/calendar.html",
        {
            "company": company,
            "year": year,
            "by_month": by_month,
            "months": range(1, 13),
        },
    )


@login_required
def edik_generate_calendar(request):
    """Auto-generiranje kalendarskih unosa za godinu."""
    company = get_user_company(request)
    from edik.models import TaxCalendar, TaxFormType

    year = int(request.POST.get("year", date.today().year))
    created_count = 0

    for ft in TaxFormType.objects.all():
        if ft.frequency == "monthly":
            for month in range(1, 13):
                dl_month = month + 1 if month < 12 else 1
                dl_year = year if month < 12 else year + 1
                dl_day = min(ft.deadline_day, 28)
                dl = date(dl_year, dl_month, dl_day)
                _, created = TaxCalendar.objects.get_or_create(
                    company=company, form_type=ft, period_year=year, period_month=month, defaults={"deadline": dl}
                )
                if created:
                    created_count += 1

        elif ft.frequency == "quarterly":
            for q in [1, 2, 3, 4]:
                month = q * 3  # March, June, Sep, Dec
                dl_month = month + 1 if month < 12 else 1
                dl_year = year if month < 12 else year + 1
                dl_day = min(ft.deadline_day, 28)
                dl = date(dl_year, dl_month, dl_day)
                _, created = TaxCalendar.objects.get_or_create(
                    company=company, form_type=ft, period_year=year, period_month=month, defaults={"deadline": dl}
                )
                if created:
                    created_count += 1

        elif ft.frequency == "yearly":
            dl_day = min(ft.deadline_day, 28)
            # Yearly forms: deadline is in the next year typically
            dl = date(year + 1, 1, dl_day)  # Will be overridden per form
            _, created = TaxCalendar.objects.get_or_create(
                company=company, form_type=ft, period_year=year, period_month=None, defaults={"deadline": dl}
            )
            if created:
                created_count += 1

    messages.success(request, f"Generirano {created_count} unosa u porezni kalendar za {year}.")
    return redirect("edik:calendar")
