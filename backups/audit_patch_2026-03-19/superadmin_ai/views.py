import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import AIActionLog, AIModulePermission, PendingAIAction


def is_superadmin(user):
    return user.is_superuser or user.is_staff

# Grupe modula — preglednije od pojedinacnih
MODULE_GROUPS = {
    'Financije': ['invoicing', 'finance', 'konto', 'eracun', 'fiscal', 'fiskalizacija', 'payments', 'payroll', 'pdv_s', 'aml', 'calculator'],
    'Prodaja & POS': ['pos', 'webshop', 'marketplace', 'rental', 'gastro_menu', 'premium_booking'],
    'Skladiste': ['inventory', 'delivery', 'tracking', 'traceability', 'procurement'],
    'Dokumenti': ['documents', 'virtual_office', 'assessment'],
    'Operacije': ['worktime', 'projects', 'appointments', 'work_orders', 'maintenance', 'interventions'],
    'Partneri & CRM': ['partners', 'helpdesk', 'outreach', 'burza'],
    'AI & Import': ['ai_assistant', 'smart_import', 'synesis'],
    'Sustav': ['accounts', 'companies', 'notifications', 'registration', 'propter', 'website'],
}

ALL_MODULES = []
for mods in MODULE_GROUPS.values():
    ALL_MODULES.extend(mods)


def sync_local_modules():
    for mod in ALL_MODULES:
        AIModulePermission.objects.get_or_create(
            company=None, module=mod,
        )


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    sync_local_modules()
    modules = AIModulePermission.objects.filter(company=None).order_by('module')
    actions = PendingAIAction.objects.filter(status='pending').order_by('-created_at')

    today_logs = AIActionLog.objects.filter(timestamp__date=timezone.now().date()).count()
    blocked_today = AIActionLog.objects.filter(timestamp__date=timezone.now().date(), outcome='blocked').count()

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
                'modules': items,
                'all_read': all_read,
                'all_write': all_write,
                'all_create': all_create,
                'all_modify': all_modify,
                'any_active': any_active,
                'count': len(items),
            }

    return render(request, 'superadmin_ai/dashboard.html', {
        'grouped': grouped,
        'modules': modules,
        'actions': actions,
        'today_logs': today_logs,
        'blocked_today': blocked_today,
    })


@login_required
@user_passes_test(is_superadmin)
@require_POST
def update_permission(request):
    try:
        data = json.loads(request.body)
        module_id = data.get('module_id')
        perm_type = data.get('permission_type')
        value = data.get('value', False)

        module = AIModulePermission.objects.get(id=module_id)

        if perm_type == 'read':
            module.can_read = value
            if not value:
                module.can_write = False
                module.can_create = False
                module.can_modify = False
        elif perm_type == 'write':
            module.can_write = value
            if value: module.can_read = True
        elif perm_type == 'create':
            module.can_create = value
            if value: module.can_read = True
        elif perm_type == 'modify':
            module.can_modify = value
            if value: module.can_read = True
        else:
            return JsonResponse({'status': 'error', 'message': 'Nepoznat tip'}, status=400)

        module.updated_by = request.user
        module.save()
        return JsonResponse({
            'status': 'success',
            'message': '%s: %s %s' % (module.module, perm_type, 'ON' if value else 'OFF'),
            'permissions': {
                'can_read': module.can_read, 'can_write': module.can_write,
                'can_create': module.can_create, 'can_modify': module.can_modify,
            }
        })
    except AIModulePermission.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Modul ne postoji'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_superadmin)
