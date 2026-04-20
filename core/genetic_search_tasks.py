"""
core/genetic_search_tasks.py — Nočna evolucija gena

Celery Beat: svaki dan u 03:00
  1. Učitaj SearchAuditLog iz zadnjih 24h
  2. Ažuriraj fitness za svaki gen
  3. Selekcija: top 20% = elite
  4. Crossover + Mutation: generiraj potomke
  5. Ukloni slabe gene (fitness < 0.1, generation > 3)
"""

import logging
import random

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="core.evolve_search_genes", bind=True, max_retries=1)
def evolve_search_genes_task(self):
    """
    Dnevna evolucija search gena po svim firmama.
    Pokreće se 03:00 svaki dan via Celery Beat.
    """
    from datetime import timedelta

    from companies.models import Company

    from .genetic_search_models import SearchGene
    from .search_audit_models import SearchAuditLog

    since_24h = timezone.now() - timedelta(hours=24)
    total_evolved = 0
    total_offspring = 0

    companies = Company.objects.filter(is_active=True).values_list("pk", flat=True)

    for company_pk in companies:
        try:
            n_evolved, n_off = _evolve_company(company_pk, since_24h, SearchGene, SearchAuditLog)
            total_evolved += n_evolved
            total_offspring += n_off
        except Exception as exc:
            logger.warning("Gene evolution failed for company %s: %s", company_pk, exc)

    logger.info(
        "Genetic evolution complete: %d genes updated, %d offspring created",
        total_evolved,
        total_offspring,
    )
    return {"evolved": total_evolved, "offspring": total_offspring}


def _evolve_company(company_pk, since_24h, SearchGene, SearchAuditLog):
    """Evolucija gena za jednu firmu."""
    from django.db.models import Avg, Count

    # ── 1. Ažuriraj fitness iz SearchAuditLog ────────────────────────────
    recent_logs = (
        SearchAuditLog.objects.filter(company_id=company_pk, searched_at__gte=since_24h)
        .values("query")
        .annotate(searches=Count("id"), avg_results=Avg("result_count"))
    )

    evolved = 0
    for row in recent_logs:
        q = row["query"]
        if not q or len(q) < 2:
            continue
        gene = SearchGene.get_or_seed(company_pk, q)
        # Simuliraj CTR: ako avg_results > 0, pretpostavljamo 30% CTR
        if row["avg_results"] and row["avg_results"] > 0:
            gene.click_count += max(1, int(row["searches"] * 0.3))
        gene.use_count += row["searches"]
        gene.last_used_at = timezone.now()
        gene._recalculate_fitness()
        gene.save(update_fields=["use_count", "click_count", "last_used_at", "fitness"])
        evolved += 1

    # ── 2. Selekcija — elite = top 20% ───────────────────────────────────
    all_genes = list(SearchGene.objects.filter(company_id=company_pk).order_by("-fitness"))
    if not all_genes:
        return evolved, 0

    elite_count = max(1, len(all_genes) // 5)
    elite_ids = [g.pk for g in all_genes[:elite_count]]

    SearchGene.objects.filter(company_id=company_pk).update(is_elite=False)
    SearchGene.objects.filter(pk__in=elite_ids).update(is_elite=True, evolved_at=timezone.now())

    # ── 3. Crossover — kombiniraj parove elita ───────────────────────────
    elites = all_genes[:elite_count]
    offspring_count = 0

    if len(elites) >= 2:
        pairs = min(3, len(elites) // 2)
        for _ in range(pairs):
            a, b = random.sample(elites, 2)
            child_query = _crossover(a.query, b.query)
            if not child_query or len(child_query) < 2:
                continue
            # Mutation
            if random.random() < 0.10:
                child_query = _mutate(child_query)
            # Spremi dijete ako ne postoji
            if not SearchGene.objects.filter(company_id=company_pk, query=child_query).exists():
                SearchGene.objects.create(
                    company_id=company_pk,
                    query=child_query[:300],
                    fitness=max(a.fitness, b.fitness) * 0.7,  # dijete počinje na 70% boljeg roditelja
                    generation=max(a.generation, b.generation) + 1,
                    parent_a=a,
                    parent_b=b,
                )
                offspring_count += 1

    # ── 4. Ukloni slabe gene (fitness < 0.05, stariji od 7 dana) ─────────
    old_threshold = timezone.now() - __import__("datetime").timedelta(days=7)
    SearchGene.objects.filter(
        company_id=company_pk,
        fitness__lt=0.05,
        generation__gt=0,
        born_at__lt=old_threshold,
    ).delete()

    return evolved, offspring_count


def _crossover(q1: str, q2: str) -> str:
    """
    Crossover dvije query stringove.
    Strategija: uzmi prvu polovicu q1 + drugu polovicu q2.
    """
    if not q1 or not q2:
        return q1 or q2 or ""
    mid1 = len(q1) // 2
    mid2 = len(q2) // 2
    child = (q1[:mid1] + " " + q2[mid2:]).strip()
    return child[:300] if len(child) > 2 else ""


def _mutate(query: str) -> str:
    """
    Mutacija: zamijeni jedan znak na random poziciji s bliskim znakom.
    Primjer: 'baumaxx' → 'baumax' (duplikat uklonjen)
    """
    if len(query) < 2:
        return query
    pos = random.randint(0, len(query) - 1)
    mutations = [
        lambda q, i: q[:i] + q[i + 1 :],  # brisanje
        lambda q, i: q[:i] + q[i] + q[i:],  # duplikacija
        lambda q, i: q[:i] + q[i].upper() + q[i + 1 :],  # uppercase
        lambda q, i: q[:i] + " " + q[i:],  # space insert
    ]
    fn = random.choice(mutations)
    try:
        result = fn(query, pos)
        return result[:300] if result else query
    except Exception:
        return query
