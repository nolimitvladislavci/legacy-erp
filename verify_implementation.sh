#!/bin/bash

echo "========================================"
echo "BOXGRAM SOCIAL IMPORT VERIFICATION"
echo "========================================"

# Check files exist
echo ""
echo "[1] File Structure Check:"
files=(
    "boxgram/services/__init__.py"
    "boxgram/services/social_import.py"
    "boxgram/views_social.py"
    "boxgram/templates/boxgram/import_wizard.html"
    "docs/BOXGRAM_META_APP_REVIEW.md"
)

for file in "${files[@]}"; do
    if [ -f "/var/www/fina-connect/$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file (MISSING)"
    fi
done

# Check imports
echo ""
echo "[2] Python Imports Check:"
/var/www/fina-connect/venv/bin/python << 'PYEOF'
import sys
sys.path.insert(0, '/var/www/fina-connect')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    import django
    django.setup()
    
    from boxgram.services.social_import import (
        detect_platform, fetch_oembed, create_social_import, ImportPreview
    )
    print("  ✓ social_import module")
    
    from boxgram.views_social import (
        import_url_preview, import_url_confirm, import_inbox, import_reject
    )
    print("  ✓ views_social module")
    
    from boxgram.tasks import retry_fetch_social_import
    print("  ✓ tasks.retry_fetch_social_import")
    
except ImportError as e:
    print(f"  ✗ Import error: {e}")
PYEOF

# Check configuration
echo ""
echo "[3] Settings Check:"
/var/www/fina-connect/venv/bin/python << 'PYEOF'
import sys
sys.path.insert(0, '/var/www/fina-connect')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    import django
    django.setup()
    
    from django.conf import settings
    
    if hasattr(settings, 'INSTAGRAM_OEMBED_TOKEN'):
        print("  ✓ INSTAGRAM_OEMBED_TOKEN setting")
    else:
        print("  ✗ INSTAGRAM_OEMBED_TOKEN missing")
        
    if 'boxgram.tasks.*' in settings.CELERY_TASK_ROUTES:
        print("  ✓ Celery task routing configured")
    else:
        print("  ✗ Celery routing not found")
        
except Exception as e:
    print(f"  ✗ Settings error: {e}")
PYEOF

# Check URL patterns
echo ""
echo "[4] URL Routes Check:"
/var/www/fina-connect/venv/bin/python << 'PYEOF'
import sys
sys.path.insert(0, '/var/www/fina-connect')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    import django
    django.setup()
    
    from boxgram.urls import urlpatterns
    
    patterns = [str(p.pattern) for p in urlpatterns]
    routes = [
        'api/boxgram/import/preview/',
        'api/boxgram/import/confirm/',
        'api/boxgram/import/inbox/',
        'api/boxgram/import/<uuid:import_id>/reject/'
    ]
    
    for route in routes:
        if any(route in p for p in patterns):
            print(f"  ✓ {route}")
        else:
            print(f"  ✗ {route} not found")
            
except Exception as e:
    print(f"  ✗ URL check error: {e}")
PYEOF

# Summary
echo ""
echo "========================================"
echo "VERIFICATION COMPLETE"
echo "========================================"
