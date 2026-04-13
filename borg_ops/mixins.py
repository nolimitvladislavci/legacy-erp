"""
BORG FSM Mixin — Lightweight Finite State Machine za kartice.

v3: Race condition fix (Dron #2) — select_for_update() u transition_to()
  - __init__ pattern: _original_status pamti status pri instanciranju
  - save() guard bez extra DB SELECT (uspoređuje s _original_status)
  - .update() konvencija dokumentirana (nema tehničkog blocka — konvencija)
  - Compound indeksi u CardActivity i StatusTimestamp (CC Code original)
  - transition_to() koristi select_for_update() za row-level lock

Zlatni template: einvoice/models/as4_message.py:185

Subclass mora definirati:
    STATUS_FIELD  = 'status'          (default)
    TRANSITIONS   = { 'OLD': ['ALLOWED1', 'ALLOWED2'] }

KONVENCIJA — OBVEZNO:
    ZABRANJENO: Model.objects.filter(...).update(status='X')
    DOZVOLJENO: instance.transition_to('X', user=user)
    Razlog: .update() zaobilazi FSM, save(), audit trail i SLA tracking.
    Custom Manager koji blokira .update(status=...) nije implementiran
    zbog overhead-a — konvencija je dovoljna za mali tim.
"""
import logging
from django.db import transaction
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('borg.fsm')


