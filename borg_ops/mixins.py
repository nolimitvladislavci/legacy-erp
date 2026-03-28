"""
BORG FSM Mixin — Lightweight Finite State Machine za kartice.

v2: Nadogradnja po Gemini analizi 2026-03-28
  - __init__ pattern: _original_status pamti status pri instanciranju
  - save() guard bez extra DB SELECT (uspoređuje s _original_status)
  - .update() konvencija dokumentirana (nema tehničkog blocka — konvencija)
  - Compound indeksi u CardActivity i StatusTimestamp (CC Code original)

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
from django.utils import timezone

logger = logging.getLogger('borg.fsm')


class FSMMixin:
    STATUS_FIELD = 'status'
    TRANSITIONS  = {}

    # ── __init__: pamti originalni status pri instanciranju ─────────
    # Gemini pattern: eliminira extra DB SELECT u save() guardu
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pamtimo status koji dolazi iz baze (ili default za novi obj)
        self._original_status = getattr(self, self.STATUS_FIELD, None)
        # Flag koji transition_to() postavlja na True prije save()
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
        Atomarna FSM tranzicija s audit trailom i SLA trackingom.
        Raises ValueError ako tranzicija nije dozvoljena.
        Returns CardActivity instance ili None.
        """
        current = getattr(self, self.STATUS_FIELD)
        if current == new_status:
            return None   # idempotent

        if not self.can_transition_to(new_status):
            allowed = self.TRANSITIONS.get(current, [])
            raise ValueError(
                f'FSM: {self.__class__.__name__} '
                f'{current!r} \u2192 {new_status!r} nije dozvoljeno. '
                f'Dozvoljeno iz \'{current}\': {allowed or ["(terminal — nema dozvoljenih)"]}'
            )

        old_status = current
        setattr(self, self.STATUS_FIELD, new_status)

        # Ažuriramo _original_status uvijek — i kad save=True i kad save=False
        # Bitno: mora biti PRIJE super().save() da guard ne puca
        self._original_status = new_status

        if save:
            self._fsm_transition_active = True
            try:
                super(FSMMixin, self).save(update_fields=[self.STATUS_FIELD])
            finally:
                self._fsm_transition_active = False

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

    # ── save() guard — Gemini pattern, bez extra DB SELECT ──────────
    def save(self, *args, **kwargs):
        """
        Guard koji detektira direktno mijenjanje statusa mimo transition_to().

        Koristi _original_status (pamćen u __init__) umjesto extra DB SELECT.
        Ne može blokirati .update() — za to postoji konvencija u docstringu.

        DEBUG=True  → RuntimeError (glasno puca, odmah vidiš)
        DEBUG=False → logger.error (produkcija, ne rušimo server)
        """
        if (
            self.pk
            and not self._fsm_transition_active
            and self._original_status is not None
        ):
            update_fields = kwargs.get('update_fields')

            # Ako update_fields ne sadrži STATUS_FIELD — status se ne mijenja, OK
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
                # Produkcija: revert na originalni status i nastavi
                setattr(self, self.STATUS_FIELD, self._original_status)

        super().save(*args, **kwargs)

        # Nakon prvog INSERT (novi objekt), postavi _original_status
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
            )
        except Exception as e:
            logger.error('CardActivity create failed: %s', e)
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
        except Exception as e:
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
        except Exception:
            pass
        return 0

    @property
    def sla_minutes_in_current_status(self):
        return self.sla_seconds_in_current_status // 60
