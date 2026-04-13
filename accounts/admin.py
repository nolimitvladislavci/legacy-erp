from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .auth_models import LoginAttempt, MagicToken
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profil"
    fk_name = "user"


class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "get_role", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser", "profile__role")

    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "-"

    get_role.short_description = "Uloga"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("email", "ip_address", "success", "method", "attempted_at")
    list_filter = ("success", "method", "attempted_at")
    search_fields = ("email", "ip_address")
    readonly_fields = ("email", "ip_address", "success", "attempted_at", "user_agent", "method")
    ordering = ("-attempted_at",)


@admin.register(MagicToken)
class MagicTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token_type", "created_at", "expires_at", "used_at")
    list_filter = ("token_type",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("token", "created_at")
