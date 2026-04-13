"""
Trojstvo — AI konsenzus sustav (v2)
====================================
Pravila zapisana u: FENIX_TROJSTVO_PRAVILA.md

Tok:
  1. Korisnik → zlatno dugme → ImprovementSuggestion
  2. trojstvo_rijesi pokreće Haiku + Gemini paralelno
  3. Sonnet uspoređuje:
     - Slažu se (≥65%, zajednička ključna riječ) → log file, bez WhatsApp
     - Ne slažu se → WhatsApp Ivanu
"""
import logging
import json
import os
from datetime import datetime

from celery import shared_task

logger = logging.getLogger('trojstvo')

IVAN_PHONE   = '+4915771998747'
AGREED_LOG   = '/var/log/trojstvo/agreed.log'
CONFLICT_LOG = '/var/log/trojstvo/conflict.log'


@shared_task(bind=True, soft_time_limit=180, max_retries=1)
def trojstvo_rijesi(self, suggestion_id):
    from pos.models import ImprovementSuggestion
    from django.db import transaction

    try:
        with transaction.atomic():
            s = ImprovementSuggestion.objects.select_for_update().get(pk=suggestion_id)
            s.trojstvo_status = 'pending'
            s.save(update_fields=['trojstvo_status'])
    except ImprovementSuggestion.DoesNotExist:
        logger.error('Trojstvo: suggestion %s ne postoji', suggestion_id)
        return

    # ── Zlatni Paket: obogaceni kontekst za AI ──
    problem = (
        f"PROBLEM: {s.title}\n\n"
        f"OPIS: {s.description}\n\n"
        f"KATEGORIJA: {s.category or 'pos'} | PRIORITET: {s.priority}/5 | "
        f"FIRMA: {s.company}\n\n"
    )

    # Dodaj error log (zadnjih 20 linija)
    try:
        import os
        log_path = '/var/www/fina-connect/logs/django.log'
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                lines = f.readlines()
            recent_errors = [l.strip() for l in lines[-100:] if 'ERROR' in l or 'Traceback' in l][-20:]
            if recent_errors:
                problem += "RECENT ERRORS (zadnjih 20):\n" + "\n".join(recent_errors) + "\n\n"
    except Exception:
        pass

    # Dodaj BookingSignature (zadnjih 10 akcija autora)
    try:
        from core.models import BookingSignature
        recent_actions = BookingSignature.objects.filter(
            user=s.author
        ).order_by('-timestamp')[:10]
        if recent_actions:
            actions_str = "\n".join(
                f"  {a.timestamp:%H:%M} {a.action} {a.target_model}:{a.target_id}"
                for a in recent_actions
            )
            problem += f"KORISNIKOVE AKCIJE (zadnjih 10):\n{actions_str}\n\n"
    except Exception:
        pass

    # Dodaj screenshot info
    if '[screenshot:' in (s.admin_note or ''):
        problem += "SCREENSHOT: prilozen (vidi admin_note)\n\n"

    # Dodaj terminal info ako je POS kategorija
    if s.category in ('pos', 'workflow'):
        try:
            from pos.models import POSTerminal
            terminals = POSTerminal.objects.filter(company=s.company, is_active=True)
            term_info = ", ".join(f"{t.name} ({t.pos_type})" for t in terminals[:5])
            problem += f"POS TERMINALI: {term_info}\n"
        except Exception:
            pass

    def _safe_save(fields):
        from pos.models import ImprovementSuggestion
        rows = ImprovementSuggestion.objects.filter(pk=suggestion_id).update(
            **{f: getattr(s, f) for f in fields}
        )
        if not rows:
            raise ImprovementSuggestion.DoesNotExist(f'suggestion {suggestion_id} deleted mid-task')

    try:
        haiku_result  = _haiku_analiza(problem)
        s.haiku_proposal = haiku_result
        _safe_save(['haiku_proposal'])

        gemini_result = _gemini_analiza(problem)
        s.gemini_proposal = gemini_result
        _safe_save(['gemini_proposal'])

        agreed, postotak, resolution = _konsenzus(problem, haiku_result, gemini_result)

        s.ai_resolution   = resolution
        s.trojstvo_status = 'agreed' if agreed else 'conflict'
        s.status          = 'reviewed'
        _safe_save(['ai_resolution', 'trojstvo_status', 'status'])

        if agreed:
            _log_agreed(s, postotak, resolution)
            logger.info('Trojstvo AGREED %s%%: %s', postotak, s.title)
        else:
            _log_conflict(s, haiku_result, gemini_result)
            _whatsapp_ivan(s, postotak, haiku_result, gemini_result)
            logger.info('Trojstvo CONFLICT %s%%: %s → WhatsApp poslan', postotak, s.title)

    except Exception as exc:
        from pos.models import ImprovementSuggestion
        ImprovementSuggestion.objects.filter(pk=suggestion_id).update(
            trojstvo_status='error',
            ai_resolution=f'Greška: {exc}'[:500],
        )
        logger.error('Trojstvo greška za %s: %s', suggestion_id, exc)
        raise self.retry(exc=exc)


