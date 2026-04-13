#!/usr/bin/env python3
"""
FENIX Inline Style → Utility Class Migrator
============================================
Scans all HTML templates and replaces common inline style patterns
with fenix utility classes. Theme-aware, safe, reversible.

Usage: python scripts/fenix_migrate_inline.py [--dry-run] [--verbose] [--path templates/invoicing/]
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# COLOR MAPPINGS: hardcoded hex → CSS variable class
# ═══════════════════════════════════════════════════════════════
TEXT_COLOR_MAP = {
    # Red variants
    '#ef4444': 'fx-text-red',
    '#dc2626': 'fx-text-red',
    '#e74c3c': 'fx-text-red',
    '#f44336': 'fx-text-red',
    '#ff4444': 'fx-text-red',
    # Green variants
    '#22c55e': 'fx-text-green',
    '#10b981': 'fx-text-green',
    '#16a34a': 'fx-text-green',
    '#2ecc71': 'fx-text-green',
    '#28a745': 'fx-text-green',
    '#059669': 'fx-text-green',
    # Gold variants
    '#c9a84c': 'fx-text-gold',
    '#c8a24e': 'fx-text-gold',
    '#d4a017': 'fx-text-gold',
    '#b8860b': 'fx-text-gold',
    '#92650a': 'fx-text-gold',
    # Blue variants
    '#3b82f6': 'fx-text-blue',
    '#2563eb': 'fx-text-blue',
    '#3498db': 'fx-text-blue',
    '#007bff': 'fx-text-blue',
    # Amber/Yellow variants
    '#f59e0b': 'fx-text-amber',
    '#d97706': 'fx-text-amber',
    '#f39c12': 'fx-text-amber',
    '#ffc107': 'fx-text-amber',
    # Purple
    '#8b5cf6': 'fx-text-purple',
    '#7c3aed': 'fx-text-purple',
    # Cyan
    '#06b6d4': 'fx-text-cyan',
    '#0891b2': 'fx-text-cyan',
    # Muted/dim text
    '#64748b': 'fx-text-dim',
    '#475569': 'fx-text-dim',
    '#94a3b8': 'fx-text-muted',
    '#888': 'fx-text-muted',
    '#888888': 'fx-text-muted',
    '#999': 'fx-text-muted',
    '#aaa': 'fx-text-muted',
    '#aaaaaa': 'fx-text-muted',
    '#666': 'fx-text-dim',
    '#666666': 'fx-text-dim',
    '#555': 'fx-text-dim',
    '#555555': 'fx-text-dim',
    '#6c757d': 'fx-text-dim',
    # White/light
    '#fff': 'fx-text-white',
    '#ffffff': 'fx-text-white',
    '#f0ede8': 'fx-text-white',
    '#e2e8f0': 'fx-text-body',
    # Dark
    '#000': 'fx-text-dark',
    '#000000': 'fx-text-dark',
    '#0a0a0a': 'fx-text-dark',
    '#0f172a': 'fx-text-dark',
    '#333': 'fx-text-dark',
    '#333333': 'fx-text-dark',
    '#212529': 'fx-text-dark',
}

BG_COLOR_MAP = {
    # Dark surfaces
    '#0a0a0a': 'fx-bg-body',
    '#0a0a0f': 'fx-bg-body',
    '#111': 'fx-bg-card',
    '#111214': 'fx-bg-card',
    '#111827': 'fx-bg-card',
    '#1a1a1a': 'fx-bg-card',
    '#1a1a2e': 'fx-bg-surface2',
    '#1e293b': 'fx-bg-surface2',
    '#0f172a': 'fx-bg-deep',
    '#0d1117': 'fx-bg-deep',
    '#16213e': 'fx-bg-deep',
    '#222': 'fx-bg-surface',
    '#222222': 'fx-bg-surface',
    # Light surfaces
    '#f8fafc': 'fx-bg-surface2',
    '#f1f5f9': 'fx-bg-body',
    '#ffffff': 'fx-bg-card',
    '#fff': 'fx-bg-card',
    '#f9f7f0': 'fx-bg-card',
    # Semantic
    '#ef4444': 'fx-bg-red',
    '#dc2626': 'fx-bg-red',
    '#22c55e': 'fx-bg-green',
    '#10b981': 'fx-bg-green',
    '#c9a84c': 'fx-bg-gold',
    '#c8a24e': 'fx-bg-gold',
    '#3b82f6': 'fx-bg-blue',
    '#f59e0b': 'fx-bg-amber',
    '#fef2f2': 'fx-bg-red-dim',
}

FONT_SIZE_MAP = {
    '0.6rem': 'fx-fs-2xs', '.6rem': 'fx-fs-2xs',
    '0.65rem': 'fx-fs-xs', '.65rem': 'fx-fs-xs',
    '0.68rem': 'fx-fs-tiny', '.68rem': 'fx-fs-tiny',
    '0.7rem': 'fx-fs-sm', '.7rem': 'fx-fs-sm',
    '0.72rem': 'fx-fs-sm', '.72rem': 'fx-fs-sm',
    '0.75rem': 'fx-fs-caption', '.75rem': 'fx-fs-caption',
    '0.78rem': 'fx-fs-body-sm', '.78rem': 'fx-fs-body-sm',
    '0.8rem': 'fx-fs-compact', '.8rem': 'fx-fs-compact',
    '0.82rem': 'fx-fs-note', '.82rem': 'fx-fs-note',
    '0.85rem': 'fx-fs-base', '.85rem': 'fx-fs-base',
    '0.88rem': 'fx-fs-body', '.88rem': 'fx-fs-body',
    '0.9rem': 'fx-fs-md', '.9rem': 'fx-fs-md',
    '0.95rem': 'fx-fs-normal', '.95rem': 'fx-fs-normal',
    '1rem': 'fx-fs-lg',
    '1.1rem': 'fx-fs-xl',
    '1.2rem': 'fx-fs-2xl',
    '1.3rem': 'fx-fs-3xl',
    '1.4rem': 'fx-fs-4xl',
    '1.5rem': 'fx-fs-5xl',
    '2rem': 'fx-fs-icon',
    '3rem': 'fx-fs-hero',
}

FONT_WEIGHT_MAP = {
    '400': 'fx-fw-normal',
    '500': 'fx-fw-medium',
    '600': 'fx-fw-semibold',
    '700': 'fx-fw-bold',
    '800': 'fx-fw-800',
    'normal': 'fx-fw-normal',
    'bold': 'fx-fw-bold',
}

# ═══════════════════════════════════════════════════════════════
# SIMPLE PROPERTY PATTERNS (standalone style="property:value")
# ═══════════════════════════════════════════════════════════════

SIMPLE_REPLACEMENTS = {
    'cursor:pointer': 'fx-pointer',
    'cursor: pointer': 'fx-pointer',
    'text-decoration:none': 'fx-no-underline',
    'text-decoration: none': 'fx-no-underline',
    'text-align:center': 'text-center',
    'text-align: center': 'text-center',
    'text-align:right': 'text-end',
    'text-align: right': 'text-end',
    'display:none': 'fx-hidden',
    'display: none': 'fx-hidden',
    'display:flex': 'd-flex',
    'display: flex': 'd-flex',
    'flex-wrap:wrap': 'fx-flex-wrap',
    'flex-wrap: wrap': 'fx-flex-wrap',
    'width:100%': 'fx-w-full',
    'width: 100%': 'fx-w-full',
    'border:none': 'fx-border-none',
    'border: none': 'fx-border-none',
    'opacity:0.5': 'fx-opacity-50',
    'opacity: 0.5': 'fx-opacity-50',
    'opacity:.5': 'fx-opacity-50',
    'opacity:0.7': 'fx-opacity-70',
    'opacity: 0.7': 'fx-opacity-70',
    'opacity:.7': 'fx-opacity-70',
    'overflow-x:auto': 'fx-scroll-x',
    'overflow-x: auto': 'fx-scroll-x',
}


def normalize_color(color):
    """Normalize color to lowercase, expand 3-char hex."""
    color = color.strip().lower()
    # Expand 3-char hex: #abc → #aabbcc
    if re.match(r'^#[0-9a-f]{3}$', color):
        return '#' + color[1]*2 + color[2]*2 + color[3]*2
    return color


def extract_style_props(style_str):
    """Parse style string into list of (property, value) tuples."""
    props = []
    for part in style_str.split(';'):
        part = part.strip()
        if ':' in part:
            prop, _, val = part.partition(':')
            props.append((prop.strip().lower(), val.strip()))
    return props


def find_class_for_prop(prop, val):
    """Map a single CSS property:value to a utility class, or None."""
    key = f"{prop}:{val}"
    key_nospace = key.replace(' ', '')

    # Simple replacements
    for pattern, cls in SIMPLE_REPLACEMENTS.items():
        if pattern.replace(' ', '') == key_nospace:
            return cls

    # Color
    if prop == 'color':
        norm = normalize_color(val)
        return TEXT_COLOR_MAP.get(norm) or TEXT_COLOR_MAP.get(val.lower())

    # Background / background-color
    if prop in ('background', 'background-color'):
        # Only handle simple color values, not gradients etc.
        if val.startswith('#') or val.startswith('rgb'):
            if val.startswith('#'):
                norm = normalize_color(val)
                return BG_COLOR_MAP.get(norm) or BG_COLOR_MAP.get(val.lower())

    # Font-size
    if prop == 'font-size':
        return FONT_SIZE_MAP.get(val.lower())

    # Font-weight
    if prop == 'font-weight':
        return FONT_WEIGHT_MAP.get(val.lower())

    # Border-radius common patterns
    if prop == 'border-radius':
        val_l = val.lower()
        if val_l in ('50%',):
            return 'fx-rounded-circle'
        if val_l in ('9999px', '999px', '100px'):
            return 'fx-rounded-full'
        if val_l in ('6px', '4px', '5px'):
            return 'fx-rounded-sm'
        if val_l in ('8px', '10px', '12px'):
            return 'fx-rounded'
        if val_l in ('14px', '16px'):
            return 'fx-rounded-lg'
        if val_l in ('20px', '24px'):
            return 'fx-rounded-xl'

    # Gap
    if prop == 'gap':
        gap_map = {
            '4px': 'fx-gap-1', '8px': 'fx-gap-2', '10px': 'fx-gap-3',
            '12px': 'fx-gap-3', '16px': 'fx-gap-4', '20px': 'fx-gap-5',
            '24px': 'fx-gap-6', '32px': 'fx-gap-8',
            '6px': 'fx-gap-2',
        }
        return gap_map.get(val.lower())

    return None


def process_style_attr(style_value):
    """
    Process a style="" attribute value.
    Returns (new_classes, remaining_styles).
    """
    props = extract_style_props(style_value)
    classes = []
    remaining = []

    for prop, val in props:
        cls = find_class_for_prop(prop, val)
        if cls:
            if cls not in classes:
                classes.append(cls)
        else:
            remaining.append(f"{prop}:{val}")

    return classes, remaining


def process_tag(match):
    """Process a single HTML tag match."""
    full_tag = match.group(0)

    # Skip Django template tags, script tags, SVG
    if full_tag.startswith('{{') or full_tag.startswith('{%'):
        return full_tag
    tag_name = re.match(r'<(\w+)', full_tag)
    if tag_name and tag_name.group(1).lower() in ('script', 'svg', 'path', 'circle', 'rect', 'line', 'polygon'):
        return full_tag

    # Find style attribute
    style_match = re.search(r'\bstyle\s*=\s*"([^"]*)"', full_tag)
    if not style_match:
        return full_tag

    style_value = style_match.group(1)
    new_classes, remaining = process_style_attr(style_value)

    if not new_classes:
        return full_tag  # Nothing to replace

    result = full_tag

    # Update or add class attribute
    class_match = re.search(r'\bclass\s*=\s*"([^"]*)"', result)
    new_class_str = ' '.join(new_classes)

    if class_match:
        existing = class_match.group(1).strip()
        # Don't add duplicate classes
        existing_set = set(existing.split())
        new_to_add = [c for c in new_classes if c not in existing_set]
        if not new_to_add:
            # Classes already there, just clean style
            pass
        else:
            merged = existing + ' ' + ' '.join(new_to_add)
            result = result[:class_match.start(1)] + merged + result[class_match.end(1):]
    else:
        # Insert class before style
        style_start = result.find('style=')
        result = result[:style_start] + f'class="{new_class_str}" ' + result[style_start:]

    # Update or remove style attribute (re-find since positions may have shifted)
    if remaining:
        new_style = ';'.join(remaining)
        result = re.sub(r'\bstyle\s*=\s*"[^"]*"', f'style="{new_style}"', result)
    else:
        result = re.sub(r'\s*\bstyle\s*=\s*"[^"]*"', '', result)

    return result


def process_file(filepath, dry_run=False, verbose=False):
    """Process a single HTML file. Returns (changes_count, details)."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        original = f.read()

    # Process all HTML tags with style attributes
    # Match opening tags: <tag ... style="..." ...>
    pattern = re.compile(r'<[a-zA-Z][^>]*\bstyle\s*=\s*"[^"]*"[^>]*>', re.DOTALL)
    result = pattern.sub(process_tag, original)

    if result == original:
        return 0, []

    # Count changes
    orig_styles = len(re.findall(r'\bstyle\s*=\s*"', original))
    new_styles = len(re.findall(r'\bstyle\s*=\s*"', result))
    removed = orig_styles - new_styles

    # Count added classes
    orig_fx = len(re.findall(r'fx-\w+', original))
    new_fx = len(re.findall(r'fx-\w+', result))
    added = new_fx - orig_fx

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(result)

    details = []
    if verbose:
        details.append(f"  Styles fully removed: {removed}")
        details.append(f"  Utility classes added: {added}")

    return removed + added, details


