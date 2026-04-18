# PLAN_054 — Trojstvo Engine (3-Agent Consensus: Haiku + Gemini + DeepSeek)

## Cilj
Trojstvo je core AI decision engine. Tri modela glasaju (2/3 konsenzus). Haiku = analiza, Gemini = istraživanje/kontekst, DeepSeek = kod/logika. Sonnet koordinira. Niti jedan AI ne odlučuje sam za kritična pitanja — uvijek konsenzus.

## Arhitektura
```
User request
    ↓
TrojstvoEngine.consult(question, context)
    ├── Haiku (Anthropic) ──→ vote_1
    ├── Gemini Flash (Google) → vote_2  
    └── DeepSeek (Bedrock) ──→ vote_3
    ↓
ConsensusResolver.resolve(votes)  → 2/3 → final answer
    ↓
TrojstvoResult(answer, confidence, dissent)
```

## Model
```python
class TrojstvoConsultation(TenantModel):
    """
    Svako savjetovanje s Trojstvom se logira.
    Za audit trail i cost tracking.
    """
    company = models.ForeignKey(Company, null=True, on_delete=models.SET_NULL)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class ConsultationType(models.TextChoices):
        BOOKING_SUGGESTION = "booking", "Prijedlog knjiženja"
        DOCUMENT_CLASSIFICATION = "classification", "Klasifikacija dokumenta"
        RISK_ASSESSMENT = "risk", "Procjena rizika"
        CODE_REVIEW = "code_review", "Pregled koda"
        GENERAL = "general", "Opći upit"

    consultation_type = models.CharField(max_length=30, choices=ConsultationType.choices)
    question = models.TextField()
    context_data = models.JSONField(default=dict)

    # Glasovi
    haiku_response = models.TextField(blank=True)
    haiku_vote = models.CharField(max_length=500, blank=True)
    haiku_confidence = models.FloatField(null=True)
    haiku_tokens = models.IntegerField(default=0)
    haiku_cost_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    gemini_response = models.TextField(blank=True)
    gemini_vote = models.CharField(max_length=500, blank=True)
    gemini_confidence = models.FloatField(null=True)
    gemini_tokens = models.IntegerField(default=0)
    gemini_cost_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    deepseek_response = models.TextField(blank=True)
    deepseek_vote = models.CharField(max_length=500, blank=True)
    deepseek_confidence = models.FloatField(null=True)
    deepseek_tokens = models.IntegerField(default=0)
    deepseek_cost_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    # Konsenzus
    final_answer = models.TextField(blank=True)
    consensus_reached = models.BooleanField(default=False)
    consensus_score = models.IntegerField(default=0)  # 1, 2, or 3
    dissenting_model = models.CharField(max_length=20, blank=True)

    total_cost_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)
    duration_ms = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True)
```