# ── Haiku analiza ─────────────────────────────────────────────────────────────

def _haiku_analiza(problem: str) -> str:
    """
    Haiku kao primarni inženjer (v2 — Advisor Strategy 2026-04-09).
    Za arhitekturalne/sigurnosne probleme konzultira Opus max 2 puta.
    """
    from core.anthropic_advisor import haiku_with_advisor

    system = (
        "Ti si senior Django inženjer na LIMIT Connect ERP/POS sustavu "
        "(Django 5.1, PostgreSQL, Celery, Redis, Nginx, WeasyPrint, WAHA). "
        "Baza: 668+ modela, 80+ klijenata, multi-tenant arhitektura, "
        "hrvatska fiskalizacija (FINA certifikati), GDPR. "
        "Imaš pristup Opus advisoru — konzultiraj ga SAMO za: "
        "arhitekturalne promjene, sigurnosne probleme, FSM tranzicije, "
        "migracijske rizike, multi-tenant izolaciju, fiskalizacijske greške. "
        "Za standardne bugove i manje promjene — rješavaj sam."
    )

    prompt = (
        f"{problem}\n\n"
        "Odgovori KONKRETNO:\n"
        "## Dijagnoza\n[Uzrok — koji fajl, koja linija, koji model]\n\n"
        "## Rješenje\n[Koraci — što promijeniti, gdje, kako]\n\n"
        "## Složenost\n[Procjena: X sati, razlog]\n\n"
        "Bez floskula. Bez uvoda. Samo tehnika."
    )

    return haiku_with_advisor(
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=1500,
        max_uses=2,
        system=system,
    )


# ── Gemini analiza ────────────────────────────────────────────────────────────

