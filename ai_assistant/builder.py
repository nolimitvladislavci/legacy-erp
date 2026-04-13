"""
AI Builder — Katana Engine
Split-screen IDE: chat lijevo, code preview desno.
Čita kontekst modula prije AI poziva za anti-halucinaciju.
Gemini 2.5 Pro za code generation, PendingAIAction za sigurnost.
"""
import json
import os
import logging
import traceback
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import DatabaseError, IntegrityError

from .models import Conversation, Message
from .claude_client import get_claude_client
from superadmin_ai.models import AIModulePermission, PendingAIAction, AIActionLog

logger = logging.getLogger(__name__)

BASE_DIR = '/var/www/fina-connect'

# ── Guard ──
def _is_builder_user(user):
    """Superuser ili staff (Marija)."""
    return user.is_superuser or user.is_staff


def get_module_context(module_name):
    """Čita models.py, views.py i forms.py modula za AI kontekst."""
    context_parts = []
    base_path = os.path.join(BASE_DIR, module_name)

    for filename in ['models.py', 'views.py', 'forms.py', 'urls.py']:
        fpath = os.path.join(base_path, filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Limitiraj na 5000 znakova po fajlu za token ekonomiju
                if len(content) > 5000:
                    content = content[:5000] + f"\n\n# ... [skraćeno, ukupno {len(content)} znakova]"
                context_parts.append(f"--- {module_name}/{filename} ---\n{content}")
            except (FileNotFoundError, PermissionError, IOError):
                pass

    # Template-i (lista naziva)
    template_dir = os.path.join(BASE_DIR, 'templates', module_name)
    if os.path.isdir(template_dir):
        try:
            templates = [f for f in os.listdir(template_dir) if f.endswith('.html')]
            if templates:
                context_parts.append(f"--- {module_name} templates ---\n" + "\n".join(templates))
        except Exception:
            pass

    return "\n\n".join(context_parts) if context_parts else f"[Modul '{module_name}' nema čitljivih datoteka]"


# ══════════════════════════════════════════
# BUILDER VIEW — Split-screen IDE
# ══════════════════════════════════════════

@login_required
@user_passes_test(_is_builder_user)
def builder_page(request):
    """Prikazuje Katana IDE sučelje."""
    modules = AIModulePermission.objects.filter(company=None).order_by('module')
    conversations = Conversation.objects.filter(
        user=request.user, is_active=True, module_context='builder'
    )[:20]
    return render(request, 'ai_assistant/builder_page.html', {
        'modules': modules,
        'conversations': conversations,
        'is_builder': True,
    })


# ══════════════════════════════════════════
# GENERATE — Gemini 2.5 Pro s kontekstom
# ══════════════════════════════════════════

@login_required
@user_passes_test(_is_builder_user)
@require_POST
def builder_generate(request):
    """Čita kontekst modula, šalje Gemini-ju, vraća strukturirani prijedlog."""
    try:
        data = json.loads(request.body)
        user_prompt = data.get('prompt', '').strip()
        target_module = data.get('module', '').strip()

        if not user_prompt or not target_module:
            return JsonResponse({
                'status': 'error',
                'message': 'Prazan zahtjev ili nije odabran ciljani modul.'
            }, status=400)

        # Čitaj kontekst modula
        module_context = get_module_context(target_module)

        # Pokušaj Gemini, fallback na Claude
        result = _call_gemini(user_prompt, target_module, module_context)
        if result is None:
            result = _call_claude(user_prompt, target_module, module_context)

        if result.get('error'):
            return JsonResponse({
                'status': 'error',
                'message': result['error']
            }, status=500)

        # Formiranje konačnog koda za preview
        proposed_code = ""
        if result.get('model_code'):
            proposed_code += f"### MODELS.PY ###\n{result['model_code']}\n\n"
        if result.get('view_code'):
            proposed_code += f"### VIEWS.PY ###\n{result['view_code']}\n\n"
        if result.get('html_code'):
            proposed_code += f"### TEMPLATE ###\n{result['html_code']}"

        if not proposed_code.strip():
            proposed_code = result.get('raw_response', 'AI nije generirao kod.')

        return JsonResponse({
            'status': 'success',
            'message': 'AI je uspješno generirao kod. Pregledajte prijedlog.',
            'description': result.get('description', ''),
            'proposed_code': proposed_code,
            'target_module': target_module,
            'action_type': result.get('action_type', 'modify'),
        })

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Builder generate error: %s", traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': f'Sistemska greška: {str(e)}'
        }, status=500)


def _call_gemini(prompt, module, context):
    """Poziv Gemini 2.5 Pro API-ja."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return None  # Fallback na Claude

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')

        system_instruction = f"""Ti si vrhunski Django inženjer za LIMIT Connect ERP sustav.
Ciljani modul za modifikaciju je: {module}

OVO JE TRENUTNI IZVORNI KOD TOG MODULA:
{context}

