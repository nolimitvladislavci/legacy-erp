# CC_TASK_FAZA1_ARMATURA — Logička armatura sustava
## Agent: Claude Code | Prioritet: P0 | Datum: 2026-03-28
## Procijenjeno: 4-5h posla | Blocker za sve ostale faze

---

## KONTEKST — PROČITAJ PRIJE KODIRANJA

Zlatni template za FSM je OVDJE (ne piši novi):
  `einvoice/models/as4_message.py:185` — transition_to() + AS4MessageEvent

LeadActivity (burza/models.py:79) već postoji — CardActivity mora biti superset koji
ga nasljeđuje/zamjenjuje via ContentType. NE dupliraj.

KRITIČNA INJEKCIJA — zatvori ODMAH:
  `work_orders/views.py:90`  → wo.status = request.POST.get('status', 'draft')
  `work_orders/views.py:182` → wo.status = request.POST.get('status', wo.status)

---

## TASK 1 — Nova app: borg_ops

Stvori novu Django app (ne u core/ — izbjegni circular imports):

```
python manage.py startapp borg_ops
```

Dodaj u INSTALLED_APPS (core/settings.py) i stvori:
  borg_ops/
    __init__.py
    apps.py
    mixins.py    ← FSMMixin (vidi Task 2)
    models.py    ← CardActivity + StatusTimestamp (vidi Task 3)
    tasks.py     ← SLA Celery task (vidi Task 4)
    migrations/

---

## TASK 2 — FSMMixin (borg_ops/mixins.py)

Ekstrakcija i nadogradnja AS4MessageEvent patterna:

