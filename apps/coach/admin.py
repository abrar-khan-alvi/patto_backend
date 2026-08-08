from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.coach.models import CoachConversation, CoachMessage, CoachParticipant, CoachRun


class CoachParticipantInline(admin.TabularInline):
    model = CoachParticipant
    extra = 0
    readonly_fields = ("id", "user", "role", "joined_at")


class CoachMessageInline(admin.TabularInline):
    model = CoachMessage
    extra = 0
    fields = ("id", "sender_type", "author", "explicitly_shared_with_partner", "created_at")
    readonly_fields = fields
    can_delete = False


@admin.register(CoachConversation)
class CoachConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "scope", "couple", "owner", "status", "created_at")
    list_filter = ("scope", "status")
    search_fields = ("id", "owner__email", "couple__id", "title")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [CoachParticipantInline, CoachMessageInline]


@admin.register(CoachMessage)
class CoachMessageAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = (
        "id",
        "conversation",
        "couple",
        "author",
        "sender_type",
        "render_as",
        "explicitly_shared_with_partner",
        "shared_at",
        "created_at",
    )
    sensitive_fields = ("body", "metadata")
    redacted_field_names = ("redacted_body", "redacted_metadata")
    list_display = ("id", "conversation", "sender_type", "author", "explicitly_shared_with_partner", "created_at")
    list_filter = ("sender_type", "explicitly_shared_with_partner")
    search_fields = ("id", "conversation__id", "author__email")
    readonly_fields = ("id", "created_at")

    @admin.display(description="Body")
    def redacted_body(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Metadata")
    def redacted_metadata(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(CoachRun)
class CoachRunAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "requested_by", "status", "model", "created_at")
    list_filter = ("status", "model")
    search_fields = ("id", "conversation__id", "requested_by__email", "provider_response_id")
    readonly_fields = ("id", "created_at", "updated_at")
