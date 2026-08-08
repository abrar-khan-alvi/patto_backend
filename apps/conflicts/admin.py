from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.conflicts.models import ConflictBridge, ConflictMessage, ConflictMediation, ConflictPerspective, ConflictResolution, ConflictThread


class ConflictPerspectiveInline(admin.TabularInline):
    model = ConflictPerspective
    extra = 0
    fields = ("id", "user", "locked_at", "created_at", "updated_at")
    readonly_fields = fields


class ConflictMessageInline(admin.TabularInline):
    model = ConflictMessage
    extra = 0
    fields = ("id", "sender_type", "author", "created_at")
    readonly_fields = fields


@admin.register(ConflictThread)
class ConflictThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "title", "status", "created_by", "created_at", "resolved_at")
    list_filter = ("status",)
    search_fields = ("id", "couple__id", "title")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ConflictPerspectiveInline, ConflictMessageInline]


@admin.register(ConflictBridge)
class ConflictBridgeAdmin(admin.ModelAdmin):
    list_display = ("thread", "status", "model", "error_code", "created_at")
    list_filter = ("status", "model")
    search_fields = ("thread__id", "provider_response_id", "error_code")
    readonly_fields = ("usage", "safety_flags", "created_at", "updated_at")


@admin.register(ConflictPerspective)
class ConflictPerspectiveAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "thread", "couple", "user", "locked_at", "created_at", "updated_at")
    sensitive_fields = ("situation", "feelings", "needs", "requested_outcome")
    redacted_field_names = ("redacted_private_perspective",)
    list_display = ("id", "thread", "user", "locked_at", "created_at")
    search_fields = ("id", "thread__id", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Private perspective")
    def redacted_private_perspective(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(ConflictMessage)
class ConflictMessageAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "thread", "couple", "author", "sender_type", "render_as", "created_at")
    sensitive_fields = ("body", "metadata")
    redacted_field_names = ("redacted_body", "redacted_metadata")
    list_display = ("id", "thread", "sender_type", "author", "created_at")
    list_filter = ("sender_type",)
    search_fields = ("id", "thread__id", "author__email")
    readonly_fields = ("id", "created_at")

    @admin.display(description="Body")
    def redacted_body(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Metadata")
    def redacted_metadata(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(ConflictMediation)
class ConflictMediationAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "thread", "couple", "requested_by", "status", "created_at", "updated_at")
    sensitive_fields = ("prompt", "response")
    redacted_field_names = ("redacted_mediation_content",)
    list_display = ("id", "thread", "requested_by", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "thread__id", "requested_by__email")
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Mediation content")
    def redacted_mediation_content(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(ConflictResolution)
class ConflictResolutionAdmin(admin.ModelAdmin):
    list_display = ("thread", "resolved_by", "created_at")
    search_fields = ("thread__id", "resolved_by__email")
    readonly_fields = ("created_at",)
