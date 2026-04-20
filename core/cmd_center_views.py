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


# ═══════════════════════════════════════════════════════════════════════════════
# NADOGRADNJA — 4 mehanizma
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. CROSS-MODULE INTELLIGENCE ─────────────────────────────────────────────


@login_required
@require_GET
def cmd_cross_module(request):
    """
    GET /api/cmd/cross/?q=term&entity_type=partner&entity_id=123

    Kad korisnik klikne rezultat (npr. Partner Baumaxx),
    vraćamo sve povezane zapise tog entiteta:
      - fakture tog partnera
      - arhiva dokumenti
      - zadnje aktivnosti

    UI prikazuje "intelligence panel" pored glavnih rezultata.
    """
    q = request.GET.get("q", "").strip()
    entity_type = request.GET.get("entity_type", "")
    entity_id = request.GET.get("entity_id", "")

    company = get_user_company(request)
    if not company:
        return JsonResponse({"related": [], "summary": ""})

    related = []
    summary = ""

    if entity_type == "partner" and entity_id:
        related, summary = _cross_partner(entity_id, company)
    elif entity_type == "invoice" and entity_id:
        related, summary = _cross_invoice(entity_id, company)
    elif q and not entity_type:
        # Fuzzy cross — ako nema explicit entity, pronađi po upitu
        related, summary = _cross_fuzzy(q, company)

    return JsonResponse({"related": related, "summary": summary})


def _cross_partner(entity_id: str, company) -> tuple[list, str]:
    """Sve što se tiče tog partnera/firme."""
    related = []
    partner_name = ""
    try:
        from partners.models import Partner

        p = Partner.objects.filter(pk=entity_id, company=company).first()
        if p:
            partner_name = p.name
    except Exception:
        pass

    name_q = partner_name or entity_id

    # Fakture za tog partnera
    try:
        from django.db.models import Sum

        from invoicing.models import Invoice

        invs = Invoice.objects.filter(company=company, client_name__icontains=name_q).order_by("-created_at")[:5]
        total = (
            Invoice.objects.filter(company=company, client_name__icontains=name_q).aggregate(t=Sum("total"))["t"] or 0
        )
        for inv in invs:
            related.append(
                {
                    "module": "invoicing",
                    "icon": "fa-file-invoice-dollar",
                    "type": "Račun",
                    "title": f"{inv.number} — {inv.total} EUR",
                    "subtitle": inv.get_status_display(),
                    "url": f"/hr/invoicing/{inv.pk}/",
                }
            )
        if total:
            summary += f"Ukupno faktura: {total:.2f} EUR. "
    except Exception:
        pass

    # Arhiva dokumenti za tog partnera
    try:
        from documents.models import ArhivaEntry

        docs = ArhivaEntry.objects.filter(company=company, title__icontains=name_q).order_by("-created_at")[:3]
        for d in docs:
            related.append(
                {
                    "module": "arhiva",
                    "icon": "fa-archive",
                    "type": "Arhiva",
                    "title": d.title,
                    "subtitle": str(d.document_date or ""),
                    "url": f"/hr/documents/arhiva/?entry={d.pk}",
                }
            )
    except Exception:
        pass

    if not summary:
        summary = f"Pronađeno {len(related)} povezanih zapisa za {partner_name or entity_id}."
    return related, summary


def _cross_invoice(entity_id: str, company) -> tuple[list, str]:
    """Sve fakture istog klijenta + arhiva."""
    related = []
    summary = ""
    try:
        from invoicing.models import Invoice

        inv = Invoice.objects.filter(pk=entity_id, company=company).first()
        if not inv:
            return related, summary
        # Ostale fakture istog klijenta
        others = (
            Invoice.objects.filter(company=company, client_name=inv.client_name)
            .exclude(pk=entity_id)
            .order_by("-created_at")[:5]
        )
        for o in others:
            related.append(
                {
                    "module": "invoicing",
                    "icon": "fa-file-invoice-dollar",
                    "type": "Račun",
                    "title": f"{o.number} — {o.total} EUR",
                    "subtitle": o.get_status_display(),
                    "url": f"/hr/invoicing/{o.pk}/",
                }
            )
        summary = f"Klijent: {inv.client_name} · {len(others)} ostalih računa."
    except Exception:
        pass
    return related, summary


