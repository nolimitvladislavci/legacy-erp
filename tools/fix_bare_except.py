#!/usr/bin/env python3
"""
BORG TOOL: fix_bare_except.py
═══════════════════════════════════════════════════════
Skenira Python fajlove i zamjenjuje bare `except:` sa
`except Exception as e:` + logger.error().

Pokretanje:
  python3 tools/fix_bare_except.py --scan          # samo izvjestaj
  python3 tools/fix_bare_except.py --fix            # popravi sve
  python3 tools/fix_bare_except.py --fix --path pos/views.py  # jedan fajl

BORG pravilo: 1803 tihe greske = 1803 potencijalnih katastrofa.
"""
import ast
import sys
import os
import re
from pathlib import Path

# Direktoriji za preskociti
SKIP_DIRS = {'venv', 'node_modules', '.git', '__pycache__', 'migrations', 'backups'}
BASE_DIR = Path('/var/www/fina-connect')


def scan_file(filepath):
    """Vraca listu (lineno, col) svih bare except: u fajlu."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
    except (FileNotFoundError, IOError):
        return []

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:  # bare except:
                hits.append((node.lineno, node.col_offset))
    return hits


def fix_file(filepath, dry_run=False):
    """Zamjenjuje bare except: sa except Exception as e: + logging."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except (FileNotFoundError, IOError):
        return 0

    hits = scan_file(filepath)
    if not hits:
        return 0

    module_name = str(filepath).replace(str(BASE_DIR) + '/', '').replace('/', '.')
    if module_name.endswith('.py'):
        module_name = module_name[:-3]

    # Dodaj import logger ako ne postoji
    has_logger = any('logger' in line and ('getLogger' in line or 'logging' in line) for line in lines)
    need_logger_import = not has_logger

    changes = 0
    # Reverse sort da line numberi ostanu stabilni
    for lineno, col in sorted(hits, reverse=True):
        idx = lineno - 1
        if idx >= len(lines):
            continue

        line = lines[idx]
        # Zamijeni bare except: sa except Exception as e:
        new_line = re.sub(
            r'(\s*)except\s*:',
            r'\1except Exception as e:  # BORG: was bare except',
            line,
            count=1
        )

        if new_line != line:
            # Dodaj logger.error() liniju nakon except
            indent = re.match(r'(\s*)', new_line).group(1)
            body_indent = indent + '    '

            # Provjeri sto je na sljedecoj liniji
            next_idx = idx + 1
            if next_idx < len(lines):
                next_line = lines[next_idx]
                next_stripped = next_line.strip()
                # Ako je vec pass ili nesto kratko, dodaj logging PRIJE
                if next_stripped == 'pass':
                    # Zamijeni pass sa logger
                    lines[next_idx] = body_indent + f'logger.debug("Handled exception in {module_name}:%d: %s", {lineno}, e)  # BORG\n'
                elif next_stripped.startswith('return') or next_stripped.startswith('continue'):
                    # Dodaj logger PRIJE return/continue
                    logger_line = body_indent + f'logger.debug("Exception in {module_name}:%d: %s", {lineno}, e)  # BORG\n'
                    lines.insert(next_idx, logger_line)
                else:
                    # Nemoj dirati body ako vec ima logiku
                    pass

            lines[idx] = new_line
            changes += 1

    if changes > 0 and not dry_run:
        # Dodaj logger import ako treba
        if need_logger_import:
            # Nadi prvu liniju koja nije komentar/docstring/import
            insert_idx = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    insert_idx = i + 1
                elif insert_idx > 0 and stripped and not stripped.startswith('#'):
                    break

            logger_imports = (
                'import logging\n'
                f'logger = logging.getLogger("{module_name}")\n'
            )
            # Provjeri da vec nema import logging
            has_import_logging = any('import logging' in l for l in lines[:insert_idx+5])
            if not has_import_logging:
                lines.insert(insert_idx, logger_imports)
            elif not has_logger:
                # Ima import logging ali nema logger = ...
                for i, line in enumerate(lines[:insert_idx+10]):
                    if 'import logging' in line:
                        # Dodaj logger = nakon importa
                        has_existing = any('logger' in l and 'getLogger' in l for l in lines)
                        if not has_existing:
                            lines.insert(i+1, f'logger = logging.getLogger("{module_name}")\n')
                        break

        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)

    return changes


def main():
    import argparse
    parser = argparse.ArgumentParser(description='BORG: Fix bare except blocks')
    parser.add_argument('--scan', action='store_true', help='Samo skeniraj, ne mijenjaj')
    parser.add_argument('--fix', action='store_true', help='Popravi bare except blokove')
    parser.add_argument('--path', type=str, help='Specifican fajl ili direktorij')
    parser.add_argument('--top', type=int, default=30, help='Top N fajlova za prikaz')
    args = parser.parse_args()

    if not args.scan and not args.fix:
        args.scan = True

    target = BASE_DIR / args.path if args.path else BASE_DIR
    
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob('*.py'))

    results = []
    total_hits = 0

    for f in files:
        # Skip excluded dirs
        parts = f.relative_to(BASE_DIR).parts
        if any(p in SKIP_DIRS for p in parts):
            continue

        hits = scan_file(f)
        if hits:
            rel = str(f.relative_to(BASE_DIR))
            results.append((rel, len(hits), [h[0] for h in hits]))
            total_hits += len(hits)

    # Sort by hit count descending
    results.sort(key=lambda x: -x[1])

    print(f"\n{'='*60}")
    print(f"BORG SCAN: bare except: blokovi")
    print(f"{'='*60}")
    print(f"Ukupno fajlova s bare except: {len(results)}")
    print(f"Ukupno bare except blokova:   {total_hits}")
    print(f"{'='*60}\n")

    for rel, count, linenos in results[:args.top]:
        lines_str = ','.join(str(l) for l in linenos[:8])
        if len(linenos) > 8:
            lines_str += f'... (+{len(linenos)-8})'
        print(f"  {count:3d}  {rel}  (lines: {lines_str})")

    if len(results) > args.top:
        print(f"\n  ... i jos {len(results) - args.top} fajlova")

    if args.fix:
        print(f"\n{'='*60}")
        print(f"FIXING...")
        print(f"{'='*60}\n")

        fixed_total = 0
        for rel, count, _ in results:
            filepath = BASE_DIR / rel
            fixed = fix_file(filepath)
            if fixed:
                print(f"  FIXED {fixed:3d}  {rel}")
                fixed_total += fixed

        print(f"\n{'='*60}")
        print(f"Popravljeno: {fixed_total} bare except blokova u {len([r for r in results if fix_file(BASE_DIR / r[0], dry_run=True)])} fajlova")
        print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
