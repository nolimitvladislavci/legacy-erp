import logging

"""
core/ai_service.py — Gemini AI adapter s troškovnom kontrolom.

Sigurnosni slojevi:
  1. AICallBudget  — dnevni (200) i satni (30) hard limit poziva
  2. GeminiUsageLog — svaki poziv upisan u bazu (smart_import_geminiusagelog)
  3. CircuitBreaker — greška = fallback dict, ne crash
  4. Input trim     — max 8000 znakova
"""
import hashlib
import json
import os
from decimal import Decimal

logger = logging.getLogger(__name__)

GEMINI_MODEL          = "gemini-2.5-flash"
DAILY_CALL_LIMIT      = 200
HOURLY_CALL_LIMIT     = 30
DAILY_TOKEN_LIMIT     = 500_000
MAX_INPUT_CHARS       = 8_000
COST_PER_INPUT_TOKEN  = Decimal("0.000000075")
COST_PER_OUTPUT_TOKEN = Decimal("0.0000003")


class AICallBudget:

    def check(self, caller=""):
        try:
            from datetime import timedelta

            from django.db.models import Count, Sum
            from django.utils import timezone

            from smart_import.gemini_log import GeminiUsageLog
            now      = timezone.now()
            hour_ago = now - timedelta(hours=1)
            daily    = GeminiUsageLog.objects.filter(called_at__date=now.date()).aggregate(
                           calls=Count("id"), tokens=Sum("input_tokens"))
            hourly   = GeminiUsageLog.objects.filter(called_at__gte=hour_ago).count()
            dc = daily["calls"]  or 0
            dt = daily["tokens"] or 0
            if dc >= DAILY_CALL_LIMIT:
                logger.warning("AIBudget BLOCK daily_calls=%d caller=%s", dc, caller)
                return {"allowed": False, "reason": f"Dnevni limit AI poziva ({dc}/{DAILY_CALL_LIMIT}). Reset sutra u ponoć."}
            if hourly >= HOURLY_CALL_LIMIT:
                logger.warning("AIBudget BLOCK hourly=%d caller=%s", hourly, caller)
                return {"allowed": False, "reason": f"Satni limit ({hourly}/{HOURLY_CALL_LIMIT}). Pričekaj malo."}
            if dt >= DAILY_TOKEN_LIMIT:
                logger.warning("AIBudget BLOCK daily_tokens=%d caller=%s", dt, caller)
                return {"allowed": False, "reason": f"Dnevni token limit ({dt:,}/{DAILY_TOKEN_LIMIT:,})."}
            return {"allowed": True, "daily_calls": dc, "hourly_calls": hourly}
        except DatabaseError as e:
            logger.error("AICallBudget.check error: %s", e)
            return {"allowed": True}

    def log(self, caller, model, input_tokens, output_tokens, success, input_hash=""):
        try:
            from smart_import.gemini_log import GeminiUsageLog
            cost = (Decimal(input_tokens) * COST_PER_INPUT_TOKEN +
                    Decimal(output_tokens) * COST_PER_OUTPUT_TOKEN)
            GeminiUsageLog.objects.create(
                caller=caller, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_eur=cost, success=success, input_hash=input_hash,
            )
        except (ValueError, TypeError) as e:
            logger.error("AICallBudget.log error: %s", e)


budget = AICallBudget()


