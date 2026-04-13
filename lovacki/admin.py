from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import HuntingGround, GameSpecies, HuntingQuota, HuntRecord


@admin.register(GameSpecies)
class GameSpeciesAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_latin', 'category', 'is_cites', 'barf_compatible')
    list_filter = ('category', 'is_cites', 'barf_compatible')


@admin.register(HuntingGround)
class HuntingGroundAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'area_ha', 'county', 'is_active')
    list_filter = ('is_active', 'county')
    search_fields = ('name', 'code')


@admin.register(HuntingQuota)
class HuntingQuotaAdmin(admin.ModelAdmin):
    list_display = ('ground', 'species', 'year', 'planned_count', 'realized_count', 'utilization_pct')
    list_filter = ('year',)


@admin.register(HuntRecord)
class HuntRecordAdmin(admin.ModelAdmin):
    list_display = ('species', 'datum', 'ground', 'hunter', 'weight_kg', 'spol', 'barf_listed')
    list_filter = ('species', 'ground', 'datum')
    search_fields = ('species__name', 'lokacija')
    date_hierarchy = 'datum'
