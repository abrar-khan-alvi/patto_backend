from rest_framework import serializers

from apps.responses.models import TopicAnalysisJob, TopicMemberCompletion, TopicResponse, TopicSession, TopicSyncEvent


class TopicSessionCreateSerializer(serializers.Serializer):
    topic_kind = serializers.ChoiceField(choices=TopicSession.TopicKind.choices)
    topic_id = serializers.UUIDField()


class TopicSessionSerializer(serializers.ModelSerializer):
    is_released = serializers.SerializerMethodField()

    class Meta:
        model = TopicSession
        fields = [
            "id",
            "topic_kind",
            "topic_stable_key",
            "topic_version",
            "expected_question_count",
            "built_in_topic",
            "custom_topic",
            "is_released",
            "created_at",
        ]

    def get_is_released(self, obj):
        from apps.responses.services import session_is_released

        return session_is_released(obj)


class TopicAnswerSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    selected_option_id = serializers.UUIDField(required=False, allow_null=True)
    text_answer = serializers.CharField(required=False, allow_blank=True)


class TopicAnswersSubmitSerializer(serializers.Serializer):
    answers = TopicAnswerSerializer(many=True)


class TopicResponseSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = TopicResponse
        fields = [
            "id",
            "user_id",
            "user_email",
            "question_stable_key",
            "question_version",
            "selected_option_key",
            "text_answer",
            "answered_at",
        ]


class TopicMemberCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicMemberCompletion
        fields = ["id", "user", "completed_at", "locked_at"]


class TopicAnalysisJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicAnalysisJob
        fields = ["id", "status", "queued_at", "started_at", "finished_at", "failure_reason"]


class TopicSyncEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicSyncEvent
        fields = ["id", "event_type", "metadata", "created_at"]
