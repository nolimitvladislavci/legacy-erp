import os

def run():
    print("--- POKREĆEM INTEGRACIJU ACCOUNTS V2 ---")
    
    # 1. URLs.py - Definiranje profesionalnih ruta
    urls_content = """from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.UserListView.as_view(), name='user_list'),
    path('<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('<int:pk>/toggle-status/', views.toggle_user_status, name='toggle_status'),
    path('api/stats/', views.api_user_stats, name='api_stats'),
]
"""
    
    # 2. Views.py - Logika s podrškom za EmployeeProfile
    views_content = """from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

class UserListView(ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        return User.objects.select_related('employeeprofile').order_by('-last_login')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.is_active = 'is_active' in request.POST
        user.save()
        messages.success(request, f'Korisnik {user.username} uspješno ažuriran.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {'target_user': user})

@login_required
def toggle_user_status(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.user.is_superuser:
        user.is_active = not user.is_active
        user.save()
        status = "aktiviran" if user.is_active else "deaktiviran"
        messages.info(request, f'Korisnik {user.username} je {status}.')
    return redirect('accounts:user_list')

def api_user_stats(request):
    data = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'staff': User.objects.filter(is_staff=True).count(),
    }
    return JsonResponse(data)
"""

    # Spremamo datoteke
    base_path = '/var/www/fina-connect/accounts/'
    with open(os.path.join(base_path, 'urls.py'), 'w') as f: f.write(urls_content)
    with open(os.path.join(base_path, 'views.py'), 'w') as f: f.write(views_content)
    
    print("✓ URLs i Views ažurirani.")
    print("--- INTEGRACIJA ZAVRŠENA ---")

if __name__ == "__main__":
    run()
