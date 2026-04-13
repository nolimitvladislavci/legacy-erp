"""
AI Bookkeeper — automatsko knjiženje pomoću LLM + pattern matching.

Prima ArhivaEntry, vraća prijedlog knjiženja:
{
    "debit":  [{"account": "4000", "amount": 500.00, "description": "Troškovi"}],
    "credit": [{"account": "2200", "amount": 595.00}],
    "confidence": 0.94,
    "reasoning": "Ulazni račun dobavljača Tele2 — telekomunikacijske usluge",
    "auto_book": True  # confidence >= threshold
}
"""

import json
import logging
import os
from decimal import Decimal

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Confidence threshold for auto-booking
AUTO_BOOK_THRESHOLD = Decimal("0.90")
HUMAN_REVIEW_THRESHOLD = Decimal("0.70")


# -----------------------------------------------
# Vendor history lookup
# -----------------------------------------------

def get_vendor_history(company, vendor_name, limit=5):
    """
    Find previous bookings for this vendor from JournalEntry + LedgerLine.
    Returns the most common account patterns.
    """
    from konto.models import JournalEntry

    if not vendor_name or len(vendor_name) < 2:
        return []

    previous = (
        JournalEntry.objects.filter(
            company=company,
            description__icontains=vendor_name,
            is_posted=True,
        )
        .order_by("-date")[:limit]
    )

    patterns = []
    for entry in previous:
        lines = entry.lines.select_related("account").all()
        pattern = {
            "date": str(entry.date),
            "description": entry.description,
            "lines": [
                {
                    "account": line.account.code,
                    "account_name": line.account.name,
                    "side": line.side,
                    "amount": float(line.amount),
                }
                for line in lines
            ],
        }
        patterns.append(pattern)

    return patterns


# -----------------------------------------------
# Main proposal function
# -----------------------------------------------

def propose_booking(archive_entry):
    """
    Main function: takes an ArhivaEntry and returns a booking proposal.

    Strategy:
    1. Check vendor history -- if >=3 identical patterns, replicate with high confidence
    2. If no/insufficient history, use AI (Claude) to classify
    3. Return structured proposal with confidence score
    """
    company = archive_entry.company
    vendor_name = archive_entry.partner_name or ""
    amount = float(archive_entry.amount or 0)

    # Step 1: Check vendor history
    history = get_vendor_history(company, vendor_name)

    if len(history) >= 3:
        proposal = _proposal_from_history(history, amount, vendor_name)
        if proposal:
            return proposal

    # Step 2: AI classification
    proposal = _proposal_from_ai(archive_entry, history, company)
    return proposal


# -----------------------------------------------
# History-based proposal
# -----------------------------------------------

def _proposal_from_history(history, amount, vendor_name):
    """
    Build proposal by replicating the most common pattern from history.
    Scale amounts proportionally.
    """
    template = history[0]
    template_lines = template["lines"]

    if not template_lines:
        return None

    # Calculate total from template (use debit side total)
    template_total = sum(
        l["amount"] for l in template_lines if l["side"] == "debit"
    )
    if template_total == 0:
        template_total = sum(
            l["amount"] for l in template_lines if l["side"] == "credit"
        )
    if template_total == 0:
        return None

    scale = amount / template_total if template_total else 1.0

    debit_lines = []
    credit_lines = []

    for line in template_lines:
        scaled_amount = round(line["amount"] * scale, 2)
        entry = {
            "account": line["account"],
            "amount": scaled_amount,
            "description": vendor_name,
        }
        if line["side"] == "debit":
            debit_lines.append(entry)
        else:
            credit_lines.append(entry)

    # Check if all history patterns use the same accounts
    template_accounts = set(l["account"] for l in template_lines)
    all_same = all(
        set(l["account"] for l in h["lines"]) == template_accounts
        for h in history[:3]
    )

    confidence = Decimal("0.95") if all_same else Decimal("0.82")

    return {
        "debit": debit_lines,
        "credit": credit_lines,
        "confidence": float(confidence),
        "reasoning": "Replicirano iz {} prethodnih knjiženja za {}".format(
            len(history), vendor_name
        ),
        "auto_book": confidence >= AUTO_BOOK_THRESHOLD,
        "source": "history",
    }


# -----------------------------------------------
# AI-based proposal
# -----------------------------------------------

