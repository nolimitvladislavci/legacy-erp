# CC_TASK_FAL_FENIX_ACCESS_LAYER.md
# Dodijeljen: CC Code
# Prioritet: VISOKO — arhitekturalni zadatak, nema produkcijskog roka ali blokira sigurnost
# Procjena: 3-5 dana (4 faze, svaka nezavisna)
# Autori plana: Sonnet + Gemini (zajednička analiza)
# Datum: 2026-03-30
#
# KONTEKST:
# Sustav ima 5 odvojenih sigurnosnih silosa koji se ne razumiju:
#   1. Django auth     → is_superuser, is_staff, has_perm()
#   2. UserProfile     → role string ('superadmin', 'company_admin'...)
#   3. permissions/    → RBAC modeli (Permission, Role, UserRole) — PRAZNI U BAZI (0 redaka)
#   4. CompanyMembership → user↔company veza s role stringom
#   5. AI ovlasti      → Gemini/CC/Haiku pišu u DB bez ijedne provjere
#
# SIMPTOMI KOJI SU VIDLJIVI:
#   - Force2FA i ForceTCMiddleware blokiraju rute zbog path string matchinga
#     (/2fa/ ne matchira /hr/2fa/ → loop)
#   - ForceTCMiddleware blokirao /no-limit/ jer NO LIMIT firma nije imala TC consent
#   - permissions/manager.py: tenant_admin i company_admin dobivaju SVA prava (linija 20)
#     → RBAC granularnost je mrtva
#   - 1848 mjesta u kodu koriste @login_required, is_superuser, is_staff provjere
#     → nema centralnog zapisa zašto je nešto dopušteno ili odbijeno
#   - AI agenti: mcp_server.py ima exec_command/write_file/query_db BEZ token scopea
#
# GEMINIJEVI DOPRINOSI (asimilirani):
#   ✓ resolver_match.view_name umjesto request.path za middleware whitelistove
#   ✓ Default Deny evaluacijski stack (superuser → blacklist → RBAC → overrides)
#   ✓ AI Scoped Token arhitektura za AI agente
#   ✗ NIJE asimilirano: spajanje Force2FA + ForceTC u jedan middleware (preuranjeno)
#
# FILOZOFIJA:
#   "Jedan ulaz. Jedna istina. Svaka odluka se može objasniti u jednoj rečenici."

---

## FAZA 1 — RouteRegistry + Middleware refaktor (Dan 1)
### Cilj: eliminirati sve string path provjere u middlewareu

### 1a. Kreiraj permissions/route_registry.py

