from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import Device, Notification, NotificationPreference
from apps.notifications.serializers import (
    DeviceRegisterSerializer,
    DeviceSerializer,
    NotificationPreferenceSerializer,
    NotificationPreferenceUpdateSerializer,
    NotificationSerializer,
)
from apps.notifications.services import mark_notification_read, register_device, revoke_device, set_notification_preference


class DeviceListRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = Device.objects.filter(user=request.user).order_by("-created_at")
        return Response({"results": DeviceSerializer(devices, many=True).data})

    def post(self, request):
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = register_device(
            user=request.user,
            platform=serializer.validated_data["platform"],
            token=serializer.validated_data["token"],
            name=serializer.validated_data.get("name", ""),
        )
        return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)


class DeviceRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        device = get_object_or_404(Device, id=device_id, user=request.user)
        device = revoke_device(device=device, user=request.user)
        return Response(DeviceSerializer(device).data)


class NotificationPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preferences = NotificationPreference.objects.filter(user=request.user).order_by("category")
        return Response({"results": NotificationPreferenceSerializer(preferences, many=True).data})

    def patch(self, request):
        serializer = NotificationPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preference = set_notification_preference(
            user=request.user,
            category=serializer.validated_data["category"],
            enabled=serializer.validated_data["enabled"],
        )
        return Response(NotificationPreferenceSerializer(preference).data)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).prefetch_related("deliveries").order_by("-created_at")
        return Response({"results": NotificationSerializer(notifications, many=True).data})


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification = mark_notification_read(notification=notification, user=request.user)
        return Response(NotificationSerializer(notification).data)
