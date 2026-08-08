from rest_framework import serializers

from apps.billing.models import IAPPurchaseAccount, Subscription
from apps.couples.models import Entitlement


class DevelopmentIAPVerifySerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=IAPPurchaseAccount.Platform.choices)
    receipt = serializers.JSONField()


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id",
            "platform",
            "product_id",
            "original_transaction_id",
            "latest_transaction_id",
            "status",
            "starts_at",
            "expires_at",
            "revoked_at",
            "updated_at",
        ]


class EntitlementSerializer(serializers.ModelSerializer):
    active = serializers.SerializerMethodField()

    class Meta:
        model = Entitlement
        fields = ["id", "source", "external_reference", "starts_at", "expires_at", "revoked_at", "active"]

    def get_active(self, obj):
        return obj.is_active()
