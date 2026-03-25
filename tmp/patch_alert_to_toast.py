#!/usr/bin/env python3
"""
Patch: Zamijeni sve alert() pozive s fenixToast() u templateima i JS fajlovima.
Preskoči vendor fajlove (rest_framework, venv).
"""
import re
import os

BASE = '/var/www/fina-connect'
CHANGED = 0
FILES_CHANGED = []

# Mapiranje konteksta na toast tip
def classify_alert(text):
    """Na temelju teksta alert poruke, odredi tip toast-a."""
    t = text.lower()
    # Success
    if any(w in t for w in ['kopiran', 'poslan', 'spremljen', 'uspje', 'ok!', 'primljen',
                             'parirano', 'odjavljen']):
        return 'success'
    # Error
    if any(w in t for w in ['gresk', 'greška', 'error', 'fehler', 'invalid',
                             'nije dostupan', 'nije uspjel', 'verbindung']):
        return 'error'
    # Warning / validation
    if any(w in t for w in ['obavezn', 'popunite', 'unesite', 'odaberite', 'oznacite',
                             'označite', 'mora imati', 'maksimal', 'max ', 'nema aktiv',
                             'prazan', 'barem', 'pflicht', 'prevelik', 'samo slike',
                             'sigurni', 'manji od', 'ne moze', 'ne može', 'pronaden',
                             'ausfullen', 'ausfüllen']):
        return 'warning'
    # Info (placeholder, coming soon)
    if any(w in t for w in ['uskoro', 'dolazi', 'kürze', 'aufbau', 'priprema',
                             'progress', 'in kürze', 'wird']):
        return 'info'
    # Default
    return 'warning'


def process_file(filepath):
    global CHANGED
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    if 'alert(' not in content:
        return

    original = content
    changes = 0

    # Pattern 1: alert('string literal') ili alert("string literal")
    # Ovo hvata najčešći slučaj
    def replace_simple_alert(m):
        nonlocal changes
        full = m.group(0)
        msg = m.group(1) or m.group(2)  # single or double quoted
        toast_type = classify_alert(msg)
        changes += 1
        # Zadrži isti quote stil
        quote = "'" if m.group(1) is not None else '"'
        return 'fenixToast(%s%s%s, %s%s%s)' % (quote, msg, quote, "'", toast_type, "'")

    # alert('...') s single quotes (može sadržavati escaped single quotes)
    content = re.sub(
        r"""alert\('((?:[^'\\]|\\.)*)'\)""",
        lambda m: _replace_alert(m, "'"),
        content
    )
    # alert("...") s double quotes
    content = re.sub(
        r'''alert\("((?:[^"\\]|\\.)*)"\)''',
        lambda m: _replace_alert(m, '"'),
        content
    )

    # Pattern 2: alert(variable) — zamijeni s fenixToast(variable, 'error')
    # Ovo hvata alert(d.error), alert(msg), alert('text' + var) itd.
    # Ali moramo paziti da ne zamjenimo ono što je već zamjenjeno
    def replace_complex_alert(m):
        nonlocal changes
        inner = m.group(1)
        if 'fenixToast' in inner:
            return m.group(0)
        # Pokušaj odrediti tip iz sadržaja
        if any(w in inner.lower() for w in ['error', 'gresk', 'greška']):
            toast_type = 'error'
        elif any(w in inner.lower() for w in ['kopiran', 'poslan', 'ok']):
            toast_type = 'success'
        else:
            toast_type = 'warning'
        changes += 1
        return "fenixToast(%s, '%s')" % (inner, toast_type)

    # alert(anything_complex) — pazi da ne hvata nested zagrade previše
    content = re.sub(
        r'alert\(([^)]+)\)',
        replace_complex_alert,
        content
    )

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        CHANGED += changes
        FILES_CHANGED.append((filepath.replace(BASE + '/', ''), changes))


def _replace_alert(m, quote):
    msg = m.group(1)
    toast_type = classify_alert(msg)
    return "fenixToast(%s%s%s, '%s')" % (quote, msg, quote, toast_type)


# Skeniraj sve HTML i JS fajlove
SKIP = {'venv', 'node_modules', 'rest_framework', '.git', 'backups', '__pycache__'}

for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for fname in files:
        if not fname.endswith(('.html', '.js')):
            continue
        filepath = os.path.join(root, fname)
        # Preskoči vendor
        if '/rest_framework/' in filepath or '/vendor/' in filepath:
            continue
        try:
            process_file(filepath)
        except Exception as e:
            print(f'[SKIP] {filepath}: {e}')

print(f'\n✅ Zamijenjeno {CHANGED} alert() poziva u {len(FILES_CHANGED)} fajlova:\n')
for path, count in sorted(FILES_CHANGED, key=lambda x: -x[1]):
    print(f'  {count:3d}  {path}')
