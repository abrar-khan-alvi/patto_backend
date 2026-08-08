from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User, UserProfile


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active", "email_verified_at", "created_at")
    search_fields = ("email",)
    readonly_fields = ("created_at", "updated_at", "last_login_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("preferred_language", "timezone")}),
        ("Important dates", {"fields": ("email_verified_at", "last_login_at")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_active"),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "preferred_language", "timezone", "onboarding_completed_at")
    search_fields = ("user__email", "display_name")
    readonly_fields = ("created_at", "updated_at")
