from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.ai.models import AIAnalysisResult, AIFollowUpQuestion, AIPromptVersion, AISafetyEvent


@admin.register(AIPromptVersion)
class AIPromptVersionAdmin(admin.ModelAdmin):
    list_display = ("key", "version", "is_active", "description", "created_at")
    list_filter = ("key", "is_active")
    search_fields = ("key", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIAnalysisResult)
class AIAnalysisResultAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = (
        "id",
        "analysis_job",
        "prompt_version",
        "status",
        "model",
        "provider_response_id",
        "schema_name",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "refusal_reason",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
    )
    sensitive_fields = ("output", "usage")
    redacted_field_names = ("redacted_output", "redacted_usage")
    list_display = ("analysis_job", "status", "model", "prompt_version", "created_at")
    list_filter = ("status", "model")
    search_fields = ("analysis_job__id", "provider_response_id")
    readonly_fields = ("output", "usage", "created_at", "updated_at")

    @admin.display(description="Output")
    def redacted_output(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Usage")
    def redacted_usage(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(AISafetyEvent)
class AISafetyEventAdmin(admin.ModelAdmin):
    list_display = ("analysis_job", "stage", "category", "severity", "route", "detector", "created_at")
    list_filter = ("stage", "category", "severity", "route", "detector")
    search_fields = ("analysis_job__id", "content_fingerprint")
    readonly_fields = ("content_fingerprint", "metadata", "created_at")


@admin.register(AIFollowUpQuestion)
class AIFollowUpQuestionAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = (
        "id",
        "session",
        "couple",
        "user",
        "prompt_version",
        "status",
        "model",
        "provider_response_id",
        "topic_stable_key",
        "topic_version",
        "skip",
        "skip_reason",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "refusal_reason",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
    )
    sensitive_fields = ("follow_up_question", "internal_reason", "usage")
    redacted_field_names = ("redacted_follow_up_question", "redacted_internal_reason", "redacted_usage")
    list_display = ("session", "user", "status", "model", "skip", "created_at")
    list_filter = ("status", "model", "skip")
    search_fields = ("session__id", "user__email")
    readonly_fields = ("usage", "created_at", "updated_at")

    @admin.display(description="Follow-up question")
    def redacted_follow_up_question(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Internal reason")
    def redacted_internal_reason(self, obj):
        return REDACTED_ADMIN_VALUE

    @admin.display(description="Usage")
    def redacted_usage(self, obj):
        return REDACTED_ADMIN_VALUE