```python
# borg_ops/mixins.py
from django.utils import timezone
import logging
logger = logging.getLogger('borg.fsm')

class FSMMixin:
    """
    Lightweight FSM za sve kartice sustava.
    Zlatni template: einvoice/models/as4_message.py:185
    
    Subclass mora definirati:
      STATUS_FIELD  = 'status'          # ime polja
      TRANSITIONS   = { 'OLD': ['ALLOWED1', 'ALLOWED2'] }
    
    Opcionalno override:
      _on_transition(old, new, user)    # custom logic (notifikacije, SLA reset)
    """
    STATUS_FIELD = 'status'
    TRANSITIONS  = {}   # prazan = sve blokirano osim samog statusa

    def can_transition_to(self, new_status):
        current = getattr(self, self.STATUS_FIELD)
        if current == new_status:
            return True   # idempotent
        return new_status in self.TRANSITIONS.get(current, [])

    def transition_to(self, new_status, user=None, note='', save=True):
        """
        Atomarna FSM tranzicija.
        Raises ValueError ako tranzicija nije dozvoljena.
        Returns CardActivity instance.
        """
        if not self.can_transition_to(new_status):
            current = getattr(self, self.STATUS_FIELD)
            allowed = self.TRANSITIONS.get(current, [])
            raise ValueError(
                f'FSM: {self.__class__.__name__} '
                f'{current!r} → {new_status!r} nije dozvoljeno. '
                f'Dozvoljeno: {allowed or ["(nema — terminal status)"]}'
            )
        old_status = getattr(self, self.STATUS_FIELD)
        setattr(self, self.STATUS_FIELD, new_status)
        if save:
            self._fsm_transition_active = True
            self.save(update_fields=[self.STATUS_FIELD])
            self._fsm_transition_active = False

        logger.info('FSM %s #%s: %s → %s (user=%s)',
                    self.__class__.__name__, self.pk, old_status, new_status,
                    getattr(user, 'username', None))

        # Audit trail
        activity = self._log_transition(old_status, new_status, user, note)

        # SLA timestamp
        self._update_sla_timestamp(old_status, new_status, user)

        # Custom hook
        self._on_transition(old_status, new_status, user)

        return activity

    def _log_transition(self, old_status, new_status, user, note):
        """Kreira CardActivity zapis."""
        from borg_ops.models import CardActivity
        from django.contrib.contenttypes.models import ContentType
        return CardActivity.objects.create(
            content_type=ContentType.objects.get_for_model(self),
            object_id=str(self.pk),
            action=f'status_change',
            old_value=old_status,
            new_value=new_status,
            note=note,
            user=user,
        )

    def _update_sla_timestamp(self, old_status, new_status, user):
        """Zatvori prethodni StatusTimestamp, otvori novi."""
        from borg_ops.models import StatusTimestamp
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self)
        obj_id = str(self.pk)
        now = timezone.now()

        # Zatvori prethodni
        StatusTimestamp.objects.filter(
            content_type=ct, object_id=obj_id,
            status=old_status, exited_at__isnull=True
        ).update(
            exited_at=now,
            duration_seconds=(now - timezone.now()).seconds  # approx
        )
        # Otvori novi
        StatusTimestamp.objects.create(
            content_type=ct, object_id=obj_id,
            status=new_status, user=user
        )

    def _on_transition(self, old_status, new_status, user=None):
        """Override u subclassu za notifikacije, WhatsApp, etc."""
        pass

    def save(self, *args, **kwargs):
        """
        Mina #3 guard (Gemini): detektira direktno mijenjanje statusa
        mimo transition_to() i blokira ga u produkciji.

        Zaobilaženje: wo.status = 'x'; wo.save() ← OVO SE DETEKTIRA
        Ispravno:     wo.transition_to('x', user=request.user)
        """
        if self.pk:
            try:
                db_obj = self.__class__.objects.get(pk=self.pk)
                db_status = getattr(db_obj, self.STATUS_FIELD)
                current = getattr(self, self.STATUS_FIELD)
                if db_status != current and not getattr(self, '_fsm_transition_active', False):
                    import logging
                    logging.getLogger('borg.fsm').error(
                        'DIREKTNA STATUS PROMJENA DETEKTIRANA: %s #%s %r → %r — '
                        'koristi transition_to() umjesto direktnog save()!',
                        self.__class__.__name__, self.pk, db_status, current
                    )
                    # U debug modu: raise — u produkciji: log + nastavi
                    from django.conf import settings
                    if settings.DEBUG:
                        raise RuntimeError(
                            f'FSM violation: koristite transition_to() za promjenu statusa '
                            f'na {self.__class__.__name__}. '
                            f'Direktno: {db_status!r} → {current!r}'
                        )
            except self.__class__.DoesNotExist:
                pass  # novi objekt — OK
        super().save(*args, **kwargs)

    @property
    def sla_seconds_in_current_status(self):
        """Koliko sekundi karta stoji u trenutnom statusu."""
        from borg_ops.models import StatusTimestamp
        from django.contrib.contenttypes.models import ContentType
        ts = StatusTimestamp.objects.filter(
            content_type=ContentType.objects.get_for_model(self),
            object_id=str(self.pk),
            status=getattr(self, self.STATUS_FIELD),
            exited_at__isnull=True,
        ).first()
        if ts:
            return int((timezone.now() - ts.entered_at).total_seconds())
        return 0

    @property
    def sla_minutes_in_current_status(self):
        return self.sla_seconds_in_current_status // 60
```

---

## TASK 3 — Modeli (borg_ops/models.py)