def main():
    parser = argparse.ArgumentParser(description='Fenix inline style migrator')
    parser.add_argument('--dry-run', action='store_true', help='Show what would change without modifying files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show per-file details')
    parser.add_argument('--path', default='templates/', help='Path to scan (default: templates/)')
    args = parser.parse_args()

    base_dir = Path('/var/www/fina-connect')
    scan_path = base_dir / args.path

    if not scan_path.exists():
        print(f"Error: {scan_path} does not exist")
        sys.exit(1)

    # Collect HTML files
    html_files = sorted(scan_path.rglob('*.html'))

    total_changes = 0
    files_changed = 0
    stats = defaultdict(int)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Scanning {len(html_files)} HTML files in {scan_path}...")
    print("=" * 60)

    for filepath in html_files:
        changes, details = process_file(filepath, dry_run=args.dry_run, verbose=args.verbose)
        if changes > 0:
            files_changed += 1
            total_changes += changes
            rel = filepath.relative_to(base_dir)
            if args.verbose:
                print(f"\n{rel}: {changes} changes")
                for d in details:
                    print(d)
            elif changes > 5:
                print(f"  {rel}: {changes} changes")

    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if args.dry_run else ''}COMPLETE")
    print(f"  Files scanned:  {len(html_files)}")
    print(f"  Files changed:  {files_changed}")
    print(f"  Total changes:  {total_changes}")

    if args.dry_run:
        print("\nRun without --dry-run to apply changes.")


if __name__ == '__main__':
    main()
