from rest_framework import serializers

from apps.billing.serializers import SubscriptionSerializer
from apps.profile_features.models import (
    AccountDeletionRequest,
    DataExportRequest,
    Referral,
    ReferralCode,
    ReferralReward,
    SubscriptionManagementRequest,
    SupportTicket,
    SupportTicketMessage,
)


class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralCode
        fields = ["id", "code", "is_active", "created_at"]


class ReferralApplySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class ReferralRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralReward
        fields = ["id", "reward_type", "status", "metadata", "granted_at", "created_at"]


class ReferralSerializer(serializers.ModelSerializer):
    referrer_email = serializers.EmailField(source="referrer.email", read_only=True)
    referred_user_email = serializers.EmailField(source="referred_user.email", read_only=True)
    reward = ReferralRewardSerializer(read_only=True)

    class Meta:
        model = Referral
        fields = ["id", "referrer_email", "referred_user_email", "status", "verified_at", "reward", "created_at"]


class SupportTicketMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicketMessage
        fields = ["id", "sender_type", "body", "created_at"]


class SupportTicketSerializer(serializers.ModelSerializer):
    messages = SupportTicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = ["id", "category", "subject", "status", "messages", "created_at", "updated_at"]


class SupportTicketCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=SupportTicket.Category.choices)
    subject = serializers.CharField(max_length=180)
    body = serializers.CharField(max_length=5000, trim_whitespace=True)


class SupportTicketMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)


class SubscriptionManagementSerializer(serializers.Serializer):
    current_subscription = SubscriptionSerializer(allow_null=True)
    platform_management = serializers.DictField()


class SubscriptionManagementRequestCreateSerializer(serializers.Serializer):
    request_type = serializers.ChoiceField(choices=SubscriptionManagementRequest.RequestType.choices)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=20)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=3000)


class SubscriptionManagementRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionManagementRequest
        fields = ["id", "request_type", "platform", "notes", "created_at"]


class DataExportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataExportRequest
        fields = ["id", "status", "checksum_sha256", "byte_size", "requested_at", "completed_at", "failure_reason"]


class AccountDeletionRequestCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    confirmation_email = serializers.EmailField()

    def validate_confirmation_email(self, value):
        request = self.context.get("request")
        if request is not None and value.strip().lower() != request.user.email.lower():
            raise serializers.ValidationError("Confirm your current account email before requesting deletion.")
        return value.strip().lower()


class AccountDeletionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountDeletionRequest
        fields = [
            "id",
            "status",
            "reason",
            "couple_action",
            "requested_at",
            "scheduled_for",
            "sessions_revoked_at",
            "billing_updated_at",
            "partner_notified_at",
            "processed_at",
            "completed_at",
            "failure_reason",
        ]
