"""Gemini Agent Celery Tasks — autonomno izvršavanje zadataka."""
import logging
from celery import shared_task

logger = logging.getLogger('gemini_agent')


@shared_task(bind=True, soft_time_limit=300, max_retries=0)
def run_gemini_task(self, task_description, max_steps=10, requested_by='system'):
    """
    Pokreni Gemini agenta kao Celery task.
    Iste ovlasti kao Claude Code — čita, piše, izvršava.

    Args:
        task_description: Što Gemini treba napraviti
        max_steps: Max broj koraka (default 10)
        requested_by: Tko je pokrenuo (za audit)

    Returns:
        dict sa summary
    """
    from core.gemini_agent import GeminiAgent

    logger.info('[GEMINI TASK] Started by %s: %s', requested_by, task_description[:100])

    agent = GeminiAgent(max_steps=max_steps)
    result = agent.run_task(task_description)
    result['requested_by'] = requested_by

    # Upozori ako Gemini nije ništa napravio
    if not result.get('stvarni_rad', True):
        logger.error('[GEMINI TASK] UPOZORENJE: 0 fajlova napisano, 0 komandi — task nije izvrsio nista!')
        from core.whatsapp import send_text
        try:
            send_text(
                phone='+491723006985',
                message=f"🟠 Gemini task nije izvrsio nista (0 fajlova/komandi).
Task: {task_description[:100]}
Pokrenuo: {requested_by}"
            )
        except Exception:
            pass

    # Notificiraj superadmina o završetku
    try:
        from superadmin_ai.tasks import _notify_superadmins
        _notify_superadmins(
            title='Gemini Agent završio zadatak',
            message='%s\n\nKoraci: %d | Fajlovi: %d | Pokrenuo: %s' % (
                task_description[:100],
                result.get('steps', 0),
                len(result.get('files_written', [])),
                requested_by,
            ),
            notification_type='system',
        )
    except Exception:
        pass

    return result