class CircuitBreakerAI:

    def __init__(self):
        self.api_key   = os.getenv("GEMINI_API_KEY")
        self.is_active = bool(self.api_key)
        self.model     = GEMINI_MODEL
        self._client   = None
        if not self.is_active:
            logger.warning("GEMINI_API_KEY nije postavljen. AI modul isključen.")

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _hash(self, text):
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _parse_json(self, text):
        t = text.strip()
        for prefix in ("```json", "```"):
            if t.startswith(prefix): t = t[len(prefix):]
        if t.endswith("```"): t = t[:-3]
        return json.loads(t.strip())

    def _est(self, text):
        return max(1, len(text) // 4)

    def process_invoice_text(self, document_text, caller="invoice_text"):
        if not self.is_active:
            return {"status": "error", "message": "AI isključen (nema ključa)."}
        chk = budget.check(caller)
        if not chk["allowed"]:
            return {"status": "budget_exceeded", "message": chk["reason"]}
        trimmed = document_text[:MAX_INPUT_CHARS]
        h = self._hash(trimmed)
        prompt = (
            "Analiziraj tekst racuna i vrati ISKLJUCIVO validan JSON objekt, "
            "bez ikakvih dodatnih rijeci ili markdown formatiranja.\n\n"
            "Struktura: {\"dobavljac\": \"Ime\", \"oib\": \"OIB ili null\", "
            "\"ukupni_iznos\": 1234.56, \"valuta\": \"EUR\", "
            "\"datum_izdavanja\": \"YYYY-MM-DD\"}\n\n"
            f"Tekst racuna:\n{trimmed}"
        )
        ein, suc, eout = self._est(prompt), False, 0
        try:
            r = self._get_client().models.generate_content(model=self.model, contents=prompt)
            res = self._parse_json(r.text)
            res["status"] = "success"
            eout = self._est(r.text)
            suc = True
            return res
        except json.JSONDecodeError as e:
            logger.error("AI JSON parse (text) caller=%s: %s", caller, e)
            return {"status": "error", "message": "AI vratio neispravan JSON. Rucni unos."}
        except Exception as e:
            logger.error("AI Circuit Breaker (text) caller=%s: %s", caller, e)
            return {"status": "error", "message": "AI greska. Rucni unos."}
        finally:
            budget.log(caller, self.model, ein, eout, suc, h)

    def process_invoice_image(self, image_path, caller="invoice_image"):
        if not self.is_active:
            return {"status": "error", "message": "AI iskljucen (nema kljuca)."}
        if not os.path.exists(image_path):
            return {"status": "error", "message": f"Slika ne postoji: {image_path}"}
        chk = budget.check(caller)
        if not chk["allowed"]:
            return {"status": "budget_exceeded", "message": chk["reason"]}
        try: sz = os.path.getsize(image_path)
        except Exception: sz = 0
        h = self._hash(f"{image_path}:{sz}")
        prompt = (
            "Analiziraj ovu sliku racuna i vrati ISKLJUCIVO validan JSON objekt, "
            "bez ikakvih dodatnih rijeci ili markdown formatiranja.\n\n"
            "Struktura: {\"dobavljac\": \"Ime (npr. INA)\", \"oib\": \"OIB ili null\", "
            "\"ukupni_iznos\": 1234.56, \"valuta\": \"EUR\", "
            "\"datum_izdavanja\": \"YYYY-MM-DD\"}"
        )
        ein, suc, eout = self._est(prompt) + 500, False, 0
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image_path)
            r   = self._get_client().models.generate_content(model=self.model, contents=[prompt, img])
            res = self._parse_json(r.text)
            res["status"] = "success"
            eout = self._est(r.text)
            suc  = True
            return res
        except json.JSONDecodeError as e:
            logger.error("AI JSON parse (image) caller=%s: %s", caller, e)
            return {"status": "error", "message": "AI vratio neispravan JSON. Rucni unos."}
        except (FileNotFoundError, IOError) as e:
            logger.error("AI Circuit Breaker (image) caller=%s: %s", caller, e)
            return {"status": "error", "message": "AI greska pri citanju slike. Rucni unos."}
        finally:
            budget.log(caller, self.model, ein, eout, suc, h)

    def status(self):
        chk = budget.check("status_check")
        return {
            "active": self.is_active, "model": self.model, "budget": chk,
            "limits": {"daily_calls": DAILY_CALL_LIMIT,
                       "hourly_calls": HOURLY_CALL_LIMIT,
                       "daily_tokens": DAILY_TOKEN_LIMIT},
        }


ai_engine = CircuitBreakerAI()
