"""
memio_pet/admin.py -- Admin za memio.pet modul
Ljubeta unosi podatke ovdje. Inline pomoc na svakom koraku.
"""
from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.contrib import messages
from memio_pet.models import (
    BreederProfile, AnimalProfile, PetHealthRecord,
    PetOwnership, WaitlistEntry, VeterinarProfile, VerificationLog, BreederReview,
)


# ── INLINE HELP ─────────────────────────────────────────────────────────

HELP_BREEDER = """
<div style="background:#fffde7; border-left:4px solid #ffc107; padding:12px; margin:10px 0; border-radius:4px;">
<strong>Kako unijeti uzgajivaca:</strong><br>
1. <b>Ime</b> — puni naziv (npr. "Uzgajivacnica Rex, vl. Ivan Horvat")<br>
2. <b>Tip</b> — Uzgajivac, Azil ili Vlasnik<br>
3. <b>OIB</b> — 11 znamenki, sustav provjerava checksum<br>
4. <b>Grad + Drzava</b> — gdje se nalazi uzgajivacnica<br>
5. Spremi, pa dodaj zivotinje kroz inline tablicu ispod<br>
<em>Trust Score se racuna automatski — vise podataka = visi score.</em>
</div>
"""

HELP_ANIMAL = """
<div style="background:#e8f5e9; border-left:4px solid #4caf50; padding:12px; margin:10px 0; border-radius:4px;">
<strong>Kako unijeti zivotinju:</strong><br>
1. <b>Ime</b> — ime ljubimca (npr. "Rex", "Bella")<br>
2. <b>Usna markica</b> — jedinstveni ID (obavezan, npr. "HR-001-2026")<br>
3. <b>Mikrocip</b> — 15-znamenkasti ISO broj (ako ima)<br>
4. <b>Vrsta + Pasmina</b> — izaberi vrstu, upisi pasminu<br>
5. <b>Roditelji</b> — imena oca i majke (za rodovnicu)<br>
6. <b>Foto</b> — obavezno za Trust Score!<br>
7. Spremi, pa dodaj zdravstvene zapise i vlasnistvo ispod<br>
<em>Svaka zivotinja dobiva javni QR profil na memio.pet</em>
</div>
"""

HELP_VET = """
<div style="background:#e3f2fd; border-left:4px solid #2196f3; padding:12px; margin:10px 0; border-radius:4px;">
<strong>Veterinar u sustavu:</strong><br>
1. <b>Ime</b> — puno ime veterinara<br>
2. <b>Ambulanta</b> — naziv vet. ambulante<br>
3. <b>Broj licence HVK</b> — Hrvatska veterinarska komora<br>
4. <b>Verificiran</b> — oznaci nakon provjere licence<br>
<em>Verificirani veterinar dize Trust Score uzgajivaca za +25 bodova!</em>
</div>
"""


class AnimalInline(admin.TabularInline):
    model = AnimalProfile
    extra = 1
    fields = ("ear_tag", "name", "vrsta", "breed", "spol", "status", "chip_number", "date_of_birth")
    show_change_link = True
    verbose_name = "Zivotinja"
    verbose_name_plural = "Zivotinje (klikni + za dodavanje)"


class HealthRecordInline(admin.TabularInline):
    model = PetHealthRecord
    extra = 1
    fields = ("datum", "tip", "opis", "veterinar", "vet_profile", "lijek", "trosak_eur")
    verbose_name = "Zdravstveni zapis"
    verbose_name_plural = "Zdravstveni kartoni (cijepljenja, pregledi)"


class OwnershipInline(admin.TabularInline):
    model = PetOwnership
    extra = 0
    fields = ("transfer_type", "owner_name", "owner_city", "acquired_at", "released_at", "contract_ref")
    show_change_link = True
    verbose_name = "Vlasnik"
    verbose_name_plural = "Lanac vlasnistva (tko je imao zivotinju)"