```python
# borg_ops/models.py
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
User = get_user_model()


class CardActivity(models.Model):
    """
    Generički audit trail za sve kartice (WorkOrder, Lead, Intervencija...).
    Nasljeđuje/zamjenjuje LeadActivity iz burza/models.py.
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                      related_name='card_activities')
    object_id    = models.CharField(max_length=50, db_index=True)
    user         = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='+')
    action       = models.CharField(max_length=200)
    old_value    = models.CharField(max_length=100, blank=True)
    new_value    = models.CharField(max_length=100, blank=True)
    note         = models.TextField(blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table  = 'card_activity'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['content_type', 'object_id', '-created_at']),
        ]

    def __str__(self):
        return f'{self.action}: {self.old_value} → {self.new_value}'


class StatusTimestamp(models.Model):
    """SLA timestamp — bilježi ulaz/izlaz iz svakog statusa."""
    content_type     = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id        = models.CharField(max_length=50, db_index=True)
    status           = models.CharField(max_length=30)
    entered_at       = models.DateTimeField(auto_now_add=True, db_index=True)
    exited_at        = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    user             = models.ForeignKey(User, null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name='+')

    class Meta:
        db_table = 'sla_status_timestamp'
        ordering = ['-entered_at']
        indexes  = [
            models.Index(fields=['content_type', 'object_id', 'status', 'exited_at']),
        ]
```

Migracija: `python manage.py makemigrations borg_ops && python manage.py migrate borg_ops`

---

## TASK 4 — Apply FSMMixin na WorkOrder (KRITIČNO)

`work_orders/models.py`:

```python
from borg_ops.mixins import FSMMixin

class WorkOrder(FSMMixin, models.Model):
    STATUS_FIELD = 'status'
    TRANSITIONS  = {
        'draft':       ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'cancelled', 'draft'],
        'completed':   ['invoiced', 'in_progress'],
        'invoiced':    [],   # terminal
        'cancelled':   ['draft'],
    }
    # ... ostatak modela nepromijenjen
```

`work_orders/views.py` — zatvori injekciju na linijama 90 i 182:

```python
# STARO (linija 90):
wo.status = request.POST.get('status', 'draft')

# NOVO:
new_status = request.POST.get('status', 'draft')
try:
    if new_status != wo.status:
        wo.transition_to(new_status, user=request.user, save=False)
except ValueError as e:
    messages.error(request, str(e))
    return redirect('work_orders:detail', pk=wo.pk)
```

Isti pattern na liniji 182.

---

## TASK 5 — Apply FSMMixin na ProjectLead (Burza)

`burza/models.py`:

```python
from borg_ops.mixins import FSMMixin

class ProjectLead(FSMMixin, models.Model):
    STATUS_FIELD = 'status'
    TRANSITIONS  = {
        'NOVI_UPIT':        ['INTERNA_PROCJENA', 'NA_BURZI'],
        'INTERNA_PROCJENA': ['NA_BURZI', 'NOVI_UPIT'],
        'NA_BURZI':         ['PREUZETO'],
        'PREUZETO':         ['RIJESENO', 'NA_BURZI'],
        'RIJESENO':         [],   # terminal
    }

    def _on_transition(self, old_status, new_status, user=None):
        """WhatsApp notifikacija kad PREUZETO → RIJESENO."""
        if new_status == 'RIJESENO':
            try:
                from core.whatsapp import send_whatsapp
                # notify company admin
                pass
            except Exception:
                pass
```

---

## TASK 6 — SLA Celery task (borg_ops/tasks.py)