```python
# permissions/route_registry.py
"""
RouteRegistry — centralni registar pristupnih razina za sve URL rute.

KLJUČNA IDEJA (Gemini): koristiti view_name umjesto request.path
View name je language-agnostic — /hr/2fa/setup/ i /en/2fa/setup/ 
obje resolveaju u view_name='setup_2fa'. Jedan entry umjesto N.

Razine pristupa:
  PUBLIC        — bez loginа, bez company (javne stranice, brošure)
  AUTHENTICATED — treba login, ne treba specifičnu company
  COMPANY       — treba login + aktivan company membership
  ADMIN         — treba company_admin ili superadmin
  SUPERADMIN    — samo ivan_brtan/superuser
  AI_READONLY   — AI agent, samo čitanje
  AI_WRITE      — AI agent, ograničeno pisanje s tokom odobrenja
"""
from enum import Enum, auto
from typing import Optional
import logging

logger = logging.getLogger('fal.route_registry')

class AccessLevel(Enum):
    PUBLIC = auto()
    AUTHENTICATED = auto()
    COMPANY = auto()
    ADMIN = auto()
    SUPERADMIN = auto()

# ─────────────────────────────────────────────────────────────
# REGISTAR RUTA
# Format: 'view_name': AccessLevel
# Svaka nova javna ruta mora biti ovdje navedena.
# Default za neregistrirane rute: COMPANY (konzervativno)
# ─────────────────────────────────────────────────────────────
ROUTE_REGISTRY: dict[str, AccessLevel] = {
    # ── POTPUNO JAVNE ──────────────────────────────────────────
    'home':                        AccessLevel.PUBLIC,
    'home_root':                   AccessLevel.PUBLIC,
    'login':                       AccessLevel.PUBLIC,
    'login_root':                  AccessLevel.PUBLIC,
    'login_fallback':              AccessLevel.PUBLIC,
    'logout':                      AccessLevel.PUBLIC,
    'register':                    AccessLevel.PUBLIC,
    'health_check':                AccessLevel.PUBLIC,
    'brochure_croxmlverify':       AccessLevel.PUBLIC,
    'no_limit_web':                AccessLevel.PUBLIC,
    'brochure_golubar':            AccessLevel.PUBLIC,
    'brochure_golubar_i18n':       AccessLevel.PUBLIC,
    'pricing':                     AccessLevel.PUBLIC,
    'about':                       AccessLevel.PUBLIC,
    'impressum':                   AccessLevel.PUBLIC,
    'datenschutz':                 AccessLevel.PUBLIC,
    'privatnost':                  AccessLevel.PUBLIC,
    'tippgeber_vertrag':           AccessLevel.PUBLIC,
    'opci_uvjeti':                 AccessLevel.PUBLIC,
    'dpa':                         AccessLevel.PUBLIC,
    'digitalni_posrednik':         AccessLevel.PUBLIC,
    'partner_signup':              AccessLevel.PUBLIC,
    'robot_pekara':                AccessLevel.PUBLIC,
    'de_landing':                  AccessLevel.PUBLIC,
    'de_pakete':                   AccessLevel.PUBLIC,
    'de_anleitung':                AccessLevel.PUBLIC,
    'newsletter':                  AccessLevel.PUBLIC,
    'newsletter_de':               AccessLevel.PUBLIC,
    'promo_hr':                    AccessLevel.PUBLIC,
    'promo_de':                    AccessLevel.PUBLIC,
    'sw_js':                       AccessLevel.PUBLIC,
    'manifest_json':               AccessLevel.PUBLIC,
    'offline_html':                AccessLevel.PUBLIC,
    'receipt_public_short':        AccessLevel.PUBLIC,
    'receipt_public_noslash':      AccessLevel.PUBLIC,
    'public_sos':                  AccessLevel.PUBLIC,
    'library_public_home':         AccessLevel.PUBLIC,
    'library_public_search':       AccessLevel.PUBLIC,
    'library_public_book':         AccessLevel.PUBLIC,
    'library_public_reserve':      AccessLevel.PUBLIC,
    'validator':                   AccessLevel.PUBLIC,
    'whatsapp_webhook':            AccessLevel.PUBLIC,  # WAHA webhook
    'inbound_webhook_direct':      AccessLevel.PUBLIC,
    'fenix_scan':                  AccessLevel.PUBLIC,
    'device_token_auto_login':     AccessLevel.PUBLIC,
    'device_token_login_api':      AccessLevel.PUBLIC,
    'inspection_dashboard':        AccessLevel.PUBLIC,
    'tc_consent':                  AccessLevel.PUBLIC,  # mora biti dostupno bez TC
    'tc_accept_view':              AccessLevel.PUBLIC,
    'password_reset':              AccessLevel.PUBLIC,
    'password_reset_done':         AccessLevel.PUBLIC,
    'password_reset_confirm':      AccessLevel.PUBLIC,
    'password_reset_complete':     AccessLevel.PUBLIC,
    'verify_email':                AccessLevel.PUBLIC,
    'resend_verification':         AccessLevel.PUBLIC,

    # ── TREBA LOGIN (ne nužno company) ──────────────────────────
    'setup_2fa':                   AccessLevel.AUTHENTICATED,
    'verify_2fa':                  AccessLevel.AUTHENTICATED,
    'gdpr_export':                 AccessLevel.AUTHENTICATED,
    'gdpr_delete':                 AccessLevel.AUTHENTICATED,
    'gdpr_dashboard':              AccessLevel.AUTHENTICATED,
    'device_token_manage':         AccessLevel.AUTHENTICATED,
    'logout_view':                 AccessLevel.AUTHENTICATED,

    # ── SUPERADMIN ONLY ────────────────────────────────────────
    'superadmin_dashboard':        AccessLevel.SUPERADMIN,
    'control_tower':               AccessLevel.SUPERADMIN,
    'cross_company_dashboard':     AccessLevel.SUPERADMIN,
    'ivan_cockpit':                AccessLevel.SUPERADMIN,
    'superadmin_companies':        AccessLevel.SUPERADMIN,
    'superadmin_users':            AccessLevel.SUPERADMIN,
    'start_impersonation':         AccessLevel.SUPERADMIN,
    'stop_impersonation':          AccessLevel.SUPERADMIN,

    # Sve ostalo → default COMPANY (konzervativno)
}


class RouteRegistry:
    """
    Single source of truth za pristupne razine ruta.
    
    Koristi view_name umjesto path string matchinga.
    Rješava i18n problem: /hr/2fa/ i /en/2fa/ oba resolveaju u 'setup_2fa'.
    """
    DEFAULT_LEVEL = AccessLevel.COMPANY  # konzervativni default

    @classmethod
    def get_access_level(cls, request) -> AccessLevel:
        """Odredi pristupnu razinu za trenutni request."""
        # Static, media, admin — uvijek propusti (Django ih ne route kroz custom middleware)
        path = request.path
        for prefix in ('/static/', '/media/', '/admin/', '/__debug__/', '/favicon'):
            if path.startswith(prefix):
                return AccessLevel.PUBLIC

        # Pokušaj resolver_match (može failati kod 404)
        resolver_match = getattr(request, 'resolver_match', None)
        if resolver_match is None:
            # URL nije resolveao — propusti Django da vrati 404
            return AccessLevel.PUBLIC

        view_name = resolver_match.url_name or ''
        namespace = resolver_match.namespace or ''
        
        # Full view name s namespace-om (npr. 'udruge:golubar_dashboard')
        full_name = f"{namespace}:{view_name}" if namespace else view_name

        # Provjeri puno ime pa kratko
        level = ROUTE_REGISTRY.get(full_name) or ROUTE_REGISTRY.get(view_name)
        
        if level is None:
            logger.debug(f"RouteRegistry MISS: {full_name} → default {cls.DEFAULT_LEVEL}")
            return cls.DEFAULT_LEVEL

        return level

    @classmethod
    def is_public(cls, request) -> bool:
        return cls.get_access_level(request) == AccessLevel.PUBLIC

    @classmethod  
    def requires_auth(cls, request) -> bool:
        return cls.get_access_level(request) != AccessLevel.PUBLIC

    @classmethod
    def requires_company(cls, request) -> bool:
        level = cls.get_access_level(request)
        return level in (AccessLevel.COMPANY, AccessLevel.ADMIN, AccessLevel.SUPERADMIN)
```

