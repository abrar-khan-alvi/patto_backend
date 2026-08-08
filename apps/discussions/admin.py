from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.discussions.models import DiscussionMessage, DiscussionThread, MediationRequest, MediationResponse


class DiscussionMessageInline(admin.TabularInline):
    model = DiscussionMessage
    extra = 0
    fields = ("sender_type", "author", "created_at")
    readonly_fields = fields


@admin.register(DiscussionThread)
class DiscussionThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "title", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "title", "couple__id", "created_by__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [DiscussionMessageInline]


@admin.register(DiscussionMessage)
class DiscussionMessageAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "thread", "couple", "author", "sender_type", "created_at")
    sensitive_fields = ("body", "metadata")
    redacted_field_names = ("redacted_body", "redacted_metadata")
    list_display = ("thread", "sender_type", "author", "created_at")
    list_filter = ("sender_type",)
    search_fields = ("thread__id", "author__email")
    readonly_fields = ("created_at",)

    @admin.display(description="Body")
    def redacted_body(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Metadata")
    def redacted_metadata(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(MediationRequest)
class MediationRequestAdmin(admin.ModelAdmin):
    list_display = ("thread", "requested_by", "status", "context_message_count", "created_at")
    list_filter = ("status",)
    search_fields = ("thread__id", "requested_by__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(MediationResponse)
class MediationResponseAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "request", "thread", "couple", "message", "model", "created_at")
    sensitive_fields = ("content", "metadata")
    redacted_field_names = ("redacted_content", "redacted_metadata")
    list_display = ("request", "thread", "model", "created_at")
    search_fields = ("request__id", "thread__id")
    readonly_fields = ("metadata", "created_at")

    @admin.display(description="Content")
    def redacted_content(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Metadata")
    def redacted_metadata(self, obj):
        return REDACTED_ADMIN_VALUE
