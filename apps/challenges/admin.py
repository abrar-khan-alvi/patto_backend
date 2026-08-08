from django.contrib import admin

from apps.challenges.models import Challenge, ChallengeAssignment, ChallengeMemberCompletion


class ChallengeMemberCompletionInline(admin.TabularInline):
    model = ChallengeMemberCompletion
    extra = 0
    readonly_fields = ("id", "user", "note", "completed_at", "created_at", "updated_at")
    can_delete = False


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("stable_key", "title", "category", "source", "duration_days", "is_active", "sort_order")
    list_filter = ("source", "category", "is_active")
    search_fields = ("stable_key", "title", "description")
    ordering = ("sort_order", "stable_key")


@admin.register(ChallengeAssignment)
class ChallengeAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "challenge", "source", "status", "starts_on", "due_on", "completed_at")
    list_filter = ("source", "status")
    search_fields = ("id", "couple__id", "challenge__stable_key")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ChallengeMemberCompletionInline]


@admin.register(ChallengeMemberCompletion)
class ChallengeMemberCompletionAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "couple", "user", "completed_at")
    search_fields = ("id", "assignment__id", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
