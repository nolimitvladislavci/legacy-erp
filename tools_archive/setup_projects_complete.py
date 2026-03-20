import os

def update_models():
    path = 'projects/models.py'
    content = """from django.db import models
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
    estimated_hours = models.FloatField(default=0, verbose_name=_('Planirani sati'))
    margin = models.FloatField(default=10.0, verbose_name=_('Marža (%)'))
    is_public = models.BooleanField(default=False, verbose_name=_('Vidljivo investitorima'))
    cover_image = models.ImageField(upload_to='projects/covers/', null=True, blank=True, verbose_name=_('Naslovna slika'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def budget_usage_percentage(self):
        try:
            from django.apps import apps
            TimeEntry = apps.get_model('worktime', 'TimeEntry')
            total_cost = 0
            entries = TimeEntry.objects.filter(project=self)
            for entry in entries:
                try:
                    rate = entry.user.userprofile.hourly_rate or 0
                except:
                    rate = 0
                total_cost += (float(entry.duration_hours) * float(rate))
            if self.budget > 0:
                return round((total_cost / float(self.budget)) * 100, 2)
            return 0
        except:
            return 0

    class Meta:
        verbose_name = _('Projekt')
        verbose_name_plural = _('Projekti')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

class ProjectUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='updates', verbose_name=_('Projekt'))
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_('Autor'))
    title = models.CharField(max_length=200, verbose_name=_('Naslov'))
    content = models.TextField(verbose_name=_('Sadržaj'))
    is_public = models.BooleanField(default=False, verbose_name=_('Vidljivo investitorima'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Ažuriranje projekta')
        verbose_name_plural = _('Ažuriranja projekta')
        ordering = ['-created_at']

class ProjectPhoto(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='photos', verbose_name=_('Projekt'))
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_('Uploadao'))
    image = models.ImageField(upload_to='projects/photos/', verbose_name=_('Fotografija'))
    caption = models.CharField(max_length=255, blank=True, verbose_name=_('Opis'))
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Fotografija projekta')
        verbose_name_plural = _('Fotografije projekta')
"""
    with open(path, 'w') as f:
        f.write(content)
    print("Models.py updated.")

def update_views():
    path = 'core/views.py'
    content = """from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.apps import apps
from django.db.models import Sum
from accounts.models import UserProfile
from accounts.auth_models import LoginAttempt

def get_user_profile(user):
    try:
        return user.userprofile
    except:
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'worker'})
        return profile

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        u = request.POST.get('username', '').strip().lower()
        p = request.POST.get('password', '')
        user = authenticate(request, username=u, password=p)
        if user and user.is_active:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'login.html', {'error': 'Greška.'})
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
    
    total_hours = 0
    projects = []
    try:
        Project = apps.get_model('projects', 'Project')
        projects = Project.objects.all().order_by('-created_at')[:10]
        TimeEntry = apps.get_model('worktime', 'TimeEntry')
        total_hours = TimeEntry.objects.aggregate(Sum('duration_hours'))['duration_hours__sum'] or 0
    except: pass

    context = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'staff_users': User.objects.filter(is_staff=True).count(),
        'superusers': User.objects.filter(is_superuser=True).count(),
        'total_hours': total_hours,
        'projects': projects,
        'recent_logins': LoginAttempt.objects.order_by('-attempted_at')[:15],
    }
    return render(request, 'dashboards/superadmin.html', context)

@login_required
def company_dashboard(request): return render(request, 'dashboards/company_admin.html', {'profile': get_user_profile(request.user)})
@login_required
def manager_dashboard(request): return redirect('ts_worker')
@login_required
def worker_dashboard(request): return redirect('ts_worker')
@login_required
def investor_dashboard(request): return render(request, 'dashboards/investor.html', {'profile': get_user_profile(request.user)})
@login_required
def partner_dashboard(request): return render(request, 'dashboards/partner.html', {'profile': get_user_profile(request.user)})
def logout_view(request):
    logout(request)
    return redirect('login')
"""
    with open(path, 'w') as f:
        f.write(content)
    print("Views.py updated.")

if __name__ == "__main__":
    update_models()
    update_views()
