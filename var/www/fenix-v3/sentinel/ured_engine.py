"""
FENIX SENTINEL — Digitalni Ured AI Engine (PLAN_080)
Claude s trajnim kontekstom firme.
Haiku za brze odgovore, Sonnet za kompleksno savjetovanje.
"""

import json
import time
from datetime import timedelta
from django.utils import timezone


class UredAIEngine:
    """
    Srce Digitalnog Ureda — Claude s trajnim kontekstom firme.
    """

    SYSTEM_PROMPT = """Ti si Fenix — osobni AI savjetnik za računovodstvo i financije.
Imaš pristup svim podacima firme: računi, plaće, PDV, EU fondovi, obveze.

PRAVILA:
- Govori direktno i konkretno (ne "možda" — reci točan broj ili datum)
- Uvijek navedi broj, datum ili iznos kad ga imaš
- Ako nešto nije u redu, reci jasno
- Predloži konkretni sljedeći korak
- Ako pitanje zahtijeva odvjetnika/revizora, jasno reci
- Jezik: prilagodi korisniku (HR/DE/EN auto-detect)
- Budi sažet — 3-5 rečenica ako nije kompleksno

KONTEKST FIRME:
{company_context}

SJEĆANJE (prethodne sesije):
{memory}

AKTIVNA UPOZORENJA:
{active_alerts}"""

    def __init__(self, konverzacija):
        self.konverzacija = konverzacija
        self.ured = konverzacija.ured
        self.company = self.ured.company

    def _build_company_context(self) -> str:

        ctx = {
            "name": self.company.name,
            "oib": getattr(self.company, "oib", "N/A"),
        }

        # Financijski podaci iz arhive
        try:
            from arhiva.models import ArhivaEntry

            last_month = timezone.now() - timedelta(days=30)
            ctx["last_30d_dokumenata"] = ArhivaEntry.objects.filter(
                company=self.company, created_at__gte=last_month, is_deleted=False
            ).count()
        except Exception:
            pass

        # Aktivni alertovi
        try:
            from sentinel.models import SentinelAlert

            ctx["active_alerts"] = SentinelAlert.objects.filter(company=self.company, resolved=False).count()
        except Exception:
            pass

        # Obrasci koji čekaju
        try:
            from sentinel.models_advisor import ObrascInstance
            from datetime import date

            ctx["obrasci_pending"] = ObrascInstance.objects.filter(
                company=self.company, status__in=["draft", "ready"], rok_podnosenja__gte=date.today()
            ).count()
        except Exception:
            pass

        # EU matchevi
        try:
            from sentinel.models_advisor import EUMatch

            ctx["eu_hot_matches"] = EUMatch.objects.filter(
                company=self.company, match_score__gte=75, status="recommended"
            ).count()
        except Exception:
            pass

        return json.dumps(ctx, ensure_ascii=False, default=str, indent=2)

    def _build_messages(self) -> list:
        poruke = self.konverzacija.poruke.filter(role__in=["user", "assistant"]).order_by("created_at")[-20:]
        return [{"role": p.role, "content": p.sadrzaj} for p in poruke]

    def _get_active_alerts_text(self) -> str:
        try:
            from sentinel.models import SentinelAlert

            alerts = SentinelAlert.objects.filter(company=self.company, resolved=False).order_by(
                "-severity", "-created_at"
            )[:5]
            if not alerts:
                return "Nema aktivnih upozorenja."
            return "\n".join([f"- [{a.severity.upper()}] {a.title}" for a in alerts])
        except Exception:
            return "N/A"

    def send(self, user_message: str, use_sonnet: bool = False) -> str:
        """Pošalji poruku, dobij odgovor."""
        import anthropic
        from sentinel.models_ured import UredPoruka

        start = time.time()

        # Spremi korisničku poruku
        UredPoruka.objects.create(konverzacija=self.konverzacija, role="user", sadrzaj=user_message)

        model = "claude-sonnet-4-6" if use_sonnet else "claude-3-5-haiku-20241022"

        system = self.SYSTEM_PROMPT.format(
            company_context=self._build_company_context(),
            memory=json.dumps(self.ured.memory, ensure_ascii=False, default=str),
            active_alerts=self._get_active_alerts_text(),
        )

        messages = self._build_messages()

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(model=model, max_tokens=1000, system=system, messages=messages)
            ai_text = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
        except Exception as e:
            ai_text = f"Greška pri komunikaciji s AI: {str(e)}"
            tokens_in = tokens_out = 0

        latency = int((time.time() - start) * 1000)

        UredPoruka.objects.create(
            konverzacija=self.konverzacija,
            role="assistant",
            sadrzaj=ai_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model_used=model,
            latency_ms=latency,
        )

        # Ažuriraj ured stats
        self.ured.last_active = timezone.now()
        self.ured.total_conversations = self.ured.conversations.count()
        self.ured.save(update_fields=["last_active", "total_conversations", "updated_at"])

        # Auto-update sjećanje svaki 10. odgovor
        msg_count = self.konverzacija.poruke.count()
        if msg_count % 10 == 0:
            self._update_memory()

        return ai_text

    def _update_memory(self):
        """Haiku izvuče ključne faktore iz razgovora i spremi u memory."""
        import anthropic

        recent = list(self.konverzacija.poruke.order_by("-created_at")[:6])
        if not recent:
            return

        context = "\n".join([f"{m.role}: {m.sadrzaj[:200]}" for m in reversed(recent)])

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Izvuci max 5 ključnih novih činjenica o firmi iz razgovora. "
                            'JSON: {"facts": [{"key": "...", "value": "..."}]}.\n\n' + context
                        ),
                    }
                ],
            )
            data = json.loads(response.content[0].text)
            for fact in data.get("facts", []):
                if fact.get("key") and fact.get("value"):
                    self.ured.memory[fact["key"]] = fact["value"]
            self.ured.save(update_fields=["memory", "updated_at"])
        except Exception:
            pass
