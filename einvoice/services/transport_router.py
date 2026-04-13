"""TransportRouter — decides HOW to deliver each invoice."""
import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger("propter.einvoice.router")


@dataclass
class RoutingDecision:
    transport: str
    reason: str
    backend_name: str
    receiver_info: dict


class TransportRouter:
    """Decides which transport backend to use for each invoice."""

    def __init__(self):
        self._backends = {}

    def resolve(self, company_id, sender_oib, receiver_oib, receiver_is_individual=False):
        from einvoice.models import PeppolParticipant, TransportConfiguration, TransportType

        try:
            config = TransportConfiguration.objects.get(company_id=company_id)
        except TransportConfiguration.DoesNotExist:
            return RoutingDecision(
                transport=TransportType.FINA_POSREDNIK,
                reason="Nema konfiguracije - koristi FINA default",
                backend_name="PosrednikService",
                receiver_info={},
            )

        if config.primary_transport == "OFF":
            return RoutingDecision(
                transport=TransportType.MANUAL,
                reason="e-Racun onemogucen za ovu tvrtku",
                backend_name="ManualQueue",
                receiver_info={},
            )

        if receiver_is_individual or not receiver_oib:
            if config.b2c_enabled:
                return RoutingDecision(
                    transport=TransportType.B2C_PORTAL,
                    reason="Primatelj je fizicka osoba - B2C portal",
                    backend_name="B2CPortalService",
                    receiver_info={"is_individual": True},
                )
            return RoutingDecision(
                transport=TransportType.EMAIL_FALLBACK,
                reason="B2C onemogucen - email fallback",
                backend_name="EmailFallbackService",
                receiver_info={},
            )

        participant = PeppolParticipant.objects.filter(
            participant_id=receiver_oib, scheme="9934", is_active=True,
        ).first()

        if participant and participant.is_on_peppol:
            if config.primary_transport == "PH4" and getattr(settings, "PHASE4_AP_ENABLED", False):
                return RoutingDecision(
                    transport=TransportType.PHASE4_AP,
                    reason=f"Primatelj na Peppol-u ({participant.access_point_id}), vlastiti AP",
                    backend_name="Phase4Client",
                    receiver_info={
                        "participant": participant.full_participant_id,
                        "access_point": participant.access_point_id,
                        "endpoint_url": participant.endpoint_url,
                    },
                )
            return RoutingDecision(
                transport=TransportType.FINA_POSREDNIK,
                reason=f"Primatelj na Peppol-u ({participant.access_point_id}), FINA posrednik",
                backend_name="PosrednikService",
                receiver_info={
                    "participant": participant.full_participant_id,
                    "access_point": participant.access_point_id,
                },
            )

        if config.email_fallback_enabled:
            return RoutingDecision(
                transport=TransportType.EMAIL_FALLBACK,
                reason=f"Primatelj {receiver_oib} NIJE na Peppol-u - email fallback",
                backend_name="EmailFallbackService",
                receiver_info={"receiver_oib": receiver_oib},
            )

        return RoutingDecision(
            transport=TransportType.MANUAL,
            reason=f"Primatelj {receiver_oib} NIJE na Peppol-u, email fallback onemogucen - rucna obrada",
            backend_name="ManualQueue",
            receiver_info={"receiver_oib": receiver_oib},
        )

    def get_backend(self, transport):
        if transport not in self._backends:
            self._backends[transport] = self._create_backend(transport)
        return self._backends[transport]

    def _create_backend(self, transport):
        from einvoice.models import TransportType
        if transport == TransportType.FINA_POSREDNIK:
            from einvoice.services.posrednik_client import PosrednikClient
            return PosrednikClient()
        elif transport == TransportType.PHASE4_AP:
            from einvoice.services.phase4_client import Phase4Client
            return Phase4Client()
        elif transport == TransportType.B2C_PORTAL:
            from einvoice.services.b2c_portal_service import B2CPortalService
            return B2CPortalService()
        else:
            raise ValueError(f"Unknown transport: {transport}")
