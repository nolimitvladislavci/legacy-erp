from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Brand, CompanyInfo, GalleryImage, HeroSection, HitnaIntervencija, SitePage, VideoGallery


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

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'founded_year', 'email']
    # Kako bismo osigurali da uvijek postoji samo jedan unos
    def has_add_permission(self, request):
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)


from .models import GrosmarktAnfrage

@admin.register(GrosmarktAnfrage)
class GrosmarktAnfrageAdmin(admin.ModelAdmin):
    list_display  = ['company', 'name', 'email', 'phone', 'status', 'created_at']
    list_filter   = ['status', 'created_at']
    search_fields = ['company', 'name', 'email']
    list_editable = ['status']
    readonly_fields = ['created_at', 'ip_address', 'user_agent']
    fieldsets = [
        ('Kontakt', {'fields': ['name','company','email','phone','message']}),
        ('Status',  {'fields': ['status','contacted_at','notes']}),
        ('Meta',    {'fields': ['created_at','ip_address','user_agent'], 'classes': ['collapse']}),
    ]
    ordering = ['-created_at']