```python
# borg_ops/tasks.py
from celery import shared_task
from django.utils import timezone
import logging
logger = logging.getLogger('borg.sla')

SLA_RULES = {
    # format: 'AppLabel.ModelName': { 'STATUS': max_minutes }
    'work_orders.WorkOrder': {
        'in_progress': 480,    # 8h → notify assigned
    },
    'burza.ProjectLead': {
        'NOVI_UPIT':        1440,   # 24h → notify Ivan
        'INTERNA_PROCJENA': 4320,   # 72h → auto na_burzu
        'NA_BURZI':         10080,  # 7d → notify Ivan
    },
}

@shared_task(name='borg_ops.check_sla')
def check_sla():
    """Celery beat: svakih 10 min — provjera SLA kršenja."""
    from borg_ops.models import StatusTimestamp
    from django.contrib.contenttypes.models import ContentType
    from django.apps import apps
    now = timezone.now()
    breaches = []

    for model_path, rules in SLA_RULES.items():
        app_label, model_name = model_path.split('.')
        try:
            Model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        ct = ContentType.objects.get_for_model(Model)

        for status, max_minutes in rules.items():
            cutoff = now - timezone.timedelta(minutes=max_minutes)
            overdue = StatusTimestamp.objects.filter(
                content_type=ct,
                status=status,
                exited_at__isnull=True,
                entered_at__lt=cutoff,
            )
            for ts in overdue:
                minutes_over = int((now - ts.entered_at).total_seconds() / 60)
                logger.warning('SLA BREACH: %s #%s u statusu %s već %d min (max %d)',
                               model_name, ts.object_id, status, minutes_over, max_minutes)
                breaches.append({
                    'model': model_name, 'pk': ts.object_id,
                    'status': status, 'minutes': minutes_over
                })
                # TODO Faza 3: WhatsApp alert + auto-eskalacija

    return {'checked': timezone.now().isoformat(), 'breaches': len(breaches)}
```

Dodaj u `core/celery.py` beat schedule:
```python
'check-sla': {
    'task': 'borg_ops.check_sla',
    'schedule': 600.0,   # 10 minuta
},
```

---

## TASK 7 — Template: card_timeline.html (reusable)

`templates/includes/card_timeline.html`:

```html
{% load tz %}
<div class="card-timeline">
  {% for act in activities %}
  <div class="ct-item">
    <div class="ct-dot {% if act.action == 'status_change' %}ct-status{% endif %}"></div>
    <div class="ct-body">
      <div class="ct-action">
        {% if act.action == 'status_change' %}
          <span class="ct-badge ct-old">{{ act.old_value }}</span>
          <i class="fas fa-arrow-right ct-arrow"></i>
          <span class="ct-badge ct-new">{{ act.new_value }}</span>
        {% else %}
          {{ act.action }}
        {% endif %}
      </div>
      <div class="ct-meta">
        {{ act.created_at|localtime|date:"d.m.Y H:i" }}
        {% if act.user %}· {{ act.user.get_full_name|default:act.user.username }}{% endif %}
        {% if act.note %}<br><small>{{ act.note }}</small>{% endif %}
      </div>
    </div>
  </div>
  {% empty %}
  <div class="ct-empty">Nema aktivnosti</div>
  {% endfor %}
</div>
```

Usage u bilo kojem template: `{% include "includes/card_timeline.html" with activities=card_activities %}`

Za dohvat aktivnosti u view:
```python
from borg_ops.models import CardActivity
from django.contrib.contenttypes.models import ContentType
activities = CardActivity.objects.filter(
    content_type=ContentType.objects.get_for_model(wo),
    object_id=str(wo.pk)
)
```

---

## TASK 8 — Validacija i testovi

Nakon implementacije, provjeri:

```bash
cd /var/www/fina-connect

# 1. Migracije
venv/bin/python manage.py migrate

# 2. Smoke test FSM
venv/bin/python manage.py shell -c "
from borg_ops.mixins import FSMMixin
from work_orders.models import WorkOrder
wo = WorkOrder.objects.first()
if wo:
    print('Status:', wo.status)
    print('Can → in_progress:', wo.can_transition_to('in_progress'))
    print('Can → invoiced:', wo.can_transition_to('invoiced'))
    try:
        wo.transition_to('invoiced')  # treba baciti ValueError
        print('ERROR: nije bacio grešku!')
    except ValueError as e:
        print('OK: FSM brani →', e)
"

# 3. System check
venv/bin/python manage.py check

# 4. Restart
systemctl restart gunicorn-fina celery-worker
```

---


## MINA #3 — save() bypass (Gemini detekcija, OBAVEZNO)

Netko može zaobići FSM direktno: `WorkOrder.objects.filter(pk=1).update(status='invoiced')`
ili čak `wo.status = 'invoiced'; wo.save()` — FSMMixin to ne hvata.

