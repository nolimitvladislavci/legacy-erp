import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from einvoice.models import AS4Message, AS4MessageEvent, InboundInvoice, MessageDirection
from einvoice.api.serializers import (
    AS4MessageSerializer, AS4MessageEventSerializer,
    InboundInvoiceSerializer, InboundApproveSerializer,
)
# ArchiveService imported lazily to avoid boto3 at module load
from einvoice.tasks.outbound_tasks import send_invoice_task
from drf_spectacular.utils import extend_schema, extend_schema_view


logger = logging.getLogger("propter.einvoice.api")


@extend_schema_view(list=extend_schema(tags=["E-Invoice"]))
class AS4MessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AS4MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        company = getattr(self.request, "current_company", None)
        if not company:
            return AS4Message.objects.none()
        qs = AS4Message.objects.filter(company=company)
        direction = self.request.query_params.get("direction")
        if direction:
            qs = qs.filter(direction=direction)
        msg_status = self.request.query_params.get("status")
        if msg_status:
            qs = qs.filter(status=msg_status)
        return qs.select_related("company", "invoice")

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        message = self.get_object()
        events = AS4MessageEvent.objects.filter(message=message).order_by("created_at")
        return Response(AS4MessageEventSerializer(events, many=True).data)

    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        message = self.get_object()
        if message.direction != MessageDirection.OUTBOUND:
            return Response({"error": "Samo izlazne poruke"}, status=status.HTTP_400_BAD_REQUEST)
        if message.status in ("DELIVERED", "ACK"):
            return Response({"error": "Vec dostavljeno"}, status=status.HTTP_400_BAD_REQUEST)
        message.retry_count = 0
        message.error_detail = ""
        message.save(update_fields=["retry_count", "error_detail"])
        message.transition_to("QUEUED", detail="Rucno pokrenuto ponovo slanje", user=request.user)
        send_invoice_task.delay(str(message.id))
        return Response({"status": "queued", "message": "Poruka u redu za ponovo slanje"})


@extend_schema_view(list=extend_schema(tags=["E-Invoice"]))
class SmartMailboxViewSet(viewsets.ModelViewSet):
    serializer_class = InboundInvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        company = getattr(self.request, "current_company", None)
        if not company:
            return InboundInvoice.objects.none()
        qs = InboundInvoice.objects.filter(company=company)
        inv_status = self.request.query_params.get("status")
        if inv_status:
            qs = qs.filter(status=inv_status)
        return qs.select_related("as4_message")

    @action(detail=True, methods=["post"], serializer_class=InboundApproveSerializer)
    def approve(self, request, pk=None):
        inbound = self.get_object()
        if inbound.status in ("BOOKED", "REJECTED"):
            return Response({"error": f"Racun je vec {inbound.get_status_display()}"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = InboundApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        konto = serializer.validated_data["konto"]
        cost_center = serializer.validated_data.get("cost_center", "")
        notes = serializer.validated_data.get("notes", "")

        inbound.status = InboundInvoice.ProcessingStatus.BOOKED
        inbound.final_konto = konto
        inbound.final_cost_center = cost_center
        inbound.approved_by = request.user
        inbound.approved_at = timezone.now()
        inbound.booked_at = timezone.now()
        inbound.notes = notes
        inbound.save()

        inbound.as4_message.transition_to("BOOKED", detail=f"Proknjizeno na konto {konto}", user=request.user)

        try:
            from einvoice.services.archive_service import ArchiveService
            archive_svc = ArchiveService()
            archive_svc.archive_message(inbound.as4_message)
        except ImportError as e:
            logger.warning(f"Archive failed: {e}")

        return Response({"status": "booked", "konto": konto, "message": f"Racun {inbound.invoice_number} proknjizen"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        inbound = self.get_object()
        reason = request.data.get("reason", "")
        inbound.status = InboundInvoice.ProcessingStatus.REJECTED
        inbound.notes = f"Odbijeno: {reason}"
        inbound.save()
        inbound.as4_message.transition_to("REJECTED", detail=f"Korisnik odbio: {reason}", user=request.user)
        return Response({"status": "rejected", "message": f"Racun {inbound.invoice_number} odbijen"})


@api_view(["GET"])
@permission_classes([AllowAny])
def verify_archive(request, sha256_hash):
    if len(sha256_hash) != 64:
        return Response({"error": "SHA-256 hash mora imati 64 znaka"}, status=status.HTTP_400_BAD_REQUEST)
    from einvoice.services.archive_service import ArchiveService
    archive_svc = ArchiveService()
    result = archive_svc.verify_document(sha256_hash)
    return Response(result)
