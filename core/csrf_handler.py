from django.http import HttpResponseRedirect
from django.contrib import messages


def csrf_failure_view(request, reason=''):
    """Umjesto 403 stranice, redirectaj na login s porukom."""
    messages.warning(request, 'Sigurnosni token je istekao. Pokušajte ponovo.')
    referer = request.META.get('HTTP_REFERER', '/login/')
    return HttpResponseRedirect(referer)
