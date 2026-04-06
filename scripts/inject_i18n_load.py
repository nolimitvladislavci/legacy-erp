"""
Add {% load i18n %} to templates that extend base.html but don't have it.
This makes them i18n-ready so {% trans %} tags will work.
"""
import os
import re

TEMPLATES_DIR = "/var/www/fina-connect/templates"
SKIP_DIRS = {"worktime_ARCHIVED", "__pycache__"}

count = 0
skipped = 0

for root, dirs, files in os.walk(TEMPLATES_DIR):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        if not fname.endswith(".html"):
            continue
        path = os.path.join(root, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            continue
        
        # Skip if already has i18n
        if "{% load i18n" in content:
            continue
        
        # Must have extends or be a standalone template with user-facing text
        has_extends = re.search(r'{%\s*extends\s', content)
        
        if has_extends:
            # Add {% load i18n %} right after the {% extends ... %} line
            content = re.sub(
                r'({%\s*extends\s+[^%]+%})\s*\n',
                r'\1\n{% load i18n %}\n',
                content,
                count=1,
            )
        else:
            # Standalone template — add at top
            content = "{% load i18n %}\n" + content
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        count += 1

print(f"Injected {{% load i18n %}} into {count} templates")