### 1b. Refaktoriraj Force2FAMiddleware koristeći RouteRegistry

```python
# U core/middleware/__init__.py — ZAMIJENI Force2FAMiddleware

class Force2FAMiddleware:
    """
    Blokira admin korisnike bez aktiviranog 2FA.
    Koristi RouteRegistry.is_public() umjesto path string matchinga.
    """
    ENFORCED_ROLES = ('superadmin', 'company_admin', 'tenant_admin')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from permissions.route_registry import RouteRegistry

        # Javne rute i nelogirani → propusti
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return self.get_response(request)

        if RouteRegistry.is_public(request):
            return self.get_response(request)

        # 2FA setup/verify rute → uvijek propusti (bez obzira na view name)
        view_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')
        if view_name in ('setup_2fa', 'verify_2fa', 'pending_2fa'):
            return self.get_response(request)

        # Provjeri ulogu i 2FA status
        try:
            profile = request.user.profile
        except Exception:
            return self.get_response(request)

        if profile.role not in self.ENFORCED_ROLES and not request.user.is_superuser:
            return self.get_response(request)

        if profile.totp_enabled:
            return self.get_response(request)

        # Blokada
        from django.shortcuts import redirect
        return redirect('setup_2fa')
```

### 1c. Refaktoriraj ForceTCMiddleware

```python
class ForceTCMiddleware:
    """
    T&C consent provjera. 
    Koristi RouteRegistry umjesto path string matchinga.
    """
    TC_CURRENT_VERSION = 'v1.0-2026'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from permissions.route_registry import RouteRegistry, AccessLevel

        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return self.get_response(request)

        # Javne i authenticated rute → ne trebaju TC
        level = RouteRegistry.get_access_level(request)
        if level in (AccessLevel.PUBLIC, AccessLevel.AUTHENTICATED):
            return self.get_response(request)

        if request.user.is_superuser:
            return self.get_response(request)

        company = getattr(request, 'current_company', None)
        if not company:
            try:
                company = request.user.profile.company
            except Exception:
                return self.get_response(request)

        if not company:
            return self.get_response(request)

        if company.has_signed_tc_consent and company.tc_consent_version == self.TC_CURRENT_VERSION:
            return self.get_response(request)

        from django.shortcuts import redirect
        return redirect('tc_consent')
```

### 1d. Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from permissions.route_registry import RouteRegistry, AccessLevel
from django.test import RequestFactory

rf = RequestFactory()

