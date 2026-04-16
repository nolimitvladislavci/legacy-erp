from django.contrib import admin
from django.utils import timezone

from no_limit.models import AmbassadorApplication, AzilPrijava, CountryChapter, PartnershipLead


@admin.register(AzilPrijava)
class AzilPrijavaAdmin(admin.ModelAdmin):
    list_display = ("naziv", "grad", "email", "contacted", "created_at")
    list_filter = ("contacted", "grad")
    search_fields = ("naziv", "email")
    actions = ["oznaci_contacted"]

    def oznaci_contacted(self, request, queryset):
        queryset.update(contacted=True)

    oznaci_contacted.short_description = "Oznaci kao kontaktirano"


@admin.register(AmbassadorApplication)
class AmbassadorApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "country",
        "desired_role",
        "organization",
        "status",
        "created_at",
    )
    list_filter = ("status", "country", "desired_role")
    search_fields = ("full_name", "email", "organization", "city")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_approved", "mark_declined", "mark_active"]

    fieldsets = (
        (
            "Osobni podaci",
            {"fields": ("full_name", "email", "phone", "country", "city")},
        ),
        (
            "Organizacija",
            {"fields": ("organization", "organization_type")},
        ),
        (
            "Uloga i motivacija",
            {"fields": ("desired_role", "motivation", "experience", "languages")},
        ),
        (
            "Status",
            {"fields": ("status", "reviewed_by", "review_notes", "approved_at")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def mark_approved(self, request, queryset):
        queryset.update(
            status="approved",
            reviewed_by=request.user.get_full_name() or request.user.username,
            approved_at=timezone.now(),
        )
        self.message_user(request, f"{queryset.count()} prijava(e) odobreno.")

    mark_approved.short_description = "✓ Odobri odabrane prijave"

    def mark_declined(self, request, queryset):
        queryset.update(
            status="declined",
            reviewed_by=request.user.get_full_name() or request.user.username,
        )
        self.message_user(request, f"{queryset.count()} prijava(e) odbijeno.")

    mark_declined.short_description = "✗ Odbij odabrane prijave"

    def mark_active(self, request, queryset):
        queryset.update(status="active")
        self.message_user(request, f"{queryset.count()} ambasador(a) aktivirano.")

    mark_active.short_description = "★ Aktiviraj kao ambasadora"


@admin.register(CountryChapter)
class CountryChapterAdmin(admin.ModelAdmin):
    list_display = (
        "country_name",
        "country",
        "coordinator_name",
        "is_active",
        "ambassador_count",
        "user_count",
        "launch_date",
    )
    list_filter = ("is_active",)
    search_fields = ("country_name", "coordinator_name", "coordinator_email")


@admin.register(PartnershipLead)
class PartnershipLeadAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "country",
        "partnership_type",
        "status",
        "potential_value",
        "created_at",
    )
    list_filter = ("status", "partnership_type", "country")
    search_fields = ("name", "organization", "email")
    actions = ["mark_contacted", "mark_declined"]

    def mark_contacted(self, request, queryset):
        queryset.update(status="contacted")
        self.message_user(request, f"{queryset.count()} lead(ova) označeno kao kontaktirano.")

    mark_contacted.short_description = "Označi kao kontaktirano"

    def mark_declined(self, request, queryset):
        queryset.update(status="declined")
        self.message_user(request, f"{queryset.count()} lead(ova) odbijeno.")

    mark_declined.short_description = "✗ Odbij odabrane leadove"
