# TRAK A — BACKEND / DATABASE

**Vlasnik**: Backend AI agent (Sonnet je idealan, Opus za design odluke)
**File područje**: `accounts/`, `companies/`, `invoicing/`, **NOVO**: `core/searchable/`, `core/cache/`, `core/intent_registry/`
**NE diraj**: `templates/`, `qa_lab/`, `static/`, `no_limit/`

---

## CILJ

Pretvoriti Fenix V3 bazu u **AI-ready** sloj koji:
1. Dopušta semantičku pretragu (`embedding`)
2. Dopušta brz tekstualni FTS (`search_vector`)
3. Dopušta ranjivu kategorizaciju (`tags`)
4. Cache-ira često korištene odgovore (Redis L1)
5. Drži intent registry (mapping ljudski upit → SQL/handler)

---

## SPRINT 1 — Searchable mixin (T1, 22.04.–28.04.)

### Akcija A1.1 — Migracija za Company

```python
# companies/migrations/0013_searchable_mixin.py
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('companies', '0012_add_pdf_template_to_company')]
    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS pg_trgm;"),
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS unaccent;"),
        migrations.AddField('company', 'tags', models.JSONField(default=list, blank=True)),
        migrations.AddField('company', 'search_vector', SearchVectorField(null=True, blank=True)),
        migrations.AddField('company', 'ai_summary', models.TextField(blank=True)),
        migrations.AddField('company', 'last_interacted_at', models.DateTimeField(null=True, blank=True)),
        migrations.AddField('company', 'interaction_count', models.IntegerField(default=0)),
        migrations.AddIndex('company', GinIndex(fields=['tags'], name='company_tags_gin')),
        migrations.AddIndex('company', GinIndex(fields=['search_vector'], name='company_fts_gin')),
        migrations.RunSQL("""
            CREATE OR REPLACE FUNCTION update_company_search_vector() RETURNS TRIGGER AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('simple', unaccent(COALESCE(NEW.name, ''))), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(NEW.oib, '')), 'B') ||
                    setweight(to_tsvector('simple', unaccent(COALESCE(NEW.address, ''))), 'C') ||
                    setweight(to_tsvector('simple', unaccent(COALESCE(NEW.ai_summary, ''))), 'D');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER company_search_vector_update
            BEFORE INSERT OR UPDATE ON companies_company
            FOR EACH ROW EXECUTE FUNCTION update_company_search_vector();
        """, reverse_sql="DROP TRIGGER IF EXISTS company_search_vector_update ON companies_company; DROP FUNCTION IF EXISTS update_company_search_vector;")
    ]
```

### Akcija A1.2 — `core/searchable/mixin.py` (zajednički)

```python
# core/searchable/mixin.py
class SearchableMixin(models.Model):
    tags = models.JSONField(default=list, blank=True)
    search_vector = SearchVectorField(null=True, blank=True)
    ai_summary = models.TextField(blank=True)
    last_interacted_at = models.DateTimeField(null=True, blank=True)
    interaction_count = models.IntegerField(default=0)

    class Meta:
        abstract = True

    def add_tag(self, tag):
        if tag not in self.tags:
            self.tags.append(tag)
            self.save(update_fields=['tags'])

    def touch_interaction(self):
        from django.utils import timezone
        self.last_interacted_at = timezone.now()
        self.interaction_count += 1
        self.save(update_fields=['last_interacted_at', 'interaction_count'])
```

### Akcija A1.3 — Backfill ai_summary za postojeće Company-je

```python
# core/searchable/tasks.py
from celery import shared_task
from companies.models import Company
from anthropic import Anthropic

@shared_task
def backfill_ai_summary(batch_size=20):
    client = Anthropic()
    qs = Company.objects.filter(ai_summary='')[:batch_size]
    for c in qs:
        text = f"{c.name}, OIB {c.oib}, {c.address or ''}, {c.activity_description or ''}"
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role":"user","content":f"Saetaj ovu firmu u jednoj recenici (max 15 rijeci, hrvatski): {text}"}]
        )
        c.ai_summary = msg.content[0].text.strip()
        c.save(update_fields=['ai_summary'])
```

Schedule: jednom dnevno, batch 20 = 0.01 EUR/dan.

### Akcija A1.4 — Resolver service (osnova)

