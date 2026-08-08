from rest_framework import serializers

from apps.accounts.models import EmailOTP, UserProfile


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    preferred_language = serializers.CharField(required=False, max_length=12, default="en")
    timezone = serializers.CharField(required=False, max_length=64, default="UTC")


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=EmailOTP.Purpose.choices, default=EmailOTP.Purpose.LOGIN)


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    purpose = serializers.ChoiceField(choices=EmailOTP.Purpose.choices, default=EmailOTP.Purpose.LOGIN)


class TokenRefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    email_verified_at = serializers.DateTimeField(source="user.email_verified_at", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "email",
            "email_verified_at",
            "display_name",
            "pronouns",
            "avatar",
            "preferred_language",
            "timezone",
            "onboarding_completed_at",
        ]
        read_only_fields = ["id", "email", "email_verified_at", "avatar"]

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        user_fields = []
        if instance.user.preferred_language != instance.preferred_language:
            instance.user.preferred_language = instance.preferred_language
            user_fields.append("preferred_language")
        if instance.user.timezone != instance.timezone:
            instance.user.timezone = instance.timezone
            user_fields.append("timezone")
        if user_fields:
            user_fields.append("updated_at")
            instance.user.save(update_fields=user_fields)
        return instance


class AvatarUploadSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=True)

    class Meta:
        model = UserProfile
        fields = ["avatar"]
