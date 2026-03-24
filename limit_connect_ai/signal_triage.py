"""
BORG Signal Triage — Haiku AI auto-klasifikacija.

Svaki novi FenixSignal prolazi kroz Haiku koji:
1. Klasificira tip problema (bug/ux/pitanje/prijedlog/spam)
2. Dodjeljuje prioritet (1-4)
3. Predlaže kome dodijeliti (cc_code/gemini/ivan/marija)
4. Generira pametan odgovor korisniku
5. Detektira duplikate

Radi autonomno preko Celery taska — 0 ljudskog inputa.
Kad se Ivan vrati s bauštele, ima kategoriziran backlog.
"""
import json
import logging
from django.conf import settings

logger = logging.getLogger("borg.signal.triage")

TRIAGE_PROMPT = """Ti si BORG — interni AI triage sustav za LIMIT Connect ERP.
Dobio si signal (prijavu problema) od korisnika. Tvoj posao:

1. KLASIFICIRAJ tip: bug (tehnička greška), ux (zbunjujuće sučelje), pitanje (ne zna kako), prijedlog (želi novu funkciju), spam (nebitno/test)
2. PRIORITET 1-4: 1=kritično (sustav ne radi, financijski gubitak), 2=visoko (blokira rad ali ima workaround), 3=normalno (smetnja), 4=nisko (kozmetika/prijedlog)
3. DODIJELI: cc_code (tehnički bug), gemini (UX/dizajn), ivan (komercijala/klijent), marija (računovodstvo/zakon)
4. ODGOVOR korisniku: 1-2 rečenice, na hrvatskom, prijateljski ali profesionalno. Ako je bug — potvrdi da je primljeno. Ako je pitanje — daj kratak odgovor ili smjer.
5. SAŽETAK za dev tim: 1 rečenica, tehnički, na engleskom.

Kontekst sustava: LIMIT Connect je ERP za hrvatske/njemačke male poduzetnike.
Moduli: POS (blagajna), Fakture, eRačun, Rental (iznajmljivanje), Payroll, Konto, Tax Wizard.

Signal:
- Tip koji je korisnik odabrao: {signal_type}
- Poruka: {message}
- Stranica: {page_url}
- Kontekst: {context}

Odgovori ISKLJUČIVO u JSON formatu:
{{"classification": "bug|ux|pitanje|prijedlog|spam", "priority": 1-4, "assign_to": "cc_code|gemini|ivan|marija", "user_response": "...", "dev_summary": "...", "is_duplicate_hint": "opis sličnog problema ako postoji ili null"}}"""


def triage_signal(signal):
    """
    Haiku AI triage za jedan FenixSignal.
    Vraća dict s klasifikacijom ili None ako API nije dostupan.
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — triage skipped")
        return None

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        prompt = TRIAGE_PROMPT.format(
            signal_type=signal.signal_type,
            message=signal.message[:1000],
            page_url=signal.page_url or "N/A",
            context=json.dumps(signal.context or {}, default=str)[:500],
        )

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()

        # Parse JSON iz odgovora
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()

        result = json.loads(text)

        logger.info(
            "Triage signal %s: %s (P%s) → %s",
            signal.id, result.get("classification"), result.get("priority"), result.get("assign_to"),
        )
        return result

    except json.JSONDecodeError:
        logger.warning("Haiku returned non-JSON for signal %s: %s", signal.id, text[:200])
        return None
    except Exception as e:
        logger.error("Triage failed for signal %s: %s", signal.id, e)
        return None


def apply_triage(signal, triage_result):
    """Primijeni triage rezultat na FenixSignal."""
    if not triage_result:
        return

    # Map classification to signal_type
    type_map = {
        "bug": "bug",
        "ux": "confusion",
        "pitanje": "confusion",
        "prijedlog": "suggestion",
        "spam": "suggestion",  # ne brisemo, samo low priority
    }
    new_type = type_map.get(triage_result.get("classification"), signal.signal_type)

    signal.signal_type = new_type
    signal.priority = min(max(int(triage_result.get("priority", 3)), 1), 4)
    signal.assigned_to = triage_result.get("assign_to", "")[:50]
    signal.status = "triaged"

    # Spremi triage u triage_note
    signal.triage_note = json.dumps({
        "classification": triage_result.get("classification"),
        "dev_summary": triage_result.get("dev_summary", ""),
        "user_response": triage_result.get("user_response", ""),
        "duplicate_hint": triage_result.get("is_duplicate_hint"),
        "model": "claude-haiku-4-5-20251001",
    }, ensure_ascii=False)

    signal.save(update_fields=[
        "signal_type", "priority", "assigned_to", "status", "triage_note",
    ])

    logger.info("Applied triage to signal %s: P%s → %s", signal.id, signal.priority, signal.assigned_to)
