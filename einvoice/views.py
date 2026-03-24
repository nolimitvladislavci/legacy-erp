"""Smart Mailbox views — AI-powered inbound invoice processing UI."""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.company_utils import get_user_company

logger = logging.getLogger("propter.einvoice.views")


@login_required
def smart_mailbox(request):
    """Smart Mailbox inbox — list all inbound invoices with AI classification."""
    company = get_user_company(request)
    if not company:
        django_messages.error(request, "Nema aktivne firme.")
        return redirect("dashboard")

    from einvoice.models import InboundInvoice, AS4Message, MessageDirection

    status_filter = request.GET.get("status", "")
    qs = InboundInvoice.objects.filter(company=company).select_related("as4_message")

    if status_filter:
        qs = qs.filter(status=status_filter)

    invoices = qs.order_by("-received_at")[:100]

    # Stats
    all_qs = InboundInvoice.objects.filter(company=company)
    stats = {
        "total": all_qs.count(),
        "pending": all_qs.filter(status__in=["PENDING", "AUTO"]).count(),
        "booked": all_qs.filter(status="BOOKED").count(),
        "rejected": all_qs.filter(status="REJECTED").count(),
        "duplicates": all_qs.filter(status="DUPLICATE").count(),
        "pending_amount": sum(
            i.gross_amount for i in all_qs.filter(status__in=["PENDING", "AUTO"])
        ),
        "booked_amount": sum(
            i.gross_amount for i in all_qs.filter(status="BOOKED")
        ),
    }

    # AS4 message stats
    as4_stats = {
        "outbound_queued": AS4Message.objects.filter(
            company=company, direction=MessageDirection.OUTBOUND, status__in=["QUEUED", "SUBMITTED", "SENT"]
        ).count(),
        "outbound_delivered": AS4Message.objects.filter(
            company=company, direction=MessageDirection.OUTBOUND, status__in=["DELIVERED", "ACK"]
        ).count(),
        "dlq": AS4Message.objects.filter(
            company=company, direction=MessageDirection.OUTBOUND, status="CANCELLED"
        ).count(),
    }

    return render(request, "einvoice/smart_mailbox.html", {
        "invoices": invoices,
        "stats": stats,
        "as4_stats": as4_stats,
        "status_filter": status_filter,
    })


@login_required
def mailbox_detail(request, pk):
    """Detail view for an inbound invoice with AI suggestion."""
    company = get_user_company(request)
    inbound = get_object_or_404(
        InboundInvoice.objects.select_related("as4_message", "approved_by", "duplicate_of"),
        pk=pk, company=company,
    )

    # Get AS4 audit trail
    events = []
    if inbound.as4_message:
        events = inbound.as4_message.events.all().order_by("created_at")

    return render(request, "einvoice/mailbox_detail.html", {
        "inbound": inbound,
        "events": events,
    })


@login_required
@require_POST
def mailbox_approve(request, pk):
    """One-click approve and book an inbound invoice."""
    company = get_user_company(request)
    from einvoice.models import InboundInvoice

    inbound = get_object_or_404(InboundInvoice, pk=pk, company=company)

    if inbound.status in ("BOOKED", "REJECTED"):
        django_messages.warning(request, f"Racun je vec {inbound.get_status_display()}.")
        return redirect("einvoice:mailbox_detail", pk=pk)

    konto = request.POST.get("konto", "").strip()
    cost_center = request.POST.get("cost_center", "").strip()
    notes = request.POST.get("notes", "").strip()

    if not konto:
        konto = inbound.suggested_konto

    if not konto:
        django_messages.error(request, "Konto je obavezan za knjizenje.")
        return redirect("einvoice:mailbox_detail", pk=pk)

    # Book the invoice
    inbound.status = InboundInvoice.ProcessingStatus.BOOKED
    inbound.final_konto = konto
    inbound.final_cost_center = cost_center
    inbound.approved_by = request.user
    inbound.approved_at = timezone.now()
    inbound.booked_at = timezone.now()
    inbound.notes = notes
    inbound.save()

    if inbound.as4_message:
        inbound.as4_message.transition_to("BOOKED", detail=f"Proknjizeno: konto {konto}", user=request.user)

    django_messages.success(request, f"Racun {inbound.invoice_number} proknjizen na konto {konto}.")
    return redirect("einvoice:mailbox_detail", pk=pk)


@login_required
@require_POST
def mailbox_reject(request, pk):
    """Reject an inbound invoice."""
    company = get_user_company(request)
    from einvoice.models import InboundInvoice

    inbound = get_object_or_404(InboundInvoice, pk=pk, company=company)
    reason = request.POST.get("reason", "Odbijeno od strane korisnika")

    inbound.status = InboundInvoice.ProcessingStatus.REJECTED
    inbound.notes = f"Odbijeno: {reason}"
    inbound.save()

    if inbound.as4_message:
        inbound.as4_message.transition_to("REJECTED", detail=reason, user=request.user)

    django_messages.info(request, f"Racun {inbound.invoice_number} odbijen.")
    return redirect("einvoice:smart_mailbox")


@login_required
def outbound_messages(request):
    """View outbound AS4 messages (sent invoices)."""
    company = get_user_company(request)
    if not company:
        return redirect("dashboard")

    from einvoice.models import AS4Message, MessageDirection

    status_filter = request.GET.get("status", "")
    qs = AS4Message.objects.filter(company=company, direction=MessageDirection.OUTBOUND)
    if status_filter:
        qs = qs.filter(status=status_filter)

    messages_list = qs.order_by("-created_at")[:100]

    return render(request, "einvoice/outbound_messages.html", {
        "messages": messages_list,
        "status_filter": status_filter,
    })


@login_required
def message_detail(request, pk):
    """Detail view for an AS4 message with full audit trail."""
    company = get_user_company(request)
    from einvoice.models import AS4Message

    message = get_object_or_404(AS4Message, pk=pk, company=company)
    events = message.events.all().order_by("created_at")

    return render(request, "einvoice/message_detail.html", {
        "message": message,
        "events": events,
    })
