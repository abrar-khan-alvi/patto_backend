from django.urls import path

from apps.notifications.views import (
    DeviceListRegisterView,
    DeviceRevokeView,
    NotificationListView,
    NotificationPreferenceView,
    NotificationReadView,
)

urlpatterns = [
    path("devices/", DeviceListRegisterView.as_view(), name="device-list-register"),
    path("devices/<uuid:device_id>/revoke/", DeviceRevokeView.as_view(), name="device-revoke"),
    path("notification-preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<uuid:notification_id>/read/", NotificationReadView.as_view(), name="notification-read"),
]
