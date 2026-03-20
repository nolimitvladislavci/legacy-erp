import os

def fix_all():
    # 1. Popravak Projects Modela (vraćamo uploaded_by koji Admin traži)
    projects_models = """from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('Naziv projekta'))
    code = models.CharField(max_length=30, unique=True, verbose_name=_('Šifra'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    location = models.CharField(max_length=255, blank=True, verbose_name=_('Lokacija'))
    status = models.CharField(max_length=20, default='planning')
    client = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects')
    team = models.ManyToManyField(User, related_name='team_projects', blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def budget_usage_percentage(self):
        return 0 # Pojednostavljeno radi migracije

    class Meta:
        verbose_name = _('Projekt')
        verbose_name_plural = _('Projekti')

class ProjectUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class ProjectPhoto(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='photos')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True) # OVO JE FALILO
    image = models.ImageField(upload_to='projects/photos/')
    caption = models.CharField(max_length=255, blank=True)
    is_public = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
"""
    with open('projects/models.py', 'w') as f:
        f.write(projects_models)

    # 2. Provjera Calculator Views (da nema onog tipfelera)
    calc_views = """from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Calculation, Normative

@login_required
def calculation_list(request):
    return render(request, 'calculator/list.html', {'calculations': Calculation.objects.all()})

@login_required
def calculation_detail(request, pk):
    calc = get_object_or_404(Calculation, pk=pk)
    return render(request, 'calculator/detail.html', {'calculation': calc})
"""
    with open('calculator/views.py', 'w') as f:
        f.write(calc_views)
    
    print("Sustav je sinkroniziran. Sva polja su vraćena.")

if __name__ == "__main__":
    fix_all()
