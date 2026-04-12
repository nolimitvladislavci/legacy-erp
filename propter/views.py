"""Propter views."""
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.utils.translation import gettext as _

from django.db import models as db_models
from .models import BillingPeriod, Otpremnica, OtpremnicaItem, PropterConfig, EkoStats
from .services.aggregate import close_period, aggregate_to_eracun


def _company(request):
    try:
        from core.company_utils import get_user_company
        return get_user_company(request)
    except Exception:
        return request.user.profile.company


# ─────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    company = _company(request)
    now = timezone.now()

    current_period = BillingPeriod.objects.filter(
        company=company, year=now.year, month=now.month
    ).first()

    recent_otpremnice = Otpremnica.objects.filter(
        company=company
    ).select_related("billing_period")[:10]

    recent_periods = BillingPeriod.objects.filter(
        company=company
    )[:6]

    try:
        tenant = company.propter_config
    except PropterConfig.DoesNotExist:
        tenant = None

    try:
        eko = EkoStats.objects.filter(
            company=company, year=now.year
        ).order_by("-month").first()
    except Exception:
        eko = None

    ctx = {
        "current_period": current_period,
        "recent_otpremnice": recent_otpremnice,
        "recent_periods": recent_periods,
        "tenant": tenant,
        "eko": eko,
        "page_title": "Propter Hub",
    }
    return render(request, "propter/dashboard.html", ctx)


# ─────────────────────────────────────────────────────────────
# BillingPeriod
# ─────────────────────────────────────────────────────────────

@login_required
def period_list(request):
    company = _company(request)
    periods = BillingPeriod.objects.filter(company=company)
    return render(request, "propter/period_list.html", {
        "periods": periods, "page_title": "Obracunski periodi"
    })


@login_required
def period_detail(request, pk):
    company = _company(request)
    period = get_object_or_404(BillingPeriod, pk=pk, company=company)
    otpremnice = period.otpremnice.all().prefetch_related("items")
    try:
        eko = period.eko_stats
    except Exception:
        eko = None
    return render(request, "propter/period_detail.html", {
        "period": period, "otpremnice": otpremnice, "eko": eko,
        "page_title": str(period)
    })


@login_required
@require_POST
def period_close(request, pk):
    company = _company(request)
    period = get_object_or_404(BillingPeriod, pk=pk, company=company)
    try:
        close_period(period, user=request.user)
        messages.success(request, _("Period zatvoren. Ukupno: {:.2f} EUR ({} otpremnica)").format(
            period.total_with_tax, period.otpremnica_count
        ))
    except Exception as e:
        messages.error(request, str(e))
    return redirect("propter:period_detail", pk=pk)


@login_required
@require_POST
def period_aggregate(request, pk):
    company = _company(request)
    period = get_object_or_404(BillingPeriod, pk=pk, company=company)
    try:
        eracun = aggregate_to_eracun(period, user=request.user)
        messages.success(request,
            _("Zbirni e-Racun kreiran: {}. Ukupno: {:.2f} EUR.").format(
                eracun.invoice_number, float(eracun.total)
            ))
    except Exception as e:
        messages.error(request, str(e))
    return redirect("propter:period_detail", pk=pk)


# ─────────────────────────────────────────────────────────────
# Otpremnice
# ─────────────────────────────────────────────────────────────

@login_required
def otpremnica_list(request):
    company = _company(request)
    status_filter = request.GET.get("status", "")
    qs = Otpremnica.objects.filter(company=company).select_related("billing_period")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, "propter/otpremnica_list.html", {
        "otpremnice": qs[:100],
        "status_filter": status_filter,
        "status_choices": Otpremnica.Status.choices,
        "page_title": "Otpremnice",
    })


