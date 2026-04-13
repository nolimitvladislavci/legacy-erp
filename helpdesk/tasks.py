from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from helpdesk.models import Ticket
from superadmin_ai.models import AIModulePermission, PendingAIAction


@shared_task
def analyze_ticket_and_propose_action(ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)

        # Provjeri AI dozvolu za helpdesk modul
        perm = AIModulePermission.get_perm(ticket.company, "helpdesk")
        if not perm or not perm.can_read:
            return  # AI nema pristup helpdesku

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

    except Ticket.DoesNotExist:
        pass
    except ObjectDoesNotExist as e:
        print(f"Greška u AI tasku: {str(e)}")
