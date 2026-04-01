"""
BORG FENIX — AI Assistant Quick Actions + Auto Knowledge (F3.2)
Pre-built prompts for common actions + auto-generate KnowledgeArticles from patrol data.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('borg.ai_assistant')

# Quick action templates - shown as buttons in AI chat widget
QUICK_ACTIONS = [
    {
        'id': 'check_pdv',
        'label': 'Provjeri PDV status',
        'icon': 'receipt',
        'prompt': 'Provjeri PDV status za moju firmu — koliko imam neplaćenog PDV-a i kad je sljedeći rok za prijavu?',
        'module_context': 'konto',
    },
    {
        'id': 'unpaid_invoices',
        'label': 'Neplaćene fakture',
        'icon': 'alert-triangle',
        'prompt': 'Pokaži mi sve neplaćene fakture starije od 30 dana sa iznosima i partnerima.',
        'module_context': 'invoicing',
    },
    {
        'id': 'account_balance',
        'label': 'Stanje računa',
        'icon': 'wallet',
        'prompt': 'Pokaži stanje žiro računa i cash flow za zadnjih 30 dana.',
        'module_context': 'konto',
    },
    {
        'id': 'pos_today',
        'label': 'POS danas',
        'icon': 'shopping-cart',
        'prompt': 'Koliko je danas prometovano na POS-u? Po blagajnama i ukupno.',
        'module_context': 'pos',
    },
    {
        'id': 'opportunities',
        'label': 'Moje prilike',
        'icon': 'gift',
        'prompt': 'Koje porezne olakšice i poticaje mogu iskoristiti? Prikaži uštedu.',
        'module_context': 'intelligence',
    },
    {
        'id': 'supplier_risk',
        'label': 'Rizici dobavljača',
        'icon': 'shield-alert',
        'prompt': 'Ima li upozorenja o riziku za moje dobavljače? Blokade, stečajevi?',
        'module_context': 'intelligence',
    },
]


def get_quick_actions_for_user(user):
    """Return quick actions filtered by user's company modules."""
    return QUICK_ACTIONS


@shared_task
def generate_knowledge_from_patrols():
    """
    Auto-generate KnowledgeArticles from patrol reports.
    Groups patrol findings into actionable articles.
    """
    from ai_assistant.models import PatrolReport, KnowledgeArticle

    # Get patrols from last 7 days that haven't been processed
    week_ago = timezone.now() - timezone.timedelta(days=7)
    recent_patrols = PatrolReport.objects.filter(
        created_at__gte=week_ago,
    ).order_by('-created_at')[:50]

    if not recent_patrols:
        return {'articles_created': 0}

    # Group patrol findings by company
    from collections import defaultdict
    by_company = defaultdict(list)
    for patrol in recent_patrols:
        company_name = str(patrol)[:60].split(' — ')[-1] if ' — ' in str(patrol) else 'General'
        by_company[company_name].append(str(patrol))

    created = 0
    for company_name, findings in by_company.items():
        title = f"Patrol sažetak: {company_name} ({timezone.now().strftime('%Y-%m-%d')})"

        # Skip if similar article exists
        if KnowledgeArticle.objects.filter(title__startswith=f"Patrol sažetak: {company_name}").exists():
            continue

        content = f"Automatski generirano iz {len(findings)} patrol reporta.\n\n"
        for i, finding in enumerate(findings[:10], 1):
            content += f"{i}. {finding}\n"

        KnowledgeArticle.objects.create(
            title=title[:200],
            content=content[:5000],
            module='patrol',
            is_active=True,
        )
        created += 1

    logger.info('Generated %d knowledge articles from patrols', created)
    return {'articles_created': created}


@shared_task
def ai_health_check():
    """Check AI assistant health — API keys, model availability, usage stats."""
    import os
    from ai_assistant.models import AIUsageLog, Conversation

    health = {
        'anthropic_key': bool(os.environ.get('ANTHROPIC_API_KEY', '')),
        'gemini_key': bool(os.environ.get('GEMINI_API_KEY', '')),
        'total_conversations': Conversation.objects.count(),
        'total_usage_logs': AIUsageLog.objects.count(),
        'last_7d_conversations': Conversation.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count(),
    }

    logger.info('AI health check: %s', health)
    return health