Override `save()` u FSMMixin:

```python
def save(self, *args, **kwargs):
    """Blokira direktnu promjenu statusa mimo transition_to()."""
    if self.pk:  # samo za postojeće objekte
        try:
            old = self.__class__.objects.only(self.STATUS_FIELD).get(pk=self.pk)
            old_status = getattr(old, self.STATUS_FIELD)
            new_status = getattr(self, self.STATUS_FIELD)
            if old_status != new_status:
                # Provjeri je li tranzicija dozvoljena
                if not self.can_transition_to(new_status):
                    raise ValueError(
                        f'FSM GUARD: Direktna promjena statusa blokirana.                         '{self.__class__.__name__}' {old_status!r} → {new_status!r}.                         Koristi transition_to()'
                    )
                # Dozvoljeno — logiraj kao da je transition_to pozvan
                # (update_fields=['status'] znači da smo već prošli kroz transition_to)
        except self.__class__.DoesNotExist:
            pass  # novi objekt
    super().save(*args, **kwargs)
```

**Iznimka:** `save(update_fields=['status'])` unutar `transition_to()` je OK jer
`transition_to()` već prošao validaciju. Da izbjegnemo beskonačnu petlju:

```python
def transition_to(self, new_status, user=None, note='', save=True):
    # ... validacija ...
    old_status = getattr(self, self.STATUS_FIELD)
    setattr(self, self.STATUS_FIELD, new_status)
    if save:
        # Direktno super().save() — bypass naš override intentionally
        super(FSMMixin, self).save(update_fields=[self.STATUS_FIELD])
    # ... log, SLA ...
```

---

## MINA #4 — CardActivity DB load (Gemini detekcija)

CardActivity može narasti brzo na 100+ firmi. Strategija od prvog dana:

1. **Indeksi** (već u planu — POTVRDI):
```python
class Meta:
    indexes = [
        models.Index(fields=['content_type', 'object_id', '-created_at']),
        models.Index(fields=['-created_at']),  # za admin i digest
    ]
```

2. **Particioniranje po starosti** — dodaj Celery task u card_ops/tasks.py:
```python
@shared_task(name='card_ops.archive_old_activity')
def archive_old_activity():
    """Svakog 1. u mjesecu: preseli aktivnosti starije od 90 dana u CardActivityArchive."""
    from django.utils import timezone
    cutoff = timezone.now() - timezone.timedelta(days=90)
    old = CardActivity.objects.filter(created_at__lt=cutoff)
    count = old.count()
    # Za sada samo log — arhivna tablica u v2
    logger.info('CardActivity: %d zapisa starijih od 90 dana', count)
    return count
```

3. **Limit u UI** — card_timeline.html uvijek `.order_by('-created_at')[:50]`
   Ne dohvaćaj sve — paginator ili limit.

---
## DEFINICIJA DONE

- [ ] borg_ops app postoji, migrirana
- [ ] FSMMixin.transition_to() baca ValueError za nedozvoljene tranzicije
- [ ] WorkOrder koristi FSMMixin, injekcija na liniji 90 i 182 zatvorena
- [ ] ProjectLead koristi FSMMixin
- [ ] CardActivity loggira svaku tranziciju
- [ ] StatusTimestamp otvara/zatvara po tranziciji
- [ ] SLA Celery task registriran (beat schedule + 10 min)
- [ ] card_timeline.html uključen na WorkOrder detail i Lead detail
- [ ] save() guard loggira direktne promjene (RuntimeError u DEBUG modu)
- [ ] manage.py check bez grešaka
- [ ] Gunicorn + celery active

## NAPOMENA ZA CC CODE

Faza 2 (HTMX + Drag&Drop) kreće tek kad je Faza 1 DONE i potvrđena.
Ne diraj: einvoice/models/, core/urls.py, FenixScan modul.
Svaki task commitat zasebno s jasnom porukom.
