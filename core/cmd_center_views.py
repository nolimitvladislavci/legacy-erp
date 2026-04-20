"""
core/cmd_center_views.py — Command Center backend

Endpointi:
  GET  /api/cmd/search/?q=&src=  → JSON rezultati + trending
  GET  /api/cmd/trending/         → JSON top-5 ove sedmice
  POST /api/cmd/chat/             → AI chat poruka → odgovor
  POST /api/cmd/ocr/              → kamera frame → tekst (za search)
"""

import json
import logging
import secrets

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.company_utils import get_user_company
from core.search_audit_models import ChatMessage, SearchAuditLog

logger = logging.getLogger("fenix.cmd_center")

MAX_PER_MODULE = 5


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", ""))[:45]


# ── SEARCH ───────────────────────────────────────────────────────────────────


@login_required
@require_GET
def cmd_search(request):
    """
    GET /api/cmd/search/?q=term&src=text|voice|camera
    Vraća JSON: {results, trending, ai_suggestion}
    Budućnost 2 (Sigurnost): svaki search se logira u SearchAuditLog.
    """
    q = request.GET.get("q", "").strip()
    src = request.GET.get("src", SearchAuditLog.SOURCE_TEXT)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"results": [], "trending": [], "ai_suggestion": None})

    results = []
    if len(q) >= 2:
        results = _do_search(q, company)

    # Audit log
    if len(q) >= 2:
        SearchAuditLog.log(
            company=company,
            query=q,
            source=src,
            result_count=len(results),
            user=request.user,
            ip=_client_ip(request),
        )

    # Trending (uvijek vraćamo, za prikaz ispod praznog input-a)
    trending = SearchAuditLog.trending(company, days=7, limit=5)

    # AI prijedlog kad nema rezultata (Budućnost 1)
    ai_suggestion = None
    if len(q) >= 3 and len(results) == 0:
        ai_suggestion = _ai_suggest_creation(q, company, request.user)

    return JsonResponse(
        {
            "results": results,
            "trending": trending,
            "ai_suggestion": ai_suggestion,
        }
    )


def _do_search(q: str, company) -> list[dict]:
    results = []

    # 1. Fakture
    try:
        from invoicing.models import Invoice

        for inv in Invoice.objects.filter(company=company).filter(
            Q(number__icontains=q) | Q(client_name__icontains=q) | Q(client_oib__icontains=q)
        )[:MAX_PER_MODULE]:
            results.append(
                {
                    "module": "invoicing",
                    "icon": "fa-file-invoice-dollar",
                    "type": "Račun",
                    "title": f"{inv.number} — {inv.client_name}",
                    "subtitle": f"{inv.total} EUR · {inv.get_status_display()}",
                    "url": f"/hr/invoicing/{inv.pk}/",
                }
            )
    except (DatabaseError, Exception):
        pass

    # 2. Arhiva
    try:
        from documents.models import ArhivaEntry

        for e in ArhivaEntry.objects.filter(company=company).filter(
            Q(title__icontains=q) | Q(ocr_text__icontains=q) | Q(ai_summary__icontains=q)
        )[:MAX_PER_MODULE]:
            results.append(
                {
                    "module": "arhiva",
                    "icon": "fa-archive",
                    "type": "Arhiva",
                    "title": e.title,
                    "subtitle": e.ai_summary[:80] if e.ai_summary else str(e.document_date or ""),
                    "url": f"/hr/documents/arhiva/?entry={e.pk}",
                }
            )
    except (DatabaseError, Exception):
        pass

    # 3. Partneri
    try:
        from partners.models import Partner

        for p in Partner.objects.filter(company=company).filter(
            Q(name__icontains=q) | Q(oib__icontains=q) | Q(email__icontains=q)
        )[:MAX_PER_MODULE]:
            results.append(
                {
                    "module": "partners",
                    "icon": "fa-building",
                    "type": "Partner",
                    "title": p.name,
                    "subtitle": p.oib or p.email or "",
                    "url": f"/hr/partners/{p.pk}/",
                }
            )
    except (DatabaseError, Exception):
        pass

    # 4. Dokumenti (opći)
    try:
        from documents.models import Document

        for d in Document.objects.filter(company=company).filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(reference_number__icontains=q)
        )[:MAX_PER_MODULE]:
            results.append(
                {
                    "module": "documents",
                    "icon": "fa-file-alt",
                    "type": "Dokument",
                    "title": d.title,
                    "subtitle": d.reference_number or "",
                    "url": f"/hr/documents/{d.pk}/",
                }
            )
    except (DatabaseError, Exception):
        pass

    # 5. Stranice/moduli (iz menija — lokalno, bez DB)
    # Dodano samo ako je malo rezultata
    if len(results) < 5:
        page_hits = _search_pages(q)
        results.extend(page_hits[: max(0, 5 - len(results))])

    return results[:20]


