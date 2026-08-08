from django.contrib import admin

from apps.analysis.models import AnalysisRun, AlignmentDimension, ConversationStarter, ProposedClause, TopicAnalysis


class AlignmentDimensionInline(admin.TabularInline):
    model = AlignmentDimension
    extra = 0
    readonly_fields = ("created_at",)


class ConversationStarterInline(admin.TabularInline):
    model = ConversationStarter
    extra = 0
    readonly_fields = ("created_at",)


class ProposedClauseInline(admin.TabularInline):
    model = ProposedClause
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = ("session", "version", "status", "deterministic_similarity_score", "created_at")
    list_filter = ("status",)
    search_fields = ("session__id", "analysis_job__id", "ai_result__id")
    readonly_fields = ("active_member_ids", "created_at", "updated_at")
    inlines = [AlignmentDimensionInline, ConversationStarterInline, ProposedClauseInline]


@admin.register(TopicAnalysis)
class TopicAnalysisAdmin(admin.ModelAdmin):
    list_display = ("run", "alignment_score", "confidence_score", "created_at")
    search_fields = ("run__id", "summary")
    readonly_fields = ("common_ground", "differences", "sensitive_areas", "safety_flags", "created_at", "updated_at")


@admin.register(ProposedClause)
class ProposedClauseAdmin(admin.ModelAdmin):
    list_display = ("run", "status", "sort_order", "created_at")
    list_filter = ("status", "source")
    search_fields = ("clause_text", "run__id")
    readonly_fields = ("created_at", "updated_at")
