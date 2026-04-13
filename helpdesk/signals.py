from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ticket
from .tasks import analyze_ticket_and_propose_action

@receiver(post_save, sender=Ticket)
def trigger_ai_analysis(sender, instance, created, **kwargs):
    # Pokreni AI analizu samo kada je tiket tek kreiran
    if created:
        analyze_ticket_and_propose_action.delay(instance.id)