def _search_pages(q: str) -> list[dict]:
    """Pretraga statičnih stranica/modula po ključnim riječima."""
    PAGES = [
        {"title": "Digitalna arhiva", "url": "/hr/documents/arhiva/", "icon": "fa-archive", "type": "Stranica"},
        {"title": "Upload dokumenta", "url": "/hr/documents/arhiva/upload/", "icon": "fa-upload", "type": "Stranica"},
        {"title": "Fakture / Računi", "url": "/hr/invoicing/", "icon": "fa-file-invoice", "type": "Stranica"},
        {"title": "POS blagajna", "url": "/hr/pos/", "icon": "fa-cash-register", "type": "Stranica"},
        {"title": "Smart Import (AI)", "url": "/hr/smart-import/", "icon": "fa-magic", "type": "Stranica"},
        {"title": "Partneri / Klijenti", "url": "/hr/partners/", "icon": "fa-handshake", "type": "Stranica"},
        {"title": "Zaposlenici", "url": "/hr/payroll/", "icon": "fa-users", "type": "Stranica"},
        {"title": "AI Cockpit — Doktor", "url": "/hr/ai-cockpit/doktor/", "icon": "fa-stethoscope", "type": "Stranica"},
        {"title": "Konto / Knjiženje", "url": "/hr/konto/", "icon": "fa-calculator", "type": "Stranica"},
        {"title": "eRačun", "url": "/hr/eracun/", "icon": "fa-file-code", "type": "Stranica"},
        {"title": "DATEV 2030 Export", "url": "/hr/konto/datev-2030/", "icon": "fa-file-export", "type": "Stranica"},
        {"title": "Postavke tvrtke", "url": "/hr/companies/postavke/", "icon": "fa-cog", "type": "Stranica"},
    ]
    ql = q.lower()
    return [p for p in PAGES if ql in p["title"].lower()]


def _ai_suggest_creation(q: str, company, user) -> dict | None:
    """
    Budućnost 1 — DeepSeek intent detection.
    Kad search ne pronalazi ništa → AI predlaže kreiranje entiteta.
    Async: ne blokira search response, vraća sync brzi prijedlog.
    """
    # Brzi rule-based intent (za instant response, bez API poziva)
    ql = q.lower()
    suggestions = [
        (["faktur", "račun", "invoice"], "Kreirati novi račun", "/hr/invoicing/new/", "fa-file-invoice-dollar"),
        (["ugovor", "contract"], "Kreirati ugovor", "/hr/documents/arhiva/upload/", "fa-file-signature"),
        (["partner", "klijent", "dobavljač", "firma"], "Dodati partnera", "/hr/partners/new/", "fa-building-plus"),
        (
            ["zaposlenik", "radnik", "worker", "employee"],
            "Dodati zaposlenika",
            "/hr/payroll/employees/new/",
            "fa-user-plus",
        ),
        (["dokument", "slika", "pdf", "scan"], "Uploadati dokument", "/hr/documents/arhiva/upload/", "fa-upload"),
        (["pos", "blagajna", "receipt", "isječak"], "Otvoriti POS", "/hr/pos/", "fa-cash-register"),
    ]
    for keywords, label, url, icon in suggestions:
        if any(kw in ql for kw in keywords):
            # Log da je AI prijedlog dat
            SearchAuditLog.objects.filter(company=company, user=user, query=q).order_by("-searched_at").update(
                ai_suggested=True
            )
            return {"label": label, "url": url, "icon": icon, "query": q}

    # Ako ništa ne matchira: generički prijedlog za upload/kreiranje
    return {
        "label": f'Nema rezultata za "{q[:40]}" — Uploadati dokument?',
        "url": "/hr/documents/arhiva/upload/",
        "icon": "fa-circle-question",
        "query": q,
    }


# ── TRENDING ─────────────────────────────────────────────────────────────────


@login_required
@require_GET
def cmd_trending(request):
    """GET /api/cmd/trending/ → JSON {trending: [...], total_searches: N}"""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"trending": []})

    trending = SearchAuditLog.trending(company, days=7, limit=5)
    return JsonResponse({"trending": trending})


# ── CHAT (AI razgovor) ───────────────────────────────────────────────────────


