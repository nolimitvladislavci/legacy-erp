"""
add_company_manager.py — Adds CompanyManager to all models that have a company FK but lack it.
Skips: models that already have objects = CompanyManager(), child models without company FK.
"""
import os
import re

ROOT = '/var/www/fina-connect'
SKIP_DIRS = {'venv', 'migrations', 'backups', '__pycache__', '.git'}
IMPORT_LINE = 'from core.managers import CompanyManager'

# Models that should NOT get CompanyManager (admin-only, lookup tables, etc.)
SKIP_MODELS = {
    'Company', 'NKDCode', 'Level', 'Country', 'BusinessType', 'Currency',
    'FiscalSystem', 'TaxRate', 'WorkflowType', 'ServiceTemplate',
    'PricingPlan', 'PromoCode',  # registration lookup
    'AccountType',  # TextChoices, not a model
}

def find_models_files():
    results = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname == 'models.py':
                results.append(os.path.join(dirpath, fname))
    return sorted(results)

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')

    # Find all model classes with company FK but no CompanyManager
    # Strategy: find class definitions, check if they have company FK within class body,
    # and check if they already have objects = CompanyManager()

    changes = []
    i = 0
    while i < len(lines):
        # Match class definition
        m = re.match(r'^class (\w+)\(', lines[i])
        if m:
            class_name = m.group(1)
            class_start = i

            if class_name in SKIP_MODELS:
                i += 1
                continue

            # Find the class body (until next class or end of file)
            indent = None
            has_company_fk = False
            has_company_manager = False
            last_field_line = None
            first_field_line = None

            j = i + 1
            while j < len(lines):
                line = lines[j]

                # Detect end of class (new class at same indent or less, or EOF)
                if re.match(r'^class \w+\(', line) or (line.strip() and not line.startswith(' ') and not line.startswith('\t') and j > i + 1):
                    break

                stripped = line.strip()
                if stripped and indent is None and (line.startswith('    ') or line.startswith('\t')):
                    indent = len(line) - len(line.lstrip())

                if 'company = models.ForeignKey' in line or 'company=models.ForeignKey' in line:
                    has_company_fk = True

                if 'objects = CompanyManager()' in line or 'objects=CompanyManager()' in line:
                    has_company_manager = True

                # Track field lines (for insertion point)
                if re.search(r'^\s+([\w]+)\s*=\s*models\.(ForeignKey|CharField|TextField|IntegerField|DecimalField|BooleanField|DateField|DateTimeField|PositiveIntegerField|PositiveSmallIntegerField|UUIDField|JSONField|EmailField|FileField|ImageField|GenericIPAddressField|SlugField|URLField|SmallIntegerField|BigIntegerField|FloatField|OneToOneField|ManyToManyField)', line):
                    if first_field_line is None:
                        first_field_line = j
                    last_field_line = j
                    # Skip multi-line field definitions
                    while j < len(lines) - 1 and lines[j].rstrip().endswith(',') and not ')' in lines[j]:
                        j += 1
                    # Find closing paren
                    while j < len(lines) - 1 and ')' not in lines[j]:
                        j += 1
                    last_field_line = j

                j += 1

            if has_company_fk and not has_company_manager and last_field_line is not None:
                # Determine indent (default 4 spaces)
                ind = ' ' * (indent or 4)
                changes.append({
                    'class': class_name,
                    'insert_after': last_field_line,
                    'indent': ind,
                })

            i = j
        else:
            i += 1

    if not changes:
        return 0

    # Check if import already exists
    has_import = IMPORT_LINE in content

    # Apply changes in reverse order (to preserve line numbers)
    new_lines = list(lines)
    for change in reversed(changes):
        insert_line = change['insert_after']
        ind = change['indent']
        # Insert after the last field line
        # Find the closing paren of that field if it's multi-line
        while insert_line < len(new_lines) - 1 and ')' not in new_lines[insert_line]:
            insert_line += 1

        new_lines.insert(insert_line + 1, f'{ind}objects = CompanyManager()')

    # Add import if needed
    if not has_import:
        # Find good place to insert import (after other imports)
        insert_idx = 0
        for idx, line in enumerate(new_lines):
            if line.startswith('from ') or line.startswith('import '):
                insert_idx = idx + 1
        new_lines.insert(insert_idx, IMPORT_LINE)

    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines))

    app = filepath.replace(ROOT + '/', '').replace('/models.py', '')
    for c in changes:
        print(f'  ✅ {app}.{c["class"]} — CompanyManager added')

    return len(changes)

def main():
    files = find_models_files()
    total = 0
    for f in files:
        count = process_file(f)
        total += count
    print(f'\n{"="*50}')
    print(f'Total: {total} models patched with CompanyManager')

if __name__ == '__main__':
    main()