# Simuliraj requests s resolver_match
from django.urls import resolve

test_paths = [
    '/no-limit/',
    '/hr/login/',
    '/hr/2fa/setup/',
    '/hr/dashboard/',
    '/hr/documents/arhiva/',
    '/health/',
]

for path in test_paths:
    try:
        req = rf.get(path)
        req.resolver_match = resolve(path.replace('/hr/', '/hr/', 1))
        level = RouteRegistry.get_access_level(req)
        print(f'{path:35s} → {level.name}')
    except Exception as e:
        print(f'{path:35s} → ERROR: {e}')
"
```

---

## FAZA 2 — PermissionEngine s Default Deny (Dan 2)
### Cilj: zamjeniti string role bypass s determinističkim evaluatorom

### 2a. Kreiraj permissions/engine.py

```python
# permissions/engine.py
"""
PermissionEngine — jedini evaluator pristupa u sustavu.

REDOSLIJED EVALUACIJE (Default Deny, Gemini suggestion):
  1. is_superuser          → GRANT (master bypass, samo za vas)
  2. user.is_active=False  → DENY (suspendiran korisnik)
  3. Company blacklist     → DENY (firma deaktivirana/blokirana)
  4. UserProfile.role      → GRANT/CHECK (brzi path za poznate uloge)
  5. CompanyMembership     → GRANT/CHECK (korisnik u firmi?)
  6. RBAC Roles            → GRANT (ako ima UserRole s ovlastima)
  7. PermissionOverride    → može GRANT ili REVOKE
  8. Default               → DENY

Svaki DENY logira se u AccessAuditLog s razlogom.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('fal.engine')


@dataclass
class AccessDecision:
    """Rezultat evaluacije pristupa. Uvijek sadrži objašnjenje."""
    granted: bool
    reason: str
    evaluator: str  # koji korak evaluacije je donio odluku
    user_id: Optional[int] = None
    company_id: Optional[str] = None
    permission: Optional[str] = None
    
    def __bool__(self):
        return self.granted
    
    def log(self):
        status = "GRANT" if self.granted else "DENY"
        logger.info(
            f"{status} | user={self.user_id} | company={self.company_id} | "
            f"perm={self.permission} | evaluator={self.evaluator} | reason={self.reason}"
        )


class PermissionEngine:
    """
    Centralni evaluator pristupa. Singleton pattern.
    
    Koristi:
        engine = PermissionEngine()
        decision = engine.evaluate(user, permission='invoices.create', company=company)
        if not decision:
            return HttpResponseForbidden(decision.reason)
    """

    def evaluate(
        self,
        user,
        permission: str,
        company=None,
        context: dict = None
    ) -> AccessDecision:
        """
        Evaluiraj pristup. Vraća AccessDecision s objašnjenjem.
        NIKAD ne baca exception — uvijek vraća decision.
        """
        ctx = context or {}
        kwargs = {'user_id': user.pk, 'company_id': str(company.pk) if company else None, 'permission': permission}

        # ── Korak 1: Superuser bypass ─────────────────────────────
        if user.is_superuser:
            return AccessDecision(True, 'Superuser bypass', 'SUPERUSER', **kwargs)

        # ── Korak 2: Aktivnost korisnika ──────────────────────────
        if not user.is_active:
            return AccessDecision(False, 'Korisnik nije aktivan', 'USER_ACTIVE', **kwargs)

        # ── Korak 3: Company blacklist ────────────────────────────
        if company and getattr(company, 'is_deactivated', False):
            return AccessDecision(False, f'Firma {company.name} je deaktivirana', 'COMPANY_BLACKLIST', **kwargs)

        # ── Korak 4: UserProfile.role brzi path ──────────────────
        try:
            role = user.profile.role
            if role == 'superadmin':
                return AccessDecision(True, 'Profile role: superadmin', 'PROFILE_ROLE', **kwargs)
            if role in ('company_admin', 'tenant_admin') and company:
                # Admin u svojoj firmi dobiva sve — ali samo za tu firmu
                if self._user_in_company(user, company):
                    return AccessDecision(True, f'Profile role: {role} @ {company.name}', 'PROFILE_ROLE', **kwargs)
        except Exception:
            pass

        # ── Korak 5: CompanyMembership provjera ──────────────────
        if company and not self._user_in_company(user, company):
            return AccessDecision(
                False,
                f'Korisnik nije član firme {company.name}',
                'COMPANY_MEMBERSHIP',
                **kwargs
            )

        # ── Korak 6: RBAC Roles ───────────────────────────────────
        rbac_result = self._check_rbac(user, permission, company)
        if rbac_result is not None:
            return AccessDecision(rbac_result, f'RBAC: {permission}', 'RBAC_ENGINE', **kwargs)

        # ── Korak 7: Permission Overrides ─────────────────────────
        override = self._check_override(user, permission, company)
        if override is not None:
            return AccessDecision(
                override,
                f'Override: {"GRANT" if override else "REVOKE"} za {permission}',
                'OVERRIDE',
                **kwargs
            )

        # ── Korak 8: Default DENY ─────────────────────────────────
        return AccessDecision(
            False,
            f'Nema dodijeljene ovlasti za {permission}',
            'DEFAULT_DENY',
            **kwargs
        )

    def _user_in_company(self, user, company) -> bool:
        """Provjeri je li korisnik član firme (CompanyMembership)."""
        from accounts.models import CompanyMembership
        return CompanyMembership.objects.filter(
            user=user, company=company, is_active=True
        ).exists()

    def _check_rbac(self, user, permission: str, company) -> Optional[bool]:
        """Provjeri RBAC Role → Permission vezu."""
        from permissions.models import UserRole
        user_roles = UserRole.objects.filter(
            user=user, role__is_active=True
        ).select_related('role')
        if company:
            from django.db.models import Q
            user_roles = user_roles.filter(Q(company=company) | Q(company__isnull=True))
        
        for ur in user_roles:
            if ur.is_valid():
                role_perms = ur.role.get_all_permissions()
                if permission in role_perms:
                    return True
        
        if not user_roles.exists():
            return None  # Nema RBAC konfiguracije → nastavi na korak 7
        
        return False

    def _check_override(self, user, permission: str, company) -> Optional[bool]:
        """Provjeri individualne override-ove."""
        from permissions.models import PermissionOverride
        from django.utils import timezone
        
        overrides = PermissionOverride.objects.filter(
            user=user,
            permission__codename=permission,
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=timezone.now())
        )
        if company:
            overrides = overrides.filter(
                models.Q(company=company) | models.Q(company__isnull=True)
            )
        
        override = overrides.order_by('-created_at').first()
        if override:
            return override.grant
        return None


# Singleton
_engine_instance = None

def get_engine() -> PermissionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PermissionEngine()
    return _engine_instance
```

### 2b. Seed permissions (init_permissions command popuni)

```bash
cd /var/www/fina-connect
venv/bin/python manage.py init_permissions
# Ako command ne postoji ili je prazan, kreiraj seed:
venv/bin/python manage.py shell -c "
from permissions.models import Permission, Role

# Core permissions
modules_actions = [
    ('invoices', ['view','create','edit','delete','approve','export']),
    ('documents', ['view','create','edit','delete','export']),
    ('finance', ['view','create','edit','approve','export']),
    ('partners', ['view','create','edit','delete']),
    ('inventory', ['view','create','edit','delete']),
    ('pos', ['view','create','edit']),
    ('worktime', ['view','create','edit','export']),
    ('payroll', ['view','create','export']),
    ('reports', ['view','export']),
    ('users', ['view','create','edit','delete','manage']),
    ('companies', ['view','edit','manage']),
    ('system', ['manage']),
    ('ai', ['read','write','execute']),
]
created = 0
for module, actions in modules_actions:
    for action in actions:
        codename = f'{module}.{action}'
        p, c = Permission.objects.get_or_create(
            module=module, action=action,
            defaults={'codename': codename, 'name': f'{module} {action}'}
        )
        if c: created += 1

print(f'Kreirano {created} permissions. Ukupno: {Permission.objects.count()}')
"
```

---

## FAZA 3 — AI Scoped Token (Dan 3)
### Cilj: svaki AI agent operira pod tokenem koji definira što smije

### 3a. Kreiraj permissions/ai_policy.py

```python
# permissions/ai_policy.py
"""
AI Policy Layer — Scoped Token za AI agente.

