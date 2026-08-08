from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.moments.models import Moment, MomentMedia, MomentMediaDownloadToken, MomentTopicLink


class MomentMediaInline(admin.TabularInline):
    model = MomentMedia
    extra = 0
    readonly_fields = ("id", "filename", "content_type", "byte_size", "width", "height", "metadata_removed", "created_at")


@admin.register(Moment)
class MomentAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "couple", "created_by", "title", "occurred_on", "status", "archived_at", "created_at", "updated_at")
    sensitive_fields = ("body",)
    redacted_field_names = ("redacted_body",)
    list_display = ("id", "couple", "title", "status", "occurred_on", "created_by", "created_at")
    list_filter = ("status", "occurred_on")
    search_fields = ("id", "title", "couple__id")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MomentMediaInline]

    @admin.display(description="Body")
    def redacted_body(self, obj):
        return REDACTED_ADMIN_VALUE


admin.site.register(MomentMedia)
admin.site.register(MomentTopicLink)
admin.site.register(MomentMediaDownloadToken)
