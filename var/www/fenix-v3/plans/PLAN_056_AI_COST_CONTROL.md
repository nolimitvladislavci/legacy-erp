# PLAN_056 — AI Cost Control Dashboard

## Cilj
AI troškovi su potencijalna crna rupa. Svaki API poziv se logira, agregira, prikazuje u dashboardu. Budget alarms. Per-company billing. Model comparison. "Zlatni Paket" tier kontrola.

## Model: AIUsageLog
```python
class AIUsageLog(TenantModel):
    """
    Svaki AI API poziv se logira ovdje.
    Kreira se u AIGateway._log_usage() (PLAN_010).
    """
    company = models.ForeignKey(Company, null=True, on_delete=models.SET_NULL, related_name="ai_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Provider(models.TextChoices):
        ANTHROPIC = "anthropic", "Anthropic"
        BEDROCK = "bedrock", "AWS Bedrock"
        GOOGLE = "google", "Google AI"
        DEEPSEEK = "deepseek", "DeepSeek"

    class UseCase(models.TextChoices):
        OCR = "ocr", "FenixScan OCR"
        BOOKING_SUGGESTION = "booking", "Prijedlog knjiženja"
        TROJSTVO = "trojstvo", "Trojstvo konsenzus"
        COCKPIT = "cockpit", "AI Cockpit"
        SMART_IMPORT = "smart_import", "Smart Import"
        PATROL = "patrol", "DeepSeek Patrol"
        GENERAL = "general", "Opći"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    model_name = models.CharField(max_length=50)  # "claude-haiku-4-5", "gemini-1.5-flash"
    use_case = models.CharField(max_length=30, choices=UseCase.choices, default=UseCase.GENERAL)
    
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=8, default=0)
    duration_ms = models.IntegerField(default=0)
    
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=200, blank=True)
    
    # Reference na entitet koji je pokrenuo poziv
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["use_case", "created_at"]),
            models.Index(fields=["provider", "created_at"]),
        ]


class AIBudget(TenantModel):
    """
    Budžet ograničenja po kompaniji.
    """
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="ai_budget")
    monthly_limit_usd = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    alert_threshold_pct = models.IntegerField(default=80)  # alert kad dođe do 80%
    hard_limit_enabled = models.BooleanField(default=False)  # blokira AI na 100%
    current_month_spend = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    last_reset_at = models.DateField(null=True)
    
    def is_over_limit(self) -> bool:
        if not self.hard_limit_enabled:
            return False
        return self.current_month_spend >= self.monthly_limit_usd
    
    def usage_pct(self) -> int:
        if self.monthly_limit_usd == 0:
            return 0
        return int((self.current_month_spend / self.monthly_limit_usd) * 100)
```

## Signal: auto-update budget na svaki AI log
```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=AIUsageLog)
def update_ai_budget(sender, instance, created, **kwargs):
    if not created or not instance.company_id:
        return
    budget, _ = AIBudget.objects.get_or_create(company_id=instance.company_id)
    AIBudget.objects.filter(id=budget.id).update(
        current_month_spend=models.F("current_month_spend") + instance.cost_usd
    )
    # Check threshold
    budget.refresh_from_db()
    if budget.usage_pct() >= budget.alert_threshold_pct:
        notify_budget_threshold.delay(str(budget.id))
```

## Celery task: reset monthly budgets
```python
@shared_task(queue="scheduled")
def reset_monthly_ai_budgets():
    """Pokreće se 1. u mjesecu u 00:00."""
    first_of_month = date.today().replace(day=1)
    AIBudget.objects.filter(last_reset_at__lt=first_of_month).update(
        current_month_spend=Decimal("0"),
        last_reset_at=first_of_month,
    )
```

Beat schedule:
```python
"reset-ai-budgets": {
    "task": "ai_cost.tasks.reset_monthly_ai_budgets",
    "schedule": crontab(day_of_month="1", hour="0", minute="0"),
}
```

## URL struktura
```
/hr/ai/troskovi/                     → AICostDashboardView
/hr/ai/troskovi/log/                 → AIUsageLogListView (filterable)
/hr/ai/troskovi/budzet/              → AIBudgetView (GET/POST)
/hr/ai/troskovi/export/              → AIExportView (CSV)
/hr/ai/troskovi/api/stats/           → AIStatsAPIView (charts data)
```

