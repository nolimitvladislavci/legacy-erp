# PLAN_057 — AI Batch Processing

## Cilj
Masovna AI obrada na zahtjev ili po rasporedu. Marija ima 500 faktura — ne čeka jednu po jednu nego pokretanjem batch-a overnight ili vikendima. Celery orchestration, progress tracking, cost estimation before run.

## Scenariji
1. **Arhiva retrograde scan** — 500 starih dokumenata bez OCR-a → batch OCR overnight
2. **Bulk booking suggestions** — svi ArhivaEntry bez ai_suggestion → batch suggest
3. **Konto reconciliation** — sve transakcije bez konto parova → AI predloži
4. **DeepSeek Patrol** — noćni code audit (poseban task, vidi PLAN_064)

## Model: AIBatchJob
```python
class AIBatchJob(TenantModel):
    """
    Batch AI posao. Svaki job procesira N entiteta.
    """
    company = models.ForeignKey(Company, null=True, on_delete=models.SET_NULL, related_name="ai_batch_jobs")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class JobType(models.TextChoices):
        OCR_RETROGRADE = "ocr_retro", "Retrogradno OCR skeniranje"
        BOOKING_SUGGEST = "booking_suggest", "Bulk prijedlog knjiženja"
        DOCUMENT_CLASSIFY = "doc_classify", "Bulk klasifikacija dokumenata"
        INVOICE_VALIDATE = "invoice_validate", "Bulk validacija faktura"

    class Status(models.TextChoices):
        PENDING = "pending", "Čeka"
        RUNNING = "running", "U tijeku"
        PAUSED = "paused", "Pauzirano"
        COMPLETED = "completed", "Završeno"
        FAILED = "failed", "Greška"
        CANCELLED = "cancelled", "Otkazano"

    job_type = models.CharField(max_length=30, choices=JobType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Scope
    filters = models.JSONField(default=dict)  # npr. {"doc_type": "ulazni_racun", "date_from": "2026-01-01"}
    
    # Progress
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    failed_items = models.IntegerField(default=0)
    
    # Cost
    estimated_cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    actual_cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    
    # Timing
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    celery_task_id = models.CharField(max_length=100, blank=True)
    
    # Results summary
    result_summary = models.JSONField(default=dict)  # {"success": 480, "failed": 20, "skipped": 0}

    @property
    def progress_pct(self) -> int:
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)

    @property
    def estimated_duration_minutes(self) -> int:
        """Rough estimate: 3s per item on average."""
        return max(1, int(self.total_items * 3 / 60))
```

## Cost Estimation
```python
# Procjena troška PRIJE pokretanja

COST_PER_ITEM = {
    AIBatchJob.JobType.OCR_RETROGRADE: Decimal("0.003"),    # FenixScan: ~$0.003/doc
    AIBatchJob.JobType.BOOKING_SUGGEST: Decimal("0.0005"),  # Haiku: ~$0.0005/entry
    AIBatchJob.JobType.DOCUMENT_CLASSIFY: Decimal("0.0002"),
    AIBatchJob.JobType.INVOICE_VALIDATE: Decimal("0.0008"),
}

def estimate_batch_cost(job_type: str, item_count: int) -> Decimal:
    cost_per = COST_PER_ITEM.get(job_type, Decimal("0.001"))
    return (cost_per * item_count).quantize(Decimal("0.01"))
```

## URL struktura
```
/hr/ai/batch/                       → AIBatchListView
/hr/ai/batch/novi/                  → AIBatchCreateView
/hr/ai/batch/<uuid>/                → AIBatchDetailView (HTMX polling)
/hr/ai/batch/<uuid>/pause/          → AIBatchPauseView (POST)
/hr/ai/batch/<uuid>/cancel/         → AIBatchCancelView (POST)
/hr/ai/batch/api/estimate/          → AIBatchEstimateView (HTMX, live estimate)
```

