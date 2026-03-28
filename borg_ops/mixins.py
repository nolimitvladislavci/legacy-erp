"""
BORG FSM Mixin — Lightweight Finite State Machine za kartice.

Zlatni template: einvoice/models/as4_message.py:185
Nadograđeno: audit trail (CardActivity), SLA (StatusTimestamp), save() guard.

Subclass mora definirati:
    STATUS_FIELD  = 'status'
    TRANSITIONS   = { 'OLD': ['ALLOWED1', 'ALLOWED2'] }
"""
import logging
from django.utils import timezone

logger = logging.getLogger('borg.fsm')


class FSMMixin:
    STATUS_FIELD = 'status'
    TRANSITIONS = {}

    def can_transition_to(self, new_status):
        """Provjeri je li tranzicija dozvoljena."""
        current = getattr(self, self.STATUS_FIELD)
        if current == new_status:
            return True  # idempotent
        return new_status in self.TRANSITIONS.get(current, [])

    def get_allowed_transitions(self):
        """Vrati listu dozvoljenih sljedećih statusa."""
        current = getattr(self, self.STATUS_FIELD)
        return list(self.TRANSITIONS.get(current, []))

    def transition_to(self, new_status, user=None, note='', save=True):
        """
        Atomarna FSM tranzicija s audit trailom i SLA trackingom.

        Raises ValueError ako tranzicija nije dozvoljena.
        Returns CardActivity instance.
        """
        current = getattr(self, self.STATUS_FIELD)
        if current == new_status:
            return None  # idempotent

        if not self.can_transition_to(new_status):
            allowed = self.TRANSITIONS.get(current, [])
            raise ValueError(
                f'FSM: {self.__class__.__name__} '
                f'{current!r} \u2192 {new_status!r} nije dozvoljeno. '
                f'Dozvoljeno: {allowed or ["(terminal status)"]}'
            )

        old_status = current
        setattr(self, self.STATUS_FIELD, new_status)

        if save:
            self._fsm_transition_active = True
            try:
                super(FSMMixin, self).save(update_fields=[self.STATUS_FIELD])
            finally:
                self._fsm_transition_active = False

        logger.info(
            'FSM %s #%s: %s \u2192 %s (user=%s)',
            self.__class__.__name__, self.pk, old_status, new_status,
            getattr(user, 'username', None)
        )

        # Audit trail
        activity = self._log_transition(old_status, new_status, user, note)

        # SLA timestamp
        self._update_sla_timestamp(old_status, new_status, user)

        # Custom hook za subclass
        self._on_transition(old_status, new_status, user)

        return activity

    def _log_transition(self, old_status, new_status, user, note):
        """Kreira CardActivity zapis."""
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

    def _update_sla_timestamp(self, old_status, new_status, user):
        """Zatvori prethodni StatusTimestamp, otvori novi."""
        try:
            from borg_ops.models import StatusTimestamp
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get_for_model(self)
            obj_id = str(self.pk)
            now = timezone.now()

            # Zatvori prethodni
            prev = StatusTimestamp.objects.filter(
                content_type=ct, object_id=obj_id,
                status=old_status, exited_at__isnull=True
            ).first()
            if prev:
                prev.exited_at = now
                prev.duration_seconds = int((now - prev.entered_at).total_seconds())
                prev.save(update_fields=['exited_at', 'duration_seconds'])

            # Otvori novi
            StatusTimestamp.objects.create(
                content_type=ct, object_id=obj_id,
                status=new_status, user=user
            )
        except Exception as e:
            logger.error('SLA timestamp update failed: %s', e)

    def _on_transition(self, old_status, new_status, user=None):
        """Override u subclassu za notifikacije, WhatsApp, etc."""
        pass

    def save(self, *args, **kwargs):
        """
        Guard: detektira direktno mijenjanje statusa mimo transition_to().
        DEBUG mode: baca RuntimeError. Produkcija: logira upozorenje.
        """
        if self.pk and not getattr(self, '_fsm_transition_active', False):
            update_fields = kwargs.get('update_fields')
            # Ako je explicit update_fields i status NIJE unutra, preskoči check
            if update_fields and self.STATUS_FIELD not in update_fields:
                super().save(*args, **kwargs)
                return
            try:
                db_obj = self.__class__.objects.only(self.STATUS_FIELD).get(pk=self.pk)
                db_status = getattr(db_obj, self.STATUS_FIELD)
                current = getattr(self, self.STATUS_FIELD)
                if db_status != current:
                    logger.error(
                        'DIREKTNA STATUS PROMJENA: %s #%s %r \u2192 %r — '
                        'koristi transition_to()!',
                        self.__class__.__name__, self.pk, db_status, current
                    )
                    from django.conf import settings
                    if settings.DEBUG:
                        raise RuntimeError(
                            f'FSM violation: koristite transition_to() za '
                            f'{self.__class__.__name__}. '
                            f'Direktno: {db_status!r} \u2192 {current!r}'
                        )
            except self.__class__.DoesNotExist:
                pass  # novi objekt
        super().save(*args, **kwargs)

    @property
    def sla_seconds_in_current_status(self):
        """Koliko sekundi karta stoji u trenutnom statusu."""
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
