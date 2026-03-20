"""
Patch: website/admin.py, website/views.py, website/urls.py
"""
import os

SERVER_BASE = '/var/www/fina-connect/website'

# ── 1. Admin ─────────────────────────────────────────────────────────────────
ADMIN_CONTENT = '''from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import SitePage, HeroSection, Brand, GalleryImage, CompanyInfo, HitnaIntervencija, VideoGallery


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ['caption_hr', 'category', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['category', 'is_active']


admin.site.register(SitePage)
admin.site.register(HeroSection)
admin.site.register(CompanyInfo)


@admin.register(HitnaIntervencija)
class HitnaIntervencijaAdmin(admin.ModelAdmin):
    list_display  = ('created_at', 'ime', 'telefon', 'vrsta_badge', 'hitnost_badge', 'status_badge', 'dodijeljeno')
    list_filter   = ('status', 'vrsta', 'hitnost', 'drzava')
    search_fields = ('ime', 'telefon', 'email', 'adresa', 'opis')
    readonly_fields = ('created_at', 'updated_at', 'ip_adresa', 'jezik')
    list_editable = ('dodijeljeno',)
    date_hierarchy = 'created_at'

    fieldsets = (
        (_('Podnositelj'), {
            'fields': ('ime', 'telefon', 'email', 'adresa', 'grad', 'drzava', 'jezik'),
        }),
        (_('Problem'), {
            'fields': ('vrsta', 'opis', 'hitnost'),
        }),
        (_('Interni status'), {
            'fields': ('status', 'dodijeljeno', 'napomena'),
        }),
        (_('Metapodaci'), {
            'fields': ('ip_adresa', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def vrsta_badge(self, obj):
        colors = {
            'voda': '#3b82f6', 'elektrika': '#f59e0b',
            'grijanje': '#ef4444', 'fasada': '#8b5cf6', 'ostalo': '#64748b',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.vrsta, '#64748b'), obj.get_vrsta_display()
        )
    vrsta_badge.short_description = _('Vrsta')

    def hitnost_badge(self, obj):
        if obj.hitnost:
            return format_html('<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:3px;font-size:11px">&#9888; HITNO</span>')
        return format_html('<span style="color:#94a3b8;font-size:11px">redovito</span>')
    hitnost_badge.short_description = _('Hitnost')

    def status_badge(self, obj):
        colors = {
            'novo': '#ef4444', 'kontaktiran': '#f59e0b',
            'u_radu': '#3b82f6', 'zavrseno': '#16a34a', 'otkazano': '#64748b',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#64748b'), obj.get_status_display()
        )
    status_badge.short_description = _('Status')


@admin.register(VideoGallery)
class VideoGalleryAdmin(admin.ModelAdmin):
    list_display  = ('naslov_hr', 'kategorija', 'video_preview', 'trajanje', 'redoslijed', 'is_featured', 'is_active')
    list_filter   = ('kategorija', 'is_active', 'is_featured')
    list_editable = ('redoslijed', 'is_featured', 'is_active')
    search_fields = ('naslov_hr', 'naslov_de', 'opis_hr')
    readonly_fields = ('video_preview', 'created_at')

    fieldsets = (
        (_('Naslov i opis'), {
            'fields': ('naslov_hr', 'naslov_de', 'naslov_en', 'opis_hr', 'opis_de', 'opis_en'),
        }),
        (_('Video izvor'), {
            'fields': ('embed_url', 'video_file', 'thumbnail'),
            'description': _('Unesite YouTube/Vimeo URL ILI uploadajte .mp4 datoteku.'),
        }),
        (_('Klasifikacija'), {
            'fields': ('kategorija', 'trajanje', 'redoslijed', 'is_featured', 'is_active'),
        }),
        (_('Info'), {
            'fields': ('video_preview', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def video_preview(self, obj):
        if obj.embed_src:
            return format_html(
                '<iframe width="320" height="180" src="{}" frameborder="0" allowfullscreen></iframe>',
                obj.embed_src
            )
        if obj.video_file:
            return format_html(
                '<video width="320" height="180" controls><source src="{}"></video>',
                obj.video_file.url
            )
        return format_html('<span style="color:#94a3b8">Nema video izvora</span>')
    video_preview.short_description = _('Preview')
'''

with open(os.path.join(SERVER_BASE, 'admin.py'), 'w') as f:
    f.write(ADMIN_CONTENT)
print('OK: admin.py updated')


