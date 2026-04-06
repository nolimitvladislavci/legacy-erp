"""
Robust PO file fixer:
1. Find entries where msgstr contains literal newlines (not \\n)
2. Fix by properly escaping them
3. For technical/API strings, copy msgid as msgstr
"""
import re

LOCALES = ["hr", "en", "de", "tr", "el"]

def fix_po_file(path, locale):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    
    # Split into blocks separated by blank lines
    blocks = raw.split('\n\n')
    fixed_blocks = []
    fix_count = 0
    
    for block in blocks:
        lines = block.split('\n')
        
        # Check if this block has a broken msgstr
        has_msgid = any(l.startswith('msgid ') for l in lines)
        has_msgstr = any(l.startswith('msgstr ') for l in lines)
        
        if not has_msgid or not has_msgstr:
            fixed_blocks.append(block)
            continue
        
        # Extract msgid
        msgid_parts = []
        msgstr_parts = []
        other_lines = []
        in_msgid = False
        in_msgstr = False
        is_broken = False
        
        for line in lines:
            if line.startswith('msgid "'):
                in_msgid = True
                in_msgstr = False
                m = re.match(r'msgid "(.*)"$', line)
                if m:
                    msgid_parts.append(m.group(1))
                else:
                    # Broken msgid line
                    is_broken = True
                    msgid_parts.append(line[7:])
            elif line.startswith('msgstr "'):
                in_msgid = False
                in_msgstr = True
                m = re.match(r'msgstr "(.*)"$', line)
                if m:
                    msgstr_parts.append(m.group(1))
                else:
                    # Broken msgstr line - doesn't end with "
                    is_broken = True
                    msgstr_parts.append(line[8:])
            elif line.startswith('"') and line.endswith('"'):
                if in_msgid:
                    msgid_parts.append(line[1:-1])
                elif in_msgstr:
                    msgstr_parts.append(line[1:-1])
                else:
                    other_lines.append(line)
            elif line.startswith('#') or line.startswith('msgid_plural') or line.startswith('msgstr['):
                in_msgid = False
                in_msgstr = False
                other_lines.append(line)
            else:
                # Unexpected line - could be part of a broken multiline
                if in_msgstr and line.strip():
                    is_broken = True
                    msgstr_parts.append(line)
                else:
                    in_msgid = False
                    in_msgstr = False
                    other_lines.append(line)
        
        if is_broken:
            # Reconstruct the entry properly
            msgid_val = ''.join(msgid_parts).strip('"').replace('\n', '\\n')
            msgstr_val = ''.join(msgstr_parts).strip('"').replace('\n', '\\n')
            
            # Clean up any double-escaping
            while '\\\\n' in msgstr_val:
                msgstr_val = msgstr_val.replace('\\\\n', '\\n')
            
            # Remove any trailing garbage
            msgstr_val = msgstr_val.strip().rstrip('"').strip()
            
            # Rebuild block
            comment_lines = [l for l in other_lines if l.startswith('#')]
            new_block_lines = comment_lines[:]
            
            # Write msgid
            if '\\n' in msgid_val or len(msgid_val) > 75:
                new_block_lines.append('msgid ""')
                for part in msgid_val.split('\\n'):
                    if part:
                        new_block_lines.append(f'"{part}\\n"')
                    else:
                        new_block_lines.append('"\\n"')
            else:
                new_block_lines.append(f'msgid "{msgid_val}"')
            
            # For msgstr, if it looks like a technical string, use msgid
            if not msgstr_val or 'OpenApi3' in msgid_val or 'schema' in msgid_val:
                msgstr_val = msgid_val
            
            new_block_lines.append(f'msgstr "{msgstr_val}"')
            
            # Add any msgid_plural / msgstr[N] lines
            for l in other_lines:
                if l.startswith('msgid_plural') or l.startswith('msgstr['):
                    new_block_lines.append(l)
            
            fixed_blocks.append('\n'.join(new_block_lines))
            fix_count += 1
        else:
            fixed_blocks.append(block)
    
    result = '\n\n'.join(fixed_blocks)
    with open(path, "w", encoding="utf-8") as f:
        f.write(result)
    
    return fix_count


for locale in LOCALES:
    path = f"/var/www/fina-connect/locale/{locale}/LC_MESSAGES/django.po"
    count = fix_po_file(path, locale)
    print(f"{locale}: fixed {count} broken entries")