## TrojstvoEngine klasa
```python
import asyncio
import time
from dataclasses import dataclass
from typing import Optional
import google.generativeai as genai
import anthropic
import boto3
import json

@dataclass
class AgentVote:
    model_name: str
    vote: str           # kratki odgovor/opcija
    reasoning: str      # objašnjenje
    confidence: float   # 0.0 - 1.0
    tokens_used: int
    cost_usd: float


@dataclass
class TrojstvoResult:
    final_answer: str
    consensus_reached: bool
    consensus_score: int        # koliko glasova = winner
    votes: list[AgentVote]
    dissenting_model: Optional[str]
    total_cost_usd: float
    duration_ms: int


class TrojstvoEngine:
    """
    3-agent consensus engine. Haiku + Gemini + DeepSeek.
    Minimum 2/3 za konsenzus.
    """

    SYSTEM_PROMPT = """Ti si AI agent u Trojstvo konsenzus sustavu.
Odgovaraš ISKLJUČIVO u JSON formatu:
{
  "vote": "<kratki odgovor/opcija, max 100 znakova>",
  "reasoning": "<objašnjenje, max 500 znakova>",
  "confidence": <float 0.0-1.0>
}
Budi koncizan. Tvoj glas ide u konsenzus s 2 druga AI agenta."""

    def __init__(self):
        self.anthropic_client = anthropic.Anthropic()
        self.bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
        self.gemini = genai.GenerativeModel("gemini-1.5-flash")

    async def consult_async(
        self,
        question: str,
        context: dict = None,
        consultation_type: str = "general",
    ) -> TrojstvoResult:
        start_ms = int(time.time() * 1000)
        prompt = self._build_prompt(question, context or {})

        # Paralelni pozivi
        votes = await asyncio.gather(
            self._ask_haiku(prompt),
            self._ask_gemini(prompt),
            self._ask_deepseek(prompt),
            return_exceptions=True,
        )

        # Filter exceptions
        valid_votes = [v for v in votes if isinstance(v, AgentVote)]
        failed = len(votes) - len(valid_votes)

        if len(valid_votes) < 2:
            raise RuntimeError(f"Trojstvo: samo {len(valid_votes)}/3 modela odgovorilo. Nemoguće postići konsenzus.")

        result = self._resolve_consensus(valid_votes)
        result.duration_ms = int(time.time() * 1000) - start_ms
        return result

    def consult(self, question: str, context: dict = None, consultation_type: str = "general") -> TrojstvoResult:
        """Sync wrapper za Django views."""
        return asyncio.run(self.consult_async(question, context, consultation_type))

    def _build_prompt(self, question: str, context: dict) -> str:
        ctx_str = ""
        if context:
            ctx_str = "\n\nKONTEKST:\n" + json.dumps(context, ensure_ascii=False, indent=2)
        return f"PITANJE: {question}{ctx_str}"

    async def _ask_haiku(self, prompt: str) -> AgentVote:
        import anthropic
        response = self.anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        parsed = json.loads(content)
        tokens = response.usage.input_tokens + response.usage.output_tokens
        # Haiku cost: $0.25/1M input, $1.25/1M output
        cost = (response.usage.input_tokens * 0.00000025 +
                response.usage.output_tokens * 0.00000125)
        return AgentVote(
            model_name="haiku",
            vote=parsed["vote"],
            reasoning=parsed["reasoning"],
            confidence=float(parsed["confidence"]),
            tokens_used=tokens,
            cost_usd=cost,
        )

    async def _ask_gemini(self, prompt: str) -> AgentVote:
        full_prompt = self.SYSTEM_PROMPT + "\n\n" + prompt
        response = await asyncio.to_thread(
            self.gemini.generate_content,
            full_prompt,
            generation_config={"max_output_tokens": 300, "temperature": 0.3},
        )
        parsed = json.loads(response.text)
        tokens = response.usage_metadata.total_token_count
        # Gemini Flash: ~$0.075/1M tokens
        cost = tokens * 0.000000075
        return AgentVote(
            model_name="gemini",
            vote=parsed["vote"],
            reasoning=parsed["reasoning"],
            confidence=float(parsed["confidence"]),
            tokens_used=tokens,
            cost_usd=cost,
        )

    async def _ask_deepseek(self, prompt: str) -> AgentVote:
        body = json.dumps({
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 300,
            "temperature": 0.3,
        })
        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId="deepseek.r1-v1:0",  # Bedrock model ID
            body=body,
        )
        result = json.loads(response["body"].read())
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        tokens = result.get("usage", {}).get("total_tokens", 0)
        # DeepSeek R1: ~$0.55/1M tokens
        cost = tokens * 0.00000055
        return AgentVote(
            model_name="deepseek",
            vote=parsed["vote"],
            reasoning=parsed["reasoning"],
            confidence=float(parsed["confidence"]),
            tokens_used=tokens,
            cost_usd=cost,
        )

    def _resolve_consensus(self, votes: list[AgentVote]) -> TrojstvoResult:
        """
        Grupira glasove. Najčešći glas = konsenzus.
        Tolerancija za semantički slične odgovore: lowercase + strip.
        """
        from collections import Counter

        normalized = [v.vote.lower().strip() for v in votes]
        counts = Counter(normalized)
        top_vote, top_count = counts.most_common(1)[0]

        consensus_votes = [v for v in votes if v.vote.lower().strip() == top_vote]
        dissenting = [v for v in votes if v.vote.lower().strip() != top_vote]

        # Uzimamo reasoning od najconfidentnijeg glasa
        best_vote = max(consensus_votes, key=lambda v: v.confidence)

        total_cost = sum(v.cost_usd for v in votes)

        return TrojstvoResult(
            final_answer=best_vote.reasoning,
            consensus_reached=top_count >= 2,
            consensus_score=top_count,
            votes=votes,
            dissenting_model=dissenting[0].model_name if dissenting else None,
            total_cost_usd=total_cost,
            duration_ms=0,  # set by caller
        )

# Singleton
trojstvo_engine = TrojstvoEngine()
```

