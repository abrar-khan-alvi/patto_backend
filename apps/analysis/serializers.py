from rest_framework import serializers

from apps.analysis.models import AnalysisRun, AlignmentDimension, ConversationStarter, ProposedClause, TopicAnalysis


class TopicAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicAnalysis
        fields = [
            "summary",
            "alignment_score",
            "confidence_score",
            "common_ground",
            "differences",
            "sensitive_areas",
            "safety_flags",
        ]


class AlignmentDimensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlignmentDimension
        fields = ["id", "label", "score", "explanation", "sort_order"]


class ConversationStarterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationStarter
        fields = ["id", "prompt", "sort_order"]


class ProposedClauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposedClause
        fields = ["id", "clause_text", "source", "status", "sort_order"]


class AnalysisRunSerializer(serializers.ModelSerializer):
    topic_analysis = TopicAnalysisSerializer(read_only=True)
    alignment_dimensions = AlignmentDimensionSerializer(many=True, read_only=True)
    conversation_starters = ConversationStarterSerializer(many=True, read_only=True)
    proposed_clauses = ProposedClauseSerializer(many=True, read_only=True)

    class Meta:
        model = AnalysisRun
        fields = [
            "id",
            "version",
            "status",
            "topic_stable_key",
            "topic_version",
            "active_member_ids",
            "deterministic_similarity_score",
            "failure_code",
            "failure_message",
            "started_at",
            "completed_at",
            "topic_analysis",
            "alignment_dimensions",
            "conversation_starters",
            "proposed_clauses",
            "created_at",
        ]
