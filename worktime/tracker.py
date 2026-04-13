"""
Universal Activity Tracker — fire-and-forget, transaction-safe.
Usage:
    from worktime.tracker import track
    track(user, 'POS', 'CHECKOUT', ref='Bon #42', detail='3 stavke, 25.50 EUR')
"""

import logging

from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger("worktime")


def track(user, module, action, ref="", detail="", metadata=None, company=None):
    """
    Jedina funkcija koju drugi moduli trebaju zvati.
    - transaction.on_commit: ne salje event ako transakcija rollbacka
    - Ne usporava pozivatelja — upis ide nakon commita
    - Nikad ne baca exception pozivatelju
    """
    if not user or not getattr(user, "is_authenticated", False):
        return

    company_id = None
    if company:
        company_id = company.pk if hasattr(company, "pk") else company
    elif hasattr(user, "company_id"):
        company_id = user.company_id

    user_id = user.pk
    now_iso = timezone.now().isoformat()
    _meta = metadata or {}

    def _write():
        try:
            from worktime.models import ActivityEvent

            ActivityEvent.objects.create(
                company_id=company_id,
                user_id=user_id,
                timestamp=timezone.datetime.fromisoformat(now_iso),
                action=action,
                detail="[%s] %s" % (module, str(detail)[:200]),
                metadata={**_meta, "module": module, "ref": str(ref)[:50]},
            )
        except (IntegrityError, DatabaseError) as e:
            logger.warning("ActivityEvent write failed: %s", e)

    try:
        transaction.on_commit(_write)
    except (IntegrityError, DatabaseError):
        pass  # Outside transaction — silently skip
