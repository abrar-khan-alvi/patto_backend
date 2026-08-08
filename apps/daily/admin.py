from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.daily.models import CoupleStreak, DailyAnswer, DailyAssignment, DailyQuestion, DailyReveal


class DailyAnswerInline(admin.TabularInline):
    model = DailyAnswer
    extra = 0
    fields = ("id", "user", "answered_at", "created_at", "updated_at")
    readonly_fields = fields
    can_delete = False


@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ("stable_key", "category", "is_active", "sort_order", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("stable_key", "prompt")
    ordering = ("sort_order", "stable_key")


@admin.register(DailyAssignment)
class DailyAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "question", "local_date", "timezone", "status", "created_at")
    list_filter = ("status", "timezone")
    search_fields = ("id", "couple__id", "question__stable_key")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [DailyAnswerInline]


@admin.register(DailyAnswer)
class DailyAnswerAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "assignment", "couple", "user", "answered_at", "created_at", "updated_at")
    sensitive_fields = ("text_answer",)
    redacted_field_names = ("redacted_text_answer",)
    list_display = ("id", "assignment", "couple", "user", "answered_at")
    search_fields = ("id", "assignment__id", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Text answer")
    def redacted_text_answer(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(DailyReveal)
class DailyRevealAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "couple", "revealed_at")
    search_fields = ("id", "assignment__id", "couple__id")
    readonly_fields = ("id", "created_at")


@admin.register(CoupleStreak)
class CoupleStreakAdmin(admin.ModelAdmin):
    list_display = ("couple", "current_count", "longest_count", "last_completed_date", "updated_at")
    search_fields = ("couple__id",)
