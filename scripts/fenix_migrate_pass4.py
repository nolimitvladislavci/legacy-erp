#!/usr/bin/env python3
"""FENIX Pass 4 — High-frequency remaining patterns"""
import re, glob, sys
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

PROP_MAP = {
    # Padding
    ('padding', '.5rem .6rem'): 'fx-p-cell',
    ('padding', '0.5rem 0.6rem'): 'fx-p-cell',
    ('padding', '.5rem'): 'fx-p-2',
    ('padding', '0.5rem'): 'fx-p-2',
    ('padding', '.75rem'): 'fx-p-3',
    ('padding', '0.75rem'): 'fx-p-3',
    ('padding', '1rem'): 'fx-p-4',
    ('padding', '1.5rem'): 'fx-p-5',
    ('padding', '2rem'): 'fx-p-6',
    ('padding', '8px'): 'fx-p-8',
    ('padding', '10px'): 'fx-p-10',
    ('padding', '12px'): 'fx-p-12',
    ('padding', '16px'): 'fx-p-16',
    ('padding', '20px'): 'fx-p-20',
    ('padding', '2px 8px'): 'fx-p-btn',
    ('padding', '.4rem .6rem'): 'fx-p-tag',
    ('padding', '0.4rem 0.6rem'): 'fx-p-tag',
    ('padding', '0'): 'fx-p-0',
    # Margin
    ('margin', '0'): 'fx-m-0',
    ('margin', '0 auto'): 'fx-m-auto',
    ('margin-bottom', '0'): 'fx-mb-0',
    ('margin-bottom', '.3rem'): 'fx-mb-2',
    ('margin-bottom', '0.3rem'): 'fx-mb-2',
    ('margin-bottom', '.5rem'): 'fx-mb-3',
    ('margin-bottom', '0.5rem'): 'fx-mb-3',
    ('margin-bottom', '.75rem'): 'fx-mb-4',
    ('margin-bottom', '0.75rem'): 'fx-mb-4',
    ('margin-bottom', '1rem'): 'fx-mb-5',
    ('margin-bottom', '1.5rem'): 'fx-mb-6',
    ('margin-top', '2px'): 'fx-mt-1',
    ('margin-top', '.25rem'): 'fx-mt-2',
    ('margin-top', '.5rem'): 'fx-mt-3',
    ('margin-top', '0.5rem'): 'fx-mt-3',
    ('margin-top', '.75rem'): 'fx-mt-4',
    ('margin-top', '0.75rem'): 'fx-mt-4',
    # Border
    ('border', '1px solid var(--border)'): 'fx-b',
    ('border', '1px solid var(--border2)'): 'fx-b2',
    ('border-bottom', '1px solid var(--border)'): 'fx-bb',
    ('border-top', '1px solid var(--border)'): 'fx-bt',
    ('border-bottom', '1px solid rgba(255,255,255,.04)'): 'fx-bb-subtle',
    ('border-color', 'var(--border)'): 'fx-bc',
    ('border-color', 'var(--border2)'): 'fx-bc2',
    ('border-collapse', 'collapse'): 'fx-b-collapse',
    ('border', 'none'): 'fx-border-none',
    # Background
    ('background', 'var(--dark)'): 'fx-bg-dark',
    ('background', 'var(--bg-card)'): 'fx-bg-card',
    ('background', 'var(--surface)'): 'fx-bg-surface',
    ('background', 'var(--surface2)'): 'fx-bg-surface2',
    ('background', 'var(--surface3)'): 'fx-bg-surface3',
    ('background', 'var(--bg)'): 'fx-bg-body',
    ('background', 'var(--bg-card-hover)'): 'fx-bg-card-hover',
    ('background', 'var(--surface-deep)'): 'fx-bg-deep',
    ('background', 'var(--gold-dim)'): 'fx-bg-gold-dim',
    ('background', 'var(--red-dim)'): 'fx-bg-red-dim',
    ('background', 'var(--green-dim)'): 'fx-bg-green-dim',
    ('background', 'var(--blue-dim)'): 'fx-bg-blue-dim',
    ('background', 'var(--amber-dim)'): 'fx-bg-amber-dim',
    ('background', 'var(--purple-dim)'): 'fx-bg-purple-dim',
    ('background', 'var(--gold)'): 'fx-bg-gold',
    ('background', 'var(--gold,#c9a84c)'): 'fx-bg-gold',
    ('background', 'transparent'): 'fx-bg-transparent',
    ('background', 'none'): 'fx-bg-transparent',
    ('background-color', 'var(--bg-card)'): 'fx-bg-card',
    ('background-color', 'transparent'): 'fx-bg-transparent',
    # Flex
    ('flex', '1'): 'fx-flex-1',
    ('flex', '1 1 0'): 'fx-flex-1',
    ('flex', '1 1 auto'): 'fx-flex-1',
    # Overflow
    ('overflow', 'hidden'): 'fx-overflow-hidden',
    ('overflow-x', 'auto'): 'fx-scroll-x',
    ('overflow-y', 'auto'): 'fx-scroll-y',
    # Typography
    ('font-family', 'monospace'): 'fx-font-mono',
    ('font-family', "'JetBrains Mono', monospace"): 'fx-font-mono',
    ('line-height', '1.6'): 'fx-lh-normal',
    ('line-height', '1.2'): 'fx-lh-tight',
    ('letter-spacing', '.5px'): 'fx-ls-1',
    ('letter-spacing', '0.5px'): 'fx-ls-1',
    ('letter-spacing', '1px'): 'fx-ls-2',
    ('letter-spacing', '1.5px'): 'fx-ls-3',
    # Display
    ('display', 'none'): 'fx-hidden',
    ('display', 'flex'): 'd-flex',
    ('display', 'block'): 'd-block',
    ('display', 'inline-block'): 'd-inline-block',
    ('display', 'inline-flex'): 'd-inline-flex',
    ('display', 'grid'): 'd-grid',
    # Alignment
    ('text-align', 'center'): 'text-center',
    ('text-align', 'right'): 'text-end',
    ('text-align', 'left'): 'text-start',
    ('align-items', 'center'): 'align-items-center',
    ('align-items', 'flex-start'): 'align-items-start',
    ('align-items', 'flex-end'): 'align-items-end',
    ('justify-content', 'center'): 'justify-content-center',
    ('justify-content', 'space-between'): 'justify-content-between',
    ('justify-content', 'flex-end'): 'justify-content-end',
    ('justify-content', 'flex-start'): 'justify-content-start',
    ('flex-wrap', 'wrap'): 'fx-flex-wrap',
    ('flex-direction', 'column'): 'fx-flex-col',
    ('flex-shrink', '0'): 'flex-shrink-0',
    # Other
    ('cursor', 'pointer'): 'fx-pointer',
    ('text-decoration', 'none'): 'fx-no-underline',
    ('text-transform', 'uppercase'): 'text-uppercase',
    ('white-space', 'nowrap'): 'text-nowrap',
    ('width', '100%'): 'w-100',
    ('min-width', '0'): 'min-w-0',
    ('user-select', 'none'): 'user-select-none',
    ('word-break', 'break-all'): 'text-break',
    ('word-break', 'break-word'): 'text-break',
    # Grid
    ('grid-template-columns', '1fr 1fr'): 'fx-grid-2-equal',
}

