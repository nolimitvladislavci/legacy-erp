import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError, models
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from .models import AIActionLog, AIModulePermission, PendingAIAction


def is_superadmin(user):
    return user.is_superuser or user.is_staff


# Grupe modula — preglednije od pojedinacnih
MODULE_GROUPS = {
    "Financije": [
        "invoicing",
        "finance",
        "konto",
        "eracun",
        "fiscal",
        "fiskalizacija",
        "payments",
        "payroll",
        "pdv_s",
        "aml",
        "calculator",
    ],
    "Prodaja & POS": ["pos", "webshop", "marketplace", "rental", "gastro_menu", "premium_booking"],
    "Skladiste": ["inventory", "delivery", "tracking", "traceability", "procurement"],
    "Dokumenti": ["documents", "virtual_office", "assessment"],
    "Operacije": ["worktime", "projects", "appointments", "work_orders", "maintenance", "interventions"],
    "Partneri & CRM": ["partners", "helpdesk", "outreach", "burza"],
    "AI & Import": ["ai_assistant", "smart_import", "synesis"],
    "Sustav": ["accounts", "companies", "notifications", "registration", "propter", "website"],
}

ALL_MODULES = []
for mods in MODULE_GROUPS.values():
    ALL_MODULES.extend(mods)


def sync_local_modules():
    for mod in ALL_MODULES:
        AIModulePermission.objects.get_or_create(
            company=None,
            module=mod,
        )


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    sync_local_modules()
    modules = AIModulePermission.objects.filter(company=None).order_by("module")
    actions = PendingAIAction.objects.filter(status="pending").order_by("-created_at")

    today_logs = AIActionLog.objects.filter(timestamp__date=timezone.now().date()).count()
    blocked_today = AIActionLog.objects.filter(timestamp__date=timezone.now().date(), outcome="blocked").count()

    # Build grouped structure
    grouped = {}
    modules_dict = {m.module: m for m in modules}
    for group_name, mod_list in MODULE_GROUPS.items():
        items = []
        for mod in mod_list:
            if mod in modules_dict:
                items.append(modules_dict[mod])
        if items:
            # Group stats
            all_read = all(m.can_read for m in items)
            all_write = all(m.can_write for m in items)
            all_create = all(m.can_create for m in items)
            all_modify = all(m.can_modify for m in items)
            any_active = any(m.can_read for m in items)
            grouped[group_name] = {
                "modules": items,
                "all_read": all_read,
                "all_write": all_write,
                "all_create": all_create,
                "all_modify": all_modify,
                "any_active": any_active,
                "count": len(items),
            }

    return render(
        request,
        "superadmin_ai/dashboard.html",
        {
            "grouped": grouped,
            "modules": modules,
            "actions": actions,
            "today_logs": today_logs,
            "blocked_today": blocked_today,
        },
    )


@login_required
@user_passes_test(is_superadmin)
@require_POST
def update_permission(request):
    try:
        data = json.loads(request.body)
        module_id = data.get("module_id")
        perm_type = data.get("permission_type")
        value = data.get("value", False)

        module = AIModulePermission.objects.get(id=module_id)

        if perm_type == "read":
            module.can_read = value
            if not value:
                module.can_write = False
                module.can_create = False
                module.can_modify = False
        elif perm_type == "write":
            module.can_write = value
            if value:
                module.can_read = True
        elif perm_type == "create":
            module.can_create = value
            if value:
                module.can_read = True
        elif perm_type == "modify":
            module.can_modify = value
            if value:
                module.can_read = True
        else:
            return JsonResponse({"status": "error", "message": "Nepoznat tip"}, status=400)

        module.updated_by = request.user
        module.save()
        return JsonResponse(
            {
                "status": "success",
                "message": "%s: %s %s" % (module.module, perm_type, "ON" if value else "OFF"),
                "permissions": {
                    "can_read": module.can_read,
                    "can_write": module.can_write,
                    "can_create": module.can_create,
                    "can_modify": module.can_modify,
                },
            }
        )
    except AIModulePermission.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Modul ne postoji"}, status=404)
    except ObjectDoesNotExist as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@user_passes_test(is_superadmin)