class FSMMixin:
    STATUS_FIELD = 'status'
    TRANSITIONS  = {}

    # ── __init__: pamti originalni status pri instanciranju ─────────
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = getattr(self, self.STATUS_FIELD, None)
        self._fsm_transition_active = False

    # ── Provjere ────────────────────────────────────────────────────
    def can_transition_to(self, new_status):
        current = getattr(self, self.STATUS_FIELD)
        if current == new_status:
            return True   # idempotent
        return new_status in self.TRANSITIONS.get(current, [])

    def get_allowed_transitions(self):
        current = getattr(self, self.STATUS_FIELD)
        return list(self.TRANSITIONS.get(current, []))

    # ── Jedina legalna metoda za promjenu statusa ────────────────────
    def transition_to(self, new_status, user=None, note='', save=True):
        """
        Atomarna FSM tranzicija s audit trailom, SLA trackingom i
        row-level lockingom (select_for_update).

        Race condition zaštita: ako dva korisnika simultano pokušaju
        pomaknut istu karticu, prvi dobiva lock, drugi čeka.
        Kad drugi pročita svježi status iz baze, tranzicija može biti
        odbačena ako je kartica već u drugom stanju.

        Raises ValueError ako tranzicija nije dozvoljena.
        Returns CardActivity instance ili None.
        """
        with transaction.atomic():
            # Row-level lock — drugi request čeka dok prvi ne završi
            if self.pk:
                fresh = (
                    self.__class__.objects
                    .select_for_update()
                    .get(pk=self.pk)
                )
                # Osvježi in-memory status iz baze (možda ga je netko drugi promijenio)
                fresh_status = getattr(fresh, self.STATUS_FIELD)
                current_status = getattr(self, self.STATUS_FIELD)
                if fresh_status != current_status:
                    # Netko je promijenio status dok smo mi čekali lock
                    setattr(self, self.STATUS_FIELD, fresh_status)
                    self._original_status = fresh_status

                current = fresh_status
            else:
                current = getattr(self, self.STATUS_FIELD)

            if current == new_status:
                return None   # idempotent

            if new_status not in self.TRANSITIONS.get(current, []):
                allowed = self.TRANSITIONS.get(current, [])
                raise ValueError(
                    f'FSM: {self.__class__.__name__} '
                    f'{current!r} \u2192 {new_status!r} nije dozvoljeno. '
                    f'Dozvoljeno iz \'{current}\': {allowed or ["(terminal)"]}'
                )

            old_status = current
            setattr(self, self.STATUS_FIELD, new_status)
            self._original_status = new_status

            if save:
                self._fsm_transition_active = True
                try:
                    super(FSMMixin, self).save(update_fields=[self.STATUS_FIELD])
                finally:
                    self._fsm_transition_active = False

        # Izvan transaction.atomic() — lock otpušten, ostale operacije
        logger.info(
            'FSM %s #%s: %s \u2192 %s (user=%s)',
            self.__class__.__name__, self.pk,
            old_status, new_status,
            getattr(user, 'username', None)
        )

        activity = self._log_transition(old_status, new_status, user, note)
        self._update_sla_timestamp(old_status, new_status, user)
        self._on_transition(old_status, new_status, user)

        return activity

    # ── save() guard — bez extra DB SELECT ──────────────────────────
    def save(self, *args, **kwargs):
        """
        Guard koji detektira direktno mijenjanje statusa mimo transition_to().
        DEBUG=True  → RuntimeError
        DEBUG=False → logger.error + revert
        """
        if (
            self.pk
            and not self._fsm_transition_active
            and self._original_status is not None
        ):
            update_fields = kwargs.get('update_fields')

            if update_fields and self.STATUS_FIELD not in update_fields:
                super().save(*args, **kwargs)
                return

            current = getattr(self, self.STATUS_FIELD, None)
            if current != self._original_status:
                msg = (
                    f'FSM VIOLATION: {self.__class__.__name__} #{self.pk} '
                    f'status promijenjen direktno: '
                    f'{self._original_status!r} \u2192 {current!r}. '
                    f'Koristi transition_to()!'
                )
                logger.error(msg)
                from django.conf import settings
                if settings.DEBUG:
                    raise RuntimeError(msg)
                setattr(self, self.STATUS_FIELD, self._original_status)

        super().save(*args, **kwargs)

        if self._original_status is None:
            self._original_status = getattr(self, self.STATUS_FIELD, None)

    # ── Audit trail ──────────────────────────────────────────────────
    def _log_transition(self, old_status, new_status, user, note):
        try:
            from borg_ops.models import CardActivity
            from django.contrib.contenttypes.models import ContentType
            return CardActivity.objects.create(
                content_type=ContentType.objects.get_for_model(self),
                object_id=str(self.pk),
                action='status_change',
                old_value=old_status,
                new_value=new_status,
                note=note,
                user=user,
                is_system_generated=True,
                is_public_facing=False,  # Default: interni. Eksplicitno markirati javne.
            )
        except (IntegrityError, DatabaseError) as e:
            logger.error('CardActivity create failed: %s', e)
            return None

    # ── Javni milestone log ─────────────────────────────────────────
    def _log_public_event(self, message, user=None):
        """
        Kreira CardActivity zapis koji JE javan.
        SAMO sustav smije zvati ovu metodu — NE korisnici direktno.
        Koristi za: "Berba završena", "QC: Prošao", "Pakiranje završeno"
        """
        try:
            from borg_ops.models import CardActivity
            from django.contrib.contenttypes.models import ContentType
            return CardActivity.objects.create(
                content_type=ContentType.objects.get_for_model(self),
                object_id=str(self.pk),
                action='public_milestone',
                old_value='',
                new_value=message,
                note='',
                user=user,
                is_system_generated=True,
                is_public_facing=True,
            )
        except (IntegrityError, DatabaseError) as e:
            logger.error('Public CardActivity create failed: %s', e)
            return None

        # ── SLA timestamps ───────────────────────────────────────────────
    def _update_sla_timestamp(self, old_status, new_status, user):
        try:
            from borg_ops.models import StatusTimestamp
            from django.contrib.contenttypes.models import ContentType
            ct     = ContentType.objects.get_for_model(self)
            obj_id = str(self.pk)
            now    = timezone.now()

            prev = StatusTimestamp.objects.filter(
                content_type=ct, object_id=obj_id,
                status=old_status, exited_at__isnull=True
            ).first()
            if prev:
                prev.exited_at        = now
                prev.duration_seconds = int((now - prev.entered_at).total_seconds())
                prev.save(update_fields=['exited_at', 'duration_seconds'])

            StatusTimestamp.objects.create(
                content_type=ct, object_id=obj_id,
                status=new_status, user=user
            )
        except (ValueError, TypeError) as e:
            logger.error('SLA timestamp update failed: %s', e)

    # ── Custom hook za subclass ──────────────────────────────────────
    def _on_transition(self, old_status, new_status, user=None):
        """Override za WhatsApp, notifikacije, email, etc."""
        pass

    # ── SLA properties ───────────────────────────────────────────────
    @property
    def sla_seconds_in_current_status(self):
        try:
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
        except (ValueError, TypeError):
            pass
        return 0

    @property
    def sla_minutes_in_current_status(self):
        return self.sla_seconds_in_current_status // 60
