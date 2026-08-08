from rest_framework import serializers

from apps.discussions.models import DiscussionMessage, DiscussionThread, MediationRequest, MediationResponse


class DiscussionThreadCreateSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=False)
    analysis_run_id = serializers.UUIDField(required=False)
    title = serializers.CharField(required=False, allow_blank=True, max_length=180)


class DiscussionMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)


class DiscussionMessageSerializer(serializers.ModelSerializer):
    author_id = serializers.UUIDField(source="author.id", read_only=True)
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = DiscussionMessage
        fields = ["id", "sender_type", "author_id", "author_email", "body", "metadata", "created_at"]


class MediationResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediationResponse
        fields = ["id", "message", "content", "model", "metadata", "created_at"]


class MediationRequestSerializer(serializers.ModelSerializer):
    response = MediationResponseSerializer(read_only=True)

    class Meta:
        model = MediationRequest
        fields = [
            "id",
            "status",
            "context_message_count",
            "failure_code",
            "failure_message",
            "response",
            "created_at",
            "updated_at",
        ]


class DiscussionThreadSerializer(serializers.ModelSerializer):
    messages = DiscussionMessageSerializer(many=True, read_only=True)
    mediation_requests = MediationRequestSerializer(many=True, read_only=True)

    class Meta:
        model = DiscussionThread
        fields = [
            "id",
            "session",
            "analysis_run",
            "title",
            "status",
            "created_by",
            "archived_at",
            "messages",
            "mediation_requests",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DiscussionThreadListSerializer(serializers.ModelSerializer):
    latest_message = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = ["id", "session", "analysis_run", "title", "status", "latest_message", "created_at", "updated_at"]

    def get_latest_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        return None if message is None else DiscussionMessageSerializer(message).data
