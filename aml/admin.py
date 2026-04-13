from django.contrib import admin

from .models import AMLClientProfile, AMLDocument, AMLRiskCategory, AMLTransaction


@admin.register(AMLRiskCategory)
class AMLRiskCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "risk_level")


@admin.register(AMLClientProfile)
class AMLClientProfileAdmin(admin.ModelAdmin):
    list_display = ("company", "overall_risk", "status", "assessment_date", "next_review_date")
    list_filter = ("overall_risk", "status")


@admin.register(AMLTransaction)
class AMLTransactionAdmin(admin.ModelAdmin):
    list_display = ("company", "amount", "status", "transaction_date", "reported_to_amla")
    list_filter = ("status", "reported_to_amla")


@admin.register(AMLDocument)
class AMLDocumentAdmin(admin.ModelAdmin):
    list_display = ("profile", "document_type", "uploaded_at")
