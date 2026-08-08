from rest_framework import serializers

from apps.coach.models import CoachConversation, CoachMessage, CoachParticipant, CoachRun


class CoachParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CoachParticipant
        fields = ["id", "user_id", "user_email", "role", "joined_at"]


class CoachMessageSerializer(serializers.ModelSerializer):
    author_id = serializers.UUIDField(source="author.id", read_only=True)
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = CoachMessage
        fields = [
            "id",
            "sender_type",
            "author_id",
            "author_email",
            "body",
            "render_as",
            "explicitly_shared_with_partner",
            "shared_at",
            "metadata",
            "created_at",
        ]


class CoachConversationSerializer(serializers.ModelSerializer):
    participants = CoachParticipantSerializer(many=True, read_only=True)
    messages = CoachMessageSerializer(many=True, read_only=True)

    class Meta:
        model = CoachConversation
        fields = ["id", "scope", "couple", "owner", "title", "status", "participants", "messages", "created_at", "updated_at"]
        read_only_fields = ["couple", "owner"]


class CoachConversationCreateSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=CoachConversation.Scope.choices)
    title = serializers.CharField(required=False, allow_blank=True, max_length=180)


class CoachMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)


class CoachRunSerializer(serializers.ModelSerializer):
    response_message = CoachMessageSerializer(read_only=True)

    class Meta:
        model = CoachRun
        fields = [
            "id",
            "status",
            "model",
            "provider_response_id",
            "response_message",
            "context_message_ids",
            "output",
            "safety_flags",
            "usage",
            "error_code",
            "error_message",
            "created_at",
        ]