## AICostDashboardView
```python
class AICostDashboardView(TenantView):
    permission_required = Permission.MANAGE_AI
    template_name = "ai_cost/dashboard.html"

    def get(self, request):
        today = date.today()
        month_start = today.replace(day=1)
        company = request.company

        budget, _ = AIBudget.objects.get_or_create(company=company)
        
        # Agregati za ovaj mjesec
        month_logs = AIUsageLog.objects.filter(
            company=company,
            created_at__date__gte=month_start,
        )
        
        by_use_case = month_logs.values("use_case").annotate(
            total_cost=Sum("cost_usd"),
            total_calls=Count("id"),
            total_tokens=Sum("total_tokens"),
        ).order_by("-total_cost")
        
        by_provider = month_logs.values("provider").annotate(
            total_cost=Sum("cost_usd"),
            total_calls=Count("id"),
        ).order_by("-total_cost")
        
        by_day = month_logs.annotate(
            day=TruncDate("created_at")
        ).values("day").annotate(
            cost=Sum("cost_usd")
        ).order_by("day")
        
        return render(request, self.template_name, {
            "budget": budget,
            "month_total": month_logs.aggregate(s=Sum("cost_usd"))["s"] or Decimal("0"),
            "month_calls": month_logs.count(),
            "by_use_case": list(by_use_case),
            "by_provider": list(by_provider),
            "by_day": list(by_day),
            "recent_logs": month_logs.order_by("-created_at").select_related("user")[:20],
            "over_limit": budget.is_over_limit(),
        })
```

## Template: ai_cost/dashboard.html
Sekcije:

**1. Budget Gauge (Alpine.js)**
```html
<div x-data="{ pct: {{ budget.usage_pct }} }">
  <div class="relative w-32 h-32 mx-auto">
    <!-- SVG arc gauge -->
    <svg viewBox="0 0 36 36" class="w-full h-full">
      <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        fill="none" stroke="#e5e7eb" stroke-width="3"/>
      <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        fill="none"
        :stroke="pct >= 80 ? '#ef4444' : pct >= 50 ? '#f59e0b' : '#22c55e'"
        stroke-width="3"
        :stroke-dasharray="`${pct}, 100`"/>
    </svg>
    <div class="absolute inset-0 flex flex-col items-center justify-center">
      <span class="text-2xl font-bold" :class="pct >= 80 ? 'text-red-600' : 'text-gray-700'"
            x-text="pct + '%'"></span>
      <span class="text-xs text-gray-400">od budžeta</span>
    </div>
  </div>
  <p class="text-center text-sm mt-2">
    ${{ month_total|floatformat:4 }} / ${{ budget.monthly_limit_usd }}
  </p>
</div>
```

**2. Troškovi po use-case (bar chart)**
```html
<!-- Jednostavni CSS bar chart bez JS biblioteke -->
<div class="space-y-3">
  {% for item in by_use_case %}
  <div>
    <div class="flex justify-between text-sm mb-1">
      <span>{{ item.use_case_display }}</span>
      <span class="font-mono">${{ item.total_cost|floatformat:4 }} ({{ item.total_calls }} poziva)</span>
    </div>
    <div class="h-2 bg-gray-100 rounded-full">
      <div class="h-2 bg-fenix-500 rounded-full"
           style="width: {{ item.total_cost|percentage:month_total }}%"></div>
    </div>
  </div>
  {% endfor %}
</div>
```

**3. Daily spend (mini sparkline)**
```html
<!-- SVG sparkline — no library needed -->
<svg class="w-full h-16" viewBox="0 0 {{ by_day|length|multiply:10 }} 40">
  {% for point in by_day %}
    <rect x="{{ forloop.counter0|multiply:10 }}" 
          y="{{ point.cost|to_sparkline_y:max_day_cost }}"
          width="8" 
          height="{{ point.cost|to_sparkline_height:max_day_cost }}"
          fill="#6366f1" rx="2"/>
  {% endfor %}
</svg>
```

**4. Recent log table**
```html
<table class="table">
  <thead>
    <tr>
      <th>Vrijeme</th><th>Model</th><th>Svrha</th><th>Tokeni</th><th>Cijena</th><th>Korisnik</th>
    </tr>
  </thead>
  <tbody>
    {% for log in recent_logs %}
    <tr>
      <td class="text-sm text-gray-500">{{ log.created_at|timesince }}</td>
      <td><span class="badge-info text-xs">{{ log.model_name }}</span></td>
      <td>{{ log.get_use_case_display }}</td>
      <td class="font-mono text-sm">{{ log.total_tokens|intcomma }}</td>
      <td class="font-mono text-sm">${{ log.cost_usd|floatformat:6 }}</td>
      <td class="text-sm">{{ log.user.get_full_name|default:"–" }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

## AIBudgetView (HTMX)
```python
class AIBudgetView(TenantView):
    permission_required = Permission.MANAGE_AI
    template_name = "ai_cost/budget_form.html"

    def get(self, request):
        budget, _ = AIBudget.objects.get_or_create(company=request.company)
        return render(request, self.template_name, {"budget": budget})

    def post(self, request):
        budget, _ = AIBudget.objects.get_or_create(company=request.company)
        budget.monthly_limit_usd = Decimal(request.POST.get("monthly_limit_usd", "10.00"))
        budget.alert_threshold_pct = int(request.POST.get("alert_threshold_pct", 80))
        budget.hard_limit_enabled = request.POST.get("hard_limit_enabled") == "on"
        budget.save()
        if request.headers.get("HX-Request"):
            return render(request, "ai_cost/partials/budget_saved.html")
        messages.success(request, "AI budžet ažuriran.")
        return redirect("ai_cost:dashboard")