# Font size + weight (already defined, catch remaining)
for fs, cls in [('.55rem','fx-fs-2xs'),('.6rem','fx-fs-2xs'),('.65rem','fx-fs-xs'),
    ('.68rem','fx-fs-tiny'),('.7rem','fx-fs-sm'),('.72rem','fx-fs-sm'),
    ('.75rem','fx-fs-caption'),('.78rem','fx-fs-body-sm'),('.8rem','fx-fs-compact'),
    ('.82rem','fx-fs-note'),('.85rem','fx-fs-base'),('.88rem','fx-fs-body'),
    ('.9rem','fx-fs-md'),('.95rem','fx-fs-normal'),('1rem','fx-fs-lg'),
    ('1.1rem','fx-fs-xl'),('1.2rem','fx-fs-2xl'),('1.3rem','fx-fs-3xl'),
    ('1.4rem','fx-fs-4xl'),('1.5rem','fx-fs-5xl'),('1.6rem','fx-fs-5xl'),
    ('2rem','fx-fs-icon'),('3rem','fx-fs-hero')]:
    PROP_MAP[('font-size', fs)] = cls
    PROP_MAP[('font-size', '0' + fs if fs.startswith('.') else fs)] = cls

for fw, cls in [('400','fx-fw-normal'),('500','fx-fw-medium'),
    ('600','fx-fw-semibold'),('700','fx-fw-bold'),('800','fx-fw-800'),
    ('bold','fx-fw-bold'),('normal','fx-fw-normal')]:
    PROP_MAP[('font-weight', fw)] = cls

