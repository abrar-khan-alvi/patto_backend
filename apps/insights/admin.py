from django.contrib import admin

from apps.insights.models import MonthlyInsight, MonthlyInsightInput


class MonthlyInsightInputInline(admin.TabularInline):
    model = MonthlyInsightInput
    extra = 0
    readonly_fields = (
        "id",
        "assignment",
        "answer",
        "local_date",
        "user",
        "question_stable_key",
        "created_at",
    )
    can_delete = False


@admin.register(MonthlyInsight)
class MonthlyInsightAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "year", "month", "status", "revealed_day_count", "model", "completed_at")
    list_filter = ("status", "year", "month")
    search_fields = ("id", "couple__id", "provider_response_id")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MonthlyInsightInputInline]


@admin.register(MonthlyInsightInput)
class MonthlyInsightInputAdmin(admin.ModelAdmin):
    list_display = ("id", "insight", "local_date", "user", "question_stable_key")
    search_fields = ("id", "insight__id", "assignment__id", "user__email", "question_stable_key")
    readonly_fields = ("id", "created_at")