@require_POST
def bulk_permission(request):
    """Bulk toggle za cijelu grupu modula — jedan klik."""
    try:
        data = json.loads(request.body)
        group_name = data.get("group", "")
        perm_type = data.get("permission_type", "read")
        value = data.get("value", False)

        mod_list = MODULE_GROUPS.get(group_name, [])
        if not mod_list:
            return JsonResponse({"error": "Grupa ne postoji"}, status=400)

        updated = 0
        for mod in AIModulePermission.objects.filter(company=None, module__in=mod_list):
            if perm_type == "read":
                mod.can_read = value
                if not value:
                    mod.can_write = False
                    mod.can_create = False
                    mod.can_modify = False
            elif perm_type == "write":
                mod.can_write = value
                if value:
                    mod.can_read = True
            elif perm_type == "create":
                mod.can_create = value
                if value:
                    mod.can_read = True
            elif perm_type == "modify":
                mod.can_modify = value
                if value:
                    mod.can_read = True
            elif perm_type == "all":
                mod.can_read = value
                mod.can_write = value
                mod.can_create = value
                mod.can_modify = value
            mod.updated_by = request.user
            mod.save()
            updated += 1

        return JsonResponse(
            {
                "ok": True,
                "message": "%s: %d modula %s" % (group_name, updated, "aktivirano" if value else "deaktivirano"),
                "updated": updated,
            }
        )
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@user_passes_test(is_superadmin)
@require_POST
def bulk_all(request):
    """Uključi/isključi SVE module odjednom."""
    try:
        data = json.loads(request.body)
        value = data.get("value", False)
        perm = data.get("permission_type", "all")

        updated = 0
        for mod in AIModulePermission.objects.filter(company=None):
            if perm == "all":
                mod.can_read = value
                mod.can_write = value
                mod.can_create = value
                mod.can_modify = value
            elif perm == "read":
                mod.can_read = value
                if not value:
                    mod.can_write = False
                    mod.can_create = False
                    mod.can_modify = False
            mod.updated_by = request.user
            mod.save()
            updated += 1

        return JsonResponse(
            {
                "ok": True,
                "message": "Svi moduli (%d) %s" % (updated, "aktivirani" if value else "deaktivirani"),
            }
        )
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({"error": str(e)}, status=500)


# ══════════════════════════════════════════════════════════
# AI AGENT GATEWAY — strukturirani API za AI agente
# ══════════════════════════════════════════════════════════

import os

AI_AGENT_TOKEN = os.environ.get("DEV_API_TOKEN", "")


def _check_agent_auth(request):
    if not AI_AGENT_TOKEN:
        return JsonResponse({"error": "AI_AGENT_TOKEN not configured"}, status=503)
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if token != AI_AGENT_TOKEN:
        return JsonResponse({"error": "unauthorized"}, status=403)
    return None