# ── 2. Views ─────────────────────────────────────────────────────────────────
VIEWS_CONTENT = '''from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from .models import Brand, GalleryImage, HitnaIntervencija, VideoGallery
from .forms import HitnaIntervencijaForm


def homepage(request):
    """Javna web stranica - bez login zahtjeva"""
    brands  = Brand.objects.filter(is_active=True)
    gallery = GalleryImage.objects.filter(is_active=True)[:12]
    videos  = VideoGallery.objects.filter(is_active=True)
    featured_videos = videos.filter(is_featured=True)[:3]
    return render(request, 'website/homepage.html', {
        'brands': brands,
        'gallery': gallery,
        'videos': videos,
        'featured_videos': featured_videos,
    })


def hitna_intervencija(request):
    """Javna forma za hitnu intervenciju"""
    if request.method == 'POST':
        form = HitnaIntervencijaForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            # Spremi IP adresu
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                obj.ip_adresa = x_forwarded_for.split(',')[0].strip()
            else:
                obj.ip_adresa = request.META.get('REMOTE_ADDR')
            # Jezik iz Accept-Language headera
            lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'de')
            obj.jezik = lang[:2].lower()
            obj.save()

            # Slanje email notifikacije (ako postoji email backend)
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                subject = f"[HITNO] Nova intervencija: {obj.get_vrsta_display()} — {obj.ime}"
                body = (
                    f"Novi zahtjev za hitnu intervenciju\\n\\n"
                    f"Ime: {obj.ime}\\n"
                    f"Telefon: {obj.telefon}\\n"
                    f"Email: {obj.email}\\n"
                    f"Adresa: {obj.adresa}, {obj.grad} ({obj.drzava})\\n"
                    f"Vrsta: {obj.get_vrsta_display()}\\n"
                    f"Hitnost: {'HITNO' if obj.hitnost else 'Redovito'}\\n\\n"
                    f"Opis:\\n{obj.opis}\\n"
                )
                notify_email = getattr(settings, 'HITNA_NOTIFY_EMAIL', None)
                if notify_email:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [notify_email], fail_silently=True)
            except Exception:
                pass

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'id': obj.id})
            messages.success(request, _('Vaš zahtjev je zaprimljen. Kontaktirat ćemo vas u najkraćem roku.'))
            return redirect('website:hitna_hvala')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    else:
        form = HitnaIntervencijaForm()

    return render(request, 'website/hitna_intervencija.html', {'form': form})


def hitna_hvala(request):
    """Stranica zahvale nakon slanja forme"""
    return render(request, 'website/hitna_hvala.html')


def video_galerija(request):
    """Javna video galerija"""
    kategorija = request.GET.get('k', '')
    videos = VideoGallery.objects.filter(is_active=True)
    if kategorija:
        videos = videos.filter(kategorija=kategorija)
    kategorije = VideoGallery.KATEGORIJA_CHOICES
    return render(request, 'website/video_galerija.html', {
        'videos': videos,
        'kategorije': kategorije,
        'aktivna_kategorija': kategorija,
    })


@login_required
def admin_panel(request):
    """Admin panel za upravljanje web stranicom"""
    brands    = Brand.objects.filter(is_active=True)
    gallery   = GalleryImage.objects.filter(is_active=True)
    hitne     = HitnaIntervencija.objects.filter(status='novo')[:10]
    videos    = VideoGallery.objects.filter(is_active=True)[:10]
    return render(request, 'website/index.html', {
        'brands': brands,
        'gallery': gallery,
        'hitne': hitne,
        'videos': videos,
    })
'''

with open(os.path.join(SERVER_BASE, 'views.py'), 'w') as f:
    f.write(VIEWS_CONTENT)
print('OK: views.py updated')


# ── 3. URLs ─────────────────────────────────────────────────────────────────
URLS_CONTENT = '''from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('hitna-intervencija/', views.hitna_intervencija, name='hitna_intervencija'),
    path('hitna-intervencija/hvala/', views.hitna_hvala, name='hitna_hvala'),
    path('video-galerija/', views.video_galerija, name='video_galerija'),
]
'''

with open(os.path.join(SERVER_BASE, 'urls.py'), 'w') as f:
    f.write(URLS_CONTENT)
print('OK: urls.py updated')


# ── 4. Forms ─────────────────────────────────────────────────────────────────
FORMS_CONTENT = '''from django import forms
from django.utils.translation import gettext_lazy as _
from .models import HitnaIntervencija


class HitnaIntervencijaForm(forms.ModelForm):
    class Meta:
        model = HitnaIntervencija
        fields = ['ime', 'telefon', 'email', 'adresa', 'grad', 'drzava', 'vrsta', 'opis', 'hitnost']
        widgets = {
            'ime':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Vaše ime i prezime')}),
            'telefon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+49 ...',
                                              'type': 'tel'}),
            'email':   forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'adresa':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Ulica i broj')}),
            'grad':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Grad / PLZ')}),
            'drzava':  forms.Select(attrs={'class': 'form-select'},
                                    choices=[('DE','Deutschland'), ('AT','Österreich'),
                                             ('CH','Schweiz'), ('HR','Hrvatska')]),
            'vrsta':   forms.Select(attrs={'class': 'form-select'}),
            'opis':    forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                             'placeholder': _('Opišite problem što detaljnije...')}),
            'hitnost': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'ime':     _('Ime i prezime'),
            'telefon': _('Telefon (obavezan)'),
            'email':   _('E-mail'),
            'adresa':  _('Adresa'),
            'grad':    _('Grad'),
            'drzava':  _('Država'),
            'vrsta':   _('Vrsta intervencije'),
            'opis':    _('Opis problema'),
            'hitnost': _('Hitno — trebam intervenciju odmah'),
        }
'''

with open(os.path.join(SERVER_BASE, 'forms.py'), 'w') as f:
    f.write(FORMS_CONTENT)
print('OK: forms.py created')