def _gemini_analiza(problem: str) -> str:
    import google.generativeai as genai
    from django.conf import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = (
        "Ti si senior Django inženjer na LIMIT Connect ERP/POS sustavu (Django 5.1, "
        "PostgreSQL, Celery, Redis, Nginx). Baza ima 543+ tablica, 80+ klijenata.\n\n"
        f"{problem}\n\n"
        "Odgovori KONKRETNO:\n"
        "## Dijagnoza\n[Uzrok — koji fajl, koja linija, koji model]\n\n"
        "## Rješenje\n[Koraci — što promijeniti, gdje, kako]\n\n"
        "## Složenost\n[Procjena: X sati, razlog]\n\n"
        "Bez floskula. Bez uvoda. Samo tehnika."
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# ── Konsenzus ─────────────────────────────────────────────────────────────────

def _konsenzus(problem: str, haiku: str, gemini: str):
    """
    Vraća (agreed: bool, postotak: int, resolution: str)
    agreed = True ako ≥65% slaganja I postoji zajednička ključna riječ u rješenjima
    """
    import anthropic
    from django.conf import settings

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = (
        f"Dva inženjera su analizirala isti problem neovisno.\n\n"
        f"PROBLEM:\n{problem}\n\n"
        f"HAIKU:\n{haiku}\n\n"
        f"GEMINI:\n{gemini}\n\n"
        "Odgovori SAMO validnim JSON-om (bez komentara, bez markdowna):\n"
        '{"slazu_se": true/false, '
        '"postotak": 0-100, '
        '"zajednicke_rijeci": ["lista", "ključnih", "termina", "koje", "dijele"], '
        '"zajednicko_rjesenje": "Jedno konkretno rješenje u 3-5 rečenica.", '
        '"razlika": "Što je drugačije između prijedloga (1-2 rečenice).", '
        '"prioritet": "odmah/ovaj-tjedan/sljedeci-sprint"}'
    )

    msg = client.messages.create(
        model='claude-sonnet-4-5',
        max_tokens=600,
        messages=[{'role': 'user', 'content': prompt}]
    )
    text = msg.content[0].text.strip()
    if '```' in text:
        text = text.split('```')[1].lstrip('json').strip()

    data = json.loads(text)

    postotak         = data.get('postotak', 0)
    zajednicke       = data.get('zajednicke_rijeci', [])
    zajednicko       = data.get('zajednicko_rjesenje', '')
    razlika          = data.get('razlika', '')
    prioritet        = data.get('prioritet', '')

    # Slažu se: ≥65% I barem 1 zajednička ključna riječ
    agreed = postotak >= 65 and len(zajednicke) > 0

    if agreed:
        resolution = (
            f"✅ DOGOVORENO ({postotak}% slaganja)\n"
            f"Zajednički termini: {', '.join(zajednicke)}\n\n"
            f"RJEŠENJE: {zajednicko}\n\n"
            f"Prioritet: {prioritet}"
        )
    else:
        resolution = (
            f"⚡ CONFLICT ({postotak}% slaganja)\n"
            f"Razlika: {razlika}\n\n"
            f"Haiku predlaže:\n{haiku[:400]}\n\n"
            f"Gemini predlaže:\n{gemini[:400]}"
        )

    return agreed, postotak, resolution


# ── Log i WhatsApp ────────────────────────────────────────────────────────────

def _log_agreed(s, postotak, resolution):
    """Dogovoreno → log file, bez WhatsApp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f"[{timestamp}] [#{s.pk}] {postotak}% | {s.title} | {resolution[:200]}\n"
    try:
        with open(AGREED_LOG, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        logger.error('Agreed log greška: %s', e)


def _log_conflict(s, haiku, gemini):
    """Conflict → log file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = (
        f"[{timestamp}] [#{s.pk}] CONFLICT | {s.title}\n"
        f"  Haiku: {haiku[:150]}\n"
        f"  Gemini: {gemini[:150]}\n\n"
    )
    try:
        with open(CONFLICT_LOG, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        logger.error('Conflict log greška: %s', e)


def _whatsapp_ivan(s, postotak, haiku, gemini):
    """Conflict → WhatsApp Ivanu. Agreed → NIŠTA."""
    try:
        from core.whatsapp import send_text
        prio_emoji = {1: '🔴', 2: '🟠', 3: '🟡', 4: '🔵', 5: '⚪'}.get(s.priority, '❓')
        msg = (
            f"⚡ TROJSTVO CONFLICT\n"
            f"{prio_emoji} P{s.priority} | {s.company}\n"
            f"Problem: {s.title}\n\n"
            f"Haiku ({postotak}% slaganja):\n"
            f"{haiku[:200]}\n\n"
            f"Gemini:\n"
            f"{gemini[:200]}\n\n"
            f"Ivan, tvoja odluka: limit-connect.com/hr/pos/improvements/"
        )
        send_text(IVAN_PHONE, msg)
    except Exception as e:
        logger.error('WhatsApp greška: %s', e)
