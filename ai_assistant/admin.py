from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
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

from .models import KnowledgeArticle

@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('module', 'title', 'priority', 'is_active', 'updated_at')
    list_filter = ('module', 'is_active')
    search_fields = ('title', 'content', 'keywords')
    list_editable = ('priority', 'is_active')
