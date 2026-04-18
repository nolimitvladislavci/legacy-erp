"""
FENIX SENTINEL — Dashboard Views (PLAN_076)
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone


@login_required
def dashboard(request):
    """SENTINEL Command Center — sve kategorije alertova."""
    from sentinel.models import SentinelAlert, TemporalLedgerScore
    from sentinel.models_advisor import ObrascInstance, EUMatch, KalendarObveza

    company = getattr(request.user, "active_company", None)
    if not company:
        # Uzmi prvu firmu korisnika
        from companies.models import Company

        company = Company.active.filter(created_by=request.user).first()

    if not company:
        return render(request, "sentinel/dashboard.html", {"no_company": True})

    # Alertovi
    alerts_all = SentinelAlert.objects.filter(company=company, resolved=False).order_by("-severity", "-created_at")

    critical = alerts_all.filter(severity="critical")
    warning = alerts_all.filter(severity="warning")
    info = alerts_all.filter(severity="info")

    # Filtriranje po kategoriji
    category = request.GET.get("cat", "")
    if category:
        alerts_all = alerts_all.filter(category=category)

    # Stats
    total_unresolved = SentinelAlert.objects.filter(company=company, resolved=False).count()
    resolved_week = SentinelAlert.objects.filter(
        company=company, resolved=True, resolved_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).count()

    # Upcoming deadlines
    from datetime import date, timedelta

    today = date.today()
    upcoming = (
        ObrascInstance.objects.filter(
            company=company,
            status__in=["draft", "ready"],
            rok_podnosenja__gte=today,
            rok_podnosenja__lte=today + timedelta(days=30),
        )
        .select_related("tip")
        .order_by("rok_podnosenja")[:5]
    )

    # EU hot matches
    eu_hot = EUMatch.objects.filter(company=company, match_score__gte=70, status="recommended").select_related("fund")[
        :3
    ]

    # Calendar (next 7 days)
    calendar_items = KalendarObveza.objects.filter(
        company=company, is_completed=False, rok__gte=today, rok__lte=today + timedelta(days=7)
    ).order_by("rok")[:5]

    # Temporal scores low
    low_scores = TemporalLedgerScore.objects.filter(company=company, score__lt=60, reviewed=False).order_by("score")[:5]

    return render(
        request,
        "sentinel/dashboard.html",
        {
            "company": company,
            "alerts": alerts_all[:50],
            "critical": critical,
            "warning": warning,
            "info_alerts": info,
            "total_unresolved": total_unresolved,
            "resolved_week": resolved_week,
            "upcoming_deadlines": upcoming,
            "eu_hot": eu_hot,
            "calendar_items": calendar_items,
            "low_scores": low_scores,
            "active_category": category,
            "categories": SentinelAlert.CATEGORY,
        },
    )


@login_required
def alert_resolve(request, alert_id):
    """Označi alert kao riješen."""
    from sentinel.models import SentinelAlert

    company = _get_company(request)
    alert = get_object_or_404(SentinelAlert, pk=alert_id, company=company)
    alert.resolve(user=request.user)
    return JsonResponse({"ok": True})


@login_required
def alerts_resolve_all(request):
    """Označi sve alertove kategorije kao riješene."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    from sentinel.models import SentinelAlert

    company = _get_company(request)
    category = request.POST.get("category", "")
    qs = SentinelAlert.objects.filter(company=company, resolved=False)
    if category:
        qs = qs.filter(category=category)
    count = qs.count()
    from django.utils import timezone

    qs.update(resolved=True, resolved_at=timezone.now(), resolved_by=request.user)
    return JsonResponse({"ok": True, "resolved": count})


# ─── VIEWS — EU NAVIGATOR ────────────────────────────────────────────────────


@login_required
def eu_navigator(request):
    from sentinel.models_advisor import EUMatch, EUFundProfile

    company = _get_company(request)
    profile = EUFundProfile.objects.filter(company=company).first()
    matches = EUMatch.objects.filter(company=company).select_related("fund").order_by("-match_score")[:20]

    total_potential = sum(m.potential_eur for m in matches)
    hot = [m for m in matches if m.match_score >= 75]

    return render(
        request,
        "sentinel/eu_navigator.html",
        {
            "company": company,
            "profile": profile,
            "matches": matches,
            "total_potential": total_potential,
            "hot_matches": hot,
        },
    )


@login_required
def eu_match_detail(request, match_id):
    from sentinel.models_advisor import EUMatch

    company = _get_company(request)
    match = get_object_or_404(EUMatch, pk=match_id, company=company)
    return render(request, "sentinel/eu_match_detail.html", {"company": company, "match": match})


# ─── VIEWS — OBRASCI ENGINE ───────────────────────────────────────────────────


@login_required
def obrasci_lista(request):
    from sentinel.models_advisor import ObrascInstance
    from datetime import date

    company = _get_company(request)
    today = date.today()

    obrasci = ObrascInstance.objects.filter(company=company).select_related("tip").order_by("rok_podnosenja")

    overdue = obrasci.filter(rok_podnosenja__lt=today, status__in=["draft", "ready"])
    pending = obrasci.filter(rok_podnosenja__gte=today, status__in=["draft", "ready"])
    submitted = obrasci.filter(status__in=["submitted", "accepted"])

    return render(
        request,
        "sentinel/obrasci_lista.html",
        {
            "company": company,
            "overdue": overdue,
            "pending": pending,
            "submitted": submitted,
        },
    )


