from django.contrib import admin

# Register your models here.


# ── Sekcije + Dokumenti + Rezultati ──
from udruge.models import Sekcija, ClanSekcija, ClanskiDokument, NatjecanjeRezultat

class ClanSekcijaInline(admin.TabularInline):
    model = ClanSekcija
    extra = 1

class ClanskiDokumentInline(admin.TabularInline):
    model = ClanskiDokument
    extra = 0

@admin.register(Sekcija)
class SekcijaAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'leader', 'member_count', 'is_active']
    list_filter = ['company', 'is_active']
    inlines = [ClanSekcijaInline]

@admin.register(ClanskiDokument)
class ClanskiDokumentAdmin(admin.ModelAdmin):
    list_display = ['clan', 'doc_type', 'doc_number', 'valid_until', 'is_expired']
    list_filter = ['doc_type']
    search_fields = ['clan__ime', 'clan__prezime', 'doc_number']

@admin.register(NatjecanjeRezultat)
class NatjecanjeRezultatAdmin(admin.ModelAdmin):
    list_display = ['dogadjaj', 'clan', 'sekcija', 'placement', 'score', 'category']
    list_filter = ['category']
