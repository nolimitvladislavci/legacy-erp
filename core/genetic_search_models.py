"""
core/genetic_search_models.py — Genetic Search Engine

Upiti koji se koriste mnogo i daju dobre rezultate → visok fitness.
Svakodnevna evolucija: top queriji preživljavaju, mutiraju, stvaraju potomke.
Rezultat: sustav sam nauči što korisnici zapravo traže.

Algoritam:
  1. Selection: top 20% po fitness su "elite"
  2. Crossover: kombinira parove elite → novi "dijete" query
  3. Mutation: ±1 znak na random poziciji (10% šansa)
  4. Fitness = CTR_score × result_bonus × freshness
"""

import uuid

from django.db import models
from django.utils import timezone


class SearchGene(models.Model):
    """
    Jedan "gen" — upit koji je prošao selekciju.
    Fitness raste s korištenjem, pada bez korištenja (freshness decay).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="search_genes",
    )
    query = models.CharField(max_length=300, db_index=True)
    fitness = models.FloatField(default=0.5, db_index=True, help_text="0-1, viši = bolji gen")

    # Genetika
    generation = models.PositiveSmallIntegerField(default=0, help_text="0 = original, 1+ = potomak")
    parent_a = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children_a",
    )
    parent_b = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children_b",
    )
    mutation_count = models.PositiveSmallIntegerField(default=0)
    is_elite = models.BooleanField(default=False, db_index=True)

    # Statistike
    use_count = models.PositiveIntegerField(default=0, help_text="Koliko puta je ovaj gen 'udarao'")
    click_count = models.PositiveIntegerField(default=0, help_text="Klikovi na rezultate")

    # Lifecycle
    born_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    evolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "core"
        verbose_name = "Search gene"
        verbose_name_plural = "Search genes"
        indexes = [
            models.Index(fields=["company", "fitness"]),
            models.Index(fields=["company", "is_elite"]),
            models.Index(fields=["company", "query"]),
        ]
        unique_together = [("company", "query")]
        ordering = ["-fitness"]

    def __str__(self):
        elite = "⭐" if self.is_elite else ""
        return f"{elite}[Gen {self.generation}] '{self.query[:40]}' fitness={self.fitness:.2f}"

    def record_hit(self, clicked: bool = False) -> None:
        """Zabilježi korištenje gena i ažuriraj fitness."""
        self.use_count += 1
        if clicked:
            self.click_count += 1
        self.last_used_at = timezone.now()
        self._recalculate_fitness()
        self.save(update_fields=["use_count", "click_count", "last_used_at", "fitness"])

    def _recalculate_fitness(self) -> None:
        """
        Fitness formula:
          CTR score   = click_count / max(use_count, 1)    → 0-1
          Volume bon. = min(1.0, use_count / 50.0)         → više pretraga = bolji gen
          Freshness   = exp(-days_since_use / 30)          → stariji gen pada
          Fitness     = (CTR × 0.5 + Volume × 0.3 + Freshness × 0.2)
        """
        import math

        ctr = self.click_count / max(self.use_count, 1)
        volume = min(1.0, self.use_count / 50.0)

        if self.last_used_at:
            days_idle = (timezone.now() - self.last_used_at).days
            freshness = math.exp(-days_idle / 30.0)
        else:
            freshness = 0.1

        self.fitness = round(ctr * 0.5 + volume * 0.3 + freshness * 0.2, 4)

    @classmethod
    def get_or_seed(cls, company, query: str) -> "SearchGene":
        """Dohvati ili kreiraj gen za ovaj query."""
        gene, _ = cls.objects.get_or_create(
            company=company,
            query=query[:300],
            defaults={"fitness": 0.1, "generation": 0},
        )
        return gene

    @classmethod
    def top_elite(cls, company, limit: int = 5) -> list[str]:
        """Vrati top elite upite za Boost prikaz u CMD centru."""
        return list(cls.objects.filter(company=company, is_elite=True).values_list("query", flat=True)[:limit])