@login_required
def obrazac_detail(request, pk):
    from sentinel.models_advisor import ObrascInstance

    company = _get_company(request)
    obrazac = get_object_or_404(ObrascInstance, pk=pk, company=company)
    return render(request, "sentinel/obrazac_detail.html", {"company": company, "obrazac": obrazac})


@login_required
def obrazac_xml_download(request, pk):
    from sentinel.models_advisor import ObrascInstance
    from django.http import HttpResponse

    company = _get_company(request)
    obrazac = get_object_or_404(ObrascInstance, pk=pk, company=company)
    response = HttpResponse(obrazac.xml_sadrzaj, content_type="application/xml")
    response["Content-Disposition"] = f'attachment; filename="{obrazac.tip.kod}_{obrazac.period_od}.xml"'
    return response


# ─── VIEWS — DIGITALNI URED ───────────────────────────────────────────────────


@login_required
def digitalni_ured(request, conv_id=None):
    from sentinel.models_ured import DigitalniUred, UredKonverzacija, UredInsight

    company = _get_company(request)
    ured, _ = DigitalniUred.objects.get_or_create(company=company, defaults={})

    conversations = UredKonverzacija.objects.filter(ured=ured, user=request.user).order_by("-last_message_at")[:15]

    insights = UredInsight.objects.filter(ured=ured, is_read=False).order_by("-created_at")[:5]

    active_conv = None
    if conv_id:
        active_conv = get_object_or_404(UredKonverzacija, pk=conv_id, ured=ured, user=request.user)
    elif conversations.exists():
        active_conv = conversations.first()

    # Poruke aktivne konverzacije
    poruke = []
    if active_conv:
        poruke = list(active_conv.poruke.order_by("created_at")[:100])

    return render(
        request,
        "sentinel/digitalni_ured.html",
        {
            "company": company,
            "ured": ured,
            "conversations": conversations,
            "active_conv": active_conv,
            "poruke": poruke,
            "insights": insights,
            "topics": UredKonverzacija.TOPIC,
        },
    )


@login_required
@csrf_exempt
def ured_send_message(request, conv_id):
    """API: pošalji poruku AI savjetniku."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        d = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    message = d.get("message", "").strip()
    use_sonnet = d.get("advanced", False)

    if not message:
        return JsonResponse({"error": "Prazna poruka"}, status=400)
    if len(message) > 2000:
        return JsonResponse({"error": "Poruka predugačka (max 2000 znakova)"}, status=400)

    from sentinel.models_ured import DigitalniUred, UredKonverzacija
    from sentinel.ured_engine import UredAIEngine

    company = _get_company(request)
    ured = get_object_or_404(DigitalniUred, company=company)
    conv = get_object_or_404(UredKonverzacija, pk=conv_id, ured=ured, user=request.user)

    engine = UredAIEngine(conv)
    response_text = engine.send(message, use_sonnet=use_sonnet)

    return JsonResponse({"response": response_text, "model": "sonnet" if use_sonnet else "haiku", "conv_id": conv.id})


@login_required
def ured_nova_konverzacija(request):
    """Kreiraj novu konverzaciju."""
    if request.method != "POST":
        return redirect("sentinel:digitalni_ured")

    from sentinel.models_ured import DigitalniUred, UredKonverzacija

    company = _get_company(request)
    ured, _ = DigitalniUred.objects.get_or_create(company=company, defaults={})

    topic = request.POST.get("topic", "general")
    conv = UredKonverzacija.objects.create(ured=ured, user=request.user, topic=topic, company=company)
    return redirect("sentinel:digitalni_ured_conv", conv_id=conv.pk)


# ─── VIEWS — KALENDAR ─────────────────────────────────────────────────────────


@login_required
def kalendar_obveza(request):
    from sentinel.models_advisor import KalendarObveza
    from datetime import date

    company = _get_company(request)
    today = date.today()

    overdue = KalendarObveza.objects.filter(company=company, rok__lt=today, is_completed=False).order_by("rok")

    upcoming = KalendarObveza.objects.filter(company=company, rok__gte=today, is_completed=False).order_by("rok")[:20]

    completed = KalendarObveza.objects.filter(company=company, is_completed=True).order_by("-completed_at")[:10]

    return render(
        request,
        "sentinel/kalendar.html",
        {
            "company": company,
            "overdue": overdue,
            "upcoming": upcoming,
            "completed": completed,
            "today": today,
        },
    )


# ─── HELPER ───────────────────────────────────────────────────────────────────


def _get_company(request):
    """Uzmi aktivnu firmu iz requesta."""
    company = getattr(request.user, "active_company", None)
    if company:
        return company
    from companies.models import Company

    return Company.active.filter(created_by=request.user).first() or Company.active.first()
