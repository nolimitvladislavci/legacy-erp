import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET

from .models import Conversation, Message, AIUsageLog
from .claude_client import chat_with_claude, SYSTEM_PROMPT, estimate_cost
from .tools import TOOLS
from .tool_handlers import handle_tool_call

logger = logging.getLogger(__name__)

def _ai_rate_check(user, max_calls=30, window_seconds=3600):
    """Per-user rate limit for AI API: max_calls per window_seconds.
    Uses Redis cache with DB fallback for reliability."""
    from django.core.cache import cache
    cache_key = f'ai_rate:{user.pk}'
    count = cache.get(cache_key)
    if count is not None:
        return count < max_calls
    # Fallback to DB if cache miss
    from django.utils import timezone
    import datetime
    cutoff = timezone.now() - datetime.timedelta(seconds=window_seconds)
    recent = AIUsageLog.objects.filter(user=user, created_at__gte=cutoff).count()
    cache.set(cache_key, recent, timeout=60)  # cache 60s
    return recent < max_calls


def _ai_rate_increment(user):
    """Increment rate limit counter in cache after successful call."""
    from django.core.cache import cache
    cache_key = f'ai_rate:{user.pk}'
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=3600)




def _get_company(request):
    """Get the current company from request/user."""
    company = getattr(request, "company", None)
    if not company:
        try:
            from companies.models import Company
            company = request.user.profile.company if hasattr(request.user, "profile") else None
        except Exception:
            pass
    return company


@login_required
def chat_page(request):
    """Full-page AI chat interface."""
    conversations = Conversation.objects.filter(
        user=request.user, is_active=True
    )[:20]
    # Get or create active conversation
    conv_id = request.GET.get("conv")
    if conv_id:
        conversation = get_object_or_404(
            Conversation, id=conv_id, user=request.user
        )
    else:
        conversation = conversations.first()

    messages_qs = []
    if conversation:
        messages_qs = conversation.messages.all()

    return render(request, "ai_assistant/chat_page.html", {
        "conversations": conversations,
        "conversation": conversation,
        "messages": messages_qs,
    })


@login_required
@require_POST
def chat_api(request):
    """API endpoint for chat messages. Handles tool-use loop."""
    try:
        return _chat_api_inner(request)
    except Exception as e:
        import logging
        logging.getLogger('ai_assistant').error(f'chat_api unhandled: {e}', exc_info=True)
        return JsonResponse({
            "error": "Connect AI trenutno nije dostupan. Pokušajte za nekoliko sekundi.",
        }, status=500)


def _chat_api_inner(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Rate limiting: 30 calls/user/hour
    if not _ai_rate_check(request.user):
        return JsonResponse({
            "error": "Prekoracen limit poziva. Maksimalno 30 upita po satu. Pokusajte kasnije."
        }, status=429)

    user_message = data.get("message", "").strip()
    conv_id = data.get("conversation_id")
    module_context = data.get("module_context", "")

    if not user_message:
        return JsonResponse({"error": "Poruka je prazna"}, status=400)

    # Get or create conversation
    if conv_id:
        conversation = get_object_or_404(
            Conversation, id=conv_id, user=request.user
        )
    else:
        title = user_message[:80] if len(user_message) > 80 else user_message
        conversation = Conversation.objects.create(
            user=request.user,
            title=title,
            module_context=module_context,
        )

    # Save user message
    Message.objects.create(
        conversation=conversation,
        role="user",
        content=user_message,
    )

    # Build message history for Claude
    history = []
    for msg in conversation.messages.all():
        if msg.role in ("user", "assistant"):
            history.append({"role": msg.role, "content": msg.content})

    company = _get_company(request)

    # Call Claude (with tool-use loop, max 5 iterations)
    total_input = 0
    total_output = 0
    final_content = ""
    all_tool_calls = []
    all_tool_results = []

    for _ in range(5):
        result = chat_with_claude(
            messages=history,
            tools=TOOLS,
            system=SYSTEM_PROMPT,
            user=request.user,
        )

        total_input += result["usage"]["input_tokens"]
        total_output += result["usage"]["output_tokens"]

        if result["stop_reason"] == "error":
            final_content = result["content"]
            break

        if result["tool_calls"]:
            # Execute tools and append results
            all_tool_calls.extend(result["tool_calls"])

            # Build assistant message with tool_use blocks
            assistant_content = []
            if result["content"]:
                assistant_content.append({"type": "text", "text": result["content"]})
            for tc in result["tool_calls"]:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["input"],
                })
            history.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and build tool_result message
            tool_results_content = []
            for tc in result["tool_calls"]:
                tool_result = handle_tool_call(
                    tc["name"], tc["input"], request.user, company
                )
                all_tool_results.append({
                    "tool_use_id": tc["id"],
                    "name": tc["name"],
                    "result": tool_result,
                })
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })
            history.append({"role": "user", "content": tool_results_content})
        else:
            # No tool calls — final response
            final_content = result["content"]
            break
    else:
        # Exhausted iterations
        if not final_content:
            final_content = result.get("content", "Dostignut je limit iteracija.")

    # Save assistant message
    Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=final_content,
        tool_calls=all_tool_calls,
        tool_results=all_tool_results,
        tokens_used=total_input + total_output,
    )

    # Log usage
    AIUsageLog.objects.create(
        user=request.user,
        conversation=conversation,
        input_tokens=total_input,
        output_tokens=total_output,
        cost_estimate=estimate_cost(total_input, total_output),
    )

    # Update conversation title if first message
    if conversation.messages.count() <= 2 and not conversation.title:
        conversation.title = user_message[:80]
        conversation.save(update_fields=["title"])

    return JsonResponse({
        "content": final_content,
        "conversation_id": conversation.id,
        "tokens": total_input + total_output,
    })