class VerificationInline(admin.TabularInline):
    model = VerificationLog
    fk_name = "animal"
    extra = 0
    fields = ("verification_type", "timestamp", "verified_by", "sha256_hash", "is_valid")
    readonly_fields = ("timestamp", "sha256_hash")
    verbose_name = "Verifikacija"
    verbose_name_plural = "Verifikacijski zapisi (dokazi)"


class ReviewInline(admin.TabularInline):
    model = BreederReview
    extra = 0
    fields = ("reviewer_name", "rating", "comment", "is_verified_purchase", "is_published", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Recenzija"
    verbose_name_plural = "Recenzije kupaca"


@admin.register(BreederProfile)
class BreederProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "account_type", "city", "country", "trust_badge", "is_cro_validated", "animal_count", "created_at")
    list_filter = ("account_type", "is_cro_validated", "country", "is_no_limit_partner")
    search_fields = ("name", "city")
    readonly_fields = ("id", "api_key", "created_at", "updated_at", "trust_updated", "trust_score_display", "help_text")
    inlines = [AnimalInline, ReviewInline]
    list_per_page = 25

    fieldsets = (
        (None, {
            "fields": ("help_text",)
        }),
        ("Identitet", {
            "fields": ("name", "account_type", "oib", "city", "country")
        }),
        ("Kontakt", {
            "fields": ("email", "phone", "website")
        }),
        ("Verifikacija", {
            "fields": ("is_cro_validated", "validated_name", "validated_at", "is_no_limit_partner", "shelter_sponsor")
        }),
        ("Trust Score", {
            "fields": ("trust_score_display", "trust_score", "trust_breakdown", "trust_updated"),
        }),
        ("Sistem", {
            "fields": ("id", "api_key", "limit_company_id", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def help_text(self, obj):
        return mark_safe(HELP_BREEDER)
    help_text.short_description = ""

    def trust_badge(self, obj):
        s = obj.trust_score
        if s >= 80:
            color, icon = "#28a745", "★"
        elif s >= 50:
            color, icon = "#ffc107", "◆"
        else:
            color, icon = "#dc3545", "○"
        return format_html(
            '<span style="color:{}; font-weight:bold;">{} {}/100</span>',
            color, icon, s
        )
    trust_badge.short_description = "Trust"
    trust_badge.admin_order_field = "trust_score"

    def trust_score_display(self, obj):
        if not obj.trust_breakdown:
            return "Spremi uzgajivaca i dodaj zivotinje — score ce se izracunati."
        breakdown = obj.trust_breakdown
        rows = ""
        for key, data in breakdown.items():
            bar_width = int(data["score"] / data["max"] * 100) if data["max"] else 0
            color = "#28a745" if bar_width >= 70 else ("#ffc107" if bar_width >= 40 else "#dc3545")
            notes = "; ".join(data.get("notes", []))
            rows += (
                f'<tr><td style="padding:3px 8px;"><b>{key.upper()}</b></td>'
                f'<td><div style="background:#eee;width:120px;height:16px;border-radius:3px;">'
                f'<div style="background:{color};width:{bar_width}%;height:16px;border-radius:3px;"></div>'
                f'</div></td>'
                f'<td style="padding:0 8px;">{data["score"]}/{data["max"]}</td>'
                f'<td style="color:#666;font-size:11px;">{notes}</td></tr>'
            )
        return mark_safe(
            f'<table style="border-collapse:collapse;">{rows}'
            f'<tr><td colspan="4" style="border-top:2px solid #333;padding-top:4px;">'
            f'<b>UKUPNO: {obj.trust_score}/100</b></td></tr></table>'
        )
    trust_score_display.short_description = "Trust Score Breakdown"

    def animal_count(self, obj):
        c = obj.animals.count()
        return f"{c} zivotinja" if c else "—"
    animal_count.short_description = "Zivotinje"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            from memio_pet.trust_score import update_trust_score
            score, _ = update_trust_score(obj)
            messages.info(request, f"Trust Score azuriran: {score}/100")
        except Exception as e:
            messages.warning(request, f"Trust Score greska: {e}")


@admin.register(AnimalProfile)
class AnimalProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "vrsta", "breed", "spol", "status", "breeder_link", "chip_number", "date_of_birth", "has_photo")
    list_filter = ("vrsta", "status", "spol")
    search_fields = ("name", "ear_tag", "chip_number", "breed", "pedigree_number")
    readonly_fields = ("id", "public_id", "created_at", "updated_at", "public_url_link", "help_text")
    inlines = [HealthRecordInline, OwnershipInline, VerificationInline]
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": ("help_text",)
        }),
        ("Osnovni podaci", {
            "fields": ("name", "vrsta", "breed", "spol", "color_description", "date_of_birth", "weight_kg", "status")
        }),
        ("Identifikacija", {
            "fields": ("ear_tag", "chip_number", "pedigree_number", "photo")
        }),
        ("Roditelji (rodovnica)", {
            "fields": ("father_name", "mother_name"),
        }),
        ("Uzgajivac", {
            "fields": ("breeder", "breeder_name_snapshot", "breeder_oib_snapshot")
        }),
        ("Napomene", {
            "fields": ("notes",)
        }),
        ("Sistem", {
            "fields": ("id", "public_id", "public_url_link", "limit_livestock_id", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def help_text(self, obj):
        return mark_safe(HELP_ANIMAL)
    help_text.short_description = ""

    def display_name(self, obj):
        icon = "" if obj.photo else " [bez foto]"
        return f"{obj.name or obj.ear_tag}{icon}"
    display_name.short_description = "Ime/Tag"

    def breeder_link(self, obj):
        if obj.breeder:
            v = " ✓" if obj.breeder.verified_badge else ""
            return f"{obj.breeder.name}{v}"
        return obj.breeder_name_snapshot or "—"
    breeder_link.short_description = "Uzgajivac"

    def has_photo(self, obj):
        return bool(obj.photo)
    has_photo.boolean = True
    has_photo.short_description = "Foto"

    def public_url_link(self, obj):
        url = obj.public_url
        return mark_safe(f'<a href="{url}" target="_blank">{url}</a>')
    public_url_link.short_description = "Javni profil (QR)"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.breeder:
            try:
                from memio_pet.trust_score import update_trust_score
                update_trust_score(obj.breeder)
            except Exception:
                pass


@admin.register(PetHealthRecord)
class PetHealthRecordAdmin(admin.ModelAdmin):
    list_display = ("animal", "datum", "tip", "vet_display", "lijek", "trosak_eur")
    list_filter = ("tip", "datum")
    search_fields = ("animal__name", "animal__ear_tag", "veterinar", "opis")
    autocomplete_fields = ("animal",)
    date_hierarchy = "datum"

    def vet_display(self, obj):
        if obj.vet_profile and obj.vet_profile.is_verified:
            return f"{obj.vet_profile.name} ✓"
        return obj.veterinar or "—"
    vet_display.short_description = "Veterinar"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.animal and obj.animal.breeder:
            try:
                from memio_pet.trust_score import update_trust_score
                update_trust_score(obj.animal.breeder)
            except Exception:
                pass


@admin.register(PetOwnership)
class PetOwnershipAdmin(admin.ModelAdmin):
    list_display = ("animal", "transfer_type", "owner_name", "owner_city", "acquired_at", "released_at")
    list_filter = ("transfer_type",)
    search_fields = ("owner_name", "animal__name", "animal__ear_tag")
    autocomplete_fields = ("animal",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.animal and obj.animal.breeder:
            try:
                from memio_pet.trust_score import update_trust_score
                update_trust_score(obj.animal.breeder)
            except Exception:
                pass


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("name", "pet_type", "user_type", "source", "is_cro_validated", "notified", "created_at")
    list_filter = ("pet_type", "user_type", "notified", "is_cro_validated")
    search_fields = ("name",)
    readonly_fields = ("id", "email_hash", "ip", "created_at", "validated_at")
    list_per_page = 50


@admin.register(VeterinarProfile)
class VeterinarProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "clinic_name", "city", "license_number", "is_verified", "record_count", "created_at")
    list_filter = ("is_verified", "country", "city")
    search_fields = ("name", "clinic_name", "license_number")
    readonly_fields = ("id", "created_at", "updated_at", "verified_at", "help_text")

    fieldsets = (
        (None, {
            "fields": ("help_text",)
        }),
        ("Osnovni podaci", {
            "fields": ("name", "clinic_name", "city", "country")
        }),
        ("Identifikacija", {
            "fields": ("oib", "license_number")
        }),
        ("Kontakt", {
            "fields": ("email", "phone")
        }),
        ("Verifikacija", {
            "fields": ("is_verified", "verified_at"),
        }),
        ("Sistem", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def help_text(self, obj):
        return mark_safe(HELP_VET)
    help_text.short_description = ""

    def record_count(self, obj):
        return obj.health_records.count()
    record_count.short_description = "Zapisa"


@admin.register(VerificationLog)
class VerificationLogAdmin(admin.ModelAdmin):
    list_display = ("verification_type", "animal", "breeder", "veterinar", "verified_by", "is_valid", "hash_short", "timestamp")
    list_filter = ("verification_type", "is_valid")
    search_fields = ("verified_by", "notes")
    readonly_fields = ("id", "timestamp", "sha256_hash")
    date_hierarchy = "timestamp"

    def hash_short(self, obj):
        if obj.sha256_hash:
            return f"{obj.sha256_hash[:12]}..."
        return "—"
    hash_short.short_description = "SHA-256"



@admin.register(BreederReview)
class BreederReviewAdmin(admin.ModelAdmin):
    list_display = ("breeder", "reviewer_name", "stars", "is_verified_purchase", "is_published", "created_at")
    list_filter = ("rating", "is_verified_purchase", "is_published")
    search_fields = ("reviewer_name", "comment", "breeder__name")
    readonly_fields = ("id", "created_at")
    list_editable = ("is_published",)
    list_per_page = 25
    actions = ["publish_reviews", "verify_purchases"]

    def stars(self, obj):
        return "★" * obj.rating + "☆" * (5 - obj.rating)
    stars.short_description = "Ocjena"

    def publish_reviews(self, request, queryset):
        count = queryset.update(is_published=True)
        messages.success(request, f"{count} recenzija objavljeno.")
    publish_reviews.short_description = "Objavi odabrane recenzije"

    def verify_purchases(self, request, queryset):
        count = queryset.update(is_verified_purchase=True)
        messages.success(request, f"{count} kupnji verificirano.")
    verify_purchases.short_description = "Verificiraj kupnje"

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except IntegrityError:
            messages.error(request, f"Recenzija od {obj.reviewer_name} za ovog uzgajivaca vec postoji.")
        # Auto-update trust score
        if obj.breeder:
            try:
                from memio_pet.trust_score import update_trust_score
                update_trust_score(obj.breeder)
            except Exception:
                pass


from memio_pet.models import RawFoodListing, RawFoodOrder

@admin.register(RawFoodListing)
class RawFoodListingAdmin(admin.ModelAdmin):
    list_display = ('company', 'product_type', 'quantity_kg', 'price_eur_kg', 'status', 'is_free_range')
    list_filter = ('product_type', 'status', 'is_antibiotic_free', 'is_free_range')
    search_fields = ('company__name', 'k3_cert_number')

@admin.register(RawFoodOrder)
class RawFoodOrderAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'listing', 'quantity_kg', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('batch_id',)


from memio_pet.models import DogTrainingSession, PetBoardingReservation

@admin.register(DogTrainingSession)
class DogTrainingSessionAdmin(admin.ModelAdmin):
    list_display = ('animal', 'training_type', 'datum', 'trainer', 'status', 'cijena_eur')
    list_filter = ('training_type', 'status')
    search_fields = ('animal__name', 'trainer__name')

@admin.register(PetBoardingReservation)
class PetBoardingReservationAdmin(admin.ModelAdmin):
    list_display = ('animal', 'hotel', 'check_in', 'check_out', 'room_type', 'status', 'total_price')
    list_filter = ('status', 'room_type')
    search_fields = ('animal__name', 'owner_name', 'hotel__name')