## AIBatchCreateView
```python
class AIBatchCreateView(TenantView):
    permission_required = Permission.MANAGE_AI
    template_name = "ai_batch/create.html"

    def get(self, request):
        return render(request, self.template_name, {
            "job_types": AIBatchJob.JobType.choices,
        })

    def post(self, request):
        data = request.POST
        job_type = data["job_type"]
        filters = {
            "date_from": data.get("date_from"),
            "date_to": data.get("date_to"),
            "doc_type": data.get("doc_type"),
        }
        filters = {k: v for k, v in filters.items() if v}  # remove empty

        # Count items
        item_count = self._count_items(request.company, job_type, filters)
        if item_count == 0:
            messages.warning(request, "Nema entiteta koji odgovaraju filtrima.")
            return redirect("ai_batch:create")

        # Check AI budget
        budget = AIBudget.objects.filter(company=request.company).first()
        estimated = estimate_batch_cost(job_type, item_count)
        if budget and budget.hard_limit_enabled:
            if budget.current_month_spend + estimated > budget.monthly_limit_usd:
                messages.error(request, f"Nedovoljno AI budžeta. Potrebno: ${estimated}, dostupno: ${budget.monthly_limit_usd - budget.current_month_spend}")
                return redirect("ai_batch:create")

        job = AIBatchJob.objects.create(
            company=request.company,
            created_by=request.user,
            job_type=job_type,
            filters=filters,
            total_items=item_count,
            estimated_cost_usd=estimated,
            status=AIBatchJob.Status.PENDING,
        )

        # Pokreni Celery task
        task = run_ai_batch_job.delay(str(job.id))
        job.celery_task_id = task.id
        job.save(update_fields=["celery_task_id"])

        messages.success(request, f"Batch job pokrenut: {item_count} stavki, est. ${estimated}")
        return redirect("ai_batch:detail", pk=job.id)

    def _count_items(self, company, job_type: str, filters: dict) -> int:
        qs = self._get_queryset(company, job_type, filters)
        return qs.count()

    def _get_queryset(self, company, job_type: str, filters: dict):
        if job_type == AIBatchJob.JobType.OCR_RETROGRADE:
            qs = ArhivaEntry.objects.filter(
                company=company,
                ai_status=ArhivaEntry.AIStatus.PENDING,
                file__isnull=False,
            )
        elif job_type == AIBatchJob.JobType.BOOKING_SUGGEST:
            qs = ArhivaEntry.objects.filter(
                company=company,
                ai_status=ArhivaEntry.AIStatus.DONE,
                ai_suggestion__isnull=True,
            )
        else:
            qs = ArhivaEntry.objects.filter(company=company)
        
        if filters.get("date_from"):
            qs = qs.filter(document_date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(document_date__lte=filters["date_to"])
        if filters.get("doc_type"):
            qs = qs.filter(doc_type=filters["doc_type"])
        
        return qs
```

## Celery Task: run_ai_batch_job
```python
@shared_task(bind=True, base=AITask, queue="heavy", max_retries=3)
def run_ai_batch_job(self, job_id: str):
    job = AIBatchJob.objects.get(id=job_id)
    
    if job.status == AIBatchJob.Status.CANCELLED:
        return
    
    job.status = AIBatchJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save()
    
    view_helper = AIBatchCreateView()
    qs = view_helper._get_queryset(job.company, job.job_type, job.filters)
    
    for entry in qs.iterator(chunk_size=50):
        # Check for pause/cancel signal (Redis flag)
        if _is_paused_or_cancelled(job_id):
            job.status = AIBatchJob.Status.PAUSED
            job.save()
            return
        
        try:
            if job.job_type == AIBatchJob.JobType.OCR_RETROGRADE:
                result = FenixScan().scan(entry.file.path)
                entry.ai_raw_response = result
                entry.vendor_name = result.get("vendor_name", "")
                entry.total_amount = Decimal(str(result.get("total_amount", 0)))
                entry.ai_status = ArhivaEntry.AIStatus.DONE
                entry.save()
            
            elif job.job_type == AIBatchJob.JobType.BOOKING_SUGGEST:
                suggestion = ai_gateway.suggest_async(entry)
                entry.ai_suggestion = suggestion
                entry.save(update_fields=["ai_suggestion"])
            
            AIBatchJob.objects.filter(id=job.id).update(
                processed_items=models.F("processed_items") + 1,
                actual_cost_usd=models.F("actual_cost_usd") + Decimal("0.001"),
            )
        
        except Exception as e:
            logger.error(f"Batch item failed: {entry.id}: {e}")
            AIBatchJob.objects.filter(id=job.id).update(
                failed_items=models.F("failed_items") + 1
            )
        
        # Throttle: max 20 items/second (avoid API rate limits)
        time.sleep(0.05)
    
    job.refresh_from_db()
    job.status = AIBatchJob.Status.COMPLETED
    job.completed_at = timezone.now()
    job.result_summary = {
        "success": job.processed_items,
        "failed": job.failed_items,
        "total": job.total_items,
    }
    job.save()


def _is_paused_or_cancelled(job_id: str) -> bool:
    from django.core.cache import cache
    return cache.get(f"ai_batch_stop_{job_id}") is not None
```

