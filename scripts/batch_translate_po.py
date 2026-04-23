"""
Batch translate empty msgstr entries in .po files using Claude Haiku.
Processes in batches of 50 strings at a time.
Usage: python batch_translate_po.py <locale> [--limit N]
"""
import json
import os
import re
import sys
import time

# Setup Django
sys.path.insert(0, "/var/www/fina-connect")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import anthropic

LOCALE = sys.argv[1] if len(sys.argv) > 1 else "en"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 99999
BATCH_SIZE = 50
PO_PATH = f"/var/www/fina-connect/locale/{LOCALE}/LC_MESSAGES/django.po"

LANG_NAMES = {
    "en": "English",
    "de": "German (Deutsch)",
    "tr": "Turkish (Turkce)",
    "el": "Greek (Ellinika)",
}

API_KEY = None
env_path = "/var/www/fina-connect/.env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY="):
            API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

if not API_KEY:
    print("ERROR: No ANTHROPIC_API_KEY found")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)
target_lang = LANG_NAMES.get(LOCALE, LOCALE)


def parse_po(path):
    """Parse .po file into list of entry dicts."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    # Split by double newline (entry separator)
    raw_entries = re.split(r'\n\n', content)

    for raw in raw_entries:
        lines = raw.split('\n')
        entry = {
            'raw': raw,
            'comments': [],
            'msgid': '',
            'msgstr': '',
            'msgid_lines': [],
            'msgstr_lines': [],
            'is_header': False,
            'is_fuzzy': False,
            'is_plural': False,
        }

        in_msgid = False
        in_msgstr = False

        for line in lines:
            if line.startswith('#'):
                entry['comments'].append(line)
                if '#, fuzzy' in line:
                    entry['is_fuzzy'] = True
            elif line.startswith('msgid_plural'):
                entry['is_plural'] = True
                in_msgid = False
            elif line.startswith('msgid '):
                in_msgid = True
                in_msgstr = False
                val = re.match(r'msgid "(.*)"', line)
                if val:
                    entry['msgid'] += val.group(1)
                entry['msgid_lines'].append(line)
            elif line.startswith('msgstr '):
                in_msgid = False
                in_msgstr = True
                val = re.match(r'msgstr "(.*)"', line)
                if val:
                    entry['msgstr'] += val.group(1)
                entry['msgstr_lines'].append(line)
            elif line.startswith('"'):
                if in_msgid:
                    val = re.match(r'"(.*)"', line)
                    if val:
                        entry['msgid'] += val.group(1)
                    entry['msgid_lines'].append(line)
                elif in_msgstr:
                    val = re.match(r'"(.*)"', line)
                    if val:
                        entry['msgstr'] += val.group(1)
                    entry['msgstr_lines'].append(line)

        if 'Project-Id-Version' in raw:
            entry['is_header'] = True

        entries.append(entry)

    return entries


def needs_translation(entry):
    """Check if entry needs translation."""
    if entry['is_header']:
        return False
    if entry['is_plural']:
        return False
    if not entry['msgid']:
        return False
    if entry['msgstr']:
        return False
    return True


def translate_batch(msgids, target_lang):
    """Translate a batch of strings using Claude Haiku."""
    # Build numbered list
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(msgids))

    prompt = (
        f"Translate each numbered Croatian string to {target_lang}. "
        f"Return ONLY a JSON object mapping the number (as string) to the translation. "
        f"Keep placeholders like %(name)s, {{name}}, %s, %d, \\n intact. "
        f"Keep technical terms (OIB, PDV, IBAN, JIR, ZKI, HZMO, NKD, GDPR, PDF, CSV, API) as-is. "
        f"Be concise. No explanations.\n\n{numbered}"
    )

    try:
        msg = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Extract JSON
        if "```" in text:
            parts = text.split("```")
            text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"  API error: {exc}")
        return {}


def rebuild_po(entries):
    """Rebuild .po file content from entries."""
    return '\n\n'.join(e['raw'] for e in entries)


def update_entry_msgstr(entry, translation):
    """Update entry's raw text with new msgstr."""
    # Escape quotes in translation
    translation = translation.replace('"', '\\"')

    lines = entry['raw'].split('\n')
    new_lines = []
    skip_msgstr_continuation = False

    for line in lines:
        if line.startswith('msgstr '):
            new_lines.append(f'msgstr "{translation}"')
            skip_msgstr_continuation = True
        elif skip_msgstr_continuation and line.startswith('"'):
            continue  # skip old continuation lines
        else:
            skip_msgstr_continuation = False
            # Remove fuzzy flag if present (we're filling it in now)
            if line == '#, fuzzy':
                continue
            new_lines.append(line)

    entry['raw'] = '\n'.join(new_lines)
    entry['msgstr'] = translation


def main():
    print(f"=== Translating {LOCALE} ({target_lang}) ===")
    entries = parse_po(PO_PATH)

    # Find entries needing translation
    to_translate = [(i, e) for i, e in enumerate(entries) if needs_translation(e)]
    total = len(to_translate)
    print(f"Found {total} empty entries (limit: {LIMIT})")

    if LIMIT < total:
        to_translate = to_translate[:LIMIT]

    translated_count = 0

    for batch_start in range(0, len(to_translate), BATCH_SIZE):
        batch = to_translate[batch_start:batch_start + BATCH_SIZE]
        msgids = [e['msgid'] for _, e in batch]

        print(f"  Batch {batch_start // BATCH_SIZE + 1}: translating {len(msgids)} strings...")

        results = translate_batch(msgids, target_lang)

        for j, (idx, entry) in enumerate(batch):
            key = str(j + 1)
            if key in results and results[key]:
                update_entry_msgstr(entry, results[key])
                entries[idx] = entry
                translated_count += 1

        # Rate limit
        time.sleep(1)

    # Write back
    with open(PO_PATH, "w", encoding="utf-8") as f:
        f.write(rebuild_po(entries))

    print(f"Done: {translated_count}/{total} translated for {LOCALE}")


if __name__ == "__main__":
    main()