Gemini, CC Code, Haiku ne smiju imati blanko ček za bazu.
Svaki AI task generira AIAccessToken koji definira:
  - allowed_models: koje modele smije čitati/pisati
  - allowed_actions: ['read', 'create', 'update'] — bez 'delete' po defaultu
  - company_scope: za koju firmu operira
  - expires_at: token istječe
  - audit_trail: sve operacije se logiraju

Ako AI pokuša operaciju izvan tokena → AI_POLICY_VIOLATION logira se
i operacija se odbija.
"""
import uuid
import json
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import models

logger = logging.getLogger('fal.ai_policy')


class AIAgentType(models.TextChoices):
    GEMINI = 'gemini', 'Google Gemini'
    CLAUDE_CODE = 'claude_code', 'Claude Code (CC)'
    HAIKU = 'haiku', 'Claude Haiku'
    SONNET = 'sonnet', 'Claude Sonnet'
    MCP = 'mcp', 'MCP Tool Call'


class AIAccessToken(models.Model):
    """
    Token za AI agent operacije.
    Generira se na početku svakog AI taska.
    """
    token_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    agent_type = models.CharField(max_length=20, choices=AIAgentType.choices)
    task_ref = models.CharField(max_length=200, help_text='CC_TASK ili GEMINI_TASK naziv')
    
    # Scope
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        help_text='null = platform-wide (samo za superadmin taskove)'
    )
    allowed_models = models.JSONField(
        default=list,
        help_text='["invoicing.Invoice", "partners.Partner"] ili ["*"] za sve (opasno)'
    )
    allowed_actions = models.JSONField(
        default=lambda: ['read'],
        help_text='["read", "create", "update"] — "delete" zahtijeva eksplicitno odobrenje'
    )
    
    # Trajanje
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=500, blank=True)
    
    # Audit
    operations_count = models.PositiveIntegerField(default=0)
    violations_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'permissions'
        db_table = 'ai_access_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.agent_type} | {self.task_ref} | expires {self.expires_at}'

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.revoked_at and timezone.now() < self.expires_at

    def can_access(self, model_label: str, action: str) -> bool:
        """
        Provjeri može li AI agent pristupiti modelu s danom akcijom.
        model_label: 'invoicing.Invoice', 'partners.Partner', itd.
        action: 'read', 'create', 'update', 'delete'
        """
        if not self.is_valid:
            self._log_violation(model_label, action, 'Token nevažeći ili istekao')
            return False
        
        # Model check
        allowed = self.allowed_models
        if '*' not in allowed and model_label not in allowed:
            # Provjeri wildcard app (npr. 'invoicing.*')
            app_label = model_label.split('.')[0]
            if f'{app_label}.*' not in allowed:
                self._log_violation(model_label, action, f'Model {model_label} nije u allowed_models')
                return False
        
        # Action check
        if action not in self.allowed_actions:
            self._log_violation(model_label, action, f'Akcija {action} nije dozvoljena (dozvoljeno: {self.allowed_actions})')
            return False

        # Log uspješan pristup
        self.operations_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['operations_count', 'last_used_at'])
        
        logger.info(f'AI_ACCESS | {self.agent_type} | {model_label}.{action} | task={self.task_ref}')
        return True

    def _log_violation(self, model_label: str, action: str, reason: str):
        """Logiraj AI_POLICY_VIOLATION."""
        self.violations_count += 1
        self.save(update_fields=['violations_count'])
        logger.warning(
            f'AI_POLICY_VIOLATION | agent={self.agent_type} | '
            f'model={model_label} | action={action} | reason={reason} | '
            f'task={self.task_ref} | token={self.token_id}'
        )

    def revoke(self, reason: str = 'Manual revoke'):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoke_reason = reason
        self.save(update_fields=['is_active', 'revoked_at', 'revoke_reason'])


def create_ai_token(
    agent_type: str,
    task_ref: str,
    allowed_models: list,
    allowed_actions: list = None,
    company=None,
    duration_hours: int = 4,
) -> AIAccessToken:
    """
    Factory funkcija za kreiranje AI tokena.
    
    Koristi se na početku svakog AI taska:
        token = create_ai_token(
            agent_type='gemini',
            task_ref='GEMINI_TASK_COMPLIANCE_WATCHDOG_V2',
            allowed_models=['invoicing.Invoice', 'documents.ArhivaEntry'],
            allowed_actions=['read'],
            company=company,
        )
    """
    if allowed_actions is None:
        allowed_actions = ['read']  # Default: samo čitanje
    
    # NIKAD ne dozvoli delete bez eksplicitnog navođenja
    if 'delete' in allowed_actions:
        logger.warning(f'AI token s DELETE ovlastima: {task_ref}. Provjerite je li ovo namjerno.')
    
    token = AIAccessToken.objects.create(
        agent_type=agent_type,
        task_ref=task_ref,
        company=company,
        allowed_models=allowed_models,
        allowed_actions=allowed_actions,
        expires_at=timezone.now() + timedelta(hours=duration_hours),
    )
    
    logger.info(f'AI_TOKEN_CREATED | {agent_type} | {task_ref} | models={allowed_models} | actions={allowed_actions}')
    return token


# ── PREDEFINIRANJI PROFILI ZA UOBIČAJENE TASKOVE ──────────────────────

AI_PROFILES = {
    'compliance_watchdog': {
        'allowed_models': ['invoicing.Invoice', 'documents.ArhivaEntry', 'eracun.EInvoice'],
        'allowed_actions': ['read'],
        'duration_hours': 24,
    },
    'ai_inbox_processor': {
        'allowed_models': ['documents.ArhivaEntry'],
        'allowed_actions': ['read', 'update'],  # update za is_booked flag
        'duration_hours': 2,
    },
    'daily_report': {
        'allowed_models': ['invoicing.*', 'pos.*', 'worktime.*'],
        'allowed_actions': ['read'],
        'duration_hours': 4,
    },
    'gemini_patrol': {
        'allowed_models': ['documents.ArhivaEntry', 'invoicing.Invoice', 'pos.Receipt'],
        'allowed_actions': ['read'],
        'duration_hours': 1,
    },
    'warehouse_w1': {
        'allowed_models': ['inventory.InventoryItem', 'inventory.GoodsReceipt'],
        'allowed_actions': ['read', 'create', 'update'],
        'duration_hours': 2,
    },
}
```

### 3b. Integracija s MCP serverom

```python
# mcp_server.py — dodati token validaciju na exec_command i write_file

# Na početku svakog MCP poziva provjeri aktivni AI token:

def _get_active_ai_token(task_ref: str = None):
    """Dohvati aktivni AI token za trenutni task."""
    from permissions.ai_policy import AIAccessToken
    tokens = AIAccessToken.objects.filter(
        agent_type='mcp',
        is_active=True,
        expires_at__gt=timezone.now(),
    )
    if task_ref:
        tokens = tokens.filter(task_ref=task_ref)
    return tokens.order_by('-created_at').first()

# Na write_file:
def write_file(path: str, content: str, task_ref: str = None) -> str:
    token = _get_active_ai_token(task_ref)
    if token and not token.can_access('filesystem', 'update'):
        return f'AI_POLICY_VIOLATION: write_file nije dozvoljen za ovaj token'
    # ... postojeća logika
```

### 3c. Migracija

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations permissions --name ai_access_token
venv/bin/python manage.py migrate permissions
```

---

## FAZA 4 — AccessAuditLog + UI (Dan 4-5)
### Cilj: vidljivost svih access decision-a u realnom vremenu

### 4a. Model

```python
# Dodati u permissions/models.py

class AccessAuditLog(models.Model):
    """
    Svaka access decision se logira.
    "Crna kutija" — za compliance (GDPR, ZOR) i debugging.
    
    Gemini: "Log mora sadržavati zašto je pristup dopušten/odbijen."
    """
    OUTCOME_CHOICES = [('grant', 'GRANT'), ('deny', 'DENY')]
    
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Što je traženo
    permission = models.CharField(max_length=200)
    view_name = models.CharField(max_length=200, blank=True)
    path = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)  # GET, POST...
    
    # Odluka
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES)
    reason = models.CharField(max_length=500)
    evaluator = models.CharField(max_length=50)  # koji korak evaluacije
    
    # AI specifično
    ai_token = models.ForeignKey(AIAccessToken, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Metapodaci
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    duration_ms = models.PositiveIntegerField(default=0, help_text='Trajanje evaluacije u ms')

    class Meta:
        app_label = 'permissions'
        db_table = 'access_audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['outcome', 'timestamp']),
            models.Index(fields=['evaluator']),
        ]
    
    def __str__(self):
        return f"{self.outcome.upper()} | {self.user} | {self.permission} | {self.evaluator}"
```

### 4b. Superadmin UI — AccessLog Dashboard

```python
# Dodati URL u core/urls.py (superadmin only):
path('superadmin/access-log/', 
     __import__('permissions.views', fromlist=['access_log_dashboard']).access_log_dashboard,
     name='access_log_dashboard'),

# permissions/views.py — access_log_dashboard view
# Template: templates/permissions/access_log.html
# Prikazuje:
#   - Real-time DENY lista (zadnjih 50)
#   - Filter: korisnik, evaluator, outcome, datum
#   - AI violations posebno označene (AI_POLICY_VIOLATION)
#   - "Simulate access" gumb — unesi korisnika i permissiona, vidi bi li prošao
```

---

## VERIFIKACIJA KOMPLETNOG FAL-a

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from permissions.engine import get_engine
from permissions.route_registry import RouteRegistry, AccessLevel
from django.contrib.auth.models import User

engine = get_engine()

# Test 1: Superuser
ivan = User.objects.get(username='ivan_brtan')
decision = engine.evaluate(ivan, 'invoices.delete')
print(f'Ivan delete: {decision.granted} | {decision.evaluator} | {decision.reason}')

# Test 2: Worker
worker = User.objects.filter(profile__role='worker').first()
if worker:
    decision = engine.evaluate(worker, 'payroll.view')
    print(f'Worker payroll: {decision.granted} | {decision.evaluator} | {decision.reason}')

# Test 3: AI token
from permissions.ai_policy import create_ai_token
token = create_ai_token('gemini', 'TEST_TASK', ['invoicing.Invoice'], ['read'])
print(f'AI read Invoice: {token.can_access(\"invoicing.Invoice\", \"read\")}')
print(f'AI delete Invoice: {token.can_access(\"invoicing.Invoice\", \"delete\")}')
print(f'AI violations: {token.violations_count}')
"
```

---

## MIGRACIJA STRATEGIJA — 3 koraka bez big bang

### Korak 1 (odmah): RouteRegistry + Middleware refaktor
Eliminira sve string path bugove. Nema promjene u logici pristupa — samo kako se gleda na rute.
Risk: NIZAK

### Korak 2 (tjedan 2): PermissionEngine seed + soft migration
Seed permissions i roles. PermissionEngine radi paralelno s postojećim sustavom — logira ali ne blokira.
Omogući "shadow mode": engine.evaluate() logira DENY ali ne vraća 403 — samo upozorava.
Risk: NIZAK

### Korak 3 (tjedan 3-4): AI Policy + AccessAuditLog + hard enforcement
Nakon što shadow mode pokaže da nema false positive, isključi ga i uključi hard enforcement.
AI tokeni se uvode postepeno — prvo Gemini task po task.
Risk: SREDNJI (uz monitoring)

### NIKAD ne raditi:
❌ Big bang migration — sve odjednom, jedna PR, sve ili ništa
❌ Brisanje @login_required dekoratora bez verifikacije da RouteRegistry pokriva tu rutu
❌ Davanje AI tokenu 'delete' bez review od Ivana

---

## COMMIT SEKVENCA

```bash
# Faza 1
git add permissions/route_registry.py core/middleware/__init__.py
git commit -m "feat(fal): RouteRegistry — view_name umjesto path string matching

Eliminira i18n blind spot: /hr/2fa/ i /en/2fa/ obje resolveaju u 'setup_2fa'.
Force2FAMiddleware i ForceTCMiddleware koriste RouteRegistry.get_access_level().
Javne rute upisane u centralnom registru (80+ ruta).

Fixes: no-limit 404, 2fa redirect loop, TC blocking public pages"

# Faza 2
git add permissions/engine.py permissions/management/
git commit -m "feat(fal): PermissionEngine — Default Deny evaluator

Redoslijed: superuser → active_check → company_blacklist → profile_role →
company_membership → RBAC → override → DEFAULT_DENY

Svaka odluka vraća AccessDecision(granted, reason, evaluator).
Seed: N permissions, M roles u bazi."

# Faza 3
git add permissions/ai_policy.py permissions/migrations/
git commit -m "feat(fal): AI Scoped Token — Gemini/CC/Haiku bez blanko čeka

AIAccessToken model: allowed_models, allowed_actions, expires_at.
Preddefinirani profili: compliance_watchdog, ai_inbox, daily_report, gemini_patrol.
AI_POLICY_VIOLATION se logira i broji po tokenu.
MCP server validira token na write_file i exec_command."

# Faza 4
git add permissions/views.py templates/permissions/
git commit -m "feat(fal): AccessAuditLog + Superadmin Dashboard

Svaka access decision se logira (outcome, reason, evaluator, duration_ms).
Superadmin view: real-time DENY lista, AI violations, simulate_access gumb."
```

---

## STATUS: READY_FOR_CC_CODE
## Faza 1 počinje odmah (nema DB promjena, samo refaktor middlewarea)
## Gemini: shadow mode monitoring u fazi 2 — prati violations prije hard enforcement
## Rok: bez fiksnog roka — svaka faza neovisna i deployable