def _proposal_from_ai(archive_entry, history, company):
    """
    Use Claude AI to classify and propose booking.
    """
    from konto.models import KontoAccount

    try:
        accounts = KontoAccount.objects.filter(
            company=company, is_active=True
        ).values_list("code", "name")[:100]
        account_list = "\n".join(
            "{} - {}".format(code, name) for code, name in accounts
        )
    except DatabaseError:
        account_list = "Standardni HR kontni plan (RRiF)"

    # Build history context
    history_text = ""
    if history:
        history_text = "Prethodna knjiženja istog dobavljača:\n"
        for h in history:
            lines_str = ", ".join(
                "{} {}:{}".format(
                    l["account"],
                    "D" if l["side"] == "debit" else "P",
                    l["amount"],
                )
                for l in h["lines"]
            )
            history_text += "  {}: {} -> {}\n".format(
                h["date"], h["description"], lines_str
            )

    prompt = (
        "Ti si hrvatski ovlašteni računovođa. Predloži knjiženje za ovaj dokument.\n\n"
        "Dokument:\n"
        "- Tip: {source_type}\n"
        "- Dobavljač/partner: {partner}\n"
        "- Broj dokumenta: {doc_number}\n"
        "- Iznos: {amount} {currency}\n"
        "- Datum: {doc_date}\n\n"
        "{history}\n"
        "Dostupni konti:\n{accounts}\n\n"
        "Odgovori ISKLJUČIVO u JSON formatu:\n"
        '{{\n'
        '  "debit": [{{"account": "XXXX", "amount": 0.00, "description": "..."}}],\n'
        '  "credit": [{{"account": "XXXX", "amount": 0.00, "description": "..."}}],\n'
        '  "confidence": 0.XX,\n'
        '  "reasoning": "Kratko obrazloženje"\n'
        '}}\n\n'
        "Pravila:\n"
        "- Ukupni debit MORA biti jednak ukupnom creditu\n"
        "- Za ulazne račune: troškovi na D, obveze dobavljaču na P, pretporez na D\n"
        "- Za izlazne račune: potraživanja na D, prihodi na P, obveza PDV na P\n"
        "- Confidence: 0.95 ako je jasno, 0.80 ako je nejasno, 0.60 ako nagađaš\n"
    ).format(
        source_type=archive_entry.source_type,
        partner=archive_entry.partner_name or "nepoznat",
        doc_number=archive_entry.doc_number or "nema",
        amount=archive_entry.amount,
        currency=archive_entry.currency,
        doc_date=archive_entry.doc_date,
        history=history_text,
        accounts=account_list,
    )

    try:
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")

        if not api_key:
            return _fallback_proposal(archive_entry)

        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        text = response.content[0].text.strip()
        # Extract JSON from response (might be wrapped in markdown)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)
        confidence = Decimal(str(result.get("confidence", 0.5)))

        return {
            "debit": result.get("debit", []),
            "credit": result.get("credit", []),
            "confidence": float(confidence),
            "reasoning": result.get("reasoning", "AI prijedlog"),
            "auto_book": confidence >= AUTO_BOOK_THRESHOLD,
            "source": "ai",
        }

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("AI bookkeeper error: {}".format(e))
        return _fallback_proposal(archive_entry)


# -----------------------------------------------
# Fallback proposal
# -----------------------------------------------

def _fallback_proposal(archive_entry):
    """
    Fallback when AI is unavailable -- puts everything in human review queue.
    """
    amount = float(archive_entry.amount or 0)
    source_type = archive_entry.source_type or ""

    if source_type in ("invoice_in", "eracun", "primka"):
        return {
            "debit": [
                {
                    "account": "4009",
                    "amount": amount,
                    "description": "Nekategorizirani trošak",
                }
            ],
            "credit": [
                {
                    "account": "2200",
                    "amount": amount,
                    "description": "Obveze dobavljačima",
                }
            ],
            "confidence": 0.40,
            "reasoning": "Fallback — AI nedostupan, potrebna ručna klasifikacija",
            "auto_book": False,
            "source": "fallback",
        }
    elif source_type in ("invoice_out",):
        return {
            "debit": [
                {
                    "account": "1200",
                    "amount": amount,
                    "description": "Potraživanja od kupaca",
                }
            ],
            "credit": [
                {
                    "account": "7500",
                    "amount": amount,
                    "description": "Nekategorizirani prihod",
                }
            ],
            "confidence": 0.40,
            "reasoning": "Fallback — AI nedostupan, potrebna ručna klasifikacija",
            "auto_book": False,
            "source": "fallback",
        }
    else:
        return {
            "debit": [],
            "credit": [],
            "confidence": 0.0,
            "reasoning": "Nepoznat tip dokumenta: {} — potrebna ručna klasifikacija".format(
                source_type
            ),
            "auto_book": False,
            "source": "fallback",
        }


