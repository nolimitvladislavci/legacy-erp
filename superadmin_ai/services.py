"""
AI Permission Gate — centralna provjera za SVE AI operacije.

Uporaba iz bilo kojeg modula:
    from superadmin_ai.services import ai_gate

    # Provjeri smije li AI čitati inventory za ovu firmu
    result = ai_gate.check(company, 'inventory', 'read', user=request.user)
    if result.allowed:
        # radi...
    elif result.queued:
        # akcija je u redu čekanja za odobrenje
    else:
        # blokirano
"""
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import AIModulePermission, PendingAIAction, AIActionLog


class AIGateResult:
    __slots__ = ('allowed', 'queued', 'blocked', 'level', 'pending_action', 'message')

    def __init__(self, allowed=False, queued=False, blocked=False, level=0,
                 pending_action=None, message=''):
        self.allowed = allowed
        self.queued = queued
        self.blocked = blocked
        self.level = level
        self.pending_action = pending_action
        self.message = message


class AIGate:
    # Akcije koje se smatraju "read" operacijama
    READ_ACTIONS = {'read', 'list', 'get', 'query', 'search', 'count', 'stats', 'export'}

    def check(self, company, module, action_type, user=None, description='',
              payload=None, ip_address=None):
        """
        Centralna provjera AI pristupa.

        Returns: AIGateResult
        """
        level = AIModulePermission.get_level(company, module)

        # DISABLED — odmah blokiraj
        if level == AIModulePermission.ACCESS_DISABLED:
            self._log(company, module, action_type, level, 'blocked', user, ip_address)
            return AIGateResult(
                blocked=True, level=level,
                message=f'AI pristup modulu "{module}" je isključen.'
            )

        # READ_ONLY — samo čitanje
        if level == AIModulePermission.ACCESS_READ_ONLY:
            is_read = action_type.lower() in self.READ_ACTIONS
            if is_read:
                self._log(company, module, action_type, level, 'allowed', user, ip_address)
                return AIGateResult(
                    allowed=True, level=level,
                    message=f'AI čitanje modula "{module}" dopušteno.'
                )
            else:
                self._log(company, module, action_type, level, 'blocked', user, ip_address)
                return AIGateResult(
                    blocked=True, level=level,
                    message=f'AI može samo čitati modul "{module}". Akcija "{action_type}" blokirana.'
                )

        # ASSISTED — kreiraj pending action
        if level == AIModulePermission.ACCESS_ASSISTED:
            is_read = action_type.lower() in self.READ_ACTIONS
            if is_read:
                self._log(company, module, action_type, level, 'allowed', user, ip_address)
                return AIGateResult(
                    allowed=True, level=level,
                    message=f'AI čitanje dopušteno (assisted mode).'
                )
            pending = PendingAIAction.objects.create(
                company=company,
                module=module,
                action_type=action_type,
                description=description or f'AI želi izvršiti: {action_type} u {module}',
                payload=payload or {},
            )
            self._log(company, module, action_type, level, 'queued', user, ip_address,
                      details={'pending_action_id': str(pending.id)})
            return AIGateResult(
                queued=True, level=level, pending_action=pending,
                message=f'Akcija stavljena u red čekanja za odobrenje (ID: {pending.id}).'
            )

        # AUTONOMOUS — odmah dozvoli
        if level == AIModulePermission.ACCESS_AUTONOMOUS:
            self._log(company, module, action_type, level, 'allowed', user, ip_address)
            return AIGateResult(
                allowed=True, level=level,
                message=f'AI autonomni pristup modulu "{module}" — akcija "{action_type}" dozvoljena.'
            )

        # Fallback
        self._log(company, module, action_type, level, 'blocked', user, ip_address)
        return AIGateResult(blocked=True, level=level, message='Nepoznata razina pristupa.')

    def _log(self, company, module, action_type, level, outcome, user=None,
             ip_address=None, details=None):
        AIActionLog.objects.create(
            company=company,
            module=module,
            action_type=action_type,
            access_level=level,
            outcome=outcome,
            user=user,
            ip_address=ip_address,
            details=details or {},
        )


# Singleton
ai_gate = AIGate()
