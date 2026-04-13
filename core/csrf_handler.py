from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def csrf_failure_view(request, reason=''):
    """
    CSRF token istekao ili nedostaje.

    AJAX/fetch → JSON odgovor, JS sam refresha token i resubmita.
    Normalna forma → HTML stranica s auto-retry (bez korisničke radnje).
    """
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.headers.get('Accept', '').startswith('application/json')
        or request.headers.get('HX-Request')
        or request.content_type == 'application/json'
    )

    # AJAX / HTMX → JSON, JS rješava
    if is_ajax:
        new_token = get_token(request)
        return JsonResponse({
            'csrf_error': True,
            'new_token': new_token,
            'message': 'Sigurnosni token osvježen. Pokušajte ponovo.',
        }, status=200)

    # Normalna forma → auto-retry HTML stranica
    referer = request.META.get('HTTP_REFERER', '/')
    new_token = get_token(request)

    html = f"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Osvježavanje sesije — LIMIT Connect</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
     display:flex;align-items:center;justify-content:center;min-height:100vh}}
.box{{background:#1e293b;border:1px solid #334155;border-radius:16px;
      padding:32px 28px;max-width:400px;width:100%;margin:20px;text-align:center}}
.spinner{{width:36px;height:36px;border:3px solid #334155;border-top-color:#c9a84c;
          border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 16px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
h2{{font-size:1rem;font-weight:600;margin-bottom:8px;color:#f1f5f9}}
p{{font-size:.82rem;color:#64748b;margin-bottom:20px;line-height:1.5}}
.btn{{display:inline-block;padding:10px 24px;border-radius:8px;
      background:#c9a84c;color:#0f172a;font-weight:700;font-size:.85rem;
      text-decoration:none;cursor:pointer;border:none}}
</style>
</head>
<body>
<div class="box">
  <div class="spinner"></div>
  <h2>Osvježavanje sesije...</h2>
  <p>Sigurnosni token osvježen. Ponovite unos — ispričavamo se na neugodnosti.</p>
  <noscript>
    <a class="btn" href="{referer}">Kliknite za povratak</a>
  </noscript>
</div>
<script>
// Osvježi CSRF cookie i automatski resubmitaj formu
document.cookie = 'csrftoken={new_token};path=/;SameSite=Lax;Secure';
setTimeout(function() {{
  // Pokušaj resubmit ako browser ima history.back + form data
  // Inače redirect na referer
  window.location.href = '{referer}';
}}, 800);
</script>
</body>
</html>"""
    return HttpResponse(html, status=200)


def csrf_token_view(request):
    """Endpoint za dohvat svježeg CSRF tokena (AJAX)."""
    return JsonResponse({'token': get_token(request)})
