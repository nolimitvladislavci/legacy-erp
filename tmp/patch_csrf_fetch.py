"""
Patch: CSRF token u fetch() pozive — 9 ranjivih templatea
Injectira getCsrf() helper i X-CSRFToken header u sve fetch(POST) pozive.
"""
import os
import re
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

BASE = '/var/www/fina-connect/templates'

# Helper funkcija za dohvat CSRF tokena — injectira se jednom po fileu
CSRF_HELPER = """
<script>
function getCsrf(){var t=document.querySelector('[name=csrfmiddlewaretoken]');if(t)return t.value;var c=document.cookie.split(';');for(var i=0;i<c.length;i++){var p=c[i].trim();if(p.startsWith('csrftoken='))return p.substring(10);}return'';}
</script>
"""

# Fajlovi za fix
targets = {
    # marketplace/cart.html — fetch bez headers-a
    'marketplace/cart.html': {
        'patterns': [
            ("body:fd, credentials:'same-origin'}", "body:fd, credentials:'same-origin', headers:{'X-CSRFToken':getCsrf()}}"),
        ]
    },
    # marketplace/catalog.html — form submit via fetch
    'marketplace/catalog.html': {
        'patterns': [
            ("fetch(this.action, {method:'POST', body:new FormData(this)})",
             "fetch(this.action, {method:'POST', body:new FormData(this), headers:{'X-CSRFToken':getCsrf()}})"),
        ]
    },
    # pos/kiosk.html
    'pos/kiosk.html': {
        'inject_after_pattern': "method: 'POST',",
        'header_line': "    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},",
    },
    # pos/pickup_menu.html
    'pos/pickup_menu.html': {
        'inject_after_pattern': "method: 'POST',",
        'header_line': "        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},",
    },
    # pos/waiter/kds.html — multiple fetch calls
    'pos/waiter/kds.html': {
        'inject_after_pattern': "method:'POST',",
        'header_line': "      headers:{'Content-Type':'application/json','X-CSRFToken':getCsrf()},",
    },
    # website/feedback.html
    'website/feedback.html': {
        'inject_after_pattern': "method: 'POST',",
        'header_line': "    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},",
    },
    # portal/invoice_detail.html
    'portal/invoice_detail.html': {
        'patterns': [
            ("headers: {'X-Requested-With': 'XMLHttpRequest'}",
             "headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrf()}"),
        ]
    },
}

fixed = 0
for rel_path, config in targets.items():
    fpath = os.path.join(BASE, rel_path)
    if not os.path.exists(fpath):
        print(f"  SKIP {rel_path} — not found")
        continue
    
    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    # Inject getCsrf() helper if not present
    if 'getCsrf' not in content:
        # Inject before </head> or before first <script> or at top
        if '</head>' in content:
            content = content.replace('</head>', CSRF_HELPER + '</head>')
        elif '<script' in content:
            first_script = content.index('<script')
            content = content[:first_script] + CSRF_HELPER + content[first_script:]
        else:
            content = CSRF_HELPER + content
    
    # Apply patterns (direct string replacement)
    if 'patterns' in config:
        for old, new in config['patterns']:
            content = content.replace(old, new)
    
    # Apply inject_after_pattern (add headers line after method: 'POST')
    if 'inject_after_pattern' in config:
        pattern = config['inject_after_pattern']
        header = config['header_line']
        
        # Only inject if headers not already present after method:POST
        lines = content.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if pattern in line and 'X-CSRFToken' not in line:
                # Check next line doesn't already have headers
                if i + 1 < len(lines) and 'headers' in lines[i + 1]:
                    # Already has headers — add CSRF to existing
                    if 'X-CSRFToken' not in lines[i + 1]:
                        lines[i + 1] = lines[i + 1].replace("headers:", "headers:").replace("}", ", 'X-CSRFToken':getCsrf()}")
                else:
                    new_lines.append(header)
        content = '\n'.join(new_lines)
    
    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ {rel_path}")
        fixed += 1
    else:
        print(f"  ~ {rel_path} (no changes needed)")


# 404.html i 500.html — error page-ovi, POST je za BORG signal koji je u base.html
# Njihov fetch koristi BORG signaling koji je u base.html — CSRF je već tamo
print(f"\n  ~ 404.html / 500.html — BORG signal fetch, CSRF je u base.html")

print(f"\n[CSRF fetch] Fixed {fixed} templates")
