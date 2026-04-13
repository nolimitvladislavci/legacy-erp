"""
Patch: CSRF Token Injection — svih 39 templatea + HTMX globalni header
═══════════════════════════════════════════════════════════════════════
CSRF (Cross-Site Request Forgery) je OWASP Top 10 ranjivost.
Bez {% csrf_token %} u POST formama, napadač može izvršiti
akcije u ime ulogiranog korisnika (npr. brisanje podataka,
promjena statusa naloga, financijske transakcije).
"""
import os
import re
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

BASE = '/var/www/fina-connect'
TEMPLATES_DIR = os.path.join(BASE, 'templates')

# ══════════════════════════════════════════════════════════════════════
# 1. Nađi sve POST forme bez {% csrf_token %}
# ══════════════════════════════════════════════════════════════════════

fixed = []
skipped = []

for root, dirs, files in os.walk(TEMPLATES_DIR):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(root, fname)
        
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Skip ako nema POST forme
        if not re.search(r'method\s*=\s*["\']?POST["\']?', content, re.IGNORECASE):
            continue
        
        # Skip ako već ima csrf_token
        if '{% csrf_token %}' in content or '{%csrf_token%}' in content:
            continue
        
        # Inject {% csrf_token %} nakon svake <form ... POST ...> tag-a
        original = content
        
        # Pattern: <form ... method="POST" ...> (može imati druge atribute između)
        def inject_csrf(match):
            form_tag = match.group(0)
            # Dodaj csrf_token odmah nakon zatvaranja form taga
            return form_tag + '\n    {% csrf_token %}'
        
        # Regex: <form [bilo što] method="POST" [bilo što]>
        content = re.sub(
            r'(<form\b[^>]*method\s*=\s*["\']?POST["\']?[^>]*>)',
            inject_csrf,
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        
        # Također: <form method="post" ...> (lowercase)
        # Već pokriven gore s re.IGNORECASE
        
        if content != original:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            rel_path = os.path.relpath(fpath, BASE)
            fixed.append(rel_path)
        else:
            rel_path = os.path.relpath(fpath, BASE)
            skipped.append(rel_path)

print(f"[CSRF] Fixed {len(fixed)} templates:")
for f in sorted(fixed):
    print(f"  ✓ {f}")
if skipped:
    print(f"\n[CSRF] Skipped {len(skipped)} (POST detected but no form tag match):")
    for s in skipped:
        print(f"  ? {s}")


# ══════════════════════════════════════════════════════════════════════
# 2. HTMX Globalni CSRF Header — base.html
# ══════════════════════════════════════════════════════════════════════

base_path = os.path.join(TEMPLATES_DIR, 'base.html')
with open(base_path, 'r', encoding='utf-8') as f:
    base = f.read()

# Provjeri ima li već HTMX CSRF config
if 'hx-headers' not in base and 'htmx.config.csrf' not in base:
    # Inject HTMX CSRF config odmah nakon HTMX script taga
    old_htmx = '<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" crossorigin="anonymous"></script>'
    
    htmx_csrf = '''<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" crossorigin="anonymous"></script>
    <!-- HTMX Global CSRF Header — svaki HTMX request šalje X-CSRFToken -->
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        document.body.addEventListener('htmx:configRequest', function(event) {
            // Pokupi CSRF token iz cookie-ja (Django ga tamo stavlja)
            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            if (!csrfToken) {
                // Fallback: pokupi iz cookie-ja
                var cookies = document.cookie.split(';');
                for (var i = 0; i < cookies.length; i++) {
                    var c = cookies[i].trim();
                    if (c.startsWith('csrftoken=')) {
                        csrfToken = c.substring('csrftoken='.length);
                        break;
                    }
                }
            }
            if (csrfToken) {
                event.detail.headers['X-CSRFToken'] = csrfToken;
            }
        });
    });
    </script>'''
    
    base = base.replace(old_htmx, htmx_csrf)
    
    with open(base_path, 'w', encoding='utf-8') as f:
        f.write(base)
    print("\n[HTMX CSRF] Globalni header konfiguriran u base.html")
    print("  Svaki HTMX request automatski šalje X-CSRFToken header")
else:
    print("\n[HTMX CSRF] Već konfigurirano — preskačem")


# ══════════════════════════════════════════════════════════════════════
# 3. Provjera: JavaScript POST/fetch bez CSRF tokena
# ══════════════════════════════════════════════════════════════════════

# Nađi JS fetchove koji koriste POST bez X-CSRFToken
js_risky = []
for root, dirs, files in os.walk(TEMPLATES_DIR):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Nađi fetch() s POST koji nema CSRFToken
        if 'fetch(' in content and 'POST' in content:
            if 'X-CSRFToken' not in content and 'csrfmiddlewaretoken' not in content and 'csrftoken' not in content.lower():
                rel = os.path.relpath(fpath, BASE)
                js_risky.append(rel)

if js_risky:
    print(f"\n[JS CSRF WARNING] {len(js_risky)} templates imaju fetch(POST) bez CSRF tokena:")
    for r in js_risky:
        print(f"  ⚠ {r}")
else:
    print("\n[JS CSRF] Svi fetch(POST) pozivi imaju CSRF token — OK")


print("\n═══════════════════════════════════════════")
print("CSRF PATCH KOMPLETIRAN")
print("═══════════════════════════════════════════")
