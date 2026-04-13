from django.core.exceptions import ObjectDoesNotExist
"""
FENIX SessionGuard — "Zaključaj kancelariju prije izlaska"

Provjerava stanje sesije pri odlasku korisnika:
- POS smjena otvorena? → upozori i ponudi zatvaranje
- Timer aktivan? → upozori i ponudi zaustavljanje
- Nespremljeni obrasci? → upozori

Koristi se u:
1. Logout view — provjeri prije odjave
2. beforeunload JS event — upozori korisnika
3. Session timeout — auto-cleanup

API:
    from core.session_guard import SessionGuard
    warnings = SessionGuard.check(request)
    # [{'type': 'pos_open', 'msg': 'Smjena #3 je otvorena...', 'action_url': '/pos/...'}]
"""
from django.utils.translation import gettext as _
from django.db import IntegrityError, DatabaseError


class SessionGuard:
    """Check all "open lights" before user exits."""

    @classmethod
    def check(cls, request):
        """Return list of warnings about open resources."""
        warnings = []
        user = request.user

        if not user.is_authenticated:
            return warnings

        # 1. POS open sessions
        try:
            from pos.models import POSSession
            open_sessions = POSSession.objects.filter(
                operator=user, status='open'
            ).select_related('terminal')
            for s in open_sessions:
                warnings.append({
                    'type': 'pos_open',
                    'icon': 'fa-cash-register',
                    'level': 'warning',
                    'msg': _('POS smjena #{n} na {t} je još otvorena.').format(
                        n=s.session_number, t=s.terminal.name
                    ),
                    'hint': _('Zatvorite smjenu ili će ostati otvorena do sutra.'),
                    'action_url': f'/hr/pos/session/{s.pk}/close/',
                    'action_label': _('Zatvori smjenu'),
                })
        except DatabaseError:
            pass

        # 2. Active work timer
        try:
            from worktime.models import TimeEntry
            active_timer = TimeEntry.objects.filter(
                user=user, status__in=('RUNNING', 'PAUSED')
            ).first()
            if active_timer:
                warnings.append({
                    'type': 'timer_active',
                    'icon': 'fa-clock',
                    'level': 'warning',
                    'msg': _('Timer je aktivan: {p}').format(
                        p=active_timer.project.name if active_timer.project else 'Bez projekta'
                    ),
                    'hint': _('Zaustavite timer ili će nastaviti brojati.'),
                    'action_url': '/hr/worktime/timer/stop/',
                    'action_label': _('Zaustavi timer'),
                })
        except DatabaseError:
            pass

        # 3. Draft invoices (unsent)
        try:
            from invoicing.models import Invoice
            draft_count = Invoice.objects.filter(
                created_by=user, status='DRAFT'
            ).count()
            if draft_count > 0:
                warnings.append({
                    'type': 'draft_invoices',
                    'icon': 'fa-file-invoice',
                    'level': 'info',
                    'msg': _('Imate {n} neodaslanih računa u nacrtu.').format(n=draft_count),
                    'hint': _('Pošaljite ih ili ih ostavite za kasnije.'),
                    'action_url': '/hr/invoicing/?status=DRAFT',
                    'action_label': _('Pregledaj nacrte'),
                })
        except DatabaseError:
            pass

        return warnings

    @classmethod
    def check_and_warn(cls, request):
        """Check and add Django messages for any warnings."""
        from django.contrib import messages
        warnings = cls.check(request)
        for w in warnings:
            if w['level'] == 'warning':
                messages.warning(request, f"{w['msg']} · {w['hint']}")
            elif w['level'] == 'info':
                messages.info(request, f"{w['msg']}")
        return warnings
