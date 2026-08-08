from rest_framework import serializers

from apps.insights.models import MonthlyInsight, MonthlyInsightInput


class MonthlyInsightRunSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)


class MonthlyInsightInputSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model = MonthlyInsightInput
        fields = [
            "id",
            "assignment",
            "answer",
            "local_date",
            "user_id",
            "question_stable_key",
            "question_prompt",
            "text_answer",
        ]


class MonthlyInsightSerializer(serializers.ModelSerializer):
    prompt_key = serializers.CharField(source="prompt_version.key", read_only=True)
    prompt_version_number = serializers.IntegerField(source="prompt_version.version", read_only=True)

    class Meta:
        model = MonthlyInsight
        fields = [
            "id",
            "year",
            "month",
            "input_start_date",
            "input_end_date",
            "minimum_revealed_days",
            "revealed_day_count",
            "status",
            "model",
            "prompt_key",
            "prompt_version_number",
            "sections",
            "safety_flags",
            "usage",
            "error_code",
            "error_message",
            "queued_at",
            "started_at",
            "completed_at",
            "created_at",
        ]
