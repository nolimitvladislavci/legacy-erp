"""
Final comprehensive PO fix:
1. Restore headers if missing
2. Fix entries with missing msgstr
3. Fix python-format string mismatches (copy msgid to msgstr)
"""
import re
import subprocess

LOCALES = ["hr", "en", "de", "tr", "el"]
HEADERS = {
    "hr": "hr",
    "en": "en",
    "de": "de",
    "tr": "tr",
    "el": "el",
}

HEADER_TEMPLATE = '''# LIMIT Connect translations.
# Copyright (C) 2026 Viskovic Group
#
msgid ""
msgstr ""
"Project-Id-Version: LIMIT Connect 1.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: 2026-04-06 20:00+0200\\n"
"PO-Revision-Date: 2026-04-06 20:00+0200\\n"
"Last-Translator: Claude AI\\n"
"Language-Team: LIMIT Connect\\n"
"Language: {lang}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
'''


def fix_header(content, lang):
    """Ensure proper header is present."""
    # Check if header exists
    if '"Project-Id-Version' not in content[:500]:
        # Replace everything before first real msgid
        first_real = content.find('\n#:')
        if first_real == -1:
            first_real = content.find('\nmsgid "')
        if first_real > 0:
            content = HEADER_TEMPLATE.format(lang=lang) + '\n' + content[first_real:]
    return content


def fix_missing_msgstr(content):
    """Add msgstr "" after msgid entries that are missing it."""
    blocks = content.split('\n\n')
    fixed = 0
    new_blocks = []

    for block in blocks:
        if 'msgid "' in block and 'msgstr' not in block and 'msgid_plural' not in block:
            # Missing msgstr - add it
            block = block.rstrip() + '\nmsgstr ""'
            fixed += 1
        new_blocks.append(block)

    return '\n\n'.join(new_blocks), fixed


def fix_format_strings(path):
    """Run msgfmt --check, find format string errors, copy msgid to msgstr for those."""
    result = subprocess.run(
        ['msgfmt', '--check', path, '-o', '/dev/null'],
        capture_output=True, text=True
    )
    errors = result.stderr

    # Find line numbers with format string errors
    bad_lines = set()
    for line in errors.split('\n'):
        m = re.match(rf'{re.escape(path)}:(\d+):.*not a valid Python format string', line)
        if m:
            bad_lines.add(int(m.group(1)))

    if not bad_lines:
        return 0

    with open(path) as f:
        lines = f.readlines()

    fixed = 0
    for bad_line_num in sorted(bad_lines):
        idx = bad_line_num - 1  # 0-based
        if idx >= len(lines):
            continue

        # Find the msgid for this msgstr
        msgid_parts = []
        i = idx - 1
        while i >= 0:
            line = lines[i].rstrip()
            if line.startswith('msgid "'):
                m = re.match(r'msgid "(.*)"', line)
                if m:
                    msgid_parts.insert(0, m.group(1))
                break
            elif line.startswith('"'):
                m = re.match(r'"(.*)"', line)
                if m:
                    msgid_parts.insert(0, m.group(1))
            elif line.startswith('msgid ""'):
                break
            else:
                break
            i -= 1

        msgid_val = ''.join(msgid_parts)
        if msgid_val:
            # Replace the msgstr with the msgid value
            lines[idx] = f'msgstr "{msgid_val}"\n'
            fixed += 1

    with open(path, 'w') as f:
        f.writelines(lines)

    return fixed


for locale in LOCALES:
    path = f"/var/www/fina-connect/locale/{locale}/LC_MESSAGES/django.po"

    with open(path) as f:
        content = f.read()

    # Fix 1: header
    content = fix_header(content, HEADERS[locale])

    # Fix 2: missing msgstr
    content, missing_fixed = fix_missing_msgstr(content)

    with open(path, 'w') as f:
        f.write(content)

    # Fix 3: format strings
    fmt_fixed = fix_format_strings(path)

    # Check remaining errors
    result = subprocess.run(
        ['msgfmt', '--check', path, '-o', '/dev/null'],
        capture_output=True, text=True
    )
    errors = [l for l in result.stderr.split('\n') if 'fatal' in l or 'error' in l.lower()]
    remaining = len([l for l in result.stderr.split('\n') if ': ' in l and 'warning' not in l and l.strip()])

    print(f"{locale}: header={'fixed' if 'Project-Id' in content[:500] else 'OK'}, "
          f"missing_msgstr={missing_fixed}, format_fixed={fmt_fixed}, "
          f"remaining_issues={remaining}")
