from rest_framework import serializers

from apps.notifications.models import Device, Notification, NotificationDelivery, NotificationPreference


class DeviceRegisterSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=Device.Platform.choices)
    token = serializers.CharField(max_length=512)
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "platform", "name", "is_active", "revoked_at", "created_at", "updated_at"]


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=NotificationPreference.Category.choices)
    enabled = serializers.BooleanField()


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["id", "category", "enabled", "created_at", "updated_at"]


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = ["id", "device", "status", "provider", "provider_message_id", "attempts", "sent_at", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    deliveries = NotificationDeliverySerializer(many=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "category",
            "event_key",
            "title",
            "body",
            "data",
            "status",
            "read_at",
            "suppressed_at",
            "deliveries",
            "created_at",
            "updated_at",
        ]