@login_required
def otpremnica_create(request):
    company = _company(request)
    if request.method == "POST":
        d = request.POST
        try:
            otp = Otpremnica.objects.create(
                company=company,
                issue_date=d.get("issue_date") or timezone.now().date(),
                recipient_name=d.get("recipient_name", ""),
                recipient_oib=d.get("recipient_oib", ""),
                recipient_address=d.get("recipient_address", ""),
                subtotal=Decimal(d.get("subtotal", "0")),
                tax_amount=Decimal(d.get("tax_amount", "0")),
                total=Decimal(d.get("total", "0")),
                source=Otpremnica.Source.MANUAL,
                status=Otpremnica.Status.ISSUED,
                note=d.get("note", ""),
                created_by=request.user,
            )
            messages.success(request, _("Otpremnica {} kreirana.").format(otp.number))
            return redirect("propter:otpremnica_detail", pk=otp.pk)
        except Exception as e:
            messages.error(request, str(e))

    return render(request, "propter/otpremnica_form.html", {
        "page_title": "Nova otpremnica"
    })


@login_required
def otpremnica_detail(request, pk):
    company = _company(request)
    otp = get_object_or_404(Otpremnica, pk=pk, company=company)
    return render(request, "propter/otpremnica_detail.html", {
        "otp": otp, "items": otp.items.all(),
        "page_title": "OTP-{}".format(otp.number)
    })


# ─────────────────────────────────────────────────────────────
# Eko dashboard
# ─────────────────────────────────────────────────────────────

@login_required
def eko_dashboard(request):
    company = _company(request)
    now = timezone.now()
    stats = EkoStats.objects.filter(company=company).order_by("-year", "-month")[:12]
    ytd = EkoStats.objects.filter(
        company=company, year=now.year
    ).first()
    return render(request, "propter/eko_dashboard.html", {
        "stats": stats, "ytd": ytd,
        "page_title": "Eko statistika",
    })


@login_required
def eko_month(request, year, month):
    company = _company(request)
    eko = get_object_or_404(EkoStats, company=company, year=year, month=month)
    return render(request, "propter/eko_month.html", {
        "eko": eko, "page_title": "{}/{:02d} Eko".format(year, month)
    })


# ─────────────────────────────────────────────────────────────
# PropterConfig settings
# ─────────────────────────────────────────────────────────────

@login_required
def tenant_settings(request):
    company = _company(request)
    tenant, created = PropterConfig.objects.get_or_create(
        company=company,
        defaults={"tier": PropterConfig.Tier.CLIENT, "monthly_fee": 0}
    )
    return render(request, "propter/tenant_settings.html", {
        "tenant": tenant, "page_title": "Propter postavke"
    })