## Celery task: trojstvo_consult
```python
@shared_task(bind=True, base=AITask, queue="heavy")
def trojstvo_consult_task(self, consultation_id: str):
    """Async Trojstvo consultation — ne blokira HTTP request."""
    consultation = TrojstvoConsultation.objects.get(id=consultation_id)

    result = trojstvo_engine.consult(
        question=consultation.question,
        context=consultation.context_data,
        consultation_type=consultation.consultation_type,
    )

    # Spremi rezultate po modelu
    for vote in result.votes:
        if vote.model_name == "haiku":
            consultation.haiku_response = vote.reasoning
            consultation.haiku_vote = vote.vote
            consultation.haiku_confidence = vote.confidence
            consultation.haiku_tokens = vote.tokens_used
            consultation.haiku_cost_usd = vote.cost_usd
        elif vote.model_name == "gemini":
            consultation.gemini_response = vote.reasoning
            consultation.gemini_vote = vote.vote
            consultation.gemini_confidence = vote.confidence
            consultation.gemini_tokens = vote.tokens_used
            consultation.gemini_cost_usd = vote.cost_usd
        elif vote.model_name == "deepseek":
            consultation.deepseek_response = vote.reasoning
            consultation.deepseek_vote = vote.vote
            consultation.deepseek_confidence = vote.confidence
            consultation.deepseek_tokens = vote.tokens_used
            consultation.deepseek_cost_usd = vote.cost_usd

    consultation.final_answer = result.final_answer
    consultation.consensus_reached = result.consensus_reached
    consultation.consensus_score = result.consensus_score
    consultation.dissenting_model = result.dissenting_model or ""
    consultation.total_cost_usd = result.total_cost_usd
    consultation.duration_ms = result.duration_ms
    consultation.completed_at = timezone.now()
    consultation.save()
```

## Integration: ArhivaEntry booking suggestion
```python
# Kada ai_suggest_booking_task treba visoku točnost (iznos > 1000 EUR):
def ai_suggest_booking(entry: ArhivaEntry) -> dict:
    amount = entry.total_amount or Decimal("0")
    
    if amount >= Decimal("1000"):
        # Visoka vrijednost → Trojstvo konsenzus
        result = trojstvo_engine.consult(
            question=f"Predloži konto knjiženje za: {entry.vendor_name}, iznos {amount} EUR, tip: {entry.doc_type}",
            context={
                "vendor": entry.vendor_name,
                "amount": str(amount),
                "doc_type": entry.doc_type,
                "date": str(entry.document_date),
            },
            consultation_type=TrojstvoConsultation.ConsultationType.BOOKING_SUGGESTION,
        )
        return {"source": "trojstvo", "suggestion": result.final_answer, "confidence": result.consensus_score / 3}
    else:
        # Mala vrijednost → samo Haiku (jeftiniji)
        return ai_gateway.suggest_async(entry)
```

## TrojstvoView (AI Cockpit integration)
```python
class TrojstvoConsultView(TenantView):
    """
    UI za ručno savjetovanje s Trojstvom.
    Dostupno u AI Cockpit → Trojstvo tab.
    """
    template_name = "ai_cockpit/trojstvo.html"
    permission_required = Permission.USE_AI

    def post(self, request):
        question = request.POST.get("question", "").strip()
        if not question:
            return JsonResponse({"ok": False, "error": "Upit je prazan."}, status=400)

        # Sinhroni poziv (za UI — max 10s timeout)
        try:
            result = trojstvo_engine.consult(question=question, context={
                "company": request.company.name,
                "date": date.today().isoformat(),
            })
        except RuntimeError as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=503)

        return JsonResponse({
            "ok": True,
            "answer": result.final_answer,
            "consensus": result.consensus_reached,
            "score": f"{result.consensus_score}/3",
            "cost": f"${result.total_cost_usd:.6f}",
            "duration": f"{result.duration_ms}ms",
            "dissent": result.dissenting_model,
            "votes": [
                {
                    "model": v.model_name,
                    "vote": v.vote,
                    "confidence": f"{int(v.confidence * 100)}%",
                }
                for v in result.votes
            ],
        })
```

## Troškovi (estimacija)
- Haiku: ~$0.0001 po consultu (najjeftiniji)
- Gemini Flash: ~$0.00005 po consultu
- DeepSeek R1: ~$0.0003 po consultu
- Ukupno po Trojstvo consultu: ~$0.0005 (0.05 centa)
- 1000 consulta/dan = $0.50/dan = $15/mjesec

## Testovi
```python
def test_trojstvo_consensus_2_of_3():
    # Mock 2 modela s istim glasom → consensus_reached = True
    ...

def test_trojstvo_no_consensus_1_of_3():
    # 3 različita glasa → consensus_reached = False
    ...

def test_trojstvo_handles_one_failure():
    # Jedan model padne → 2 preostala → konsenzus moguć
    ...

def test_cost_tracked_per_model():
    # Svaki AgentVote ima cost_usd > 0
    ...
```

## NAPOMENE
1. API ključevi: ANTHROPIC_API_KEY (env), GOOGLE_AI_API_KEY (env), AWS Bedrock credentials
2. Fallback: ako Bedrock padne → samo Haiku + Gemini (2 agenta, 2/2 = 100%)
3. Rate limiting: max 100 Trojstvo consulta/sat po kompaniji (Redis counter)
4. Logiranje: svaka konsultacija u TrojstvoConsultation model (za AI Cockpit prikaz)
5. NIKAD ne koristiti Trojstvo za real-time POS operacije — preskupo i presporo
