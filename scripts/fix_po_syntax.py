"""
Fix .po syntax errors: unescaped newlines in msgstr lines.
If a msgstr "..." spans multiple lines without proper PO continuation,
wrap the content properly.
"""

LOCALES = ["hr", "en", "de", "tr", "el"]

for locale in LOCALES:
    path = f"/var/www/fina-connect/locale/{locale}/LC_MESSAGES/django.po"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed = 0
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a msgstr with unescaped newlines
        if line.startswith('msgstr "') and not line.rstrip().endswith('"'):
            # Broken msgstr - collect until we find a proper ending or next entry
            broken = line.rstrip('\n')
            i += 1
            while i < len(lines):
                next_line = lines[i].rstrip('\n')
                if next_line == '' or next_line.startswith('#') or next_line.startswith('msgid'):
                    break
                if next_line.startswith('msgstr') or next_line.startswith('"'):
                    # This might be a continuation or new entry
                    if next_line.startswith('"') and broken.count('"') % 2 != 0:
                        broken += '\\n' + next_line.strip('"').rstrip('"')
                        i += 1
                        continue
                    break
                # It's continuation of the broken string
                broken += '\\n' + next_line
                i += 1

            # Close the msgstr properly
            if not broken.rstrip().endswith('"'):
                broken = broken.rstrip() + '"'
            new_lines.append(broken + '\n')
            fixed += 1
            continue

        new_lines.append(line)
        i += 1

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    if fixed:
        print(f"{locale}: fixed {fixed} broken msgstr entries")
    else:
        print(f"{locale}: OK (no broken entries)")