## Pause/Cancel
```python
class AIBatchPauseView(TenantView):
    def post(self, request, pk):
        job = get_object_or_404(AIBatchJob, id=pk, company=request.company)
        cache.set(f"ai_batch_stop_{pk}", "pause", timeout=3600)
        return JsonResponse({"ok": True})

class AIBatchCancelView(TenantView):
    def post(self, request, pk):
        job = get_object_or_404(AIBatchJob, id=pk, company=request.company)
        cache.set(f"ai_batch_stop_{pk}", "cancel", timeout=3600)
        # Revoke Celery task
        if job.celery_task_id:
            from celery.app import current_app
            current_app.control.revoke(job.celery_task_id, terminate=True)
        job.status = AIBatchJob.Status.CANCELLED
        job.save()
        return JsonResponse({"ok": True})
```

## Template: ai_batch/detail.html (HTMX progress)
```html
<div hx-get="/hr/ai/batch/{{ job.id }}/"
     hx-trigger="every 5s [job.status === 'running']"
     hx-swap="outerHTML"
     hx-select="#batch-progress">

  <div id="batch-progress" class="card">
    <!-- Progress bar -->
    <div class="mb-4">
      <div class="flex justify-between text-sm mb-1">
        <span>{{ job.processed_items }} / {{ job.total_items }} stavki</span>
        <span>{{ job.progress_pct }}%</span>
      </div>
      <div class="h-3 bg-gray-100 rounded-full">
        <div class="h-3 bg-fenix-500 rounded-full transition-all"
             style="width: {{ job.progress_pct }}%"></div>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-3 gap-4 text-center">
      <div>
        <div class="text-2xl font-bold text-green-600">{{ job.processed_items }}</div>
        <div class="text-xs text-gray-500">Obrađeno</div>
      </div>
      <div>
        <div class="text-2xl font-bold text-red-500">{{ job.failed_items }}</div>
        <div class="text-xs text-gray-500">Greška</div>
      </div>
      <div>
        <div class="text-2xl font-bold text-gray-700">${{ job.actual_cost_usd }}</div>
        <div class="text-xs text-gray-500">Potrošeno</div>
      </div>
    </div>

    <!-- Actions -->
    {% if job.status == "running" %}
    <div class="flex gap-3 mt-4">
      <button hx-post="/hr/ai/batch/{{ job.id }}/pause/" class="btn-secondary btn-sm">Pauziraj</button>
      <button hx-post="/hr/ai/batch/{{ job.id }}/cancel/" class="btn-danger btn-sm">Otkaži</button>
    </div>
    {% endif %}
  </div>
</div>
```

## Live Estimate (HTMX)
```python
class AIBatchEstimateView(TenantView):
    def get(self, request):
        job_type = request.GET.get("job_type")
        filters = {
            "date_from": request.GET.get("date_from"),
            "date_to": request.GET.get("date_to"),
        }
        view = AIBatchCreateView()
        count = view._count_items(request.company, job_type, filters) if job_type else 0
        cost = estimate_batch_cost(job_type, count) if job_type else Decimal("0")
        duration = max(1, int(count * 3 / 60))
        
        return render(request, "ai_batch/partials/estimate.html", {
            "count": count,
            "cost": cost,
            "duration_minutes": duration,
        })
```

## Scheduled batch (Beat)
```python
# Overnight retrogradno skeniranje — pokreće se u 02:30
@shared_task(queue="scheduled")
def schedule_overnight_batch():
    """Ako postoje neprocesirani dokumenti, pokreni batch."""
    for company in Company.objects.filter(is_active=True):
        pending_count = ArhivaEntry.objects.filter(
            company=company,
            ai_status=ArhivaEntry.AIStatus.PENDING,
        ).count()
        if pending_count >= 10:  # min threshold
            job = AIBatchJob.objects.create(
                company=company,
                job_type=AIBatchJob.JobType.OCR_RETROGRADE,
                filters={},
                total_items=pending_count,
                estimated_cost_usd=estimate_batch_cost("ocr_retro", pending_count),
                status=AIBatchJob.Status.PENDING,
            )
            task = run_ai_batch_job.delay(str(job.id))
            job.celery_task_id = task.id
            job.save(update_fields=["celery_task_id"])
```

Beat schedule:
```python
"overnight-ai-batch": {
    "task": "ai_batch.tasks.schedule_overnight_batch",
    "schedule": crontab(hour="2", minute="30"),
}
```