def _cross_fuzzy(q: str, company) -> tuple[list, str]:
    """Fuzzy cross: traži entityje koji se pojavljuju u više modula."""
    related = []
    # Uzmi prvih 5 normalnih rezultata i dodaj cross-links
    base = _do_search(q, company)
    if base:
        related = base[:5]
        summary = f"Pronađeno u {len(set(r['module'] for r in base))} modula."
    else:
        summary = ""
    return related, summary


# ── 2. LIVE COLLABORATION ─────────────────────────────────────────────────────

_LIVE_KEY = "cmd:live:{company_id}"
_LIVE_TTL = 25  # sekundi — koliko dugo ostaje "active"
_LIVE_LIMIT = 10  # max korisnika u live setu


@login_required
@require_GET
def cmd_live(request):
    """
    GET /api/cmd/live/?q=

    Dual role:
      1. Ako je q prisutan → publisha "user X traži q" u Redis
      2. Uvijek vraća tko je aktivan u firmi (zadnjih 25s)

    Vraća: {active: [{username, query, ts}], count: N}
    Frontend polla ovo svakih 8s.
    """
    q = request.GET.get("q", "").strip()
    company = get_user_company(request)
    if not company:
        return JsonResponse({"active": [], "count": 0})

    try:
        from django.core.cache import cache

        redis_key = _LIVE_KEY.format(company_id=company.pk)

        # Dohvati postojeći live set
        live_set: list = cache.get(redis_key) or []

        # Ukloni stare zapise (> TTL)
        import time

        now = time.time()
        live_set = [e for e in live_set if now - e.get("ts", 0) < _LIVE_TTL]

        # Update ili dodaj current user
        if q and len(q) >= 2:
            username = request.user.get_full_name() or request.user.username
            # Ukloni stari zapis za ovog usera
            live_set = [e for e in live_set if e.get("uid") != request.user.pk]
            live_set.append(
                {
                    "uid": request.user.pk,
                    "username": username,
                    "query": q[:60],
                    "ts": now,
                }
            )
            live_set = live_set[-_LIVE_LIMIT:]
            cache.set(redis_key, live_set, _LIVE_TTL)

        # Pripremi response — ne prikazuj current usera drugima (ali vrati count)
        others = [{"username": e["username"], "query": e["query"]} for e in live_set if e.get("uid") != request.user.pk]

    except Exception as e:
        logger.debug("cmd_live redis error: %s", e)
        others = []

    return JsonResponse({"active": others, "count": len(others)})


# ── 3. ZERO-RESULT DEEPSEEK ──────────────────────────────────────────────────


@login_required
@require_GET
def cmd_zero_result_ai(request):
    """
    GET /api/cmd/zero/?q=term

    Kada search vrati 0 rezultata → pravi DeepSeek poziv s contextom firme.
    Vraća: {answer, actions, confidence}

    Nije rule-based — pravi AI koji razumije kontekst.
    Cache: 5 minuta po (company, query) paru.
    """
    q = request.GET.get("q", "").strip()
    if len(q) < 3:
        return JsonResponse({"answer": "", "actions": [], "confidence": 0})

    company = get_user_company(request)
    if not company:
        return JsonResponse({"answer": "", "actions": [], "confidence": 0})

    # Cache po company+query (5min)
    from django.core.cache import cache

    cache_key = f"cmd:zero:{company.pk}:{hash(q.lower())}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    result = _call_deepseek_zero(q, company, request.user)
    cache.set(cache_key, result, 300)
    return JsonResponse(result)