```python
# core/searchable/resolver.py
from django.contrib.postgres.search import SearchQuery, SearchRank
from companies.models import Company

def resolve_company(query: str, limit=5):
    """Vraca top N firmi po relevantnosti, kombinacija FTS + tags + recency."""
    sq = SearchQuery(query, config='simple')
    qs = (Company.objects
          .annotate(rank=SearchRank('search_vector', sq))
          .filter(search_vector=sq)
          .order_by('-rank', '-last_interacted_at')[:limit])
    return list(qs.values('id', 'name', 'oib', 'rank'))
```

---

## SPRINT 2 — pgvector + embeddings (T2, 29.04.–05.05.)

### Akcija A2.1 — pgvector ekstenzija + VectorField

```bash
# Provjera da pgvector postoji
psql -d fenix_v3_clean -c "CREATE EXTENSION IF NOT EXISTS vector;"
pip install pgvector
```

```python
# companies/migrations/0014_company_embedding.py
from pgvector.django import VectorField, HnswIndex
operations = [
    migrations.AddField('company', 'embedding', VectorField(dimensions=384, null=True, blank=True)),
    migrations.AddIndex('company',
        HnswIndex(fields=['embedding'], name='company_embed_hnsw',
                  m=8, ef_construction=100,
                  opclasses=['vector_cosine_ops'])),
]
```

**Napomena**: Koristim **384 dim (multilingual MiniLM)** umjesto 768 (LaBSE) — 50% manje RAM-a, dovoljna kvaliteta za HR.

### Akcija A2.2 — Embedding generator (lokalno, bez API troška)

```python
# core/searchable/embeddings.py
from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _model

def embed_text(text: str):
    return get_model().encode(text, normalize_embeddings=True).tolist()
```

### Akcija A2.3 — Asinkroni embedding s debouncing

```python
# core/searchable/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from companies.models import Company
from .tasks import regenerate_embedding_debounced

@receiver(post_save, sender=Company)
def queue_embedding(sender, instance, **kwargs):
    # Debounce: 5 min nakon zadnje izmjene
    regenerate_embedding_debounced.apply_async(
        args=[instance.id], countdown=300, expires=600,
        task_id=f"emb_company_{instance.id}"  # idempotent: nova izmjena overrides
    )
```

---

## SPRINT 3 — Redis L1 cache + Intent Registry (T3, 06.05.–12.05.)

### Akcija A3.1 — Redis cache za hot lookups

```python
# core/cache/lookup.py
from django.core.cache import cache

def cached_company_search(query: str, ttl=900):
    key = f"comp:search:{query.lower()}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    from core.searchable.resolver import resolve_company
    result = resolve_company(query)
    cache.set(key, result, ttl)
    return result

# Invalidation hook
def invalidate_company_caches(company_id):
    cache.delete_pattern(f"comp:*")  # naive but works for small system
```

### Akcija A3.2 — Intent Registry tablica

```python
# core/intent_registry/models.py
class IntentDefinition(models.Model):
    name = models.SlugField(max_length=64, unique=True)  # "create_invoice"
    handler_path = models.CharField(max_length=256)      # "invoicing.views.create_invoice"
    example_phrases = models.JSONField(default=list)     # ["napravi račun", "create invoice", ...]
    schema = models.JSONField(default=dict)              # slot definitions
    enabled = models.BooleanField(default=True)
```

---

## SLJEDEĆA AKCIJA (sljedeći agent počinje ovdje)

→ **Akcija A1.1**: kreiraj migraciju za Company. Provjeri da postoji `pg_trgm`, `unaccent`, `vector` ekstenzija. Pokreni `migrate`.

## ZADNJA IZMJENA

| Datum | Tko | Što je dovršeno | Sljedeći korak |
|---|---|---|---|
| 21.04.2026. | Opus design | Plan napisan | Pokrenuti A1.1 |

---

## DEPENDENCIES

- **Čeka**: ništa (može početi odmah)
- **Blokira**: Trak C (AI Resolver) ne može početi prije Sprint 1 gotov

## POVEZANI URL-OVI

- Resolver service test: `https://limit-connect.com/api/test/resolve/?q=Nikolic`
- pgvector verzija: `SELECT extversion FROM pg_extension WHERE extname='vector';`