@require_POST
def agent_gateway(request):
    """
    AI Agent Gateway — strukturirani pristup s permission proverom.
    POST /api/ai-agent/
    {
        "action": "read" | "write" | "exec" | "query",
        "module": "pos" | "inventory" | ...,
        "payload": { ... }
    }
    """
    err = _check_agent_auth(request)
    if err:
        return err

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    action = data.get("action", "")
    module = data.get("module", "general")
    payload = data.get("payload", {})
    company_id = data.get("company_id")

    # Resolve company
    company = None
    if company_id:
        from companies.models import Company

        company = Company.objects.filter(pk=company_id).first()

    # Check permission
    level = AIModulePermission.get_level(company, module)
    ip = request.META.get("HTTP_X_REAL_IP", request.META.get("REMOTE_ADDR", ""))

    # Map action to required level
    required = {
        "read": AIModulePermission.ACCESS_READ_ONLY,
        "query": AIModulePermission.ACCESS_READ_ONLY,
        "write": AIModulePermission.ACCESS_ASSISTED,
        "exec": AIModulePermission.ACCESS_AUTONOMOUS,
        "create": AIModulePermission.ACCESS_ASSISTED,
        "modify": AIModulePermission.ACCESS_ASSISTED,
    }.get(action, AIModulePermission.ACCESS_AUTONOMOUS)

    # COUNCIL (4) može sve — prolazi required check jer je > AUTONOMOUS (3)
    if level < required and level != AIModulePermission.ACCESS_COUNCIL:
        # Log blocked
        AIActionLog.objects.create(
            company=company,
            module=module,
            action_type=action,
            access_level=level,
            outcome="blocked",
            ip_address=ip,
            details={"reason": "insufficient_level", "required": required, "actual": level},
        )
        level_names = {0: "DISABLED", 1: "READ_ONLY", 2: "ASSISTED", 3: "AUTONOMOUS", 4: "COUNCIL"}
        return JsonResponse(
            {
                "error": "permission_denied",
                "module": module,
                "current_level": level_names.get(level, str(level)),
                "required_level": level_names.get(required, str(required)),
                "message": "Modul %s nema dovoljnu razinu pristupa za akciju %s" % (module, action),
            },
            status=403,
        )

    # COUNCIL level — zahtijeva 2/3 AI glasova
    if level == AIModulePermission.ACCESS_COUNCIL and action in ("write", "create", "modify", "exec"):
        from superadmin_ai.models import AICouncilVote

        # Nađi ili kreiraj pending akciju
        pending = (
            PendingAIAction.objects.filter(
                company=company,
                module=module,
                action_type=action,
                status="pending",
            )
            .order_by("-created_at")
            .first()
        )

        if not pending:
            pending = PendingAIAction.objects.create(
                company=company,
                module=module,
                action_type=action,
                description=payload.get("description", "Council akcija: %s" % action),
                payload=payload,
                status="pending",
            )

        # Glas od ovog agenta
        agent_name = data.get("agent", "system")
        AICouncilVote.objects.get_or_create(
            pending_action=pending,
            agent=agent_name,
            defaults={
                "vote": data.get("vote", "approve"),
                "reasoning": data.get("reasoning", ""),
                "confidence": data.get("confidence", 75),
            },
        )

        # Provjeri odluku vijeća
        decision = AICouncilVote.get_decision(pending)
        vote_count = pending.council_votes.count()

        if decision == "approved":
            pending.status = "approved"
            pending.reviewed_at = timezone.now()
            pending.save(update_fields=["status", "reviewed_at"])
            result = _execute_agent_action(action, module, payload, company, ip)
            AIActionLog.objects.create(
                company=company,
                module=module,
                action_type=action,
                access_level=level,
                outcome="executed" if result.get("ok") else "failed",
                ip_address=ip,
                details={"council": True, "votes": vote_count, "result_ok": result.get("ok", False)},
            )
            return JsonResponse({"status": "executed", "data": result, "council_votes": vote_count})

        elif decision == "rejected":
            pending.status = "rejected"
            pending.save(update_fields=["status"])
            AIActionLog.objects.create(
                company=company,
                module=module,
                action_type=action,
                access_level=level,
                outcome="blocked",
                ip_address=ip,
                details={"council": True, "votes": vote_count, "decision": "rejected"},
            )
            return JsonResponse(
                {"status": "rejected", "message": "AI vijeće odbilo akciju", "votes": vote_count}, status=403
            )

        else:
            AIActionLog.objects.create(
                company=company,
                module=module,
                action_type=action,
                access_level=level,
                outcome="queued",
                ip_address=ip,
                details={"council": True, "votes": vote_count, "pending_id": str(pending.id)},
            )
            return JsonResponse(
                {
                    "status": "council_pending",
                    "pending_id": str(pending.id),
                    "votes_so_far": vote_count,
                    "votes_needed": max(0, 2 - pending.council_votes.filter(vote="approve").count()),
                    "message": "AI vijeće: %d/3 glasova." % vote_count,
                }
            )

    # ASSISTED level — queue for approval
    if level == AIModulePermission.ACCESS_ASSISTED and action in ("write", "create", "modify", "exec"):
        pending = PendingAIAction.objects.create(
            company=company,
            module=module,
            action_type=action,
            description=payload.get("description", "AI agent %s" % action),
            proposed_code=payload.get("code", ""),
            payload=payload,
            status="pending",
        )
        AIActionLog.objects.create(
            company=company,
            module=module,
            action_type=action,
            access_level=level,
            outcome="queued",
            ip_address=ip,
            details={"pending_id": str(pending.id)},
        )
        return JsonResponse(
            {
                "status": "queued",
                "pending_id": str(pending.id),
                "message": "Akcija stavljena na cekanje — treba odobrenje superadmina",
            }
        )

    # AUTONOMOUS or READ — execute
    result = _execute_agent_action(action, module, payload, company, ip)

    # Log execution
    AIActionLog.objects.create(
        company=company,
        module=module,
        action_type=action,
        access_level=level,
        outcome="executed" if result.get("ok") else "failed",
        ip_address=ip,
        details={"payload_keys": list(payload.keys()), "result_ok": result.get("ok", False)},
    )

    # AI Self-Report — agent objašnjava što je napravio
    if result.get("ok") and level >= AIModulePermission.ACCESS_AUTONOMOUS:
        try:
            import os

            import anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                client = anthropic.Anthropic(api_key=api_key)
                report = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=150,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "Napiši kratko izvješće (1-2 rečenice, HR) što si upravo napravio:\n"
                                "Modul: %s, Akcija: %s\n"
                                "Payload ključevi: %s\n"
                                "Rezultat: uspješno"
                            )
                            % (module, action, list(payload.keys())),
                        }
                    ],
                )
                result["ai_report"] = report.content[0].text
        except (IntegrityError, DatabaseError):
            pass

    return JsonResponse(result)


