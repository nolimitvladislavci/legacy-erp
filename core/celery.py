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
# core.tasks — database_backup, system_test, ai_health (eksplicitno jer autodiscover ponekad ne pokupi)
app.autodiscover_tasks(['core.tasks'])
# Eksplicitni import za nestandardne module
app.autodiscover_tasks(['core.gemini_tasks', 'core.whatsapp_tasks'])


@app.on_after_finalize.connect
def setup_extra_tasks(sender, **kwargs):
    """Import tasks from non-standard module names after app is ready."""
    import importlib
    for mod in ['core.whatsapp_tasks', 'core.gemini_tasks', 'inventory.prediction_tasks']:
        try:
            importlib.import_module(mod)
        except ImportError:
            pass


# PDF Vision patch za skenirane fakture
try:
    from core.smart_import_pdf_patch import apply_vision_patch
    apply_vision_patch()
except ImportError:
    pass
app.autodiscover_tasks(['marketplace'])
app.autodiscover_tasks(['experiences'])
app.autodiscover_tasks(['limit_connect_ai.tasks_doktor'])
app.autodiscover_tasks(['pos.trojstvo_task'])
app.autodiscover_tasks(['limit_connect_ai.tasks_signal'])
app.autodiscover_tasks(['limit_connect_ai.tasks_risk'])
app.autodiscover_tasks(['limit_connect_ai.tasks_opportunity'])
