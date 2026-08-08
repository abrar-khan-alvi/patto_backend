from rest_framework import serializers

from apps.ai.models import AIFollowUpQuestion


class AIFollowUpQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIFollowUpQuestion
        fields = [
            "id",
            "session",
            "status",
            "model",
            "topic_stable_key",
            "topic_version",
            "follow_up_question",
            "internal_reason",
            "skip",
            "skip_reason",
            "refusal_reason",
            "error_code",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
