"""
Surgical fix for known problematic PO entries.
Uses line-by-line approach to find and fix broken entries.
"""
import re

LOCALES = ["hr", "en", "de", "tr", "el"]

# These msgids cause problems because Haiku unescapes \n
PROBLEM_MSGIDS = [
    "Choose from:\\n\\t{choices}",
    "OpenApi3 schema",
]


def fix_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Strategy: find broken msgstr entries and replace them
    # A broken entry has msgstr "..." followed by content NOT starting with # or msgid or "
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    fixes = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Detect a msgstr that's broken (content after closing quote)
        if line.startswith('msgstr "'):
            # Find the corresponding msgid
            msgid = ""
            for j in range(len(new_lines) - 1, max(0, len(new_lines) - 20), -1):
                if new_lines[j].startswith('msgid "'):
                    m = re.match(r'msgid "(.*)"$', new_lines[j])
                    if m:
                        msgid = m.group(1)
                    break
                elif new_lines[j].startswith('msgid ""'):
                    # Multiline msgid
                    parts = []
                    for k in range(j + 1, len(new_lines)):
                        if new_lines[k].startswith('"'):
                            m = re.match(r'"(.*)"$', new_lines[k])
                            if m:
                                parts.append(m.group(1))
                        else:
                            break
                    msgid = ''.join(parts)
                    break
            
            # Check if this msgstr line is properly formatted
            m = re.match(r'^msgstr "(.*)"$', line)
            if m:
                # Properly formatted single-line msgstr
                new_lines.append(line)
                i += 1
                continue
            
            # Broken msgstr - collect all garbage until next proper entry
            i += 1
            garbage_lines = []
            while i < len(lines):
                next_line = lines[i]
                if next_line == '' or next_line.startswith('#') or next_line.startswith('msgid'):
                    break
                if next_line.startswith('"') and next_line.endswith('"'):
                    # Proper continuation - might be OK
                    garbage_lines.append(next_line)
                    i += 1
                    continue
                garbage_lines.append(next_line)
                i += 1
            
            # For these broken entries, just set msgstr = msgid
            if msgid:
                new_lines.append(f'msgstr "{msgid}"')
            else:
                new_lines.append('msgstr ""')
            fixes += 1
            continue
        
        new_lines.append(line)
        i += 1
    
    with open(path, "w", encoding="utf-8") as f:
        f.write('\n'.join(new_lines))
    
    return fixes


for locale in LOCALES:
    path = f"/var/www/fina-connect/locale/{locale}/LC_MESSAGES/django.po"
    count = fix_file(path)
    print(f"{locale}: {count} entries fixed")
