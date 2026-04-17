# AI GENERATED: Dodati /health endpoint za monitoring
# Priority: HIGH
# Issue: Nema health checka
# Generated: 2026-04-16T23:30:23.967371


# HEALTH CHECK ENDPOINT - Dodaj u evalidator/urls.py
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError

def health_check(request):
    """
    Health check endpoint za monitoring
    """
    health = {
        'status': 'healthy',
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'checks': {}
    }
    
    # Provjera baze
    try:
        connections['default'].cursor()
        health['checks']['database'] = 'ok'
    except OperationalError:
        health['status'] = 'unhealthy'
        health['checks']['database'] = 'error'
    
    # Provjera diska
    import shutil
    disk = shutil.disk_usage('/')
    health['checks']['disk'] = {
        'free_gb': round(disk.free / (1024**3), 2),
        'percent_free': round(disk.free / disk.total * 100, 2)
    }
    
    return JsonResponse(health)

# Dodaj u urlpatterns:
# path('health/', health_check),