@require_POST
def bulk_permission(request):
    """Bulk toggle za cijelu grupu modula — jedan klik."""
    try:
        data = json.loads(request.body)
        group_name = data.get('group', '')
        perm_type = data.get('permission_type', 'read')
        value = data.get('value', False)

        mod_list = MODULE_GROUPS.get(group_name, [])
        if not mod_list:
            return JsonResponse({'error': 'Grupa ne postoji'}, status=400)

        updated = 0
        for mod in AIModulePermission.objects.filter(company=None, module__in=mod_list):
            if perm_type == 'read':
                mod.can_read = value
                if not value:
                    mod.can_write = False
                    mod.can_create = False
                    mod.can_modify = False
            elif perm_type == 'write':
                mod.can_write = value
                if value: mod.can_read = True
            elif perm_type == 'create':
                mod.can_create = value
                if value: mod.can_read = True
            elif perm_type == 'modify':
                mod.can_modify = value
                if value: mod.can_read = True
            elif perm_type == 'all':
                mod.can_read = value
                mod.can_write = value
                mod.can_create = value
                mod.can_modify = value
            mod.updated_by = request.user
            mod.save()
            updated += 1

        return JsonResponse({
            'ok': True,
            'message': '%s: %d modula %s' % (group_name, updated, 'aktivirano' if value else 'deaktivirano'),
            'updated': updated,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(is_superadmin)
@require_POST
def bulk_all(request):
    """Uključi/isključi SVE module odjednom."""
    try:
        data = json.loads(request.body)
        value = data.get('value', False)
        perm = data.get('permission_type', 'all')

        updated = 0
        for mod in AIModulePermission.objects.filter(company=None):
            if perm == 'all':
                mod.can_read = value
                mod.can_write = value
                mod.can_create = value
                mod.can_modify = value
            elif perm == 'read':
                mod.can_read = value
                if not value:
                    mod.can_write = False
                    mod.can_create = False
                    mod.can_modify = False
            mod.updated_by = request.user
            mod.save()
            updated += 1

        return JsonResponse({
            'ok': True,
            'message': 'Svi moduli (%d) %s' % (updated, 'aktivirani' if value else 'deaktivirani'),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════════
# AI AGENT GATEWAY — strukturirani API za AI agente
# ══════════════════════════════════════════════════════════

import os

AI_AGENT_TOKEN = os.environ.get('DEV_API_TOKEN', '')

def _check_agent_auth(request):
    if not AI_AGENT_TOKEN:
        return JsonResponse({'error': 'AI_AGENT_TOKEN not configured'}, status=503)
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else ''
    if token != AI_AGENT_TOKEN:
        return JsonResponse({'error': 'unauthorized'}, status=403)
    return None


@csrf_exempt
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
    if err: return err

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    action = data.get('action', '')
    module = data.get('module', 'general')
    payload = data.get('payload', {})
    company_id = data.get('company_id')

    # Resolve company
    company = None
    if company_id:
        from companies.models import Company
        company = Company.objects.filter(pk=company_id).first()

    # Check permission
    level = AIModulePermission.get_level(company, module)
    ip = request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR', ''))

    # Map action to required level
    required = {
        'read': AIModulePermission.ACCESS_READ_ONLY,
        'query': AIModulePermission.ACCESS_READ_ONLY,
        'write': AIModulePermission.ACCESS_ASSISTED,
        'exec': AIModulePermission.ACCESS_AUTONOMOUS,
        'create': AIModulePermission.ACCESS_ASSISTED,
        'modify': AIModulePermission.ACCESS_ASSISTED,
    }.get(action, AIModulePermission.ACCESS_AUTONOMOUS)

    if level < required:
        # Log blocked
        AIActionLog.objects.create(
            company=company, module=module, action_type=action,
            access_level=level, outcome='blocked', ip_address=ip,
            details={'reason': 'insufficient_level', 'required': required, 'actual': level},
        )
        level_names = {0: 'DISABLED', 1: 'READ_ONLY', 2: 'ASSISTED', 3: 'AUTONOMOUS'}
        return JsonResponse({
            'error': 'permission_denied',
            'module': module,
            'current_level': level_names.get(level, str(level)),
            'required_level': level_names.get(required, str(required)),
            'message': 'Modul %s nema dovoljnu razinu pristupa za akciju %s' % (module, action),
        }, status=403)

    # ASSISTED level — queue for approval
    if level == AIModulePermission.ACCESS_ASSISTED and action in ('write', 'create', 'modify', 'exec'):
        pending = PendingAIAction.objects.create(
            company=company, module=module, action_type=action,
            description=payload.get('description', 'AI agent %s' % action),
            proposed_code=payload.get('code', ''),
            payload=payload,
            status='pending',
        )
        AIActionLog.objects.create(
            company=company, module=module, action_type=action,
            access_level=level, outcome='queued', ip_address=ip,
            details={'pending_id': str(pending.id)},
        )
        return JsonResponse({
            'status': 'queued',
            'pending_id': str(pending.id),
            'message': 'Akcija stavljena na cekanje — treba odobrenje superadmina',
        })

    # AUTONOMOUS or READ — execute
    result = _execute_agent_action(action, module, payload, company, ip)

    # Log execution
    AIActionLog.objects.create(
        company=company, module=module, action_type=action,
        access_level=level,
        outcome='executed' if result.get('ok') else 'failed',
        ip_address=ip,
        details={'payload_keys': list(payload.keys()), 'result_ok': result.get('ok', False)},
    )

    return JsonResponse(result)


def _execute_agent_action(action, module, payload, company, ip):
    """Execute AI agent action based on type."""
    import subprocess

    if action == 'read':
        path = payload.get('path', '')
        if not path or '..' in path:
            return {'ok': False, 'error': 'invalid path'}
        full = os.path.join('/var/www/fina-connect', path)
        try:
            with open(full) as f:
                return {'ok': True, 'content': f.read()[:100000], 'path': path}
        except FileNotFoundError:
            return {'ok': False, 'error': 'File not found'}
        except PermissionError:
            return {'ok': False, 'error': 'Permission denied'}
        except Exception as e:
            import logging
            logging.getLogger('superadmin_ai').error(f'agent read error: {e}', exc_info=True)
            return {'ok': False, 'error': 'Read failed — check server logs'}

    elif action == 'query':
        # Django ORM query — read-only
        model_name = payload.get('model', '')
        filters = payload.get('filters', {})
        limit = min(payload.get('limit', 50), 200)
        try:
            from django.apps import apps as django_apps
            app_label, model = model_name.split('.') if '.' in model_name else (module, model_name)
            Model = django_apps.get_model(app_label, model)
            qs = Model.objects.filter(**filters)[:limit]
            data = list(qs.values())
            # Serialize special types
            import datetime
            import decimal
            import uuid
            for row in data:
                for k, v in row.items():
                    if isinstance(v, (decimal.Decimal,)): row[k] = float(v)
                    elif isinstance(v, (datetime.datetime, datetime.date)): row[k] = str(v)
                    elif isinstance(v, uuid.UUID): row[k] = str(v)
            return {'ok': True, 'count': len(data), 'data': data}
        except Exception as e:
            import logging
            logging.getLogger('superadmin_ai').error(f'agent query error: {e}', exc_info=True)
            return {'ok': False, 'error': 'Query failed — check server logs'}

    elif action == 'exec':
        cmd = payload.get('cmd', '')
        if not cmd:
            return {'ok': False, 'error': 'no cmd'}
        # Security: whitelist dozvoljenih komandi
        ALLOWED_PREFIXES = [
            'python3 manage.py', 'python manage.py',
            'cat ', 'ls ', 'grep ', 'wc ', 'head ', 'tail ',
            'pg_dump', 'redis-cli ping', 'systemctl status',
            'df -h', 'free -m', 'uptime',
        ]
        cmd_strip = cmd.strip()
        if not any(cmd_strip.startswith(p) for p in ALLOWED_PREFIXES):
            return {'ok': False, 'error': f'command not allowed. Permitted: {", ".join(ALLOWED_PREFIXES)}'}
        # Blokiraj opasne znakove (pipe injection, command chaining)
        if any(c in cmd_strip for c in [';', '&&', '||', '`', '$(']):
            return {'ok': False, 'error': 'command contains blocked characters (;, &&, ||, `, $()'}
        try:
            import shlex
            result = subprocess.run(shlex.split(cmd_strip), capture_output=True, text=True,
                                    timeout=30, cwd='/var/www/fina-connect')
            return {'ok': True, 'stdout': result.stdout[:50000], 'stderr': result.stderr[:5000], 'code': result.returncode}
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': 'timeout'}

    elif action in ('write', 'create', 'modify'):
        path = payload.get('path', '')
        content = payload.get('content', '')
        if not path or '..' in path:
            return {'ok': False, 'error': 'invalid path'}
        full = os.path.join('/var/www/fina-connect', path)
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w') as f:
                f.write(content)
            return {'ok': True, 'path': path, 'bytes': len(content)}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    return {'ok': False, 'error': 'unknown action: %s' % action}


# ══════════════════════════════════════════════════════════
# EXISTING VIEWS (preserved)
# ══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_superadmin)
@require_POST
def submit_request(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    req_type = data.get('type', 'upit')
    module = data.get('module', 'general')
    description = data.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Opis je obavezan'}, status=400)
    from core.company_utils import get_user_company
    company = get_user_company(request)
    action = PendingAIAction.objects.create(
        company=company, module=module,
        action_type='user_%s' % req_type,
        description=description,
        payload={'submitted_by': request.user.username, 'type': req_type},
        status='pending',
    )
    return JsonResponse({'ok': True, 'id': str(action.id), 'message': 'Zahtjev poslan (#%s)' % str(action.id)[:8]})


@login_required
@user_passes_test(is_superadmin)
@require_POST
def resolve_action(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    action_id = data.get('action_id')
    decision = data.get('decision', 'REJECTED')
    try:
        action = PendingAIAction.objects.get(pk=action_id)
    except PendingAIAction.DoesNotExist:
        return JsonResponse({'error': 'Akcija ne postoji'}, status=404)
    action.status = 'approved' if decision == 'APPROVED' else 'rejected'
    action.reviewed_by = request.user
    action.reviewed_at = timezone.now()
    action.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    AIActionLog.objects.create(
        company=action.company, module=action.module,
        action_type='resolve_%s' % action.action_type, access_level=2,
        outcome='allowed' if decision == 'APPROVED' else 'blocked',
        user=request.user, details={'action_id': str(action.id), 'decision': decision},
    )
    return JsonResponse({'ok': True, 'message': 'Akcija %s' % ('odobrena' if decision == 'APPROVED' else 'odbijena')})


@login_required
@user_passes_test(is_superadmin)
def action_logs(request):
    logs = AIActionLog.objects.select_related('company', 'user').order_by('-timestamp')[:200]
    module_filter = request.GET.get('module')
    outcome_filter = request.GET.get('outcome')
    if module_filter:
        logs = logs.filter(module=module_filter)
    if outcome_filter:
        logs = logs.filter(outcome=outcome_filter)
    return render(request, 'superadmin_ai/logs.html', {
        'logs': logs,
        'module_choices': [(m.module, m.module) for m in AIModulePermission.objects.filter(company=None)],
        'outcome_choices': AIActionLog.OUTCOME_CHOICES,
        'module_filter': module_filter or '',
        'outcome_filter': outcome_filter or '',
    })
