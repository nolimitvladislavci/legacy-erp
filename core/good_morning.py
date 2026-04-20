"""
core/good_morning.py — Good Morning Dashboard aggregator

Proaktivni briefing: sustav donosi informacije korisniku.
Nema vlastiti DB model — aggr. iz postojećih modela.

Prioriteti:
  0 (🔴 HITNO)  — ističe/dospijeva unutar 2 dana
  1 (🟡 ROK)    — unutar 7 dana
  2 (🔵 INFO)   — obavijest, zahtjev na čekanju
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def get_morning_items(company, user=None) -> list[dict]:
    """
    Skupi sve urgentne stavke za firmu.
    Vraća listu dict-a sortiranu po prioritetu (0=najhitnije).
    """
    now = timezone.now()
    today = now.date()
    items = []

    # ─── 1. e-Računi koji dospijevaju ─────────────────────────────────────
    try:
        from eracun.models import ERacun

        soon = today + timedelta(days=7)
        unpaid = ERacun.objects.filter(
            company=company,
            status__in=["sent", "draft", "overdue"],
            due_date__isnull=False,
            due_date__lte=soon,
            due_date__gte=today,
        ).order_by("due_date")[:5]

        for inv in unpaid:
            days_left = (inv.due_date - today).days
            priority = 0 if days_left <= 2 else 1
            emoji = "🔴" if priority == 0 else "🟡"
            label = "HITNO" if priority == 0 else "ROK"
            items.append(
                {
                    "priority": priority,
                    "emoji": emoji,
                    "label": label,
                    "title": f"Faktura {inv.invoice_number} dospijeva za {days_left} {'dan' if days_left == 1 else 'dana'}",
                    "subtitle": getattr(inv, "recipient_name", ""),
                    "actions": [
                        {"label": "Označi plaćeno", "url": f"/hr/eracun/{inv.pk}/", "icon": "fa-check"},
                        {"label": "Pogledaj", "url": f"/hr/eracun/{inv.pk}/", "icon": "fa-eye"},
                    ],
                    "dismiss_key": f"invoice_{inv.pk}",
                }
            )
    except Exception:
        pass

    # ─── 2. Arhiva — dokumenti zaštićeni do (deletion_protected_until) ────
    try:
        from documents.models import ArhivaEntry

        prot_soon = today + timedelta(days=7)
        expiring = ArhivaEntry.objects.filter(
            company=company,
            deletion_protected_until__isnull=False,
            deletion_protected_until__lte=prot_soon,
            deletion_protected_until__gte=today,
        ).order_by("deletion_protected_until")[:5]

        for entry in expiring:
            days_left = (entry.deletion_protected_until - today).days
            priority = 0 if days_left <= 2 else 1
            emoji = "🔴" if priority == 0 else "🟡"
            label = "HITNO" if priority == 0 else "ROK"
            items.append(
                {
                    "priority": priority,
                    "emoji": emoji,
                    "label": label,
                    "title": f"Zaštita dokumenta istječe za {days_left} {'dan' if days_left == 1 else 'dana'}: {entry.doc_number[:40]}",
                    "subtitle": entry.partner_name or "",
                    "actions": [
                        {"label": "Otvori arhivu", "url": "/hr/documents/arhiva/", "icon": "fa-folder-open"},
                    ],
                    "dismiss_key": f"arhiva_{entry.pk}",
                }
            )
    except Exception:
        pass

    # ─── 3. NO LIMIT termini za danas / sutra ─────────────────────────────
    try:
        from no_limit.models import NoLimitMeeting

        tomorrow = today + timedelta(days=1)
        meetings = NoLimitMeeting.objects.filter(
            status__in=["pending", "confirmed"],
            preferred_date__in=[today, tomorrow],
        ).order_by("preferred_date", "preferred_time")[:3]

        for m in meetings:
            when = "danas" if m.preferred_date == today else "sutra"
            items.append(
                {
                    "priority": 1,
                    "emoji": "📅",
                    "label": "TERMIN",
                    "title": f"Termin {when} u {m.preferred_time.strftime('%H:%M')}: {m.full_name}",
                    "subtitle": (m.topic or "")[:60],
                    "actions": [
                        {"label": "Detalji", "url": "/no-limit/admin/", "icon": "fa-calendar-check"},
                    ],
                    "dismiss_key": f"meeting_{m.pk}",
                }
            )
    except Exception:
        pass

    # ─── 4. Dokumenti čekaju AI obradu >3 dana ────────────────────────────
    try:
        from documents.models import ArhivaEntry

        stale_threshold = now - timedelta(days=3)
        stale = ArhivaEntry.objects.filter(
            company=company,
            ai_status__in=["pending", "none"],
            archived_at__lt=stale_threshold,
        ).count()

        if stale > 0:
            items.append(
                {
                    "priority": 2,
                    "emoji": "🔵",
                    "label": "INFO",
                    "title": f"{stale} {'dokument čeka' if stale == 1 else 'dokumenta čekaju'} AI obradu više od 3 dana",
                    "subtitle": "FenixScan nije obradio sve dokumente",
                    "actions": [
                        {"label": "Pregledaj", "url": "/hr/documents/arhiva/", "icon": "fa-robot"},
                    ],
                    "dismiss_key": "stale_docs",
                }
            )
    except Exception:
        pass

    # ─── 5. Neuspješne pretrage (slijepe točke) ───────────────────────────
    try:
        from core.search_audit_models import SearchAuditLog

        since_week = now - timedelta(days=7)
        zero_count = SearchAuditLog.objects.filter(
            company=company,
            result_count=0,
            searched_at__gte=since_week,
        ).count()

        if zero_count >= 5:
            items.append(
                {
                    "priority": 2,
                    "emoji": "🔵",
                    "label": "INFO",
                    "title": f"{zero_count} neuspješnih pretraga ovog tjedna",
                    "subtitle": "Moguće slijepe točke — nema odgovarajućih zapisa",
                    "actions": [
                        {"label": "Blind Spots", "url": "/hr/admin/blind-spots/", "icon": "fa-chart-bar"},
                    ],
                    "dismiss_key": "zero_results_week",
                }
            )
    except Exception:
        pass

    # Sortiraj: hitno prvo, onda rok, onda info
    items.sort(key=lambda x: x["priority"])
    return items


def get_morning_greeting(user=None) -> str:
    """Personalizirani pozdrav ovisno o dobu dana."""
    hour = timezone.now().hour
    name = f", {user.first_name}" if (user and getattr(user, "first_name", "")) else ""
    if hour < 12:
        return f"🌅 Dobro jutro{name}!"
    if hour < 18:
        return f"☀️ Dobar dan{name}!"
    return f"🌙 Dobra večer{name}!"
