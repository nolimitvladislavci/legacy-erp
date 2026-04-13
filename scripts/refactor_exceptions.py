#!/usr/bin/env python3
"""
Exception Handling Refactoring Script — DIO 1
Replaces broad `except Exception:` / `except:` with specific exceptions.
Safe: creates .bak backup, validates syntax after changes.
"""
import re
import sys
import ast
import shutil
from pathlib import Path

# ── Mapping: what's in the try block → which exception to use ──
DB_KEYWORDS = {
    '.objects.get(': 'ObjectDoesNotExist',
    '.save()': '(IntegrityError, DatabaseError)',
    '.delete()': '(IntegrityError, DatabaseError)',
    '.objects.create(': '(IntegrityError, DatabaseError)',
    '.objects.update(': 'DatabaseError',
    '.objects.filter(': 'DatabaseError',
    '.objects.all()': 'DatabaseError',
    '.objects.exclude(': 'DatabaseError',
    'bulk_create': '(IntegrityError, DatabaseError)',
    'bulk_update': 'DatabaseError',
    'transaction.atomic': '(IntegrityError, DatabaseError)',
    '.aggregate(': 'DatabaseError',
    '.annotate(': 'DatabaseError',
}

JSON_KEYWORDS = {
    'json.loads': '(json.JSONDecodeError, ValueError)',
    'json.dumps': '(TypeError, ValueError)',
    'request.body': '(json.JSONDecodeError, ValueError)',
    'json.load': '(json.JSONDecodeError, ValueError)',
}

TYPE_KEYWORDS = {
    'int(': '(ValueError, TypeError)',
    'float(': '(ValueError, TypeError)',
    'Decimal(': '(ValueError, TypeError)',
    'uuid.UUID(': 'ValueError',
    'datetime.strptime': 'ValueError',
    'parse_date': 'ValueError',
}

FILE_KEYWORDS = {
    'open(': '(FileNotFoundError, PermissionError, IOError)',
    '.read()': 'IOError',
    '.write()': 'IOError',
    'os.path': 'OSError',
    'shutil.': 'OSError',
    'Path(': 'OSError',
}

HTTP_KEYWORDS = {
    'requests.get': 'requests.RequestException',
    'requests.post': 'requests.RequestException',
    'requests.put': 'requests.RequestException',
    'requests.delete': 'requests.RequestException',
    'urlopen': '(URLError, HTTPError)',
    'httpx.': 'httpx.HTTPError',
}

IMPORT_KEYWORDS = {
    'importlib': 'ImportError',
}

CRYPTO_KEYWORDS = {
    'fernet': 'Exception',
    'decrypt(': 'Exception',
    'encrypt(': 'Exception',
}


def classify_try_block(try_content: str) -> str:
    """Determine the best specific exception for a try block's content."""
    try_lower = try_content.lower()

    # 1. If it's a .get() call, very specific
    if '.objects.get(' in try_content:
        return 'ObjectDoesNotExist'

    # 2. JSON parsing
    for kw, exc in JSON_KEYWORDS.items():
        if kw in try_content:
            return exc

    # 3. Type casting
    for kw, exc in TYPE_KEYWORDS.items():
        if kw in try_content:
            return exc

    # 4. File I/O
    for kw, exc in FILE_KEYWORDS.items():
        if kw in try_content:
            return exc

    # 5. HTTP
    for kw, exc in HTTP_KEYWORDS.items():
        if kw in try_content:
            return exc

    # 6. Import
    for kw, exc in IMPORT_KEYWORDS.items():
        if kw in try_content:
            return exc

    # 7. DB operations (broadest category)
    for kw, exc in DB_KEYWORDS.items():
        if kw in try_content:
            return exc

    # 8. Crypto
    for kw, exc in CRYPTO_KEYWORDS.items():
        if kw in try_lower:
            return exc

    # If we can't classify, keep Exception but add TODO comment on separate line
    return 'Exception'


def needs_import(exception_str: str) -> set:
    """Determine what imports are needed for the exception type."""
    imports = set()
    if 'ObjectDoesNotExist' in exception_str:
        imports.add('from django.core.exceptions import ObjectDoesNotExist')
    if 'IntegrityError' in exception_str or 'DatabaseError' in exception_str:
        imports.add('from django.db import IntegrityError, DatabaseError')
    if 'json.JSONDecodeError' in exception_str:
        imports.add('import json')
    if 'requests.RequestException' in exception_str:
        imports.add('import requests')
    return imports


