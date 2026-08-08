from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.responses.models import TopicAnalysisJob, TopicMemberCompletion, TopicResponse, TopicSession, TopicSyncEvent


@admin.register(TopicSession)
class TopicSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "topic_kind", "topic_stable_key", "topic_version", "created_at")
    list_filter = ("topic_kind",)
    search_fields = ("id", "couple__id", "topic_stable_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TopicResponse)
class TopicResponseAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = (
        "id",
        "session",
        "couple",
        "user",
        "question_stable_key",
        "question_version",
        "selected_option_key",
        "answered_at",
        "created_at",
        "updated_at",
    )
    sensitive_fields = ("text_answer",)
    redacted_field_names = ("redacted_text_answer",)
    list_display = ("session", "user", "question_stable_key", "question_version", "answered_at")
    search_fields = ("session__id", "user__email", "question_stable_key")
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Text answer")
    def redacted_text_answer(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(TopicMemberCompletion)
class TopicMemberCompletionAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "completed_at", "locked_at")
    search_fields = ("session__id", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TopicAnalysisJob)
class TopicAnalysisJobAdmin(admin.ModelAdmin):
    list_display = ("session", "couple", "status", "queued_at", "started_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("session__id", "couple__id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TopicSyncEvent)
class TopicSyncEventAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "event_type", "created_at")
    list_filter = ("event_type",)
    search_fields = ("session__id", "user__email")
    readonly_fields = ("created_at",)
