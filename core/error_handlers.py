"""
core/error_handlers.py — Custom error handlers (404, 500)
Izdvojeno iz urls.py da se izbjegne circular import pri test DB kreaciji.
"""
from django.shortcuts import render


def custom_404_handler(request, exception=None):
    """404 → renders 404 stranica. NIKAD redirect (izaziva beskonačnu petlju)."""
    return render(request, '404.html', status=404)


def custom_500_handler(request):
    """500 → renders 500 stranica."""
    return render(request, '500.html', status=500)