# ─────────────────────────────────────────────────────────────
# API endpointi (Synesis + vanjski)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def api_create_otpremnica(request):
    """POST -- API key autentikacija. Kreira otpremnicu iz vanjskog sustava."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    # Rate limiting: max 100 req/min per IP
    from django.core.cache import cache
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",")[0].strip() \
         or request.META.get("REMOTE_ADDR", "")
    rate_key = f"propter_api_rate:{ip}"
    hits = cache.get(rate_key, 0)
    if hits > 100:
        return JsonResponse({"error": "Rate limit exceeded (100/min)"}, status=429)
    cache.set(rate_key, hits + 1, 60)

    # Body size check (max 64KB)
    if len(request.body) > 65536:
        return JsonResponse({"error": "Request body too large (max 64KB)"}, status=413)

    api_key = request.headers.get("X-Propter-Key") or request.POST.get("api_key")
    if not api_key:
        return JsonResponse({"error": "API key obavezan"}, status=401)

    # Sanitize API key (prevent injection)
    if len(api_key) > 128 or not api_key.isalnum():
        return JsonResponse({"error": "Nevaljan API key format"}, status=401)

    try:
        tenant = PropterConfig.objects.select_related("company").get(
            company__eracun_config__api_key=api_key,
            is_active=True
        )
    except PropterConfig.DoesNotExist:
        return JsonResponse({"error": "Nevaljan API key"}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Nevaljan JSON"}, status=400)

    try:
        company = tenant.company
        # Input validation
        recipient_name = str(data.get("recipient_name", ""))[:200]
        recipient_oib = str(data.get("recipient_oib", ""))[:20]
        note = str(data.get("note", ""))[:1000]
        try:
            subtotal = Decimal(str(data.get("subtotal", "0")))
            tax_amount = Decimal(str(data.get("tax_amount", "0")))
            total = Decimal(str(data.get("total", "0")))
            if any(v < 0 or v > Decimal("99999999.99") for v in [subtotal, tax_amount, total]):
                return JsonResponse({"error": "Iznos izvan dozvoljenog raspona"}, status=400)
        except Exception:
            return JsonResponse({"error": "Neispravan format iznosa"}, status=400)

        otp = Otpremnica.objects.create(
            company=company,
            issue_date=data.get("issue_date") or timezone.now().date(),
            recipient_name=recipient_name,
            recipient_oib=recipient_oib,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=total,
            source=Otpremnica.Source.API,
            status=Otpremnica.Status.ISSUED,
            note=note,
        )
        return JsonResponse({
            "id": str(otp.pk),
            "number": otp.number,
            "billing_period": str(otp.billing_period),
            "status": "created",
        }, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
def api_period_status(request, pk):
    company = _company(request)
    period = get_object_or_404(BillingPeriod, pk=pk, company=company)
    return JsonResponse({
        "id": period.pk,
        "period": str(period),
        "status": period.status,
        "otpremnica_count": period.otpremnica_count,
        "total_with_tax": float(period.total_with_tax),
        "zbirni_invoice_number": period.zbirni_invoice_number,
        "invoiced_at": period.invoiced_at.isoformat() if period.invoiced_at else None,
    })


# ─────────────────────────────────────────────────────────────
# Faza C -- Javna eko stranica + ESG PDF
# ─────────────────────────────────────────────────────────────

def eko_public(request, slug):
    """Public eko page -- no login required.
    Company puts badge/link on their own website.
    URL: /propter/eko/public/<slug>/
    """
    from django.views.decorators.cache import cache_page
    from companies.models import Company

    # Sanitize slug
    if not slug or len(slug) > 100:
        from django.http import Http404
        raise Http404("Nevaljan slug.")

    company = get_object_or_404(Company, booking_slug=slug)

    # Check if public eco page is enabled
    try:
        config = company.propter_config
        if not config.public_eco_page:
            from django.http import Http404
            raise Http404("Eko stranica nije aktivirana.")
    except PropterConfig.DoesNotExist:
        from django.http import Http404
        raise Http404("Propter nije konfiguriran.")

    now = timezone.now()
    stats = EkoStats.objects.filter(company=company).order_by("-year", "-month")[:12]

    # Current year totals
    ytd = EkoStats.objects.filter(company=company, year=now.year)
    ytd_agg = {
        "paper": sum(e.paper_saved_sheets for e in ytd),
        "co2": sum(e.co2_saved_grams for e in ytd),
        "trees": sum(e.trees_equivalent for e in ytd),
        "eracuni": sum(e.eracuni_sent for e in ytd),
    }

    # Best badge this year
    badges = [e.badge_level for e in ytd if e.badge_level]
    badge_order = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4}
    best_badge = max(badges, key=lambda b: badge_order.get(b, 0)) if badges else ""

    return render(request, "propter/eko_public.html", {
        "company": company,
        "stats": stats,
        "ytd": ytd_agg,
        "best_badge": best_badge,
        "year": now.year,
    })


@login_required
def esg_pdf(request, year=None):
    """Generate ESG PDF report for the company (annual).
    Uses WeasyPrint. URL: /propter/eko/pdf/<year>/
    """
    import weasyprint
    from django.template.loader import render_to_string
    from django.http import HttpResponse

    company = _company(request)
    now = timezone.now()
    year = year or now.year

    stats = EkoStats.objects.filter(
        company=company, year=year
    ).order_by("month")

    if not stats.exists():
        messages.warning(request, _("Nema eko podataka za {}.").format(year))
        return redirect("propter:eko_dashboard")

    # Aggregates
    total_paper = sum(e.paper_saved_sheets for e in stats)
    total_co2 = sum(e.co2_saved_grams for e in stats)
    total_trees = sum(e.trees_equivalent for e in stats)
    total_eracuni = sum(e.eracuni_sent for e in stats)

    # Best badge
    badges = [e.badge_level for e in stats if e.badge_level]
    badge_order = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4}
    best_badge = max(badges, key=lambda b: badge_order.get(b, 0)) if badges else ""

    html = render_to_string("propter/esg_report_pdf.html", {
        "company": company,
        "year": year,
        "stats": stats,
        "total_paper": total_paper,
        "total_co2": total_co2,
        "total_trees": total_trees,
        "total_eracuni": total_eracuni,
        "best_badge": best_badge,
        "generated_at": now,
    })

    pdf = weasyprint.HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="ESG-Report-{}-{}.pdf"'.format(
        company.name.replace(" ", "_"), year
    )
    return response


# ─────────────────────────────────────────────────────────────
# Propter SaaS Landing / Sales page (public, no login)
# ─────────────────────────────────────────────────────────────

def propter_landing(request):
    """Public SaaS landing page — sells Propter e-Racun service."""
    # Live stats for social proof
    from django.core.cache import cache
    landing_data = cache.get("propter_landing_stats")
    if not landing_data:
        from registration.models import PropterTenant
        active = PropterTenant.objects.filter(is_active=True).count()
        total_eracuni = PropterTenant.objects.aggregate(
            t=db_models.Sum('eracuni_sent_total')
        )['t'] or 0
        # Round to nearest 10 for privacy (ne exact count)
        landing_data = {
            "active_tenants": max((active // 10) * 10, 10),
            "total_eracuni": max((total_eracuni // 100) * 100, 100) if total_eracuni else 0,
        }
        cache.set("propter_landing_stats", landing_data, 3600)  # 1h cache
    return render(request, "propter/landing.html", landing_data)


# -------------------------------------------------------------
# Propter Soba -- Document Processing Room
# -------------------------------------------------------------

@login_required
def propter_soba(request):
    """Propter Soba - document processing room with upload, AI parsing, and mobile camera."""
    company = _company(request)
    if not company:
        messages.error(request, _("Nema povezane tvrtke."))
        return redirect("/dashboard/")

    # Security: PropterConfig must exist and be active
    try:
        propter_config = company.propter_config
        if not propter_config.is_active:
            messages.warning(request, _("Propter modul nije aktivan za vašu tvrtku."))
            return redirect("propter:dashboard")
    except PropterConfig.DoesNotExist:
        messages.warning(request, _("Propter nije konfiguriran. Kontaktirajte administratora."))
        return redirect("propter:dashboard")

    from eracun.models import ERacunConfig
    config = ERacunConfig.objects.filter(company=company).first()

    from smart_import.models import ImportBatch
    recent_batches = ImportBatch.objects.filter(company=company).order_by("-created_at")[:10]

    now = timezone.now()
    current_period = BillingPeriod.objects.filter(
        company=company, year=now.year, month=now.month
    ).first()
    recent_otpremnice = Otpremnica.objects.filter(company=company).order_by("-created_at")[:5]

    total_batches = ImportBatch.objects.filter(company=company).count()
    confirmed_batches = ImportBatch.objects.filter(company=company, status="confirmed").count()
    pending_batches = ImportBatch.objects.filter(company=company, status__in=["pending", "processing"]).count()
    total_otp = Otpremnica.objects.filter(company=company).count()

    try:
        eko = EkoStats.objects.filter(company=company, year=now.year).order_by("-month").first()
    except Exception:
        eko = None

    return render(request, "propter/soba.html", {
        "company": company,
        "config": config,
        "recent_batches": recent_batches,
        "current_period": current_period,
        "recent_otpremnice": recent_otpremnice,
        "total_batches": total_batches,
        "confirmed_batches": confirmed_batches,
        "pending_batches": pending_batches,
        "total_otp": total_otp,
        "eko": eko,
        "page_title": "Propter Soba",
    })


# ════════════════════════════════════════════════════════════
# Fenix Inbox — Centralni dokumentni router (Sprint Fenix)
# ════════════════════════════════════════════════════════════

@login_required
def fenix_inbox(request):
    company = _company(request)
    if not company:
        from django.contrib import messages as _msg
        _msg.error(request, 'Nema tvrtke.')
        return redirect('/dashboard/')

    from smart_import.models import FenixInboxItem
    from django.core.paginator import Paginator
    from django.db.models import Sum

    status_f = request.GET.get('status', '')
    tip_f = request.GET.get('tip', '')
    izvor_f = request.GET.get('izvor', '')

    qs = FenixInboxItem.objects.filter(company=company).order_by('-created_at')
    if status_f:
        qs = qs.filter(status=status_f)
    if tip_f:
        qs = qs.filter(tip=tip_f)
    if izvor_f:
        qs = qs.filter(izvor=izvor_f)

    ukupno = FenixInboxItem.objects.filter(company=company).count()
    ceka = FenixInboxItem.objects.filter(company=company, status__in=['ceka', 'novo']).count()
    arhiv = FenixInboxItem.objects.filter(company=company, status='arhivirano').count()
    ura_eur = (FenixInboxItem.objects.filter(company=company, tip='ura', iznos__isnull=False)
               .aggregate(s=Sum('iznos'))['s'] or 0)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'propter/inbox.html', {
        'items': page, 'ukupno': ukupno, 'ceka': ceka,
        'arhiv': arhiv, 'ura_eur': ura_eur,
        'status_filter': status_f, 'tip_filter': tip_f, 'izvor_filter': izvor_f,
        'status_choices': FenixInboxItem.STATUS_CHOICES,
        'tip_choices': FenixInboxItem.TIP_CHOICES,
        'izvor_choices': FenixInboxItem.IZVOR_CHOICES,
        'page_title': 'Fenix Inbox',
    })


@login_required
def fenix_inbox_action(request, item_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    company = _company(request)
    from smart_import.models import FenixInboxItem
    try:
        item = FenixInboxItem.objects.get(pk=item_id, company=company)
    except FenixInboxItem.DoesNotExist:
        return JsonResponse({'error': 'Nije pronadjeno'}, status=404)

    action = request.POST.get('action', '')

    if action == 'arhiviraj':
        item.status = 'arhivirano'
        item.obradjeno_by = request.user
        item.save(update_fields=['status', 'obradjeno_by', 'updated_at'])
        return JsonResponse({'ok': True})

    if action == 'set_tip':
        novi = request.POST.get('tip', '')
        valid_tips = [c[0] for c in FenixInboxItem.TIP_CHOICES]
        if novi in valid_tips:
            item.tip = novi
            item.status = 'ceka'
            item.obradjeno_by = request.user
            item.save(update_fields=['tip', 'status', 'obradjeno_by', 'updated_at'])
            return JsonResponse({'ok': True, 'tip': novi})

    if action == 'usmjeri':
        dest = request.POST.get('odrediste', '')
        if dest in ('inventory', 'konto', 'arhiva', 'propter'):
            from django.utils import timezone as tz
            item.status = 'usmjereno'
            item.usmjereno_na = dest
            item.usmjereno_at = tz.now()
            item.obradjeno_by = request.user
            item.save(update_fields=['status', 'usmjereno_na', 'usmjereno_at', 'obradjeno_by', 'updated_at'])
            return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Nepoznata akcija'}, status=400)
