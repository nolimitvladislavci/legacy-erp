"""
Celery application for LIMIT Connect ERP.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('fina_connect')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
# Eksplicitni import za apps koje autodiscover ne pokupi automatski
app.autodiscover_tasks(['smart_import'])
# Eksplicitni import za nestandardne module
app.autodiscover_tasks(['core.gemini_tasks', 'core.whatsapp_tasks'])


@app.on_after_finalize.connect
def setup_extra_tasks(sender, **kwargs):
    """Import tasks from non-standard module names after app is ready."""
    import importlib
    for mod in ['core.whatsapp_tasks', 'core.gemini_tasks', 'inventory.prediction_tasks']:
        try:
            importlib.import_module(mod)
        except Exception:
            pass


# PDF Vision patch za skenirane fakture
try:
    from core.smart_import_pdf_patch import apply_vision_patch
    apply_vision_patch()
except Exception:
    pass
app.autodiscover_tasks(['marketplace'])
app.autodiscover_tasks(['experiences'])
