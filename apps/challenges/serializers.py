from rest_framework import serializers

from apps.challenges.models import Challenge, ChallengeAssignment, ChallengeMemberCompletion


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = [
            "id",
            "stable_key",
            "title",
            "description",
            "instructions",
            "category",
            "source",
            "duration_days",
        ]


class ChallengeMemberCompletionSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ChallengeMemberCompletion
        fields = ["id", "user_id", "user_email", "note", "completed_at"]


class ChallengeAssignmentSerializer(serializers.ModelSerializer):
    challenge = ChallengeSerializer(read_only=True)
    member_completions = ChallengeMemberCompletionSerializer(many=True, read_only=True)

    class Meta:
        model = ChallengeAssignment
        fields = [
            "id",
            "challenge",
            "source",
            "status",
            "starts_on",
            "due_on",
            "safety_flags",
            "fallback_reason",
            "completed_at",
            "member_completions",
            "created_at",
        ]


class ChallengeAssignmentCreateSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()


class ChallengeCompletionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
