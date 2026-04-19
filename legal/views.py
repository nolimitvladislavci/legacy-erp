"""Fenix V3 — Legal Views | Blok 7"""

import hashlib
import json
import logging

from core.base_view import TenantView
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Contract, ContractTemplate, Dispute, DisputeEvent, PowerOfAttorney

logger = logging.getLogger("fenix.legal")


# ── Ugovori ──────────────────────────────────────────────────────────────────


class ContractListView(TenantView):
    template_name = "legal/contract_list.html"
    page_title = "Ugovori"

    def get(self, request):
        status = request.GET.get("status", "")
        qs = Contract.objects.filter(company=self.company).order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        return self.render(
            request,
            {
                "contracts": qs[:50],
                "status_choices": Contract.STATUS_CHOICES,
                "active_status": status,
                "expiring": Contract.objects.filter(
                    company=self.company,
                    status=Contract.STATUS_SIGNED,
                    valid_until__lte=timezone.now().date() + timezone.timedelta(days=30),
                    valid_until__gte=timezone.now().date(),
                ).count(),
            },
        )


class ContractCreateView(TenantView):
    template_name = "legal/contract_form.html"
    page_title = "Novi ugovor"

    def get(self, request):
        templates = ContractTemplate.objects.filter(company=self.company, is_active=True)
        return self.render(
            request,
            {
                "templates": templates,
                "doc_type_choices": ContractTemplate.TYPE_CHOICES,
            },
        )

    def post(self, request):
        data = request.POST
        template_id = data.get("template_id")
        template = None
        if template_id:
            template = ContractTemplate.objects.filter(company=self.company, pk=template_id).first()

        contract = Contract.objects.create(
            company=self.company,
            template=template,
            title=data.get("title", ""),
            doc_type=data.get("doc_type", "other"),
            party_a_name=data.get("party_a_name", ""),
            party_a_oib=data.get("party_a_oib", ""),
            party_a_address=data.get("party_a_address", ""),
            party_b_name=data.get("party_b_name", ""),
            party_b_oib=data.get("party_b_oib", ""),
            party_b_address=data.get("party_b_address", ""),
            body_html=data.get("body_html", ""),
            valid_from=data.get("valid_from") or None,
            valid_until=data.get("valid_until") or None,
            created_by=request.user,
        )
        logger.info("Contract created: %s company=%s", contract.id, self.company.id)
        if self.is_htmx():
            return HttpResponse(
                f'<div class="fenix-toast fenix-toast-success">Ugovor kreiran ✓</div>'
                f'<script>window.location="/hr/pravni/ugovori/{contract.pk}/"</script>'
            )
        from django.shortcuts import redirect

        return redirect("legal:contract_detail", pk=contract.pk)


class ContractDetailView(TenantView):
    template_name = "legal/contract_detail.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk, company=self.company)
        return self.render(
            request,
            {
                "contract": contract,
                "page_title": contract.title,
            },
        )


class ContractSignView(TenantView):
    """Digitalni potpis — SHA-256 hash tijela ugovora."""

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk, company=self.company)
        if contract.status != Contract.STATUS_DRAFT:
            return self.json_error("Ugovor nije u statusu Nacrt.")

        signed_by = request.POST.get("signed_by") or request.user.get_full_name()
        body_bytes = contract.body_html.encode("utf-8")
        contract.sha256_hash = hashlib.sha256(body_bytes).hexdigest()
        contract.signed_at = timezone.now()
        contract.signed_by = signed_by
        contract.status = Contract.STATUS_SIGNED
        contract.save(update_fields=["sha256_hash", "signed_at", "signed_by", "status", "updated_at"])
        logger.info("Contract signed: %s hash=%s", contract.id, contract.sha256_hash[:16])
        return self.json_ok({"hash": contract.sha256_hash[:16] + "..."})


class ContractAIGenerateView(TenantView):
    """AI generira tijelo ugovora iz predloška i varijabli."""

    def post(self, request, pk):
        template = get_object_or_404(ContractTemplate, pk=pk, company=self.company)
        variables = {}
        for key in template.variables:
            variables[key] = request.POST.get(key, f"[{key}]")

        # Popuni tijelo s varijablama
        body = template.body_html
        for k, v in variables.items():
            body = body.replace("{{" + k + "}}", v)
            body = body.replace("{{ " + k + " }}", v)

        # AI poboljšanje ako postoji AI prompt
        if template.ai_prompt:
            try:
                from core.ai_gateway import AIGateway

                gateway = AIGateway()
                prompt = f"{template.ai_prompt}\n\nVarijable:\n{json.dumps(variables, ensure_ascii=False)}\n\nTrenutno tijelo:\n{body[:3000]}"
                result = gateway.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2000,
                )
                body = result.get("content", body)
            except Exception as e:
                logger.warning("AI contract generation failed: %s", e)

        return JsonResponse({"body_html": body, "variables": variables})


# ── Punomoći ──────────────────────────────────────────────────────────────────


class POAListView(TenantView):
    template_name = "legal/poa_list.html"
    page_title = "Punomoći"

    def get(self, request):
        qs = PowerOfAttorney.objects.filter(company=self.company).order_by("-valid_from")
        return self.render(
            request,
            {
                "poas": qs,
                "active_count": qs.filter(is_revoked=False).count(),
            },
        )


