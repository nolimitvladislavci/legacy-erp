# CC_TASK_SUBSCRIPTION_TRACKING — ARR i churn za skaliranje na 1500 korisnika
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-25

**Kontekst:** Platform ide u produkciju 01.04. Na 86+ firmi, nema modela koji prati
tko plaća, koji plan, koliko ARR, tko je u churn riziku. Bez ovoga ne možeš
znati je li platforma profitabilna ni kad dodati hardware.

---

## ZADATAK 1 — Model: CompanySubscription

**Fajl:** `registration/models.py` ili novi `billing/models.py`

```python
from django.db import models
from django.utils import timezone
from django.conf import settings
import decimal


class CompanySubscription(models.Model):
    """
    Prati aktivnu pretplatu po firmi.
    Jedan aktivni zapis po firmi u bilo kojem trenutku.
    """
    STATUS_CHOICES = [
        ('trialing',   'Trial (15 dana)'),
        ('active',     'Aktivna'),
        ('past_due',   'Kasni s plaćanjem'),
        ('cancelled',  'Otkazana'),
        ('paused',     'Pauzirana'),
    ]

    company = models.OneToOneField(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name='Tvrtka',
    )
    plan = models.CharField(
        max_length=50,
        verbose_name='Plan',
        help_text='Iz PLAN_FEATURES: pausalalac, udruga, starter, professional...',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')

    # Datumi
    trial_start = models.DateTimeField(null=True, blank=True, verbose_name='Početak triala')
    trial_end   = models.DateTimeField(null=True, blank=True, verbose_name='Kraj triala (15 dana)')
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name='Aktivacija')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Otkazano')
    next_billing = models.DateField(null=True, blank=True, verbose_name='Sljedeće naplaćivanje')

    # Financije
    monthly_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=decimal.Decimal('0.00'),
        verbose_name='Iznos/mj (EUR)',
    )
    currency = models.CharField(max_length=3, default='EUR')

    # Payment gateway ref (Stripe/Revolut — za kasniju integraciju)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    revolut_subscription_id = models.CharField(max_length=100, blank=True)

    # Meta
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_subscriptions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Pretplata'
        verbose_name_plural = 'Pretplate'

    def __str__(self):
        return f'{self.company.name} → {self.plan} ({self.status})'

    @property
    def arr(self):
        """Annual Recurring Revenue za ovu firmu."""
        if self.status in ('active', 'trialing'):
            return self.monthly_amount * 12
        return decimal.Decimal('0.00')

    @property
    def is_trial_active(self):
        return self.status == 'trialing' and self.trial_end and self.trial_end > timezone.now()

    @property
    def days_until_trial_end(self):
        if not self.trial_end:
            return None
        delta = self.trial_end - timezone.now()
        return max(0, delta.days)

    def start_trial(self):
        """Poziva se pri registraciji. 15 dana trial."""
        self.status = 'trialing'
        self.trial_start = timezone.now()
        self.trial_end = timezone.now() + timezone.timedelta(days=15)
        self.save(update_fields=['status', 'trial_start', 'trial_end', 'updated_at'])

    def activate(self, plan=None, monthly_amount=None):
        """Poziva se kad korisnik odabere plaćeni plan."""
        if plan:
            self.plan = plan
        if monthly_amount is not None:
            self.monthly_amount = monthly_amount
        self.status = 'active'
        self.activated_at = timezone.now()
        self.next_billing = (timezone.now() + timezone.timedelta(days=30)).date()
        self.save()

    def cancel(self):
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancelled_at', 'updated_at'])
```

---

## ZADATAK 2 — SubscriptionMetrics: ARR dashboard

**Fajl:** novi `billing/metrics.py`

```python
from django.db.models import Sum, Count, Q
from django.utils import timezone


def get_platform_metrics():
    """
    Sve metrike platforme u jednom pozivu.
    Koristi u cockpitu i admin dashboardu.
    """
    from billing.models import CompanySubscription

    now = timezone.now()
    subs = CompanySubscription.objects.all()

    active = subs.filter(status='active')
    trialing = subs.filter(status='trialing', trial_end__gt=now)
    past_due = subs.filter(status='past_due')
    cancelled = subs.filter(status='cancelled')

    # ARR
    arr = active.aggregate(
        total=Sum('monthly_amount')
    )['total'] or 0
    arr_annual = arr * 12

    # Trial → konverzija u zadnjih 30 dana
    last_30 = now - timezone.timedelta(days=30)
    converted = active.filter(activated_at__gte=last_30).count()
    trials_ended = subs.filter(
        status__in=['active', 'cancelled'],
        trial_end__gte=last_30,
        trial_end__lte=now,
    ).count()
    conversion_rate = (converted / trials_ended * 100) if trials_ended else 0

    # Churn u zadnjih 30 dana
    churned = cancelled.filter(cancelled_at__gte=last_30).count()

    # MRR po planu
    mrr_by_plan = list(
        active.values('plan').annotate(
            count=Count('id'),
            mrr=Sum('monthly_amount'),
        ).order_by('-mrr')
    )

    return {
        'mrr': float(arr),
        'arr': float(arr_annual),
        'active_count': active.count(),
        'trialing_count': trialing.count(),
        'past_due_count': past_due.count(),
        'churned_30d': churned,
        'converted_30d': converted,
        'conversion_rate': round(conversion_rate, 1),
        'mrr_by_plan': mrr_by_plan,
        'trial_ending_soon': trialing.filter(
            trial_end__lte=now + timezone.timedelta(days=3)
        ).count(),
    }
```