@login_required
@require_GET
def chat_widget_data(request):
    """Returns widget status JSON for the floating chat widget."""
    recent = Conversation.objects.filter(
        user=request.user, is_active=True
    ).first()
    return JsonResponse({
        "has_conversation": recent is not None,
        "conversation_id": recent.id if recent else None,
        "title": recent.title if recent else "",
    })


@login_required
def patrol_page(request):
    """Show patrol reports for user's company."""
    from core.company_utils import get_user_company
    from .models import PatrolReport
    company = get_user_company(request)
    reports = PatrolReport.objects.filter(company=company)[:30] if company else PatrolReport.objects.none()
    return render(request, 'ai_assistant/patrol.html', {'reports': reports})


@login_required
def ai_intro(request):
    """AI introduction / onboarding assistant."""
    from core.company_utils import get_user_company
    company = get_user_company(request)

    if request.method == 'POST':
        if company:
            try:
                ob = company.onboarding
                ob.ai_intro_completed = True
                ob.save(update_fields=['ai_intro_completed'])
            except Exception:
                pass
        return JsonResponse({'ok': True})

    if company:
        try:
            ob = company.onboarding
            if not ob.ai_intro_shown:
                ob.ai_intro_shown = True
                ob.save(update_fields=['ai_intro_shown'])
        except Exception:
            pass

    context = {'company': company, 'plan': 'starter', 'modules': []}
    if company:
        try:
            sub = company.subscriptions.filter(is_active=True).first()
            if sub:
                context['plan'] = sub.plan
                context['modules'] = list(sub.allowed_modules)
        except Exception:
            pass

    return render(request, 'ai_assistant/ai_intro.html', context)


