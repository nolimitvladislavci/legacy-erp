import os

def upgrade():
    base_dir = '/var/www/fina-connect'
    
    # 1. Definiranje sadržaja datoteka
    files = {
        'accounts/urls.py': """from django.urls import path
from . import views
app_name = 'accounts'
urlpatterns = [
    path('', views.UserListView.as_view(), name='user_list'),
    path('<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('<int:pk>/reset-password/', views.reset_password_request, name='reset_password'),
    path('<int:pk>/toggle/', views.toggle_user_status, name='toggle_status'),
]""",

        'accounts/views.py': """from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm

class UserListView(ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    def get_queryset(self):
        return User.objects.select_related('employeeprofile').order_by('-last_login')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.is_active = 'is_active' in request.POST
        user.is_staff = 'is_staff' in request.POST
        user.save()
        messages.success(request, f'Korisnik {user.username} ažuriran.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {'target_user': user})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def reset_password_request(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    form = PasswordResetForm({'email': target_user.email})
    if form.is_valid():
        form.save(request=request, use_https=request.is_secure())
        messages.success(request, f'Reset lozinke poslan na {target_user.email}')
    return redirect('accounts:user_list')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def toggle_user_status(request, pk):
    u = get_object_or_404(User, pk=pk)
    u.is_active = not u.is_active
    u.save()
    return redirect('accounts:user_list')""",
    }

    # 2. Kreiranje mapa i datoteka
    for rel_path, content in files.items():
        full_path = os.path.join(base_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Kreirano: {rel_path}")

    # 3. Osiguranje template-ova (ako ih već nismo kreirali)
    # Ovdje bi išao i sadržaj za user_list.html i user_form.html

if __name__ == "__main__":
    upgrade()
