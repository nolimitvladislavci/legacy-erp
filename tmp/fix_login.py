
import re

with open('/var/www/fina-connect/core/views.py', 'r') as f:
    content = f.read()

old = '''def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')'''

new = '''def login_view(request):
    # ?switch=1 ili ?force=1 → odjavi starog korisnika i prikaži formu
    if request.user.is_authenticated:
        if request.GET.get('switch') or request.GET.get('force'):
            from django.contrib.auth import logout as _logout
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
            _logout(request)
        else:
            return redirect('dashboard')'''

if old in content:
    content = content.replace(old, new)
    with open('/var/www/fina-connect/core/views.py', 'w') as f:
        f.write(content)
    print('OK — login_view patched')
else:
    print('ERROR — pattern not found')
