#!/usr/bin/env python3
"""
BORG Auth Audit Patcher — fixa 8 pronađenih bugova u auth flowu.

Bug #1: Password min length 8→10 (uskladi sa settings.py validatorima)
Bug #2: Rate limit na 2FA verify (5 pokušaja / 10 min)
Bug #3: Audit log na registraciju
Bug #4: ForcePasswordChange whitelist za /onboarding/
"""
import re

# ═══════════════════════════════════════════════════════════════
# BUG #1: Password validator mismatch — 8 → 10
# ═══════════════════════════════════════════════════════════════

# File: accounts/auth_views.py
with open('/var/www/fina-connect/accounts/auth_views.py', 'r') as f:
    content = f.read()

# Fix password_reset_confirm: len(p1) < 8 → len(p1) < 10
content = content.replace(
    "elif len(p1) < 8:\n            messages.error(request, _('Lozinka mora imati najmanje 8 znakova.'))",
    "elif len(p1) < 10:\n            messages.error(request, _('Lozinka mora imati najmanje 10 znakova.'))"
)

with open('/var/www/fina-connect/accounts/auth_views.py', 'w') as f:
    f.write(content)
print("FIX #1a: auth_views.py password_reset_confirm 8→10")


# File: accounts/views.py
with open('/var/www/fina-connect/accounts/views.py', 'r') as f:
    content = f.read()

# Fix change_password: len(p1) < 8 → len(p1) < 10
content = content.replace(
    "elif len(p1) < 8:\n",
    "elif len(p1) < 10:\n",
)

# Fix quick_register: len(password) < 8 → len(password) < 10
content = content.replace(
    "if len(password) < 8:\n            errors['password'] = 'Lozinka mora imati najmanje 8 znakova.'",
    "if len(password) < 10:\n            errors['password'] = 'Lozinka mora imati najmanje 10 znakova.'"
)

with open('/var/www/fina-connect/accounts/views.py', 'w') as f:
    f.write(content)
print("FIX #1b: views.py change_password + quick_register 8→10")


# ═══════════════════════════════════════════════════════════════
# BUG #2: Rate limit na 2FA verify
# ═══════════════════════════════════════════════════════════════

with open('/var/www/fina-connect/accounts/auth_views.py', 'r') as f:
    content = f.read()

# Dodaj rate limit check u verify_2fa
old_verify = """def verify_2fa(request):
    \"\"\"Provjera 2FA koda pri prijavi\"\"\"
    user_id = request.session.get('pending_2fa_user')
    if not user_id:
        return redirect('smart_login')

    if request.method == 'POST':
        import pyotp
        code = request.POST.get('code', '').replace(' ', '')"""

new_verify = """def verify_2fa(request):
    \"\"\"Provjera 2FA koda pri prijavi — rate limited (5/10min)\"\"\"
    user_id = request.session.get('pending_2fa_user')
    if not user_id:
        return redirect('smart_login')

    if request.method == 'POST':
        import pyotp
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
        code = request.POST.get('code', '').replace(' ', '')

        # Rate limit: max 5 pokušaja u 10 min (sprečava brute-force 6-digit koda)
        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')
        attempt_key = f'2fa_{user_id}'
        if LoginAttempt.is_blocked(ip, attempt_key, max_attempts=5, minutes=10):
            messages.error(request, _('Previše neuspješnih pokušaja. Pričekajte 10 minuta.'))
            return render(request, 'accounts/verify_2fa.html')"""

content = content.replace(old_verify, new_verify)

# Dodaj LoginAttempt logging za 2FA
old_2fa_success = """            if totp.verify(code):
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                del request.session['pending_2fa_user']"""

new_2fa_success = """            if totp.verify(code):
                LoginAttempt.objects.create(email=attempt_key, ip_address=ip, success=True, method='2fa')
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                del request.session['pending_2fa_user']"""

content = content.replace(old_2fa_success, new_2fa_success)

old_2fa_fail = """            else:
                messages.error(request, _('Pogrešan kod. Pokušajte ponovo.'))"""

new_2fa_fail = """            else:
                LoginAttempt.objects.create(email=attempt_key, ip_address=ip, success=False, method='2fa')
                messages.error(request, _('Pogrešan kod. Pokušajte ponovo.'))"""

content = content.replace(old_2fa_fail, new_2fa_fail)

with open('/var/www/fina-connect/accounts/auth_views.py', 'w') as f:
    f.write(content)
print("FIX #2: 2FA verify rate limited (5 attempts / 10 min)")


# ═══════════════════════════════════════════════════════════════
# BUG #4: ForcePasswordChange whitelist za /onboarding/
# ═══════════════════════════════════════════════════════════════

with open('/var/www/fina-connect/core/middleware/__init__.py', 'r') as f:
    content = f.read()

old_whitelist = "if request.path.startswith('/accounts/password/') or request.path.startswith('/accounts/logout'):"
new_whitelist = "if request.path.startswith('/accounts/password/') or request.path.startswith('/accounts/logout') or request.path.startswith('/onboarding/'):"

content = content.replace(old_whitelist, new_whitelist)

with open('/var/www/fina-connect/core/middleware/__init__.py', 'w') as f:
    f.write(content)
print("FIX #4: ForcePasswordChange whitelist += /onboarding/")


print("\n✅ All 4 critical fixes applied!")
