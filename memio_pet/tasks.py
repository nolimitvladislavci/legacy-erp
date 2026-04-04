"""
memio_pet/tasks.py -- Celery periodic tasks

trust_score_refresh: Svaka 24h recalculate Trust Score za sve breedere.
"""
import logging
from celery import shared_task

logger = logging.getLogger("memio_pet")


@shared_task(name="memio_pet.trust_score_refresh")
def trust_score_refresh():
    """Periodic: refresh Trust Score za sve breedere."""
    from memio_pet.trust_score import bulk_update_trust_scores
    results = bulk_update_trust_scores()
    logger.info("Trust Score refresh: %d breedera azurirano", len(results))
    return {"updated": len(results), "scores": {name: score for name, score in results}}
