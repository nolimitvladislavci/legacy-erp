from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import PravniPredmet, DimnjacarskaInspekcija, NotariatPredlozak


@admin.register(NotariatPredlozak)
class NotariatPredlozakAdmin(admin.ModelAdmin):
    list_display = ('vrsta', 'naslov', 'aktivan')
    list_filter = ('aktivan', 'vrsta')
    search_fields = ('naslov',)


@admin.register(PravniPredmet)
class PravniPredmetAdmin(admin.ModelAdmin):
    list_display = ('naziv', 'vrsta', 'status', 'rok', 'klijent')
    list_filter = ('status', 'vrsta')
    search_fields = ('naziv', 'opis')
    date_hierarchy = 'rok'


@admin.register(DimnjacarskaInspekcija)
class DimnjacarskaInspekcijaAdmin(admin.ModelAdmin):
    list_display = ('adresa', 'broj_dimnjaka', 'status_dimnjaka', 'datum_pregleda', 'sljedeci_pregled')
    list_filter = ('status_dimnjaka',)
    search_fields = ('adresa', 'opis_nalaza')
    date_hierarchy = 'datum_pregleda'