def refactor_file(filepath: str, dry_run: bool = False) -> dict:
    """Refactor a single Python file's exception handling."""
    path = Path(filepath)
    if not path.exists():
        return {'error': f'File not found: {filepath}'}

    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    original = ''.join(lines)
    changes = []
    needed_imports = set()
    new_lines = list(lines)
    offset = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Match broad except patterns
        is_bare = stripped == 'except:'
        is_broad = stripped.startswith('except Exception')
        if not (is_bare or is_broad):
            continue

        # Find indent
        indent = line[:len(line) - len(line.lstrip())]

        # Scan backward to find try:
        try_start = i - 1
        while try_start >= 0:
            ts = lines[try_start].strip()
            ti = lines[try_start][:len(lines[try_start]) - len(lines[try_start].lstrip())]
            if ts == 'try:' and len(ti) <= len(indent):
                break
            try_start -= 1

        if try_start < 0:
            continue

        # Collect try block content
        try_content = ''.join(lines[try_start + 1:i])

        # Classify
        specific_exc = classify_try_block(try_content)

        # If still generic Exception, skip (no improvement)
        if specific_exc == 'Exception':
            continue

        # Build the new except line
        has_as = 'except Exception as' in stripped
        if has_as:
            var_match = re.search(r'as\s+(\w+)', stripped)
            var_name = var_match.group(1) if var_match else 'e'
            new_except = f'{indent}except {specific_exc} as {var_name}:\n'
        else:
            new_except = f'{indent}except {specific_exc}:\n'

        # Track needed imports
        needed_imports.update(needs_import(specific_exc))

        # Record change
        adj_i = i + offset
        old_stripped = new_lines[adj_i].strip()
        new_stripped = new_except.strip()
        if old_stripped != new_stripped:
            changes.append({
                'line': i + 1,
                'old': lines[i].rstrip(),
                'new': new_except.rstrip(),
                'category': specific_exc
            })
            new_lines[adj_i] = new_except

    if not changes:
        return {'file': filepath, 'changes': 0}

    # Add needed imports at the top of the file
    import_lines = []
    existing_content = original
    for imp in sorted(needed_imports):
        if imp not in existing_content:
            import_lines.append(imp + '\n')

    if import_lines:
        insert_at = 0
        for j, line in enumerate(new_lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_at = j + 1
            elif insert_at > 0 and line.strip() and not line.startswith('#'):
                break

        for k, imp_line in enumerate(import_lines):
            new_lines.insert(insert_at + k, imp_line)
            offset += 1

    new_content = ''.join(new_lines)

    # Validate syntax
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {'file': filepath, 'error': f'Syntax error: {e}', 'changes': len(changes)}

    if not dry_run:
        shutil.copy2(path, str(path) + '.exc_bak')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return {
        'file': filepath,
        'changes': len(changes),
        'imports_added': len(import_lines),
        'details': changes[:5],
        'dry_run': dry_run
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python refactor_exceptions.py <file_or_dir> [--dry-run]")
        sys.exit(1)

    target = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    path = Path(target)
    if path.is_file():
        result = refactor_file(str(path), dry_run=dry_run)
        print(f"{'[DRY RUN] ' if dry_run else ''}{result['file']}: {result.get('changes', 0)} changes")
        if 'error' in result:
            print(f"  ERROR: {result['error']}")
        for d in result.get('details', []):
            print(f"  L{d['line']}: {d['category']}")
    elif path.is_dir():
        total = 0
        errors = 0
        for py_file in sorted(path.rglob('*.py')):
            if 'venv' in str(py_file) or '__pycache__' in str(py_file) or 'migrations' in str(py_file):
                continue
            if 'backups' in str(py_file):
                continue
            result = refactor_file(str(py_file), dry_run=dry_run)
            if result.get('changes', 0) > 0:
                total += result['changes']
                status = 'OK' if 'error' not in result else 'ERR'
                print(f"{'[DRY RUN] ' if dry_run else ''}[{status}] {result['file']}: {result['changes']} changes, {result.get('imports_added', 0)} imports")
                if 'error' in result:
                    print(f"  ERROR: {result['error']}")
                    errors += 1
        print(f"\nTotal: {total} changes, {errors} errors")
    else:
        print(f"Not found: {target}")
        sys.exit(1)