def _execute_agent_action(action, module, payload, company, ip):
    """Execute AI agent action based on type."""
    import subprocess

    if action == "read":
        path = payload.get("path", "")
        if not path or ".." in path:
            return {"ok": False, "error": "invalid path"}
        full = os.path.join("/var/www/fina-connect", path)
        try:
            with open(full) as f:
                return {"ok": True, "content": f.read()[:100000], "path": path}
        except FileNotFoundError:
            return {"ok": False, "error": "File not found"}
        except PermissionError:
            return {"ok": False, "error": "Permission denied"}
        except (FileNotFoundError, PermissionError, IOError) as e:
            import logging

            logging.getLogger("superadmin_ai").error(f"agent read error: {e}", exc_info=True)
            return {"ok": False, "error": "Read failed — check server logs"}

    elif action == "query":
        # Django ORM query — read-only
        model_name = payload.get("model", "")
        filters = payload.get("filters", {})
        limit = min(payload.get("limit", 50), 200)
        try:
            from django.apps import apps as django_apps

            app_label, model = model_name.split(".") if "." in model_name else (module, model_name)
            Model = django_apps.get_model(app_label, model)
            qs = Model.objects.filter(**filters)[:limit]
            data = list(qs.values())
            # Serialize special types
            import datetime
            import decimal
            import uuid

            for row in data:
                for k, v in row.items():
                    if isinstance(v, (decimal.Decimal,)):
                        row[k] = float(v)
                    elif isinstance(v, (datetime.datetime, datetime.date)):
                        row[k] = str(v)
                    elif isinstance(v, uuid.UUID):
                        row[k] = str(v)
            return {"ok": True, "count": len(data), "data": data}
        except (ValueError, TypeError) as e:
            import logging

            logging.getLogger("superadmin_ai").error(f"agent query error: {e}", exc_info=True)
            return {"ok": False, "error": "Query failed — check server logs"}

    elif action == "exec":
        cmd = payload.get("cmd", "")
        if not cmd:
            return {"ok": False, "error": "no cmd"}
        if not request.user.is_superuser:
            return {"ok": False, "error": "Nedovoljne ovlasti za exec akciju"}
        # Security: whitelist dozvoljenih komandi
        ALLOWED_PREFIXES = [
            "python3 manage.py",
            "python manage.py",
            "cat ",
            "ls ",
            "grep ",
            "wc ",
            "head ",
            "tail ",
            "pg_dump",
            "redis-cli ping",
            "systemctl status",
            "df -h",
            "free -m",
            "uptime",
        ]
        cmd_strip = cmd.strip()
        if not any(cmd_strip.startswith(p) for p in ALLOWED_PREFIXES):
            return {"ok": False, "error": f"command not allowed. Permitted: {', '.join(ALLOWED_PREFIXES)}"}
        # Blokiraj opasne znakove (pipe injection, command chaining)
        if any(c in cmd_strip for c in [";", "&&", "||", "`", "$("]):
            return {"ok": False, "error": "command contains blocked characters (;, &&, ||, `, $()"}
        try:
            import shlex

            result = subprocess.run(
                shlex.split(cmd_strip), capture_output=True, text=True, timeout=30, cwd="/var/www/fina-connect"
            )
            return {
                "ok": True,
                "stdout": result.stdout[:50000],
                "stderr": result.stderr[:5000],
                "code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout"}

    elif action in ("write", "create", "modify"):
        path = payload.get("path", "")
        content = payload.get("content", "")
        if not path or ".." in path:
            return {"ok": False, "error": "invalid path"}
        full = os.path.join("/var/www/fina-connect", path)
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(content)
            return {"ok": True, "path": path, "bytes": len(content)}
        except (FileNotFoundError, PermissionError, IOError) as e:
            import logging

            logging.getLogger("superadmin_ai").error(f"agent write error: {e}", exc_info=True)
            return {"ok": False, "error": "Write failed — check server logs"}

    return {"ok": False, "error": "unknown action"}


