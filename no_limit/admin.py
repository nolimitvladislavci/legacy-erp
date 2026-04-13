from django.contrib import admin

from no_limit.models import AzilPrijava


@admin.register(AzilPrijava)
class AzilPrijavaAdmin(admin.ModelAdmin):
    list_display = ("naziv", "grad", "email", "contacted", "created_at")
    list_filter = ("contacted", "grad")
    search_fields = ("naziv", "email")
    actions = ["oznaci_contacted"]

    def oznaci_contacted(self, request, queryset):
        queryset.update(contacted=True)

    oznaci_contacted.short_description = "Oznaci kao kontaktirano"