```

## Hard limit middleware
```python
# core/middleware.py — dodat u AIMiddleware

class AIHardLimitMiddleware:
    """Blokira AI pozive ako je hard limit prekoračen."""
    AI_URLS = ["/hr/smart-import/upload/", "/hr/arhiva/upload/", "/hr/ai-cockpit/"]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if any(request.path.startswith(url) for url in self.AI_URLS):
            company = getattr(request, "company", None)
            if company:
                budget = AIBudget.objects.filter(company=company).first()
                if budget and budget.is_over_limit():
                    if request.headers.get("HX-Request"):
                        return HttpResponse(
                            '<div class="alert-danger">AI budžet iscrpljen. Kontaktiraj administratora.</div>',
                            status=402
                        )
                    messages.error(request, "AI budžet za ovaj mjesec je iscrpljen.")
                    return redirect("ai_cost:dashboard")
        return self.get_response(request)
```

## Notifikacija: budget threshold
```python
@shared_task(queue="default")
def notify_budget_threshold(budget_id: str):
    budget = AIBudget.objects.get(id=budget_id)
    company = budget.company
    # Email adminu
    send_mail(
        subject=f"[Fenix] AI budžet {budget.usage_pct()}% — {company.name}",
        message=f"AI troškovi su dosegli {budget.usage_pct()}% od ${budget.monthly_limit_usd} budžeta.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[m.user.email for m in company.memberships.filter(role__in=["owner","admin"])],
        fail_silently=True,
    )
```

## Template tags za dashboard
```python
@register.filter
def percentage(value, total):
    if not total:
        return 0
    return min(int((Decimal(str(value)) / Decimal(str(total))) * 100), 100)

@register.filter
def to_sparkline_y(cost, max_cost):
    if not max_cost:
        return 40
    return int(40 - (float(cost) / float(max_cost)) * 35)

@register.filter
def to_sparkline_height(cost, max_cost):
    if not max_cost:
        return 5
    return max(int((float(cost) / float(max_cost)) * 35), 2)
```

## CSV Export
```python
class AIExportView(TenantView):
    permission_required = Permission.MANAGE_AI

    def get(self, request):
        month = request.GET.get("month", date.today().strftime("%Y-%m"))
        year, m = month.split("-")
        logs = AIUsageLog.objects.filter(
            company=request.company,
            created_at__year=year,
            created_at__month=m,
        ).order_by("created_at")
        
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ai-troskovi-{month}.csv"'
        response.write('\ufeff')  # BOM za Excel
        writer = csv.writer(response)
        writer.writerow(["Datum", "Model", "Svrha", "Input tokeni", "Output tokeni", "Cijena USD", "Korisnik"])
        for log in logs:
            writer.writerow([
                log.created_at.strftime("%Y-%m-%d %H:%M"),
                log.model_name,
                log.get_use_case_display(),
                log.input_tokens,
                log.output_tokens,
                str(log.cost_usd),
                log.user.email if log.user else "",
            ])
        return response
```

## Testovi
```python
def test_budget_increments_on_log(company):
    AIUsageLog.objects.create(company=company, cost_usd=Decimal("0.001"), ...)
    budget = AIBudget.objects.get(company=company)
    assert budget.current_month_spend == Decimal("0.001")

def test_hard_limit_blocks_ai_endpoint(auth_client, company):
    budget = AIBudget.objects.create(
        company=company,
        monthly_limit_usd=Decimal("0.01"),
        current_month_spend=Decimal("0.01"),
        hard_limit_enabled=True,
    )
    resp = auth_client.get("/hr/smart-import/upload/")
    assert resp.status_code in [302, 402]

def test_monthly_reset_zeroes_spend(company):
    AIBudget.objects.create(company=company, current_month_spend=Decimal("5.00"), last_reset_at=date(2026,3,1))
    reset_monthly_ai_budgets()
    budget = AIBudget.objects.get(company=company)
    assert budget.current_month_spend == Decimal("0")
```