def _call_deepseek_zero(q: str, company, user) -> dict:
    """Pravi DeepSeek poziv za zero-result situacije."""
    # Skupi company context
    context_lines = [f"Tvrtka: {company.name}"]
    try:
        from invoicing.models import Invoice

        inv_count = Invoice.objects.filter(company=company).count()
        context_lines.append(f"Faktura u sustavu: {inv_count}")
    except Exception:
        pass
    try:
        from documents.models import ArhivaEntry

        doc_count = ArhivaEntry.objects.filter(company=company).count()
        context_lines.append(f"Dokumenata u arhivi: {doc_count}")
    except Exception:
        pass
    try:
        recent = SearchAuditLog.trending(company, days=7, limit=3)
        if recent:
            context_lines.append(f"Nedavne pretrage: {', '.join(recent)}")
    except Exception:
        pass

    company_ctx = "\n".join(context_lines)

    prompt = f"""Ti si AI asistent u ERP sustavu za računovodstvo (LIMIT Connect / Fenix).
Korisnik je tražio: "{q}"
Pretraživanje nije pronašlo ništa.

Kontekst tvrtke:
{company_ctx}

Dostupni moduli: Fakture (/hr/invoicing/), Arhiva (/hr/documents/arhiva/), 
Partneri (/hr/partners/), POS (/hr/pos/), Smart Import (/hr/smart-import/),
AI Cockpit (/hr/ai-cockpit/doktor/), Konto (/hr/konto/), eRačun (/hr/eracun/).

Odgovori na hrvatskom u JSON formatu:
{{
  "answer": "kratko objašnjenje što je korisnik vjerojatno htio i zašto nema rezultata (max 2 rečenice)",
  "actions": [
    {{"label": "Naziv akcije", "url": "/hr/...", "icon": "fa-plus", "priority": 1}},
    ...max 3 akcije
  ],
  "confidence": 0.0-1.0
}}

Samo JSON, bez markdowna."""

    try:
        from core.deepseek_client import DeepSeekClient

        client = DeepSeekClient()
        raw = client.chat(prompt, max_tokens=400)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json as _json

        parsed = _json.loads(raw)
        return {
            "answer": parsed.get("answer", ""),
            "actions": parsed.get("actions", [])[:3],
            "confidence": float(parsed.get("confidence", 0.5)),
        }
    except Exception as e:
        logger.warning("DeepSeek zero-result failed: %s", e)
        # Fallback: strukturirani rule-based
        sug = _ai_suggest_creation(q, company, user)
        return {
            "answer": f"Nema zapisa za '{q[:40]}' u sustavu. Možda trebate kreirati novi zapis?",
            "actions": [{"label": sug["label"], "url": sug["url"], "icon": sug["icon"], "priority": 1}] if sug else [],
            "confidence": 0.3,
        }


# ── 4. PREFETCH ENDPOINT (za SearchPrefetcher) ────────────────────────────────


@login_required
@require_GET
def cmd_prefetch(request):
    """
    GET /api/cmd/prefetch/?prefixes=fa,fak,faktu

    Batch endpoint — prima listu prefiksa, vraća rezultate za svaki.
    Koristi SearchPrefetcher na frontendu koji predviđa sljedeće znakove.
    Odgovara max 3 prefiksa po zahtjevu, svaki max 3 rezultata.
    """
    raw = request.GET.get("prefixes", "")
    prefixes = [p.strip() for p in raw.split(",") if len(p.strip()) >= 2][:3]

    company = get_user_company(request)
    if not company or not prefixes:
        return JsonResponse({"prefetched": {}})

    from django.core.cache import cache

    out = {}
    for pref in prefixes:
        cache_key = f"cmd:pf:{company.pk}:{pref.lower()[:20]}"
        hits = cache.get(cache_key)
        if hits is None:
            hits = _do_search(pref, company)[:3]
            cache.set(cache_key, hits, 120)  # 2min cache
        out[pref] = hits

    return JsonResponse({"prefetched": out})


# ── 5. TEMPORAL PREDICTION ENDPOINT ─────────────────────────────────────────


@login_required
@require_GET
def cmd_predict(request):
    """
    GET /api/cmd/predict/

    Temporalna predikcija — što se traži u ovo doba dana/tjedna.

    Response:
    {
        "personal": ["faktura Horvat", ...],
        "team":     ["DPO izvještaj", ...],
        "confidence": 0.72,
        "window_label": "ponedjeljak jutro",
        "has_data": true
    }

    Frontend: FenixTemporalPredictor — prikazuje chipove ispod inputa
    kad je prazan, nestaju čim user počne tipkati.
    """
    from .search_audit_models import SearchAuditLog

    company = get_user_company(request)
    if not company:
        return JsonResponse({"personal": [], "team": [], "confidence": 0.0, "has_data": False})

    from django.core.cache import cache

    cache_key = f"cmd:predict:{company.pk}:{request.user.pk}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    result = SearchAuditLog.temporal_prediction(company=company, user=request.user, limit=3)
    result["has_data"] = bool(result["personal"] or result["team"])

    cache.set(cache_key, result, 300)  # 5min — podaci se ne mijenjaju minutno
    return JsonResponse(result)