# ══════════════════════════════════════════════════════════
# EXISTING VIEWS (preserved)
# ══════════════════════════════════════════════════════════


@login_required
@user_passes_test(is_superadmin)
@require_POST
def submit_request(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    req_type = data.get("type", "upit")
    module = data.get("module", "general")
    description = data.get("description", "").strip()
    if not description:
        return JsonResponse({"error": "Opis je obavezan"}, status=400)
    from core.company_utils import get_user_company

    company = get_user_company(request)
    action = PendingAIAction.objects.create(
        company=company,
        module=module,
        action_type="user_%s" % req_type,
        description=description,
        payload={"submitted_by": request.user.username, "type": req_type},
        status="pending",
    )
    return JsonResponse({"ok": True, "id": str(action.id), "message": "Zahtjev poslan (#%s)" % str(action.id)[:8]})


@login_required
@require_POST
def tim_chat_send(request):
    """Tim chat poruka — svi korisnici, ne samo superadmin."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    description = data.get("description", "").strip()
    if not description:
        return JsonResponse({"error": "Poruka je prazna"}, status=400)

    module = data.get("module", "tim_chat")
    priority = data.get("priority", 1)

    from core.company_utils import get_user_company

    company = get_user_company(request)

    action = PendingAIAction.objects.create(
        company=company,
        module=module,
        action_type="tim_chat_msg",
        description=description,
        payload={
            "submitted_by": request.user.username,
            "user_id": request.user.pk,
            "full_name": request.user.get_full_name() or request.user.username,
            "company": company.name if company else "",
            "priority": priority,
        },
        status="pending",
    )
    return JsonResponse(
        {
            "ok": True,
            "id": str(action.id),
            "message": "Poruka poslana! Tim je obavijesten.",
        }
    )


@login_required
@user_passes_test(is_superadmin)
@require_POST
def resolve_action(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    action_id = data.get("action_id")
    decision = data.get("decision", "REJECTED")
    try:
        action = PendingAIAction.objects.get(pk=action_id)
    except PendingAIAction.DoesNotExist:
        return JsonResponse({"error": "Akcija ne postoji"}, status=404)
    action.status = "approved" if decision == "APPROVED" else "rejected"
    action.reviewed_by = request.user
    action.reviewed_at = timezone.now()
    action.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    AIActionLog.objects.create(
        company=action.company,
        module=action.module,
        action_type="resolve_%s" % action.action_type,
        access_level=2,
        outcome="allowed" if decision == "APPROVED" else "blocked",
        user=request.user,
        details={"action_id": str(action.id), "decision": decision},
    )
    return JsonResponse({"ok": True, "message": "Akcija %s" % ("odobrena" if decision == "APPROVED" else "odbijena")})


@login_required
@user_passes_test(is_superadmin)
def action_logs(request):
    logs = AIActionLog.objects.select_related("company", "user").order_by("-timestamp")[:200]
    module_filter = request.GET.get("module")
    outcome_filter = request.GET.get("outcome")
    if module_filter:
        logs = logs.filter(module=module_filter)
    if outcome_filter:
        logs = logs.filter(outcome=outcome_filter)
    return render(
        request,
        "superadmin_ai/logs.html",
        {
            "logs": logs,
            "module_choices": [(m.module, m.module) for m in AIModulePermission.objects.filter(company=None)],
            "outcome_choices": AIActionLog.OUTCOME_CHOICES,
            "module_filter": module_filter or "",
            "outcome_filter": outcome_filter or "",
        },
    )


@login_required
@user_passes_test(is_superadmin)
def live_metrics(request):
    """Live metrike za dashboard widget — AJAX refresh svakih 30s."""
    from superadmin_ai.models import AICouncilVote

    today = timezone.now().date()

    # Recent actions (zadnjih 10)
    recent = AIActionLog.objects.select_related("company").order_by("-timestamp")[:10]
    recent_list = []
    for a in recent:
        recent_list.append(
            {
                "status": a.outcome or "unknown",
                "module": a.module or "general",
                "description": (a.details or {}).get("description", a.action_type or "")[:60],
                "time": a.timestamp.strftime("%H:%M") if a.timestamp else "",
                "id": str(a.id),
            }
        )

    # Pending actions (cekaju odobrenje)
    pending = PendingAIAction.objects.filter(status="pending").select_related("company").order_by("-created_at")[:5]
    pending_list = []
    for a in pending:
        pending_list.append(
            {
                "id": str(a.id),
                "module": a.module or "general",
                "description": a.description[:60] if a.description else "",
                "time": a.created_at.strftime("%H:%M") if a.created_at else "",
                "company": a.company.name if a.company else "N/A",
            }
        )

    total_today = AIActionLog.objects.filter(timestamp__date=today).count()

    return JsonResponse(
        {
            "autonomous_today": AIActionLog.objects.filter(
                timestamp__date=today, access_level__gte=3, outcome="executed"
            ).count(),
            "pending_count": PendingAIAction.objects.filter(status="pending").count(),
            "blocked_today": AIActionLog.objects.filter(timestamp__date=today, outcome="blocked").count(),
            "council_votes": AICouncilVote.objects.filter(voted_at__date=today).count(),
            "total_today": total_today,
            "recent_actions": recent_list,
            "pending_actions": pending_list,
        }
    )


# ── SUBSCRIPTION COCKPIT — ARR/MRR ───────────────────────────────────────────


@login_required
@user_passes_test(is_superadmin)
def subscription_cockpit(request):
    """ARR/MRR cockpit — monetizacijski pregled za superadmina."""
    from collections import Counter, defaultdict
    from datetime import timedelta
    from decimal import Decimal

    from companies.models import Company
    from registration.models import CompanySubscription

    today = timezone.now().date()

    # Active subscriptions
    active_subs = CompanySubscription.objects.filter(is_active=True).select_related("company", "pricing_plan")

    # MRR calculation
    mrr = Decimal("0.00")
    plan_revenue = defaultdict(Decimal)
    billing_breakdown = Counter()

    for sub in active_subs:
        if sub.billing_cycle == "yearly" and sub.monthly_fee:
            monthly = sub.monthly_fee / 12
        else:
            monthly = sub.monthly_fee or Decimal("0.00")
        mrr += monthly
        plan_name = sub.pricing_plan.name if sub.pricing_plan else sub.plan
        plan_revenue[plan_name] += monthly
        billing_breakdown[sub.billing_cycle] += 1

    arr = mrr * 12

    # Trial metrics
    trials = active_subs.filter(trial_ends__isnull=False, trial_ends__gte=today)
    trial_expiring_7d = trials.filter(trial_ends__lte=today + timedelta(days=7))

    # Churn risk — subscriptions with cancel_at_period_end=True
    churn_risk = active_subs.filter(cancel_at_period_end=True)

    # Plan distribution
    plan_dist = sorted(plan_revenue.items(), key=lambda x: x[1], reverse=True)

    # Companies without subscription
    total_companies = Company.objects.count()
    companies_with_sub = active_subs.values("company").distinct().count()
    companies_no_sub = total_companies - companies_with_sub

    # Recent subscriptions (last 30 days)
    recent = (
        CompanySubscription.objects.filter(valid_from__gte=today - timedelta(days=30))
        .select_related("company", "pricing_plan")
        .order_by("-valid_from")[:20]
    )

    # Monthly trend (last 6 months)
    months = []
    for i in range(5, -1, -1):
        m_start = today.replace(day=1) - timedelta(days=30 * i)
        m_start = m_start.replace(day=1)
        month_subs = CompanySubscription.objects.filter(
            is_active=True,
            valid_from__lte=m_start,
        ).filter(models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=m_start))
        m_mrr = sum(
            (s.monthly_fee / 12 if s.billing_cycle == "yearly" else s.monthly_fee) or Decimal("0") for s in month_subs
        )
        months.append(
            {
                "label": m_start.strftime("%b %Y"),
                "mrr": float(m_mrr),
                "count": month_subs.count(),
            }
        )

    ctx = {
        "mrr": mrr,
        "arr": arr,
        "active_count": active_subs.count(),
        "plan_dist": plan_dist,
        "billing_breakdown": dict(billing_breakdown),
        "trials": trials,
        "trial_expiring_7d": trial_expiring_7d,
        "churn_risk": churn_risk,
        "total_companies": total_companies,
        "companies_with_sub": companies_with_sub,
        "companies_no_sub": companies_no_sub,
        "recent": recent,
        "months_json": json.dumps(months),
    }
    return render(request, "superadmin_ai/subscription_cockpit.html", ctx)


# ─────────────────────────────────────────────────────────────
#  AI CHAT SOBA  –  /superadmin/ai/chat/
# ─────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_superadmin)
def ai_chat(request):
    """Prikaži chat sučelje."""
    return render(request, "superadmin_ai/ai_chat.html", {
        "providers": [
            {"id": "haiku",   "label": "Claude Haiku",   "icon": "fa-robot",  "color": "#c9a84c"},
            {"id": "gemini",  "label": "Gemini Flash",   "icon": "fa-star",   "color": "#4285f4"},
            {"id": "deepseek","label": "DeepSeek Chat",  "icon": "fa-brain",  "color": "#00b4d8"},
        ]
    })


@csrf_exempt
@login_required
@user_passes_test(is_superadmin)
@require_POST
def ai_chat_send(request):
    """
    HTMX endpoint — primi poruku, pozovi AI, vrati HTML fragment.
    Body: { provider, message, history: [{role,content},...] }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    provider = data.get("provider", "haiku").strip()
    user_msg = data.get("message", "").strip()
    history  = data.get("history", [])   # [{role,content}, ...]

    if not user_msg:
        return JsonResponse({"error": "Prazna poruka"}, status=400)

    messages = history + [{"role": "user", "content": user_msg}]
    reply = _call_ai(provider, messages)
    return JsonResponse({"reply": reply, "provider": provider})


def _call_ai(provider, messages):
    """Pozovi odabrani AI provider i vrati odgovor kao string."""
    from django.conf import settings

    # ── Claude Haiku ──────────────────────────────────────────
    if provider == "haiku":
        import urllib.request as ur, json as _j
        key = getattr(settings, "ANTHROPIC_API_KEY", "")
        payload = _j.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2048,
            "system": (
                "Ti si Fenix AI asistent za superadmina LIMIT Connect platforme. "
                "Odgovaraj kratko i precizno, na jeziku korisnika (HR/EN/DE)."
            ),
            "messages": messages,
        }).encode()
        req = ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        try:
            with ur.urlopen(req, timeout=60) as r:
                d = _j.loads(r.read())
                return d["content"][0]["text"]
        except Exception as e:
            return f"[Haiku greška: {e}]"

    # ── Gemini Flash ──────────────────────────────────────────
    elif provider == "gemini":
        import urllib.request as ur, json as _j
        key = getattr(settings, "GEMINI_API_KEY", "")
        # Konvertiraj u Gemini format
        parts = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            parts.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = _j.dumps({"contents": parts}).encode()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        req = ur.Request(url, data=payload,
                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with ur.urlopen(req, timeout=60) as r:
                d = _j.loads(r.read())
                return d["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"[Gemini greška: {e}]"

    # ── DeepSeek Chat ─────────────────────────────────────────
    elif provider == "deepseek":
        import urllib.request as ur, json as _j
        key = getattr(settings, "DEEPSEEK_API_KEY", "")
        sys_msg = {"role": "system", "content": (
            "Ti si Fenix AI asistent za superadmina LIMIT Connect platforme. "
            "Odgovaraj kratko i precizno, na jeziku korisnika (HR/EN/DE)."
        )}
        payload = _j.dumps({
            "model": "deepseek-chat",
            "messages": [sys_msg] + messages,
            "max_tokens": 2048,
            "temperature": 0.3,
        }).encode()
        req = ur.Request(
            "https://api.deepseek.com/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"},
            method="POST"
        )
        try:
            with ur.urlopen(req, timeout=90) as r:
                d = _j.loads(r.read())
                return d["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[DeepSeek greška: {e}]"

    return "[Nepoznat provider]"