# -----------------------------------------------
# Execute booking (create JournalEntry + LedgerLines)
# -----------------------------------------------

def _get_or_create_account(company, code, fallback_name=""):
    """Get or auto-create a KontoAccount by code for the company."""
    from konto.models import KontoAccount

    try:
        return KontoAccount.objects.get(company=company, code=code)
    except KontoAccount.DoesNotExist:
        account_type = "asset"
        if code.startswith("2"):
            account_type = "liability"
        elif code.startswith(("4", "5", "6")):
            account_type = "expense"
        elif code.startswith("7"):
            account_type = "income"
        elif code.startswith("9"):
            account_type = "equity"

        acct = KontoAccount.objects.create(
            company=company,
            code=code,
            name=fallback_name or "Auto-konto {}".format(code),
            account_type=account_type,
            is_active=True,
        )
        logger.info(
            "Auto-created KontoAccount {} - {} for company {}".format(
                code, acct.name, company.pk
            )
        )
        return acct


@transaction.atomic
def _execute_booking(archive_entry, proposal):
    """
    Create JournalEntry + LedgerLines from a proposal.
    Returns the JournalEntry PK.
    """
    from konto.models import JournalEntry, LedgerLine
    from konto.services_file import _next_entry_number

    company = archive_entry.company
    doc_date = archive_entry.doc_date or timezone.now().date()

    entry_number = _next_entry_number(company, "AIB")

    journal = JournalEntry.objects.create(
        company=company,
        entry_number=entry_number,
        date=doc_date,
        description=proposal.get("reasoning", "")[:300],
        source_type="manual",  # closest existing choice; AI origin indicated by AIB- prefix
        is_posted=True,
    )

    for line in proposal.get("debit", []):
        account = _get_or_create_account(
            company, line["account"], line.get("description", "")
        )
        LedgerLine.objects.create(
            journal_entry=journal,
            account=account,
            side="debit",
            amount=Decimal(str(line["amount"])),
            description=line.get("description", "")[:200],
        )

    for line in proposal.get("credit", []):
        account = _get_or_create_account(
            company, line["account"], line.get("description", "")
        )
        LedgerLine.objects.create(
            journal_entry=journal,
            account=account,
            side="credit",
            amount=Decimal(str(line["amount"])),
            description=line.get("description", "")[:200],
        )

    # Mark as booked on ArhivaEntry
    if hasattr(archive_entry, "is_booked"):
        archive_entry.is_booked = True
        archive_entry.save(update_fields=["is_booked"])

    logger.info(
        "AI auto-booked ArhivaEntry {} -> JournalEntry {} (confidence: {})".format(
            archive_entry.pk, journal.entry_number, proposal["confidence"]
        )
    )
    return journal.pk


def _save_review(archive_entry, proposal):
    """
    Save proposal for human review as JSON on ArhivaEntry.ai_proposal.
    """
    if hasattr(archive_entry, "ai_proposal"):
        archive_entry.ai_proposal = proposal
        archive_entry.save(update_fields=["ai_proposal"])
    else:
        logger.info(
            "Review needed for ArhivaEntry {}: {}".format(
                archive_entry.pk, json.dumps(proposal, default=str)
            )
        )


# -----------------------------------------------
# Main entry point
# -----------------------------------------------

def process_archive_entry(archive_entry_id, auto_commit=False):
    """
    Main entry point -- called from Celery task, signal, or view.

    1. Gets the ArhivaEntry
    2. Generates proposal
    3. If auto_commit and confidence >= threshold, creates JournalEntry
    4. Otherwise, saves proposal for human review
    """
    from documents.models import ArhivaEntry

    try:
        entry = ArhivaEntry.objects.select_related("company").get(pk=archive_entry_id)
    except ArhivaEntry.DoesNotExist:
        logger.warning("ArhivaEntry {} not found".format(archive_entry_id))
        return {"status": "not_found"}

    # Skip if already booked
    if getattr(entry, "is_booked", False):
        return {"status": "already_booked"}

    # Skip zero-amount entries
    if not entry.amount or entry.amount <= 0:
        return {"status": "skipped_zero_amount"}

    proposal = propose_booking(entry)

    if auto_commit and proposal.get("auto_book"):
        journal_pk = _execute_booking(entry, proposal)
        return {
            "status": "auto_booked",
            "proposal": proposal,
            "journal_entry_id": journal_pk,
        }
    else:
        _save_review(entry, proposal)
        return {"status": "pending_review", "proposal": proposal}
