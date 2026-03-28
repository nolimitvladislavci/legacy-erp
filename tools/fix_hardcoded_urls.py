#!/usr/bin/env python3
"""
BORG TOOL: fix_hardcoded_urls.py
═══════════════════════════════════════════════════════
Skenira HTML template-e i zamjenjuje hardkodirane URL-ove
sa Django {% url %} tagovima.

Pokretanje:
  python3 tools/fix_hardcoded_urls.py --scan       # samo izvjestaj
  python3 tools/fix_hardcoded_urls.py --fix         # popravi sve
"""
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path('/var/www/fina-connect')
TEMPLATE_DIRS = [
    BASE_DIR / 'templates',
]
# Dodaj app template dirs
for app_dir in BASE_DIR.iterdir():
    t = app_dir / 'templates'
    if t.is_dir():
        TEMPLATE_DIRS.append(t)

SKIP_DIRS = {'venv', 'node_modules', '.git', '__pycache__', 'backups'}

# ═══════════════════════════════════════════════════════════════
# Mapiranje: hardkodirani URL → Django {% url %} tag
# ═══════════════════════════════════════════════════════════════
# Samo sigurne zamjene — URL-ovi koji sigurno postoje
URL_MAP = {
    # Auth
    'href="/login/"':        "href=\"{% url 'login' %}\"",
    'href="/register/"':     "href=\"{% url 'accounts:quick_register' %}\"",
    'action="/login/"':      "action=\"{% url 'login' %}\"",
    "href='/login/'":        "href=\"{% url 'login' %}\"",
    "href='/register/'":     "href=\"{% url 'accounts:quick_register' %}\"",

    # Dashboard
    'href="/dashboard/"':    "href=\"{% url 'dashboard' %}\"",
    'href="/"':              "href=\"{% url 'dashboard' %}\"",

    # Core modules
    'href="/pos/"':          "href=\"{% url 'pos:terminal' %}\"",
    'href="/partners/"':     "href=\"{% url 'partners:partner_list' %}\"",
    'href="/invoicing/"':    "href=\"{% url 'invoicing:invoice_list' %}\"",
    'href="/inventory/"':    "href=\"{% url 'inventory:item_list' %}\"",
    'href="/worktime/"':     "href=\"{% url 'worktime:dashboard' %}\"",
    'href="/appointments/"': "href=\"{% url 'appointments:booking_list' %}\"",
    'href="/ai/"':           "href=\"{% url 'ai_cockpit' %}\"",
    'href="/smart-import/"': "href=\"{% url 'smart_import:upload' %}\"",

    # Actions
    'action="/smart-import/"': "action=\"{% url 'smart_import:upload' %}\"",
}

# Pattern za href="/nesto/" koji NIJE {% url %}
HARDCODED_PATTERN = re.compile(
    r'(?:href|action)=["\']/((?!static|media|cdn|i18n|admin|__debug__|favicon|manifest|sw\.js|offline)[a-z0-9_/-]+)["\']',
    re.IGNORECASE
)


def scan_file(filepath):
    """Skenira fajl za hardkodirane URL-ove."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []

    hits = []
    for i, line in enumerate(content.split('\n'), 1):
        # Skip lines that already use {% url %}
        if '{% url' in line or '{%url' in line:
            continue
        # Skip comments
        if line.strip().startswith('{#') or line.strip().startswith('<!--'):
            continue

        for match in HARDCODED_PATTERN.finditer(line):
            url = '/' + match.group(1)
            full_match = match.group(0)
            hits.append((i, url, full_match))

    return hits


def fix_file(filepath, dry_run=False):
    """Zamjenjuje poznate hardkodirane URL-ove sa {% url %} tagovima."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return 0

    original = content
    changes = 0

    for old, new in URL_MAP.items():
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            changes += count

    if changes > 0 and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return changes


def main():
    import argparse
    parser = argparse.ArgumentParser(description='BORG: Fix hardcoded URLs in templates')
    parser.add_argument('--scan', action='store_true', help='Samo skeniraj')
    parser.add_argument('--fix', action='store_true', help='Popravi poznate URL-ove')
    parser.add_argument('--top', type=int, default=30, help='Top N za prikaz')
    args = parser.parse_args()

    if not args.scan and not args.fix:
        args.scan = True

    all_files = []
    for td in TEMPLATE_DIRS:
        all_files.extend(td.rglob('*.html'))

    # Deduplicate
    all_files = list(set(all_files))

    results = {}  # url → [(file, line)]
    total_hits = 0
    files_with_hits = set()

    for f in all_files:
        parts = f.relative_to(BASE_DIR).parts
        if any(p in SKIP_DIRS for p in parts):
            continue

        hits = scan_file(f)
        if hits:
            files_with_hits.add(str(f.relative_to(BASE_DIR)))
            for lineno, url, full in hits:
                total_hits += 1
                if url not in results:
                    results[url] = []
                results[url].append((str(f.relative_to(BASE_DIR)), lineno, full))

    # Sort by frequency
    sorted_urls = sorted(results.items(), key=lambda x: -len(x[1]))

    print(f"\n{'='*60}")
    print(f"BORG SCAN: Hardcoded URLs in templates")
    print(f"{'='*60}")
    print(f"Ukupno hardkodiranih URL-ova: {total_hits}")
    print(f"Ukupno fajlova:               {len(files_with_hits)}")
    print(f'Poznati za auto-fix:          {len(URL_MAP)} mapiranja')
    print(f"{'='*60}\n")

    for url, locations in sorted_urls[:args.top]:
        fixable = any(url in k for k in URL_MAP)
        marker = " ✓ AUTO-FIX" if fixable else ""
        print(f"  {len(locations):3d}×  {url}{marker}")
        for fpath, line, full in locations[:3]:
            print(f"        {fpath}:{line}")
        if len(locations) > 3:
            print(f"        ... +{len(locations)-3} više")

    if args.fix:
        print(f"\n{'='*60}")
        print(f"FIXING known URLs...")
        print(f"{'='*60}\n")

        fixed_total = 0
        for f in all_files:
            parts = f.relative_to(BASE_DIR).parts
            if any(p in SKIP_DIRS for p in parts):
                continue
            n = fix_file(f)
            if n:
                print(f"  FIXED {n:3d}  {f.relative_to(BASE_DIR)}")
                fixed_total += n

        print(f"\n{'='*60}")
        print(f"Popravljeno: {fixed_total} hardkodiranih URL-ova")
        print(f"{'='*60}")


if __name__ == '__main__':
    sys.exit(main())
