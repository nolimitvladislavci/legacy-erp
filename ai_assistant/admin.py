from django.contrib import admin
from .models import Conversation, Message, AIUsageLog


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "module_context", "is_active", "created_at"]
    list_filter = ["is_active", "module_context"]
    search_fields = ["title", "user__username"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "role", "tokens_used", "created_at"]
    list_filter = ["role"]


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ["user", "model", "input_tokens", "output_tokens", "cost_estimate", "created_at"]
    list_filter = ["model"]
    date_hierarchy = "created_at"
