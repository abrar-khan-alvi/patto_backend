from rest_framework import serializers

from apps.daily.models import CoupleStreak, DailyAnswer, DailyAssignment, DailyQuestion
from apps.daily.services import daily_assignment_is_revealed, streak_for_couple


class DailyQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyQuestion
        fields = ["id", "stable_key", "prompt", "category"]


class DailyAnswerSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = DailyAnswer
        fields = ["id", "user_id", "user_email", "text_answer", "answered_at"]


class CoupleStreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoupleStreak
        fields = ["current_count", "longest_count", "last_completed_date"]


class DailyAssignmentSerializer(serializers.ModelSerializer):
    question = DailyQuestionSerializer(read_only=True)
    is_revealed = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()

    class Meta:
        model = DailyAssignment
        fields = ["id", "local_date", "timezone", "status", "is_revealed", "question", "streak", "created_at"]

    def get_is_revealed(self, obj):
        return daily_assignment_is_revealed(obj)

    def get_streak(self, obj):
        return CoupleStreakSerializer(streak_for_couple(obj.couple)).data


class DailyAssignmentDetailSerializer(serializers.Serializer):
    assignment = DailyAssignmentSerializer()
    answers = DailyAnswerSerializer(many=True)


class DailyAnswerSubmitSerializer(serializers.Serializer):
    text_answer = serializers.CharField(max_length=4000, trim_whitespace=True)
