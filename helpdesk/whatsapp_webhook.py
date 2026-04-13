"""
helpdesk/whatsapp_webhook.py
WAHA webhook handler — creates/appends helpdesk tickets from WhatsApp messages.
"""

import json
import logging

from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger("helpdesk.whatsapp")


def _get_vip(phone):
    """Check if phone is VIP from DB."""
    from helpdesk.models import VIPContact

    vip = VIPContact.objects.filter(phone=phone, is_active=True).first()
    if not vip and len(phone) > 9:
        vip = VIPContact.objects.filter(phone__endswith=phone[-9:], is_active=True).first()
    if vip:
        return {
            "priority": vip.priority,
            "note": vip.name + (" - " + vip.note if vip.note else ""),
            "assign_to": vip.auto_assign_to,
        }
    return None


# Normalizacija telefona — centralizirana u core.whatsapp
from core.whatsapp import normalize_phone as _normalize_phone_core


def _normalize_phone(raw):
    """Strip WhatsApp suffix and normalize. Delegira na core.whatsapp.normalize_phone."""
    # Ukloni WhatsApp suffixe koje core ne zna
    raw = raw.replace("@c.us", "").replace("@s.whatsapp.net", "")
    return _normalize_phone_core(raw)


def _find_partner(phone):
    """Try to match phone to a Partner record."""
    from partners.models import Partner

    for field in ["phone", "contact_phone", "mobile"]:
        if not hasattr(Partner, field):
            continue
        lookup = {f"{field}__contains": phone[-9:]}
        partner = Partner.objects.filter(**lookup).first()
        if partner:
            return partner
    return None


# CSRF exempt: external webhook — no browser session
@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """Receive inbound WhatsApp messages from WAHA."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "invalid json"}, status=400)

    event = payload.get("event", "")
    if event != "message":
        return JsonResponse({"ok": True, "skipped": event})

    msg_data = payload.get("payload", {}) or payload.get("message", {})
    if not msg_data:
        return JsonResponse({"ok": True, "skipped": "no payload"})

    # Extract message details
    from_phone = msg_data.get("from", "") or msg_data.get("chatId", "")
    body = msg_data.get("body", "") or ""
    is_from_me = msg_data.get("fromMe", False)

    # Skip our own outbound messages
    if is_from_me:
        return JsonResponse({"ok": True, "skipped": "outbound"})

    phone = _normalize_phone(from_phone)
    if not phone or not body.strip():
        return JsonResponse({"ok": True, "skipped": "empty"})

    from django.contrib.auth import get_user_model

    from helpdesk.models import Ticket, TicketMessage

    User = get_user_model()

    # Check VIP
    vip = _get_vip(phone)
    priority = vip["priority"] if vip else "normal"
    vip_note = vip["note"] if vip else ""

    # Try to find existing open ticket from this phone
    open_ticket = (
        Ticket.objects.filter(
            contact_phone__contains=phone[-9:],
            status__in=["open", "in_progress", "waiting"],
        )
        .order_by("-created_at")
        .first()
    )

    if open_ticket:
        # Append to existing ticket
        TicketMessage.objects.create(
            ticket=open_ticket,
            sender_name=vip_note or f"WhatsApp +{phone}",
            body=body[:5000],
            is_from_client=True,
            is_internal=False,
        )
        # Reopen if waiting
        if open_ticket.status == "waiting":
            open_ticket.status = "open"
            open_ticket.save(update_fields=["status"])

        logger.info(f"WA msg appended to ticket {open_ticket.ticket_number} from {phone}")
        return JsonResponse({"ok": True, "ticket": open_ticket.ticket_number, "action": "appended"})

    # Create new ticket
    partner = _find_partner(phone)

    # Determine company
    company = None
    if partner and hasattr(partner, "company"):
        company = partner.company
    else:
        # Default to first active company (Konjik)
        from companies.models import Company

        company = Company.objects.first()

    # Auto-assign for VIP
    assignee = None
    if vip:
        # Assign to superadmin
        assignee = vip.get("assign_to") or User.objects.filter(is_superuser=True, is_active=True).first()

    subject = body[:80] + ("..." if len(body) > 80 else "")

    ticket = Ticket(
        company=company,
        subject=subject,
        description=body[:5000],
        source="whatsapp",
        contact_phone=f"+{phone}",
        priority=priority,
        category="other",
        client=partner,
        assigned_to=assignee,
    )
    ticket.ticket_number = ticket.generate_ticket_number()
    ticket.save()

    TicketMessage.objects.create(
        ticket=ticket,
        sender_name=vip_note or f"WhatsApp +{phone}",
        body=body[:5000],
        is_from_client=True,
        is_internal=False,
    )

    # Send auto-reply
    try:
        from core.whatsapp import send_text

        reply = f"Hvala! Vas tiket {ticket.ticket_number} je primljen. Javit cemo Vam se uskoro."
        if vip:
            reply = f"Pozdrav! Vas tiket {ticket.ticket_number} je primljen s prioritetom HITNO. Odmah se javljamo."
        send_text(f"+{phone}", reply)
    except ImportError as e:
        logger.warning(f"Auto-reply failed for {phone}: {e}")

    # Notify admins for VIP tickets
    if vip:
        try:
            from notifications.services import notify

            admins = User.objects.filter(is_superuser=True, is_active=True)
            for admin in admins:
                notify(
                    recipient=admin,
                    notification_type="urgent",
                    title=f"VIP WhatsApp tiket: {vip_note}",
                    message=body[:200],
                    url=f"/helpdesk/{ticket.id}/",
                    company=company,
                )
        except DatabaseError:
            pass

    logger.info(f"WA new ticket {ticket.ticket_number} from {phone} (VIP={bool(vip)})")
    return JsonResponse(
        {
            "ok": True,
            "ticket": ticket.ticket_number,
            "action": "created",
            "vip": bool(vip),
        }
    )
