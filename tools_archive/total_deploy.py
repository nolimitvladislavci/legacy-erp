import os

def build_full_system():
    # --- MODELS.PY (Kompletna struktura s kalkulacijom) ---
    models_path = 'projects/models.py'
    models_content = """from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class Project(models.Model):
    STATUS = [
        ('planning', _('Planiranje')),
        ('active', _('Aktivno')),
        ('paused', _('Pauzirano')),
        ('completed', _('Završeno')),
        ('cancelled', _('Otkazano')),
    ]
    name = models.CharField(max_length=200, verbose_name=_('Naziv projekta'))
    code = models.CharField(max_length=30, unique=True, verbose_name=_('Šifra'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    location = models.CharField(max_length=255, blank=True, verbose_name=_('Lokacija'))
    status = models.CharField(max_length=20, choices=STATUS, default='planning', verbose_name=_('Status'))
    client = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True, related_name='client_projects', verbose_name=_('Klijent/Investitor'))
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Tvrtka'))
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects', verbose_name=_('Voditelj'))
    team = models.ManyToManyField(User, related_name='team_projects', blank=True, verbose_name=_('Tim'))
    start_date = models.DateField(null=True, blank=True, verbose_name=_('Početak'))
    end_date = models.DateField(null=True, blank=True, verbose_name=_('Planirani kraj'))
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name=_('Budžet (EUR)'))
    estimated_hours = models.FloatField(default=0, verbose_name=_('Procjena sati'))
    margin = models.FloatField(default=20.0, verbose_name=_('Marža (%)'))
    is_public = models.BooleanField(default=False, verbose_name=_('Vidljivo klijentu'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_labor_cost(self):
        try:
            from django.apps import apps
            TimeEntry = apps.get_model('worktime', 'TimeEntry')
            total = 0
            entries = TimeEntry.objects.filter(project=self)
            for e in entries:
                rate = getattr(e.user.userprofile, 'hourly_rate', 0) or 0
                total += (float(e.duration_hours) * float(rate))
            return round(total, 2)
        except: return 0

    @property
    def budget_usage_percentage(self):
        cost = self.total_labor_cost
        if self.budget > 0:
            return round((cost / float(self.budget)) * 100, 2)
        return 0

    class Meta:
        verbose_name = _('Projekt')
        verbose_name_plural = _('Projekti')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

class ProjectUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class ProjectPhoto(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='projects/photos/')
    caption = models.CharField(max_length=255, blank=True)
    is_public = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
"""
    with open(models_path, 'w') as f: f.write(models_content)

    # --- VIEWS.PY (Kompletna logika Dashborda i Kalkulatora) ---
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
def logout_view(request):
    logout(request)
    return redirect('login')

# Stub funkcije za URL stabilnost
@login_required
def investor_dashboard(request): return redirect('dashboard')
@login_required
def partner_dashboard(request): return redirect('dashboard')
"""
    with open(views_path, 'w') as f: f.write(views_content)

if __name__ == "__main__":
    build_full_system()
