"""
Fill HR .po file: since msgid is already Croatian, set msgstr = msgid for empty entries.
Skip the header entry and any fuzzy entries.
"""
import re
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

PO_PATH = "/var/www/fina-connect/locale/hr/LC_MESSAGES/django.po"

with open(PO_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Split into entries by double newline
entries = re.split(r'\n\n', content)
filled = 0
new_entries = []

for entry in entries:
    lines = entry.split('\n')
    
    # Skip fuzzy entries and header
    if '#, fuzzy' in entry and 'msgid ""' in entry and 'Project-Id-Version' in entry:
        new_entries.append(entry)
        continue
    
    # Find msgid and msgstr positions
    msgid_lines = []
    msgstr_lines = []
    in_msgid = False
    in_msgstr = False
    msgid_start = -1
    msgstr_start = -1
    
    for i, line in enumerate(lines):
        if line.startswith('msgid '):
            in_msgid = True
            in_msgstr = False
            msgid_start = i
            msgid_lines = [line]
        elif line.startswith('msgstr '):
            in_msgid = False
            in_msgstr = True
            msgstr_start = i
            msgstr_lines = [line]
        elif line.startswith('"') and in_msgid:
            msgid_lines.append(line)
        elif line.startswith('"') and in_msgstr:
            msgstr_lines.append(line)
        else:
            in_msgid = False
            in_msgstr = False
    
    # Extract msgid value
    if msgid_lines and msgstr_lines:
        msgid_val = ''
        for ml in msgid_lines:
            match = re.match(r'(?:msgid\s+)?"(.*)"', ml)
            if match:
                msgid_val += match.group(1)
        
        msgstr_val = ''
        for ml in msgstr_lines:
            match = re.match(r'(?:msgstr\s+)?"(.*)"', ml)
            if match:
                msgstr_val += match.group(1)
        
        # If msgstr is empty and msgid is not, fill it
        if msgid_val and not msgstr_val:
            # Replace msgstr "" with msgstr "msgid_val"
            new_lines = lines[:msgstr_start]
            # Reconstruct msgstr with the msgid content
            new_lines.extend(msgid_lines[0].replace('msgid ', 'msgstr ') if len(msgid_lines) == 1 else [msgid_lines[0].replace('msgid ', 'msgstr ')])
            if len(msgid_lines) > 1:
                new_lines.extend(msgid_lines[1:])
            # Add remaining lines after msgstr block
            after_msgstr = msgstr_start + len(msgstr_lines)
            new_lines.extend(lines[after_msgstr:])
            new_entries.append('\n'.join(new_lines))
            filled += 1
            continue
    
    new_entries.append(entry)

result = '\n\n'.join(new_entries)
with open(PO_PATH, "w", encoding="utf-8") as f:
    f.write(result)

print(f"HR: filled {filled} empty translations")