---

## ZADATAK 3 — Auto-kreiranje pri registraciji

U `registration/views.py`, `admin_approve_registration()`, odmah nakon `company.save()`:

```python
from billing.models import CompanySubscription
from registration.constants import PLAN_FEATURES

plan_key = registration.selected_plan or 'starter'
plan_data = PLAN_FEATURES.get(plan_key, {})
monthly = plan_data.get('price', 0)

sub, created = CompanySubscription.objects.get_or_create(
    company=company,
    defaults={
        'plan': plan_key,
        'monthly_amount': monthly,
        'created_by': request.user,
    }
)
if created:
    sub.start_trial()
```

---

## ZADATAK 4 — Signal: auto-trial za postojeće firme (backfill)

Management command za 86 Synesis firmi koje nemaju subscription:

```python
# billing/management/commands/init_subscriptions.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Backfill: kreira CompanySubscription za firme koje je nemaju'

    def handle(self, *args, **options):
        from companies.models import Company
        from billing.models import CompanySubscription

        companies_without_sub = Company.objects.exclude(
            id__in=CompanySubscription.objects.values('company_id')
        )

        created = 0
        for co in companies_without_sub:
            sub = CompanySubscription.objects.create(
                company=co,
                plan='starter',  # default
                monthly_amount=0,  # Synesis firme su Marijini klijenti, platit će kad budu aktivne
                status='trialing',
            )
            self.stdout.write(f'  Created: {co.name}')
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Ukupno kreirano: {created} subscriptiona'))
```

Pokretanje: `venv/bin/python manage.py init_subscriptions`

---

## ZADATAK 5 — Cockpit widget (mini)

U `core/cockpit_views.py`, u context cockpit dashboarda:

```python
from billing.metrics import get_platform_metrics

context['billing_metrics'] = get_platform_metrics()
```

U cockpit template, dodaj karticice:
```html
<div class="row g-2 mb-3">
  <div class="col-md-3">
    <div class="stat-card text-center">
      <div class="h4 text-warning">{{ billing_metrics.mrr|floatformat:0 }} €</div>
      <div class="text-muted small">MRR</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="stat-card text-center">
      <div class="h4 text-success">{{ billing_metrics.active_count }}</div>
      <div class="text-muted small">Aktivnih pretplatnika</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="stat-card text-center">
      <div class="h4 text-info">{{ billing_metrics.trialing_count }}</div>
      <div class="text-muted small">U trialu</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="stat-card text-center">
      <div class="h4 {% if billing_metrics.trial_ending_soon > 0 %}text-warning{% else %}text-muted{% endif %}">
        {{ billing_metrics.trial_ending_soon }}
      </div>
      <div class="text-muted small">Trial ističe za 3 dana</div>
    </div>
  </div>
</div>
```

---

## ZADATAK 6 — Admin

```python
# billing/admin.py
@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan', 'status', 'monthly_amount',
                    'trial_end', 'next_billing', 'days_until_trial_end']
    list_filter = ['status', 'plan']
    search_fields = ['company__name']
    readonly_fields = ['created_at', 'updated_at', 'arr']
    actions = ['activate_selected', 'cancel_selected', 'extend_trial_7d']

    def activate_selected(self, request, queryset):
        for sub in queryset:
            sub.activate()
        self.message_user(request, f'{queryset.count()} pretplata aktivirano.')

    def extend_trial_7d(self, request, queryset):
        from django.utils import timezone
        queryset.update(trial_end=timezone.now() + timezone.timedelta(days=7))
        self.message_user(request, f'Trial produžen za 7 dana.')
```

---

## DONE kriterij

- [ ] `CompanySubscription` model + migracija
- [ ] `billing/metrics.py` — `get_platform_metrics()` radi
- [ ] `admin_approve_registration()` kreira sub + start_trial() automatski
- [ ] `init_subscriptions` management command — backfill za 86 firmi
- [ ] Cockpit prikazuje MRR, aktivne, trial, uskoro ističe
- [ ] Admin: vidi, aktivira, otkazuje, produžuje trial
- [ ] Commit: "feat(billing): CompanySubscription — ARR tracking, trial management, cockpit metrics"
