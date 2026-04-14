import logging

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from helpdesk.models import Ticket
from superadmin_ai.models import AIModulePermission, PendingAIAction

logger = logging.getLogger("helpdesk.tasks")


@shared_task
def analyze_ticket_and_propose_action(ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)

        # Provjeri AI dozvolu za helpdesk modul
        perm = AIModulePermission.get_perm(ticket.company, "helpdesk")
        if not perm or not perm.can_read:
            # AI nema pristup — eskalacija direktno na WhatsApp
            _whatsapp_escalate(ticket, reason="AI nema pristup helpdesku")
            return

        proposed_code = ""
        action_desc = f"AI Analiza ticketa #{ticket.ticket_number}: {ticket.subject}"
        action_type = "update"

        if ticket.category == "technical":
            proposed_code = (
                "# Prijedlog SQL zakrpe ili ispravka koda\n# UPDATE auth_user SET is_active=True WHERE id=...;"
            )
            action_desc = f"Detektiran tehnički problem. Predlažem primjenu zakrpe za tiket #{ticket.ticket_number}."
            action_type = "bugfix"
        elif ticket.category == "feature":
            proposed_code = "# Prijedlog arhitekture nove značajke..."
            action_desc = f"Korisnik traži novu funkcionalnost u tiketu #{ticket.ticket_number}."
            action_type = "feature_request"
        else:
            action_desc = f"Automatski prijedlog rješenja za upit: {ticket.subject}"
            action_type = "data_update"

        # Kreiranje akcije na čekanju u superadmin_ai modulu
        PendingAIAction.objects.create(
            company=ticket.company,
            module="helpdesk",
            action_type=action_type,
            description=action_desc,
            proposed_code=proposed_code,
            payload={"ticket_id": ticket.id, "action": "resolve_ticket"},
            status="pending",
        )

        # Ažuriranje statusa ticketa u "waiting_internal" jer AI obrađuje
        ticket.status = "waiting_internal"
        ticket.save(update_fields=["status"])

        # WhatsApp eskalacija — obavijest Ivanu i Mariji
        _whatsapp_escalate(ticket, reason=f"Trojstvo: {action_type}")

    except Ticket.DoesNotExist:
        pass
    except ObjectDoesNotExist as e:
        logger.error("Helpdesk AI task greška: %s", e)


def _whatsapp_escalate(ticket, reason=""):
    """Pošalji WhatsApp obavijest Ivanu i Mariji o novom tiketu."""
    try:
        from core.whatsapp import send_text

        company_name = ticket.company.name if ticket.company else "N/A"
        msg = (
            f"Helpdesk #{ticket.ticket_number}\n"
            f"Firma: {company_name}\n"
            f"Prioritet: {ticket.get_priority_display()}\n"
            f"Predmet: {ticket.subject}\n"
        )
        if reason:
            msg += f"Status: {reason}\n"
        msg += f"\nhttps://limit-connect.com/hr/helpdesk/{ticket.pk}/"

        # Ivan (DE)
        send_text("4915771998747", msg)
        # Marija (HR)
        send_text("385976091655", msg)

        logger.info("WhatsApp eskalacija poslana za tiket %s", ticket.ticket_number)
    except ImportError:
        logger.warning("WhatsApp modul nije dostupan za eskalaciju tiketa %s", ticket.ticket_number)
    except Exception as e:
        logger.error("WhatsApp eskalacija failed za tiket %s: %s", ticket.ticket_number, e)
