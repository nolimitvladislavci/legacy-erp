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


# ── Golubar modul ──
from udruge.models import (
    Golubinjak, Golub, ParGolubova, Leglo,
    ZdravstveniZapisGolub, Utrka, RezultatUtrke,
)


class ZdravstveniZapisGolubInline(admin.TabularInline):
    model = ZdravstveniZapisGolub
    extra = 0


class RezultatUtrkeInline(admin.TabularInline):
    model = RezultatUtrke
    extra = 0


@admin.register(Golubinjak)
class GolubinjakAdmin(admin.ModelAdmin):
    list_display = ['naziv', 'eu_reg_broj', 'kapacitet', 'aktivan', 'company']


@admin.register(Golub)
class GolubAdmin(admin.ModelAdmin):
    list_display = ['prsten_broj', 'naziv', 'spol', 'boja', 'golubinjak', 'aktivan', 'broj_utrka']
    search_fields = ['prsten_broj', 'naziv']
    list_filter = ['spol', 'aktivan', 'golubinjak']
    inlines = [ZdravstveniZapisGolubInline]


@admin.register(ParGolubova)
class ParGolubovaAdmin(admin.ModelAdmin):
    list_display = ['muzjak', 'zenka', 'sezona', 'aktivan']


@admin.register(Leglo)
class LegloAdmin(admin.ModelAdmin):
    list_display = ['par', 'datum_jaja', 'datum_izlijeganja_1']


@admin.register(ZdravstveniZapisGolub)
class ZdravstveniZapisGolubAdmin(admin.ModelAdmin):
    list_display = ['golub', 'vrsta', 'datum', 'lijek_preparat', 'veterinar']


@admin.register(Utrka)
class UtrkaAdmin(admin.ModelAdmin):
    list_display = ['naziv', 'datum', 'startna_tocka', 'udaljenost_km', 'organizator']
    inlines = [RezultatUtrkeInline]


@admin.register(RezultatUtrke)
class RezultatUtrkeAdmin(admin.ModelAdmin):
    list_display = ['utrka', 'golub', 'placiranje', 'brzina_mpm', 'bodovi']


# ── Perad (Flock) modul ──
from udruge.models import Flock, EggRecord, FlockHealthRecord, FlockMortality
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class EggRecordInline(admin.TabularInline):
    model = EggRecord
    extra = 0


class FlockHealthRecordInline(admin.TabularInline):
    model = FlockHealthRecord
    extra = 0


class FlockMortalityInline(admin.TabularInline):
    model = FlockMortality
    extra = 0


@admin.register(Flock)
class FlockAdmin(admin.ModelAdmin):
    list_display = ['naziv', 'vrsta', 'pasmina', 'broj_komada', 'tip_uzgoja', 'aktivan', 'company']
    list_filter = ['vrsta', 'tip_uzgoja', 'aktivan', 'company']
    search_fields = ['naziv', 'pasmina', 'objekt']
    inlines = [EggRecordInline, FlockHealthRecordInline, FlockMortalityInline]


@admin.register(EggRecord)
class EggRecordAdmin(admin.ModelAdmin):
    list_display = ['flock', 'datum', 'broj_jaja', 'broken', 'sold', 'za_prodaju']
    list_filter = ['za_prodaju', 'datum']
    date_hierarchy = 'datum'


@admin.register(FlockHealthRecord)
class FlockHealthRecordAdmin(admin.ModelAdmin):
    list_display = ['flock', 'vrsta_tretmana', 'datum', 'lijek', 'veterinar', 'karenca_dana']
    list_filter = ['vrsta_tretmana']


@admin.register(FlockMortality)
class FlockMortalityAdmin(admin.ModelAdmin):
    list_display = ['flock', 'datum', 'broj_uginulih', 'razlog']
    date_hierarchy = 'datum'