# Border radius
for br, cls in [('50%','fx-rounded-circle'),('9999px','fx-rounded-full'),
    ('4px','fx-rounded-sm'),('5px','fx-rounded-sm'),('6px','fx-rounded-sm'),
    ('8px','fx-rounded'),('10px','fx-rounded'),('12px','fx-rounded'),
    ('14px','fx-rounded-lg'),('16px','fx-rounded-lg'),('20px','fx-rounded-xl')]:
    PROP_MAP[('border-radius', br)] = cls

# Gap
for g, cls in [('4px','fx-gap-1'),('6px','fx-gap-2'),('8px','fx-gap-2'),
    ('10px','fx-gap-3'),('12px','fx-gap-3'),('16px','fx-gap-4'),
    ('20px','fx-gap-5'),('24px','fx-gap-6'),('32px','fx-gap-8'),
    ('.5rem','fx-gap-2'),('.75rem','fx-gap-3'),('1rem','fx-gap-4')]:
    PROP_MAP[('gap', g)] = cls


def process_tag(match):
    full_tag = match.group(0)
    style_match = re.search(r'\bstyle\s*=\s*"([^"]*)"', full_tag)
    if not style_match:
        return full_tag
    style_value = style_match.group(1)
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
        cls = PROP_MAP.get((prop, val))
        if cls and cls not in new_classes:
            new_classes.append(cls)
        else:
            remaining.append(f"{prop}:{val}")

    if not new_classes:
        return full_tag

    result = full_tag
    class_match = re.search(r'\bclass\s*=\s*"([^"]*)"', result)
    if class_match:
        existing_set = set(class_match.group(1).split())
        new_to_add = [c for c in new_classes if c not in existing_set]
        if new_to_add:
            merged = class_match.group(1).strip() + ' ' + ' '.join(new_to_add)
            result = result[:class_match.start(1)] + merged + result[class_match.end(1):]
    else:
        style_start = result.find('style=')
        result = result[:style_start] + f'class="{" ".join(new_classes)}" ' + result[style_start:]

    if remaining:
        result = re.sub(r'\bstyle\s*=\s*"[^"]*"', f'style="{";".join(remaining)}"', result)
    else:
        result = re.sub(r'\s*\bstyle\s*=\s*"[^"]*"', '', result)

    return result


pattern = re.compile(r'<[a-zA-Z][^>]*\bstyle\s*=\s*"[^"]*"[^>]*>', re.DOTALL)
dry_run = '--dry-run' in sys.argv
files_changed = 0
total_changes = 0
styles_removed = 0

for filepath in sorted(glob.glob('/var/www/fina-connect/templates/**/*.html', recursive=True)):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        original = f.read()
    result = pattern.sub(process_tag, original)
    if result != original:
        files_changed += 1
        orig_s = len(re.findall(r'\bstyle\s*=\s*"', original))
        new_s = len(re.findall(r'\bstyle\s*=\s*"', result))
        styles_removed += (orig_s - new_s)
        total_changes += abs(len(re.findall(r'fx-\w+|d-flex|d-block|d-inline|text-center|text-end|text-start|align-items|justify-content|text-uppercase|text-nowrap|w-100|flex-shrink|text-break|user-select', result)) - len(re.findall(r'fx-\w+|d-flex|d-block|d-inline|text-center|text-end|text-start|align-items|justify-content|text-uppercase|text-nowrap|w-100|flex-shrink|text-break|user-select', original)))
        if not dry_run:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

prefix = '[DRY RUN] ' if dry_run else ''
print(f"{prefix}Pass 4: {files_changed} files, {total_changes} class additions, {styles_removed} style attrs fully removed")