class POACreateView(TenantView):
    template_name = "legal/poa_form.html"
    page_title = "Nova punomoć"

    def get(self, request):
        return self.render(request, {"type_choices": PowerOfAttorney.TYPE_CHOICES})

    def post(self, request):
        data = request.POST
        PowerOfAttorney.objects.create(
            company=self.company,
            title=data.get("title", ""),
            poa_type=data.get("poa_type", "general"),
            principal_name=data.get("principal_name", ""),
            principal_oib=data.get("principal_oib", ""),
            agent_name=data.get("agent_name", ""),
            agent_oib=data.get("agent_oib", ""),
            scope=data.get("scope", ""),
            restrictions=data.get("restrictions", ""),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until") or None,
            is_indefinite="is_indefinite" in data,
        )
        from django.shortcuts import redirect

        return redirect("legal:poa_list")


# ── Sporovi ──────────────────────────────────────────────────────────────────


class DisputeListView(TenantView):
    template_name = "legal/dispute_list.html"
    page_title = "Sporovi"

    def get(self, request):
        qs = Dispute.objects.filter(company=self.company).order_by("-priority", "deadline")
        status = request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return self.render(
            request,
            {
                "disputes": qs[:100],
                "status_choices": Dispute.STATUS_CHOICES,
                "active_status": status,
                "overdue_count": sum(1 for d in qs if d.is_overdue),
                "open_count": qs.filter(status=Dispute.STATUS_OPEN).count(),
            },
        )


class DisputeCreateView(TenantView):
    template_name = "legal/dispute_form.html"
    page_title = "Novi spor"

    def get(self, request):
        return self.render(
            request,
            {
                "type_choices": Dispute.TYPE_CHOICES,
                "priority_choices": Dispute.PRIORITY_CHOICES,
            },
        )

    def post(self, request):
        data = request.POST
        dispute = Dispute.objects.create(
            company=self.company,
            title=data.get("title", ""),
            dispute_type=data.get("dispute_type", "other"),
            priority=data.get("priority", Dispute.PRIORITY_MEDIUM),
            opponent_name=data.get("opponent_name", ""),
            opponent_oib=data.get("opponent_oib", ""),
            opponent_contact=data.get("opponent_contact", ""),
            amount_claimed=data.get("amount_claimed") or None,
            deadline=data.get("deadline") or None,
            court_date=data.get("court_date") or None,
            description=data.get("description", ""),
            assigned_to=request.user if "self_assign" in data else None,
        )
        # Trigger AI analysis async
        _trigger_dispute_ai.delay(str(dispute.id))
        from django.shortcuts import redirect

        return redirect("legal:dispute_detail", pk=dispute.pk)


class DisputeDetailView(TenantView):
    template_name = "legal/dispute_detail.html"

    def get(self, request, pk):
        dispute = get_object_or_404(Dispute, pk=pk, company=self.company)
        return self.render(
            request,
            {
                "dispute": dispute,
                "events": dispute.events.all(),
                "page_title": dispute.title,
            },
        )

    def post(self, request, pk):
        """Dodaj bilješku / događaj."""
        dispute = get_object_or_404(Dispute, pk=pk, company=self.company)
        event_type = request.POST.get("event_type", "note")
        description = request.POST.get("description", "")
        if description:
            DisputeEvent.objects.create(
                dispute=dispute,
                event_type=event_type,
                description=description,
                created_by=request.user,
            )
            # Promjena statusa
            new_status = request.POST.get("new_status", "")
            if new_status and new_status != dispute.status:
                dispute.status = new_status
                if new_status == Dispute.STATUS_CLOSED:
                    dispute.closed_at = timezone.now()
                dispute.save(update_fields=["status", "closed_at", "updated_at"])

        if self.is_htmx():
            events = dispute.events.all()
            return self.render(
                request, {"dispute": dispute, "events": events}, template="legal/partials/dispute_events.html"
            )
        from django.shortcuts import redirect

        return redirect("legal:dispute_detail", pk=pk)


# Celery task — lazy import da ne blokiramo startup
def _trigger_dispute_ai(dispute_id: str):
    """Async AI analiza spora — rizik score + preporuka."""
    try:
        from celery import shared_task

        @shared_task(queue="ai")
        def _run(did):
            try:
                dispute = Dispute.objects.get(pk=did)
                from core.ai_gateway import AIGateway

                gw = AIGateway()
                prompt = (
                    f"Analiziraj sljedeći poslovni spor i daj: "
                    f"1) rizik score 0-100 (0=nema rizika, 100=kritično) "
                    f"2) kratku preporuku (max 3 rečenice) što poduzeti.\n\n"
                    f"Vrsta: {dispute.get_dispute_type_display()}\n"
                    f"Opis: {dispute.description[:1000]}\n"
                    f"Protustrana: {dispute.opponent_name}\n"
                    f"Rok: {dispute.deadline}\n"
                    f"Iznos: {dispute.amount_claimed} EUR\n\n"
                    f'Odgovori JSON: {{"risk_score": N, "recommendation": "..."}}'
                )
                result = gw.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                )
                import json as _json

                content = result.get("content", "{}")
                try:
                    data = _json.loads(content)
                    dispute.ai_risk_score = int(data.get("risk_score", 50))
                    dispute.ai_recommendation = data.get("recommendation", "")
                except Exception:
                    dispute.ai_recommendation = content[:500]
                dispute.save(update_fields=["ai_risk_score", "ai_recommendation", "updated_at"])
                DisputeEvent.objects.create(
                    dispute=dispute,
                    event_type="ai_analysis",
                    description=f"AI rizik: {dispute.ai_risk_score}/100\n{dispute.ai_recommendation}",
                )
            except Exception as exc:
                logger.error("Dispute AI failed %s: %s", did, exc)

        _run.delay(dispute_id)
    except Exception as exc:
        logger.warning("Could not trigger dispute AI: %s", exc)
