#!/usr/bin/env python3
"""
FENIX Pass 2 — Migrate var(--*) colors and remaining patterns
"""
import re, glob, sys

# var() color → utility class
VAR_COLOR_MAP = {
    'var(--gold)': 'fx-text-gold',
    'var(--gold,#c9a84c)': 'fx-text-gold',
    'var(--gold, #c9a84c)': 'fx-text-gold',
    'var(--text-muted)': 'fx-text-muted',
    'var(--text-muted,#64748b)': 'fx-text-muted',
    'var(--text-muted, #64748b)': 'fx-text-muted',
    'var(--muted)': 'fx-text-muted',
    'var(--muted,#94a3b8)': 'fx-text-muted',
    'var(--text)': 'fx-text-body',
    'var(--text,#0f172a)': 'fx-text-body',
    'var(--text-dim)': 'fx-text-dim',
    'var(--text-dim,#94a3b8)': 'fx-text-dim',
    'var(--green)': 'fx-text-green',
    'var(--red)': 'fx-text-red',
    'var(--blue)': 'fx-text-blue',
    'var(--amber)': 'fx-text-amber',
    'var(--purple)': 'fx-text-purple',
    'var(--cyan)': 'fx-text-cyan',
    'var(--text-secondary)': 'fx-text-dim',
    '#60a5fa': 'fx-text-blue',
    '#4ade80': 'fx-text-green',
    '#fbbf24': 'fx-text-amber',
    '#e8c96a': 'fx-text-gold',
}

# Properties we can convert to margin/padding classes
MARGIN_BOTTOM_MAP = {
    '0': 'mb-0',
    '2px': 'mb-1',
    '4px': 'mb-1',
    '6px': 'mb-1',
    '8px': 'mb-2',
    '10px': 'mb-2',
    '12px': 'mb-3',
    '16px': 'mb-3',
    '20px': 'mb-4',
    '24px': 'mb-4',
    '32px': 'mb-5',
    '.5rem': 'mb-2',
    '1rem': 'mb-3',
}

MARGIN_TOP_MAP = {
    '0': 'mt-0',
    '4px': 'mt-1',
    '6px': 'mt-1',
    '8px': 'mt-2',
    '12px': 'mt-3',
    '16px': 'mt-3',
    '20px': 'mt-4',
    '24px': 'mt-4',
    '32px': 'mt-5',
    '.5rem': 'mt-2',
    '1rem': 'mt-3',
}


def find_class(prop, val):
    val = val.strip()

    if prop == 'color':
        return VAR_COLOR_MAP.get(val)

    if prop == 'margin-bottom':
        return MARGIN_BOTTOM_MAP.get(val)

    if prop == 'margin-top':
        return MARGIN_TOP_MAP.get(val)

    if prop == 'text-align':
        m = {'center': 'text-center', 'right': 'text-end', 'left': 'text-start'}
        return m.get(val)

    if prop == 'display':
        m = {'none': 'fx-hidden', 'flex': 'd-flex', 'block': 'd-block',
             'inline-block': 'd-inline-block', 'inline': 'd-inline',
             'grid': 'd-grid', 'inline-flex': 'd-inline-flex'}
        return m.get(val)

    if prop == 'align-items':
        m = {'center': 'align-items-center', 'flex-start': 'align-items-start',
             'flex-end': 'align-items-end', 'stretch': 'align-items-stretch'}
        return m.get(val)

    if prop == 'justify-content':
        m = {'center': 'justify-content-center', 'space-between': 'justify-content-between',
             'flex-start': 'justify-content-start', 'flex-end': 'justify-content-end'}
        return m.get(val)

    if prop == 'flex-wrap':
        if val == 'wrap': return 'fx-flex-wrap'

    if prop == 'flex-direction':
        if val == 'column': return 'fx-flex-col'

    if prop == 'cursor':
        if val == 'pointer': return 'fx-pointer'

    if prop == 'text-decoration':
        if val == 'none': return 'fx-no-underline'

    if prop == 'overflow-x':
        if val == 'auto': return 'fx-scroll-x'

    if prop == 'white-space':
        if val == 'nowrap': return 'text-nowrap'

    if prop == 'gap':
        gap_map = {'4px':'fx-gap-1','6px':'fx-gap-2','8px':'fx-gap-2',
                   '10px':'fx-gap-3','12px':'fx-gap-3','16px':'fx-gap-4',
                   '20px':'fx-gap-5','24px':'fx-gap-6','32px':'fx-gap-8',
                   '.5rem':'fx-gap-2','.75rem':'fx-gap-3','1rem':'fx-gap-4'}
        return gap_map.get(val)

    if prop == 'width':
        if val == '100%': return 'fx-w-full'

    if prop == 'border':
        if val == 'none': return 'fx-border-none'

    if prop == 'font-weight':
        m = {'400':'fx-fw-normal','500':'fx-fw-medium','600':'fx-fw-semibold',
             '700':'fx-fw-bold','800':'fx-fw-800','bold':'fx-fw-bold','normal':'fx-fw-normal'}
        return m.get(val)

    return None