@login_required
@require_GET
def ai_context_widget(request):
    """Return contextual AI tips based on current module/page."""
    module = request.GET.get('module', '')

    tips = {
        'invoicing': {
            'title': 'Fakturiranje',
            'icon': 'fa-file-invoice-dollar',
            'tips': [
                'Koristite predloske za brze kreiranje racuna.',
                'Postavite automatske podsjetnike za neplacene fakture.',
                'e-Racun modul omogucuje slanje direktno u FINA CIS.',
            ],
            'quick_actions': [
                {'label': 'Novi racun', 'url': '/invoicing/wizard/', 'icon': 'fa-plus'},
                {'label': 'Neplaceni', 'url': '/invoicing/?status=UNPAID', 'icon': 'fa-exclamation'},
            ]
        },
        'inventory': {
            'title': 'Zalihe',
            'icon': 'fa-warehouse',
            'tips': [
                'Smart Import automatski prepoznaje artikle iz PDF/XML.',
                'Postavite min_quantity za automatska upozorenja.',
                'Koristite barkod skener za brzi unos.',
            ],
            'quick_actions': [
                {'label': 'Novi artikl', 'url': '/inventory/item/new/', 'icon': 'fa-plus'},
                {'label': 'Inventura', 'url': '/inventory/stocktake/', 'icon': 'fa-clipboard-check'},
            ]
        },
        'partners': {
            'title': 'Partneri',
            'icon': 'fa-handshake',
            'tips': [
                'Importirajte partnere iz Synesis arhive.',
                'Dodajte OIB za automatsku provjeru tvrtke.',
                'Koristite CRM za pracenje komunikacije.',
            ],
            'quick_actions': [
                {'label': 'Novi partner', 'url': '/partners/create/', 'icon': 'fa-user-plus'},
            ]
        },
        'pos': {
            'title': 'POS Blagajna',
            'icon': 'fa-cash-register',
            'tips': [
                'Gastro meni omogucuje QR narucivanje.',
                'Postavite Pfand (povratnu ambalazu) za boce.',
                'KDS tablet prikazuje narudzbe u kuhinji.',
            ],
            'quick_actions': [
                {'label': 'Nova smjena', 'url': '/pos/open/', 'icon': 'fa-play'},
            ]
        },
        'worktime': {
            'title': 'Radni sati',
            'icon': 'fa-clock',
            'tips': [
                'GPS geofence osigurava clock-in samo na lokaciji.',
                'Prekovremeni sati se automatski racunaju.',
                'Izvoz u Payroll za obracun placa.',
            ],
            'quick_actions': [
                {'label': 'Pregled sati', 'url': '/worktime/', 'icon': 'fa-list'},
            ]
        },
        'rental': {
            'title': 'Najam (Robot Hotel)',
            'icon': 'fa-hotel',
            'tips': [
                'Guest self-checkin smanjuje recepcijsko opterecenje.',
                'Sezonske cijene automatski se primjenjuju.',
                'Housekeeping se automatski kreira po checkoutu.',
            ],
            'quick_actions': [
                {'label': 'Kalendar', 'url': '/rental/calendar/', 'icon': 'fa-calendar'},
            ]
        },
    }

    data = tips.get(module, {
        'title': 'Connect',
        'icon': 'fa-robot',
        'tips': [
            'Pitaj me bilo sto o svom poslovanju.',
            'Jutarnji patrol analizira podatke svaki dan.',
            'Ctrl+K otvara brzu navigaciju.',
        ],
        'quick_actions': [
            {'label': 'Connect Chat', 'url': '/ai/', 'icon': 'fa-comments'},
        ]
    })

    return JsonResponse(data)


@login_required
@require_GET
def patrol_insights_api(request):
    """Return latest patrol insights as JSON for dashboard widget."""
    from .models import PatrolReport
    from .patrol import generate_insights
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return JsonResponse({'insights': [], 'summary': '', 'has_issues': False})

    report = PatrolReport.objects.filter(company=company).order_by('-created_at').first()
    if not report:
        return JsonResponse({'insights': [], 'summary': 'Jos nema patrol izvjestaja.', 'has_issues': False})

    insights = generate_insights(report)
    return JsonResponse({
        'insights': insights,
        'summary': report.summary or '',
        'has_issues': report.has_issues,
        'finding_count': report.finding_count,
        'critical_count': report.critical_count,
        'created_at': report.created_at.isoformat(),
    })



@login_required
@require_POST
def analyze_image(request):
    """Analyze an image using Claude Haiku vision."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    b64 = data.get('image_b64', '')
    prompt = data.get('prompt', 'What is in this image?')
    module = data.get('module', 'general')

    if not b64:
        return JsonResponse({'error': 'No image'}, status=400)

    if not _ai_rate_check(request.user):
        return JsonResponse({'error': 'Rate limit exceeded'}, status=429)

    try:
        import anthropic, os
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=500,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                    {'type': 'text', 'text': prompt},
                ],
            }],
        )
        _ai_rate_increment(request.user)
        return JsonResponse({'response': response.content[0].text})
    except Exception as e:
        logger.error(f'analyze_image error: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