KORISNIČKI ZAHTJEV: {prompt}

Generiraj kod koji ispunjava zahtjev, poštujući POSTOJEĆU arhitekturu.
Vrati ISKLJUČIVO čisti JSON (bez markdown backticks) sa ključevima:
"description": "Kratko objašnjenje na hrvatskom što si napravio",
"model_code": "Kod za models.py (prazno ako nema promjena)",
"view_code": "Kod za views.py (prazno ako nema promjena)",
"html_code": "HTML/Template kod (prazno ako nema promjena)",
"action_type": "Kategorija: model_update, view_update, template_update, form_update, style_change, logic_change"
"""
        response = model.generate_content(system_instruction)
        text = response.text.strip()

        # Čišćenje markdown wrappera
        if text.startswith('```json'):
            text = text[7:]
        if text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                'description': 'AI je vratio odgovor ali ne u JSON formatu.',
                'raw_response': text,
                'action_type': 'modify',
            }

    except ImportError:
        return None
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Gemini call failed: %s, falling back to Claude", e)
        return None


def _call_claude(prompt, module, context):
    """Fallback: Claude Haiku s istim kontekstom."""
    try:
        client = get_claude_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=f"""Ti si Django inženjer za LIMIT Connect ERP.
Modul: {module}
Trenutni kod:
{context}

Vrati ISKLJUČIVO JSON sa: description, model_code, view_code, html_code, action_type.
Bez markdown backticks. Odgovaraj na hrvatskom.""",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return {
                'description': 'Claude odgovor:',
                'raw_response': text,
                'action_type': 'modify',
            }
    except (json.JSONDecodeError, ValueError) as e:
        return {'error': f'Ni Gemini ni Claude nisu dostupni: {str(e)}'}


# ══════════════════════════════════════════
# QUEUE — Šalje u PendingAIAction
# ══════════════════════════════════════════

@login_required
@user_passes_test(_is_builder_user)
@require_POST
def builder_queue(request):
    """Šalje pregledani kod u red čekanja za superadmin odobrenje."""
    try:
        data = json.loads(request.body)
        target_module = data.get('module', '')
        proposed_code = data.get('code', '')
        description = data.get('description', '')
        action_type = data.get('action_type', 'modify')

        if not proposed_code or not target_module:
            return JsonResponse({
                'status': 'error',
                'message': 'Nedostaju podaci za kreiranje zahtjeva.'
            }, status=400)

        action = PendingAIAction.objects.create(
            company=None,
            module=target_module,
            action_type=action_type,
            description=description,
            proposed_code=proposed_code,
            payload={
                'source': 'katana_builder',
                'requested_by': request.user.get_full_name() or request.user.username,
                'requested_at': timezone.now().isoformat(),
            },
            status='pending',
        )

        # Audit log
        AIActionLog.objects.create(
            company=None,
            module=target_module,
            action_type=action_type,
            access_level=AIModulePermission.ACCESS_ASSISTED,
            outcome='queued',
            user=request.user,
            details={'action_id': str(action.id), 'source': 'katana_builder'},
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Promjena poslana u Red čekanja (ID: {str(action.id)[:8]}...). Čeka odobrenje superadmina.',
        })
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ══════════════════════════════════════════
# CHAT API — konverzacijski mod (existing)
# ══════════════════════════════════════════

@login_required
@user_passes_test(_is_builder_user)
@require_POST
def builder_api(request):
    """Chat API za konverzacijski builder mod (Claude + tools)."""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({"error": "Pristup odbijen"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user_message = data.get("message", "").strip()
    conv_id = data.get("conversation_id")

    if not user_message:
        return JsonResponse({"error": "Poruka je prazna"}, status=400)

    if conv_id:
        conversation = get_object_or_404(Conversation, id=conv_id, user=request.user)
    else:
        conversation = Conversation.objects.create(
            user=request.user, title=user_message[:80], module_context='builder',
        )

    Message.objects.create(conversation=conversation, role="user", content=user_message)

    history = []
    for msg in conversation.messages.all():
        if msg.role in ("user", "assistant"):
            history.append({"role": msg.role, "content": msg.content})

    # Simple Claude call for chat mode
    try:
        client = get_claude_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system="""Ti si AI Builder asistent za LIMIT Connect ERP.
Pomazeš korisnicima prilagoditi sustav. Odgovaraj na hrvatskom.
Kada korisnik opisuje promjenu, predloži korake i objasni što se mijenja.
Za generiranje koda, uputi ih da koriste Katana Engine (lijevi panel → odaberi modul → opiši promjenu).""",
            messages=history,
        )
        final_content = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
    except (IntegrityError, DatabaseError) as e:
        final_content = f"Greška: {e}"
        tokens = 0

    Message.objects.create(
        conversation=conversation, role="assistant", content=final_content, tokens_used=tokens,
    )

    return JsonResponse({
        "content": final_content,
        "conversation_id": conversation.id,
        "tokens": tokens,
    })
