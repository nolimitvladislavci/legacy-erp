"""
core/cmd_center_tasks.py — Async AI taskovi za Command Center

- deepseek_chat_task: složeni chat upiti → DeepSeek → update ChatMessage
"""

import logging

from celery import shared_task

logger = logging.getLogger("fenix.cmd_center")


@shared_task(name="cmd_center.deepseek_chat", max_retries=2, default_retry_delay=30)
def deepseek_chat_task(message: str, company_id: int, user_id: int, session_id: str) -> dict:
    """
    Budućnost 1 — DeepSeek intent + entity suggestion.
    Poziva se async kad rule-based engine ne zna odgovor.
    Sprema odgovor kao ChatMessage i signalizira WS push (ako postoji).
    """
    from django.contrib.auth import get_user_model

    from companies.models import Company
    from core.cmd_center_views import _do_search
    from core.search_audit_models import ChatMessage

    try:
        company = Company.objects.get(pk=company_id)
        _user = get_user_model().objects.get(pk=user_id)  # noqa: F841 (reserved for future use)
    except Exception as e:
        logger.error("deepseek_chat: lookup failed — %s", e)
        return {"error": str(e)}

    # Dohvati search context
    search_results = _do_search(message, company)

    # Izgradi prompt za DeepSeek
    context_str = ""
    if search_results:
        lines = [f"- {r['type']}: {r['title']} ({r['url']})" for r in search_results[:5]]
        context_str = "Pronađeno u sustavu:\n" + "\n".join(lines)

    prompt = f"""Ti si inteligentni asistent u računovodstvenom ERP sustavu LIMIT Connect.
Korisnik pita: "{message}"

{context_str if context_str else "Pretraživanje nije pronašlo rezultate u sustavu."}

Daj kratak, koristan odgovor na hrvatskom. Ako preporučuješ akciju, navedi konkretni URL iz sustava.
Budi koncizan (max 3 rečenice)."""

    reply = ""
    try:
        from core.deepseek_client import DeepSeekClient

        client = DeepSeekClient()
        result = client.chat(prompt, max_tokens=300)
        reply = result.strip() if result else ""
    except Exception as e:
        logger.warning("DeepSeek chat failed: %s", e)
        if search_results:
            reply = f"Pronašao sam {len(search_results)} relevantnih zapisa. Kliknite na rezultat za detalje."
        else:
            reply = "Nisam pronašao odgovarajuće podatke. Probajte uploadati dokument ili kreirajte novi zapis."

    # Spremi AI odgovor (zamijeni placeholder)
    ChatMessage.objects.filter(
        session_id=session_id,
        role=ChatMessage.ROLE_ASSISTANT,
        content__startswith="Tražim po sustavu",
    ).order_by("-created_at").update(
        content=reply,
        metadata={"deepseek": True, "search_results": len(search_results)},
    )

    return {"reply": reply, "session_id": session_id}
