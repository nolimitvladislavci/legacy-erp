import os

def build_full_system():
    # --- VIEWS.PY (Sve funkcije koje URL-ovi traže) ---
    views_path = 'core/views.py'
    views_content = """from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.apps import apps
from django.db.models import Sum
from accounts.models import UserProfile
from accounts.auth_models import LoginAttempt

def get_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'worker'})
    return profile

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        u = request.POST.get('username', '').strip().lower()
        p = request.POST.get('password', '')
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            return redirect('dashboard')
    return render(request, 'login.html')

@login_required
def dashboard_router(request):
    p = get_user_profile(request.user)
    if request.user.is_superuser or p.role == 'superadmin':
        return redirect('superadmin_dashboard')
    return redirect('ts_worker')

@login_required
def superadmin_dashboard(request):
    if not request.user.is_superuser: return redirect('dashboard')
    Project = apps.get_model('projects', 'Project')
    TimeEntry = apps.get_model('worktime', 'TimeEntry')
    
    context = {
        'total_users': User.objects.count(),
        'projects': Project.objects.all().order_by('-created_at')[:10],
        'total_hours': TimeEntry.objects.aggregate(Sum('duration_hours'))['duration_hours__sum'] or 0,
        'recent_logins': LoginAttempt.objects.order_by('-attempted_at')[:10],
    }
    return render(request, 'dashboards/superadmin.html', context)

@login_required
def company_dashboard(request): return render(request, 'dashboards/company_admin.html')

@login_required
def manager_dashboard(request): return redirect('ts_worker')

@login_required
def worker_dashboard(request): return redirect('ts_worker')

@login_required
def investor_dashboard(request): return render(request, 'dashboards/investor.html')

@login_required
def partner_dashboard(request): return render(request, 'dashboards/partner.html')

def logout_view(request):
    logout(request)
    return redirect('login')
"""
    with open(views_path, 'w') as f: f.write(views_content)
    print("Views.py is now COMPLETE and compatible with urls.py.")

if __name__ == "__main__":
    build_full_system()
