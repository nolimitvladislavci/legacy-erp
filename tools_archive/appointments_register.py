"""
Adds api_booking_register view to appointments/views.py
and api_booking_register URL to appointments/urls.py
"""
import json

VIEWS_FILE = '/var/www/fina-connect/appointments/views.py'
URLS_FILE  = '/var/www/fina-connect/appointments/urls.py'

REGISTER_VIEW = '''

@csrf_exempt
def api_booking_register(request):
    """AJAX registracija novog korisnika za booking portal"""
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        from django.contrib.auth import get_user_model, login
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        User = get_user_model()
        data = json.loads(request.body)
        username  = data.get('username', '').strip()
        email     = data.get('email', '').strip()
        password  = data.get('password', '')
        first     = data.get('first_name', '').strip()
        last      = data.get('last_name', '').strip()

        if not username or not password:
            return JsonResponse({"success": False, "error": "Korisničko ime i lozinka su obavezni."})
        if User.objects.filter(username=username).exists():
            return JsonResponse({"success": False, "error": "Korisničko ime je zauzeto."})
        if email and User.objects.filter(email=email).exists():
            return JsonResponse({"success": False, "error": "Email je već registriran."})
        # Password validation
        try:
            validate_password(password)
        except ValidationError as ve:
            return JsonResponse({"success": False, "error": " ".join(ve.messages)})

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first, last_name=last
        )
        login(request, user)
        return JsonResponse({
            "success": True,
            "email": user.email,
            "full_name": user.get_full_name() or user.username
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
'''

with open(VIEWS_FILE) as f:
    content = f.read()

if 'def api_booking_register' not in content:
    content += REGISTER_VIEW
    with open(VIEWS_FILE, 'w') as f:
        f.write(content)
    print('OK: api_booking_register view added')
else:
    print('SKIP: api_booking_register already exists')

with open(URLS_FILE) as f:
    urls = f.read()

if 'api_booking_register' not in urls:
    urls = urls.replace(
        "    path('api/booking/auth/', views.api_booking_auth_check, name='api_booking_auth_check'),",
        "    path('api/booking/auth/', views.api_booking_auth_check, name='api_booking_auth_check'),\n"
        "    path('api/booking/register/', views.api_booking_register, name='api_booking_register'),"
    )
    with open(URLS_FILE, 'w') as f:
        f.write(urls)
    print('OK: api_booking_register URL added')
else:
    print('SKIP: URL already exists')