def process_tag(match):
    full_tag = match.group(0)

    # Skip Django template tags
    if '{%' in full_tag.split('style=')[0][-5:]:
        return full_tag

    style_match = re.search(r'\bstyle\s*=\s*"([^"]*)"', full_tag)
    if not style_match:
        return full_tag

    style_value = style_match.group(1)

    # Skip styles with Django tags
    if '{%' in style_value or '{{' in style_value:
        return full_tag

    props = []
    for part in style_value.split(';'):
        part = part.strip()
        if ':' in part:
            colon = part.index(':')
            props.append((part[:colon].strip().lower(), part[colon+1:].strip()))

    new_classes = []
    remaining = []

    for prop, val in props:
        cls = find_class(prop, val)
        if cls and cls not in new_classes:
            new_classes.append(cls)
        else:
            remaining.append(f"{prop}:{val}")

    if not new_classes:
        return full_tag

    result = full_tag

    # Update class attribute
    class_match = re.search(r'\bclass\s*=\s*"([^"]*)"', result)
    if class_match:
        existing_set = set(class_match.group(1).split())
        new_to_add = [c for c in new_classes if c not in existing_set]
        if not new_to_add:
            pass
        else:
            merged = class_match.group(1).strip() + ' ' + ' '.join(new_to_add)
            result = result[:class_match.start(1)] + merged + result[class_match.end(1):]
    else:
        style_start = result.find('style=')
        result = result[:style_start] + f'class="{" ".join(new_classes)}" ' + result[style_start:]

    # Update or remove style
    if remaining:
        new_style = ';'.join(remaining)
        result = re.sub(r'\bstyle\s*=\s*"[^"]*"', f'style="{new_style}"', result)
    else:
        result = re.sub(r'\s*\bstyle\s*=\s*"[^"]*"', '', result)

    return result


def main():
    dry_run = '--dry-run' in sys.argv
    base_dir = '/var/www/fina-connect'
    html_files = sorted(glob.glob(f'{base_dir}/templates/**/*.html', recursive=True))

    total_changes = 0
    files_changed = 0

    pattern = re.compile(r'<[a-zA-Z][^>]*\bstyle\s*=\s*"[^"]*"[^>]*>', re.DOTALL)

    for filepath in html_files:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            original = f.read()

        result = pattern.sub(process_tag, original)

        if result != original:
            files_changed += 1
            orig_styles = len(re.findall(r'\bstyle\s*=\s*"', original))
            new_styles = len(re.findall(r'\bstyle\s*=\s*"', result))
            changes = orig_styles - new_styles + (len(re.findall(r'fx-\w+', result)) - len(re.findall(r'fx-\w+', original)))
            total_changes += changes

            if not dry_run:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(result)

    prefix = '[DRY RUN] ' if dry_run else ''
    print(f"{prefix}Pass 2 complete: {files_changed} files, {total_changes} changes")


if __name__ == '__main__':
    main()