@login_required
@csrf_exempt
@require_POST
def cmd_chat(request):
    """
    POST /api/cmd/chat/
    Body: {message, session_id}
    Returns: {reply, search_results, suggested_actions, session_id}

    Budućnost 1: DeepSeek intent → search → suggest create.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    message = data.get("message", "").strip()
    session_id = data.get("session_id") or secrets.token_hex(16)

    if not message:
        return JsonResponse({"error": "Prazna poruka"}, status=400)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "No company"}, status=403)

    # Spremi user poruku
    ChatMessage.objects.create(
        company=company,
        user=request.user,
        session_id=session_id,
        role=ChatMessage.ROLE_USER,
        content=message,
    )

    # Pokušaj search za kontekst
    search_results = _do_search(message, company) if len(message) >= 2 else []

    # AI odgovor (DeepSeek async ili brzi rule-based)
    reply, suggested_actions = _generate_chat_reply(message, search_results, company, request.user, session_id)

    # Spremi AI odgovor
    ChatMessage.objects.create(
        company=company,
        user=request.user,
        session_id=session_id,
        role=ChatMessage.ROLE_ASSISTANT,
        content=reply,
        metadata={
            "search_results": len(search_results),
            "suggested_actions": suggested_actions,
        },
    )

    # Audit log
    SearchAuditLog.log(
        company=company,
        query=message,
        source=SearchAuditLog.SOURCE_CHAT,
        result_count=len(search_results),
        user=request.user,
        ip=_client_ip(request),
    )

    return JsonResponse(
        {
            "reply": reply,
            "search_results": search_results[:5],
            "suggested_actions": suggested_actions,
            "session_id": session_id,
        }
    )


def _generate_chat_reply(message: str, results: list, company, user, session_id: str):
    """
    Brzi rule-based odgovor + async DeepSeek za složene upite.
    Ne blokira — DeepSeek se poziva async, ovdje vraćamo instant reply.
    """
    ml = message.lower()
    suggested_actions = []

    # Ima rezultata → prikaži
    if results:
        titles = [r["title"] for r in results[:3]]
        reply = f'Pronašao sam {len(results)} rezultata za "{message[:40]}":\n' + "\n".join(f"• {t}" for t in titles)
        if len(results) > 3:
            reply += f"\n... i još {len(results) - 3} više."
        return reply, suggested_actions

    # Intent routing
    if any(w in ml for w in ["faktur", "račun", "napravi faktur"]):
        suggested_actions = [{"label": "Novi račun", "url": "/hr/invoicing/new/", "icon": "fa-plus"}]
        reply = "Nema pronađenih faktura. Kreirajte novu?"
    elif any(w in ml for w in ["upload", "dodaj dokument", "slika", "pdf"]):
        suggested_actions = [{"label": "Upload dokumenta", "url": "/hr/documents/arhiva/upload/", "icon": "fa-upload"}]
        reply = "Možete uploadati dokument u Digitalnu arhivu."
    elif any(w in ml for w in ["trend", "kolege traže", "popular", "što se traži"]):
        trending = SearchAuditLog.trending(company, days=7, limit=5)
        if trending:
            reply = "Ove sedmice vaši kolege traže:\n" + "\n".join(f"• {t}" for t in trending)
        else:
            reply = "Još nema trending podataka za ovu sedmicu."
    elif any(w in ml for w in ["pomoć", "help", "što mogu", "komande"]):
        reply = (
            "Mogu vam pomoći s:\n"
            "• Pretraživanjem faktura, dokumenata, partnera\n"
            "• Navigacijom po sustavu\n"
            "• Prijedlozima kreiranja novih entiteta\n"
            "Upišite što tražite ili koristite 🎤 glas ili 📷 kameru."
        )
    else:
        # Async DeepSeek (fire-and-forget) za složenije upite
        _trigger_deepseek_chat(message, company, user, session_id)
        reply = "Tražim po sustavu... za kompleksnije upite koristim AI analizu."
        suggested_actions = [
            {"label": "Smart Import (AI)", "url": "/hr/smart-import/", "icon": "fa-magic"},
            {"label": "AI Cockpit", "url": "/hr/ai-cockpit/doktor/", "icon": "fa-stethoscope"},
        ]

    return reply, suggested_actions


def _trigger_deepseek_chat(message: str, company, user, session_id: str) -> None:
    """Fire-and-forget DeepSeek task za složene chat upite."""
    try:
        from core.cmd_center_tasks import deepseek_chat_task

        deepseek_chat_task.apply_async(
            args=[message, company.pk, user.pk, session_id],
            countdown=1,
        )
    except Exception as e:
        logger.debug("DeepSeek chat task failed: %s", e)


# ── OCR iz kamere ─────────────────────────────────────────────────────────────


@login_required
@csrf_exempt
@require_POST
def cmd_ocr(request):
    """
    POST /api/cmd/ocr/
    Body: multipart form — file=image
    Returns: {text} — prepoznati tekst koji se stavlja u search input
    """
    img_file = request.FILES.get("file")
    if not img_file:
        return JsonResponse({"error": "No file"}, status=400)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "No company"}, status=403)

    try:
        from core.ai_gateway import gateway

        img_bytes = img_file.read()
        result = gateway.ocr(
            img_bytes,
            prompt="Extract the main searchable text from this image. Return only the key words/phrases relevant for searching: names, numbers, dates. Max 200 chars.",
        )
        text = result.content.strip()[:200] if result.success else ""
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        text = ""

    return JsonResponse({"text": text})
